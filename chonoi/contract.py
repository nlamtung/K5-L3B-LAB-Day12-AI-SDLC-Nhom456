"""Đọc game.contract.json và kiểm dải hợp lệ của tuning (v1.0 & v1.1)."""

import json
import os

from .errors import BadInput
from .inventory import KINDS_P1, KINDS_P2, is_v12

FIXED_RECIPES_V10 = {
    "ca_loc_nuong_trui": {"ca_loc": 1},
    "goi_bong_sung": {"bong_sung": 2},
    "lau_ca_linh_dien_dien": {"ca_linh": 3, "bong_dien_dien": 1},
}
FIXED_RECIPES_V11 = {
    **FIXED_RECIPES_V10,
    "canh_chua_ca_loc": {"ca_loc": 1, "bong_dien_dien": 1},
    "ca_keo_nuong": {"ca_keo": 2},
    "lau_mam": {"ca_linh": 2, "ca_keo": 1, "keo_neo": 1, "bong_dien_dien": 1},
}
FIXED_LAYOUT_V10 = {"stoves": ("B1",), "tables": ("T1",)}
FIXED_LAYOUT_V11 = {"stoves": ("B1", "B2"), "tables": ("T1", "T2", "T3", "T4")}

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
    version = str(c.get("contract_version", "1.0"))
    validate_tuning(c.get("tuning"), version=version)
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


def _validate_gather(g, version="1.1"):
    is_v10 = version == "1.0"
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

    req_fish = {"ca_linh", "ca_loc"} if is_v10 else {"ca_linh", "ca_loc", "ca_keo"}
    fy = g.get("fish_yield")
    if not isinstance(fy, dict) or not req_fish <= set(fy):
        raise BadInput(f"tuning.gather.fish_yield phải có {sorted(req_fish)}")
    for k, v in fy.items():
        _int_between(f"gather.fish_yield.{k}", v, 1, g["hold_capacity"])

    req_nodes = {"bong_dien_dien", "bong_sung"} if is_v10 else {"bong_dien_dien", "bong_sung", "keo_neo"}
    nodes = g.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise BadInput("tuning.gather.nodes phải là mảng không rỗng")
    seen, kinds = set(), set()
    for n in nodes:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or n["id"] in seen:
            raise BadInput("tuning.gather.nodes: mỗi nút cần id duy nhất")
        seen.add(n["id"])
        if n.get("kind") not in req_nodes:
            raise BadInput(f"tuning.gather.nodes.{n['id']}: kind phải thuộc {sorted(req_nodes)}")
        kinds.add(n["kind"])
        _pos_in(f"gather.nodes.{n['id']}.pos", n.get("pos"), b, ("x", "d"))
        if n["pos"][1] != 0:
            raise BadInput(f"tuning.gather.nodes.{n['id']}: nút hái nằm ở mặt nước (d = 0)")
    if kinds != req_nodes:
        raise BadInput(f"tuning.gather.nodes phải có ít nhất một nút mỗi loại ({sorted(req_nodes)})")

    fish = g.get("fish_initial")
    if is_v10:
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
    else:
        _int_between("gather.fish_initial", fish, 1, 30)
        _between("gather.fish_speed", g.get("fish_speed"), 0.1, 10)
        _int_between("gather.fish_turn_ticks", g.get("fish_turn_ticks"), 1, 10_000)
        _int_between("gather.fish_max", g.get("fish_max"), fish, 100)
        _int_between("gather.fish_spawn_ticks", g.get("fish_spawn_ticks"), 1, 10_000)
        _between("gather.fish_spawn_clearance", g.get("fish_spawn_clearance"), 0, 20)
        for key in ("fish_depths", "fish_spawn_depths", "fish_weights"):
            mp = g.get(key)
            if not isinstance(mp, dict) or not req_fish <= set(mp):
                raise BadInput(f"tuning.gather.{key} phải có đủ {sorted(req_fish)}")
        monsters = g.get("monsters")
        if not isinstance(monsters, dict) or "ca_sau" not in monsters.get("species", {}):
            raise BadInput("tuning.gather.monsters phải có species.ca_sau")


FRESHNESS_KEYS = {"initial", "gather_decay_per_s", "quan_decay_per_s", "spoiled_below"}


