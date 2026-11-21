"""Bất biến của quán (lát 3 + lát 4) dưới input ngẫu nhiên có seed — bảo vệ luật khi quan.py còn được sửa ở các phase sau.

Một "bot" tất định (random.Random(seed)) chọn bếp/bàn làm đích, đi tới đó, thỉnh thoảng đi lạc, bấm E thất thường.
Sau MỖI bước kiểm toàn bộ snapshot + event. Đọc mọi số liệu từ game.contract.json; chạy được với kho đếm (v1.0/v1.1)
và kho cá thể (v1.2: stock là mảng {id,kind,fresh}, reserved là mảng id).
"""

import math
import random
import unittest
from collections import Counter

from chonoi.contract import load_contract
from chonoi.inputs import InputState
from chonoi.runner import Session

CONTRACT = load_contract()
TUNING = CONTRACT["tuning"]
Q = TUNING["quan"]
MENU = TUNING["menu"]
INSTANCE_STOCK = CONTRACT.get("contract_version") in ("1.2", "1.3")
BURN_ON = Q.get("burn_s") is not None
SEEDS = (1, 7, 42, 2026)


def ticks(seconds):
    return int(round(seconds * 60))


def initial_stock(portions=3):
    """Đủ nấu mỗi món `portions` suất, để bot có việc làm."""
    need = Counter()
    for dish in MENU.values():
        for k, n in dish["recipe"].items():
            need[k] += n * portions
    if not INSTANCE_STOCK:
        return dict(need)
    out, i = [], 0
    for k in sorted(need):
        for _ in range(need[k]):
            i += 1
            out.append({"id": f"I{i}", "kind": k, "fresh": 100})
    return out


def stock_counts(stock):
    if isinstance(stock, dict):
        return Counter(stock)
    return Counter(x["kind"] for x in stock)


def reserved_counts(reserved):
    return Counter(reserved) if isinstance(reserved, dict) else None


