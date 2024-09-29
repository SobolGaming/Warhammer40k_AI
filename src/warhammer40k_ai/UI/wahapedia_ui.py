import sys
import os
import warnings
from bs4 import GuessedAtParserWarning, MarkupResemblesLocatorWarning

# Suppress specific warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*found in sys.modules.*")
warnings.filterwarnings("ignore", category=GuessedAtParserWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

# Add the parent directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(parent_dir)

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QScrollArea, 
                             QLabel, QFrame, QGridLayout, QCompleter)
from PyQt6.QtCore import Qt

from warhammer40k_ai.waha_helper.waha_helper import WahaHelper
from types import SimpleNamespace

class WahapediaUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wahapedia Viewer")  # Updated window title
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.waha_helper = WahaHelper()
        self.datasheet_names = self.waha_helper.get_all_datasheet_names()  # Fetch all datasheet names

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Enter a datasheet name...")
        self.search_bar.returnPressed.connect(self.search_datasheet)
        self.layout.addWidget(self.search_bar)

        completer = QCompleter(self.datasheet_names)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search_bar.setCompleter(completer)  # Attach completer to the search bar

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search_datasheet)
        self.layout.addWidget(self.search_button)

        self.result_area = QScrollArea()
        self.result_area.setWidgetResizable(True)
        self.result_content = QWidget()
        self.result_layout = QVBoxLayout(self.result_content)
        self.result_area.setWidget(self.result_content)
        self.layout.addWidget(self.result_area)

        self.waha_helper = WahaHelper()

    def search_datasheet(self):
        # Clear previous results
        for i in reversed(range(self.result_layout.count())): 
            self.result_layout.itemAt(i).widget().setParent(None)

        datasheet_name = self.search_bar.text()
        datasheet = self.waha_helper.get_full_datasheet_info_by_name(datasheet_name)
        
        if datasheet:
            print(f"Found datasheet: {datasheet.name}")  # Use dot notation here
            self.display_datasheet(datasheet)
        else:
            print(f"Datasheet not found: {datasheet_name}")
            self.display_not_found()

    def display_datasheet(self, datasheet):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.Box)
        frame.setFrameShadow(QFrame.Shadow.Raised)
        layout = QVBoxLayout(frame)

        name_label = QLabel(f"<b>{datasheet.name}</b>")
        layout.addWidget(name_label)

        for key in datasheet.__dict__.keys():
            if key != 'name':
                value = getattr(datasheet, key)
                collapsible_pane = CollapsiblePane(key.capitalize(), self)
                grid_layout = QGridLayout()
                self.populate_grid_layout(grid_layout, value)
                collapsible_pane.setContentLayout(grid_layout)
                layout.addWidget(collapsible_pane)

        self.result_layout.addWidget(frame)

    def populate_grid_layout(self, grid_layout, value, row=0):
        if isinstance(value, SimpleNamespace):
            for sub_key in value.__dict__.keys():
                key_label = QLabel(f"{sub_key}:")
                key_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                grid_layout.addWidget(key_label, row, 0)
                
                sub_value = getattr(value, sub_key)
                if isinstance(sub_value, SimpleNamespace):
                    sub_grid = QGridLayout()
                    self.populate_grid_layout(sub_grid, sub_value)
                    grid_layout.addLayout(sub_grid, row, 1)
                else:
                    value_label = self.create_value_label(sub_value)
                    grid_layout.addWidget(value_label, row, 1)
                row += 1
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, SimpleNamespace):
                    sub_grid = QGridLayout()
                    self.populate_grid_layout(sub_grid, item)
                    grid_layout.addLayout(sub_grid, row, 0, 1, 2)
                else:
                    value_label = self.create_value_label(item)
                    grid_layout.addWidget(value_label, row, 0, 1, 2)
                row += 1
        else:
            value_label = self.create_value_label(value)
            grid_layout.addWidget(value_label, row, 0, 1, 2)
        return row

    def create_value_label(self, value):
        value_str = str(value).strip()  # Remove leading/trailing whitespace
        value_label = QLabel(value_str)
        value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        value_label.setWordWrap(True)  # Enable word wrapping for long text
        return value_label

    def display_not_found(self):
        label = QLabel("Datasheet not found.")
        self.result_layout.addWidget(label)

class CollapsiblePane(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.toggle_button = QPushButton(title)
        self.toggle_button.setStyleSheet("text-align: left; padding: 5px;")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.toggled.connect(self.on_toggle)

        self.content_area = QWidget()
        self.content_area.setVisible(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content_area)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

    def on_toggle(self, checked):
        self.content_area.setVisible(checked)

    def setContentLayout(self, layout):
        self.content_area.setLayout(layout)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ui = WahapediaUI()  # Updated class name
    ui.show()
    sys.exit(app.exec())
