import hashlib
import json
import os
import platform
import shutil
import tarfile
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

def extract_archive(archive:Path,destination:Path):
    destination.mkdir(parents=True,exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            if sum(x.file_size for x in z.infolist())>2*1024**3:
                raise ValueError("Archive exceeds unpacked size limit.")
            for item in z.infolist():
                if not (destination/item.filename).resolve().is_relative_to(destination.resolve()):
                    raise ValueError("Archive contains a path outside the destination.")
                if (item.external_attr>>16)&0o170000==0o120000:
                    raise ValueError("Unsupported archive symbolic link.")
            z.extractall(destination)
    else:
        with tarfile.open(archive) as t:
            if sum(x.size for x in t.getmembers())>2*1024**3:
                raise ValueError("Archive exceeds unpacked size limit.")
            for member in t.getmembers():
                if not (destination/member.name).resolve().is_relative_to(destination.resolve()):
                    raise ValueError("Archive contains a path outside the destination.")
            t.extractall(destination,filter="data")

def install(destination:Path,cancel:threading.Event|None=None)->Path:
    manifest = json.loads(Path(__file__).with_name("manifest.json").read_text())
    if platform.machine().lower() not in ("x86_64","amd64"):
        raise ValueError("Pinned runtime installers support x86-64 only.")
    asset = next((a for a in manifest["assets"] if a["platform"]==platform.system()),None)
    if not asset:
        raise ValueError("No pinned runtime for this operating system.")
    if destination.exists():
        raise ValueError("Destination exists. Choose a new folder; runtimes are never overwritten.")
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as work:
        root = Path(work)
        archive = root/asset["name"]
        digest = hashlib.sha256()
        started,downloaded = time.monotonic(),0
        request = urllib.request.Request(asset["url"],headers={"User-Agent":"InferLM/0.1"})
        with urllib.request.urlopen(request,timeout=30) as response,archive.open("wb") as output:
            while block:=response.read(1024**2):
                if cancel and cancel.is_set():
                    raise RuntimeError("Runtime download cancelled.")
                if time.monotonic()-started>600:
                    raise RuntimeError("Runtime download exceeded its time budget.")
                downloaded += len(block)
                if downloaded>asset["size"]:
                    raise ValueError("Download exceeds pinned size.")
                digest.update(block)
                output.write(block)
        if downloaded!=asset["size"] or digest.hexdigest()!=asset["sha256"]:
            raise ValueError("Runtime download failed SHA-256 verification.")
        unpacked = root/"unpacked"
        extract_archive(archive,unpacked)
        name = "llama-server.exe" if os.name=="nt" else "llama-server"
        servers = list(unpacked.rglob(name))
        if len(servers)!=1:
            raise ValueError("Unexpected runtime layout.")
        folder = servers[0].parent
        (folder/"inferlm-runtime.json").write_text(json.dumps(asset,indent=2))
        shutil.copytree(folder,destination)
    return destination

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Download verified llama.cpp b11564 CPU runtime.")
    parser.add_argument("destination",type=Path)
    print(install(parser.parse_args().destination).resolve())

if __name__=="__main__":
    main()

