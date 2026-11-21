"""Nạp và kiểm scenario (Contract D). Trả về dict của đúng khối theo mode.

KHUNG: kiểm cú pháp, id trùng, bộ đếm âm, khoang vượt sức chứa, trường lạ.
Lát 3 (TV2): kiểm mâu thuẫn mức luật của quán theo PRD-0 mục D (khách, đơn, bếp, tay, liên kết đơn ↔ món).
Riêng "giữ quá tồn" kiểm ở QuanSim (lúc đó mới biết kho thật, kể cả khi kho đến từ --inventory).
TICKET-02 (TV2): khối day {money, earned, reputation, upgrades, day_plan}; chạy day cấm quan.stock / quan.reputation.
"""

import json

from .contract import DAYS
from .day_plan import validate_plan_entry
from .errors import BadInput
from .inventory import KINDS, validate_items

GATHER_KEYS = {"player", "hold", "nodes", "fish", "random_fish", "time_left_ticks"}
GATHER_PLAYER_KEYS = {"pos", "vel", "heading_deg", "hp", "oxygen_ticks", "zero_oxy_ticks",
                      "invuln_ticks", "catch_cd_ticks"}
NODE_KINDS = ("bong_dien_dien", "bong_sung")
FISH_KINDS = ("ca_linh", "ca_loc")
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


def load_scenario(path, mode: str, tuning: dict) -> dict:
    """gather/quan: trả về dict của đúng khối theo mode.
    day (v1.1): trả về {"gather": ..., "quan": ..., "day": ...} — gather/quan là mẫu khởi tạo mỗi Ngày."""
    if path is None:
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise BadInput(f"không đọc được scenario {path}: {e}")
    if mode == "day":
        return _load_day(data, tuning)
    if not isinstance(data, dict) or not set(data) <= {"gather", "quan"}:
        raise BadInput("scenario chỉ được có khối 'gather' hoặc 'quan'")
    if set(data) - {mode}:
        raise BadInput(f"khối sai mode: chạy --mode {mode} chỉ nhận khối '{mode}'")
    block = data.get(mode, {})
    _validate_block(mode, block, tuning)
    return block


def _validate_block(mode, block, tuning):
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


# --- day (TICKET-02, Test Contract v1.1 mục 4.3) — TV2 -----------------------------------
DAY_KEYS = {"money", "earned", "reputation", "upgrades", "day_plan"}
DAY_FORBIDDEN_QUAN_KEYS = ("stock", "reputation")  # kho đến từ gather, uy tín từ khối day
UPGRADE_IDS = ("oxygen", "hp", "weapon", "net")  # lõi: oxygen, hp; mở rộng: weapon, net


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
    """Khối day {money, earned, reputation, upgrades, day_plan}: trạng thái xuyên Ngày."""
    if not isinstance(b, dict):
        raise BadInput("khối day phải là object")
    extra = set(b) - DAY_KEYS
    if extra:
        raise BadInput(f"trường lạ/chưa hỗ trợ trong day: {sorted(extra)}")
    for key in ("money", "earned"):
        if key in b:
            _nonneg_int(f"day.{key}", b[key])
    if b.get("money", 0) > 0 and "earned" not in b:
        raise BadInput("day: có tiền đầu kỳ thì khai cả money và earned")
    if b.get("money", 0) > b.get("earned", 0):
        raise BadInput("day: cần 0 ≤ money ≤ earned")
    q = tuning["quan"]
    if "reputation" in b:
        r = b["reputation"]
        if not _num(r) or not (q["reputation_min"] <= r <= q["reputation_max"]):
            raise BadInput(f"day.reputation phải trong [{q['reputation_min']}, {q['reputation_max']}]")
    if "upgrades" in b:
        _validate_upgrades(b["upgrades"], tuning)
    if "day_plan" in b:
        plan = b["day_plan"]
        if not isinstance(plan, list):
            raise BadInput("day.day_plan phải là mảng")
        seen = set()
        for i, e in enumerate(plan):
            entry = validate_plan_entry(f"day.day_plan[{i}]", e, tuning["menu"], DAYS, require_ingredients=False)
            if entry["day"] in seen:
                raise BadInput(f"day.day_plan: trùng Ngày {entry['day']}")
            seen.add(entry["day"])
    return b


def _validate_upgrades(ups, tuning):
    """Cấp đã mua: map id nâng cấp -> cấp (nguyên ≥ 0). Có tuning.shop thì kiểm theo số cấp khai ở đó."""
    if not isinstance(ups, dict):
        raise BadInput("day.upgrades phải là map id nâng cấp -> cấp")
    shop = tuning.get("shop", {}).get("upgrades") if isinstance(tuning.get("shop"), dict) else None
    known = set(shop) if isinstance(shop, dict) else set(UPGRADE_IDS)
    for k, lv in ups.items():
        if k not in known:
            raise BadInput(f"day.upgrades: nâng cấp lạ {k!r}")
        _nonneg_int(f"day.upgrades.{k}", lv)
        if isinstance(shop, dict) and lv > len(shop[k]):
            raise BadInput(f"day.upgrades.{k}: cấp {lv} vượt cấp tối đa {len(shop[k])}")


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
    for arr in ("nodes", "fish"):
        if arr in b:
            _check_ids(arr, b[arr])
    if "random_fish" in b and not isinstance(b["random_fish"], bool):
        raise BadInput("random_fish phải là boolean")
    if "hold" in b:
        h = b["hold"]
        if not isinstance(h, list) or any(k not in KINDS for k in h):
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
    recipe = {k: v for k, v in menu[c["dish_id"]]["recipe"].items() if v > 0}
    if "reserved" in c:
        try:
            held = validate_items(c["reserved"])
        except BadInput as e:
            raise BadInput(f"customers.{cid}.reserved: {e}")
        want = recipe if status == "reserved" else {}
        if held != want:
            raise BadInput(f"customers.{cid}: reserved {held} khác {'công thức' if want else 'rỗng'} của đơn {status}")
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
