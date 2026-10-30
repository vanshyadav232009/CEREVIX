from core.gpu import get_gpu_stats

stats = get_gpu_stats()

print("\n========== NEXUS GPU MODULE TEST ==========")

if stats:
    print(f"GPU Utilisation: {stats['utilisation']}%")
    print(f"VRAM Used: {stats['vram_used']:.2f} GB")
    print(f"VRAM Total: {stats['vram_total']:.2f} GB")
    print(f"GPU Clock: {stats['clock']} MHz")
else:
    print("GPU statistics unavailable.")

print("========== TEST COMPLETE ==========")