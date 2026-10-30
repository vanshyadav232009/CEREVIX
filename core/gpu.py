import pynvml


def get_gpu_stats():
    try:
        pynvml.nvmlInit()

        device = pynvml.nvmlDeviceGetHandleByIndex(0)

        utilization = pynvml.nvmlDeviceGetUtilizationRates(device)
        memory = pynvml.nvmlDeviceGetMemoryInfo(device)
        clock = pynvml.nvmlDeviceGetClockInfo(
            device, pynvml.NVML_CLOCK_GRAPHICS
        )

        return {
            "utilisation": utilization.gpu,
            "vram_used": memory.used / (1024 ** 3),
            "vram_total": memory.total / (1024 ** 3),
            "clock": clock
        }

    except Exception as error:
        print(f"GPU sensor error: {error}")
        return None

    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass