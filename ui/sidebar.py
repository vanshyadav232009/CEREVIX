from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton
)

from core.config import APP_NAME, APP_VERSION


# Theme
BG = "#0B0D0C"
ACCENT = "#00C781"
TEXT = "#E8EFEB"
MUTED = "#89958E"
PANEL = "#141816"


class Sidebar(QWidget):

    page_selected = Signal(str)

    def __init__(self):
        super().__init__()

        self.setFixedWidth(210)
        self.setStyleSheet(f"background-color: {BG};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 25, 15, 20)
        layout.setSpacing(6)

        # Application branding
        logo = QLabel(APP_NAME)
        logo.setStyleSheet(f"""
            color: {ACCENT};
            font-size: 25px;
            font-weight: bold;
            letter-spacing: 4px;
        """)

        layout.addWidget(logo)
        layout.addSpacing(40)

        # Navigation
        self.buttons = {}

        pages = [
            "Overview",
            "Processor",
            "Graphics",
            "Memory",
            "Storage",
            "Settings"
        ]

        for page in pages:

            button = QPushButton(page.upper())
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedHeight(42)

            button.setStyleSheet(f"""
                QPushButton {{
                    color: {MUTED};
                    background-color: transparent;
                    border: none;
                    border-radius: 5px;
                    text-align: left;
                    padding-left: 10px;
                    font-size: 12px;
                    font-weight: 600;
                }}

                QPushButton:hover {{
                    background-color: {PANEL};
                    color: {TEXT};
                }}
            """)

            button.clicked.connect(
                lambda checked=False, p=page: self.select_page(p)
            )

            layout.addWidget(button)
            self.buttons[page] = button

        layout.addStretch()

        # Application version
        version = QLabel(f"{APP_NAME} v{APP_VERSION}")
        version.setStyleSheet(f"""
            color: {MUTED};
            font-size: 10px;
        """)

        layout.addWidget(version)

        # Default page
        self.select_page("Overview")

    # Page selection
    def select_page(self, page):

        for name, button in self.buttons.items():

            if name == page:
                button.setStyleSheet(f"""
                    QPushButton {{
                        color: {ACCENT};
                        background-color: {PANEL};
                        border: none;
                        border-left: 3px solid {ACCENT};
                        border-radius: 5px;
                        text-align: left;
                        padding-left: 10px;
                        font-size: 12px;
                        font-weight: bold;
                    }}
                """)

            else:
                button.setStyleSheet(f"""
                    QPushButton {{
                        color: {MUTED};
                        background-color: transparent;
                        border: none;
                        border-radius: 5px;
                        text-align: left;
                        padding-left: 10px;
                        font-size: 12px;
                        font-weight: 600;
                    }}

                    QPushButton:hover {{
                        background-color: {PANEL};
                        color: {TEXT};
                    }}
                """)

        self.page_selected.emit(page)