from PySide6.QtWidgets import (
    QStackedWidget,
    QWidget,
    QVBoxLayout,
    QLabel
)

# Theme
BG = "#0B0D0C"
TEXT = "#E8EFEB"
MUTED = "#89958E"


class PlaceholderPage(QWidget):

    def __init__(self, title):
        super().__init__()

        self.setStyleSheet(f"background-color: {BG};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)

        heading = QLabel(title)
        heading.setStyleSheet(f"""
            color: {TEXT};
            font-size: 25px;
            font-weight: 600;
        """)

        description = QLabel("This section is under development.")
        description.setStyleSheet(f"""
            color: {MUTED};
            font-size: 13px;
        """)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addStretch()


class PageManager(QStackedWidget):

    def __init__(self):
        super().__init__()

        self.pages = {}

    def add_page(self, name, widget):

        self.pages[name] = widget
        self.addWidget(widget)

    def show_page(self, name):

        if name in self.pages:
            self.setCurrentWidget(self.pages[name])