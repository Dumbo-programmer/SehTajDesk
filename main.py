import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

import fitz  # PyMuPDF
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QListView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

APP_DIR = Path(__file__).resolve().parent
EBOOK_CACHE_FILE = APP_DIR / "ebook_cache.json"
GAMES_FILE = APP_DIR / "games.json"
UNITY_EDITOR_PATH_FILE = APP_DIR / "unity_editor_path.txt"

SUPPORTED_EBOOK_EXTENSIONS = {".pdf", ".epub", ".txt"}
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
CODE_FILE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go",
    ".rs", ".php", ".rb", ".swift", ".kt", ".scala", ".html", ".css", ".scss", ".json", ".xml",
    ".yaml", ".yml", ".toml", ".md", ".sql", ".sh", ".ps1", ".bat",
}
GAME_FILE_EXTENSIONS = {".exe", ".bat", ".lnk"}
UNITY_FILE_EXTENSIONS = {".unity", ".prefab", ".asset", ".mat"}

# Safety limits to prevent huge directory scans from exhausting UI memory.
MAX_UI_LIST_ITEMS = 15000
MAX_EBOOK_ADDITIONS_PER_SCAN = 5000
MAX_PROJECTS_SCANNED = 2000
MAX_FILES_ANALYZED_PER_PROJECT = 6000
ICON_CACHE: dict[str, QIcon] = {}

APP_STYLESHEET = """
QMainWindow {
    background: #f4f6fb;
}

QWidget {
    color: #1f2937;
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 10pt;
}

QTabWidget::pane {
    border: 1px solid #dbe3f0;
    border-radius: 10px;
    background: #ffffff;
    margin-top: 6px;
}

QTabBar::tab {
    background: #e7edf8;
    border: 1px solid #dbe3f0;
    padding: 8px 14px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
}

QTabBar::tab:selected {
    background: #ffffff;
    border-bottom-color: #ffffff;
    font-weight: 600;
}

QPushButton {
    background: #1f6feb;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: 600;
}

QPushButton:hover {
    background: #165fd3;
}

QPushButton:pressed {
    background: #0f4cb5;
}

QLineEdit {
    border: 1px solid #c8d4e8;
    border-radius: 8px;
    padding: 8px 10px;
    background: #ffffff;
}

QLineEdit:focus {
    border: 1px solid #1f6feb;
}

QListWidget {
    border: 1px solid #dbe3f0;
    border-radius: 8px;
    background: #fbfdff;
    alternate-background-color: #eef3fa;
    padding: 4px;
}

QListWidget::item {
    padding: 7px 8px;
    border-radius: 6px;
    background: transparent;
    color: #1f2937;
}

QListWidget::item:alternate {
    background: #eef3fa;
    color: #1f2937;
}

QListWidget::item:selected {
    background: #dbe9ff;
    color: #102040;
}

QComboBox {
    border: 1px solid #c8d4e8;
    border-radius: 8px;
    padding: 6px 8px;
    background: #ffffff;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: 1px solid #c8d4e8;
    background: #ffffff;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}

QComboBox::down-arrow {
    width: 10px;
    height: 10px;
}

QComboBox QAbstractItemView {
    background: #ffffff;
    selection-background-color: #dbe9ff;
    selection-color: #102040;
}

QScrollBar:vertical {
    background: #ffffff;
    width: 13px;
    margin: 0px;
    border: 1px solid #dbe3f0;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background: #cfd8e8;
    min-height: 24px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background: #b7c4db;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    background: #ffffff;
    height: 0px;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: #ffffff;
}

QScrollBar:horizontal {
    background: #ffffff;
    height: 13px;
    margin: 0px;
    border: 1px solid #dbe3f0;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background: #cfd8e8;
    min-width: 24px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal:hover {
    background: #b7c4db;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    background: #ffffff;
    width: 0px;
}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: #ffffff;
}

QLabel#AppTitle {
    font-size: 36px;
    font-weight: 700;
    color: #0f2a55;
}

QLabel#AppSubtitle {
    font-size: 12pt;
    color: #3b4d6d;
}

QPushButton#MenuButton {
    min-height: 54px;
    font-size: 10.5pt;
}
"""


def load_json_file(file_path: Path) -> dict[str, Any]:
    if not file_path.exists():
        return {}

    try:
        with file_path.open("r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Failed to load {file_path}: {exc}")
        return {}


def save_json_file(file_path: Path, data: dict[str, Any]) -> None:
    try:
        with file_path.open("w", encoding="utf-8") as file_obj:
            json.dump(data, file_obj, indent=2)
    except OSError as exc:
        print(f"Failed to save {file_path}: {exc}")


def create_title_label(text: str, size: int = 14) -> QLabel:
    label = QLabel(text)
    label.setFont(QFont("Arial", size))
    return label


