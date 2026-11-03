"""Phase-2 builder tests: files, patches, git checkpoints, approval gate."""

import shutil

import pytest

from app.builder.approvals import ApprovalGate
from app.builder.checkpoints import create_checkpoint, init_repo, restore_checkpoint
from app.builder.files import GenesisWorkspace
from app.builder.patches import apply_patch

git = shutil.which("git")


def test_create_and_read_file(tmp_path):
    ws = GenesisWorkspace(tmp_path)
    ws.create_file("hello.txt", "hi genesis")
    assert ws.read_file("hello.txt") == "hi genesis"
    assert any(e.operation == "create_file" for e in ws.audit)


def test_create_refuses_overwrite_and_escape(tmp_path):
    ws = GenesisWorkspace(tmp_path)
    ws.create_file("a.txt", "1")
    with pytest.raises(FileExistsError):
        ws.create_file("a.txt", "2")
    with pytest.raises(ValueError):
        ws.create_file("../escape.txt", "nope")
    with pytest.raises(ValueError):
        ws.create_file("/abs.txt", "nope")


def test_apply_patch_single_match(tmp_path):
    target = tmp_path / "code.py"
    target.write_text("x = 1\ny = 2\n", encoding="utf-8")
    res = apply_patch(target, "x = 1", "x = 42")
    assert res["ok"]
    assert target.read_text(encoding="utf-8") == "x = 42\ny = 2\n"


def test_apply_patch_rejects_zero_and_multi_match(tmp_path):
    target = tmp_path / "code.py"
    target.write_text("a = 1\na = 1\n", encoding="utf-8")
    with pytest.raises(LookupError):
        apply_patch(target, "missing", "x")
    with pytest.raises(LookupError):
        apply_patch(target, "a = 1", "b = 2")
    with pytest.raises(ValueError):
        apply_patch(target, "", "x")


@pytest.mark.skipif(git is None, reason="git not installed")
def test_checkpoint_roundtrip(tmp_path):
    repo = tmp_path / "repo"
    init_repo(repo)
    ws = GenesisWorkspace(repo)
    ws.create_file("app.txt", "v1")
    sha = create_checkpoint(repo, "v1 checkpoint")
    assert len(sha) == 40
    ws.create_file("app.txt", "v2", overwrite=True)
    assert ws.read_file("app.txt") == "v2"
    gate = ApprovalGate()
    item = gate.request("restore_checkpoint", sha)
    assert gate.pending()[0].id == item.id
    gate.approve(item.id)
    restore_checkpoint(repo, sha)
    assert (repo / "app.txt").read_text(encoding="utf-8") == "v1"


def test_approval_gate_lifecycle():
    gate = ApprovalGate()
    item = gate.request("apply_patch", "code.py")
    assert item.status == "PENDING"
    gate.approve(item.id)
    assert item.status == "APPROVED"
    with pytest.raises(ValueError):
        gate.approve(item.id)
    other = gate.request("deploy", "prod")
    gate.reject(other.id)
    assert other.status == "REJECTED"
    assert gate.pending() == []
    with pytest.raises(KeyError):
        gate.approve("APR-9999")
