"""Developer verification of the packaged core; never runs during normal launch."""
import json
from dataclasses import asdict
from pathlib import Path
from inferlm.core.services import Services
from inferlm.core.types import Settings

def verify(model_path:Path,report_path:Path):
    s = Services()
    s.save_config({"max_tokens":32,"temperature":0})
    try:
        model = s.import_model(model_path)
        settings = Settings(threads=2)
        s.load(model.id,settings)
        conversation = s.new_conversation(model.id)
        result = s.chat(conversation["id"],"Explain what RAM does in two simple sentences.",lambda _:None)
        if not result["text"] or not result["usage"].get("completion_tokens"):
            raise RuntimeError("Packaged runtime returned no measured generated tokens.")
        report = {"status":"passed","model":model.name,"fingerprint":model.fingerprint,
                  "settings":asdict(settings),"runtime":s.runtime.version,
                  "load_seconds":s.runtime.load_seconds,
                  "chat":{k:v for k,v in result.items() if k!="text"}}
        report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        return report
    finally:
        s.close()

