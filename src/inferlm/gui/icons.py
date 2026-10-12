from PySide6.QtCore import QByteArray,Qt
from PySide6.QtGui import QIcon,QPainter,QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS = ['<path d="M4 4h16v12H9l-5 4z"/>',
         '<path d="M4 7l8-4 8 4v10l-8 4-8-4zM4 7l8 4 8-4M12 11v10"/>',
         '<path d="M5 4v16M12 4v16M19 4v16"/><circle cx="5" cy="9" r="2"/><circle cx="12" cy="15" r="2"/><circle cx="19" cy="7" r="2"/>',
         '<path d="M4 20h16M6 17v-5M12 17V5M18 17V9"/>',
         '<path d="M12 8a4 4 0 100 8 4 4 0 000-8zM12 3v3M12 18v3M3 12h3M18 12h3M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2"/>']

def icon(index:int)->QIcon:
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="#89a8cf" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round">'+PATHS[index]+'</g></svg>'
    pixmap = QPixmap(24,24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    return QIcon(pixmap)

