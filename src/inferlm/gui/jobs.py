import traceback
from PySide6.QtCore import QObject,Signal,Slot

class Worker(QObject):
    result = Signal(object)
    error = Signal(str)
    progress = Signal(str)
    chunk = Signal(str)
    finished = Signal()

    def __init__(self,operation):
        super().__init__()
        self.operation = operation

    @Slot()
    def run(self):
        try:
            self.result.emit(self.operation(self.progress.emit,self.chunk.emit))
        except Exception as exc:
            traceback.print_exc()
            self.error.emit(str(exc))
        finally:
            self.finished.emit()

