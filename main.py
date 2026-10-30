import sys
from collections import deque
from datetime import datetime
import time

import psutil
import pyqtgraph as pg

from PySide6.QtCore import Qt, QTimer, QObject, QThread, Signal, Slot, QSettings
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QScrollArea,
    QGridLayout,
    QComboBox,
    QCheckBox,
)

from core.sensors import get_hardware_temperatures
from core.gpu import get_gpu_stats
from core.storage import get_storage_info
from core.config import APP_NAME, APP_VERSION
from ui.sidebar import Sidebar
from ui.pages.page_manager import PageManager
from pathlib import Path
from PySide6.QtGui import QIcon


# ---------------- CONFIGURATION ----------------

BG = "#0B0D0C"
PANEL = "#141816"
ACCENT = "#00C781"
TEXT = "#E8EFEB"
MUTED = "#89958E"
BORDER = "#252D29"

HISTORY_LENGTH = 60
UPDATE_INTERVAL = 1000


def format_temp(value):
    """Format a temperature while handling unavailable sensors."""
    if value is None:
        return "N/A"
    return f"{value:.1f}°C"


def gb(value):
    return value / (1024 ** 3)


def format_speed(bytes_per_second):
    """Format disk throughput without excessive decimal noise."""
    if bytes_per_second is None:
        return "N/A"
    mb_per_second = bytes_per_second / (1024 ** 2)
    if mb_per_second >= 1:
        return f"{mb_per_second:.1f} MB/s"
    return f"{bytes_per_second / 1024:.0f} KB/s"


# ---------------- REUSABLE UI COMPONENTS ----------------

