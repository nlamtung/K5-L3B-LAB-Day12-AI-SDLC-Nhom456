"""Phase 3 (TICKET-03, Test Contract v1.2) — độ tươi, ngưỡng ươn, giữ chỗ theo id, bàn giao kho cá thể.

Bổ sung cho tests/test_quan_v12_fresh.py (nấu theo cá thể, giá theo tươi, smoke bàn giao):
- gather: hàng mới 100 hao từ bước sau; spoiled đúng tick biên, đúng một lần, theo id; id I nối tiếp; pause dừng hao.
- quán: hao cả hàng đang giữ; giữ cá thể tươi nhất (hòa theo id); hàng vừa ươn -> nhả và giữ lại đúng một lần theo
  order_tick rồi id bàn, thiếu -> unfulfillable; hàng ươn không dùng để chọn món.
- file kho đủ chính xác ở ngưỡng 30; day bàn giao cùng tick không hao thêm, Ngày kế cấp id mới, Shop không hao.
- fixture v1.2 sai / mâu thuẫn -> mã 2.

Số đọc từ game.contract.json; độ tươi kỳ vọng tính bằng Fraction (chính xác), so ±0.01 như Test Contract.
"""

import json
import os
import unittest
from fractions import Fraction

from chonoi.contract import load_contract
from chonoi.inputs import InputState
from chonoi.runner import Session
from chonoi.sim.day import DaySession

from helpers import Workdir, events, frames, items, read_jsonl, run_headless, snapshots, write_json

CONTRACT = load_contract()
TUNING = CONTRACT["tuning"]
FRESH = TUNING["freshness"]
Q = TUNING["quan"]
MENU = TUNING["menu"]
G_DECAY = Fraction(str(FRESH["gather_decay_per_s"])) / 60
Q_DECAY = Fraction(str(FRESH["quan_decay_per_s"])) / 60
BELOW = FRESH["spoiled_below"]
STOVE = {s["id"]: s["pos"] for s in Q["stoves"]}["B1"]


def idle():
    return InputState((0.0, 0.0), {}, set())


def press(name="interact"):
    return InputState((0.0, 0.0), {name: True}, {name})


def gather(hold, **scn):
    base = {"hold": hold, "random_fish": False, "monsters": [], "player": {"pos": [50, 10]}}
    base.update(scn)
    return Session("gather", TUNING, base, 1)


def quan(stock, customers=(), **scn):
    base = {"stock": stock, "customers": list(customers), "random_customers": False}
    base.update(scn)
    return Session("quan", TUNING, base, 1)


def waiting(cid, table_id, dish_id, order_tick=0, **kw):
    c = {"id": cid, "table_id": table_id, "dish_id": dish_id, "order_tick": order_tick}
    c.update(kw)
    return c


def names(rows):
    return [r["name"] for r in rows]


def by_id(snap_items):
    return {x["id"]: x for x in snap_items}


