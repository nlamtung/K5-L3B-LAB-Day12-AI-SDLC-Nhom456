"""`--mode day` — vòng ngày gather → quan → shop (TICKET-02 mục 2, Test Contract v1.1 mục 4) — TV3.

Một Ngày: day_start → day_plan → phase_start(gather) → … gather_end → phase_start(quan) (cùng tick, kể cả ngất)
→ … quan_end → phase_start(shop) (cùng tick) → … shop_end → Ngày kế (cùng tick) hoặc kết thúc `days_complete`.

- Pha mới chỉ chạy gameplay từ bước sau. Snapshot đổi pha ghi pha mới với phase_tick 0; event kết thúc mang pha cũ.
- Tiền, earned, uy tín và cấp đã mua giữ qua Ngày. Giỏ làm mới, kho dư bị bỏ sau Shop.
- Kho bàn giao trong bộ nhớ, cùng schema với file kho (`gather_end.data.inventory.items`).
- Shop: xử lý một `buy` TRƯỚC cạnh `shop_done` (kể cả bước cuối); tự đóng sau `shop.max_ticks` bước hoạt động.
  Mua cấp kế tiếp, đủ đúng giá vẫn mua được, trừ money (giữ earned/điểm); thiếu tiền / đã tối đa / lệnh lạ → buy_failed.
  Cấp vừa mua có trong `upgrades` ngay, chỉ sao sang `active_upgrades` khi dựng Ngày mới (oxy, Máu áp từ Ngày kế).
- Pause: dùng chung `PauseGate` với gather/quan; khi pause mọi timer (kể cả Shop) đứng yên.
- Mọi số liệu đọc từ tuning (`day_plan`, `shop`); không hard-code.

v1.2 (TICKET-03): bàn giao mảng cá thể {id, kind, fresh} trong cùng tick chuyển pha (không hao thêm, ca quán chạy
từ bước sau). Ngày đầu giữ nguyên id trong mẫu gather.hold; các Ngày kế cấp id mới theo thứ tự mảng với kind/fresh
ban đầu (id I… nối tiếp xuyên pha và Ngày). Hàng thô ở Shop không hao; kho dư bị bỏ sau Shop.

Quán trong day chỉ nhận món của kế hoạch Ngày (`QuanSim(plan_dishes=...)`). `GatherSim` nhận thêm `day=` nếu
lớp hỗ trợ (bố trí thủy quái theo Ngày, M2 từ Ngày 3).
"""

import copy
import inspect

from ..errors import BadInput
from ..fresh import Freshness
from ..ids import IdAllocator
from ..rng import Streams
from ..runner import PauseGate, score_of
from .gather import GatherSim
from .quan import QuanSim


def _accepts(cls, name):
    return name in inspect.signature(cls.__init__).parameters


def _level(entries, level):
    return next((e for e in entries if e["level"] == level), None)


def plan_ingredients(dishes, menu):
    """Tổng nguyên liệu cần = Σ công thức × số suất, sắp theo kind (TICKET-02 mục 2, v1.1 mục 4.3)."""
    total = {}
    for dish_id, servings in dishes.items():
        for kind, n in menu[dish_id]["recipe"].items():
            total[kind] = total.get(kind, 0) + n * servings
    return {k: total[k] for k in sorted(total) if total[k] > 0}


