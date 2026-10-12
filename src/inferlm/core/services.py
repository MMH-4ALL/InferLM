import copy
import json
import os
import sys
import threading
from dataclasses import asdict
from pathlib import Path
import psutil
from filelock import FileLock,Timeout
from platformdirs import user_data_path
from inferlm.core.types import Model,Settings,identifier,now
from inferlm.hardware.detect import detect,hardware_key
from inferlm.hardware.memory import plan
from inferlm.models.gguf import read_model,assert_unchanged
from inferlm.runtime.manager import Runtime,Cancelled
from inferlm.runtime.client import Client
from inferlm.storage.database import Database

class Services:
    def __init__(self,data_dir:Path|None=None):
        self.data_dir = data_dir or Path(os.environ.get("INFERLM_DATA_DIR") or user_data_path("InferLM",appauthor=False))
        self.data_dir.mkdir(parents=True,exist_ok=True)
        self.db = Database(self.data_dir/"inferlm.sqlite")
        self.lease = FileLock(str(self.data_dir/"runtime.lock"),thread_local=False)
        self.runtime,self.cancel = Runtime(self.lease),threading.Event()
        self.client = Client(self.runtime)
        try:
            with self.lease.acquire(timeout=0):
                for conv in self.db.list("conversations"):
                    changed = False
                    for message in conv.get("messages",[]):
                        if message.get("state")=="generating":
                            message["state"],changed = "interrupted",True
                    if changed:
                        self.db.put("conversations",conv["id"],conv)
        except Timeout:
            pass

    def config(self)->dict:
        bundled = Path(sys.executable).resolve().parent/"runtime"
        return {"runtime_folder":str(bundled) if bundled.is_dir() else "","theme":"dark","reserve_gib":2,
                "system_prompt":"You are a helpful assistant.","temperature":.7,"max_tokens":256,
                **(self.db.get("config","main") or {})}

    def save_config(self,settings:dict):
        self.db.put("config","main",{**self.config(),**settings})

    def models(self)->list[Model]:
        return [Model(**m) for m in self.db.list("models")]

    def model(self,id:str)->Model:
        record = self.db.get("models",id)
        if not record:
            raise ValueError("Model not found.")
        return Model(**record)

    def import_model(self,path:Path)->Model:
        model = read_model(path)
        for existing in self.models():
            if existing.fingerprint==model.fingerprint:
                model.id = existing.id
        self.db.put("models",model.id,asdict(model))
        return model

    def settings(self,model_id:str="")->Settings:
        record = self.db.get("active_settings",model_id)
        return Settings(**record) if record else Settings(threads=min(8,psutil.cpu_count(logical=False) or 1))

    def load(self,model_id:str,settings:Settings|None=None,allow_uncertain=False):
        model = self.model(model_id)
        assert_unchanged(model)
        settings = settings or self.settings(model_id)
        memory = plan(model,detect(self.data_dir),settings,self.config()["reserve_gib"])
        if memory.classification=="Unlikely to fit":
            raise ValueError("Estimated memory is too high. Reduce context/offload or choose a smaller model.")
        if memory.classification=="Not enough information" and not allow_uncertain:
            raise ValueError("Memory estimate incomplete. Explicitly allow an unverified load after review.")
        self.runtime.load(self.config()["runtime_folder"],model,settings,self.cancel,memory.reserve)

    def new_conversation(self,model_id:str)->dict:
        conv:dict = {"id":identifier(),"title":"New conversation","model_id":model_id,"created":now(),
                     "messages":[],"settings":asdict(self.settings(model_id)),"draft":""}
        self.db.put("conversations",conv["id"],conv)
        return conv

    def chat(self,conversation_id:str,text:str,emit)->dict:
        conv = self.db.get("conversations",conversation_id)
        if not conv or not self.runtime.model or not self.runtime.settings or self.runtime.model.id!=conv["model_id"]:
            raise ValueError("Load this conversation's model before sending.")
        config = self.config()
        messages = [{"role":"system","content":config["system_prompt"]}]
        messages += [{"role":m["role"],"content":m["content"]} for m in conv["messages"]
                     if m["state"]!="error" and m["content"]]
        messages.append({"role":"user","content":text})
        conv["draft"] = text
        self.db.put("conversations",conversation_id,conv)
        count = self.client.token_count(messages)
        if count is None:
            raise ValueError("This runtime cannot count chat-template tokens. Choose a supported runtime.")
        if count+config["max_tokens"]>self.runtime.settings.context:
            raise ValueError(f"Context is full ({count} input tokens). Trim older turns, start a new chat, "
                             "or increase context; history and draft were kept.")
        conv["draft"] = ""
        conv["messages"].append({"role":"user","content":text,"state":"complete","timestamp":now()})
        assistant:dict = {"role":"assistant","content":"","state":"generating","timestamp":now()}
        conv["messages"].append(assistant)
        if conv["title"]=="New conversation":
            conv["title"] = text[:48]
        conv["settings"] = asdict(self.runtime.settings)
        self.db.put("conversations",conversation_id,conv)
        def collect(piece):
            assistant["content"] += piece
            emit(piece)
        try:
            from inferlm.core.jobs import MemoryGuard
            with MemoryGuard(self.runtime.reserve,self.cancel,self.client.cancel):
                result = self.client.generate(messages,self.cancel,collect,config["max_tokens"],config["temperature"])
            assistant["state"],assistant["measurement"] = "complete",result
            return result
        except Cancelled:
            assistant["state"] = "interrupted"
            raise
        except Exception:
            assistant["state"] = "error"
            raise
        finally:
            self.db.put("conversations",conversation_id,conv)

    def trim_conversation(self,conversation_id:str)->dict:
        conv = self.db.get("conversations",conversation_id)
        if not conv or not self.runtime.model or not self.runtime.settings or conv["model_id"]!=self.runtime.model.id:
            raise ValueError("Load this conversation's model before trimming.")
        branch,config,removed = copy.deepcopy(conv),self.config(),0
        while True:
            if self.cancel.is_set():
                raise Cancelled("Trimming cancelled; original conversation kept.")
            messages = [{"role":"system","content":config["system_prompt"]}]
            messages += [{"role":m["role"],"content":m["content"]} for m in branch["messages"]
                         if m["state"]!="error" and m["content"]]
            if branch.get("draft"):
                messages.append({"role":"user","content":branch["draft"]})
            count = self.client.token_count(messages)
            if count is None:
                raise ValueError("Token counting unavailable; history kept.")
            if count+config["max_tokens"]<=self.runtime.settings.context:
                break
            if len(branch["messages"]) <= (0 if branch.get("draft") else 2):
                raise ValueError("Latest question/answer cannot fit. Increase context or shorten draft; history kept.")
            branch["messages"] = branch["messages"][2:]
            removed += 2
        if not removed:
            raise ValueError("Conversation already fits; no history changed.")
        branch.update(id=identifier(),title=conv["title"][:100]+" · shorter branch",created=now(),branched_from=conversation_id)
        self.db.put("conversations",branch["id"],branch)
        return branch

    def retry(self,conversation_id:str)->str:
        conv = self.db.get("conversations",conversation_id)
        if not conv or len(conv["messages"])<2:
            raise ValueError("No answer to retry.")
        user,assistant = conv["messages"][-2:]
        if user["role"]!="user" or assistant["role"]!="assistant":
            raise ValueError("Conversation does not end in a complete turn.")
        conv["messages"] = conv["messages"][:-2]
        self.db.put("conversations",conversation_id,conv)
        return user["content"]

    def export_conversation(self,id:str,path:Path):
        conv = self.db.get("conversations",id)
        if not conv:
            raise ValueError("Conversation missing.")
        text = json.dumps(conv,indent=2,ensure_ascii=False) if path.suffix.lower()==".json" else (
            "# "+conv["title"]+"\n\n"+"\n\n".join("## "+m["role"].title()+"\n\n"+m["content"] for m in conv["messages"]))
        path.write_text(text,encoding="utf-8")

    def apply_profile(self,id:str)->Settings:
        profile = self.db.get("profiles",id)
        if not profile:
            raise ValueError("Profile missing.")
        model = self.model(profile["model_id"])
        assert_unchanged(model)
        from inferlm.runtime.capabilities import inspect,binaries
        version = inspect(binaries(self.config()["runtime_folder"])[0]).version
        if profile["fingerprint"]!=model.fingerprint or profile["hardware"]!=hardware_key(detect(self.data_dir)) \
                or profile["runtime_version"]!=version:
            raise ValueError("Profile is stale. Model, hardware, driver or runtime changed; tune again.")
        settings = Settings(**profile["settings"])
        self.db.put("active_settings",model.id,asdict(settings))
        return settings

    def stop_job(self):
        self.cancel.set()
        self.client.cancel()

    def close(self):
        self.stop_job()
        self.runtime.stop()

