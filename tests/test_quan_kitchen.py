"""Lát 4 — bếp ở quán: chọn đối tượng interact, nấu, chín, bưng (PRD-0 mục F, Quán).

Chạy qua Session (cùng lớp sim với headless). Khách dựng sẵn khai `reserved` tường minh để không phụ thuộc lát 3.
"""

import unittest

from chonoi.contract import load_contract
from chonoi.inputs import InputState
from chonoi.runner import Session

from helpers import ROOT, Workdir, events, read_jsonl, write_json

TUNING = load_contract()["tuning"]
STOVE = TUNING["quan"]["stoves"][0]["pos"]  # B1


def idle():
    return InputState((0.0, 0.0), {}, set())


def press():
    return InputState((0.0, 0.0), {"interact": True}, {"interact"})


def lau_customer(**kw):
    c = {"id": "C1", "table_id": "T1", "dish_id": "lau_ca_linh_dien_dien", "order_tick": 0,
         "state": "waiting", "patience_ticks_left": 3600, "order_status": "reserved",
         "reserved": {"ca_linh": 3, "bong_dien_dien": 1}}
    c.update(kw)
    return c


def session(**scn):
    base = {"player": {"pos": list(STOVE)}, "random_customers": False,
            "stock": {"ca_linh": 3, "bong_dien_dien": 1, "ca_loc": 1},
            "customers": [lau_customer()]}
    base.update(scn)
    return Session("quan", TUNING, base, 1)


def names(rows):
    return [r["name"] for r in rows]


class Kitchen(unittest.TestCase):
    def test_cook_started_consumes_reserved_and_locks_price(self):
        s = session()
        rows = s.step(press())
        ev = [r for r in rows if r["name"] == "cook_started"]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["tick"], 1)
        self.assertEqual(ev[0]["data"], {"stove_id": "B1", "order_id": "C1", "dish_id": "lau_ca_linh_dien_dien",
                                         "items": ["bong_dien_dien", "ca_linh", "ca_linh", "ca_linh"],
                                         "base_price": TUNING["menu"]["lau_ca_linh_dien_dien"]["price"]})
        snap = s.snapshot()
        self.assertEqual(snap["stock"], {"ca_loc": 1}, "chỉ tiêu đúng phần giữ chỗ")
        b1 = snap["stoves"][0]
        self.assertEqual(b1["state"], "cooking")
        self.assertEqual(b1["cook_ticks_left"], TUNING["menu"]["lau_ca_linh_dien_dien"]["cook_s"] * 60)
        c = snap["customers"][0]
        self.assertEqual((c["order_status"], c["reserved"]), ("assigned", {}))

    def test_dish_ready_on_exact_tick_then_ready_ticks_grow(self):
        s = session()
        s.step(press())  # nấu ở bước 0, cook_ticks_left = L
        L = TUNING["menu"]["lau_ca_linh_dien_dien"]["cook_s"] * 60
        ready_at = None
        for _ in range(L + 5):
            for r in s.step(idle()):
                if r["name"] == "dish_ready":
                    ready_at = r["tick"]
                    self.assertEqual(r["data"], {"stove_id": "B1", "order_id": "C1",
                                                 "dish_id": "lau_ca_linh_dien_dien"})
        self.assertEqual(ready_at, 1 + L)
        b1 = s.snapshot()["stoves"][0]
        self.assertEqual(b1["state"], "ready")
        self.assertEqual(b1["cook_ticks_left"], 0)
        self.assertEqual(b1["ready_ticks"], s.tick - ready_at, "tuổi món chỉ tăng từ bước SAU khi chín")

    def test_pick_up_ready_dish(self):
        dish = {"order_id": "C1", "dish_id": "lau_ca_linh_dien_dien", "base_price": 120}
        s = session(stoves=[{"id": "B1", "state": "ready", "dish": dish, "ready_ticks": 3}],
                    customers=[lau_customer(order_status="assigned", reserved={})])
        rows = s.step(press())
        self.assertEqual(names(rows), ["dish_picked"])
        self.assertEqual(rows[0]["data"], {"stove_id": "B1", "order_id": "C1", "dish_id": "lau_ca_linh_dien_dien"})
        snap = s.snapshot()
        self.assertEqual(snap["hand"], dish)
        self.assertEqual(snap["stoves"][0]["state"], "idle")
        self.assertIsNone(snap["stoves"][0]["dish"])

    def test_full_hand_cannot_pick(self):
        # Trạng thái nội bộ, KHÔNG phải fixture hợp lệ theo mục D (Phase 1 chỉ 1 bàn nên không thể có
        # hai đơn cùng lúc; scenario.py của lát 3 sẽ từ chối C9). Dựng thẳng qua Session để kiểm nhánh phòng thủ.
        dish = {"order_id": "C1", "dish_id": "lau_ca_linh_dien_dien", "base_price": 120}
        other = {"order_id": "C9", "dish_id": "goi_bong_sung", "base_price": 40}
        s = session(stoves=[{"id": "B1", "state": "ready", "dish": dish}], hand=other,
                    customers=[lau_customer(order_status="assigned", reserved={})])
        self.assertEqual(s.step(press()), [])
        self.assertEqual(s.snapshot()["stoves"][0]["state"], "ready")

    def test_cooking_stove_ignores_interact(self):
        s = session()
        s.step(press())
        left = s.snapshot()["stoves"][0]["cook_ticks_left"]
        s.step(InputState((0.0, 0.0), {"interact": False}, set()))
        self.assertEqual(names(s.step(press())), [])
        self.assertEqual(s.snapshot()["stoves"][0]["cook_ticks_left"], left - 2)

    def test_idle_stove_without_reserved_order_does_nothing(self):
        s = session(customers=[])
        self.assertEqual(s.step(press()), [])
        self.assertEqual(s.snapshot()["stoves"][0]["state"], "idle")

    def test_stove_wins_tie_with_table(self):
        # bàn và bếp cách người chơi đúng bằng nhau -> bếp trước
        s = session(player={"pos": [2, 7]}, tables=[{"id": "T1", "pos": [2, 6]}])
        self.assertEqual(names(s.step(press())), ["cook_started"])

    def test_closer_table_blocks_stove(self):
        # bàn gần hơn được chọn; bàn chưa phục vụ được -> bỏ lượt, không thử bếp
        s = session(player={"pos": [2, 7]}, tables=[{"id": "T1", "pos": [2, 6.5]}])
        self.assertEqual(s.step(press()), [])
        self.assertEqual(s.snapshot()["stoves"][0]["state"], "idle")

    def test_out_of_radius_does_nothing(self):
        r = TUNING["quan"]["interact_radius"]
        # TICKET-02 thêm B2 [5,8] ở phía +x của B1 (cách 3 m): đứng phía -x để chỉ B1 nằm gần ngưỡng bán kính.
        s = session(player={"pos": [STOVE[0] - r - 0.01, STOVE[1]]})
        self.assertEqual(s.step(press()), [])
        s = session(player={"pos": [STOVE[0] - r, STOVE[1]]})  # đúng mép vẫn tính
        self.assertEqual(names(s.step(press())), ["cook_started"])

    def test_cook_order_of_customer_spawned_by_lat3(self):
        # khách tự sinh (lát 3) ở first_customer_tick -> bếp (lát 4) nấu được đơn đó, tiêu đúng phần giữ
        s = session(customers=[], random_customers=True, stock={"ca_loc": 1})
        arrived = None
        while arrived is None:
            for r in s.step(idle()):
                if r["name"] == "customer_arrived":
                    arrived = r
        self.assertEqual(arrived["tick"], TUNING["quan"]["first_customer_tick"])
        self.assertEqual(arrived["data"]["dish_id"], "ca_loc_nuong_trui", "chỉ món này đủ nguyên liệu")
        rows = s.step(press())
        self.assertEqual(names(rows), ["cook_started"])
        self.assertEqual(rows[0]["data"]["order_id"], arrived["data"]["order_id"])
        self.assertEqual(rows[0]["data"]["items"], ["ca_loc"])
        self.assertEqual(s.snapshot()["stock"], {})


