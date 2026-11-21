"""File kho (Contract G).

v1.0/v1.1 — kho đếm: {"items": {kind: số nguyên >= 0}}.
v1.2 (TICKET-03) — kho cá thể: {"items": [{"id": "I1", "kind": "ca_linh", "fresh": 100}, ...]}.
  id chuỗi duy nhất khác rỗng, kind thuộc danh mục, fresh hữu hạn trong [0, 100]. Kho rỗng {"items": []}.

Bên đọc chọn schema theo contract_version: v1.2 trả mã 2 (BadInput) cho file kho đếm hoặc sai schema,
kind lạ, id trùng, fresh ngoài miền. Bên ghi xuất theo id, float đủ chính xác để đọc lại giữ đúng giá trị/ngưỡng,
qua file tạm cùng thư mục rồi thay thế nguyên tử, byte-ổn-định.
"""

import json
import math
import os
import tempfile

from .errors import BadInput
from .ids import sort_by_id

KINDS_P1 = ("ca_loc", "ca_linh", "bong_dien_dien", "bong_sung")
KINDS_P2 = ("ca_loc", "ca_linh", "ca_keo", "bong_dien_dien", "bong_sung", "keo_neo")
ITEM_KEYS = {"id", "kind", "fresh"}


def is_v12(version) -> bool:
    try:
        return tuple(int(x) for x in str(version).split(".")) >= (1, 2)
    except ValueError:
        return False


# --- v1.0/v1.1: kho đếm -----------------------------------------------------------------
def validate_items(items, kinds=KINDS_P2):
    if not isinstance(items, dict):
        raise BadInput("items phải là object")
    out = {}
    for k, v in items.items():
        if k not in kinds:
            raise BadInput(f"nguyên liệu lạ: {k}")
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise BadInput(f"số lượng không hợp lệ cho {k}: {v!r}")
        if v > 0:
            out[k] = v
    return out


def hold_to_items(hold: list) -> dict:
    """Khoang (mảng kind theo thứ tự nhặt) -> object đếm, sắp theo kind (v1.0/v1.1)."""
    counts = {}
    for k in hold:
        counts[k] = counts.get(k, 0) + 1
    return {k: counts[k] for k in sorted(counts)}


# --- v1.2: kho cá thể -------------------------------------------------------------------
def _fresh_ok(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 100


def validate_item_list(items, name="items", kinds=KINDS_P2) -> list:
    """Mảng cá thể {id, kind, fresh}; trả bản copy. Sai schema / kind lạ / id trùng / fresh ngoài miền -> BadInput."""
    if not isinstance(items, list):
        raise BadInput(f"{name} phải là mảng cá thể {{id, kind, fresh}} (v1.2)")
    seen, out = set(), []
    for i, it in enumerate(items):
        if not isinstance(it, dict) or set(it) != ITEM_KEYS:
            raise BadInput(f"{name}[{i}] phải có đúng các khóa id, kind, fresh")
        if not isinstance(it["id"], str) or not it["id"]:
            raise BadInput(f"{name}[{i}].id phải là chuỗi khác rỗng")
        if it["id"] in seen:
            raise BadInput(f"{name}: id trùng {it['id']}")
        seen.add(it["id"])
        if it["kind"] not in kinds:
            raise BadInput(f"{name}[{i}]: nguyên liệu lạ {it['kind']!r}")
        if not _fresh_ok(it["fresh"]):
            raise BadInput(f"{name}[{i}].fresh phải là số hữu hạn trong [0, 100]")
        out.append(dict(it))
    return out


def read_inventory(path: str, version="1.2"):
    """Trả mảng cá thể (v1.2) hoặc object đếm (v1.0/v1.1)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise BadInput(f"không đọc được file kho {path}: {e}")
    if not isinstance(data, dict) or set(data.keys()) != {"items"}:
        raise BadInput("file kho chỉ được có khóa gốc 'items'")
    if is_v12(version):
        return validate_item_list(data["items"], "items")
    return validate_items(data["items"])


def _dump_atomic(path, obj):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".inv-", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_inventory(path: str, items):
    """v1.2: `items` là mảng cá thể {id, kind, fresh} -> ghi theo id. v1.0/v1.1: object đếm -> bỏ lượng 0."""
    if isinstance(items, list):
        _dump_atomic(path, {"items": [{"id": it["id"], "kind": it["kind"], "fresh": it["fresh"]}
                                      for it in sort_by_id(items)]})
    else:
        _dump_atomic(path, {"items": {k: items[k] for k in sorted(items) if items[k] > 0}})