class Bot:
    """Người chơi giả tất định: đi tới bếp/bàn ngẫu nhiên, bấm E khi tới gần hoặc ngẫu nhiên."""

    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.spots = [s["pos"] for s in Q["stoves"]] + [t["pos"] for t in Q["tables"]]
        self.target = None
        self.retarget_in = 0
        self.held = False
        self.lazy_left = 0

    def next(self, pos):
        r = self.rng
        if self.lazy_left > 0:  # lơ là đủ lâu để khách hết kiên nhẫn
            self.lazy_left -= 1
            self.held = False
            return InputState((0.0, 0.0), {"interact": False}, set())
        if r.random() < 0.0008:
            self.lazy_left = r.randint(ticks(Q["patience_s"]) // 2, ticks(Q["patience_s"]) + 600)
        if self.retarget_in <= 0 or self.target is None:
            self.target = r.choice(self.spots)
            self.retarget_in = r.randint(60, 400)
        self.retarget_in -= 1
        dx, dz = self.target[0] - pos[0], self.target[1] - pos[1]
        d = math.hypot(dx, dz)
        if r.random() < 0.05:
            move = (r.uniform(-1, 1), r.uniform(-1, 1))      # đi lạc
        elif d > 0.3:
            move = (dx / d, dz / d)
        else:
            move = (0.0, 0.0)
        want = (d <= Q["interact_radius"] and r.random() < 0.3) or r.random() < 0.01
        edge = {"interact"} if want and not self.held else set()
        self.held = want
        return InputState(move, {"interact": want}, edge)


class Checker:
    def __init__(self, tc, sess):
        self.tc = tc
        self.sess = sess
        self.prev_earned = 0
        self.paid_total = 0
        self.cooked = Counter()
        self.seen = Counter()
        self.cook_at = {}      # order_id -> (tick bắt đầu nấu, số tick nấu)
        self.served_at = {}    # order_id -> tick phục vụ
        self.arrived_at = {}   # order_id -> tick khách tới (khách tự sinh)

    def events(self, rows):
        tc = self.tc
        for r in rows:
            tc.assertEqual(r["tick"], self.sess.tick, "event ghi ở tick k+1")
            name, d = r["name"], r["data"]
            t = r["tick"]
            self.seen[name] += 1
            if name == "paid":
                tc.assertEqual(d["amount"], d["base_price"] + d["tip"])
                tc.assertIn(d["tip"], (0, math.floor(d["base_price"] * Q["tip_rate"])))
                tc.assertIn(d["reason"], ("finished_eating", "closing"))
                if d["reason"] == "finished_eating":
                    tc.assertEqual(t - self.served_at[d["order_id"]], ticks(Q["eat_s"]), "ăn đúng eat_s rồi trả")
                else:
                    tc.assertLessEqual(t - self.served_at[d["order_id"]], ticks(Q["eat_s"]))
                self.paid_total += d["amount"]
            elif name == "served":
                tc.assertIn(d["tip"], (0, math.floor(d["base_price"] * Q["tip_rate"])))
                self.served_at[d["order_id"]] = t
            elif name == "customer_arrived":
                self.arrived_at[d["order_id"]] = t
            elif name == "dish_ready":
                start, length = self.cook_at[d["order_id"]]
                tc.assertEqual(t - start, length, "chín đúng cook_s sau khi bắt đầu nấu")
            elif name == "customer_left" and d["reason"] == "patience":
                if d["order_id"] in self.arrived_at:
                    tc.assertEqual(t - self.arrived_at[d["order_id"]], ticks(Q["patience_s"]),
                                   "rời đúng patience_s sau khi tới")
            elif name == "cook_started":
                self.cook_at[d["order_id"]] = (t, ticks(MENU[d["dish_id"]]["cook_s"]))
                self.cooked[d["order_id"]] += 1
                if not BURN_ON:
                    tc.assertEqual(self.cooked[d["order_id"]], 1, "không cháy thì mỗi đơn nấu đúng một lần")
                kinds = [x if isinstance(x, str) else x["kind"] for x in d["items"]]
                tc.assertEqual(sorted(kinds), kinds, "items sắp theo kind")
                recipe = MENU[d["dish_id"]]["recipe"]
                tc.assertEqual(Counter(kinds), Counter(recipe), "tiêu đúng công thức")
                if not INSTANCE_STOCK:
                    tc.assertEqual(d["base_price"], MENU[d["dish_id"]]["price"])
            elif name == "quan_end":
                tc.assertIs(r, rows[-1], "quan_end là event cuối của bước cuối")

    def snapshot(self, s):
        tc = self.tc
        # tiền, điểm, uy tín
        tc.assertEqual(s["money"], s["earned"], "quán độc lập: chưa có khoản chi")
        tc.assertGreaterEqual(s["earned"], self.prev_earned, "earned không giảm")
        tc.assertEqual(s["earned"], self.paid_total, "earned = tổng paid.amount")
        self.prev_earned = s["earned"]
        tc.assertTrue(Q["reputation_min"] - 1e-9 <= s["reputation"] <= Q["reputation_max"] + 1e-9)
        tc.assertEqual(s["score"], s["earned"] + TUNING["score"]["reputation_multiplier"] * math.floor(s["reputation"]))
        # kho và giữ chỗ
        have = stock_counts(s["stock"])
        tc.assertTrue(all(n >= 0 for n in have.values()), f"kho âm: {have}")
        customers = s["customers"]
        held = Counter()
        held_ids = []
        for c in customers:
            rc = reserved_counts(c["reserved"])
            if rc is None:
                held_ids += c["reserved"]
            else:
                held += rc
        if INSTANCE_STOCK:
            ids = {x["id"] for x in s["stock"]}
            tc.assertEqual(len(held_ids), len(set(held_ids)), "một cá thể không giữ cho hai đơn")
            tc.assertTrue(set(held_ids) <= ids, "phần giữ trỏ tới cá thể có trong kho")
        else:
            tc.assertTrue(all(have[k] >= n for k, n in held.items()), f"giữ quá tồn: {held} > {have}")
        # khách, bàn
        tc.assertEqual(len({c["table_id"] for c in customers}), len(customers), "mỗi bàn tối đa một khách")
        by_id = {c["id"]: c for c in customers}
        for tb in s["tables"]:
            owner = tb["customer_id"]
            if owner is not None:
                tc.assertEqual(by_id[owner]["table_id"], tb["id"])
        time_left = s["time_left_ticks"]
        for c in customers:
            tc.assertIn(c["state"], ("waiting", "eating"))
            tc.assertEqual(c["state"] == "eating", c["order_status"] == "served", "eating ⇔ served")
            if c["id"] in self.arrived_at and c["state"] == "waiting":
                tc.assertEqual(c["patience_ticks_left"],
                               ticks(Q["patience_s"]) - (s["tick"] - self.arrived_at[c["id"]]),
                               "kiên nhẫn giảm đúng 1/tick từ bước sau khi tới")
            if c["state"] == "eating":
                tc.assertGreater(c["eat_ticks_left"], 0, "ăn xong phải trả tiền ngay trong bước")
                tc.assertEqual(c["eat_ticks_left"], ticks(Q["eat_s"]) - (s["tick"] - self.served_at[c["id"]]),
                               "timer ăn giảm đúng 1/tick")
            else:
                tc.assertGreaterEqual(c["patience_ticks_left"], 0)
                if time_left > 0:
                    tc.assertGreater(c["patience_ticks_left"], 0, "hết kiên nhẫn khi còn giờ phải rời bàn")
            if c["order_status"] in ("assigned", "served", "unfulfillable"):
                tc.assertFalse(c["reserved"], f"{c['order_status']} không còn phần giữ")
        # món: bếp + tay
        dishes = [x["dish"] for x in s["stoves"] if x["dish"]] + ([s["hand"]] if s["hand"] else [])
        owners = Counter(d["order_id"] for d in dishes)
        tc.assertTrue(all(n == 1 for n in owners.values()), "một đơn tối đa một món")
        for d in dishes:
            c = by_id.get(d["order_id"])
            tc.assertIsNotNone(c, "món phải thuộc khách còn ngồi")
            tc.assertEqual((c["order_status"], c["dish_id"]), ("assigned", d["dish_id"]))
        for c in customers:
            if c["order_status"] == "assigned":
                tc.assertEqual(owners[c["id"]], 1, "đơn assigned có đúng một món ở bếp hoặc tay")
        for st in s["stoves"]:
            if st["state"] == "idle":
                tc.assertEqual((st["dish"], st["cook_ticks_left"], st["ready_ticks"]), (None, 0, 0))
            elif st["state"] == "cooking":
                tc.assertGreater(st["cook_ticks_left"], 0)
                tc.assertEqual(st["ready_ticks"], 0)
            else:
                tc.assertEqual(st["state"], "ready")
                tc.assertEqual(st["cook_ticks_left"], 0)
                if BURN_ON:
                    tc.assertLessEqual(st["ready_ticks"], ticks(Q["burn_s"]))


def play(tc, seed, time_left=None):
    scn = {"stock": initial_stock()}
    if time_left is not None:
        scn["time_left_ticks"] = time_left
    sess = Session("quan", TUNING, scn, seed)
    bot = Bot(seed)
    chk = Checker(tc, sess)
    trace = []
    chk.snapshot(sess.snapshot())
    while not sess.done:
        rows = sess.step(bot.next(sess.sim.pos))
        chk.events(rows)
        snap = sess.snapshot()
        chk.snapshot(snap)
        trace.append((rows, snap["money"], snap["reputation"], len(snap["customers"])))
    end = sess.snapshot()
    tc.assertEqual(end["customers"], [], "đóng ca dọn hết khách")
    tc.assertIsNone(end["hand"], "đóng ca không còn món trên tay của khách đã rời")
    tc.assertEqual(chk.seen["quan_end"], 1)
    return chk, trace


class RandomPlay(unittest.TestCase):
    def test_full_shift_invariants(self):
        total = Counter()
        for seed in SEEDS:
            with self.subTest(seed=seed):
                chk, _ = play(self, seed)
                total += chk.seen
        # bot phải thật sự chơi, không thì các bất biến trên kiểm rỗng
        for name in ("customer_arrived", "cook_started", "dish_ready", "dish_picked", "served", "paid",
                     "customer_left"):
            self.assertGreater(total[name], 0, f"bot chưa từng tạo {name} — tăng độ phủ của bot")

    def test_short_shifts_close_with_customers_seated(self):
        for seed in SEEDS:
            for time_left in (1, 250, 1500, 2000):
                with self.subTest(seed=seed, time_left=time_left):
                    play(self, seed, time_left)

    def test_same_seed_same_trace(self):
        _, a = play(self, 7)
        _, b = play(self, 7)
        self.assertEqual(a, b, "cùng seed + cùng input -> cùng chuỗi event và trạng thái")


if __name__ == "__main__":
    unittest.main()
