"""Tiện ích test: chạy headless, đọc JSONL, dựng fixture, so sánh có dung sai."""

import json
import math
import os
import shlex
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    return path


def frames(*fr):
    return {"frames": list(fr)}


def headless_cmd():
    """Lệnh headless khai trong game.contract.json — test chạy qua đây nên dùng được với MỌI ngôn ngữ."""
    with open(os.path.join(ROOT, "game.contract.json"), encoding="utf-8") as f:
        return shlex.split(json.load(f)["headless_cmd"])


def run_headless(*args, cwd=ROOT):
    """Chạy `<headless_cmd> <args>`; trả (mã thoát, stderr)."""
    p = subprocess.run([*headless_cmd(), *args], cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stderr


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def snapshots(rows):
    return [r for r in rows if r["type"] == "snapshot"]


def events(rows, name=None):
    return [r for r in rows if r["type"] == "event" and (name is None or r["name"] == name)]


def close(a, b, tol=0.1):
    return abs(a - b) <= tol


def dist(p, q):
    return math.dist(p, q)


class Workdir:
    """Thư mục tạm tự dọn: with Workdir() as w: w.path('x.json')."""

    def __enter__(self):
        self._d = tempfile.TemporaryDirectory()
        return self

    def __exit__(self, *a):
        self._d.cleanup()

    def path(self, name):
        return os.path.join(self._d.name, name)


# --- v1.2 (TICKET-03): kho / giỏ là mảng cá thể {id, kind, fresh} ----------------------------
def items(*kinds, fresh=100, start=1, prefix="I"):
    """Mảng cá thể theo thứ tự kinds, id I{start}, I{start+1}…"""
    return [{"id": f"{prefix}{start + i}", "kind": k, "fresh": fresh} for i, k in enumerate(kinds)]


def stock_of(counted, fresh=100, start=1, prefix="I"):
    """Kho đếm {kind: n} -> mảng cá thể (kind theo thứ tự chữ cái, id nối tiếp từ start)."""
    kinds = [k for k in sorted(counted) for _ in range(counted[k])]
    return items(*kinds, fresh=fresh, start=start, prefix=prefix)


def counts(item_list):
    """Mảng cá thể (hoặc mảng kind) -> {kind: n} sắp theo kind, để so lượng."""
    out = {}
    for it in item_list:
        k = it["kind"] if isinstance(it, dict) else it
        out[k] = out.get(k, 0) + 1
    return {k: out[k] for k in sorted(out)}


def kinds(item_list):
    """Mảng cá thể -> mảng kind (giữ thứ tự)."""
    return [it["kind"] for it in item_list]
