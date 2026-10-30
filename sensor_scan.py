import json
import urllib.request


URL = "http://localhost:8085/data.json"


def scan_sensors(node, path=""):

    name = node.get("Text", "")
    current_path = f"{path} / {name}"

    if node.get("Type") == "Temperature":
        print(
            f"{current_path}\n"
            f"    Value: {node.get('Value')}\n"
        )

    for child in node.get("Children", []):
        scan_sensors(child, current_path)


try:
    with urllib.request.urlopen(URL, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))

    print("\n========== NEXUS SENSOR SCANNER ==========\n")

    scan_sensors(data)

    print("\n========== SCAN COMPLETE ==========")

except Exception as error:
    print(f"Connection failed: {error}")