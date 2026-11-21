"""Phase 2 (TICKET-02 mục 1.3) — lát 4 với 2 bếp B1/B2, 4 bàn T1–T4 và 6 món.

Số liệu đọc từ game.contract.json. Khi contract chưa lên v1.1 (chưa có B2 / lau_mam) thì các test tự skip,
vì luật lát 4 đã duyệt danh sách bếp/bàn/menu chung, chỉ chờ cấu hình chuẩn.
Khách dựng sẵn khai đủ trường; kiên nhẫn giảm 1 ở bước 1 (lát 3) trước interact.
"""

import math
import unittest

from chonoi.contract import load_contract
from chonoi.inputs import InputState
from chonoi.runner import Session

from fractions import Fraction

from helpers import stock_of

# TICKET-03 (v1.2) [THAY THẾ]: kho là mảng cá thể; đơn reserved để trống `reserved` cho sim tự cấp theo id (tươi nhất,
# hòa theo id), đơn khác giữ []. Giá chốt khi nấu = floor(giá × fresh trung bình / 100), hàng 100 hao 1 tick trước.

TUNING = load_contract()["tuning"]
Q = TUNING["quan"]
MENU = TUNING["menu"]
STOVES = {s["id"]: s["pos"] for s in Q["stoves"]}
TABLES = {t["id"]: t["pos"] for t in Q["tables"]}
P2_READY = {"B1", "B2"} <= set(STOVES) and {"T1", "T2", "T3", "T4"} <= set(TABLES) and "lau_mam" in MENU


def ticks(seconds):
    return int(round(seconds * 60))


def idle():
    return InputState((0.0, 0.0), {}, set())


def press():
    return InputState((0.0, 0.0), {"interact": True}, {"interact"})


def payload(cid, dish_id):
    return {"order_id": cid, "dish_id": dish_id, "base_price": MENU[dish_id]["price"]}


def customer(cid, table_id, dish_id, **kw):
    c = {"id": cid, "table_id": table_id, "dish_id": dish_id, "order_tick": 0, "state": "waiting",
         "patience_ticks_left": ticks(Q["patience_s"]), "order_status": "reserved"}
    c.update(kw)
    return c


def assigned(cid, table_id, dish_id, **kw):
    return customer(cid, table_id, dish_id, **{"order_status": "assigned", "reserved": [], **kw})


def eating(cid, table_id, dish_id, eat_left, tip=0):
    return assigned(cid, table_id, dish_id, state="eating", order_status="served", eat_ticks_left=eat_left,
                    base_price=MENU[dish_id]["price"], tip=tip)


def stock_for(*customers):
    """Kho cá thể vừa đủ công thức cho các đơn reserved."""
    out = {}
    for c in customers:
        if c.get("order_status", "reserved") == "reserved":
            for k, n in MENU[c["dish_id"]]["recipe"].items():
                out[k] = out.get(k, 0) + n
    return stock_of(out)


def fresh_price(dish_id, ticks_in_quan=1):
    f = 100 - Fraction(str(TUNING["freshness"]["quan_decay_per_s"])) / 60 * ticks_in_quan
    return math.floor(MENU[dish_id]["price"] * f / 100)


def session(pos, customers, **scn):
    base = {"player": {"pos": list(pos)}, "random_customers": False, "customers": customers,
            "stock": stock_for(*customers)}
    base.update(scn)
    return Session("quan", TUNING, base, 1)


def names(rows):
    return [r["name"] for r in rows]


@unittest.skipUnless(P2_READY, "chờ game.contract.json v1.1 (B2, T2–T4, 6 món)")
class TwoStoves(unittest.TestCase):
    def test_tie_between_stoves_picks_lower_id(self):
        mid = [(STOVES["B1"][0] + STOVES["B2"][0]) / 2, STOVES["B1"][1]]
        if math.dist(mid, STOVES["B1"]) > Q["interact_radius"]:
            self.skipTest("hai bếp cách nhau quá 2 × interact_radius")
        s = session(mid, [customer("C1", "T1", "ca_loc_nuong_trui")])
        rows = s.step(press())
        self.assertEqual([(r["name"], r["data"]["stove_id"]) for r in rows], [("cook_started", "B1")])

    def test_second_stove_cooks_while_first_busy(self):
        c1 = assigned("C1", "T1", "ca_loc_nuong_trui")
        c2 = customer("C2", "T2", "goi_bong_sung")
        b1 = {"id": "B1", "state": "cooking", "dish": payload("C1", "ca_loc_nuong_trui"),
              "cook_ticks_left": ticks(MENU["ca_loc_nuong_trui"]["cook_s"])}
        s = session(STOVES["B2"], [c1, c2], stoves=[b1])
        rows = s.step(press())
        self.assertEqual(names(rows), ["cook_started"])
        self.assertEqual((rows[0]["data"]["stove_id"], rows[0]["data"]["order_id"]), ("B2", "C2"))
        st = {x["id"]: x for x in s.snapshot()["stoves"]}
        self.assertEqual((st["B1"]["state"], st["B2"]["state"]), ("cooking", "cooking"))
        self.assertEqual(st["B1"]["cook_ticks_left"], ticks(MENU["ca_loc_nuong_trui"]["cook_s"]) - 1)

    def test_both_stoves_ready_on_same_tick_emit_by_stove_id(self):
        c1 = assigned("C1", "T1", "ca_loc_nuong_trui")
        c2 = assigned("C2", "T2", "goi_bong_sung")
        stoves = [{"id": "B2", "state": "cooking", "dish": payload("C2", "goi_bong_sung"), "cook_ticks_left": 1},
                  {"id": "B1", "state": "cooking", "dish": payload("C1", "ca_loc_nuong_trui"), "cook_ticks_left": 1}]
        s = session(Q["start_pos"], [c1, c2], stoves=stoves)
        rows = s.step(idle())
        self.assertEqual([(r["name"], r["data"]["stove_id"]) for r in rows],
                         [("dish_ready", "B1"), ("dish_ready", "B2")])

    def test_oldest_order_then_table_id(self):
        cs = [customer("C1", "T3", "ca_loc_nuong_trui", order_tick=0),
              customer("C2", "T2", "goi_bong_sung", order_tick=0),
              customer("C3", "T1", "ca_keo_nuong", order_tick=120)]
        s = session(STOVES["B1"], cs)
        self.assertEqual(s.step(press())[0]["data"]["order_id"], "C2", "cùng order_tick -> bàn id nhỏ (T2 < T3)")

    def test_hand_full_cannot_pick_from_other_stove(self):
        c1 = assigned("C1", "T1", "ca_loc_nuong_trui")
        c2 = assigned("C2", "T2", "goi_bong_sung")
        b2 = {"id": "B2", "state": "ready", "dish": payload("C2", "goi_bong_sung")}
        s = session(STOVES["B2"], [c1, c2], stoves=[b2], hand=payload("C1", "ca_loc_nuong_trui"))
        self.assertEqual(s.step(press()), [], "carry_limit 1: tay đang cầm món của C1")
        self.assertEqual({x["id"]: x["state"] for x in s.snapshot()["stoves"]}["B2"], "ready")


