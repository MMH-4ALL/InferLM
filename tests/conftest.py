import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import struct
from pathlib import Path
import pytest
from inferlm.core.services import Services

def write_gguf(path:Path,architecture="llama",overrides=None):
    metadata = {"general.architecture":architecture,"general.name":"Test model",
                architecture+".block_count":2,architecture+".embedding_length":32,
                architecture+".attention.head_count":4,architecture+".attention.head_count_kv":2}
    metadata.update(overrides or {})
    def string(value):
        raw = value.encode()
        return struct.pack("<Q",len(raw))+raw
    data = b"GGUF"+struct.pack("<IQQ",3,1,len(metadata))
    for key,value in metadata.items():
        data += string(key)
        data += struct.pack("<I",8)+string(value) if isinstance(value,str) else struct.pack("<II",4,value)
    data += string("blk.0.weight")+struct.pack("<I",1)+struct.pack("<Q",32)+struct.pack("<IQ",0,0)
    data += bytes((-len(data))%32)+bytes(128)
    path.write_bytes(data)
    return path

@pytest.fixture
def model_file(tmp_path):
    return write_gguf(tmp_path/"نموذج with spaces.gguf")

@pytest.fixture
def services(tmp_path):
    s = Services(tmp_path/"data")
    yield s
    s.close()

