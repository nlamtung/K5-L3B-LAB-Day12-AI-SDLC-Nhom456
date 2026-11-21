"""Lát 4 — phục vụ, trả tiền, boa, uy tín, đóng ca (PRD-0 mục F, Quán).

Khách dựng sẵn khai đủ trường. Kiên nhẫn (lát 3) giảm 1 ở bước 1, TRƯỚC interact, nên lúc served
patience_ticks_left = giá trị fixture − 1 và boa xét trên giá trị đó ("sau bước 1", mục F).
"""

import math
import subprocess
import sys
import unittest

from chonoi.contract import load_contract
from chonoi.inputs import InputState
from chonoi.runner import Session

from helpers import ROOT, Workdir, events, items, read_jsonl, write_json

from fractions import Fraction

# TICKET-03 (v1.2) [THAY THẾ]: kho là mảng cá thể, reserved là mảng id; giá chốt theo độ tươi khi bắt đầu nấu
# (hàng 100 hao 1 tick ở quán trước tương tác -> gỏi 40 chốt 39). Boa tính trên giá đã chốt.

TUNING = load_contract()["tuning"]
Q = TUNING["quan"]
MENU = TUNING["menu"]
TABLE = Q["tables"][0]["pos"]  # T1
STOVE = Q["stoves"][0]["pos"]  # B1
PATIENCE = Q["patience_s"] * 60
EAT = Q["eat_s"] * 60
LAU = {"order_id": "C1", "dish_id": "lau_ca_linh_dien_dien", "base_price": MENU["lau_ca_linh_dien_dien"]["price"]}


def idle():
    return InputState((0.0, 0.0), {}, set())


def press():
    return InputState((0.0, 0.0), {"interact": True}, {"interact"})


def assigned(**kw):
    c = {"id": "C1", "table_id": "T1", "dish_id": "lau_ca_linh_dien_dien", "order_tick": 0, "state": "waiting",
         "patience_ticks_left": PATIENCE, "order_status": "assigned", "reserved": []}
    c.update(kw)
    return c


def eating(**kw):
    c = assigned(state="eating", order_status="served", eat_ticks_left=EAT,
                 base_price=LAU["base_price"], tip=math.floor(LAU["base_price"] * Q["tip_rate"]))
    c.update(kw)
    return c


def session(**scn):
    base = {"player": {"pos": list(TABLE)}, "random_customers": False, "hand": dict(LAU),
            "customers": [assigned()]}
    base.update(scn)
    return Session("quan", TUNING, base, 1)


def names(rows):
    return [r["name"] for r in rows]


class Serve(unittest.TestCase):
    def test_served_with_tip_when_patient(self):
        s = session()
        rows = s.step(press())
        self.assertEqual(names(rows), ["served"])
        tip = math.floor(LAU["base_price"] * Q["tip_rate"])
        self.assertEqual(rows[0]["data"], {"order_id": "C1", "table_id": "T1", "dish_id": "lau_ca_linh_dien_dien",
                                           "patience_ticks_left": PATIENCE - 1, "base_price": LAU["base_price"],
                                           "tip": tip})
        snap = s.snapshot()
        self.assertIsNone(snap["hand"])
        c = snap["customers"][0]
        self.assertEqual((c["state"], c["order_status"], c["eat_ticks_left"], c["tip"]),
                         ("eating", "served", EAT, tip))

    def test_tip_threshold(self):
        # fixture = ngưỡng + 1 -> sau bước 1 còn đúng ngưỡng -> vẫn được boa; fixture = ngưỡng -> dưới ngưỡng
        edge = math.ceil(PATIENCE * Q["tip_min_patience_ratio"])
        s = session(customers=[assigned(patience_ticks_left=edge + 1)])
        d = s.step(press())[0]["data"]
        self.assertEqual(d["patience_ticks_left"], edge)
        self.assertGreater(d["tip"], 0, "đúng ngưỡng vẫn được boa")
        s = session(customers=[assigned(patience_ticks_left=edge)])
        self.assertEqual(s.step(press())[0]["data"]["tip"], 0)

    def test_serve_at_zero_patience_still_valid(self):
        s = session(customers=[assigned(patience_ticks_left=0)])
        self.assertEqual(names(s.step(press())), ["served"])

    def test_wrong_order_or_empty_hand_skips(self):
        wrong = {"order_id": "C9", "dish_id": "goi_bong_sung", "base_price": 40}
        self.assertEqual(session(hand=wrong).step(press()), [])
        self.assertEqual(session(hand=None).step(press()), [])

    def test_empty_table_skips(self):
        self.assertEqual(session(customers=[]).step(press()), [])


class Pay(unittest.TestCase):
    def test_paid_after_eating_and_reputation_up(self):
        s = session()
        s.step(press())  # served ở tick 1
        paid = None
        for _ in range(EAT + 2):
            for r in s.step(idle()):
                if r["name"] == "paid":
                    paid = r
        self.assertIsNotNone(paid)
        self.assertEqual(paid["tick"], 1 + EAT)
        tip = math.floor(LAU["base_price"] * Q["tip_rate"])
        self.assertEqual(paid["data"], {"order_id": "C1", "table_id": "T1", "base_price": LAU["base_price"],
                                        "tip": tip, "amount": LAU["base_price"] + tip,
                                        "reason": "finished_eating"})
        snap = s.snapshot()
        self.assertEqual((snap["money"], snap["earned"]), (LAU["base_price"] + tip,) * 2)
        self.assertAlmostEqual(snap["reputation"], Q["reputation_initial"] + Q["tip_reputation"])
        self.assertEqual(snap["customers"], [])
        self.assertIsNone(snap["tables"][0]["customer_id"])
        self.assertEqual(snap["score"], snap["earned"] + 100 * math.floor(snap["reputation"]))

    def test_no_tip_keeps_reputation(self):
        s = session(customers=[eating(tip=0, eat_ticks_left=1)], hand=None)
        rows = s.step(idle())
        self.assertEqual(names(rows), ["paid"])
        self.assertEqual(rows[0]["data"]["amount"], LAU["base_price"])
        self.assertEqual(s.snapshot()["reputation"], Q["reputation_initial"])

    def test_reputation_clamped_at_max(self):
        s = session(customers=[eating(eat_ticks_left=1)], hand=None, reputation=Q["reputation_max"] - 0.1)
        s.step(idle())
        self.assertEqual(s.snapshot()["reputation"], Q["reputation_max"])