@unittest.skipUnless(CONTRACT.get("contract_version") == "1.2", "chờ contract v1.2")
class GatherFreshness(unittest.TestCase):
    def test_spoiled_on_exact_boundary_tick(self):
        # 30.5 tươi, giỏ hao 0.5/s: tick 60 đúng 30.0 (chưa ươn), tick 61 < 30 -> spoiled đúng tick 61
        s = gather(items("ca_linh", fresh=30.5))
        got = []
        for _ in range(61):
            got += s.step(idle())
        sp = [r for r in got if r["name"] == "spoiled"]
        self.assertEqual([(r["tick"], r["data"]) for r in sp],
                         [(61, {"item_id": "I1", "kind": "ca_linh", "location": "hold"})])

    def test_spoiled_once_and_by_id_and_not_for_already_spoiled(self):
        hold = (items("ca_loc", fresh=30, start=10) + items("ca_loc", fresh=30, start=2)
                + items("bong_sung", fresh=29, start=3))
        s = gather(hold)
        rows = s.step(idle()) + s.step(idle()) + s.step(idle())
        self.assertEqual([(r["tick"], r["data"]["item_id"]) for r in rows if r["name"] == "spoiled"],
                         [(1, "I2"), (1, "I10")], "theo id (I2 trước I10), một lần; I3 đã ươn từ đầu không phát")

    def test_new_item_starts_at_100_and_decays_from_next_step(self):
        node = {"id": "N1", "kind": "bong_sung", "pos": [20, 0]}
        s = Session("gather", TUNING, {"hold": items("ca_loc", fresh=80, start=7), "random_fish": False,
                                       "monsters": [], "nodes": [node], "player": {"pos": [20, 0]}}, 1)
        s.step(press())
        h = s.snapshot()["hold"]
        self.assertEqual([x["id"] for x in h], ["I7", "I8"], "id mới nối sau id lớn nhất đã nạp")
        self.assertEqual(h[1]["fresh"], FRESH["initial"], "hàng mới = 100 ở bước hái")
        self.assertAlmostEqual(h[0]["fresh"], float(80 - G_DECAY), delta=0.01)
        s.step(idle())
        self.assertAlmostEqual(s.snapshot()["hold"][1]["fresh"], float(100 - G_DECAY), delta=0.01)

    def test_pause_stops_decay(self):
        s = gather(items("ca_loc", fresh=50))
        s.step(press("pause"))
        for _ in range(120):
            s.step(idle())
        self.assertEqual(s.snapshot()["state"], "paused")
        self.assertEqual(s.snapshot()["hold"][0]["fresh"], 50, "pause dừng hao tươi")


@unittest.skipUnless(CONTRACT.get("contract_version") == "1.2", "chờ contract v1.2")
class QuanFreshness(unittest.TestCase):
    def test_reserved_items_decay_and_spoil_in_stock(self):
        c = waiting("C1", "T1", "ca_loc_nuong_trui", reserved=["I1"])
        s = quan(items("ca_loc", fresh=30) + items("ca_loc", fresh=90, start=2), [c])
        rows = s.step(idle())
        self.assertEqual([r["data"] for r in rows if r["name"] == "spoiled"],
                         [{"item_id": "I1", "kind": "ca_loc", "location": "stock"}], "hao cả hàng đang giữ")
        snap = s.snapshot()
        self.assertAlmostEqual(by_id(snap["stock"])["I2"]["fresh"], float(90 - Q_DECAY), delta=0.01)
        self.assertEqual(snap["customers"][0]["reserved"], ["I2"], "nhả I1 vừa ươn, giữ lại cá thể khả dụng")
        self.assertEqual(snap["customers"][0]["order_status"], "reserved")

    def test_spoiled_reservation_unfulfillable_when_no_replacement(self):
        c = waiting("C1", "T1", "ca_loc_nuong_trui", reserved=["I1"])
        s = quan(items("ca_loc", fresh=30), [c])
        s.step(idle())
        got = s.snapshot()["customers"][0]
        self.assertEqual((got["order_status"], got["reserved"], got["state"]), ("unfulfillable", [], "waiting"))
        s2 = quan(items("ca_loc", fresh=30), [waiting("C1", "T1", "ca_loc_nuong_trui", reserved=["I1"])],
                  player={"pos": list(STOVE)})
        self.assertEqual(names(s2.step(press())), ["spoiled"], "đơn vừa thành unfulfillable không được bếp nấu")

    def test_re_reserve_order_by_order_tick_then_table(self):
        # C2 (order_tick 0, T2) cũ hơn C1 (order_tick 5, T1): một cá thể thay thế duy nhất thuộc về C2
        cs = [waiting("C1", "T1", "ca_loc_nuong_trui", order_tick=5, reserved=["I1"]),
              waiting("C2", "T2", "ca_loc_nuong_trui", order_tick=0, reserved=["I2"])]
        s = quan(items("ca_loc", "ca_loc", fresh=30) + items("ca_loc", fresh=70, start=3), cs)
        rows = s.step(idle())
        self.assertEqual([r["data"]["item_id"] for r in rows if r["name"] == "spoiled"], ["I1", "I2"])
        cust = {c["id"]: c for c in s.snapshot()["customers"]}
        self.assertEqual((cust["C2"]["order_status"], cust["C2"]["reserved"]), ("reserved", ["I3"]))
        self.assertEqual((cust["C1"]["order_status"], cust["C1"]["reserved"]), ("unfulfillable", []))

    def test_auto_reserve_takes_freshest_then_lower_id(self):
        stock = (items("ca_loc", fresh=60, start=10) + items("ca_loc", fresh=60, start=2)
                 + items("ca_loc", fresh=40, start=1))
        s = quan(stock, [waiting("C1", "T1", "ca_loc_nuong_trui")])
        self.assertEqual(s.snapshot()["customers"][0]["reserved"], ["I2"], "tươi nhất, hòa theo id (I2 < I10)")

    def test_spoiled_stock_not_offered_to_new_customers(self):
        s = quan(items("ca_loc", fresh=10), random_customers=True)
        evs = []
        for _ in range(Q["first_customer_tick"]):
            evs += s.step(idle())
        self.assertEqual([(r["name"], r["data"]) for r in evs], [("no_dish", {})], "hàng ươn không dùng nấu")

    def test_cook_uses_reserved_ids_even_if_others_fresher(self):
        c = waiting("C1", "T1", "ca_loc_nuong_trui", reserved=["I1"])
        s = quan(items("ca_loc", fresh=50) + items("ca_loc", fresh=100, start=2), [c], player={"pos": list(STOVE)})
        rows = s.step(press())
        cook = next(r for r in rows if r["name"] == "cook_started")["data"]
        self.assertEqual([x["id"] for x in cook["items"]], ["I1"])
        f = Fraction(50) - Q_DECAY
        self.assertEqual(cook["base_price"], (MENU["ca_loc_nuong_trui"]["price"] * f / 100).__floor__())


