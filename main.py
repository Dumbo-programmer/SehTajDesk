import os
import fitz  # PyMuPDF
import json
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QWidget,
    QVBoxLayout, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QTabWidget, QInputDialog, QMessageBox
)
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtCore import Qt

# Utility

def load_json_file(file):
    if os.path.exists(file):
        with open(file, 'r') as f:
            return json.load(f)
    return {}

def save_json_file(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)


class EbookManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())

        self.label = QLabel("Ebook Manager")
        self.label.setFont(QFont("Arial", 16))
        self.layout().addWidget(self.label)

        self.btn_scan = QPushButton("Scan Ebook Directory")
        self.btn_scan.clicked.connect(self.select_directory)
        self.layout().addWidget(self.btn_scan)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.open_file)
        self.layout().addWidget(self.list_widget)

        self.cache_file = "ebook_cache.json"
        self.cache = load_json_file(self.cache_file)
        self.refresh_list()

    def select_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Ebook Directory")
        if dir_path:
            self.scan_ebooks(dir_path)

    def scan_ebooks(self, directory):
        extensions = ['.pdf', '.epub', '.txt']
        for root, dirs, files in os.walk(directory):
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, file)
                    if file_path not in self.cache:
                        try:
                            pages = len(fitz.open(file_path)) if file.endswith(".pdf") else "N/A"
                            self.cache[file_path] = {"name": file, "path": file_path, "pages": pages}
                        except Exception as e:
                            print(f"Failed to read {file_path}: {e}")
        save_json_file(self.cache_file, self.cache)
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        for item in self.cache.values():
            QListWidgetItem(f"{item['name']} ({item['pages']} pages)", self.list_widget)

    def open_file(self, item):
        for path, info in self.cache.items():
            if item.text().startswith(info["name"]):
                os.startfile(path)
                break


