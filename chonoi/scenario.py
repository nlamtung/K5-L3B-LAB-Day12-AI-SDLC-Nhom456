"""Nạp và kiểm scenario (Contract D). Trả về dict của đúng khối theo mode.

KHUNG: kiểm cú pháp, id trùng, bộ đếm âm, khoang vượt sức chứa, trường lạ.
Lát 3 (TV2): kiểm mâu thuẫn mức luật của quán theo PRD-0 mục D (khách, đơn, bếp, tay, liên kết đơn ↔ món).
Riêng "giữ quá tồn" kiểm ở QuanSim (lúc đó mới biết kho thật, kể cả khi kho đến từ --inventory).
v1.2 (TICKET-03): gather.hold và quan.stock là mảng cá thể {id, kind, fresh}; customers[].reserved là mảng id cá thể
(liên kết tới kho — có thật, chưa ươn, đủ công thức, không dùng chung — kiểm ở QuanSim vì kho có thể đến từ --inventory).
day (v1.1 mục 4.3, TV3): nhận khối gather, quan làm mẫu khởi tạo mỗi Ngày và khối day {money, earned, reputation,
upgrades, day_plan}; cấm quan.stock / quan.reputation; trả về {"gather", "quan", "day"}.
"""

import json

from .errors import BadInput
from .inventory import KINDS_P2, validate_item_list, validate_items

GATHER_KEYS = {"player", "hold", "nodes", "fish", "random_fish", "monsters", "time_left_ticks"}
GATHER_PLAYER_KEYS = {"pos", "vel", "heading_deg", "hp", "oxygen_ticks", "zero_oxy_ticks",
                      "invuln_ticks", "catch_cd_ticks"}
NODE_KINDS = ("bong_dien_dien", "bong_sung", "keo_neo")
FISH_KINDS = ("ca_linh", "ca_loc", "ca_keo")
MONSTER_KEYS = {"id", "kind", "pos", "waypoints", "target_idx", "state", "state_ticks_left", "recoil_dir"}
MONSTER_STATES = ("patrol", "chase", "recoil", "stunned")
QUAN_PLAYER_KEYS = {"pos", "vel"}
QUAN_KEYS = {"player", "stock", "hand", "stoves", "tables", "customers", "random_customers",
             "reputation", "time_left_ticks"}
# Quán (PRD-0 mục D) — lát 3, TV2
QUAN_CUSTOMER_KEYS = {"id", "table_id", "dish_id", "order_tick", "state", "patience_ticks_left", "eat_ticks_left",
                      "order_status", "reserved", "base_price", "tip"}
CUSTOMER_STATES = ("waiting", "eating")
ORDER_STATUSES = ("reserved", "assigned", "unfulfillable", "served")
QUAN_STOVE_KEYS = {"id", "pos", "state", "dish", "cook_ticks_left", "ready_ticks"}
QUAN_TABLE_KEYS = {"id", "pos"}
STOVE_STATES = ("idle", "cooking", "ready")
PAYLOAD_KEYS = {"order_id", "dish_id", "base_price"}


def _check_ids(name, arr):
    if not isinstance(arr, list):
        raise BadInput(f"{name} phải là mảng")
    seen = set()
    for e in arr:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not e["id"]:
            raise BadInput(f"{name}: mỗi phần tử cần id (chuỗi khác rỗng)")
        if e["id"] in seen:
            raise BadInput(f"{name}: id trùng {e['id']}")
        seen.add(e["id"])


