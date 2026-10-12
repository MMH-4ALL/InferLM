import sys
from inferlm.core.services import Services
from inferlm import __version__

def main():
    try:
        from PySide6.QtCore import QTimer,QCoreApplication,QEvent
        from PySide6.QtWidgets import QApplication
        from inferlm.gui.window import Window
    except ImportError:
        raise SystemExit("Desktop dependencies missing. Install inferlm[gui,cli].") from None
    smoke = "--smoke-test" in sys.argv
    if smoke:
        sys.argv.remove("--smoke-test")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("InferLM")
    app.setApplicationVersion(__version__)
    window = Window(Services())
    window.show()
    if smoke:
        QTimer.singleShot(2000,window.close)
    result = app.exec()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    app.processEvents()
    if smoke:
        print("InferLM native GUI smoke test passed",flush=True)
    return result

if __name__=="__main__":
    raise SystemExit(main())

