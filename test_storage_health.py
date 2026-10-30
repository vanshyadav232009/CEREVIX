import subprocess
import json

command = """
$disks = Get-PhysicalDisk

$result = foreach ($disk in $disks) {
    $health = $null

    try {
        $health = $disk | Get-StorageReliabilityCounter |
            Select-Object Temperature, Wear, PowerOnHours
    }
    catch {}

    [PSCustomObject]@{
        Model = $disk.FriendlyName
        Health = $disk.HealthStatus
        Status = $disk.OperationalStatus
        SizeGB = [math]::Round($disk.Size / 1GB, 2)
        Reliability = $health
    }
}

$result | ConvertTo-Json -Depth 4
"""

try:
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            command
        ],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode == 0 and result.stdout.strip():
        print(json.dumps(
            json.loads(result.stdout),
            indent=4
        ))
    else:
        print("PowerShell error:")
        print(result.stderr or "No disk information returned.")

except Exception as error:
    print(f"Diagnostic failed: {error}")