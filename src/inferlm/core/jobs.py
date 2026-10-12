import threading
import psutil

class MemoryGuard:
    def __init__(self,reserve:int,cancel:threading.Event,close_stream):
        self.reserve,self.cancel,self.close_stream = reserve,cancel,close_stream
        self.done = threading.Event()
        self.reason = ""
        self.thread: threading.Thread | None = None

    def __enter__(self):
        initial_swap = psutil.swap_memory().used
        def observe():
            while not self.done.wait(.25):
                if psutil.virtual_memory().available < self.reserve or psutil.swap_memory().used-initial_swap > 256*1024**2:
                    self.reason = "Generation stopped because memory crossed the safety limit."
                    self.cancel.set()
                    self.close_stream()
                    return
        self.thread = threading.Thread(target=observe,daemon=True)
        self.thread.start()
        return self

    def __exit__(self,*args):
        self.done.set()
        if self.thread:
            self.thread.join(timeout=1)
        if self.reason:
            raise RuntimeError(self.reason)