def _validate_day_block(d, tuning):
    if not isinstance(d, dict):
        raise BadInput("khối day phải là object")
    allowed = {"money", "earned", "reputation", "upgrades", "day_plan"}
    extra = set(d) - allowed
    if extra:
        raise BadInput(f"trường lạ trong day: {sorted(extra)}")
    if ("money" in d) != ("earned" in d):
        raise BadInput("day: phải khai cả money và earned khi có tiền đầu kỳ")
    if "money" in d:
        _nonneg_int("day.money", d["money"])
        _nonneg_int("day.earned", d["earned"])
        if d["money"] > d["earned"]:
            raise BadInput("day: cần 0 <= money <= earned")
    if "reputation" in d:
        r = d["reputation"]
        q = tuning["quan"]
        if not _num(r) or not (q["reputation_min"] <= r <= q["reputation_max"]):
            raise BadInput(f"day.reputation phải trong [{q['reputation_min']}, {q['reputation_max']}]")
    if "upgrades" in d:
        ups = d["upgrades"]
        if not isinstance(ups, dict):
            raise BadInput("day.upgrades phải là object")
        shop_ups = tuning.get("shop", {}).get("upgrades", {})
        for k, lv in ups.items():
            if k not in shop_ups:
                raise BadInput(f"day.upgrades: nâng cấp lạ {k}")
            _nonneg_int(f"day.upgrades.{k}", lv)
            top = max(e["level"] for e in shop_ups[k])
            if lv > top:
                raise BadInput(f"day.upgrades.{k}: cấp {lv} vượt trần {top}")
    if "day_plan" in d:
        dp = d["day_plan"]
        if not isinstance(dp, list):
            raise BadInput("day.day_plan phải là mảng")
        menu = tuning["menu"]
        max_day = len(tuning.get("day_plan", []))
        seen_days = set()
        for e in dp:
            if not isinstance(e, dict) or not set(e) <= {"day", "dishes", "ingredients"}:
                raise BadInput("day.day_plan: mỗi phần tử chỉ có day, dishes, ingredients")
            dn = e.get("day")
            if isinstance(dn, bool) or not isinstance(dn, int) or not (1 <= dn <= max_day) or dn in seen_days:
                raise BadInput(f"day.day_plan: day không hợp lệ hoặc trùng ({dn!r})")
            seen_days.add(dn)
            dishes = e.get("dishes")
            if not isinstance(dishes, dict) or not dishes:
                raise BadInput(f"day.day_plan.{dn}: dishes phải là object không rỗng")
            calc = {}
            for did, qty in dishes.items():
                if did not in menu:
                    raise BadInput(f"day.day_plan.{dn}: món ngoài menu ({did})")
                if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
                    raise BadInput(f"day.day_plan.{dn}.dishes.{did}: số suất phải nguyên dương")
                for k, n in menu[did]["recipe"].items():
                    calc[k] = calc.get(k, 0) + n * qty
            if "ingredients" in e:
                ing = e["ingredients"]
                if not isinstance(ing, dict) or {k: v for k, v in ing.items() if v != 0} != calc:
                    raise BadInput(f"day.day_plan.{dn}: ingredients không khớp tổng công thức ({calc})")


def _validate_mode_block(block, mode: str, tuning: dict):
    if not isinstance(block, dict):
        raise BadInput(f"khối {mode} phải là object")
    allowed = GATHER_KEYS if mode == "gather" else QUAN_KEYS
    extra = set(block) - allowed
    if extra:
        raise BadInput(f"trường lạ/chưa hỗ trợ trong {mode}: {sorted(extra)}")
    dur = int(round(tuning[mode]["duration_s"] * 60))
    if "time_left_ticks" in block:
        t = block["time_left_ticks"]
        if isinstance(t, bool) or not isinstance(t, int) or not (1 <= t <= dur):
            raise BadInput(f"time_left_ticks phải là số nguyên trong [1, {dur}]")
    if mode == "gather":
        _validate_gather(block, tuning)
    else:
        _validate_quan(block, tuning)


def load_scenario(path, mode: str, tuning: dict) -> dict:
    if path is None:
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise BadInput(f"không đọc được scenario {path}: {e}")
    if mode == "day":
        if not isinstance(data, dict) or not set(data) <= {"day", "gather", "quan"}:
            raise BadInput("scenario day chỉ được có khối 'day', 'gather' hoặc 'quan'")
        if "day" in data:
            _validate_day_block(data["day"], tuning)
        if "gather" in data:
            _validate_mode_block(data["gather"], "gather", tuning)
        if "quan" in data:
            qb = data["quan"]
            if isinstance(qb, dict) and ("stock" in qb or "reputation" in qb):
                raise BadInput("cấm khai quan.stock và quan.reputation khi chạy --mode day")
            _validate_mode_block(qb, "quan", tuning)
        return data
    if not isinstance(data, dict) or not set(data) <= {"gather", "quan"}:
        raise BadInput("scenario chỉ được có khối 'gather' hoặc 'quan'")
    if set(data) - {mode}:
        raise BadInput(f"khối sai mode: chạy --mode {mode} chỉ nhận khối '{mode}'")
    block = data.get(mode, {})
    _validate_mode_block(block, mode, tuning)
    return block


