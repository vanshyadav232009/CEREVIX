import pynvml

try:
    pynvml.nvmlInit()

    device = pynvml.nvmlDeviceGetHandleByIndex(0)

    name = pynvml.nvmlDeviceGetName(device)

    utilization = pynvml.nvmlDeviceGetUtilizationRates(device)

    memory = pynvml.nvmlDeviceGetMemoryInfo(device)

    clock = pynvml.nvmlDeviceGetClockInfo(
        device,
        pynvml.NVML_CLOCK_GRAPHICS
    )

    print("\n========== NEXUS GPU TEST ==========\n")

    print(f"GPU: {name}")
    print(f"GPU Utilisation: {utilization.gpu}%")
    print(f"VRAM Used: {memory.used / (1024**3):.2f} GB")
    print(f"VRAM Total: {memory.total / (1024**3):.2f} GB")
    print(f"GPU Clock: {clock} MHz")

    print("\n========== TEST COMPLETE ==========")

except Exception as error:
    print(f"GPU detection failed: {error}")

finally:
    try:
        pynvml.nvmlShutdown()
    except Exception:
        pass