import json
import subprocess
import sys
import threading
import time
from dataclasses import asdict
from types import SimpleNamespace
import httpx
import pytest
from filelock import FileLock,Timeout
from inferlm.runtime.client import Client
from inferlm.runtime.manager import Runtime,Cancelled
from inferlm.runtime.capabilities import Capabilities,runtime_env
from inferlm.optimization.benchmark import guarded_process
from inferlm.core.types import Settings

def test_capabilities_separate():
    caps = Capabilities("server","fake",{"--host","--api-key"},"")
    caps.require("--host")
    with pytest.raises(ValueError):
        caps.require("-o")

def test_no_ambient_flags(monkeypatch):
    monkeypatch.setenv("LLAMA_ARG_AGENT","1")
    monkeypatch.setenv("LLAMA_API_KEY","private")
    assert not any(k.startswith("LLAMA_") for k in runtime_env())

def test_cross_instance_lease(tmp_path):
    first,second = FileLock(str(tmp_path/"runtime.lock")),FileLock(str(tmp_path/"runtime.lock"))
    with first.acquire(timeout=0):
        with pytest.raises(Timeout):
            second.acquire(timeout=0)

def test_owned_shutdown(tmp_path):
    runtime = Runtime(FileLock(str(tmp_path/"runtime.lock")))
    proc = subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"])
    runtime.process = proc
    runtime.stop()
    assert proc.poll() is not None and runtime.process is None

def test_timeout_cleanup():
    started = time.monotonic()
    with pytest.raises(RuntimeError,match="time budget"):
        guarded_process([sys.executable,"-c","import time;time.sleep(60)"],threading.Event(),0,.2)
    assert time.monotonic()-started<5

def test_benchmark_cancel():
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(Cancelled):
        guarded_process([sys.executable,"-c","import time;time.sleep(60)"],cancel,0,10)

class Fragmented(httpx.SyncByteStream):
    def __iter__(self):
        events = [{"choices":[{"delta":{"content":"Hello 🌍"}}]},{"choices":[],"usage":{"completion_tokens":2}}]
        data = "".join("data: "+json.dumps(e,ensure_ascii=False)+"\n\n" for e in events)+"data: [DONE]\n\n"
        raw = data.encode()
        for i in range(0,len(raw),3):
            yield raw[i:i+3]

def test_stream_fragments_utf8(monkeypatch):
    original = httpx.Client
    transport = httpx.MockTransport(lambda request:httpx.Response(200,stream=Fragmented()))
    monkeypatch.setattr(httpx,"Client",lambda **kwargs:original(transport=transport,**kwargs))
    runtime = SimpleNamespace(process=SimpleNamespace(poll=lambda:None),url="http://127.0.0.1:123",
                              headers=lambda:{"Authorization":"Bearer test"})
    pieces = []
    result = Client(runtime).generate([{"role":"user","content":"Hi"}],threading.Event(),pieces.append)
    assert "".join(pieces)=="Hello 🌍" and result["usage"]["completion_tokens"]==2
    assert result["ttft_seconds"]>=0

def test_context_limit_keeps_history(services,model_file,monkeypatch):
    model = services.import_model(model_file)
    services.runtime.model,services.runtime.settings = model,Settings(context=256)
    conv = services.new_conversation(model.id)
    monkeypatch.setattr(services.client,"token_count",lambda messages:1000)
    with pytest.raises(ValueError,match="history"):
        services.chat(conv["id"],"question",lambda _:None)
    assert services.db.get("conversations",conv["id"])["messages"]==[]
    assert services.db.get("conversations",conv["id"])["draft"]=="question"

def test_truncated_stream_is_not_reported_as_complete(monkeypatch):
    original = httpx.Client
    data = 'data: {"choices":[{"delta":{"content":"Partial"}}]}\n\n'
    transport = httpx.MockTransport(lambda request:httpx.Response(200,content=data))
    monkeypatch.setattr(httpx,"Client",lambda **kwargs:original(transport=transport,**kwargs))
    runtime = SimpleNamespace(process=SimpleNamespace(poll=lambda:None),url="http://127.0.0.1:123",
                              headers=lambda:{})
    pieces = []
    with pytest.raises(RuntimeError,match="before generation finished"):
        Client(runtime).generate([],threading.Event(),pieces.append)
    assert pieces==["Partial"]

def test_generation_cancelled_before_request(monkeypatch):
    cancel = threading.Event()
    cancel.set()
    monkeypatch.setattr(httpx,"Client",lambda **kwargs:pytest.fail("Cancelled jobs must not contact the runtime"))
    with pytest.raises(Cancelled):
        Client(SimpleNamespace()).generate([],cancel,lambda _:None)

def test_partial_persisted(services,model_file,monkeypatch):
    model = services.import_model(model_file)
    services.runtime.model,services.runtime.settings = model,Settings()
    conv = services.new_conversation(model.id)
    monkeypatch.setattr(services.client,"token_count",lambda messages:10)
    def interrupted(messages,cancel,emit,*args):
        emit("Partial answer")
        raise Cancelled("Stopped")
    monkeypatch.setattr(services.client,"generate",interrupted)
    with pytest.raises(Cancelled):
        services.chat(conv["id"],"question",lambda _:None)
    message = services.db.get("conversations",conv["id"])["messages"][-1]
    assert message["content"]=="Partial answer" and message["state"]=="interrupted"

def test_profile_invalidated(services,model_file,monkeypatch):
    model = services.import_model(model_file)
    services.db.put("profiles","p",{"model_id":model.id,"fingerprint":model.fingerprint,"hardware":{},
                                  "runtime_version":"old","settings":asdict(Settings())})
    monkeypatch.setattr("inferlm.runtime.capabilities.inspect",lambda _:SimpleNamespace(version="new"))
    with pytest.raises(ValueError,match="stale"):
        services.apply_profile("p")

