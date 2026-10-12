"""Keyboard-first command picker; all actions reuse the window's handlers."""
from collections.abc import Callable
from PySide6.QtCore import Qt,QEvent
from PySide6.QtWidgets import QDialog,QLineEdit,QListWidget,QListWidgetItem,QVBoxLayout,QLabel


class CommandPalette(QDialog):
    def __init__(self, parent, commands: list[tuple[str, str, Callable]]):
        super().__init__(parent)
        self.commands = commands
        self.setWindowTitle("InferLM commands")
        self.setMinimumWidth(520)
        self.resize(600,420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16,16,16,16)
        heading = QLabel("COMMANDS")
        heading.setObjectName("eyebrow")
        layout.addWidget(heading)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a command…")
        self.search.setAccessibleName("Search commands")
        layout.addWidget(self.search)
        self.results = QListWidget()
        self.results.setObjectName("commands")
        self.results.setAccessibleName("Available commands")
        layout.addWidget(self.results,1)
        hint = QLabel("Enter to run   ·   ↓ to select   ·   Esc to close")
        hint.setObjectName("hint")
        layout.addWidget(hint)
        self.search.installEventFilter(self)
        self.search.textChanged.connect(self.filter)
        self.search.returnPressed.connect(self.activate)
        self.results.itemActivated.connect(self.activate)
        self.results.itemClicked.connect(self.activate)
        self.filter("")
        self.search.setFocus()

    def eventFilter(self, watched, event):
        if watched is self.search and event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Down:
            if self.results.count():
                self.results.setFocus()
            return True
        return super().eventFilter(watched,event)

    def filter(self, query: str):
        self.results.clear()
        for index,(title,shortcut,_) in enumerate(self.commands):
            if query.casefold() in title.casefold():
                item = QListWidgetItem(title + ("    " + shortcut if shortcut else ""))
                item.setData(Qt.ItemDataRole.UserRole,index)
                self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)

    def activate(self, *_):
        item = self.results.currentItem()
        if item:
            action = self.commands[item.data(Qt.ItemDataRole.UserRole)][2]
            self.accept()
            action()