def _v12(tuning) -> bool:
    """Contract v1.2 có khối tuning.freshness (kho cá thể)."""
    return tuning.get("freshness") is not None


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _nonneg_int(name, v):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise BadInput(f"{name} phải là số nguyên không âm")


def _pos(name, pos, bounds, axes=("x", "d")):
    if not (isinstance(pos, list) and len(pos) == 2 and all(_num(c) for c in pos)):
        raise BadInput(f"{name} phải là [{axes[0]}, {axes[1]}]")
    for c, axis in zip(pos, axes):
        lo, hi = bounds[axis]
        if not (lo <= c <= hi):
            raise BadInput(f"{name} nằm ngoài vùng nước ({axis} ∈ [{lo}, {hi}])")


def _validate_gather(b, tuning):
    g = tuning["gather"]
    bounds = g["bounds"]
    for arr in ("nodes", "fish", "monsters"):
        if arr in b:
            _check_ids(arr, b[arr])
    if "random_fish" in b and not isinstance(b["random_fish"], bool):
        raise BadInput("random_fish phải là boolean")
    if "hold" in b:
        h = b["hold"]
        if _v12(tuning):
            validate_item_list(h, "gather.hold")
        elif not isinstance(h, list) or any(k not in KINDS_P2 for k in h):
            raise BadInput("hold phải là mảng id nguyên liệu hợp lệ")
        if len(h) > g["hold_capacity"]:
            raise BadInput("hold vượt sức chứa")
    p = b.get("player", {})
    if not isinstance(p, dict):
        raise BadInput("player phải là object")
    extra = set(p) - GATHER_PLAYER_KEYS
    if extra:
        raise BadInput(f"trường lạ/chưa hỗ trợ trong gather.player: {sorted(extra)}")
    if "pos" in p:
        _pos("player.pos", p["pos"], bounds)
    if "vel" in p and not (isinstance(p["vel"], list) and len(p["vel"]) == 2 and all(_num(c) for c in p["vel"])):
        raise BadInput("player.vel phải là [x, d]")
    if "heading_deg" in p and not _num(p["heading_deg"]):
        raise BadInput("player.heading_deg phải là số")
    for key in ("invuln_ticks", "catch_cd_ticks", "zero_oxy_ticks", "oxygen_ticks", "hp"):
        if key in p:
            _nonneg_int(f"player.{key}", p[key])
    omax = int(round(g["oxygen_max_s"] * 60))
    if "oxygen_ticks" in p and p["oxygen_ticks"] > omax:
        raise BadInput("player.oxygen_ticks vượt oxy tối đa")
    if "hp" in p and not (1 <= p["hp"] <= g["hp_max"]):
        raise BadInput("player.hp phải trong [1, hp_max]")
    if "zero_oxy_ticks" in p:
        pos = p.get("pos", g["start_pos"])
        oxy = p.get("oxygen_ticks", omax)
        if p["zero_oxy_ticks"] > 59:
            raise BadInput("player.zero_oxy_ticks phải trong [0, 59]")
        if p["zero_oxy_ticks"] > 0 and not (oxy == 0 and pos[1] > g["surface_depth"]):
            raise BadInput("player.zero_oxy_ticks > 0 chỉ khi oxy = 0 và đang dưới nước")
    for n in b.get("nodes", []):
        if n.get("kind") not in NODE_KINDS:
            raise BadInput(f"nodes.{n['id']}: kind phải là một trong {NODE_KINDS}")
        _pos(f"nodes.{n['id']}.pos", n.get("pos"), bounds)
        if n["pos"][1] != 0:
            raise BadInput(f"nodes.{n['id']}: nút hái nằm ở mặt nước (d = 0)")
        if "regrow_ticks" in n:
            _nonneg_int(f"nodes.{n['id']}.regrow_ticks", n["regrow_ticks"])
    for f in b.get("fish", []):
        if f.get("kind") not in FISH_KINDS:
            raise BadInput(f"fish.{f['id']}: kind phải là một trong {FISH_KINDS}")
        _pos(f"fish.{f['id']}.pos", f.get("pos"), bounds)
        if f["pos"][1] <= g["surface_depth"]:
            raise BadInput(f"fish.{f['id']}: đàn cá phải ở dưới nước")
        if "heading_deg" in f and not _num(f["heading_deg"]):
            raise BadInput(f"fish.{f['id']}.heading_deg phải là số")
        if "age_ticks" in f:
            _nonneg_int(f"fish.{f['id']}.age_ticks", f["age_ticks"])
    species_map = g.get("monsters", {}).get("species", {})
    for m in b.get("monsters", []):
        mid = m["id"]
        extra = set(m) - MONSTER_KEYS
        if extra:
            raise BadInput(f"monsters.{mid}: trường lạ {sorted(extra)}")
        kind = m.get("kind")
        if kind not in species_map:
            raise BadInput(f"monsters.{mid}: kind không hợp lệ ({kind!r})")
        sp = species_map[kind]
        d_lo, d_hi = sp["depths"]
        _pos(f"monsters.{mid}.pos", m.get("pos"), bounds)
        if not (d_lo <= m["pos"][1] <= d_hi):
            raise BadInput(f"monsters.{mid}.pos: d phải trong [{d_lo}, {d_hi}]")
        wps = m.get("waypoints")
        if not isinstance(wps, list) or len(wps) != 2:
            raise BadInput(f"monsters.{mid}.waypoints phải gồm đúng 2 điểm")
        for idx, wp in enumerate(wps):
            _pos(f"monsters.{mid}.waypoints[{idx}]", wp, bounds)
            if not (d_lo <= wp[1] <= d_hi):
                raise BadInput(f"monsters.{mid}.waypoints[{idx}]: d phải trong [{d_lo}, {d_hi}]")
        tidx = m.get("target_idx", 1)
        if isinstance(tidx, bool) or tidx not in (0, 1):
            raise BadInput(f"monsters.{mid}.target_idx phải là 0 hoặc 1")
        st = m.get("state", "patrol")
        if st not in MONSTER_STATES:
            raise BadInput(f"monsters.{mid}.state phải thuộc {MONSTER_STATES}")
        if "state_ticks_left" in m:
            _nonneg_int(f"monsters.{mid}.state_ticks_left", m["state_ticks_left"])
        stl = m.get("state_ticks_left", 0)
        if st in ("recoil", "stunned") and stl < 1:
            raise BadInput(f"monsters.{mid}: trạng thái {st} cần state_ticks_left > 0")
        if st in ("patrol", "chase") and stl != 0:
            raise BadInput(f"monsters.{mid}: trạng thái {st} phải có state_ticks_left = 0")
        rdir = m.get("recoil_dir")
        if st == "recoil":
            if not (isinstance(rdir, list) and len(rdir) == 2 and all(_num(c) for c in rdir)):
                raise BadInput(f"monsters.{mid}: recoil cần recoil_dir là vector đơn vị [x, d]")
            norm = (rdir[0] ** 2 + rdir[1] ** 2) ** 0.5
            if abs(norm - 1.0) > 1e-2:
                raise BadInput(f"monsters.{mid}: recoil_dir phải là vector đơn vị")
        elif rdir is not None:
            raise BadInput(f"monsters.{mid}: recoil_dir phải là null khi không recoil")


