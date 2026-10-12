"""Repeated native measurements plus actual authenticated server validation."""
import json
import os
import statistics
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict
import psutil
from inferlm.core.types import Model,Settings,identifier,now
from inferlm.hardware.detect import detect,hardware_key
from inferlm.hardware.memory import plan
from inferlm.models.gguf import assert_unchanged
from inferlm.runtime.capabilities import binaries,inspect,runtime_env
from inferlm.runtime.manager import Cancelled

def guarded_process(args:list[str],cancel:threading.Event,reserve:int,timeout:float)->tuple[str,int]:
    peak,started = 0,time.monotonic()
    with tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(args,stdout=out,stderr=err,env=runtime_env(),
                                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0) if os.name=="nt" else 0)
        try:
            while proc.poll() is None:
                if cancel.is_set():
                    raise Cancelled("Benchmark cancelled.")
                if time.monotonic()-started>timeout:
                    raise RuntimeError("Benchmark exceeded its time budget.")
                if psutil.virtual_memory().available<reserve:
                    raise RuntimeError("Benchmark stopped at the RAM safety reserve.")
                if out.tell()+err.tell()>8*1024**2:
                    raise RuntimeError("Runtime output exceeded its safety limit.")
                try:
                    peak = max(peak,psutil.Process(proc.pid).memory_info().rss)
                except psutil.NoSuchProcess:
                    pass
                cancel.wait(.1)
            out.seek(0)
            data = out.read(8*1024**2).decode("utf-8",errors="replace")
            if proc.returncode:
                raise RuntimeError("llama-bench failed. Check backend and memory settings.")
            return data,peak
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

def native_report(folder:str,model:Model,settings:Settings,cancel:threading.Event,reserve:int,timeout=300)->dict:
    caps = inspect(binaries(folder)[1])
    caps.require("-m","-t","-ngl","-b","-ub","-p","-n","-r","-o","-d")
    caps.validate_offload(settings.gpu_layers)
    rows,peak,started = [],0,time.monotonic()
    depths = [0,min(1024,settings.context-256)]
    for depth in depths:
        args = [caps.path,"-m",model.path,"-t",str(settings.threads),"-ngl",str(settings.gpu_layers),
                "-b",str(settings.batch),"-ub",str(settings.ubatch),"-p","128","-n","64",
                "-r","3","-o","json","-d",str(depth)]
        if "--offline" in caps.flags:
            args.append("--offline")
        data,rss = guarded_process(args,cancel,reserve,max(1,timeout-(time.monotonic()-started)))
        try:
            result = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError("llama-bench returned invalid JSON; no valid measurements saved.") from exc
        if not isinstance(result,list) or not result:
            raise ValueError("llama-bench returned no samples.")
        for row in result:
            if not isinstance(row.get("avg_ts"),(float,int)) or row["avg_ts"]<=0:
                raise ValueError("Throughput measurement missing.")
            row["requested_depth"] = depth
            if row.get("samples_ts"):
                row["median_ts"] = statistics.median(row["samples_ts"])
            rows.append(row)
        peak = max(peak,rss)
    rates = [float(r.get("median_ts",r["avg_ts"])) for r in rows if r.get("n_gen",0)>0 and not r.get("n_prompt",0)]
    if not rates:
        raise ValueError("No native generation measurement returned.")
    return {"rows":rows,"generation_score":min(rates),"sampled_process_rss_peak":peak,
            "benchmark_version":caps.version,"depths":depths}