def open_path(path: str, parent: QWidget | None = None) -> None:
    if not path or not os.path.exists(path):
        QMessageBox.warning(parent, "File Not Found", f"Could not find:\n{path}")
        return

    try:
        os.startfile(path)
    except OSError as exc:
        QMessageBox.warning(parent, "Open Failed", f"Could not open file:\n{exc}")


def open_containing_folder(path: str, parent: QWidget | None = None) -> None:
    target_path = path if os.path.isdir(path) else os.path.dirname(path)
    if not target_path:
        QMessageBox.warning(parent, "Folder Not Found", "No containing folder was found.")
        return
    open_path(target_path, parent)


def set_status_message(widget: QWidget, message: str, timeout_ms: int = 3000) -> None:
    main_window = widget.window()
    if isinstance(main_window, QMainWindow):
        status_bar = main_window.statusBar()
        if status_bar is not None:
            status_bar.showMessage(message, timeout_ms)


def add_path_item(list_widget: QListWidget, label_text: str, path: str) -> None:
    list_item = QListWidgetItem(label_text)
    list_item.setData(Qt.ItemDataRole.UserRole, path)
    list_item.setToolTip(path)
    list_widget.addItem(list_item)


def create_category_icon(kind: str) -> QIcon:
    cached_icon = ICON_CACHE.get(kind)
    if cached_icon is not None:
        return cached_icon

    icon_specs = {
        "book": ("BK", "#f59e0b"),
        "code": ("{}", "#2563eb"),
        "image": ("IMG", "#16a34a"),
        "game": ("G", "#dc2626"),
        "unity": ("U", "#374151"),
        "folder": ("DIR", "#7c3aed"),
        "file": ("F", "#475569"),
    }
    label, color_hex = icon_specs.get(kind, icon_specs["file"])

    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_hex))
    painter.drawRoundedRect(4, 4, 56, 56, 12, 12)

    painter.setPen(QColor("white"))
    text_font = QFont("Segoe UI", 13, QFont.Weight.Bold)
    painter.setFont(text_font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, label)
    painter.end()

    icon = QIcon(pixmap)
    ICON_CACHE[kind] = icon
    return icon


def infer_file_icon_kind(path: str) -> str:
    extension = os.path.splitext(path)[1].lower()
    if extension in SUPPORTED_EBOOK_EXTENSIONS:
        return "book"
    if extension in SUPPORTED_IMAGE_EXTENSIONS:
        return "image"
    if extension in CODE_FILE_EXTENSIONS:
        return "code"
    if extension in UNITY_FILE_EXTENSIONS:
        return "unity"
    if extension in GAME_FILE_EXTENSIONS:
        return "game"
    return "file"


def add_categorized_item(list_widget: QListWidget, label_text: str, path: str, icon_kind: str) -> None:
    list_item = QListWidgetItem(label_text)
    list_item.setData(Qt.ItemDataRole.UserRole, path)
    list_item.setToolTip(path)
    list_item.setIcon(create_category_icon(icon_kind))
    list_widget.addItem(list_item)


def get_current_path(list_widget: QListWidget) -> str | None:
    current_item = list_widget.currentItem()
    if not current_item:
        return None
    path = current_item.data(Qt.ItemDataRole.UserRole)
    return path if isinstance(path, str) else None


def apply_filter_to_list(list_widget: QListWidget, query: str) -> int:
    normalized = query.strip().casefold()
    visible_count = 0

    for index in range(list_widget.count()):
        item = list_widget.item(index)
        if item is None:
            continue
        item_path = item.data(Qt.ItemDataRole.UserRole)
        searchable = f"{item.text()} {item_path if isinstance(item_path, str) else ''}".casefold()
        should_show = normalized in searchable
        item.setHidden(not should_show)
        if should_show:
            visible_count += 1

    return visible_count


def update_count_label(label: QLabel, visible_count: int, total_count: int) -> None:
    noun = "item" if total_count == 1 else "items"
    label.setText(f"Showing {visible_count} of {total_count} {noun}")


def show_path_context_menu(
    list_widget: QListWidget,
    position,
    parent: QWidget,
    open_item_handler: Callable[[QListWidgetItem], None] | None,
) -> None:
    item = list_widget.itemAt(position)
    if not item:
        return

    path = item.data(Qt.ItemDataRole.UserRole)
    if not isinstance(path, str):
        return

    menu = QMenu(list_widget)
    open_action = menu.addAction("Open")
    open_folder_action = menu.addAction("Open Containing Folder")
    copy_path_action = menu.addAction("Copy Path")

    selected_action = menu.exec(list_widget.mapToGlobal(position))
    if selected_action == open_action:
        if open_item_handler is not None:
            open_item_handler(item)
        else:
            open_path(path, parent)
    elif selected_action == open_folder_action:
        open_containing_folder(path, parent)
    elif selected_action == copy_path_action:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(path)
            set_status_message(parent, "Copied path to clipboard")


