"""Native unsigned onedir desktop packaging, built on the intended OS."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--assemble-only",action="store_true")
    parser.add_argument("--build-runtime",action="store_true",help="Explicitly download pinned CPU runtime.")
    parser.add_argument("--runtime-folder",type=Path,help="Bundle an existing verified runtime directory.")
    args=parser.parse_args()
    from inferlm import __version__
    root=Path(__file__).resolve().parents[1]
    os.chdir(root)
    out=root/"dist"
    folder=out/"frozen"/"InferLM"
    if not args.assemble_only:
        subprocess.run([sys.executable,"-m","PyInstaller","--noconfirm","--onedir","--windowed",
                        "--name","InferLM","--paths",str(root/"src"),
                        "--add-data",str(root/"src/inferlm/runtime/manifest.json")+":inferlm/runtime",
                        "--collect-submodules","inferlm",
                        "--exclude-module","PySide6.QtWebEngineCore",
                        "--exclude-module","PySide6.QtWebEngineWidgets",
                        "--exclude-module","PySide6.QtPdf",
                        "--distpath",str(out/"frozen"),"--workpath",str(out/"frozen-build"),
                        "--specpath",str(root/"packaging"),str(root/"scripts/launch_gui.py")],check=True)
    if not folder.is_dir():
        raise RuntimeError("Standalone directory was not produced.")
    if args.build_runtime:
        from inferlm.runtime.install import install
        install(folder/"runtime")
    elif args.runtime_folder:
        if not (folder/"runtime").exists():
            shutil.copytree(args.runtime_folder.resolve(),folder/"runtime")
    for name in ("README.md","LICENSE","THIRD_PARTY_NOTICES.md","TESTING.md"):
        if (root/name).is_file():
            shutil.copy2(root/name,folder/name)
    if (root/"docs").is_dir():
        shutil.copytree(root/"docs",folder/"docs",dirs_exist_ok=True)
    licenses=folder/"THIRD_PARTY_LICENSES"
    licenses.mkdir(exist_ok=True)
    for distribution in importlib.metadata.distributions():
        name=distribution.metadata.get("Name","dependency")
        for file in distribution.files or []:
            if any(part.lower().startswith(("license","copying","notice")) for part in file.parts):
                source=Path(distribution.locate_file(file))
                if source.is_file():
                    target=licenses/name/str(file).replace("/","_")
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(source,target)
    metadata={"version":__version__,"platform":sys.platform,"python":sys.version,"packager":"PyInstaller",
              "signed":False,"runtime_bundled":(folder/"runtime").is_dir()}
    (folder/"BUILD_INFO.json").write_text(json.dumps(metadata,indent=2))
    suffix="windows-x64" if os.name=="nt" else "linux-x64"
    archive=shutil.make_archive(str(out/("InferLM-"+__version__+"-"+suffix)),"zip",folder)
    checksum=hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    Path(archive+".sha256").write_text(checksum+"  "+Path(archive).name+"\n")
    print(archive)

if __name__=="__main__":
    main()

