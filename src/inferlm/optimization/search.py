import math
import time
from dataclasses import asdict,replace
from inferlm.core.types import Settings,identifier,now
from inferlm.hardware.detect import detect,hardware_key
from inferlm.runtime.manager import Cancelled
from inferlm.runtime.capabilities import inspect,binaries
from inferlm.optimization.benchmark import run

def candidates(base:Settings,cores:int,layers:int,gpu:bool,limit:int)->list[Settings]:
    options = [base]
    if gpu:
        options += [replace(base,gpu_layers=max(1,layers//3)),replace(base,threads=max(1,cores//2)),
                    replace(base,gpu_layers=max(1,layers*2//3)),replace(base,batch=128,ubatch=64),
                    replace(base,gpu_layers=layers)]
    for threads in sorted({1,max(1,cores//2),min(cores,8),min(cores,16)}):
        options.append(replace(base,threads=threads))
    for batch,ubatch in ((128,64),(512,128),(512,256),(256,64)):
        options.append(replace(base,batch=batch,ubatch=ubatch))
    return list(dict.fromkeys(options))[:limit]

def noise_margin(report:dict)->float:
    relative = []
    for row in report["native"]["rows"]:
        if row.get("n_gen",0) and not row.get("n_prompt",0):
            relative.append(2*row.get("stddev_ts",0)/row["avg_ts"]/math.sqrt(3))
    return max([.05,*relative])

def choose(baseline:dict,reports:list[dict])->tuple[dict,str]:
    base = baseline["native"]["generation_score"]
    allowed = [r for r in reports if r["median_ttft_seconds"]<=baseline["median_ttft_seconds"]*1.2
               and r["native"]["generation_score"]>base*(1+max(noise_margin(baseline),noise_margin(r)))]
    if not allowed:
        return baseline,"No convincing improvement measured; baseline retained."
    best = max(allowed,key=lambda r:r["native"]["generation_score"])
    gain = (best["native"]["generation_score"]/base-1)*100
    return best,f"Measured {gain:.1f}% higher native generation throughput on these workloads."

def optimize(services,model_id:str,mode="quick",budget=900,emit=lambda _:None)->dict:
    if mode not in ("quick","thorough") or budget<30:
        raise ValueError("Choose quick/thorough with at least a 30-second budget.")
    model,hw = services.model(model_id),detect(services.data_dir)
    base = services.settings(model_id)
    caps = inspect(binaries(services.config()["runtime_folder"])[0])
    options = candidates(base,hw.physical_cores,int(model.metadata.get(model.architecture+".block_count",0)),
                         bool(hw.gpus) and bool(caps.devices),6 if mode=="quick" else 12)
    started,reports,failures = time.monotonic(),[],[]
    with services.lease.acquire(timeout=0):
        baseline = run(services,model,base,emit,min(300,budget))
        reports.append(baseline)
        for index,settings in enumerate(options[1:],2):
            remaining = budget-(time.monotonic()-started)
            if remaining<30:
                emit("Time budget reached. Completed measurements kept.")
                break
            if services.cancel.is_set():
                raise Cancelled("Tuning cancelled. Active settings preserved.")
            emit(f"Testing {index}/{len(options)}: {settings.threads} threads, {settings.gpu_layers} GPU layers, batch {settings.batch}.")
            try:
                reports.append(run(services,model,settings,emit,min(300,remaining)))
            except Cancelled:
                raise
            except Exception as exc:
                failures.append({"settings":asdict(settings),"error":str(exc)})
                emit("Configuration rejected: "+str(exc))
        best,conclusion = choose(baseline,reports[1:])
        remaining = budget-(time.monotonic()-started)
        if best is not baseline and remaining>=30:
            emit("Rechecking baseline for thermal/background-load drift…")
            recheck = run(services,model,base,emit,min(300,remaining))
            baseline = max((baseline,recheck),key=lambda r:r["native"]["generation_score"])
            best,conclusion = choose(baseline,reports[1:])
        elif best is not baseline:
            best,conclusion = baseline,"Insufficient time for a baseline recheck; baseline retained."
        profile = {"id":identifier(),"created":now(),"model_id":model.id,"fingerprint":model.fingerprint,
                   "hardware":hardware_key(hw),"runtime_version":baseline["runtime_version"],
                   "settings":best["settings"],"baseline_settings":asdict(base),"baseline_run":baseline["id"],
                   "selected_run":best["id"],"conclusion":conclusion,"mode":mode,"failed_candidates":failures,
                   "completed_runs":[r["id"] for r in reports],
                   "comparison":"Same weights, f16 cache, context capacity and workload; quality not measured."}
        services.db.put("profiles",profile["id"],profile)
        emit(conclusion)
        return profile

