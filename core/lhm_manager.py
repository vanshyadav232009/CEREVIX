import ctypes
import secrets
import socket
import subprocess
import sys
import time

from pathlib import Path


# Application directory
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent


# Bundled LibreHardwareMonitor
LHM_PATH = (
    APP_DIR
    / "third_party"
    / "LibreHardwareMonitor"
    / "LibreHardwareMonitor.exe"
)


# Helper paths
HELPER_SCRIPT = Path(__file__).with_name("lhm_elevated_helper.py")
HELPER_EXE = APP_DIR / "LHMHelper.exe"

SENSOR_URL = "http://127.0.0.1:8085/data.json"

STARTUP_TIMEOUT = 30
HELPER_TIMEOUT = 120
POLL_INTERVAL = 0.5


class LHMManager:

    def __init__(self):
        self.connection = None
        self.started_by_cerevix = False
        self.process_pid = None
        self._token = None

    @staticmethod
    def is_server_available():
        try:
            with socket.create_connection(
                ("127.0.0.1", 8085), timeout=1
            ):
                return True
        except OSError:
            return False

    @staticmethod
    def is_process_running():
        try:
            result = subprocess.run(
                [
                    "tasklist",
                    "/FI",
                    "IMAGENAME eq LibreHardwareMonitor.exe",
                    "/NH"
                ],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            return "LibreHardwareMonitor.exe" in result.stdout

        except Exception:
            return False

    def start(self):

        if self.is_server_available():
            print("LHM sensor server already available.")
            return True

        if self.is_process_running():
            print("Existing LHM process detected.")
            return self._wait_for_server()

        if not LHM_PATH.is_file():
            print(f"LHM executable not found: {LHM_PATH}")
            return False

        frozen = getattr(sys, "frozen", False)

        if frozen:
            if not HELPER_EXE.is_file():
                print(f"LHM helper executable not found: {HELPER_EXE}")
                return False
        else:
            if not HELPER_SCRIPT.is_file():
                print(f"LHM helper script not found: {HELPER_SCRIPT}")
                return False

        token = secrets.token_hex(16)
        self._token = token

        try:
            with socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            ) as server:

                server.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_REUSEADDR,
                    1
                )

                server.bind(("127.0.0.1", 0))
                server.listen(1)
                server.settimeout(HELPER_TIMEOUT)

                port = server.getsockname()[1]

                if frozen:
                    launch_file = str(HELPER_EXE)
                    parameters = subprocess.list2cmdline([
                        str(port),
                        token,
                        str(LHM_PATH)
                    ])
                else:
                    launch_file = sys.executable
                    parameters = subprocess.list2cmdline([
                        str(HELPER_SCRIPT),
                        str(port),
                        token,
                        str(LHM_PATH)
                    ])

                result = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    launch_file,
                    parameters,
                    str(APP_DIR),
                    0
                )

                if result <= 32:
                    print(f"Could not launch elevated helper: {result}")
                    return False

                print("Waiting for elevated LHM helper...")

                connection, _ = server.accept()
                connection.settimeout(10)

                with connection.makefile(
                    "r", encoding="utf-8"
                ) as reader:
                    message = reader.readline().strip()

                expected_prefix = f"READY:{token}:"

                if not message.startswith(expected_prefix):
                    connection.close()
                    print("Invalid helper response.")
                    return False

                self.process_pid = int(
                    message[len(expected_prefix):]
                )

                connection.settimeout(None)

                self.connection = connection
                self.started_by_cerevix = True

                print(f"LHM launched. PID: {self.process_pid}")

        except Exception as error:
            print(f"LHM startup error: {error}")
            return False

        if self._wait_for_server():
            return True

        print("LHM failed to initialise. Cleaning up.")
        self.stop()
        return False

    def _wait_for_server(self):

        start_time = time.monotonic()

        while time.monotonic() - start_time < STARTUP_TIMEOUT:

            if self.is_server_available():
                print("LHM sensor server ready.")
                return True

            time.sleep(POLL_INTERVAL)

        print("LHM sensor server startup timed out.")
        return False

    def stop(self):

        if not self.started_by_cerevix:
            return

        print("Stopping CEREVIX-managed LHM instance...")

        try:
            if self.connection is not None:
                self.connection.sendall(
                    f"STOP:{self._token}\n".encode("utf-8")
                )

        except Exception as error:
            print(f"LHM shutdown communication error: {error}")

        finally:
            if self.connection is not None:
                self.connection.close()

            self.connection = None
            self.started_by_cerevix = False
            self.process_pid = None
            self._token = None