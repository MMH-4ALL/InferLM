import os
import re
import secrets
import socket
import subprocess
import threading
import time
from collections import deque
import httpx
import psutil
from filelock import FileLock,Timeout
from inferlm.core.types import Model,Settings
from inferlm.runtime.capabilities import binaries,inspect,runtime_env

class Cancelled(RuntimeError):
    pass

class Runtime:
    def __init__(self,lease: FileLock):
        self.lease = lease
        self.process: subprocess.Popen | None = None
        self.logs: deque[str] = deque(maxlen=300)
        self.url,self.key = "",""
        self.model: Model | None = None
        self.settings: Settings | None = None
        self.load_seconds,self.reserve = 0.,0
        self.version = ""
        self._lock_held = False
        self._reader: threading.Thread | None = None

    def load(self,folder: str,model: Model,settings: Settings,cancel: threading.Event,reserve_bytes:int|None=None):
        self.stop()
        settings.validate()
        caps = inspect(binaries(folder)[0])
        caps.require("--model","--ctx-size","--threads","--gpu-layers","--batch-size","--ubatch-size",
                     "--host","--port","--api-key")
        caps.validate_offload(settings.gpu_layers)
        try:
            self.lease.acquire(timeout=0)
            self._lock_held = True
        except Timeout as exc:
            raise RuntimeError("Another InferLM window or CLI owns the runtime. Unload it first.") from exc
        try:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1",0))
                port = sock.getsockname()[1]
            self.key = secrets.token_urlsafe(32)
            args = [caps.path,"--model",model.path,"--ctx-size",str(settings.context),
                    "--threads",str(settings.threads),"--gpu-layers",str(settings.gpu_layers),
                    "--batch-size",str(settings.batch),"--ubatch-size",str(settings.ubatch),
                    "--host","127.0.0.1","--port",str(port)]
            for flag in ("--no-webui","--no-context-shift","--offline"):
                if flag in caps.flags:
                    args.append(flag)
            if "--parallel" in caps.flags:
                args += ["--parallel","1"]
            env = runtime_env()
            env["LLAMA_API_KEY"] = self.key
            kw: dict = {"creationflags":getattr(subprocess,"CREATE_NO_WINDOW",0)} if os.name=="nt" else {"start_new_session":True}
            started = time.monotonic()
            self.reserve = max(2*1024**3,int(psutil.virtual_memory().total*.2),reserve_bytes or 0)
            initial_swap = psutil.swap_memory().used
            self.process = subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                            text=True,encoding="utf-8",errors="replace",env=env,**kw)
            self.logs.clear()
            stream = self.process.stdout
            def drain():
                if stream:
                    for line in stream:
                        self.logs.append(line.strip().replace(self.key,"[redacted]")[:2000])
            self._reader = threading.Thread(target=drain,daemon=True)
            self._reader.start()
            self.url = f"http://127.0.0.1:{port}"
            with httpx.Client(trust_env=False,timeout=1) as client:
                while time.monotonic()-started < 180:
                    if cancel.is_set():
                        raise Cancelled("Model loading cancelled.")
                    if psutil.virtual_memory().available < self.reserve or psutil.swap_memory().used-initial_swap > 256*1024**2:
                        raise RuntimeError("Model loading crossed the memory safety limit.")
                    if self.process.poll() is not None:
                        raise RuntimeError("Runtime exited while loading. Check the log and model/backend compatibility.")
                    try:
                        if client.get(self.url+"/health").status_code == 200:
                            self.model,self.settings = model,settings
                            self.load_seconds,self.version = time.monotonic()-started,caps.version
                            offloads = [int(n) for line in self.logs for n in re.findall(r"offloaded (\d+)/",line)]
                            if settings.gpu_layers and (not offloads or max(offloads)<settings.gpu_layers):
                                raise RuntimeError("Runtime did not confirm the requested GPU offload.")
                            return
                    except httpx.HTTPError:
                        pass
                    cancel.wait(.15)
            raise RuntimeError("Loading timed out after 180 seconds.")
        except BaseException:
            self.stop()
            raise

    def stop(self):
        proc = self.process
        if proc:
            try:
                owner = psutil.Process(proc.pid)
                targets = owner.children(recursive=True)+[owner]
                for child in targets:
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                _,alive = psutil.wait_procs(targets,timeout=3)
                for child in alive:
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
            except psutil.NoSuchProcess:
                pass
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            if self._reader:
                self._reader.join(timeout=1)
            if proc.stdout:
                proc.stdout.close()
        self.process,self.model,self.settings = None,None,None
        self.url,self.key = "",""
        if self._lock_held:
            self.lease.release()
            self._lock_held = False

    def headers(self):
        return {"Authorization":"Bearer "+self.key}

