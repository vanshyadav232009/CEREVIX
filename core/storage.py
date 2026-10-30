import subprocess
import json


def get_storage_info():
    command = """
    Get-PhysicalDisk |
    Select-Object FriendlyName, HealthStatus,
    OperationalStatus, Size |
    ConvertTo-Json -Compress
    """

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command
            ],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        if result.returncode != 0 or not result.stdout.strip():
            return None

        disks = json.loads(result.stdout)

        if isinstance(disks, dict):
            disks = [disks]

        return [
            {
                "model": disk.get("FriendlyName", "Unknown"),
                "health": disk.get("HealthStatus", "Unknown"),
                "status": disk.get("OperationalStatus", "Unknown"),
                "capacity_gb": round(
                    disk.get("Size", 0) / (1024 ** 3), 2
                )
            }
            for disk in disks
        ]

    except Exception as error:
        print(f"Storage detection error: {error}")
        return None