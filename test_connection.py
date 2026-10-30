from core.sensors import get_hardware_temperatures

print("\n========== NEXUS HARDWARE STATUS ==========\n")

temperatures = get_hardware_temperatures()

for component, temperature in temperatures.items():

    if temperature is not None:
        print(f"{component.upper():15} {temperature:.1f} °C")
    else:
        print(f"{component.upper():15} Sensor unavailable")

print("\n===========================================")