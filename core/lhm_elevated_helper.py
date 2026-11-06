import socket
import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 4:
        return 1

    port = int(sys.argv[1])
    token = sys.argv[2]
    executable = Path(sys.argv[3])

    if not executable.is_file():
        return 2

    process = None
    connection = None

    try:
        startup_info = subprocess.STARTUPINFO()
        startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup_info.wShowWindow = 7

        process = subprocess.Popen(
            [str(executable)],
            cwd=str(executable.parent),
            startupinfo=startup_info
        )

        connection = socket.create_connection(
            ("127.0.0.1", port),
            timeout=30
        )

        connection.settimeout(None)

        connection.sendall(
            f"READY:{token}:{process.pid}\n".encode("utf-8")
        )

        with connection.makefile("r", encoding="utf-8") as reader:
            command = reader.readline().strip()

        if command == f"STOP:{token}":
            process.terminate()

            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

        return 0

    except Exception as error:
        print(f"LHM helper error: {error}")
        return 3

    finally:
        if connection is not None:
            connection.close()

        if process is not None and process.poll() is None:
            process.terminate()

            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    sys.exit(main())