def _ticks(seconds):
    return int(round(seconds * 60))


def _payload(name, p, menu):
    """Payload món (mục D): {order_id, dish_id, base_price}, order_id = id khách."""
    if not isinstance(p, dict) or set(p) != PAYLOAD_KEYS:
        raise BadInput(f"{name} phải là null hoặc payload món {sorted(PAYLOAD_KEYS)}")
    if not isinstance(p["order_id"], str) or not p["order_id"]:
        raise BadInput(f"{name}.order_id phải là id khách")
    if not isinstance(p["dish_id"], str) or p["dish_id"] not in menu:
        raise BadInput(f"{name}.dish_id ngoài phạm vi menu")
    price = p["base_price"]
    if isinstance(price, bool) or not isinstance(price, int) or price <= 0:
        raise BadInput(f"{name}.base_price phải là số nguyên dương")


def _validate_stove(s, q, menu):
    sid = s["id"]
    extra = set(s) - QUAN_STOVE_KEYS
    if extra:
        raise BadInput(f"stoves.{sid}: trường lạ {sorted(extra)}")
    if "pos" in s:
        _pos(f"stoves.{sid}.pos", s["pos"], q["bounds"], axes=("x", "z"))
    state, dish = s.get("state", "idle"), s.get("dish")
    if state not in STOVE_STATES:
        raise BadInput(f"stoves.{sid}: state phải là một trong {STOVE_STATES}")
    for key in ("cook_ticks_left", "ready_ticks"):
        if key in s:
            _nonneg_int(f"stoves.{sid}.{key}", s[key])
    cook, ready = s.get("cook_ticks_left", 0), s.get("ready_ticks", 0)
    if state == "idle":
        if dish is not None or cook or ready:
            raise BadInput(f"stoves.{sid}: bếp idle không có món, cook_ticks_left = ready_ticks = 0")
        return
    _payload(f"stoves.{sid}.dish", dish, menu)
    if state == "cooking":
        if not (1 <= cook <= _ticks(menu[dish["dish_id"]]["cook_s"])) or ready:
            raise BadInput(f"stoves.{sid}: bếp cooking cần cook_ticks_left trong [1, cook_s] và ready_ticks = 0")
    elif cook:
        raise BadInput(f"stoves.{sid}: bếp ready phải có cook_ticks_left = 0")


