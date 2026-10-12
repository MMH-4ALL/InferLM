import io
import tarfile
import zipfile
import pytest
from inferlm.runtime.install import extract_archive
from inferlm.runtime.capabilities import Capabilities

def test_zip_traversal(tmp_path):
    archive = tmp_path/"evil.zip"
    with zipfile.ZipFile(archive,"w") as z:
        z.writestr("../outside.txt","bad")
    with pytest.raises(ValueError,match="outside"):
        extract_archive(archive,tmp_path/"destination")
    assert not (tmp_path/"outside.txt").exists()

def test_tar_traversal(tmp_path):
    archive = tmp_path/"evil.tar"
    with tarfile.open(archive,"w") as t:
        member = tarfile.TarInfo("../outside.txt")
        member.size = 3
        t.addfile(member,io.BytesIO(b"bad"))
    with pytest.raises(ValueError,match="outside"):
        extract_archive(archive,tmp_path/"destination")
    assert not (tmp_path/"outside.txt").exists()

def test_good_zip(tmp_path):
    archive = tmp_path/"good.zip"
    with zipfile.ZipFile(archive,"w") as z:
        z.writestr("runtime/llama-server.exe","binary")
    extract_archive(archive,tmp_path/"destination")
    assert (tmp_path/"destination/runtime/llama-server.exe").read_text()=="binary"

def test_cpu_no_fake_gpu():
    caps = Capabilities("cpu","fake",set(),"")
    caps.validate_offload(0)
    with pytest.raises(ValueError,match="no available accelerator"):
        caps.validate_offload(12)

