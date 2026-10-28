import json
import threading
import time
import httpx
from inferlm.runtime.manager import Runtime,Cancelled

class Client:
    def __init__(self,runtime: Runtime):
        self.runtime = runtime
        self.response: httpx.Response | None = None
        self.last_timings: dict = {}

    def cancel(self):
        response = self.response
        if response:
            try:
                response.close()
            except Exception:
                pass

    def token_count(self,messages: list[dict]) -> int | None:
        with httpx.Client(trust_env=False,timeout=15) as client:
            template = client.post(self.runtime.url+"/apply-template",headers=self.runtime.headers(),
                                   json={"messages":messages,"add_generation_prompt":True})
            if template.status_code==200 and isinstance(template.json().get("prompt"),str):
                result = client.post(self.runtime.url+"/tokenize",headers=self.runtime.headers(),
                                     json={"content":template.json()["prompt"],"add_special":True})
                if result.status_code==200:
                    return len(result.json()["tokens"])
        return None

    def generate(self,messages:list[dict],cancel:threading.Event,emit,max_tokens:int=256,temperature:float=.7):
        if cancel.is_set():
            raise Cancelled("Generation stopped.")
        if self.runtime.process is None or self.runtime.process.poll() is not None:
            raise RuntimeError("Load a model before chatting.")
        started,first = time.monotonic(),None
        text = ""
        usage:dict = {}
        finished = False
        self.last_timings = {}
        body = {"messages":messages,"stream":True,"max_tokens":max_tokens,"temperature":temperature,
                "seed":42,"cache_prompt":False,"stream_options":{"include_usage":True}}
        try:
            with httpx.Client(trust_env=False,timeout=httpx.Timeout(180,connect=5)) as client:
                with client.stream("POST",self.runtime.url+"/v1/chat/completions",
                                   headers=self.runtime.headers(),json=body) as response:
                    self.response = response
                    if response.status_code>=400:
                        response.read()
                        raise RuntimeError(f"Local runtime rejected the request (HTTP {response.status_code}).")
                    for line in response.iter_lines():
                        if cancel.is_set():
                            raise Cancelled("Generation stopped.")
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data=="[DONE]":
                            finished = True
                            break
                        event = json.loads(data)
                        if event.get("error"):
                            raise RuntimeError("Local runtime reported a generation error.")
                        usage = event.get("usage") or usage
                        self.last_timings = event.get("timings") or self.last_timings
                        for choice in event.get("choices",[]):
                            delta = choice.get("delta",{})
                            piece = (delta.get("reasoning_content") or "")+(delta.get("content") or "")
                            if piece:
                                first = first or time.monotonic()
                                text += piece
                                emit(piece)
            if cancel.is_set():
                raise Cancelled("Generation stopped.")
            if not finished:
                raise RuntimeError("The local runtime closed the response before generation finished. Retry the message.")
        except Exception:
            if cancel.is_set():
                raise Cancelled("Generation stopped.") from None
            raise
        finally:
            self.response = None
        return {"text":text,"ttft_seconds":first-started if first else None,
                "request_seconds":time.monotonic()-started,"usage":usage,"timings":self.last_timings}

