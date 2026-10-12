import os
from pathlib import Path
import httpx
import pytest
from inferlm.core.types import Settings
from inferlm.runtime.manager import Cancelled
from inferlm.optimization.benchmark import run

@pytest.fixture
def real_services(services):
    folder,model = os.environ.get("INFERLM_TEST_RUNTIME"),os.environ.get("INFERLM_TEST_MODEL")
    if not folder or not model:
        pytest.skip("Real runtime/model not configured; not a simulated pass.")
    services.save_config({"runtime_folder":folder,"max_tokens":32})
    services.import_model(Path(model))
    return services

@pytest.mark.real
def test_real_load_stream_auth_cleanup(real_services):
    s = real_services
    model = s.models()[0]
    s.load(model.id,Settings(threads=2))
    proc = s.runtime.process
    with httpx.Client(trust_env=False) as client:
        assert client.post(s.runtime.url+"/v1/chat/completions",
                           json={"messages":[{"role":"user","content":"hello"}]}).status_code==401
    conv = s.new_conversation(model.id)
    pieces = []
    result = s.chat(conv["id"],"Tell a short story about a student.",pieces.append)
    assert result["text"] and "".join(pieces)==result["text"]
    assert result["usage"]["completion_tokens"]>0
    assert s.db.get("conversations",conv["id"])["messages"][-1]["state"]=="complete"
    s.runtime.stop()
    assert proc.poll() is not None

@pytest.mark.real
def test_real_repeat_load_cancel(real_services):
    s = real_services
    model = s.models()[0]
    for _ in range(3):
        s.cancel.clear()
        s.load(model.id,Settings(threads=2))
        proc = s.runtime.process
        s.runtime.stop()
        assert proc.poll() is not None
    s.cancel.set()
    with pytest.raises(Cancelled):
        s.load(model.id,Settings(threads=2))
    assert s.runtime.process is None

@pytest.mark.real
def test_real_benchmark(real_services):
    s = real_services
    report = run(s,s.models()[0],Settings(threads=2),timeout=120)
    assert report["label"]=="Measured" and len(report["server_samples"])==6
    assert len({x["workload_tokens"] for x in report["server_samples"]})==2
    assert all(len(row["samples_ts"])==3 for row in report["native"]["rows"])
    assert report["conditions"]["quality"]=="Not evaluated"
    assert s.runtime.process is None