class HardwareCard(QFrame):
    def __init__(self, title, subtitle):
        super().__init__()
        self.setObjectName("hardwareCard")
        self.setStyleSheet(f"""
            QFrame#hardwareCard {{
                background-color: {PANEL};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(9)

        self.title = QLabel(title)
        self.title.setStyleSheet(
            f"color: {MUTED}; font-size: 12px; border: none;"
        )

        self.value = QLabel("--")
        self.value.setStyleSheet(
            f"color: {TEXT}; font-size: 28px; font-weight: 600; border: none;"
        )

        self.subtitle = QLabel(subtitle)
        self.subtitle.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; border: none;"
        )

        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.subtitle)
        layout.addStretch()


class TemperatureGraph(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("graphPanel")
        self.setStyleSheet(f"""
            QFrame#graphPanel {{
                background-color: {PANEL};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
        """)

        self.history = deque(maxlen=HISTORY_LENGTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {TEXT}; font-size: 12px; font-weight: 600; border: none;"
        )

        self.current_value = QLabel("N/A")
        self.current_value.setStyleSheet(
            f"color: {ACCENT}; font-size: 14px; font-weight: 600; border: none;"
        )

        header.addWidget(title_label)
        header.addStretch()
        header.addWidget(self.current_value)
        layout.addLayout(header)

        self.plot = pg.PlotWidget()
        self.plot.setBackground(PANEL)
        self.plot.setMinimumHeight(175)
        self.plot.showGrid(x=True, y=True, alpha=0.12)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.setMenuEnabled(False)
        self.plot.setLabel("left", "Temperature", units="°C")
        self.plot.setLabel("bottom", "Seconds ago")
        self.plot.setXRange(-59, 0, padding=0)
        self.plot.setYRange(0, 100, padding=0)
        self.plot.getAxis("left").setTextPen(MUTED)
        self.plot.getAxis("bottom").setTextPen(MUTED)

        self.curve = self.plot.plot(
            [],
            [],
            pen=pg.mkPen(color=ACCENT, width=2),
            connect="finite",
        )
        layout.addWidget(self.plot)

    def add_reading(self, temperature):
        self.current_value.setText(format_temp(temperature))

        value = float(temperature) if temperature is not None else float("nan")
        self.history.append(value)

        values = list(self.history)
        x_values = list(range(-len(values) + 1, 1))
        self.curve.setData(x_values, values)


class PercentageGraph(QFrame):
    """Lightweight percentage history chart with a fixed-size sample buffer."""

    def __init__(self, title="RAM UTILISATION", axis_label="Memory utilisation"):
        super().__init__()
        self.setObjectName("graphPanel")
        self.setStyleSheet(f"""
            QFrame#graphPanel {{
                background-color: {PANEL};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
        """)

        self.history = deque(maxlen=HISTORY_LENGTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {TEXT}; font-size: 12px; font-weight: 600; border: none;"
        )

        self.current_value = QLabel("N/A")
        self.current_value.setStyleSheet(
            f"color: {ACCENT}; font-size: 14px; font-weight: 600; border: none;"
        )

        header.addWidget(title_label)
        header.addStretch()
        header.addWidget(self.current_value)
        layout.addLayout(header)

        self.plot = pg.PlotWidget()
        self.plot.setBackground(PANEL)
        self.plot.setMinimumHeight(150)
        self.plot.showGrid(x=True, y=True, alpha=0.12)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.setMenuEnabled(False)
        self.plot.setLabel("left", axis_label, units="%")
        self.plot.setLabel("bottom", "Seconds ago")
        self.plot.setXRange(-59, 0, padding=0)
        self.plot.setYRange(0, 100, padding=0)
        self.plot.getAxis("left").setTextPen(MUTED)
        self.plot.getAxis("bottom").setTextPen(MUTED)

        self.curve = self.plot.plot(
            [],
            [],
            pen=pg.mkPen(color=ACCENT, width=2),
            connect="finite",
        )
        layout.addWidget(self.plot)

    def add_reading(self, percentage):
        if percentage is None:
            self.current_value.setText("N/A")
            value = float("nan")
        else:
            value = float(percentage)
            self.current_value.setText(f"{value:.1f}%")

        self.history.append(value)
        values = list(self.history)
        x_values = list(range(-len(values) + 1, 1))
        self.curve.setData(x_values, values)



class MetricRow(QFrame):
    """A simple label/value row used on the detailed hardware pages."""

    def __init__(self, name):
        super().__init__()
        self.setStyleSheet(
            f"background-color: {PANEL}; border: 1px solid {BORDER}; "
            "border-radius: 8px;"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)

        self.name_label = QLabel(name)
        self.name_label.setStyleSheet(
            f"color: {MUTED}; font-size: 12px; border: none;"
        )

        self.value_label = QLabel("N/A")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.value_label.setStyleSheet(
            f"color: {TEXT}; font-size: 13px; font-weight: 600; border: none;"
        )

        layout.addWidget(self.name_label)
        layout.addStretch()
        layout.addWidget(self.value_label)


# ---------------- PAGES ----------------

class OverviewPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {BG};")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {BG}; border: none; }}"
        )

        content = QWidget()
        content.setStyleSheet(f"background-color: {BG};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 26, 32, 26)
        layout.setSpacing(18)

        # Header
        header = QHBoxLayout()
        heading = QLabel("System Overview")
        heading.setStyleSheet(
            f"color: {TEXT}; font-size: 24px; font-weight: 600;"
        )

        self.clock = QLabel("--")
        self.clock.setStyleSheet(f"color: {MUTED}; font-size: 12px;")

        header.addWidget(heading)
        header.addStretch()
        header.addWidget(self.clock)
        layout.addLayout(header)

        self.status = QLabel("●  INITIALISING HARDWARE MONITOR")
        self.status.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(self.status)

        # Summary cards
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self.cpu_card = HardwareCard("PROCESSOR", "CPU utilisation")
        self.gpu_card = HardwareCard("GRAPHICS", "GPU hotspot")
        self.ram_card = HardwareCard("MEMORY", "Memory utilisation")
        self.storage_card = HardwareCard("STORAGE", "SSD temperature")

        for card in (
            self.cpu_card,
            self.gpu_card,
            self.ram_card,
            self.storage_card,
        ):
            cards_layout.addWidget(card)

        layout.addLayout(cards_layout)

        graphs_title = QLabel("PERFORMANCE HISTORY")
        graphs_title.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(graphs_title)

        graphs_layout = QHBoxLayout()
        graphs_layout.setSpacing(12)

        self.cpu_graph = TemperatureGraph("CPU TEMPERATURE")
        self.gpu_graph = TemperatureGraph("GPU TEMPERATURE")

        graphs_layout.addWidget(self.cpu_graph)
        graphs_layout.addWidget(self.gpu_graph)
        layout.addLayout(graphs_layout)

        self.ram_graph = PercentageGraph()
        layout.addWidget(self.ram_graph)

        # Compact live information panel
        info_panel = QFrame()
        info_panel.setObjectName("infoPanel")
        info_panel.setStyleSheet(f"""
            QFrame#infoPanel {{
                background-color: {PANEL};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
        """)

        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(18, 16, 18, 16)
        info_layout.setSpacing(10)

        info_title = QLabel("LIVE SYSTEM INFORMATION")
        info_title.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; font-weight: bold; border: none;"
        )

        self.system_info = QLabel("Collecting system information...")
        self.system_info.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.system_info.setStyleSheet(
            f"color: {TEXT}; font-size: 12px; border: none;"
        )

        info_layout.addWidget(info_title)
        info_layout.addWidget(self.system_info)
        layout.addWidget(info_panel)

        footer = QLabel(f"{APP_NAME}  |  Hardware Intelligence")
        footer.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        layout.addWidget(footer)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)


class DetailPage(QWidget):
    """Lightweight detail page for one hardware category."""

    def __init__(self, title, description, metric_names, extra_widget=None):
        super().__init__()
        self.setStyleSheet(f"background-color: {BG};")
        self.metric_labels = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        heading = QLabel(title)
        heading.setStyleSheet(
            f"color: {TEXT}; font-size: 24px; font-weight: 600;"
        )

        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setStyleSheet(
            f"color: {MUTED}; font-size: 12px;"
        )

        layout.addWidget(heading)
        layout.addWidget(description_label)
        layout.addSpacing(8)

        for metric_name in metric_names:
            row = MetricRow(metric_name)
            self.metric_labels[metric_name] = row.value_label
            layout.addWidget(row)

        if extra_widget is not None:
            layout.addSpacing(10)
            layout.addWidget(extra_widget)

        layout.addStretch()

    def set_metrics(self, values):
        for name, label in self.metric_labels.items():
            label.setText(str(values.get(name, "N/A")))


class SettingsPage(QWidget):
    monitoring_interval_changed = Signal(int)
    monitoring_toggled = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {BG};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        heading = QLabel("Settings")
        heading.setStyleSheet(
            f"color: {TEXT}; font-size: 24px; font-weight: 600;"
        )

        description = QLabel(
            f"Control how often {APP_NAME} refreshes hardware readings."
        )
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {MUTED}; font-size: 12px;")

        section = QFrame()
        section.setStyleSheet(
            f"background-color: {PANEL}; border: 1px solid {BORDER}; "
            "border-radius: 12px;"
        )
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(18, 16, 18, 16)
        section_layout.setSpacing(12)

        interval_title = QLabel("MONITORING INTERVAL")
        interval_title.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; font-weight: 600; "
            "border: none;"
        )

        self.interval_combo = QComboBox()
        self.interval_combo.addItem("1 second", 1000)
        self.interval_combo.addItem("2 seconds", 2000)
        self.interval_combo.addItem("5 seconds", 5000)
        self.interval_combo.setCurrentIndex(0)
        self.interval_combo.setFixedWidth(180)
        self.interval_combo.setStyleSheet(f"""
            QComboBox {{
                color: {TEXT};
                background-color: {BG};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 8px;
            }}
            QComboBox QAbstractItemView {{
                color: {TEXT};
                background-color: {PANEL};
                selection-background-color: {ACCENT};
                selection-color: {BG};
            }}
        """)
        self.interval_combo.currentIndexChanged.connect(
            self._emit_interval_change
        )

        self.monitoring_checkbox = QCheckBox("Enable hardware monitoring")
        self.monitoring_checkbox.setChecked(True)
        self.monitoring_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {TEXT};
                spacing: 9px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
            QCheckBox::indicator:checked {{
                background-color: {ACCENT};
                border: 1px solid {ACCENT};
                border-radius: 3px;
            }}
            QCheckBox::indicator:unchecked {{
                background-color: {BG};
                border: 1px solid {MUTED};
                border-radius: 3px;
            }}
        """)
        self.monitoring_checkbox.toggled.connect(
            self.monitoring_toggled.emit
        )

        self.status_label = QLabel("●  MONITORING ACTIVE")
        self.status_label.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: 600; "
            "border: none;"
        )

        section_layout.addWidget(interval_title)
        section_layout.addWidget(self.interval_combo)
        section_layout.addSpacing(4)
        section_layout.addWidget(self.monitoring_checkbox)
        section_layout.addWidget(self.status_label)

        info_section = QFrame()
        info_section.setStyleSheet(
            f"background-color: {PANEL}; border: 1px solid {BORDER}; "
            "border-radius: 12px;"
        )
        info_layout = QVBoxLayout(info_section)
        info_layout.setContentsMargins(18, 16, 18, 16)
        info_layout.setSpacing(8)

        info_title = QLabel("APPLICATION")
        info_title.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; font-weight: 600; "
            "border: none;"
        )

        version_label = QLabel(f"{APP_NAME} version  {APP_VERSION}")
        version_label.setStyleSheet(
            f"color: {TEXT}; font-size: 13px; border: none;"
        )

        efficiency_note = QLabel(
            f"{APP_NAME} reuses existing sensor readings, keeps graph history "
            "bounded, and performs drive identification only at startup."
        )
        efficiency_note.setWordWrap(True)
        efficiency_note.setStyleSheet(
            f"color: {MUTED}; font-size: 12px; border: none;"
        )

        info_layout.addWidget(info_title)
        info_layout.addWidget(version_label)
        info_layout.addWidget(efficiency_note)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(section)
        layout.addWidget(info_section)
        layout.addStretch()

    def load_preferences(self, interval_ms, monitoring_enabled):
        self.interval_combo.blockSignals(True)
        index = self.interval_combo.findData(interval_ms)
        self.interval_combo.setCurrentIndex(index if index >= 0 else 0)
        self.interval_combo.blockSignals(False)

        self.monitoring_checkbox.blockSignals(True)
        self.monitoring_checkbox.setChecked(monitoring_enabled)
        self.monitoring_checkbox.blockSignals(False)

        self.set_monitoring_status(monitoring_enabled)

    def _emit_interval_change(self):
        interval = self.interval_combo.currentData()
        if interval is not None:
            self.monitoring_interval_changed.emit(int(interval))

    def set_monitoring_status(self, enabled):
        if enabled:
            self.status_label.setText("●  MONITORING ACTIVE")
            self.status_label.setStyleSheet(
                f"color: {ACCENT}; font-size: 11px; font-weight: 600; "
                "border: none;"
            )
        else:
            self.status_label.setText("●  MONITORING PAUSED")
            self.status_label.setStyleSheet(
                f"color: {MUTED}; font-size: 11px; font-weight: 600; "
                "border: none;"
            )


