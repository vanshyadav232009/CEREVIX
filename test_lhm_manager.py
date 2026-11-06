from core.lhm_manager import LHMManager


manager = LHMManager()

print("\n--- CEREVIX LHM MANAGER TEST ---")

started = manager.start()

if started:
    print("\nLHM sensor server is available.")

    input("\nPress ENTER to test shutdown...")

    manager.stop()

    print("\nShutdown command sent.")

else:
    print("\nLHM startup failed. Check the messages above.")