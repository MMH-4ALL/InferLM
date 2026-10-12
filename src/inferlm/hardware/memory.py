import re
from inferlm.core.types import GIB,Model,Hardware,Settings,MemoryPlan

SUPPORTED = {"llama","qwen2","qwen3","gemma","gemma2","mistral"}

def plan(model: Model,hw: Hardware,settings: Settings,reserve_gib: int=2) -> MemoryPlan:
    settings.validate()
    reserve = max(2*GIB,reserve_gib*GIB,int(hw.ram_total*.2))
    assumptions = ["Estimated; loading and smooth performance are not guaranteed.",
                   "Full file-backed weights conservatively remain reserved in RAM.",
                   "Compute buffers use a 512 MiB + batch-dependent allowance.",
                   "Repacking, memory mapping and backend allocations can change actual use."]
    m,a = model.metadata,model.architecture
    kv = None
    if a in SUPPORTED and not m.get(a+".expert_count",0):
        fields = [m.get(a+suffix) for suffix in (".block_count",".embedding_length",
                                                ".attention.head_count",".attention.head_count_kv")]
        if all(isinstance(x,int) and x > 0 for x in fields):
            layers,width,heads,kvheads = [int(x or 0) for x in fields]
            keydim,valdim = m.get(a+".attention.key_length",width//heads),m.get(a+".attention.value_length",width//heads)
            if all(isinstance(x,int) and 0 < x <= 65536 for x in (keydim,valdim)):
                kv = settings.context*layers*kvheads*(int(keydim)+int(valdim))*2
                assumptions.append("KV uses full-context f16 K/V, without sliding-window discounts.")
    if kv is None:
        return MemoryPlan("Not enough information",None,None,None,reserve,
                          assumptions+["No validated architecture-specific KV estimate. Automatic tuning disabled."])
    buffers = 512*1024**2+settings.batch*1024**2
    ram,vram = model.weights+kv+buffers,0
    if settings.gpu_layers:
        if not hw.gpus or hw.gpus[0].free is None or hw.gpus[0].memory_kind != "dedicated":
            return MemoryPlan("Not enough information",ram,None,kv,reserve,
                              assumptions+["Dedicated GPU free memory is unavailable."])
        count = int(m.get(a+".block_count",0))
        gpu_weights = sum(t["bytes"] for t in model.tensors if
                          (match:=re.match(r"blk\.(\d+)\.",t["name"])) and
                          int(match[1]) >= max(0,count-settings.gpu_layers))
        if settings.gpu_layers > count:
            gpu_weights = model.weights
        vram = gpu_weights+kv+buffers
    available = hw.ram_available-reserve
    gpu_free = (hw.gpus[0].free or 0)-max(512*1024**2,int((hw.gpus[0].total or 0)*.1)) if hw.gpus else 0
    if ram > available or (vram > 0 and vram > gpu_free):
        status = "Unlikely to fit"
    elif ram > available*.8 or (vram > 0 and vram > gpu_free*.8):
        status = "Close to memory limits"
    else:
        status = "Likely to fit"
    return MemoryPlan(status,ram,vram,kv,reserve,assumptions)