def configure_path_list_widget(
    list_widget: QListWidget,
    parent: QWidget,
    open_item_handler: Callable[[QListWidgetItem], None] | None,
) -> None:
    list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    list_widget.setAlternatingRowColors(True)
    list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    list_widget.customContextMenuRequested.connect(
        lambda pos, lw=list_widget, p=parent, cb=open_item_handler: show_path_context_menu(lw, pos, p, cb)
    )
    set_list_view_mode(list_widget)


def set_list_view_mode(list_widget: QListWidget) -> None:
    list_widget.setViewMode(QListView.ViewMode.ListMode)
    list_widget.setAlternatingRowColors(True)
    list_widget.setIconSize(QSize(22, 22))
    list_widget.setGridSize(QSize())
    list_widget.setWordWrap(False)
    list_widget.setSpacing(2)


def set_grid_view_mode(list_widget: QListWidget) -> None:
    list_widget.setViewMode(QListView.ViewMode.IconMode)
    list_widget.setAlternatingRowColors(False)
    list_widget.setIconSize(QSize(52, 52))
    list_widget.setResizeMode(QListView.ResizeMode.Adjust)
    list_widget.setMovement(QListView.Movement.Static)
    list_widget.setGridSize(QSize(180, 96))
    list_widget.setWordWrap(True)
    list_widget.setSpacing(8)


def create_view_mode_selector(list_widget: QListWidget) -> tuple[QHBoxLayout, QComboBox]:
    row_layout = QHBoxLayout()

    view_label = QLabel("View:")
    selector = QComboBox()
    selector.addItems(["List View", "Grid View"])
    selector.setToolTip("Choose how items are displayed")
    selector.currentTextChanged.connect(
        lambda value, lw=list_widget: set_grid_view_mode(lw) if value == "Grid View" else set_list_view_mode(lw)
    )

    row_layout.addWidget(view_label)
    row_layout.addWidget(selector)
    row_layout.addStretch()
    return row_layout, selector


def create_filter_row(placeholder: str) -> tuple[QHBoxLayout, QLineEdit, QPushButton]:
    row_layout = QHBoxLayout()

    filter_input = QLineEdit()
    filter_input.setPlaceholderText(placeholder)
    filter_input.setClearButtonEnabled(True)
    filter_input.setToolTip("Filter list items by name or path")

    open_selected_button = QPushButton("Open Selected")
    open_selected_button.setToolTip("Open the currently selected item")

    row_layout.addWidget(filter_input)
    row_layout.addWidget(open_selected_button)
    return row_layout, filter_input, open_selected_button


def collect_file_paths_limited(
    directory: str,
    matcher: Callable[[str, str], bool],
    limit: int,
) -> tuple[list[str], bool]:
    paths: list[str] = []
    for root, _, files in os.walk(directory):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            if matcher(file_name, file_path):
                paths.append(file_path)
                if len(paths) >= limit:
                    return paths, True
    return paths, False


def collect_unity_projects_limited(directory: str, limit: int) -> tuple[list[str], bool]:
    project_paths: list[str] = []
    for root, dirs, _ in os.walk(directory):
        if "Assets" in dirs and "ProjectSettings" in dirs:
            project_paths.append(root)
            # Do not scan inside already-detected Unity project trees.
            dirs[:] = []
            if len(project_paths) >= limit:
                return project_paths, True
    return project_paths, False


def show_truncated_scan_message(parent: QWidget, noun: str, limit: int) -> None:
    QMessageBox.information(
        parent,
        "Large Directory Notice",
        f"Showing the first {limit} {noun} to keep the app responsive. "
        "Use a smaller folder to see everything.",
    )


