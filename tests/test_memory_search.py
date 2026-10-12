from dataclasses import replace
import pytest
from inferlm.core.types import GIB,GPU,Hardware,Settings
from inferlm.hardware.memory import plan
from inferlm.models.gguf import read_model
from inferlm.optimization.search import candidates,choose

def hardware(total=16,available=12,gpus=None):
    return Hardware("Linux","x86_64","Example CPU",4,8,total*GIB,available*GIB,0,0,20*GIB,gpus or [])

def test_dense_memory(model_file):
    result = plan(read_model(model_file),hardware(),Settings())
    assert result.label=="Estimated" and result.classification=="Likely to fit"
    assert result.kv_bytes==2048*2*2*16*2
    assert result.reserve==int(16*GIB*.2)

def test_eight_gb_reserve(model_file):
    assert plan(read_model(model_file),hardware(8,6),Settings()).reserve==2*GIB

def test_memory_pressure(model_file):
    assert plan(read_model(model_file),hardware(8,2),Settings()).classification=="Unlikely to fit"

def test_unknown_kv(model_file):
    model = replace(read_model(model_file),architecture="mamba")
    assert plan(model,hardware(),Settings()).classification=="Not enough information"

def test_gpu_unknown(model_file):
    assert plan(read_model(model_file),hardware(),Settings(gpu_layers=1)).classification=="Not enough information"

def test_gpu_separate_memory(model_file):
    result = plan(read_model(model_file),hardware(gpus=[GPU("GPU",4*GIB,3*GIB)]),Settings(gpu_layers=1))
    assert result.vram_required>0 and result.ram_required>result.vram_required

@pytest.mark.parametrize("settings",[Settings(context=1),Settings(threads=0),Settings(ubatch=1024,batch=128)])
def test_invalid_settings(settings):
    with pytest.raises(ValueError):
        settings.validate()

def test_candidates_bounded_context():
    base = Settings(context=4096)
    result = candidates(base,8,32,True,6)
    assert len(result)<=6 and len(set(result))==len(result)
    assert all(s.context==4096 for s in result) and result[0]==base

def report(speed,latency=1,noise=0):
    return {"native":{"generation_score":speed,"rows":[{"n_gen":64,"n_prompt":0,"avg_ts":speed,"stddev_ts":noise}]},
            "median_ttft_seconds":latency}

def test_no_invented_improvement():
    base = report(10)
    assert choose(base,[report(10.2)])[0] is base

def test_latency_limit():
    base = report(10)
    assert choose(base,[report(20,2)])[0] is base

def test_noise_limit():
    base = report(10,noise=5)
    assert choose(base,[report(11)])[0] is base

def test_stable_improvement():
    best = report(12)
    assert choose(report(10),[best])[0] is best