def _validate_customer(c, q, menu):
    """Khách theo mục D. Mặc định: waiting, order_tick 0, kiên nhẫn đầy, order_status reserved."""
    cid = c["id"]
    extra = set(c) - QUAN_CUSTOMER_KEYS
    if extra:
        raise BadInput(f"customers.{cid}: trường lạ {sorted(extra)}")
    if not isinstance(c.get("dish_id"), str) or c["dish_id"] not in menu:
        raise BadInput(f"customers.{cid}: dish_id thiếu hoặc ngoài phạm vi menu")
    state, status = c.get("state", "waiting"), c.get("order_status", "reserved")
    if state not in CUSTOMER_STATES:
        raise BadInput(f"customers.{cid}: state phải là một trong {CUSTOMER_STATES}")
    if status not in ORDER_STATUSES:
        raise BadInput(f"customers.{cid}: order_status phải là một trong {ORDER_STATUSES}")
    for key in ("order_tick", "patience_ticks_left", "eat_ticks_left", "tip"):
        if key in c:
            _nonneg_int(f"customers.{cid}.{key}", c[key])
    if c.get("patience_ticks_left", 0) > _ticks(q["patience_s"]):
        raise BadInput(f"customers.{cid}: patience_ticks_left vượt kiên nhẫn đầy")
    if c.get("eat_ticks_left", 0) > _ticks(q["eat_s"]):
        raise BadInput(f"customers.{cid}: eat_ticks_left vượt thời gian ăn")
    if "base_price" in c and (isinstance(c["base_price"], bool) or not isinstance(c["base_price"], int)
                              or c["base_price"] <= 0):
        raise BadInput(f"customers.{cid}: base_price phải là số nguyên dương")
    if "reserved" in c:
        r = c["reserved"]
        if not (isinstance(r, list) and all(isinstance(x, str) and x for x in r) and len(set(r)) == len(r)):
            raise BadInput(f"customers.{cid}.reserved phải là mảng id cá thể khác rỗng, không trùng (v1.2)")
        if status != "reserved" and r:
            raise BadInput(f"customers.{cid}: đơn {status} phải có reserved rỗng")
    if (state == "eating") != (status == "served"):
        raise BadInput(f"customers.{cid}: khách eating khi và chỉ khi đơn served")
    if state == "eating":
        if c.get("eat_ticks_left", 0) < 1:
            raise BadInput(f"customers.{cid}: khách eating cần eat_ticks_left dương")
        missing = [k for k in ("base_price", "tip") if k not in c]
        if missing:
            raise BadInput(f"customers.{cid}: khách eating thiếu {missing}")
    elif c.get("eat_ticks_left", 0):
        raise BadInput(f"customers.{cid}: chỉ khách eating mới có eat_ticks_left dương")


