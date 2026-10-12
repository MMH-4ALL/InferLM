"""Bounded little-endian GGUF v2/v3 metadata reader. Never deserialize weights."""
import hashlib
import math
import struct
from collections import Counter
from pathlib import Path
from inferlm.core.types import Model, identifier

SCALARS = {0:"B",1:"b",2:"H",3:"h",4:"I",5:"i",6:"f",7:"?",10:"Q",11:"q",12:"d"}
QUANTS = {0:"F32",1:"F16",2:"Q4_0",3:"Q4_1",6:"Q5_0",7:"Q5_1",8:"Q8_0",9:"Q8_1",
          10:"Q2_K",11:"Q3_K",12:"Q4_K",13:"Q5_K",14:"Q6_K",15:"Q8_K",30:"BF16"}
BLOCKS = {0:(1,4),1:(1,2),2:(32,18),3:(32,20),6:(32,22),7:(32,24),8:(32,34),9:(32,40),
          10:(256,84),11:(256,110),12:(256,144),13:(256,176),14:(256,210),15:(256,292),30:(1,2)}
MAX_METADATA = 64*1024**2

class GGUFError(ValueError):
    pass

class Reader:
    def __init__(self, stream, size: int):
        self.stream, self.size, self.entries = stream, size, 0

    def read(self, n: int) -> bytes:
        if n < 0 or n > MAX_METADATA or self.stream.tell()+n > min(self.size,MAX_METADATA):
            raise GGUFError("Truncated or excessively large GGUF metadata.")
        data = self.stream.read(n)
        if len(data) != n:
            raise GGUFError("Truncated GGUF file.")
        return data

    def number(self, fmt: str):
        return struct.unpack("<"+fmt,self.read(struct.calcsize("<"+fmt)))[0]

    def string(self, retain=True):
        n = self.number("Q")
        if n > 1024**2:
            raise GGUFError("GGUF string exceeds the safety limit.")
        data = self.read(n)
        if not retain:
            return None
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GGUFError("Invalid UTF-8 in GGUF metadata.") from exc

    def value(self, typ: int, retain=True):
        self.entries += 1
        if self.entries > 4_000_000:
            raise GGUFError("GGUF metadata exceeds the safety limit.")
        if typ in SCALARS:
            return self.number(SCALARS[typ])
        if typ == 8:
            return self.string(retain)
        if typ != 9:
            raise GGUFError("Unknown GGUF metadata type.")
        element, count = self.number("I"),self.number("Q")
        if count > 2_000_000 or element not in (*SCALARS,8):
            raise GGUFError("Invalid or excessively large GGUF array.")
        if element in SCALARS:
            data = self.read(struct.calcsize("<"+SCALARS[element])*count)
            return list(struct.unpack("<"+str(count)+SCALARS[element],data)) if retain and count <= 512 else {"array_count":count}
        values = [self.string(retain and count <= 64) for _ in range(count)]
        return values if retain and count <= 64 else {"array_count":count}

def read_model(path: Path) -> Model:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise GGUFError("Model is missing. Choose an existing .gguf file.")
    size = path.stat().st_size
    with path.open("rb") as stream:
        r = Reader(stream,size)
        if r.read(4) != b"GGUF" or r.number("I") not in (2,3):
            raise GGUFError("Only little-endian GGUF v2 and v3 are supported.")
        tensor_count, metadata_count = r.number("Q"),r.number("Q")
        if not 0 < tensor_count <= 200_000 or metadata_count > 100_000:
            raise GGUFError("Invalid tensor/metadata count.")
        metadata = {}
        for _ in range(metadata_count):
            key,typ = r.string(),r.number("I")
            metadata[key] = r.value(typ,not key.startswith("tokenizer.ggml."))
        if metadata.get("split.count",1) != 1:
            raise GGUFError("Split GGUF is not supported in 0.1. Import a single-file model.")
        architecture = metadata.get("general.architecture")
        if not isinstance(architecture,str):
            raise GGUFError("Missing architecture metadata.")
        tensors = []
        for _ in range(tensor_count):
            name,dims = r.string(),r.number("I")
            if not 1 <= dims <= 4:
                raise GGUFError("Invalid tensor dimensions.")
            shape = [r.number("Q") for _ in range(dims)]
            if any(d == 0 or d > 2**32 for d in shape) or math.prod(shape) > 2**48:
                raise GGUFError("Invalid tensor shape.")
            tensors.append({"name":name,"shape":shape,"type":r.number("I"),"offset":r.number("Q")})
        alignment = metadata.get("general.alignment",32)
        if not isinstance(alignment,int) or not 1 <= alignment <= 4096 or alignment & (alignment-1):
            raise GGUFError("Invalid alignment.")
        data_start = (stream.tell()+alignment-1)//alignment*alignment
        weights = size-data_start
        ordered = sorted(tensors,key=lambda t:t["offset"])
        offsets = [t["offset"] for t in ordered]
        if weights <= 0 or len(set(offsets)) != len(offsets) or offsets[-1] >= weights:
            raise GGUFError("Tensor data is truncated or overlaps.")
        for i,tensor in enumerate(ordered):
            end = ordered[i+1]["offset"] if i+1 < len(ordered) else weights
            tensor["bytes"] = end-tensor["offset"]
            if tensor["type"] not in BLOCKS:
                raise GGUFError("Unvalidated quantization. Use F16/BF16 or standard Q/K quants.")
            block,width = BLOCKS[tensor["type"]]
            if tensor["shape"][0] % block or math.prod(tensor["shape"])//block*width > tensor["bytes"]:
                raise GGUFError("Tensor data is truncated or its shape is invalid.")
    with path.open("rb") as stream:
        fingerprint = hashlib.file_digest(stream,"sha256").hexdigest()
    quantization = ", ".join(f"{name} ({count})" for name,count in Counter(
        QUANTS[t["type"]] for t in ordered).most_common(3))
    return Model(identifier(),str(path),str(metadata.get("general.name",path.stem)),size,weights,
                 architecture,quantization,fingerprint,metadata,ordered)

def assert_unchanged(model: Model) -> None:
    path = Path(model.path)
    if not path.is_file() or path.stat().st_size != model.size:
        raise GGUFError("Model changed or is missing. Relink/import it again.")
    with path.open("rb") as stream:
        if hashlib.file_digest(stream,"sha256").hexdigest() != model.fingerprint:
            raise GGUFError("Model contents changed. Import again to invalidate old profiles.")