# ---------------- BACKGROUND SENSOR WORKER ----------------

class SensorWorker(QObject):
    readings_ready = Signal(dict)
    finished = Signal()

    @Slot()
    def run(self):
        try:
            temperatures = get_hardware_temperatures()
            temperatures["gpu_stats"] = get_gpu_stats()
            self.readings_ready.emit(temperatures)
        except Exception as error:
            print(f"Sensor worker error: {error}")
            self.readings_ready.emit({})
        finally:
            self.finished.emit()


# ---------------- MAIN WINDOW ----------------

class Cerevix(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.resize(1200, 820)
        self.setMinimumSize(850, 600)

        # Migrate existing NEXUS preferences to CEREVIX.
        legacy_settings = QSettings("NEXUS", "NEXUS")
        self.app_settings = QSettings(APP_NAME, APP_NAME)

        for key in ("monitoring/interval", "monitoring/enabled"):
            if not self.app_settings.contains(key) and legacy_settings.contains(key):
                self.app_settings.setValue(key, legacy_settings.value(key))

        self.app_settings.sync()
        saved_interval = self.app_settings.value(
            "monitoring/interval", UPDATE_INTERVAL, type=int
        )
        self.monitoring_interval_ms = (
            saved_interval if saved_interval in (1000, 2000, 5000)
            else UPDATE_INTERVAL
        )
        self.monitoring_enabled = self.app_settings.value(
            "monitoring/enabled", True, type=bool
        )

        self.temperatures = {}
        self.gpu_stats = None
        self.cpu_usage = 0.0
        self.cpu_frequency = "N/A"
        self.logical_cores = psutil.cpu_count(logical=True) or 0
        self.physical_cores = psutil.cpu_count(logical=False) or 0
        self.memory_usage = 0.0
        self.ram_used = 0.0
        self.ram_total = 0.0
        self.disk_used = 0.0
        self.disk_total = 0.0
        self.disk_read_speed = None
        self.disk_write_speed = None
        self.disk_io_previous = psutil.disk_io_counters()
        self.disk_io_last_time = time.monotonic()

        # Query drive identity/health once at startup; never poll PowerShell.
        detected_disks = get_storage_info()
        self.storage_info = detected_disks[0] if detected_disks else None

        self.sensor_thread = None
        self.sensor_worker = None

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.page_selected.connect(self.change_page)
        main_layout.addWidget(self.sidebar)

        # Stacked page area
        self.page_manager = PageManager()
        main_layout.addWidget(self.page_manager, 1)

        # Create and register pages
        self.overview_page = OverviewPage()
        self.cpu_usage_graph = PercentageGraph(
            "CPU UTILISATION", "CPU utilisation"
        )
        self.processor_page = DetailPage(
            "Processor",
            "Live CPU temperature, utilisation and processor information.",
            [
                "Temperature",
                "Utilisation",
                "Physical cores",
                "Logical cores",
                "Frequency",
            ],
            extra_widget=self.cpu_usage_graph,
        )
        self.graphics_page = DetailPage(
            "Graphics",
            "Live NVIDIA GPU telemetry when the sensor is available.",
            [
                "GPU temperature",
                "GPU hotspot",
                "GPU memory junction",
                "Utilisation",
                "VRAM used",
                "VRAM total",
                "GPU clock",
            ],
        )
        self.memory_page = DetailPage(
            "Memory",
            "Current system memory usage.",
            ["Memory used", "Memory available", "Total memory", "Utilisation"],
        )
        self.storage_page = DetailPage(
            "Storage",
            "Disk capacity and SSD temperature.",
            [
                "SSD temperature",
                "Space used",
                "Space available",
                "Total capacity",
                "System read speed",
                "System write speed",
                "Drive model",
                "Health status",
                "Operational status",
            ],
        )
        self.settings_page = SettingsPage()
        self.settings_page.load_preferences(
            self.monitoring_interval_ms,
            self.monitoring_enabled
        )

        self.page_manager.add_page("Overview", self.overview_page)
        self.page_manager.add_page("Processor", self.processor_page)
        self.page_manager.add_page("Graphics", self.graphics_page)
        self.page_manager.add_page("Memory", self.memory_page)
        self.page_manager.add_page("Storage", self.storage_page)
        self.page_manager.add_page("Settings", self.settings_page)

        self.page_manager.show_page("Overview")

        # FIX LABEL BACKGROUNDS
        for label in self.findChildren(QLabel):
            label.setStyleSheet(
                label.styleSheet() +
                "\nbackground-color: transparent;"
            )
        
        # Timer and initial statistics
        psutil.cpu_percent(interval=None)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_stats)
        self.timer.setInterval(self.monitoring_interval_ms)

        self.settings_page.monitoring_interval_changed.connect(
            self.set_monitoring_interval
        )
        self.settings_page.monitoring_toggled.connect(
            self.set_monitoring_enabled
        )

        if self.monitoring_enabled:
            self.timer.start()
            self.update_stats()
            self.set_overview_monitoring_status("active")
        else:
            self.set_overview_monitoring_status("paused")

    # ---------------- SETTINGS CONTROLS ----------------

    @Slot(int)
    def set_monitoring_interval(self, interval_ms):
        if interval_ms not in (1000, 2000, 5000):
            return

        self.monitoring_interval_ms = interval_ms
        self.app_settings.setValue(
            "monitoring/interval", self.monitoring_interval_ms
        )
        self.timer.setInterval(self.monitoring_interval_ms)

    def set_overview_monitoring_status(self, state):
        if state == "paused":
            self.overview_page.status.setText(
                "●  MONITORING PAUSED  |  READINGS FROZEN"
            )
            self.overview_page.status.setStyleSheet(
                f"color: {MUTED}; font-size: 11px; font-weight: bold;"
            )
        elif state == "unavailable":
            self.overview_page.status.setText(
                "●  HARDWARE SENSORS UNAVAILABLE"
            )
            self.overview_page.status.setStyleSheet(
                "color: #D6A85F; font-size: 11px; font-weight: bold;"
            )
        else:
            self.overview_page.status.setText(
                "●  SYSTEM MONITORING ACTIVE"
            )
            self.overview_page.status.setStyleSheet(
                f"color: {ACCENT}; font-size: 11px; font-weight: bold;"
            )

    @Slot(bool)
    def set_monitoring_enabled(self, enabled):
        self.monitoring_enabled = bool(enabled)
        self.app_settings.setValue(
            "monitoring/enabled", self.monitoring_enabled
        )

        if self.monitoring_enabled:
            self.settings_page.set_monitoring_status(True)
            self.set_overview_monitoring_status("active")
            self.timer.start(self.monitoring_interval_ms)
            # Refresh immediately. If an old worker is still finishing,
            # start_sensor_poll() prevents a duplicate worker.
            self.update_stats()
        else:
            self.timer.stop()
            self.settings_page.set_monitoring_status(False)
            self.set_overview_monitoring_status("paused")

    # ---------------- NAVIGATION ----------------

    @Slot(str)
    def change_page(self, page):
        self.page_manager.show_page(page)

    # ---------------- BACKGROUND SENSOR POLLING ----------------

    def start_sensor_poll(self):
        if not self.monitoring_enabled:
            return

        # Do not start another worker while the previous one is running.
        if self.sensor_thread is not None:
            return

        thread = QThread(self)
        worker = SensorWorker()
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.readings_ready.connect(self.receive_temperatures)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.sensor_poll_finished)

        self.sensor_thread = thread
        self.sensor_worker = worker
        thread.start()

    @Slot()
    def sensor_poll_finished(self):
        self.sensor_thread = None
        self.sensor_worker = None

    @Slot(dict)
    def receive_temperatures(self, temperatures):
        # Discard results from a worker that completed after monitoring was paused.
        if not self.monitoring_enabled:
            return

        readings = temperatures or {}
        self.gpu_stats = readings.get("gpu_stats")
        self.temperatures = {
            key: value for key, value in readings.items()
            if key != "gpu_stats"
        }

        cpu_temp = self.temperatures.get("cpu")
        gpu_temp = self.temperatures.get("gpu")
        gpu_hotspot = self.temperatures.get("gpu_hotspot")
        gpu_memory_temp = self.temperatures.get("gpu_memory")
        ssd_temp = self.temperatures.get("ssd")

        # Overview cards
        self.overview_page.cpu_card.value.setText(format_temp(cpu_temp))
        self.overview_page.gpu_card.value.setText(format_temp(gpu_temp))
        self.overview_page.gpu_card.subtitle.setText(
            f"Hotspot: {format_temp(gpu_hotspot)}"
        )
        self.overview_page.storage_card.value.setText(format_temp(ssd_temp))

        if not self.monitoring_enabled:
            # A worker may finish after the user pauses monitoring.
            # Never let that late result overwrite the paused indicator.
            return

        if any(value is not None for value in (cpu_temp, gpu_temp, ssd_temp)):
            self.set_overview_monitoring_status("active")
        else:
            self.set_overview_monitoring_status("unavailable")

        self.overview_page.cpu_graph.add_reading(cpu_temp)
        self.overview_page.gpu_graph.add_reading(gpu_temp)

        # Detailed pages
        self.processor_page.set_metrics({
            "Temperature": format_temp(cpu_temp),
            "Utilisation": f"{self.cpu_usage:.1f}%",
            "Physical cores": str(self.physical_cores or "N/A"),
            "Logical cores": str(self.logical_cores or "N/A"),
            "Frequency": self.cpu_frequency,
        })

        gpu_stats = self.gpu_stats or {}

        self.graphics_page.set_metrics({
            "GPU temperature": format_temp(gpu_temp),
            "GPU hotspot": format_temp(gpu_hotspot),
            "GPU memory junction": format_temp(gpu_memory_temp),
            "Utilisation": (
                f"{gpu_stats['utilisation']}%"
                if "utilisation" in gpu_stats else "N/A"
            ),
            "VRAM used": (
                f"{gpu_stats['vram_used']:.2f} GB"
                if "vram_used" in gpu_stats else "N/A"
            ),
            "VRAM total": (
                f"{gpu_stats['vram_total']:.2f} GB"
                if "vram_total" in gpu_stats else "N/A"
            ),
            "GPU clock": (
                f"{gpu_stats['clock']} MHz"
                if "clock" in gpu_stats else "N/A"
            ),
        })

        self.storage_page.set_metrics({
            "SSD temperature": format_temp(ssd_temp),
            "Space used": f"{self.disk_used:.1f} GB",
            "Space available": f"{max(self.disk_total - self.disk_used, 0):.1f} GB",
            "Total capacity": f"{self.disk_total:.1f} GB",
            "System read speed": format_speed(self.disk_read_speed),
            "System write speed": format_speed(self.disk_write_speed),
            "Drive model": (
                self.storage_info.get("model", "Unknown")
                if self.storage_info else "Unavailable"
            ),
            "Health status": (
                self.storage_info.get("health", "Unknown")
                if self.storage_info else "Unavailable"
            ),
            "Operational status": (
                self.storage_info.get("status", "Unknown")
                if self.storage_info else "Unavailable"
            ),
        })

        self.update_information()

    # ---------------- SYSTEM STATISTICS ----------------

    def cpu_frequency_text(self):
        try:
            frequency = psutil.cpu_freq()
            if frequency and frequency.current:
                return f"{frequency.current:.0f} MHz"
        except Exception:
            pass
        return "N/A"

    def update_stats(self):
        self.cpu_usage = psutil.cpu_percent(interval=None)
        self.cpu_frequency = self.cpu_frequency_text()

        # Reuse the CPU utilisation sample already collected above.
        # Avoid updating a hidden graph to keep redraw work to a minimum.
        if self.processor_page.isVisible():
            self.cpu_usage_graph.add_reading(self.cpu_usage)

        memory = psutil.virtual_memory()
        self.ram_used = gb(memory.used)
        self.ram_total = gb(memory.total)
        self.memory_usage = memory.percent
        self.overview_page.ram_graph.add_reading(self.memory_usage)

        try:
            disk = psutil.disk_usage("C:\\")
            self.disk_used = gb(disk.used)
            self.disk_total = gb(disk.total)
        except (OSError, PermissionError):
            self.disk_used = 0.0
            self.disk_total = 0.0

        # Reuse the existing one-second update cycle for lightweight disk I/O.
        # psutil returns aggregate system disk counters, not per-drive SSD data.
        try:
            current_disk_io = psutil.disk_io_counters()
            current_time = time.monotonic()
            elapsed = current_time - self.disk_io_last_time

            if (
                current_disk_io is not None
                and self.disk_io_previous is not None
                and elapsed > 0
            ):
                read_delta = max(
                    0,
                    current_disk_io.read_bytes - self.disk_io_previous.read_bytes
                )
                write_delta = max(
                    0,
                    current_disk_io.write_bytes - self.disk_io_previous.write_bytes
                )
                self.disk_read_speed = read_delta / elapsed
                self.disk_write_speed = write_delta / elapsed
            else:
                self.disk_read_speed = None
                self.disk_write_speed = None

            self.disk_io_previous = current_disk_io
            self.disk_io_last_time = current_time
        except (AttributeError, OSError, PermissionError):
            self.disk_read_speed = None
            self.disk_write_speed = None

        # Overview cards
        self.overview_page.cpu_card.subtitle.setText(
            f"{self.cpu_usage:.1f}% utilisation"
        )
        self.overview_page.ram_card.value.setText(
            f"{self.ram_used:.1f} GB"
        )
        self.overview_page.ram_card.subtitle.setText(
            f"Used out of {self.ram_total:.1f} GB"
        )
        self.overview_page.storage_card.subtitle.setText(
            f"{self.disk_used:.0f} GB used of {self.disk_total:.0f} GB"
        )
        self.overview_page.clock.setText(
            datetime.now().strftime("%d %b %Y  |  %H:%M:%S")
        )

        self.memory_page.set_metrics({
            "Memory used": f"{self.ram_used:.1f} GB",
            "Memory available": f"{gb(memory.available):.1f} GB",
            "Total memory": f"{self.ram_total:.1f} GB",
            "Utilisation": f"{self.memory_usage:.1f}%",
        })

        self.processor_page.set_metrics({
            "Temperature": format_temp(self.temperatures.get("cpu")),
            "Utilisation": f"{self.cpu_usage:.1f}%",
            "Physical cores": str(self.physical_cores or "N/A"),
            "Logical cores": str(self.logical_cores or "N/A"),
            "Frequency": self.cpu_frequency,
        })

        self.update_information()
        self.start_sensor_poll()

    # ---------------- OVERVIEW INFORMATION ----------------

    def update_information(self):
        cpu_temp = self.temperatures.get("cpu")
        gpu_temp = self.temperatures.get("gpu")
        gpu_hotspot = self.temperatures.get("gpu_hotspot")
        ssd_temp = self.temperatures.get("ssd")

        self.overview_page.system_info.setText(
            f"CPU  {format_temp(cpu_temp)}     "
            f"GPU  {format_temp(gpu_temp)}     "
            f"RAM  {self.memory_usage:.1f}%     "
            f"SSD  {format_temp(ssd_temp)}\n"
            f"GPU hotspot  {format_temp(gpu_hotspot)}     "
            f"CPU utilisation  {self.cpu_usage:.1f}%"
        )

    # ---------------- CLEAN SHUTDOWN ----------------

    def closeEvent(self, event):
        self.timer.stop()

        if self.sensor_thread is not None and self.sensor_thread.isRunning():
            self.sensor_thread.quit()

            if not self.sensor_thread.wait(4000):
                event.ignore()
                self.timer.start(UPDATE_INTERVAL)
                return

        event.accept()


# ---------------- APPLICATION ----------------

if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)

    app.setStyle("Fusion")

    # Application branding
    icon_path = Path(__file__).resolve().parent / "assets" / "cerevix_icon.ico"
    app_icon = QIcon(str(icon_path))

    app.setWindowIcon(app_icon)

    app.setStyleSheet(f"""
        QWidget {{
            font-family: 'Segoe UI';
        }}

        QLabel {{
            background-color: transparent;
        }}

        QMainWindow {{
            background-color: {BG};
        }}
    """)

    window = Cerevix()
    window.setWindowIcon(app_icon)
    window.show()

    sys.exit(app.exec())