class MainMenuPage(QWidget):
    def __init__(self, open_tab_callback: Callable[[str], None]):
        super().__init__()
        self.open_tab_callback = open_tab_callback

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel("SehTajDesk")
        title.setObjectName("AppTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setAccessibleName("Application title")
        layout.addWidget(title)

        subtitle = QLabel("A single desktop workspace for your files, projects, games, and media.")
        subtitle.setObjectName("AppSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setAccessibleName("Application subtitle")
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        menu_items = [
            ("Ebooks", "Open Ebook Manager"),
            ("Games", "Open Game Manager"),
            ("Programming", "Open Programming Manager"),
            ("PC Assets", "Open PC Asset Manager"),
            ("Photos", "Open Photo Manager"),
            ("Unity Projects", "Open Unity Project Manager"),
        ]

        for index, (tab_name, button_text) in enumerate(menu_items):
            row = index // 2
            col = index % 2
            button = QPushButton(button_text)
            button.setObjectName("MenuButton")
            button.setAccessibleName(button_text)
            button.setToolTip(f"Go to {tab_name}")
            button.clicked.connect(lambda _, n=tab_name: self.open_tab_callback(n))
            grid.addWidget(button, row, col)

        layout.addLayout(grid)

        hint = QLabel("Tip: Use the tabs above to switch sections anytime.")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch()


class EbookManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.label = create_title_label("Ebook Manager", 16)
        layout.addWidget(self.label)
        layout.addWidget(QLabel("Scan, search, and open your ebook collection quickly."))

        action_row = QHBoxLayout()

        self.btn_scan = QPushButton("Scan Ebook Directory")
        self.btn_scan.setToolTip("Scan folders for PDF, EPUB, and TXT files")
        self.btn_scan.clicked.connect(self.select_directory)
        action_row.addWidget(self.btn_scan)

        self.btn_prune = QPushButton("Remove Missing")
        self.btn_prune.setToolTip("Remove cache entries that no longer exist")
        self.btn_prune.clicked.connect(self.prune_missing_entries)
        action_row.addWidget(self.btn_prune)

        layout.addLayout(action_row)

        filter_row, self.filter_input, self.btn_open_selected = create_filter_row("Filter ebooks...")
        self.filter_input.textChanged.connect(self.apply_filter)
        self.btn_open_selected.clicked.connect(self.open_selected_file)
        layout.addLayout(filter_row)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.open_file)
        self.list_widget.setAccessibleName("Ebook list")
        configure_path_list_widget(self.list_widget, self, self.open_file)

        view_row, self.view_selector = create_view_mode_selector(self.list_widget)
        layout.addLayout(view_row)

        layout.addWidget(self.list_widget)

        self.count_label = QLabel("Showing 0 of 0 items")
        layout.addWidget(self.count_label)

        self.cache_file = EBOOK_CACHE_FILE
        self.cache = load_json_file(self.cache_file)
        self.refresh_list()

    def select_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Ebook Directory")
        if dir_path:
            self.scan_ebooks(dir_path)

    def scan_ebooks(self, directory):
        added_count = 0
        truncated = False
        for root, _, files in os.walk(directory):
            for file_name in files:
                extension = os.path.splitext(file_name)[1].lower()
                if extension in SUPPORTED_EBOOK_EXTENSIONS:
                    file_path = os.path.join(root, file_name)
                    if file_path not in self.cache:
                        try:
                            if extension == ".pdf":
                                pdf_document = fitz.open(file_path)
                                pages = pdf_document.page_count
                                pdf_document.close()
                            else:
                                pages = "N/A"

                            self.cache[file_path] = {
                                "name": file_name,
                                "path": file_path,
                                "pages": pages,
                            }
                            added_count += 1
                            if added_count >= MAX_EBOOK_ADDITIONS_PER_SCAN:
                                truncated = True
                                break
                        except Exception as exc:
                            print(f"Failed to read {file_path}: {exc}")
            if truncated:
                break

        save_json_file(self.cache_file, self.cache)
        self.refresh_list()
        QMessageBox.information(self, "Scan Complete", f"Added {added_count} new ebook(s).")
        set_status_message(self, f"Ebook scan complete: {added_count} new item(s)")
        if truncated:
            show_truncated_scan_message(self, "new ebooks", MAX_EBOOK_ADDITIONS_PER_SCAN)

    def prune_missing_entries(self):
        missing_paths = [path for path in self.cache if not os.path.exists(path)]
        if not missing_paths:
            QMessageBox.information(self, "Nothing To Remove", "No missing ebook entries were found.")
            return

        for path in missing_paths:
            self.cache.pop(path, None)

        save_json_file(self.cache_file, self.cache)
        self.refresh_list()
        QMessageBox.information(self, "Cleanup Complete", f"Removed {len(missing_paths)} missing entry(ies).")
        set_status_message(self, f"Removed {len(missing_paths)} missing ebook entries")

    def refresh_list(self):
        self.list_widget.clear()

        for item in sorted(self.cache.values(), key=lambda value: value.get("name", "").lower()):
            add_categorized_item(self.list_widget, f"{item['name']} ({item['pages']} pages)", item["path"], "book")

        self.apply_filter()

    def apply_filter(self):
        visible_count = apply_filter_to_list(self.list_widget, self.filter_input.text())
        update_count_label(self.count_label, visible_count, self.list_widget.count())

    def open_selected_file(self):
        path = get_current_path(self.list_widget)
        if not path:
            QMessageBox.information(self, "No Selection", "Select an ebook first.")
            return
        open_path(path, self)

    def open_file(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(path, str):
            open_path(path, self)


class GameManager(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(create_title_label("Game Manager", 16))
        layout.addWidget(QLabel("Add game executables and launch them without browsing folders."))

        action_row = QHBoxLayout()

        self.btn_add = QPushButton("Add Game Executable")
        self.btn_add.setToolTip("Add a game executable to your launch list")
        self.btn_add.clicked.connect(self.add_game)
        action_row.addWidget(self.btn_add)

        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.setToolTip("Remove the selected game from the list")
        self.btn_remove.clicked.connect(self.remove_selected_game)
        action_row.addWidget(self.btn_remove)

        layout.addLayout(action_row)

        filter_row, self.filter_input, self.btn_open_selected = create_filter_row("Filter games...")
        self.filter_input.textChanged.connect(self.apply_filter)
        self.btn_open_selected.clicked.connect(self.open_selected_game)
        layout.addLayout(filter_row)

        self.game_list = QListWidget()
        self.game_list.itemDoubleClicked.connect(self.launch_game)
        self.game_list.setAccessibleName("Game list")
        configure_path_list_widget(self.game_list, self, self.launch_game)

        view_row, self.view_selector = create_view_mode_selector(self.game_list)
        layout.addLayout(view_row)

        layout.addWidget(self.game_list)

        self.count_label = QLabel("Showing 0 of 0 items")
        layout.addWidget(self.count_label)

        self.games_file = GAMES_FILE
        loaded_games = load_json_file(self.games_file)
        self.games = {k: v for k, v in loaded_games.items() if isinstance(k, str) and isinstance(v, str)}
        self.refresh_list()

    def add_game(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Game Executable",
            "",
            "Executables (*.exe);;All Files (*)",
        )
        if file_path:
            name, ok = QInputDialog.getText(self, "Game Name", "Enter game name:")
            if ok and name.strip():
                clean_name = name.strip()
                if clean_name in self.games:
                    should_replace = QMessageBox.question(
                        self,
                        "Replace Existing?",
                        f"A game named '{clean_name}' already exists. Replace it?",
                    )
                    if should_replace != QMessageBox.StandardButton.Yes:
                        return

                self.games[clean_name] = file_path
                save_json_file(self.games_file, self.games)
                self.refresh_list()
                set_status_message(self, f"Saved game: {clean_name}")

    def remove_selected_game(self):
        selected_item = self.game_list.currentItem()
        if not selected_item:
            QMessageBox.information(self, "No Selection", "Select a game to remove.")
            return

        game_name = selected_item.text()
        confirmation = QMessageBox.question(self, "Confirm Remove", f"Remove '{game_name}' from your game list?")
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        self.games.pop(game_name, None)
        save_json_file(self.games_file, self.games)
        self.refresh_list()
        set_status_message(self, f"Removed game: {game_name}")

    def refresh_list(self):
        self.game_list.clear()
        for name in sorted(self.games):
            add_categorized_item(self.game_list, name, self.games[name], "game")

        self.apply_filter()

    def apply_filter(self):
        visible_count = apply_filter_to_list(self.game_list, self.filter_input.text())
        update_count_label(self.count_label, visible_count, self.game_list.count())

    def open_selected_game(self):
        selected_item = self.game_list.currentItem()
        if not selected_item:
            QMessageBox.information(self, "No Selection", "Select a game first.")
            return
        self.launch_game(selected_item)

    def launch_game(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(path, str):
            open_path(path, self)


class ProgrammingManager(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(create_title_label("Programming Manager", 16))
        layout.addWidget(QLabel("Scan coding project folders and open projects quickly."))

        action_row = QHBoxLayout()

        self.btn_scan = QPushButton("Scan Project Directory")
        self.btn_scan.setToolTip("Scan a folder for project directories")
        self.btn_scan.clicked.connect(self.scan_projects)
        action_row.addWidget(self.btn_scan)

        self.btn_open_selected = QPushButton("Open Selected")
        self.btn_open_selected.clicked.connect(self.open_selected_project)
        action_row.addWidget(self.btn_open_selected)

        layout.addLayout(action_row)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter projects...")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self.apply_filter)
        layout.addWidget(self.filter_input)

        self.project_list = QListWidget()
        self.project_list.itemDoubleClicked.connect(self.open_project)
        self.project_list.setAccessibleName("Project list")
        configure_path_list_widget(self.project_list, self, self.open_project)

        view_row, self.view_selector = create_view_mode_selector(self.project_list)
        layout.addLayout(view_row)

        layout.addWidget(self.project_list)

        self.count_label = QLabel("Showing 0 of 0 items")
        layout.addWidget(self.count_label)
        self.projects = []

    def scan_projects(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Programming Projects Directory")
        if dir_path:
            self.projects.clear()
            scanned_projects = 0
            partial_analysis = False
            project_limit_hit = False
            for folder in os.listdir(dir_path):
                full_path = os.path.join(dir_path, folder)
                if os.path.isdir(full_path):
                    if scanned_projects >= MAX_PROJECTS_SCANNED:
                        project_limit_hit = True
                        break
                    scanned_projects += 1

                    extension_set: set[str] = set()
                    files_analyzed = 0
                    for root, _, files in os.walk(full_path):
                        for file_name in files:
                            files_analyzed += 1
                            extension = os.path.splitext(file_name)[1]
                            if extension:
                                extension_set.add(extension)

                            if files_analyzed >= MAX_FILES_ANALYZED_PER_PROJECT:
                                partial_analysis = True
                                break

                        if files_analyzed >= MAX_FILES_ANALYZED_PER_PROJECT:
                            break

                    extension_list = sorted(extension_set)
                    if extension_list:
                        extension_preview = ", ".join(extension_list[:6])
                        if len(extension_list) > 6:
                            extension_preview = f"{extension_preview}, +{len(extension_list) - 6} more"
                    else:
                        extension_preview = "No detected file extensions"

                    summary = f"{folder} - Contains: {extension_preview}"
                    self.projects.append((full_path, summary))
            self.refresh_list()
            set_status_message(self, f"Found {len(self.projects)} project folder(s)")
            if project_limit_hit or partial_analysis:
                QMessageBox.information(
                    self,
                    "Large Directory Notice",
                    f"For performance, this scan shows up to {MAX_PROJECTS_SCANNED} projects "
                    f"and inspects up to {MAX_FILES_ANALYZED_PER_PROJECT} files per project.",
                )

    def refresh_list(self):
        self.project_list.clear()
        for path, summary in self.projects:
            add_categorized_item(self.project_list, summary, path, "code")

        self.apply_filter()

    def apply_filter(self):
        visible_count = apply_filter_to_list(self.project_list, self.filter_input.text())
        update_count_label(self.count_label, visible_count, self.project_list.count())

    def open_selected_project(self):
        selected_item = self.project_list.currentItem()
        if not selected_item:
            QMessageBox.information(self, "No Selection", "Select a project first.")
            return
        self.open_project(selected_item)

    def open_project(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(path, str):
            open_path(path, self)


class PCAssetManager(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(create_title_label("PC Asset Manager", 16))
        layout.addWidget(QLabel("Browse and open files from any selected directory tree."))

        action_row = QHBoxLayout()

        self.btn_scan = QPushButton("Scan for PC Assets")
        self.btn_scan.clicked.connect(self.scan_assets)
        action_row.addWidget(self.btn_scan)

        self.btn_open_selected = QPushButton("Open Selected")
        self.btn_open_selected.clicked.connect(self.open_selected_asset)
        action_row.addWidget(self.btn_open_selected)

        layout.addLayout(action_row)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter assets...")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self.apply_filter)
        layout.addWidget(self.filter_input)

        self.asset_list = QListWidget()
        self.asset_list.itemDoubleClicked.connect(self.open_asset)
        self.asset_list.setAccessibleName("Asset list")
        configure_path_list_widget(self.asset_list, self, self.open_asset)

        view_row, self.view_selector = create_view_mode_selector(self.asset_list)
        layout.addLayout(view_row)

        layout.addWidget(self.asset_list)

        self.count_label = QLabel("Showing 0 of 0 items")
        layout.addWidget(self.count_label)

    def open_asset(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(path, str):
            open_path(path, self)

    def open_selected_asset(self):
        selected_item = self.asset_list.currentItem()
        if not selected_item:
            QMessageBox.information(self, "No Selection", "Select an asset first.")
            return
        self.open_asset(selected_item)

    def scan_assets(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Asset Directory")
        if dir_path:
            self.asset_list.clear()
            paths, truncated = collect_file_paths_limited(
                dir_path,
                lambda _name, _path: True,
                MAX_UI_LIST_ITEMS,
            )

            for path in sorted(paths, key=str.lower):
                add_categorized_item(self.asset_list, path, path, infer_file_icon_kind(path))

            self.apply_filter()
            set_status_message(self, f"Indexed {self.asset_list.count()} asset file(s)")
            if truncated:
                show_truncated_scan_message(self, "files", MAX_UI_LIST_ITEMS)

    def apply_filter(self):
        visible_count = apply_filter_to_list(self.asset_list, self.filter_input.text())
        update_count_label(self.count_label, visible_count, self.asset_list.count())


class PhotoManager(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(create_title_label("Photo Manager", 16))
        layout.addWidget(QLabel("Scan and open image files from your photo folders."))

        action_row = QHBoxLayout()

        self.btn_scan = QPushButton("Scan Image Folder")
        self.btn_scan.clicked.connect(self.scan_images)
        action_row.addWidget(self.btn_scan)

        self.btn_open_selected = QPushButton("Open Selected")
        self.btn_open_selected.clicked.connect(self.open_selected_image)
        action_row.addWidget(self.btn_open_selected)

        layout.addLayout(action_row)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter images...")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self.apply_filter)
        layout.addWidget(self.filter_input)

        self.image_list = QListWidget()
        self.image_list.itemDoubleClicked.connect(self.open_image)
        self.image_list.setAccessibleName("Photo list")
        configure_path_list_widget(self.image_list, self, self.open_image)

        view_row, self.view_selector = create_view_mode_selector(self.image_list)
        layout.addLayout(view_row)

        layout.addWidget(self.image_list)

        self.count_label = QLabel("Showing 0 of 0 items")
        layout.addWidget(self.count_label)

    def open_image(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(path, str):
            open_path(path, self)

    def open_selected_image(self):
        selected_item = self.image_list.currentItem()
        if not selected_item:
            QMessageBox.information(self, "No Selection", "Select an image first.")
            return
        self.open_image(selected_item)

    def scan_images(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Image Directory")
        if dir_path:
            self.image_list.clear()
            images, truncated = collect_file_paths_limited(
                dir_path,
                lambda file_name, _path: os.path.splitext(file_name)[1].lower() in SUPPORTED_IMAGE_EXTENSIONS,
                MAX_UI_LIST_ITEMS,
            )

            for path in sorted(images, key=str.lower):
                add_categorized_item(self.image_list, path, path, "image")

            self.apply_filter()
            set_status_message(self, f"Indexed {self.image_list.count()} image file(s)")
            if truncated:
                show_truncated_scan_message(self, "images", MAX_UI_LIST_ITEMS)

    def apply_filter(self):
        visible_count = apply_filter_to_list(self.image_list, self.filter_input.text())
        update_count_label(self.count_label, visible_count, self.image_list.count())


class UnityManager(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(create_title_label("Unity Project Manager", 16))
        layout.addWidget(QLabel("Set your Unity Editor and launch discovered Unity projects."))

        top_row = QHBoxLayout()

        self.btn_set_editor = QPushButton("Set Unity Editor Path")
        self.btn_set_editor.clicked.connect(self.set_unity_editor_path)
        top_row.addWidget(self.btn_set_editor)

        self.btn_launch_selected = QPushButton("Launch Selected")
        self.btn_launch_selected.clicked.connect(self.launch_selected_project)
        top_row.addWidget(self.btn_launch_selected)

        layout.addLayout(top_row)

        self.unity_path_label = QLabel("Unity Editor: Not set")
        layout.addWidget(self.unity_path_label)

        self.btn_scan = QPushButton("Scan Unity Project Folder")
        self.btn_scan.clicked.connect(self.scan_unity_projects)
        layout.addWidget(self.btn_scan)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter Unity projects...")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self.apply_filter)
        layout.addWidget(self.filter_input)

        self.unity_project_list = QListWidget()
        self.unity_project_list.itemDoubleClicked.connect(self.launch_project_from_item)
        self.unity_project_list.setAccessibleName("Unity project list")
        configure_path_list_widget(self.unity_project_list, self, self.launch_project_from_item)

        view_row, self.view_selector = create_view_mode_selector(self.unity_project_list)
        layout.addLayout(view_row)

        layout.addWidget(self.unity_project_list)

        self.count_label = QLabel("Showing 0 of 0 items")
        layout.addWidget(self.count_label)

        self.editor_path = self.load_editor_path()
        self.unity_path_label.setText(f"Unity Editor: {self.editor_path}" if self.editor_path else "Unity Editor: Not set")

    def set_unity_editor_path(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Unity Editor Executable", "", "Executables (*.exe);;All Files (*)")
        if path:
            self.editor_path = path
            self.save_editor_path(path)
            self.unity_path_label.setText(f"Unity Editor: {path}")
            set_status_message(self, "Updated Unity editor path")

    def save_editor_path(self, path):
        try:
            with UNITY_EDITOR_PATH_FILE.open("w", encoding="utf-8") as file_obj:
                file_obj.write(path)
        except OSError as exc:
            QMessageBox.warning(self, "Save Failed", f"Could not save editor path:\n{exc}")

    def load_editor_path(self):
        if UNITY_EDITOR_PATH_FILE.exists():
            try:
                with UNITY_EDITOR_PATH_FILE.open("r", encoding="utf-8") as file_obj:
                    return file_obj.read().strip()
            except OSError as exc:
                print(f"Failed to load Unity editor path: {exc}")
        return ""

    def scan_unity_projects(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Unity Projects Directory")
        if dir_path:
            self.unity_project_list.clear()
            project_paths, truncated = collect_unity_projects_limited(dir_path, MAX_UI_LIST_ITEMS)

            for project_path in sorted(project_paths, key=str.lower):
                add_categorized_item(self.unity_project_list, project_path, project_path, "unity")

            self.apply_filter()
            set_status_message(self, f"Found {self.unity_project_list.count()} Unity project(s)")
            if truncated:
                show_truncated_scan_message(self, "Unity projects", MAX_UI_LIST_ITEMS)

    def apply_filter(self):
        visible_count = apply_filter_to_list(self.unity_project_list, self.filter_input.text())
        update_count_label(self.count_label, visible_count, self.unity_project_list.count())

    def launch_selected_project(self):
        selected_item = self.unity_project_list.currentItem()
        if not selected_item:
            QMessageBox.information(self, "No Selection", "Select a Unity project first.")
            return
        self.launch_project_from_item(selected_item)

    def launch_project_from_item(self, item):
        project_path = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(project_path, str):
            self.launch_project(project_path)

    def launch_project(self, project_path):
        if not self.editor_path or not os.path.exists(self.editor_path):
            QMessageBox.warning(self, "Error", "Unity Editor path not set or invalid")
            return
        if not os.path.exists(project_path):
            QMessageBox.warning(self, "Error", "Unity project path is invalid")
            return

        try:
            subprocess.Popen([self.editor_path, "-projectPath", project_path])
        except OSError as exc:
            QMessageBox.warning(self, "Launch Failed", f"Could not launch Unity project:\n{exc}")


class DesktopManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SehTajDesk")
        self.setMinimumSize(980, 680)
        self.resize(1180, 760)

        self.tabs = QTabWidget()
        self.tabs.setMovable(True)
        self.tab_indices: dict[str, int] = {}

        self.tab_indices["Main Menu"] = self.tabs.addTab(MainMenuPage(self.open_tab_by_name), "Main Menu")
        self.tab_indices["Ebooks"] = self.tabs.addTab(EbookManager(), "Ebooks")
        self.tab_indices["Games"] = self.tabs.addTab(GameManager(), "Games")
        self.tab_indices["Programming"] = self.tabs.addTab(ProgrammingManager(), "Programming")
        self.tab_indices["PC Assets"] = self.tabs.addTab(PCAssetManager(), "PC Assets")
        self.tab_indices["Photos"] = self.tabs.addTab(PhotoManager(), "Photos")
        self.tab_indices["Unity Projects"] = self.tabs.addTab(UnityManager(), "Unity Projects")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.setCentralWidget(self.tabs)

        self.create_menus()
        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.showMessage("Ready - Main Menu", 2500)

    def open_tab_by_name(self, tab_name: str):
        index = self.tab_indices.get(tab_name)
        if index is not None:
            self.tabs.setCurrentIndex(index)

    def create_menus(self):
        menu_bar = self.menuBar()
        if menu_bar is None:
            return

        file_menu = menu_bar.addMenu("&File")
        if file_menu is None:
            return
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menu_bar.addMenu("&View")
        if view_menu is None:
            return
        home_action = QAction("Go To Main Menu", self)
        home_action.setShortcut(QKeySequence("Ctrl+Home"))
        home_action.triggered.connect(lambda: self.open_tab_by_name("Main Menu"))
        view_menu.addAction(home_action)

        refresh_action = QAction("Refresh Current Tab", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self.refresh_current_tab)
        view_menu.addAction(refresh_action)

        help_menu = menu_bar.addMenu("&Help")
        if help_menu is None:
            return
        about_action = QAction("About SehTajDesk", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def on_tab_changed(self, index: int):
        tab_name = self.tabs.tabText(index)
        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.showMessage(f"Switched to {tab_name}", 2000)

    def refresh_current_tab(self):
        tab_widget = self.tabs.currentWidget()
        if tab_widget is None:
            return

        refresh_fn = getattr(tab_widget, "refresh_list", None)
        if callable(refresh_fn):
            refresh_fn()
            status_bar = self.statusBar()
            if status_bar is not None:
                status_bar.showMessage("Refreshed current tab", 2000)
        else:
            status_bar = self.statusBar()
            if status_bar is not None:
                status_bar.showMessage("This tab has nothing to refresh", 2000)

    def show_about_dialog(self):
        QMessageBox.information(
            self,
            "About SehTajDesk",
            "SehTajDesk\n\n"
            "A personal desktop manager for ebooks, games, projects, assets, photos, and Unity workflows.",
        )


if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)

    main_window = DesktopManager()
    main_window.show()
    sys.exit(app.exec())
