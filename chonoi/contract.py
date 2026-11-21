"""Đọc game.contract.json và kiểm dải hợp lệ của tuning P1 (PRD mục 13.2, Test Contract)."""

import json
import os

from .errors import BadInput
from .day_plan import validate_day_plan
from .inventory import KINDS

# TICKET-02 mục 1.3 (v1.1): cố định id + công thức 6 món, 2 bếp B1–B2, 4 bàn T1–T4.
# (Phase 1 là 3 món, 1 bếp B1, 1 bàn T1 — đổi theo số chuẩn của TICKET-02.)
FIXED_RECIPES = {
    "ca_loc_nuong_trui": {"ca_loc": 1},
    "goi_bong_sung": {"bong_sung": 2},
    "lau_ca_linh_dien_dien": {"ca_linh": 3, "bong_dien_dien": 1},
    "canh_chua_ca_loc": {"ca_loc": 1, "bong_dien_dien": 1},
    "ca_keo_nuong": {"ca_keo": 2},
    "lau_mam": {"ca_linh": 2, "ca_keo": 1, "keo_neo": 1, "bong_dien_dien": 1},
}
FIXED_LAYOUT = {"stoves": ("B1", "B2"), "tables": ("T1", "T2", "T3", "T4")}
DAYS = 5

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "game.contract.json")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _between(name, v, lo, hi):
    if not _num(v) or not (lo <= v <= hi):
        raise BadInput(f"tuning.{name} phải trong [{lo}, {hi}], đang là {v!r}")


