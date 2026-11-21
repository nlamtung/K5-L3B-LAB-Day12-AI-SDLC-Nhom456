"""Buổi tối — Mở Quán. KHUNG: đi lại, chặn biên, đồng hồ, kho nạp từ file/scenario.

Theo PRD-0 (mục D, E, F "Quán"):
  Lát 3 (TV2): khách đến theo lịch phase_tick, chọn món đều theo seed, giữ chỗ nguyên liệu,
        kiên nhẫn, rời bàn (customer_left: patience / closing), no_dish, khách dựng sẵn từ scenario.
  Lát 4 (TV3): bếp (nấu, chín, ready_ticks), interact chọn theo (khoảng cách, bếp trước bàn, id):
        cook_started / dish_picked / served (chốt boa); ăn xong trả tiền (paid: finished_eating / closing),
        boa dương cộng uy tín.

Khách (mục D): {id, table_id, dish_id, order_tick, state, patience_ticks_left, eat_ticks_left,
                order_status, reserved, base_price, tip}
  state: waiting | eating · order_status: reserved | assigned | unfulfillable | served
  order_id của đơn = id khách. Payload món (bếp `dish`, `hand`) = {order_id, dish_id, base_price}.
Kho: `stock` là tồn VẬT LÝ, gồm cả phần giữ chỗ. Kho khả dụng = stock − Σ reserved (`available_stock`).
  Lát 4 khi bắt đầu nấu: trừ stock đúng phần giữ, đặt reserved = {}, order_status = "assigned".
Hợp đồng chi tiết: docs/contracts/quan.md.

v1.2 (TICKET-03, Change Request độ tươi) — [THAY THẾ] các luật kho/giữ chỗ/giá ở trên:
  - `stock` là mảng cá thể {id, kind, fresh} (gồm cả hàng đang giữ, cả hàng ươn). Snapshot theo id.
  - Bước 1b: hao quan_decay mọi cá thể kho thô, phát hết `spoiled` (location "stock") theo id; rồi các đơn reserved có
    cá thể vừa ươn (theo order_tick rồi id bàn): nhả toàn bộ phần giữ và thử giữ lại đúng một lần, thiếu -> unfulfillable.
  - Giữ theo id: mỗi kind của công thức lấy các cá thể khả dụng (chưa giữ, chưa ươn) tươi nhất, hòa theo id.
    `customers[].reserved` là mảng id cá thể.
  - Bắt đầu nấu: tiêu đúng các id đang giữ, base_price = floor(giá niêm yết × trung bình fresh / 100);
    cook_started.items là mảng cá thể sắp theo kind rồi id. Boa tính trên giá đã chốt.
"""

import math

from ..errors import BadInput
from ..fresh import Freshness
from ..ids import id_key, sort_by_id
from .ramp import ramp_velocity

TICK = 60.0
CUSTOMER_DISH_STREAM = "customer_dish"  # luồng RNG riêng cho việc khách chọn món


def to_ticks(seconds) -> int:
    return int(round(seconds * TICK))


def recipe_fits(recipe: dict, available: dict) -> bool:
    """available: map kind -> số cá thể khả dụng."""
    return all(available.get(k, 0) >= n for k, n in recipe.items())