@unittest.skipUnless(CONTRACT.get("contract_version") == "1.2", "chờ contract v1.2")
class FilePrecisionAndDay(unittest.TestCase):
    def test_file_roundtrip_keeps_threshold_branch(self):
        # 30 + 1/120: sau 1 bước gather đúng 30.0 (chưa ươn) -> file -> quán đọc lại vẫn 30 -> bước quán đầu mới ươn
        with Workdir() as w:
            sc = write_json(w.path("dock.json"), {"gather": {"hold": items("ca_linh", fresh=float(30 + G_DECAY)),
                                                             "random_fish": False, "monsters": []}})
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            inv = w.path("catch.json")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--scenario", sc, "--inputs", inp,
                                     "--ticks", "1", "--out", w.path("g.jsonl"), "--inventory-out", inv)
            self.assertEqual(code, 0, err)
            self.assertEqual(events(read_jsonl(w.path("g.jsonl")), "spoiled"), [], "đúng 30 chưa ươn")
            with open(inv, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["items"][0]["fresh"], 30)
            code, err = run_headless("--mode", "quan", "--seed", "1", "--inventory", inv, "--ticks", "1",
                                     "--out", w.path("q.jsonl"))
            self.assertEqual(code, 0, err)
            sp = events(read_jsonl(w.path("q.jsonl")), "spoiled")
            self.assertEqual([(r["tick"], r["data"]["location"]) for r in sp], [(1, "stock")])

    def test_day_handoff_same_tick_new_ids_next_day_and_no_decay_in_shop(self):
        hold = items("ca_loc", "bong_sung", fresh=90)
        s = DaySession(TUNING, {"gather": {"hold": hold, "random_fish": False, "monsters": []},
                                "quan": {"time_left_ticks": 2, "random_customers": False}}, 1, 2)
        rows = s.step(press())
        end = next(r for r in rows if r["name"] == "gather_end")["data"]["inventory"]["items"]
        stock = s.snapshot()["stock"]
        self.assertEqual([x["id"] for x in stock], ["I1", "I2"])
        for a, b in zip(stock, end):
            self.assertAlmostEqual(a["fresh"], b["fresh"], delta=0.01, msg="bàn giao cùng tick, không hao thêm")
        while s.phase != "shop":
            s.step(idle())
        shop0 = s.snapshot()["stock"]
        for _ in range(10):
            s.step(idle())
        self.assertEqual(s.snapshot()["stock"], shop0, "hàng thô ở Shop không hao")
        s.step(press("shop_done"))
        self.assertEqual((s.day, [x["id"] for x in s.snapshot()["hold"]]), (2, ["I3", "I4"]),
                         "Ngày kế cấp id mới theo thứ tự mảng mẫu")
        self.assertEqual([x["fresh"] for x in s.snapshot()["hold"]], [90, 90])