def _validate_freshness(f):
    """v1.2 (TICKET-03): freshness {initial, gather_decay_per_s, quan_decay_per_s, spoiled_below}."""
    if not isinstance(f, dict) or set(f) != FRESHNESS_KEYS:
        raise BadInput(f"tuning.freshness phải có đúng các khóa {sorted(FRESHNESS_KEYS)} (contract v1.2)")
    _between("freshness.initial", f["initial"], 0, 100)
    _between("freshness.spoiled_below", f["spoiled_below"], 0, 100)
    for k in ("gather_decay_per_s", "quan_decay_per_s"):
        _between(f"freshness.{k}", f[k], 0, 100)


def validate_tuning(t, version="1.1"):
    if not isinstance(t, dict):
        raise BadInput("thiếu khối tuning")
    g, q, menu = t.get("gather"), t.get("quan"), t.get("menu")
    if not isinstance(g, dict) or not isinstance(q, dict) or not isinstance(menu, dict):
        raise BadInput("tuning phải có gather, quan, menu")
    is_v10 = version == "1.0"
    _validate_gather(g, version=version)

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
    burn = q.get("burn_s")
    if is_v10 and burn is not None:
        raise BadInput("burn_s phải là null ở Phase 1")
    if burn is not None and (not _num(burn) or int(round(burn * 60)) < 1):
        raise BadInput("quan.burn_s phải là null hoặc số dương")

    _validate_quan_layout(q, version=version)
    fixed_recipes = FIXED_RECIPES_V10 if is_v10 else FIXED_RECIPES_V11
    allowed_kinds = KINDS_P1 if is_v10 else KINDS_P2
    if {k: (d.get("recipe") if isinstance(d, dict) else None) for k, d in menu.items()} != fixed_recipes:
        raise BadInput(f"tuning.menu phải khớp công thức cố định của contract v{version}")
    for dish_id, d in menu.items():
        price, cook = d.get("price"), d.get("cook_s")
        if (isinstance(price, bool) or not isinstance(price, int) or price <= 0 or not _num(cook)
                or int(round(cook * 60)) < 1):
            raise BadInput(f"menu.{dish_id}: price nguyên dương, cook_s quy đổi ra số tick dương")
        recipe = d.get("recipe")
        if not isinstance(recipe, dict) or not recipe:
            raise BadInput(f"menu.{dish_id}: recipe phải là object không rỗng")
        for k, n in recipe.items():
            if k not in allowed_kinds:
                raise BadInput(f"menu.{dish_id}: nguyên liệu lạ {k}")
            _int_between(f"menu.{dish_id}.recipe.{k}", n, 1, 10_000)

    if not is_v10:
        dp = t.get("day_plan")
        if not isinstance(dp, list) or len(dp) != 5:
            raise BadInput("tuning.day_plan phải có đúng 5 ngày (D1–D5)")
        shop = t.get("shop")
        if not isinstance(shop, dict) or "upgrades" not in shop:
            raise BadInput("tuning.shop phải có max_ticks và upgrades")
        _int_between("shop.max_ticks", shop.get("max_ticks"), 1, 100_000)

    if is_v12(version):
        _validate_freshness(t.get("freshness"))

    score = t.get("score")
    if not isinstance(score, dict) or not _num(score.get("reputation_multiplier")) or score["reputation_multiplier"] < 0:
        raise BadInput("tuning.score.reputation_multiplier phải là số >= 0")


def _validate_quan_layout(q, version="1.1"):
    qb = q["bounds"]
    _pos_in("quan.start_pos", q.get("start_pos"), qb, ("x", "z"))
    _int_between("quan.carry_limit", q.get("carry_limit"), 1, 10_000)
    rmin, rmax, rinit = q.get("reputation_min"), q.get("reputation_max"), q.get("reputation_initial")
    if not (_num(rmin) and _num(rmax) and _num(rinit) and rmin < rmax and rmin <= rinit <= rmax):
        raise BadInput("quan: cần reputation_min < reputation_max và reputation_initial nằm giữa")
    fixed_layout = FIXED_LAYOUT_V10 if version == "1.0" else FIXED_LAYOUT_V11
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
        if sorted(seen) != list(fixed_layout[name]):
            raise BadInput(f"tuning.quan.{name} phải đúng {list(fixed_layout[name])}")