@unittest.skipUnless(P2_READY, "chờ game.contract.json v1.1 (B2, T2–T4, 6 món)")
class NewDishes(unittest.TestCase):
    def test_new_dishes_cook_with_recipe_price_and_time_from_data(self):
        for dish_id in ("canh_chua_ca_loc", "ca_keo_nuong", "lau_mam"):
            with self.subTest(dish_id):
                c = customer("C1", "T1", dish_id)
                s = session(STOVES["B1"], [c])
                rows = s.step(press())
                self.assertEqual(names(rows), ["cook_started"])
                recipe = MENU[dish_id]["recipe"]
                items = [k for k in sorted(recipe) for _ in range(recipe[k])]
                self.assertEqual([x["kind"] for x in rows[0]["data"]["items"]], items, "items sắp theo kind, đủ số lượng")
                self.assertEqual(rows[0]["data"]["base_price"], fresh_price(dish_id))
                self.assertEqual(s.snapshot()["stoves"][0]["cook_ticks_left"], ticks(MENU[dish_id]["cook_s"]))
                self.assertEqual(s.snapshot()["stock"], [], "tiêu đúng phần giữ")

    def test_lau_mam_full_flow_price_and_tip(self):
        c = assigned("C1", "T4", "lau_mam")
        s = session(TABLES["T4"], [c], hand=payload("C1", "lau_mam"))
        rows = s.step(press())
        price = MENU["lau_mam"]["price"]
        tip = math.floor(price * Q["tip_rate"])
        self.assertEqual(names(rows), ["served"])
        self.assertEqual((rows[0]["data"]["table_id"], rows[0]["data"]["tip"]), ("T4", tip))
        paid = None
        for _ in range(ticks(Q["eat_s"]) + 1):
            paid = paid or next((r for r in s.step(idle()) if r["name"] == "paid"), None)
        self.assertEqual(paid["data"]["amount"], price + tip)


@unittest.skipUnless(P2_READY, "chờ game.contract.json v1.1 (B2, T2–T4, 6 món)")
class FourTables(unittest.TestCase):
    def test_serve_at_own_table_only(self):
        c3 = assigned("C3", "T3", "goi_bong_sung")
        c1 = customer("C1", "T1", "ca_loc_nuong_trui")
        hand = payload("C3", "goi_bong_sung")
        s = session(TABLES["T1"], [c1, c3], hand=hand)
        self.assertEqual(s.step(press()), [], "đứng ở T1 nhưng món của khách T3 -> bỏ lượt")
        s = session(TABLES["T3"], [c1, c3], hand=hand)
        rows = s.step(press())
        self.assertEqual([(r["name"], r["data"]["table_id"]) for r in rows], [("served", "T3")])

    def test_paid_same_tick_in_table_id_order(self):
        cs = [eating("C1", "T2", "goi_bong_sung", 1), eating("C2", "T1", "ca_loc_nuong_trui", 1),
              eating("C3", "T4", "ca_keo_nuong", 1)]
        s = session(Q["start_pos"], cs)
        rows = s.step(idle())
        self.assertEqual([(r["name"], r["data"]["table_id"]) for r in rows],
                         [("paid", "T1"), ("paid", "T2"), ("paid", "T4")])
        self.assertEqual(s.snapshot()["money"], sum(MENU[c["dish_id"]]["price"] for c in cs))

    def test_closing_with_mixed_tables(self):
        cs = [eating("C1", "T1", "goi_bong_sung", ticks(Q["eat_s"])),
              customer("C2", "T2", "ca_loc_nuong_trui"),
              eating("C3", "T3", "ca_keo_nuong", ticks(Q["eat_s"]))]
        s = session(Q["start_pos"], cs, time_left_ticks=1)
        rows = s.step(idle())
        self.assertEqual([(r["name"], r["data"].get("table_id"), r["data"].get("reason")) for r in rows],
                         [("paid", "T1", "closing"), ("customer_left", "T2", "closing"),
                          ("paid", "T3", "closing"), ("quan_end", None, "time")])
        self.assertEqual(s.snapshot()["reputation"], Q["reputation_initial"], "boa 0, khách chờ rời closing")


if __name__ == "__main__":
    unittest.main()
