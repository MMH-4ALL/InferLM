DARK = """
QWidget { background:#11151b; color:#e8edf4; font-family:'Inter','Segoe UI','DejaVu Sans'; font-size:13px; }
QLabel { background:transparent; }
QFrame#sidebar { background:#161c25; border-right:1px solid #28313e; }
QLabel#brand { font-size:25px; font-weight:700; color:#f5f8fc; }
QLabel#title { font-size:27px; font-weight:650; }
QLabel#subtitle { color:#aab7c8; }
QLabel#eyebrow { color:#92afd3; font-size:11px; font-weight:700; }
QLabel#status { color:#a9c9f4; padding:8px 12px; border:1px solid #34445a; border-radius:6px; }
QPushButton { background:#252f3d; border:1px solid #3b4b60; border-radius:6px; padding:9px 13px; }
QPushButton:hover { background:#33445b; border-color:#8ab2e8; }
QPushButton:focus,QLineEdit:focus,QPlainTextEdit:focus,QComboBox:focus { border:2px solid #a8caff; }
QPushButton:disabled { color:#8b95a4; background:#1d2530; border-color:#2b3543; }
QPushButton#primary { background:#426fa8; border-color:#6a94c7; color:#ffffff; }
QLineEdit,QPlainTextEdit,QTextBrowser,QSpinBox,QDoubleSpinBox,QComboBox {
 background:#161e29; border:1px solid #344154; border-radius:6px; padding:8px; selection-background-color:#416ba0;
}
QComboBox QAbstractItemView { background:#1d2735; selection-background-color:#385d8e; }
QListWidget { background:transparent; border:none; outline:0; }
QListWidget::item { padding:13px 12px; border-radius:5px; margin:2px 0; }
QListWidget::item:selected { background:#2a3e58; color:#edf5ff; }
QListWidget::item:hover { background:#263346; }
QTableWidget { background:#161e29; alternate-background-color:#1d2735; border:1px solid #344154; gridline-color:#2c3849; }
QHeaderView::section { background:#263346; color:#c8d6e8; padding:10px; border:none; }
QProgressBar { border:1px solid #344154; border-radius:4px; background:#161e29; min-height:8px; }
QProgressBar::chunk { background:#6f9bd0; }
QScrollBar:vertical { background:#161e29; width:10px; }
QScrollBar::handle:vertical { background:#4d5d73; border-radius:4px; min-height:24px; }
QToolTip { background:#263346; color:white; border:1px solid #667e9e; padding:5px; }
"""
LIGHT = DARK.replace("#11151b","#f5f7fb").replace("#161c25","#e9eef6").replace("#161e29","#ffffff") \
    .replace("#e8edf4","#202c3c").replace("#f5f8fc","#14243a").replace("#aab7c8","#4c5d75") \
    .replace("#a9c9f4","#254a7b").replace("#92afd3","#345680").replace("#252f3d","#e0e7f1") \
    .replace("#1d2735","#edf2f8").replace("#263346","#dae5f2").replace("#c8d6e8","#263c59")
def stylesheet(theme:str)->str:
    return LIGHT if theme=="light" else DARK