def _validate_quan_links(b, menu):
    """Liên kết đơn ↔ món trên bếp/tay: món phải trỏ đơn có thật, khớp dish_id, đơn đang assigned;
    mỗi đơn assigned có đúng một món ở bếp hoặc tay; bếp và tay không giữ cùng đơn."""
    orders = {c["id"]: c for c in b.get("customers", [])}
    holders = [(f"stoves.{s['id']}.dish", s.get("dish")) for s in b.get("stoves", [])]
    holders.append(("hand", b.get("hand")))
    count = {}
    for name, p in holders:
        if p is None:
            continue
        c = orders.get(p["order_id"])
        if c is None:
            raise BadInput(f"{name}: order_id {p['order_id']} không trỏ tới khách nào")
        if p["dish_id"] != c["dish_id"]:
            raise BadInput(f"{name}: món {p['dish_id']} không khớp đơn {c['id']} ({c['dish_id']})")
        if c.get("order_status", "reserved") != "assigned":
            raise BadInput(f"{name}: đơn {c['id']} phải ở trạng thái assigned khi đã có món")
        count[c["id"]] = count.get(c["id"], 0) + 1
    for cid, c in orders.items():
        if c.get("order_status", "reserved") == "assigned" and count.get(cid, 0) != 1:
            raise BadInput(f"customers.{cid}: đơn assigned phải có đúng một món ở bếp hoặc tay (đang có {count.get(cid, 0)})")


def _validate_quan(b, tuning):
    q, menu = tuning["quan"], tuning["menu"]
    for arr in ("stoves", "tables", "customers"):
        if arr in b:
            _check_ids(arr, b[arr])
    if "stock" in b:
        if _v12(tuning):
            validate_item_list(b["stock"], "quan.stock")
        else:
            validate_items(b["stock"])
    if "random_customers" in b and not isinstance(b["random_customers"], bool):
        raise BadInput("random_customers phải là boolean")
    if "reputation" in b:
        r = b["reputation"]
        if not _num(r) or not (q["reputation_min"] <= r <= q["reputation_max"]):
            raise BadInput(f"reputation phải trong [{q['reputation_min']}, {q['reputation_max']}]")
    if b.get("hand") is not None:
        _payload("hand", b["hand"], menu)
    for name, keys in (("stoves", None), ("tables", QUAN_TABLE_KEYS)):
        known = {e["id"] for e in q[name]}
        for e in b.get(name, []):
            if e["id"] not in known:
                raise BadInput(f"{name}.{e['id']}: id cập nhật không tồn tại")
            if keys is not None:
                if set(e) - keys:
                    raise BadInput(f"tables.{e['id']}: trường lạ {sorted(set(e) - keys)}")
                if "pos" in e:
                    _pos(f"tables.{e['id']}.pos", e["pos"], q["bounds"], axes=("x", "z"))
    for s in b.get("stoves", []):
        _validate_stove(s, q, menu)
    p = b.get("player", {})
    if not isinstance(p, dict) or set(p) - QUAN_PLAYER_KEYS:
        raise BadInput("quan.player chỉ có pos và vel")
    if "pos" in p:
        _pos("player.pos", p["pos"], q["bounds"], axes=("x", "z"))
    if "vel" in p and not (isinstance(p["vel"], list) and len(p["vel"]) == 2 and all(_num(c) for c in p["vel"])):
        raise BadInput("player.vel phải là [x, z]")
    tables = {t["id"] for t in q["tables"]}
    for c in b.get("customers", []):
        if not isinstance(c.get("table_id"), str) or c["table_id"] not in tables:
            raise BadInput(f"customers.{c['id']}: table_id phải là bàn có thật")
        _validate_customer(c, q, menu)
    table_ids = [c["table_id"] for c in b.get("customers", [])]
    if len(table_ids) != len(set(table_ids)):
        raise BadInput("hai khách cùng bàn")
    _validate_quan_links(b, menu)


# --- day (TICKET-02, Test Contract v1.1 mục 4.3) — TV3 -----------------------------------
DAY_KEYS = {"money", "earned", "reputation", "upgrades", "day_plan"}
DAY_FORBIDDEN_QUAN_KEYS = ("stock", "reputation")  # kho đến từ gather.hold, uy tín ở khối day
PLAN_OVERRIDE_KEYS = {"day", "dishes", "ingredients"}