class Closing(unittest.TestCase):
    def test_eating_customer_pays_on_closing(self):
        s = session(customers=[eating()], hand=None, time_left_ticks=1)
        rows = s.step(idle())
        self.assertEqual(names(rows), ["paid", "quan_end"])
        self.assertEqual(rows[0]["data"]["reason"], "closing")
        amount = rows[0]["data"]["amount"]
        self.assertEqual(rows[1]["data"], {"reason": "time", "money": amount, "earned": amount,
                                           "shift_earned": amount,
                                           "reputation": Q["reputation_initial"] + Q["tip_reputation"]})
        self.assertTrue(s.done)
        self.assertEqual(s.end_row()["reason"], "time")

    def test_served_on_last_tick_pays_on_closing(self):
        s = session(time_left_ticks=1)
        self.assertEqual(names(s.step(press())), ["served", "paid", "quan_end"])

    def test_waiting_customer_leaves_without_penalty_and_dish_dropped(self):
        s = session(customers=[assigned()], hand=None, time_left_ticks=1,
                    stoves=[{"id": "B1", "state": "ready", "dish": dict(LAU)}])
        rows = s.step(idle())
        self.assertEqual(names(rows), ["customer_left", "quan_end"])
        self.assertEqual(rows[0]["data"], {"order_id": "C1", "table_id": "T1", "reason": "closing",
                                           "reputation": Q["reputation_initial"]})
        snap = s.snapshot()
        self.assertEqual(snap["stoves"][0]["state"], "idle")
        self.assertEqual(snap["customers"], [])

    def test_reserved_order_released_keeps_stock(self):
        c = assigned(order_status="reserved", reserved=["I1"], dish_id="ca_loc_nuong_trui")
        s = session(customers=[c], hand=None, time_left_ticks=1, stock=items("ca_loc"))
        s.step(idle())
        self.assertEqual([x["id"] for x in s.snapshot()["stock"]], ["I1"], "nhả phần giữ, không mất nguyên liệu")


class FullFlowHeadless(unittest.TestCase):
    """nấu -> bưng -> phục vụ -> trả tiền, chạy qua headless."""

    def test_cook_pick_serve_pay(self):
        with Workdir() as w:
            scn = write_json(w.path("s.json"), {"quan": {
                "player": {"pos": list(STOVE)}, "random_customers": False,
                "stock": items("bong_sung", "bong_sung"),
                "customers": [{"id": "C1", "table_id": "T1", "dish_id": "goi_bong_sung",
                               "reserved": ["I1", "I2"]}]}})
            cook = MENU["goi_bong_sung"]["cook_s"] * 60
            # đi từ bếp (2,8) tới bàn (9,2): dx=7, dz=-6 -> đi theo hướng chuẩn hóa
            dist = math.dist(STOVE, TABLE)
            walk = math.ceil(dist / Q["walk_speed"] * 60) + Q["ramp_max_ticks"] + 5
            t_pick = cook + 2
            t_go = t_pick + 2
            t_stop = t_go + walk
            mv = [(TABLE[0] - STOVE[0]) / dist, (TABLE[1] - STOVE[1]) / dist]
            inp = write_json(w.path("i.json"), {"frames": [
                {"tick": 0, "interact": True}, {"tick": 1, "interact": False},
                {"tick": t_pick, "interact": True}, {"tick": t_pick + 1, "interact": False},
                {"tick": t_go, "move": mv}, {"tick": t_stop, "move": [0, 0]},
                {"tick": t_stop + 1, "interact": True}]})
            out = w.path("o.jsonl")
            ticks = t_stop + 1 + EAT + 10
            p = subprocess.run([sys.executable, "-m", "chonoi.headless", "--mode", "quan", "--seed", "1",
                                "--scenario", scn, "--inputs", inp, "--ticks", str(ticks), "--out", out],
                               cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            rows = read_jsonl(out)
            seq = [r["name"] for r in events(rows)]
            self.assertEqual(seq, ["cook_started", "dish_ready", "dish_picked", "served", "paid"])
            fresh = 100 - Fraction(str(TUNING["freshness"]["quan_decay_per_s"])) / 60  # hao 1 tick trước khi nấu
            price = math.floor(MENU["goi_bong_sung"]["price"] * fresh / 100)
            self.assertEqual(events(rows, "cook_started")[0]["data"]["base_price"], price)
            tip = math.floor(price * Fraction(str(Q["tip_rate"])))
            end = rows[-1]
            self.assertEqual((end["money"], end["earned"]), (price + tip, price + tip))
            self.assertEqual(end["score"], price + tip + 100 * math.floor(end["reputation"]))
            self.assertEqual(end["reason"], "tick_limit")


if __name__ == "__main__":
    unittest.main()