class DaySession:
    mode = "day"

    def __init__(self, tuning, scenario, seed, days=1):
        if "day_plan" not in tuning or "shop" not in tuning:
            raise BadInput("--mode day cần tuning.day_plan và tuning.shop (contract v1.1)")
        if isinstance(days, bool) or not isinstance(days, int) or not (1 <= days <= len(tuning["day_plan"])):
            raise BadInput(f"--days phải là số nguyên trong [1, {len(tuning['day_plan'])}]")
        self.tuning = tuning
        self.days = days
        scenario = scenario or {}
        self.tpl_gather = scenario.get("gather", {})
        self.tpl_quan = scenario.get("quan", {})
        d = scenario.get("day", {})
        self.money = d.get("money", 0)
        self.earned = d.get("earned", 0)
        self.reputation = d.get("reputation", tuning["quan"]["reputation_initial"])
        self.upgrades = {k: v for k, v in d.get("upgrades", {}).items() if v > 0}
        self.active_upgrades = {}
        self.plan = self._build_plan(d.get("day_plan", []))
        self.streams = Streams(seed)
        self.ids = IdAllocator()  # id khách/cá nối tiếp xuyên Ngày trong cùng lượt
        self.gate = PauseGate()
        self.fresh = Freshness(tuning)
        self.tick = 0
        self.sim_tick = 0
        self.phase_tick = 0
        self.day = 0
        self.days_completed = 0
        self.done = False
        self.reason = None
        self.phase = None
        self.sim = None
        self.shop_left = 0
        self.shop_stock = {}
        self.initial_rows = self._rows(self._start_day())

    # --- kế hoạch ------------------------------------------------------------------------
    def _build_plan(self, overrides):
        plan = {e["day"]: {"dishes": dict(e["dishes"]), "ingredients": dict(e["ingredients"])}
                for e in self.tuning["day_plan"]}
        if overrides:
            for e in overrides:
                plan[e["day"]] = {"dishes": dict(e["dishes"]),
                                  "ingredients": plan_ingredients(e["dishes"], self.tuning["menu"])}
        return plan

    # --- dựng pha ------------------------------------------------------------------------
    def _start_day(self):
        self.day += 1
        self.active_upgrades = dict(self.upgrades)
        entry = self.plan[self.day]
        events = [(self.day, "gather", "day_start", {}),
                  (self.day, "gather", "day_plan", {"dishes": dict(entry["dishes"]),
                                                    "ingredients": dict(entry["ingredients"])})]
        self._build_gather()
        events.append((self.day, "gather", "phase_start", {}))
        return events

    def _day_tuning(self):
        """Tuning của Ngày: áp cấp oxygen/hp đang hiệu lực (Máu, oxy hồi đầy theo cấp đó)."""
        t = copy.deepcopy(self.tuning)
        ups = self.tuning["shop"]["upgrades"]
        lv = self.active_upgrades.get("oxygen", 0)
        if lv:
            t["gather"]["oxygen_max_s"] = _level(ups["oxygen"], lv)["oxygen_max_s"]
        lv = self.active_upgrades.get("hp", 0)
        if lv:
            t["gather"]["hp_max"] = _level(ups["hp"], lv)["hp_max"]
        return t

    def _sync_into(self, sim):
        sim.money, sim.earned, sim.reputation = self.money, self.earned, self.reputation

    def _gather_template(self):
        """Mẫu gather của Ngày: Ngày 1 giữ id trong gather.hold; Ngày kế cấp id mới theo thứ tự mảng (v1.2)."""
        tpl = copy.deepcopy(self.tpl_gather)
        if self.day > 1 and tpl.get("hold"):
            tpl["hold"] = [dict(it, id=self.ids.new("I")) for it in tpl["hold"]]
        return tpl

    def _build_gather(self):
        kw = {"day": self.day} if _accepts(GatherSim, "day") else {}
        self.sim = GatherSim(self._day_tuning(), self._gather_template(), self.streams, self.ids, **kw)
        self._sync_into(self.sim)
        self.phase, self.phase_tick = "gather", 0

    def _build_quan(self, items):
        self.sim = QuanSim(self.tuning, copy.deepcopy(self.tpl_quan), self.streams, self.ids, inventory=list(items),
                           plan_dishes=list(self.plan[self.day]["dishes"]))
        self._sync_into(self.sim)
        self.sim.shift_earned = 0
        self.phase, self.phase_tick = "quan", 0

    def _build_shop(self, leftover):
        self.sim = None
        self.shop_left = self.tuning["shop"]["max_ticks"]
        self.shop_stock = [dict(it) for it in leftover]  # cá thể dư từ ca, không hao ở Shop
        self.phase, self.phase_tick = "shop", 0

    # --- một bước ------------------------------------------------------------------------
    def step(self, inp) -> list:
        run_gameplay, pre = self.gate.filter(inp)
        events = [(self.day, self.phase, name, data) for name, data in pre]
        if run_gameplay:
            self.sim_tick += 1
            self.phase_tick += 1
            events += self._gameplay(inp)
        self.tick += 1
        return self._rows(events)

    def _gameplay(self, inp):
        day, phase = self.day, self.phase
        if phase == "shop":
            return self._shop_step(inp)
        out = self.sim.step(inp)
        events = [(day, phase, name, data) for name, data in out]
        if phase == "quan":
            self.money, self.earned, self.reputation = self.sim.money, self.sim.earned, self.sim.reputation
        if not self.sim.done:
            return events
        if phase == "gather":
            self._build_quan(self.sim.handoff_items())  # bản chính xác, cùng tick, không hao thêm
            events.append((day, "quan", "phase_start", {}))
        else:
            self._build_shop(self.sim.stock)
            events.append((day, "shop", "phase_start", {}))
        return events

    def _shop_step(self, inp):
        self.shop_left = max(0, self.shop_left - 1)
        events = []
        if inp.buy:
            events.append(self._buy(inp.buy))
        if inp.pressed("shop_done"):
            events += self._close_shop("done")
        elif self.shop_left == 0:
            events += self._close_shop("time")
        return events

    def _buy(self, action):
        ups = self.tuning["shop"]["upgrades"]
        if action not in ups:
            return (self.day, "shop", "buy_failed", {"action": action, "reason": "unknown"})
        level = self.upgrades.get(action, 0) + 1
        nxt = _level(ups[action], level)
        if nxt is None:
            return (self.day, "shop", "buy_failed", {"action": action, "reason": "max_level"})
        if self.money < nxt["price"]:
            return (self.day, "shop", "buy_failed", {"action": action, "reason": "funds"})
        self.money -= nxt["price"]
        self.upgrades[action] = level
        return (self.day, "shop", "bought", {"upgrade": action, "level": level, "price": nxt["price"],
                                            "money": self.money})

    def _close_shop(self, reason):
        events = [(self.day, "shop", "shop_end", {"reason": reason})]
        self.days_completed += 1
        if self.days_completed >= self.days:
            self.done, self.reason = True, "days_complete"
            return events
        return events + self._start_day()

    # --- đầu ra --------------------------------------------------------------------------
    def _rows(self, events):
        return [{"type": "event", "tick": self.tick, "phase": phase, "day": day, "name": name, "data": data}
                for day, phase, name, data in events]

    def _state(self):
        if self.done:
            return "finished"
        return "paused" if self.gate.paused else "playing"

    @property
    def paused(self) -> bool:
        return self.gate.paused

    def snapshot(self) -> dict:
        time_left = self.shop_left if self.phase == "shop" else self.sim.time_left_ticks
        s = {"type": "snapshot", "tick": self.tick, "sim_tick": self.sim_tick, "mode": self.mode,
             "phase": self.phase, "phase_tick": self.phase_tick, "state": self._state(),
             "time_left_ticks": time_left, "money": self.money, "earned": self.earned,
             "reputation": self.reputation, "score": score_of(self.tuning, self.earned, self.reputation),
             "day": self.day, "day_plan": copy.deepcopy(self.plan[self.day]),
             "upgrades": dict(self.upgrades), "active_upgrades": dict(self.active_upgrades)}
        if self.phase == "shop":
            s["stock"] = self.fresh.out_list(self.shop_stock)
        else:
            s.update(self.sim.snapshot())
        return s

    def end_row(self) -> dict:
        return {"type": "end", "ticks": self.tick, "sim_tick": self.sim_tick, "mode": self.mode,
                "state": self._state(), "reason": self.reason if self.done else "tick_limit",
                "money": self.money, "earned": self.earned, "reputation": self.reputation,
                "score": score_of(self.tuning, self.earned, self.reputation),
                "days_completed": self.days_completed}
