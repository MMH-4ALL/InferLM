from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

GIB = 1024**3

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def identifier() -> str:
    return uuid.uuid4().hex[:12]

@dataclass
class GPU:
    name: str
    total: int | None = None
    free: int | None = None
    driver: str | None = None
    memory_kind: str = "dedicated"

@dataclass
class Hardware:
    os: str
    architecture: str
    cpu: str
    physical_cores: int
    logical_cores: int
    ram_total: int
    ram_available: int
    swap_total: int
    swap_used: int
    disk_free: int
    gpus: list[GPU] = field(default_factory=list)
    gpu_status: str = "Unavailable"
    ac_power: bool | None = None
    timestamp: str = field(default_factory=now)

@dataclass
class Model:
    id: str
    path: str
    name: str
    size: int
    weights: int
    architecture: str
    quantization: str
    fingerprint: str
    metadata: dict[str, Any]
    tensors: list[dict[str, Any]] = field(default_factory=list)
    added: str = field(default_factory=now)

@dataclass(frozen=True)
class Settings:
    context: int = 2048
    threads: int = 4
    gpu_layers: int = 0
    batch: int = 256
    ubatch: int = 128

    def validate(self) -> None:
        if not 256 <= self.context <= 131072:
            raise ValueError("Context must be 256–131072 tokens.")
        if not 1 <= self.threads <= 256 or not 0 <= self.gpu_layers <= 1000:
            raise ValueError("Invalid threads or GPU layer count.")
        if not 16 <= self.ubatch <= self.batch <= 8192:
            raise ValueError("Microbatch must be at least 16 and cannot exceed batch (maximum 8192).")

@dataclass
class MemoryPlan:
    classification: str
    ram_required: int | None
    vram_required: int | None
    kv_bytes: int | None
    reserve: int
    assumptions: list[str]
    label: str = "Estimated"

def plain(value: Any) -> Any:
    return asdict(value) if hasattr(value, "__dataclass_fields__") else value