def _load_day(data, tuning):
    if not isinstance(data, dict) or not set(data) <= {"gather", "quan", "day"}:
        raise BadInput("scenario của day chỉ được có khối 'gather', 'quan', 'day'")
    quan = data.get("quan", {})
    if isinstance(quan, dict):
        banned = [k for k in DAY_FORBIDDEN_QUAN_KEYS if k in quan]
        if banned:
            raise BadInput(f"chạy day cấm quan.{'/'.join(banned)} (dựng hàng bằng gather.hold, uy tín ở khối day)")
    out = {}
    for mode in ("gather", "quan"):
        if mode in data:
            _validate_block(mode, data[mode], tuning)
            out[mode] = data[mode]
    out["day"] = _validate_day(data.get("day", {}), tuning)
    return out


def _validate_day(b, tuning):
    if not isinstance(b, dict):
        raise BadInput("khối day phải là object")
    extra = set(b) - DAY_KEYS
    if extra:
        raise BadInput(f"trường lạ/chưa hỗ trợ trong day: {sorted(extra)}")
    for key in ("money", "earned"):
        if key in b:
            _nonneg_int(f"day.{key}", b[key])
    money, earned = b.get("money", 0), b.get("earned", 0)
    if money > 0 and "earned" not in b:
        raise BadInput("day: có tiền đầu kỳ thì khai cả money và earned")
    if money > earned:
        raise BadInput("day: cần 0 ≤ money ≤ earned")
    q = tuning["quan"]
    if "reputation" in b and (not _num(b["reputation"]) or
                              not (q["reputation_min"] <= b["reputation"] <= q["reputation_max"])):
        raise BadInput(f"day.reputation phải trong [{q['reputation_min']}, {q['reputation_max']}]")
    if "upgrades" in b:
        ups = b["upgrades"]
        shop = tuning.get("shop", {}).get("upgrades", {})
        if not isinstance(ups, dict):
            raise BadInput("day.upgrades phải là map id nâng cấp -> cấp")
        for k, lv in ups.items():
            if k not in shop:
                raise BadInput(f"day.upgrades: nâng cấp lạ {k!r}")
            _nonneg_int(f"day.upgrades.{k}", lv)
            if lv > max(e["level"] for e in shop[k]):
                raise BadInput(f"day.upgrades.{k}: cấp {lv} vượt cấp tối đa")
    if "day_plan" in b:
        _validate_plan_overrides(b["day_plan"], tuning)
    return b


def _validate_plan_overrides(plan, tuning):
    """day.day_plan ghi đè theo số Ngày, mỗi mục có dishes; ingredients nếu khai phải bằng Σ công thức × số suất."""
    if not isinstance(plan, list):
        raise BadInput("day.day_plan phải là mảng")
    menu, max_day = tuning["menu"], len(tuning.get("day_plan", []))
    seen = set()
    for i, e in enumerate(plan):
        name = f"day.day_plan[{i}]"
        if not isinstance(e, dict) or set(e) - PLAN_OVERRIDE_KEYS or "dishes" not in e:
            raise BadInput(f"{name} cần dishes, chỉ có các khóa {sorted(PLAN_OVERRIDE_KEYS)}")
        d = e.get("day")
        if isinstance(d, bool) or not isinstance(d, int) or not (1 <= d <= max_day) or d in seen:
            raise BadInput(f"{name}.day phải là số nguyên trong [1, {max_day}], không trùng")
        seen.add(d)
        dishes = e["dishes"]
        if not isinstance(dishes, dict) or not dishes:
            raise BadInput(f"{name}.dishes phải là map không rỗng id món -> số suất")
        want = {}
        for dish_id, n in dishes.items():
            if dish_id not in menu:
                raise BadInput(f"{name}.dishes: món ngoài thực đơn {dish_id!r}")
            if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
                raise BadInput(f"{name}.dishes.{dish_id} phải là số nguyên dương")
            for kind, k in menu[dish_id]["recipe"].items():
                want[kind] = want.get(kind, 0) + k * n
        if "ingredients" in e and e["ingredients"] != want:
            raise BadInput(f"{name}.ingredients phải bằng tổng công thức × số suất: {dict(sorted(want.items()))}")