@unittest.skipUnless(CONTRACT.get("contract_version") == "1.2", "chờ contract v1.2")
class BadFixturesV12(unittest.TestCase):
    def test_bad_v12_fixtures_exit_2(self):
        c = {"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui"}
        bad = {
            "hold_counted_kinds": {"gather": {"hold": ["ca_loc"]}},
            "hold_missing_fresh": {"gather": {"hold": [{"id": "I1", "kind": "ca_loc"}]}},
            "hold_fresh_over": {"gather": {"hold": items("ca_loc", fresh=101)}},
            "hold_dup_id": {"gather": {"hold": items("ca_loc") + items("ca_linh")}},
            "stock_counted": {"quan": {"stock": {"ca_loc": 1}}},
            "stock_unknown_kind": {"quan": {"stock": items("ca_tra")}},
            "reserved_counted": {"quan": {"stock": items("ca_loc"), "customers": [dict(c, reserved={"ca_loc": 1})]}},
            "reserved_missing_id": {"quan": {"stock": items("ca_loc"), "customers": [dict(c, reserved=["I9"])]}},
            "reserved_spoiled": {"quan": {"stock": items("ca_loc", fresh=10), "customers": [dict(c, reserved=["I1"])]}},
            "reserved_wrong_kind": {"quan": {"stock": items("ca_linh"), "customers": [dict(c, reserved=["I1"])]}},
            "reserved_shared": {"quan": {"stock": items("ca_loc"), "customers": [
                dict(c, reserved=["I1"]), dict(c, id="C2", table_id="T2", reserved=["I1"])]}},
            "auto_reserve_only_spoiled": {"quan": {"stock": items("ca_loc", fresh=29), "customers": [c]}},
            "assigned_with_reserved": {"quan": {"stock": items("ca_loc"), "customers": [
                dict(c, order_status="unfulfillable", reserved=["I1"])]}},
        }
        with Workdir() as w:
            out = w.path("o.jsonl")
            for name, data in bad.items():
                mode = next(iter(data))
                sc = write_json(w.path(f"{name}.json"), data)
                code, _ = run_headless("--mode", mode, "--seed", "1", "--ticks", "0", "--scenario", sc, "--out", out)
                self.assertEqual(code, 2, name)
                self.assertFalse(os.path.exists(out), f"{name}: phải thoát trước khi ghi JSONL")

    def test_good_v12_fixtures_exit_0(self):
        with Workdir() as w:
            for data in ({"gather": {"hold": items("ca_loc", fresh=0)}}, {"gather": {"hold": []}},
                         {"quan": {"stock": []}}, {"quan": {"stock": items("ca_loc", fresh=12.5)}},
                         {"quan": {"stock": items("ca_loc"), "customers": [
                             {"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "reserved": ["I1"]}]}}):
                mode = next(iter(data))
                sc = write_json(w.path("sc.json"), data)
                code, err = run_headless("--mode", mode, "--seed", "1", "--ticks", "1", "--scenario", sc,
                                         "--out", w.path("o.jsonl"))
                self.assertEqual(code, 0, (data, err))
                snaps = snapshots(read_jsonl(w.path("o.jsonl")))
                self.assertTrue(snaps)


if __name__ == "__main__":
    unittest.main()