class QuanSim:
    mode = "quan"
    phase = "quan"

    def __init__(self, tuning, scenario, streams, ids, inventory=None, plan_dishes=None):
        """`plan_dishes` (chỉ dùng trong `--mode day`, TICKET-02 mục 2 / v1.1 mục 4.5): id món trong kế hoạch Ngày.
        Có thì khách chỉ chọn trong các món đó (lọc kế hoạch TRƯỚC khi lọc nguyên liệu khả dụng), và món của
        khách/bếp/tay dựng sẵn phải thuộc kế hoạch (mã 2). Quán chạy riêng để None: dùng cả thực đơn."""
        t = tuning["quan"]
        self.t = t
        self.menu = tuning["menu"]
        self.plan_dishes = None if plan_dishes is None else sorted(plan_dishes)
        if self.plan_dishes is not None and not set(self.plan_dishes) <= set(self.menu):
            raise BadInput(f"kế hoạch có món ngoài thực đơn: {sorted(set(self.plan_dishes) - set(self.menu))}")
        self.rng = streams
        self.ids = ids
        p = scenario.get("player", {})
        self.pos = list(p.get("pos", t["start_pos"]))
        self.vel = [float(c) for c in p.get("vel", [0.0, 0.0])]
        self._tgt = None
        self._ramp_left = 0
        # kho: --inventory HOẶC scenario.stock (cả hai -> cli đã báo mã 2); v1.2 là mảng cá thể
        self.fresh = Freshness(tuning)
        src_stock = inventory if inventory is not None else scenario.get("stock", [])
        self.stock = [self.fresh.load(it) for it in src_stock]
        if len({it["id"] for it in self.stock}) != len(self.stock):
            raise BadInput("kho quán có id cá thể trùng")
        for it in self.stock:
            ids.reserve(it["id"])
        self.hand = scenario.get("hand")
        self.duration_ticks = to_ticks(t["duration_s"])
        self.time_left_ticks = scenario.get("time_left_ticks", self.duration_ticks)
        self.phase_tick = 0  # lịch khách tính theo phase_tick kể cả khi rút ngắn ca (PRD-0 mục D)
        self.reputation = scenario.get("reputation", t["reputation_initial"])
        self.stoves = [dict(s, state=s.get("state", "idle"), dish=s.get("dish"),
                            cook_ticks_left=s.get("cook_ticks_left", 0), ready_ticks=s.get("ready_ticks", 0))
                       for s in self._merge(t["stoves"], scenario.get("stoves", []))]
        self.tables = self._merge(t["tables"], scenario.get("tables", []))
        # --- Lát 3 (TV2): khách ---
        self.patience_max_ticks = to_ticks(t["patience_s"])
        self.customer_interval_ticks = to_ticks(t["customer_interval_s"])
        self.random_customers = scenario.get("random_customers", True)
        self.customers = [self._customer_from_scenario(c) for c in scenario.get("customers", [])]
        for e in self.customers:
            ids.reserve(e["id"])
        self._check_plan_dishes()
        self._init_reservations(scenario.get("customers", []))
        self.money = 0
        self.earned = 0
        self.shift_earned = 0
        self.done = False
        self.reason = None

    @staticmethod
    def _merge(defaults, updates):
        by_id = {d["id"]: dict(d) for d in defaults}
        for u in updates:
            if u["id"] not in by_id:
                raise BadInput(f"id bếp/bàn không tồn tại: {u['id']}")
            by_id[u["id"]].update(u)
        return sort_by_id(list(by_id.values()))

    def snapshot(self) -> dict:
        occupied = {c["table_id"]: c["id"] for c in self.customers}
        return {
            "player": {"pos": self.pos, "vel": self.vel},
            "stock": self.fresh.out_list(self.stock),
            "hand": self.hand,
            "stoves": [{k: s.get(k) for k in ("id", "pos", "state", "dish", "cook_ticks_left", "ready_ticks")}
                       for s in self.stoves],
            "tables": [{"id": tb["id"], "pos": tb["pos"], "customer_id": occupied.get(tb["id"])} for tb in self.tables],
            "customers": sort_by_id(self.customers),
        }

    def step(self, inp):
        """Một bước theo PRD-0 mục F "Quán"."""
        events = []
        # 1. đồng hồ, timer ca, nấu (+ tuổi món ready), ăn, kiên nhẫn
        #    2. bếp theo id: nấu xong -> ready, dish_ready (gộp trong _tick_stoves; bước 1 không phát event)
        self.phase_tick += 1
        self.time_left_ticks = max(0, self.time_left_ticks - 1)
        self._tick_eating()             # lát 4
        self._tick_patience()           # lát 3
        # 1b. (v1.2) hao tươi kho thô, phát spoiled theo id, rồi xử lý phần giữ bị ươn
        self._tick_freshness(events)
        # 2. xét món chín / cháy theo id bếp
        self._tick_stoves(events)       # lát 4
        # 3. di chuyển rồi tối đa một interact (lát 4)
        self._move(inp)
        if inp.pressed("interact"):
            self._interact(events)
        # 4. theo id bàn: trả tiền (lát 4), rời bàn (lát 3); hết ca -> quan_end
        closing = self.time_left_ticks <= 0
        self._settle_customers(events, closing)
        if closing:
            self.done = True
            self.reason = "time"
            events.append(("quan_end", {"reason": "time", "money": self.money, "earned": self.earned,
                                        "shift_earned": self.shift_earned, "reputation": self.reputation}))
            return events
        # 5. lượt khách mới (chỉ khi còn giờ, lát 3)
        self._spawn_customer(events)
        return events

    # --- Lát 3 (TV2): khách — hàm dùng chung cho lát 4 ------------------------------
    def available_items(self) -> list:
        """Cá thể khả dụng: trong kho, chưa bị đơn nào giữ, chưa ươn."""
        held = {iid for c in self.customers for iid in c["reserved"]}
        return [it for it in self.stock if it["id"] not in held and not self.fresh.spoiled(it)]

    def available_stock(self) -> dict:
        """Số cá thể khả dụng theo kind (tồn vật lý − phần giữ − hàng ươn)."""
        out = {}
        for it in self.available_items():
            out[it["kind"]] = out.get(it["kind"], 0) + 1
        return {k: out[k] for k in sorted(out)}

    def reserve_for(self, dish_id):
        """Giữ theo id: mỗi kind của công thức lấy cá thể khả dụng tươi nhất, hòa theo id. Thiếu -> None."""
        avail = self.available_items()
        picked = []
        for kind, n in self._recipe(dish_id).items():
            cands = [it for it in avail if it["kind"] == kind]
            if len(cands) < n:
                return None
            picked += self.fresh.freshest(cands, n)
        return sorted((it["id"] for it in picked), key=id_key)

    def add_reputation(self, delta):
        """Cộng uy tín, kẹp [reputation_min, reputation_max]. Lát 4 dùng cho boa (tip_reputation)."""
        self.reputation = min(self.t["reputation_max"], max(self.t["reputation_min"], self.reputation + delta))

    def remove_customer(self, c):
        """Khách rời bàn: nhả phần giữ thô (xóa khách là nhả), bỏ món của đơn đang nấu / ready / trên tay.
        Nguyên liệu đã dùng không hoàn lại. Lát 4 gọi sau khi `paid`."""
        self.customers = [x for x in self.customers if x["id"] != c["id"]]
        for s in self.stoves:
            if s.get("dish") and s["dish"].get("order_id") == c["id"]:
                s.update(state="idle", dish=None, cook_ticks_left=0, ready_ticks=0)
        if self.hand and self.hand.get("order_id") == c["id"]:
            self.hand = None

    # --- Lát 3 (TV2): nội bộ ---------------------------------------------------------
    def _recipe(self, dish_id) -> dict:
        r = self.menu[dish_id]["recipe"]
        return {k: r[k] for k in sorted(r)}

    def _customer_from_scenario(self, src) -> dict:
        """Mặc định (mục D): waiting, order_tick 0, kiên nhẫn đầy, order_status reserved.
        v1.2: `reserved` là mảng id cá thể; đơn reserved bỏ trống thì cấp sau (`_init_reservations`)."""
        status = src.get("order_status", "reserved")
        return {"id": src["id"], "table_id": src["table_id"], "dish_id": src["dish_id"],
                "order_tick": src.get("order_tick", 0), "state": src.get("state", "waiting"),
                "patience_ticks_left": src.get("patience_ticks_left", self.patience_max_ticks),
                "eat_ticks_left": src.get("eat_ticks_left", 0), "order_status": status,
                "reserved": sorted(src.get("reserved", []), key=id_key),
                "base_price": src.get("base_price"), "tip": src.get("tip")}

    def _init_reservations(self, src_customers):
        """Kiểm phần giữ khai sẵn (trỏ tới cá thể chưa ươn trong kho, đủ đúng công thức, không dùng chung đơn khác);
        rồi cấp cho đơn reserved bỏ trống `reserved` theo order_tick rồi id bàn (tươi nhất, id nhỏ). Sai -> mã 2."""
        by_id = {it["id"]: it for it in self.stock}
        explicit = {c["id"] for c in src_customers if "reserved" in c}
        used = set()
        for c in self.customers:
            ids = c["reserved"]
            if c["order_status"] != "reserved":
                if ids:
                    raise BadInput(f"customers.{c['id']}: đơn {c['order_status']} phải có reserved rỗng")
                continue
            if c["id"] not in explicit:
                continue
            kinds = {}
            for iid in ids:
                it = by_id.get(iid)
                if it is None:
                    raise BadInput(f"customers.{c['id']}.reserved: id {iid} không có trong kho")
                if iid in used:
                    raise BadInput(f"customers.{c['id']}.reserved: id {iid} đã bị đơn khác giữ")
                if self.fresh.spoiled(it):
                    raise BadInput(f"customers.{c['id']}.reserved: {iid} đã ươn")
                used.add(iid)
                kinds[it["kind"]] = kinds.get(it["kind"], 0) + 1
            if len(set(ids)) != len(ids) or kinds != self._recipe(c["dish_id"]):
                raise BadInput(f"customers.{c['id']}.reserved khác công thức {self._recipe(c['dish_id'])}")
        todo = [c for c in self.customers if c["order_status"] == "reserved" and c["id"] not in explicit]
        for c in sorted(todo, key=lambda x: (x["order_tick"], id_key(x["table_id"]))):
            ids = self.reserve_for(c["dish_id"])
            if ids is None:
                raise BadInput(f"customers.{c['id']}: giữ chỗ quá tồn kho khả dụng cho {c['dish_id']}")
            c["reserved"] = ids

    def _tick_freshness(self, events):
        """v1.2 bước 1b: hao kho thô (kể cả hàng đang giữ), phát hết spoiled theo id; rồi đơn reserved có cá thể vừa
        ươn (theo order_tick rồi id bàn) nhả toàn bộ phần giữ và thử giữ lại đúng một lần; thiếu -> unfulfillable."""
        spoiled = self.fresh.decay(self.stock, self.fresh.quan_decay, "stock")
        if not spoiled:
            return
        events += spoiled
        just = {data["item_id"] for _, data in spoiled}
        hit = [c for c in self.customers if c["order_status"] == "reserved" and just & set(c["reserved"])]
        for c in sorted(hit, key=lambda x: (x["order_tick"], id_key(x["table_id"]))):
            c["reserved"] = []
            ids = self.reserve_for(c["dish_id"])
            if ids is None:
                c["order_status"] = "unfulfillable"
            else:
                c["reserved"] = ids

    def _tick_patience(self):
        """Bước 1: khách waiting mất 1 kiên nhẫn (không âm). Việc rời bàn xét ở bước 4."""
        for c in self.customers:
            if c["state"] == "waiting":
                c["patience_ticks_left"] = max(0, c["patience_ticks_left"] - 1)

    def _settle_customers(self, events, closing):
        """Bước 4, theo id bàn:
        - khách eating: ăn xong -> paid(finished_eating); hết ca -> paid(closing) kể cả vừa được giao (lát 4)
        - khách waiting: hết ca -> rời closing, không trừ uy tín; còn giờ và kiên nhẫn 0 -> rời patience,
          uy tín + left_reputation_delta (lát 3)."""
        for c in sorted(self.customers, key=lambda x: id_key(x["table_id"])):
            if c["state"] == "eating":
                if c["eat_ticks_left"] == 0:
                    self._pay(c, "finished_eating", events)
                elif closing:
                    self._pay(c, "closing", events)
                continue
            if closing:
                self._leave(c, "closing", events)
            elif c["patience_ticks_left"] == 0:
                self.add_reputation(self.t["left_reputation_delta"])
                self._leave(c, "patience", events)

    def _leave(self, c, reason, events):
        self.remove_customer(c)
        events.append(("customer_left", {"order_id": c["id"], "table_id": c["table_id"], "reason": reason,
                                         "reputation": self.reputation}))

    def _free_table(self):
        occupied = {c["table_id"] for c in self.customers}
        return next((tb for tb in sort_by_id(self.tables) if tb["id"] not in occupied), None)

    def menu_candidates(self) -> list:
        """Id món khách được gọi, theo mã Unicode: trong day chỉ các món của kế hoạch Ngày."""
        return list(self.plan_dishes) if self.plan_dishes is not None else sorted(self.menu)

    def _check_plan_dishes(self):
        """Trong day: món của khách, bếp và tay dựng sẵn phải thuộc kế hoạch Ngày (mâu thuẫn -> mã 2)."""
        if self.plan_dishes is None:
            return
        used = [(f"customers.{c['id']}", c["dish_id"]) for c in self.customers]
        used += [(f"stoves.{s['id']}.dish", s["dish"]["dish_id"]) for s in self.stoves if s.get("dish")]
        if self.hand:
            used.append(("hand", self.hand["dish_id"]))
        for where, dish_id in used:
            if dish_id not in self.plan_dishes:
                raise BadInput(f"{where}: món {dish_id} không thuộc kế hoạch Ngày {self.plan_dishes}")

    def _choose_dish(self):
        """Chọn đều theo seed trong các món đủ nguyên liệu khả dụng (cá thể chưa giữ, chưa ươn); duyệt id món
        theo mã Unicode."""
        avail = self.available_stock()
        cookable = [d for d in self.menu_candidates() if recipe_fits(self.menu[d]["recipe"], avail)]
        if not cookable:
            return None
        return cookable[self.rng.get(CUSTOMER_DISH_STREAM).randrange(len(cookable))]

    def _spawn_customer(self, events):
        """Bước 5: lượt khách ở phase_tick = first_customer_tick + n × customer_interval. Không còn bàn -> bỏ lượt.
        Bàn trống id nhỏ nhất. Không món đủ -> no_dish {}. Khách mới giữ đúng công thức, order_tick = phase_tick,
        kiên nhẫn đầy (bắt đầu giảm từ bước sau)."""
        if not self.random_customers:
            return
        k, first = self.phase_tick, self.t["first_customer_tick"]
        if k < first or (k - first) % self.customer_interval_ticks:
            return
        table = self._free_table()
        if table is None:
            return
        dish = self._choose_dish()
        if dish is None:
            events.append(("no_dish", {}))
            return
        c = {"id": self.ids.new("C"), "table_id": table["id"], "dish_id": dish, "order_tick": k,
             "state": "waiting", "patience_ticks_left": self.patience_max_ticks, "eat_ticks_left": 0,
             "order_status": "reserved", "reserved": self.reserve_for(dish), "base_price": None, "tip": None}
        self.customers.append(c)
        events.append(("customer_arrived", {"order_id": c["id"], "table_id": c["table_id"], "dish_id": dish}))

    # --- Lát 4 (TV3): bếp ------------------------------------------------------------
    def _tick_stoves(self, events):
        """Món ready ở ĐẦU bước tăng tuổi; món đang nấu giảm timer, về 0 thì ready + dish_ready (theo id).
        Mở rộng burn (burn_s hữu hạn): tuổi món > burn ticks thì cháy (xem _burn); đúng burn ticks vẫn bưng được."""
        burn = self.t.get("burn_s")
        burn_ticks = None if burn is None else to_ticks(burn)
        for s in self.stoves:  # self.stoves đã sắp theo id
            if s["state"] == "ready":
                s["ready_ticks"] += 1
                if burn_ticks is not None and s["ready_ticks"] > burn_ticks:
                    self._burn(s, events)
            elif s["state"] == "cooking":
                s["cook_ticks_left"] = max(0, s["cook_ticks_left"] - 1)
                if s["cook_ticks_left"] == 0:
                    s["state"] = "ready"
                    s["ready_ticks"] = 0
                    d = s["dish"]
                    events.append(("dish_ready", {"stove_id": s["id"], "order_id": d["order_id"],
                                                  "dish_id": d["dish_id"]}))

    def _burn(self, s, events):
        """Món cháy: bỏ món (nguyên liệu đã dùng mất), bếp rảnh ngay; thử giữ lại ngay nguyên liệu cho đơn từ kho
        khả dụng: đủ -> reserved (giữ order_tick), thiếu -> unfulfillable (khách chờ tới hết kiên nhẫn)."""
        d = s["dish"]
        s.update(state="idle", dish=None, cook_ticks_left=0, ready_ticks=0)
        c = next(x for x in self.customers if x["id"] == d["order_id"])
        ids = self.reserve_for(c["dish_id"])
        if ids is not None:
            c.update(order_status="reserved", reserved=ids, base_price=None)
        else:
            c.update(order_status="unfulfillable", reserved=[], base_price=None)
        events.append(("dish_burnt", {"stove_id": s["id"], "order_id": d["order_id"], "dish_id": d["dish_id"],
                                      "order_status": c["order_status"]}))

    def _tick_eating(self):
        for c in self.customers:
            if c["state"] == "eating":
                c["eat_ticks_left"] = max(0, c["eat_ticks_left"] - 1)

    # --- Lát 4 (TV3): interact -------------------------------------------------------
    def _interact(self, events):
        """Chọn đúng MỘT đối tượng trong bán kính theo (khoảng cách, bếp trước bàn, id).
        Đối tượng được chọn không tương tác được thì bỏ lượt (không thử đối tượng khác)."""
        r = self.t["interact_radius"]
        cands = []
        for order, kind, coll in ((0, "stove", self.stoves), (1, "table", self.tables)):
            for obj in coll:
                d = math.dist(self.pos, obj["pos"])
                if d <= r:
                    cands.append((d, order, id_key(obj["id"]), kind, obj))
        if not cands:
            return
        _, _, _, kind, obj = min(cands, key=lambda c: c[:3])
        if kind == "stove":
            self._interact_stove(obj, events)
        else:
            self._interact_table(obj, events)

    def _interact_stove(self, s, events):
        if s["state"] == "idle":
            c = self._oldest_reserved_order()
            if c is None:
                return
            dish_id = c["dish_id"]
            dish = self.menu[dish_id]
            held = set(c["reserved"])
            used = [it for it in self.stock if it["id"] in held]  # tiêu đúng các id đang giữ
            self.stock = [it for it in self.stock if it["id"] not in held]
            used.sort(key=lambda it: (it["kind"], id_key(it["id"])))
            items = [self.fresh.out(it) for it in used]
            base_price = self.fresh.locked_price(dish["price"], used)  # v1.2: giá theo độ tươi
            c["order_status"] = "assigned"
            c["reserved"] = []
            c["base_price"] = base_price
            s["state"] = "cooking"
            s["dish"] = {"order_id": c["id"], "dish_id": dish_id, "base_price": base_price}
            s["cook_ticks_left"] = to_ticks(dish["cook_s"])
            s["ready_ticks"] = 0
            events.append(("cook_started", {"stove_id": s["id"], "order_id": c["id"], "dish_id": dish_id,
                                            "items": items, "base_price": base_price}))
        elif s["state"] == "ready" and self.hand is None:  # carry_limit = 1
            d = s["dish"]
            self.hand = d
            s.update(state="idle", dish=None, cook_ticks_left=0, ready_ticks=0)
            events.append(("dish_picked", {"stove_id": s["id"], "order_id": d["order_id"], "dish_id": d["dish_id"]}))
        # cooking, hoặc ready mà tay đã cầm món: bỏ lượt

    def _oldest_reserved_order(self):
        """Đơn reserved cũ nhất theo (order_tick, id bàn)."""
        orders = [c for c in self.customers if c["order_status"] == "reserved"]
        if not orders:
            return None
        return min(orders, key=lambda c: (c["order_tick"], id_key(c["table_id"])))

    def _interact_table(self, tb, events):
        """Bàn nhận đúng order_id trên tay -> khách ăn (timer đầy), chốt boa theo kiên nhẫn còn lại sau bước 1."""
        c = next((x for x in self.customers if x["table_id"] == tb["id"]), None)
        if c is None or self.hand is None or self.hand["order_id"] != c["id"] or c["state"] != "waiting":
            return  # bàn được chọn nhưng không phục vụ được -> bỏ lượt
        t = self.t
        d = self.hand
        base_price = d["base_price"]
        left = c["patience_ticks_left"]
        ok = left / self.patience_max_ticks >= t["tip_min_patience_ratio"]
        tip = math.floor(base_price * t["tip_rate"]) if ok else 0
        c.update(state="eating", order_status="served", eat_ticks_left=to_ticks(t["eat_s"]),
                 base_price=base_price, tip=tip)
        self.hand = None
        events.append(("served", {"order_id": c["id"], "table_id": tb["id"], "dish_id": d["dish_id"],
                                  "patience_ticks_left": left, "base_price": base_price, "tip": tip}))

    # --- Lát 4 (TV3): trả tiền -------------------------------------------------------
    def _pay(self, c, reason, events):
        """Thu base_price + tip; boa dương cộng tip_reputation; khách rời bàn ngay (remove_customer)."""
        base_price, tip = c["base_price"], c["tip"]
        amount = base_price + tip
        self.money += amount
        self.earned += amount
        self.shift_earned += amount
        if tip > 0:
            self.add_reputation(self.t["tip_reputation"])
        self.remove_customer(c)
        events.append(("paid", {"order_id": c["id"], "table_id": c["table_id"], "base_price": base_price,
                                "tip": tip, "amount": amount, "reason": reason}))

    # --- đi lại ---------------------------------------------------------------------
    def _move(self, inp):
        speed = self.t["walk_speed"]
        mx, mz = inp.move
        self.vel = ramp_velocity(self, (mx * speed, mz * speed), int(self.t.get("ramp_max_ticks", 6)))
        b = self.t["bounds"]
        for i, axis in enumerate(("x", "z")):
            self.pos[i] += self.vel[i] / TICK
            lo, hi = b[axis]
            if self.pos[i] <= lo:
                self.pos[i], self.vel[i] = lo, max(0.0, self.vel[i])
            elif self.pos[i] >= hi:
                self.pos[i], self.vel[i] = hi, min(0.0, self.vel[i])