class KitchenHeadless(unittest.TestCase):
    """Cùng luồng qua headless (python -m chonoi.headless) để chắc JSONL đúng thứ tự."""

    def test_cook_and_pick_jsonl(self):
        import subprocess
        import sys
        with Workdir() as w:
            scn = write_json(w.path("s.json"), {"quan": {
                "player": {"pos": list(STOVE)}, "random_customers": False,
                "stock": {"bong_sung": 2}, "customers": [{
                    "id": "C1", "table_id": "T1", "dish_id": "goi_bong_sung",
                    "reserved": {"bong_sung": 2}}]}})
            L = TUNING["menu"]["goi_bong_sung"]["cook_s"] * 60
            inp = write_json(w.path("i.json"), {"frames": [
                {"tick": 0, "interact": True}, {"tick": 1, "interact": False},
                {"tick": L + 2, "interact": True}]})
            out = w.path("o.jsonl")
            p = subprocess.run([sys.executable, "-m", "chonoi.headless", "--mode", "quan", "--seed", "1",
                                "--scenario", scn, "--inputs", inp, "--ticks", str(L + 5), "--out", out],
                               cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            rows = read_jsonl(out)
            ev = [(r["tick"], r["name"]) for r in events(rows) if r["name"] in ("cook_started", "dish_ready", "dish_picked")]
            self.assertEqual(ev, [(1, "cook_started"), (1 + L, "dish_ready"), (L + 3, "dish_picked")])
            self.assertEqual(rows[-2]["hand"], {"order_id": "C1", "dish_id": "goi_bong_sung", "base_price": 40})


if __name__ == "__main__":
    unittest.main()
