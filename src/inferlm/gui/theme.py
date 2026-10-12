"""Warm neutral desktop tokens, inspired by terminal workspaces."""
TOKENS = {
    "dark": {
        "background": "#141413", "sidebar": "#191918", "surface": "#20201e",
        "raised": "#282825", "border": "#353531", "text": "#e5e3dd",
        "muted": "#a7a59d", "subtle": "#807e77", "accent": "#e0b184",
        "accent_text": "#21190f", "selection": "#3a342c", "disabled": "#73716b",
    },
    "light": {
        "background": "#faf9f5", "sidebar": "#f0efe9", "surface": "#f5f4ee",
        "raised": "#e8e6dd", "border": "#d8d5c9", "text": "#262520",
        "muted": "#656258", "subtle": "#716d61", "accent": "#7c4d20",
        "accent_text": "#ffffff", "selection": "#e5d8c6", "disabled": "#807c71",
    },
}


def colors(theme: str) -> dict[str, str]:
    return TOKENS["light" if theme == "light" else "dark"]


def document_style(theme: str) -> str:
    c = colors(theme)
    return f"""
        body {{ color: {c['text']}; font-size: 14px; }}
        h3 {{ color: {c['accent']}; font-size: 12px; margin-top: 26px; margin-bottom: 12px; }}
        p {{ line-height: 145%; margin-bottom: 14px; }}
        h1 {{ font-size: 23px; }} h2 {{ font-size: 18px; }}
        pre {{ background-color: {c['surface']}; padding: 16px; }}
        code {{ color: {c['accent']}; }}
        a {{ color: {c['accent']}; }}
        blockquote {{ color: {c['muted']}; }}
    """


_TEMPLATE = """
QWidget { background:$background; color:$text; font-family:'Cascadia Code','Consolas','DejaVu Sans Mono'; font-size:12px; }
QLabel { background:transparent; border:none; }
QFrame#sidebar { background:$sidebar; border-right:1px solid $border; }
QFrame#workspaceHeader { border-bottom:1px solid $border; }
QFrame#taskbar { border-top:1px solid $border; }
QLabel#brand { font-size:18px; font-weight:700; letter-spacing:-1px; }
QLabel#wordmark { font-size:38px; font-weight:700; letter-spacing:-2px; }
QLabel#brandMark { color:$accent; font-size:19px; font-weight:700; }
QLabel#title { font-size:22px; font-weight:600; }
QLabel#subtitle,QLabel#breadcrumb,QLabel#hint { color:$muted; }
QLabel#hint { font-size:10px; }
QLabel#eyebrow { color:$subtle; font-size:10px; }
QLabel#status { color:$accent; font-size:11px; }
QLabel#sessionTitle { font-size:14px; font-weight:600; }
QPushButton { background:transparent; border:1px solid $border; border-radius:4px; padding:8px 12px; }
QPushButton:hover { background:$raised; border-color:$muted; }
QPushButton:pressed { background:$selection; }
QPushButton:focus { border:1px solid $accent; }
QPushButton:disabled { color:$disabled; border-color:$border; }
QPushButton#primary { background:$accent; border-color:$accent; color:$accent_text; font-weight:600; }
QPushButton#primary:hover { background:$text; border-color:$text; color:$background; }
QPushButton#primary:disabled { background:$raised; color:$disabled; border-color:$border; }
QPushButton#ghost { border:1px solid transparent; padding:6px 8px; color:$muted; }
QPushButton#ghost:hover { background:$raised; color:$text; }
QPushButton#ghost:focus { border-color:$accent; }
QPushButton#suggestion { text-align:left; padding:13px 14px; background:$surface; }
QLineEdit,QPlainTextEdit,QSpinBox,QDoubleSpinBox,QComboBox {
 background:$surface; border:1px solid $border; border-radius:4px; padding:8px; selection-background-color:$selection;
}
QLineEdit:focus,QPlainTextEdit:focus,QComboBox:focus,QSpinBox:focus,QDoubleSpinBox:focus { border-color:$accent; }
QLineEdit:disabled,QPlainTextEdit:disabled,QComboBox:disabled { color:$disabled; }
QLineEdit#sessionSearch { background:$surface; font-size:11px; padding:8px; }
QComboBox { padding-right:24px; }
QComboBox::drop-down { border:none; width:20px; }
QComboBox QAbstractItemView { background:$surface; color:$text; selection-background-color:$selection; border:1px solid $border; }
QFrame#composerFrame { background:$surface; border:1px solid $border; border-left:2px solid $accent; border-radius:5px; }
QPlainTextEdit#composer { border:none; padding:8px 4px; font-size:13px; }
QPlainTextEdit#composer:focus { border:none; }
QTextBrowser { border:1px solid $border; border-radius:4px; background:$surface; padding:12px; }
QTextBrowser#transcript { background:$background; border:none; padding:0; font-size:14px; }
QListWidget { background:transparent; border:none; outline:0; }
QListWidget::item { padding:10px 12px; border-radius:3px; margin:1px 0; }
QListWidget::item:selected { background:$selection; color:$text; }
QListWidget::item:hover { background:$raised; }
QListWidget::item:focus { border:1px solid $accent; }
QListWidget#navigation::item { padding:8px 10px; }
QListWidget#sessions::item { padding:10px; font-size:11px; }
QTableWidget { background:$background; alternate-background-color:$surface; border:1px solid $border; gridline-color:$border; selection-background-color:$selection; }
QHeaderView::section { background:$surface; color:$muted; padding:12px; border:none; border-bottom:1px solid $border; }
QTableWidget QTableCornerButton::section { background:$surface; border:none; }
QMenu { background:$surface; color:$text; border:1px solid $border; padding:4px; }
QMenu::item { padding:9px 18px; }
QMenu::item:selected { background:$selection; }
QMenu::item:disabled { color:$disabled; }
QMenu::separator { height:1px; background:$border; margin:4px; }
QProgressBar { border:none; background:$raised; min-height:2px; max-height:2px; }
QProgressBar::chunk { background:$accent; }
QScrollArea { border:none; background:transparent; }
QSplitter::handle { background:$border; width:1px; }
QScrollBar:vertical { background:transparent; width:8px; margin:0; }
QScrollBar:horizontal { background:transparent; height:8px; margin:0; }
QScrollBar::handle { background:$border; border-radius:3px; min-height:24px; min-width:24px; }
QScrollBar::handle:hover { background:$subtle; }
QScrollBar::add-line,QScrollBar::sub-line { height:0; width:0; }
QScrollBar::add-page,QScrollBar::sub-page { background:transparent; }
QToolTip { background:$surface; color:$text; border:1px solid $border; padding:7px; }
QDialog { background:$background; }
QListWidget#commands::item { padding:14px 12px; }
"""


def stylesheet(theme: str) -> str:
    # Kept separate so token replacements cannot overlap (accent vs accent_text).
    c = colors(theme)
    template = _TEMPLATE
    for key in sorted(c, key=len, reverse=True):
        template = template.replace("$" + key, c[key])
    return template
