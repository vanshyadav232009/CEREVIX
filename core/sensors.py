import json
import urllib.request


SENSOR_URL = "http://localhost:8085/data.json"


def get_all_sensors():

    try:
        with urllib.request.urlopen(
            SENSOR_URL, timeout=3
        ) as response:

            data = json.loads(
                response.read().decode("utf-8")
            )

        sensors = {}

        def scan(node, path=""):

            name = node.get("Text", "")
            current_path = f"{path}/{name}"

            if node.get("Type") == "Temperature":

                sensors[current_path] = node.get("Value")

            for child in node.get("Children", []):
                scan(child, current_path)

        scan(data)

        return sensors

    except Exception as error:
        print(f"Sensor error: {error}")
        return {}


def find_sensor(sensors, sensor_name):

    for path, value in sensors.items():

        if path.endswith("/" + sensor_name):
            try:
                return float(value.replace(" °C", ""))
            except (ValueError, AttributeError):
                pass

    return None


def get_hardware_temperatures():

    sensors = get_all_sensors()

    return {
        "cpu": find_sensor(sensors, "Core (Tctl/Tdie)"),
        "gpu": find_sensor(sensors, "GPU Core"),
        "gpu_hotspot": find_sensor(sensors, "GPU Hot Spot"),
        "gpu_memory": find_sensor(sensors, "GPU Memory Junction"),
        "ssd": find_sensor(sensors, "Composite Temperature")
    }