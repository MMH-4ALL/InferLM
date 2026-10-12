import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

def runtime_env() -> dict[str,str]:
    return {k:v for k,v in os.environ.items() if not k.startswith("LLAMA_")}

@dataclass
class Capabilities:
    path: str
    version: str
    flags: set[str]
    help: str
    devices: str = ""

    def require(self,*flags: str):
        missing = set(flags)-self.flags
        if missing:
            raise ValueError("Runtime does not support "+", ".join(sorted(missing))+". Choose a compatible build.")

    def validate_offload(self,layers: int):
        if layers and not self.devices:
            raise ValueError("This runtime has no available accelerator. Use CPU settings or choose a GPU build.")

def inspect(path: Path) -> Capabilities:
    if not path.is_file():
        raise ValueError("Runtime not found: "+str(path)+". Choose a folder with llama-server and llama-bench.")
    kw: dict = {"capture_output":True,"text":True,"encoding":"utf-8","errors":"replace",
                "timeout":15,"env":runtime_env(),"creationflags":getattr(subprocess,"CREATE_NO_WINDOW",0) if os.name=="nt" else 0}
    result = subprocess.run([str(path),"--help"],**kw)
    version = subprocess.run([str(path),"--version"],**kw)
    if result.returncode:
        raise ValueError("Runtime help failed. Check shared libraries, CPU and backend compatibility.")
    text = result.stdout+result.stderr
    flags = set(re.findall(r"(?<!\w)--?[a-z][a-z0-9-]*",text))
    devices = ""
    if "--list-devices" in flags:
        listing = subprocess.run([str(path),"--list-devices"],**kw).stdout
        if "Available devices:" in listing:
            listing = listing.split("Available devices:",1)[1].strip()
            if listing and "(none)" not in listing:
                devices = listing[:4000]
    return Capabilities(str(path),(version.stdout+version.stderr).strip()[:2000],flags,text,devices)

def binaries(folder: str) -> tuple[Path,Path]:
    ext = ".exe" if os.name=="nt" else ""
    return Path(folder)/("llama-server"+ext),Path(folder)/("llama-bench"+ext)

