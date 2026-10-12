import pytest
from inferlm.core.services import Services
from inferlm.core.types import GIB,Settings
from inferlm.hardware.memory import plan
from inferlm.models.gguf import read_model,GGUFError
from test_memory_search import hardware

def test_recovery_after_interruption(services):
    services.db.put("conversations","recover",{"id":"recover","messages":[
        {"role":"assistant","content":"partial","state":"generating"}]})
    reopened = Services(services.data_dir)
    assert reopened.db.get("conversations","recover")["messages"][0]["state"]=="interrupted"
    reopened.close()

def test_live_instance_not_changed(services):
    services.db.put("conversations","active",{"id":"active","messages":[
        {"role":"assistant","content":"","state":"generating"}]})
    with services.lease.acquire(timeout=0):
        another = Services(services.data_dir)
        assert another.db.get("conversations","active")["messages"][0]["state"]=="generating"
        another.close()

def test_custom_reserve(model_file):
    assert plan(read_model(model_file),hardware(),Settings(),reserve_gib=5).reserve==5*GIB

def test_truncated_weights(model_file):
    model_file.write_bytes(model_file.read_bytes()[:-100])
    with pytest.raises(GGUFError,match="truncated"):
        read_model(model_file)

def test_trim_preserves_original(services,model_file,monkeypatch):
    model = services.import_model(model_file)
    services.runtime.model,services.runtime.settings = model,Settings()
    conv = services.new_conversation(model.id)
    conv["draft"] = "Latest question"
    conv["messages"] = [{"role":"user" if i%2==0 else "assistant","content":str(i),"state":"complete"} for i in range(8)]
    services.db.put("conversations",conv["id"],conv)
    monkeypatch.setattr(services.client,"token_count",lambda messages:len(messages)*300)
    branch = services.trim_conversation(conv["id"])
    assert branch["id"]!=conv["id"] and branch["draft"]=="Latest question"
    assert len(branch["messages"])==2 and branch["messages"][-1]["content"]=="7"
    assert len(services.db.get("conversations",conv["id"])["messages"])==8

