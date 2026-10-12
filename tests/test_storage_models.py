import io
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from inferlm.models.gguf import GGUFError,read_model,assert_unchanged
from inferlm.storage.database import Database
from conftest import write_gguf

def test_import_and_deduplicate(services,model_file):
    one,two = services.import_model(model_file),services.import_model(model_file)
    assert one.id==two.id and len(services.models())==1
    assert one.weights==128 and len(one.fingerprint)==64
    services.db.delete("models",one.id)
    assert model_file.exists()

@pytest.mark.parametrize("data",[b"",b"GGUF",b"bad file",b"GGUF"+bytes(100)])
def test_malformed(tmp_path,data):
    path = tmp_path/"bad.gguf"
    path.write_bytes(data)
    with pytest.raises(GGUFError):
        read_model(path)

def test_truncated_metadata(tmp_path,model_file):
    path = tmp_path/"bad.gguf"
    path.write_bytes(model_file.read_bytes()[:35])
    with pytest.raises(GGUFError):
        read_model(path)

def test_split_rejected(tmp_path):
    with pytest.raises(GGUFError,match="Split"):
        read_model(write_gguf(tmp_path/"split.gguf",overrides={"split.count":2}))

def test_modified_contents_invalidate(model_file):
    model = read_model(model_file)
    data = bytearray(model_file.read_bytes())
    data[-1] = 1
    model_file.write_bytes(data)
    with pytest.raises(GGUFError,match="contents changed"):
        assert_unchanged(model)

def test_missing_file(model_file):
    model = read_model(model_file)
    model_file.unlink()
    with pytest.raises(GGUFError,match="missing"):
        assert_unchanged(model)

def test_parallel_connections(tmp_path):
    db = Database(tmp_path/"db.sqlite")
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda i:db.put("example",str(i),{"n":i}),range(40)))
    assert len(db.list("example"))==40
    assert db.get("example","9")=={"n":9}
    db.delete("example","9")
    assert db.get("example","9") is None

def test_future_schema_rejected(tmp_path):
    path = tmp_path/"db.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=999")
    with pytest.raises(RuntimeError,match="newer"):
        Database(path)

def test_chat_export_retry(services,model_file,tmp_path):
    conv = services.new_conversation(services.import_model(model_file).id)
    conv["messages"] = [{"role":"user","content":"Hi","state":"complete"},
                        {"role":"assistant","content":"Hello","state":"interrupted"}]
    services.db.put("conversations",conv["id"],conv)
    path = tmp_path/"chat.md"
    services.export_conversation(conv["id"],path)
    assert "Hello" in path.read_text()
    assert services.retry(conv["id"])=="Hi"
    assert services.db.get("conversations",conv["id"])["messages"]==[]

def test_total_metadata_limit(tmp_path,monkeypatch):
    from inferlm.models import gguf
    monkeypatch.setattr(gguf,"MAX_METADATA",32)
    reader = gguf.Reader(io.BytesIO(bytes(100)),100)
    reader.read(24)
    with pytest.raises(GGUFError,match="Truncated"):
        reader.read(16)

