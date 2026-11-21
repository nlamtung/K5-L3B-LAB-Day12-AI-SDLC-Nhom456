"""Độ tươi cá thể (TICKET-03, Test Contract v1.2).

Biểu diễn chính xác: mỗi điểm tươi = 240 đơn vị nguyên (UNITS). Với preset, giỏ hao 0.5/s = 2 đơn vị/tick,
kho quán hao 0.25/s = 1 đơn vị/tick, ngưỡng ươn 30 = 7.200 đơn vị -> so ngưỡng và floor giá không lệch do số thực.
Giá trị fresh đọc vào không rơi đúng lưới đơn vị thì giữ dạng Fraction (vẫn chính xác, chỉ chậm hơn).

Cá thể trong sim: {"id", "kind", "u"} (u = đơn vị tươi). Ra JSONL / file kho: {"id", "kind", "fresh"}.
"""

import math
from fractions import Fraction

from .ids import id_key, sort_by_id

UNITS = 240  # đơn vị mỗi điểm tươi
PRESET = {"initial": 100, "gather_decay_per_s": 0.5, "quan_decay_per_s": 0.25, "spoiled_below": 30}


def _exact(v):
    """Số JSON -> Fraction chính xác theo cách viết thập phân (97.5 -> 195/2)."""
    return Fraction(str(v)) if isinstance(v, float) else Fraction(v)


def _snap(x: Fraction):
    """Về số nguyên nếu đúng lưới (hoặc lệch < 1e-6 đơn vị do float đọc lại từ file của chính mình)."""
    r = round(x)
    if abs(x - r) < Fraction(1, 10**6):
        return int(r)
    return x


class Freshness:
    def __init__(self, tuning):
        f = tuning.get("freshness", PRESET)
        hz = tuning.get("tick_hz", 60)
        self.initial = self.units(f["initial"])
        self.threshold = self.units(f["spoiled_below"])
        self.gather_decay = _snap(_exact(f["gather_decay_per_s"]) * UNITS / hz)
        self.quan_decay = _snap(_exact(f["quan_decay_per_s"]) * UNITS / hz)

    # --- chuyển đổi -----------------------------------------------------------------
    @staticmethod
    def units(fresh):
        return _snap(_exact(fresh) * UNITS)

    @staticmethod
    def value(u) -> float:
        return u / UNITS if isinstance(u, int) else float(Fraction(u) / UNITS)

    def item(self, iid, kind, fresh=None) -> dict:
        return {"id": iid, "kind": kind, "u": self.initial if fresh is None else self.units(fresh)}

    def load(self, it) -> dict:
        """Cá thể từ scenario/file ({id,kind,fresh}) hoặc bản trong bộ nhớ ({id,kind,u}) -> bản sim (copy)."""
        if "u" in it:
            return {"id": it["id"], "kind": it["kind"], "u": it["u"]}
        return self.item(it["id"], it["kind"], it["fresh"])

    def out(self, it) -> dict:
        return {"id": it["id"], "kind": it["kind"], "fresh": self.value(it["u"])}

    def out_list(self, items, by_id=True) -> list:
        return [self.out(it) for it in (sort_by_id(items) if by_id else items)]

    # --- luật -------------------------------------------------------------------------
    def spoiled(self, it) -> bool:
        return it["u"] < self.threshold

    def decay(self, items, per_tick, location) -> list:
        """Hao một tick cho mọi cá thể (kẹp đáy 0). Trả event spoiled (theo id) cho cá thể vừa đi từ ≥ ngưỡng xuống
        < ngưỡng — đúng một lần mỗi cá thể."""
        events = []
        for it in sort_by_id(items):
            was_ok = it["u"] >= self.threshold
            it["u"] = max(0, it["u"] - per_tick)
            if was_ok and it["u"] < self.threshold:
                events.append(("spoiled", {"item_id": it["id"], "kind": it["kind"], "location": location}))
        return events

    @staticmethod
    def locked_price(price, items) -> int:
        """base_price = floor(giá niêm yết × trung bình fresh / 100), tính chính xác trên đơn vị."""
        total = sum((Fraction(it["u"]) for it in items), Fraction(0))
        return math.floor(Fraction(price) * total / (len(items) * UNITS * 100))

    @staticmethod
    def freshest(items, n):
        """n cá thể tươi nhất, hòa theo id (id nhỏ trước)."""
        return sorted(items, key=lambda it: (-Fraction(it["u"]), id_key(it["id"])))[:n]