def load_contract(path=DEFAULT_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            c = json.load(f)
    except (OSError, ValueError) as e:
        raise BadInput(f"không đọc được {path}: {e}")
    validate_tuning(c.get("tuning"))
    return c


def _int_between(name, v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, int) or not (lo <= v <= hi):
        raise BadInput(f"tuning.{name} phải là số nguyên trong [{lo}, {hi}], đang là {v!r}")


def _pos_in(name, pos, bounds, keys):
    if (not isinstance(pos, list) or len(pos) != 2 or not all(_num(c) for c in pos)):
        raise BadInput(f"tuning.{name} phải là [số, số]")
    for c, k in zip(pos, keys):
        lo, hi = bounds[k]
        if not (lo <= c <= hi):
            raise BadInput(f"tuning.{name} nằm ngoài vùng {k} ∈ [{lo}, {hi}]")


def _bounds(name, b, keys):
    if not isinstance(b, dict) or set(b) != set(keys):
        raise BadInput(f"tuning.{name}.bounds phải có đúng khóa {list(keys)}")
    for k in keys:
        v = b[k]
        if not (isinstance(v, list) and len(v) == 2 and all(_num(c) for c in v) and v[0] == 0 and v[1] > 0):
            raise BadInput(f"tuning.{name}.bounds.{k} phải là [0, số dương]")


def _validate_gather(g):
    """Dải hợp lệ P1 theo PRD mục 13.2."""
    _between("gather.duration_s", g.get("duration_s"), 60, 600)
    _bounds("gather", g.get("bounds"), ("x", "d"))
    b = g["bounds"]
    _between("gather.dock_radius", g.get("dock_radius"), 0.5, 5)
    _between("gather.interact_radius", g.get("interact_radius"), 0.5, 5)
    _between("gather.catch_radius", g.get("catch_radius"), 0.5, 5)
    _between("gather.swim_speed", g.get("swim_speed"), 1, 10)
    _between("gather.catch_cooldown_s", g.get("catch_cooldown_s"), 0, 10)
    _between("gather.oxygen_max_s", g.get("oxygen_max_s"), 10, 120)
    _int_between("gather.ramp_max_ticks", g.get("ramp_max_ticks"), 0, 6)
    _int_between("gather.hold_capacity", g.get("hold_capacity"), 4, 30)
    _int_between("gather.hp_max", g.get("hp_max"), 1, 99)
    _int_between("gather.oxygen_refill_per_tick", g.get("oxygen_refill_per_tick"), 1, 10_000)
    _int_between("gather.choke_interval_ticks", g.get("choke_interval_ticks"), 1, 10_000)
    _int_between("gather.node_yield", g.get("node_yield"), 1, 12)
    _between("gather.regrow_s", g.get("regrow_s"), 0.1, 600)
    _between("gather.surface_depth", g.get("surface_depth"), 0, 5)
    _pos_in("gather.dock_pos", g.get("dock_pos"), b, ("x", "d"))
    _pos_in("gather.start_pos", g.get("start_pos"), b, ("x", "d"))
    if not _num(g.get("start_heading_deg")):
        raise BadInput("tuning.gather.start_heading_deg phải là số")
    fy = g.get("fish_yield")
    if not isinstance(fy, dict) or not {"ca_linh", "ca_loc"} <= set(fy):
        raise BadInput("tuning.gather.fish_yield phải có ca_linh và ca_loc")
    for k, v in fy.items():
        _int_between(f"gather.fish_yield.{k}", v, 1, g["hold_capacity"])
    nodes = g.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise BadInput("tuning.gather.nodes phải là mảng không rỗng")
    seen, kinds = set(), set()
    for n in nodes:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or n["id"] in seen:
            raise BadInput("tuning.gather.nodes: mỗi nút cần id duy nhất")
        seen.add(n["id"])
        if n.get("kind") not in ("bong_dien_dien", "bong_sung"):
            raise BadInput(f"tuning.gather.nodes.{n['id']}: kind phải là bong_dien_dien hoặc bong_sung")
        kinds.add(n["kind"])
        _pos_in(f"gather.nodes.{n['id']}.pos", n.get("pos"), b, ("x", "d"))
        if n["pos"][1] != 0:
            raise BadInput(f"tuning.gather.nodes.{n['id']}: nút hái nằm ở mặt nước (d = 0)")
    if kinds != {"bong_dien_dien", "bong_sung"}:
        raise BadInput("tuning.gather.nodes phải có ít nhất một nút mỗi loại (bong_dien_dien, bong_sung)")
    fish = g.get("fish_initial")
    if not isinstance(fish, list) or len(fish) != 6:
        raise BadInput("tuning.gather.fish_initial phải là danh sách đúng 6 đàn")
    seen = set()
    for f in fish:
        if not isinstance(f, dict) or not isinstance(f.get("id"), str) or f["id"] in seen:
            raise BadInput("tuning.gather.fish_initial: mỗi đàn cần id duy nhất")
        seen.add(f["id"])
        if f.get("kind") not in fy:
            raise BadInput(f"tuning.gather.fish_initial.{f['id']}: kind phải thuộc fish_yield")
        _pos_in(f"gather.fish_initial.{f['id']}.pos", f.get("pos"), b, ("x", "d"))
        if f["pos"][1] <= g["surface_depth"]:
            raise BadInput(f"tuning.gather.fish_initial.{f['id']}: đàn cá phải ở dưới nước")


def validate_tuning(t):
    if not isinstance(t, dict):
        raise BadInput("thiếu khối tuning")
    g, q, menu = t.get("gather"), t.get("quan"), t.get("menu")
    if not isinstance(g, dict) or not isinstance(q, dict) or not isinstance(menu, dict):
        raise BadInput("tuning phải có gather, quan, menu")
    _validate_gather(g)
    # Quán: dải hợp lệ P1 (PRD mục 13.2)
    _between("quan.duration_s", q.get("duration_s"), 60, 600)
    _bounds("quan", q.get("bounds"), ("x", "z"))
    _between("quan.patience_s", q.get("patience_s"), 20, 180)
    _between("quan.walk_speed", q.get("walk_speed"), 1, 10)
    _between("quan.interact_radius", q.get("interact_radius"), 0.5, 5)
    _int_between("quan.ramp_max_ticks", q.get("ramp_max_ticks", 6), 0, 6)
    _between("quan.eat_s", q.get("eat_s"), 0.1, 600)
    _between("quan.customer_interval_s", q.get("customer_interval_s"), 0.1, 600)
    _int_between("quan.first_customer_tick", q.get("first_customer_tick"), 1, int(q["duration_s"] * 60) - 1)
    if not (_num(q.get("tip_rate")) and q["tip_rate"] > 0 and _num(q.get("left_reputation_delta"))
            and q["left_reputation_delta"] < 0):
        raise BadInput("tip_rate phải > 0 và left_reputation_delta phải < 0")
    ratio = q.get("tip_min_patience_ratio")
    if not (_num(ratio) and 0 < ratio <= 1):
        raise BadInput("quan.tip_min_patience_ratio phải thuộc (0, 1]")
    if not (_num(q.get("tip_reputation")) and q["tip_reputation"] > 0):
        raise BadInput("quan.tip_reputation phải > 0")
    if q.get("burn_s") is not None:
        raise BadInput("burn_s phải là null ở Phase 1")
    _validate_quan_layout(q)
    if {k: (d.get("recipe") if isinstance(d, dict) else None) for k, d in menu.items()} != FIXED_RECIPES:
        raise BadInput(f"tuning.menu phải có đúng 6 món và công thức cố định (TICKET-02 mục 1.3): {FIXED_RECIPES}")
    for dish_id, d in menu.items():
        price, cook = d.get("price"), d.get("cook_s")
        if (isinstance(price, bool) or not isinstance(price, int) or price <= 0 or not _num(cook)
                or int(round(cook * 60)) < 1):
            raise BadInput(f"menu.{dish_id}: price nguyên dương, cook_s quy đổi ra số tick dương")
        recipe = d.get("recipe")
        if not isinstance(recipe, dict) or not recipe:
            raise BadInput(f"menu.{dish_id}: recipe phải là object không rỗng")
        for k, n in recipe.items():
            if k not in KINDS:
                raise BadInput(f"menu.{dish_id}: nguyên liệu lạ {k}")
            _int_between(f"menu.{dish_id}.recipe.{k}", n, 1, 10_000)
    validate_day_plan(t.get("day_plan"), menu, DAYS)
    score = t.get("score")
    if not isinstance(score, dict) or not _num(score.get("reputation_multiplier")) or score["reputation_multiplier"] < 0:
        raise BadInput("tuning.score.reputation_multiplier phải là số >= 0")


def _validate_quan_layout(q):
    """Lát 3 (TV2): kiểm bếp/bàn, vị trí đầu, uy tín, carry_limit — chỉ kiểm cấu trúc/mâu thuẫn, không tự đặt dải."""
    qb = q["bounds"]
    _pos_in("quan.start_pos", q.get("start_pos"), qb, ("x", "z"))
    _int_between("quan.carry_limit", q.get("carry_limit"), 1, 10_000)
    rmin, rmax, rinit = q.get("reputation_min"), q.get("reputation_max"), q.get("reputation_initial")
    if not (_num(rmin) and _num(rmax) and _num(rinit) and rmin < rmax and rmin <= rinit <= rmax):
        raise BadInput("quan: cần reputation_min < reputation_max và reputation_initial nằm giữa")
    for name in ("stoves", "tables"):
        arr = q.get(name)
        if not isinstance(arr, list) or not arr:
            raise BadInput(f"tuning.quan.{name} phải là mảng không rỗng")
        seen = set()
        for e in arr:
            if not isinstance(e, dict) or not isinstance(e.get("id"), str) or e["id"] in seen:
                raise BadInput(f"tuning.quan.{name}: mỗi phần tử cần id duy nhất")
            seen.add(e["id"])
            _pos_in(f"quan.{name}.{e['id']}.pos", e.get("pos"), qb, ("x", "z"))
        if sorted(seen) != list(FIXED_LAYOUT[name]):
            raise BadInput(f"tuning.quan.{name} phải đúng {list(FIXED_LAYOUT[name])} (TICKET-02 mục 1.3)")
