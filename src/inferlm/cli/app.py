import json
from dataclasses import asdict
from pathlib import Path
import typer
from rich.console import Console
from inferlm.core.services import Services
from inferlm.hardware.detect import detect
from inferlm.optimization.benchmark import run
from inferlm.optimization.search import optimize

app = typer.Typer(help="InferLM · local chat and measured tuning",no_args_is_help=True)
models,profiles = typer.Typer(help="Local GGUF models."),typer.Typer(help="Measured tuning profiles.")
app.add_typer(models,name="models")
app.add_typer(profiles,name="profiles")
console = Console()

def output(value,json_output=False):
    if json_output:
        print(json.dumps(value,indent=2,ensure_ascii=False))
    else:
        console.print(value)

@app.command()
def doctor(json_output:bool=typer.Option(False,"--json")):
    s = Services()
    output({"hardware":asdict(detect(s.data_dir)),"runtime_folder":s.config()["runtime_folder"],
            "data_dir":str(s.data_dir),"label":"Hardware observation, not an inference benchmark"},json_output)

@app.command()
def configure(runtime:Path):
    from inferlm.runtime.capabilities import binaries,inspect
    folder = str(runtime.resolve())
    for path in binaries(folder):
        inspect(path)
    Services().save_config({"runtime_folder":folder})
    console.print("[green]Runtime configured.[/green]")

@models.command("add")
def model_add(path:Path,json_output:bool=typer.Option(False,"--json")):
    output(asdict(Services().import_model(path)),json_output)

@models.command("list")
def model_list(json_output:bool=typer.Option(False,"--json")):
    output([{"id":m.id,"name":m.name,"path":m.path,"size_bytes":m.size,"architecture":m.architecture}
            for m in Services().models()],json_output)

@app.command()
def chat(model:str=typer.Option(...,"--model"),unverified:bool=False):
    s = Services()
    try:
        s.load(model,allow_uncertain=unverified)
        conv = s.new_conversation(model)
        console.print("Local chat ready. Type /exit to leave.")
        while True:
            text = console.input("[bold]You > [/bold]")
            if text.strip()=="/exit":
                break
            s.chat(conv["id"],text,lambda piece:console.print(piece,end="",markup=False))
            console.print()
    finally:
        s.close()

@app.command()
def benchmark(model:str=typer.Option(...,"--model"),json_output:bool=typer.Option(False,"--json")):
    s = Services()
    try:
        output(run(s,s.model(model),s.settings(model),emit=(lambda _:None) if json_output else console.print),json_output)
    finally:
        s.close()

@app.command("optimize")
def optimize_model(model:str=typer.Option(...,"--model"),mode:str="quick",budget:int=900,
                   json_output:bool=typer.Option(False,"--json")):
    s = Services()
    try:
        output(optimize(s,model,mode,budget,(lambda _:None) if json_output else console.print),json_output)
    finally:
        s.close()

@profiles.command("list")
def profile_list(json_output:bool=typer.Option(False,"--json")):
    output(Services().db.list("profiles"),json_output)

@profiles.command("apply")
def profile_apply(profile_id:str):
    output(asdict(Services().apply_profile(profile_id)))

@app.command("export-benchmark")
def export_benchmark(run_id:str,format:str="json",destination:Path|None=None):
    record = Services().db.get("benchmarks",run_id)
    if not record:
        raise ValueError("Benchmark not found.")
    if format!="json":
        raise ValueError("Version 0.1 exports benchmark JSON.")
    text = json.dumps(record,indent=2,ensure_ascii=False)
    if destination:
        destination.write_text(text,encoding="utf-8")
    else:
        print(text)

@app.command()
def gui():
    from inferlm.app import main as gui_main
    gui_main()

def main():
    try:
        app()
    except (ValueError,RuntimeError,OSError) as exc:
        console.print("Error: "+str(exc),style="red",markup=False)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        raise SystemExit(130) from None

