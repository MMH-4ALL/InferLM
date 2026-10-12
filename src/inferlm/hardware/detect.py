import csv
import io
import platform
import shutil
import subprocess
from pathlib import Path
import psutil
from inferlm.core.types import GPU,Hardware

def cpu_name() -> str:
    if platform.system() == "Linux":
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    return line.split(":",1)[1].strip()
        except OSError:
            pass
    if platform.system() == "Windows":
        try:
            import importlib
            registry = importlib.import_module("winreg")
            with registry.OpenKey(registry.HKEY_LOCAL_MACHINE,
                                  r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                return str(registry.QueryValueEx(key,"ProcessorNameString")[0]).strip()
        except (OSError,ImportError):
            pass
    return platform.processor() or platform.machine()

def detect(data_dir: Path) -> Hardware:
    ram,swap = psutil.virtual_memory(),psutil.swap_memory()
    gpus = []
    status = "Unavailable — no supported GPU telemetry provider"
    if shutil.which("nvidia-smi"):
        try:
            result = subprocess.run(["nvidia-smi","--query-gpu=name,memory.total,memory.free,driver_version",
                                     "--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=4,check=True)
            for row in csv.reader(io.StringIO(result.stdout)):
                name,total,free,driver = (part.strip() for part in row)
                gpus.append(GPU(name,int(total)*1024**2,int(free)*1024**2,driver))
            status = "Measured dedicated NVIDIA memory" if gpus else "Unavailable"
        except (OSError,ValueError,subprocess.SubprocessError):
            status = "Unavailable — GPU query failed"
    try:
        battery = psutil.sensors_battery()
        ac = battery.power_plugged if battery else None
    except (OSError,AttributeError):
        ac = None
    return Hardware(platform.system(),platform.machine(),cpu_name(),psutil.cpu_count(logical=False) or 1,
                    psutil.cpu_count(logical=True) or 1,ram.total,ram.available,swap.total,swap.used,
                    shutil.disk_usage(data_dir).free,gpus,status,ac)

def hardware_key(hw: Hardware) -> dict:
    return {"os":hw.os,"architecture":hw.architecture,"cpu":hw.cpu,"physical_cores":hw.physical_cores,
            "ram_total":hw.ram_total,"gpus":[{"name":g.name,"total":g.total,"driver":g.driver} for g in hw.gpus]}

