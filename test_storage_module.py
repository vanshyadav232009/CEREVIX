from core.storage import get_storage_info

disks = get_storage_info()

print("\n========== NEXUS STORAGE TEST ==========")

if disks:
    for disk in disks:
        print(f"Model: {disk['model']}")
        print(f"Health: {disk['health']}")
        print(f"Status: {disk['status']}")
        print(f"Capacity: {disk['capacity_gb']} GB")
        print("--------------------------------")
else:
    print("Storage information unavailable.")

print("========== TEST COMPLETE ==========")