def run(services,model:Model,settings:Settings,emit=lambda _:None,timeout=300)->dict:
    assert_unchanged(model)
    hw = detect(services.data_dir)
    estimate = plan(model,hw,settings,services.config()["reserve_gib"])
    if estimate.classification!="Likely to fit":
        raise ValueError("Automatic benchmark rejected: "+estimate.classification+". Reduce memory use first.")
    previous_model,previous_settings,previous_reserve = services.runtime.model,services.runtime.settings,services.runtime.reserve
    services.runtime.stop()
    started = time.monotonic()
    try:
        with services.lease.acquire(timeout=0):
            emit("Measuring native prompt and generation throughput at two context depths…")
            native = native_report(services.config()["runtime_folder"],model,settings,services.cancel,estimate.reserve,timeout)
            if services.cancel.is_set():
                raise Cancelled("Benchmark cancelled.")
            emit("Validating the same settings through actual local chat…")
            services.runtime.load(services.config()["runtime_folder"],model,settings,services.cancel,estimate.reserve)
            load_time = services.runtime.load_seconds
            samples,server_peak = [],0
            pressure,done = threading.Event(),threading.Event()
            swap_start = psutil.swap_memory().used
            def monitor():
                nonlocal server_peak
                while not done.wait(.1):
                    proc = services.runtime.process
                    if proc:
                        try:
                            server_peak = max(server_peak,psutil.Process(proc.pid).memory_info().rss)
                        except psutil.NoSuchProcess:
                            pass
                    if psutil.virtual_memory().available<estimate.reserve or psutil.swap_memory().used-swap_start>256*1024**2 \
                            or time.monotonic()-started>timeout:
                        pressure.set()
                        services.cancel.set()
                        services.client.cancel()
            watcher = threading.Thread(target=monitor,daemon=True)
            watcher.start()
            try:
                for target in (min(128,settings.context-64),min(1024,settings.context-64)):
                    prefix = "Explain the main idea briefly. "
                    prefix_count = services.client.token_count([{"role":"user","content":prefix}])
                    if prefix_count is None or prefix_count+32>settings.context:
                        raise ValueError("Benchmark template cannot fit in this context.")
                    length = max(1,target//8)
                    for _ in range(10):
                        messages = [{"role":"user","content":prefix+"A student learns through practice. "*length}]
                        count = services.client.token_count(messages)
                        if count is None:
                            raise ValueError("Runtime token counting unavailable.")
                        if count<=target:
                            break
                        length = max(0,min(length-1,int(length*max(0,target-prefix_count)/max(1,count-prefix_count))))
                    if count is None or count+32>settings.context:
                        raise ValueError("Benchmark workload does not fit.")
                    services.client.generate(messages,services.cancel,lambda _:None,32,0)
                    for repetition in range(3):
                        if time.monotonic()-started>timeout:
                            raise RuntimeError("Benchmark exceeded its total time budget.")
                        result = services.client.generate(messages,services.cancel,lambda _:None,32,0)
                        if not result["text"] or result["ttft_seconds"] is None:
                            raise RuntimeError("Server validation returned no text.")
                        samples.append({"workload_tokens":count,"repetition":repetition,
                                        **{k:v for k,v in result.items() if k!="text"}})
            finally:
                done.set()
                watcher.join(timeout=2)
            if pressure.is_set():
                raise RuntimeError("Server validation reached its memory/time limit.")
            report = {"id":identifier(),"timestamp":now(),"label":"Measured","model_id":model.id,
                      "fingerprint":model.fingerprint,"hardware":hardware_key(hw),"hardware_observation":asdict(hw),
                      "settings":asdict(settings),"runtime_version":services.runtime.version,"load_seconds":load_time,
                      "native":native,"server_samples":samples,
                      "median_ttft_seconds":statistics.median(s["ttft_seconds"] for s in samples),
                      "sampled_server_rss_peak":server_peak,"gpu_memory":"Unavailable as a process-attributed measurement",
                      "conditions":{"cache_prompt":False,"warmup_excluded":True,"repetitions":3,
                                    "sampling_interval_seconds":.1,"token_source":"runtime",
                                    "ac_power":hw.ac_power,"quality":"Not evaluated"},
                      "duration_seconds":time.monotonic()-started}
            services.db.put("benchmarks",report["id"],report)
            return report
    finally:
        services.runtime.stop()
        if previous_model and previous_settings:
            try:
                services.runtime.load(services.config()["runtime_folder"],previous_model,previous_settings,
                                      threading.Event(),previous_reserve)
            except Exception as exc:
                emit("Previous model could not be restored: "+str(exc))