class GameManager(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Game Manager - Add game executables", font=QFont("Arial", 14)))

        self.btn_add = QPushButton("Add Game Executable")
        self.btn_add.clicked.connect(self.add_game)
        layout.addWidget(self.btn_add)

        self.game_list = QListWidget()
        self.game_list.itemDoubleClicked.connect(self.launch_game)
        layout.addWidget(self.game_list)

        self.games_file = "games.json"
        self.games = load_json_file(self.games_file)
        self.refresh_list()

    def add_game(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Game Executable")
        if file_path:
            name, ok = QInputDialog.getText(self, "Game Name", "Enter game name:")
            if ok and name:
                self.games[name] = file_path
                save_json_file(self.games_file, self.games)
                self.refresh_list()

    def refresh_list(self):
        self.game_list.clear()
        for name in self.games:
            QListWidgetItem(name, self.game_list)

    def launch_game(self, item):
        path = self.games.get(item.text())
        if path:
            os.startfile(path)


class ProgrammingManager(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Programming Manager - Manage Projects, IDEs, Assets", font=QFont("Arial", 14)))

        self.btn_scan = QPushButton("Scan Project Directory")
        self.btn_scan.clicked.connect(self.scan_projects)
        layout.addWidget(self.btn_scan)

        self.project_list = QListWidget()
        self.project_list.itemDoubleClicked.connect(self.open_project)
        layout.addWidget(self.project_list)
        self.projects = []

    def scan_projects(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Programming Projects Directory")
        if dir_path:
            self.projects.clear()
            for folder in os.listdir(dir_path):
                full_path = os.path.join(dir_path, folder)
                if os.path.isdir(full_path):
                    types = {os.path.splitext(file)[1] for root, _, files in os.walk(full_path) for file in files}
                    summary = f"{folder} - Contains: {', '.join(types) if types else 'No code files'}"
                    self.projects.append((full_path, summary))
            self.refresh_list()

    def refresh_list(self):
        self.project_list.clear()
        for path, summary in self.projects:
            QListWidgetItem(summary, self.project_list)

    def open_project(self, item):
        for path, summary in self.projects:
            if item.text() == summary:
                os.startfile(path)


class PCAssetManager(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("PC Asset Manager - Track PC resource files", font=QFont("Arial", 14)))

        self.btn_scan = QPushButton("Scan for PC Assets")
        self.btn_scan.clicked.connect(self.scan_assets)
        layout.addWidget(self.btn_scan)

        self.asset_list = QListWidget()
        self.asset_list.itemDoubleClicked.connect(lambda item: os.startfile(item.text()))
        layout.addWidget(self.asset_list)

    def scan_assets(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Asset Directory")
        if dir_path:
            self.asset_list.clear()
            for root, _, files in os.walk(dir_path):
                for file in files:
                    QListWidgetItem(os.path.join(root, file), self.asset_list)


class PhotoManager(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Photo Manager - View Image Files", font=QFont("Arial", 14)))

        self.btn_scan = QPushButton("Scan Image Folder")
        self.btn_scan.clicked.connect(self.scan_images)
        layout.addWidget(self.btn_scan)

        self.image_list = QListWidget()
        self.image_list.itemDoubleClicked.connect(lambda item: os.startfile(item.text()))
        layout.addWidget(self.image_list)

    def scan_images(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Image Directory")
        if dir_path:
            self.image_list.clear()
            for root, _, files in os.walk(dir_path):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        QListWidgetItem(os.path.join(root, file), self.image_list)


class UnityManager(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Unity Game Manager - Launch and Track Unity Projects", font=QFont("Arial", 14)))

        self.btn_set_editor = QPushButton("Set Unity Editor Path")
        self.btn_set_editor.clicked.connect(self.set_unity_editor_path)
        layout.addWidget(self.btn_set_editor)

        self.unity_path_label = QLabel("Unity Editor: Not set")
        layout.addWidget(self.unity_path_label)

        self.btn_scan = QPushButton("Scan Unity Project Folder")
        self.btn_scan.clicked.connect(self.scan_unity_projects)
        layout.addWidget(self.btn_scan)

        self.unity_project_list = QListWidget()
        self.unity_project_list.itemDoubleClicked.connect(lambda item: self.launch_project(item.text()))
        layout.addWidget(self.unity_project_list)

        self.editor_path = self.load_editor_path()
        self.unity_path_label.setText(f"Unity Editor: {self.editor_path}" if self.editor_path else "Unity Editor: Not set")

    def set_unity_editor_path(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Unity Editor Executable")
        if path:
            self.editor_path = path
            self.save_editor_path(path)
            self.unity_path_label.setText(f"Unity Editor: {path}")

    def save_editor_path(self, path):
        with open("unity_editor_path.txt", "w") as f:
            f.write(path)

    def load_editor_path(self):
        if os.path.exists("unity_editor_path.txt"):
            with open("unity_editor_path.txt", "r") as f:
                return f.read().strip()
        return ""

    def scan_unity_projects(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Unity Projects Directory")
        if dir_path:
            self.unity_project_list.clear()
            for root, dirs, files in os.walk(dir_path):
                if 'Assets' in dirs and 'ProjectSettings' in dirs:
                    QListWidgetItem(root, self.unity_project_list)

    def launch_project(self, project_path):
        if not self.editor_path or not os.path.exists(self.editor_path):
            QMessageBox.warning(self, "Error", "Unity Editor path not set or invalid")
            return
        subprocess.Popen([self.editor_path, "-projectPath", project_path])


class DesktopManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔥 Desktop Manager 🔥")
        self.setGeometry(100, 100, 1000, 700)

        tabs = QTabWidget()
        tabs.addTab(EbookManager(), "📚 Ebooks")
        tabs.addTab(GameManager(), "🎮 Games")
        tabs.addTab(ProgrammingManager(), "💻 Programming")
        tabs.addTab(PCAssetManager(), "🧰 PC Assets")
        tabs.addTab(PhotoManager(), "🖼️ Photos")
        tabs.addTab(UnityManager(), "🧩 Unity Projects")
        self.setCentralWidget(tabs)


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    main_window = DesktopManager()
    main_window.show()
    sys.exit(app.exec())
