"""Phase 3 (TICKET-03, Test Contract v1.2) — phần TV3: bếp tiêu đúng cá thể, giá theo độ tươi, boa trên giá đã chốt,
và bàn giao kho cá thể gather -> quan.

Tự skip cho tới khi game.contract.json có contract_version "1.2".
Giá trị kỳ vọng tính bằng Fraction (chính xác), theo luật:
- Quán: mỗi bước hao tươi kho thô (kể cả hàng đang giữ) TRƯỚC tương tác: −quan_decay_per_s / 60 mỗi tick.
- Gather: hàng có sẵn hao ở đầu bước: −gather_decay_per_s / 60 mỗi tick.
- Bắt đầu nấu: tiêu đúng các id đang giữ, base_price = floor(giá niêm yết × trung bình fresh / 100).
- cook_started.items là mảng cá thể sắp theo kind rồi id (I2 trước I10).
- Dung sai quan sát độ tươi ±0.01; id, kind, giá, tiền so chính xác.
"""

import json
import math
import os
import subprocess
import sys
import unittest
from fractions import Fraction

from chonoi.contract import load_contract
from chonoi.ids import id_key
from chonoi.inputs import InputState
from chonoi.runner import Session

from helpers import ROOT, Workdir, events, frames, headless_cmd, read_jsonl, snapshots, write_json

CONTRACT = load_contract()
V12 = CONTRACT.get("contract_version") in ("1.2", "1.3")
TUNING = CONTRACT["tuning"]
Q = TUNING["quan"]
MENU = TUNING["menu"]
FRESH = TUNING.get("freshness", {})
STOVE = {s["id"]: s["pos"] for s in Q["stoves"]}["B1"]
TABLE = {t["id"]: t["pos"] for t in Q["tables"]}["T1"]
SKIP = "chờ game.contract.json v1.2 (kho cá thể, độ tươi)"


def ticks(seconds):
    return int(round(seconds * 60))


def quan_after(fresh, steps=1):
    """Độ tươi chính xác sau `steps` bước ở quán, kẹp đáy 0."""
    return max(Fraction(0), Fraction(str(fresh)) - Fraction(str(FRESH["quan_decay_per_s"])) / 60 * steps)


def gather_after(fresh, steps=1):
    return max(Fraction(0), Fraction(str(fresh)) - Fraction(str(FRESH["gather_decay_per_s"])) / 60 * steps)


def locked_price(dish_id, fresh_values):
    avg = sum(fresh_values, Fraction(0)) / len(fresh_values)
    return math.floor(Fraction(MENU[dish_id]["price"]) * avg / 100)


def item(iid, kind, fresh):
    return {"id": iid, "kind": kind, "fresh": fresh}


def idle():
    return InputState((0.0, 0.0), {}, set())


def press():
    return InputState((0.0, 0.0), {"interact": True}, {"interact"})


def reserved_customer(cid, table_id, dish_id, ids, **kw):
    c = {"id": cid, "table_id": table_id, "dish_id": dish_id, "order_tick": 0, "state": "waiting",
         "patience_ticks_left": ticks(Q["patience_s"]), "order_status": "reserved", "reserved": list(ids)}
    c.update(kw)
    return c


def session(pos, stock, customers, **scn):
    base = {"player": {"pos": list(pos)}, "random_customers": False, "stock": stock, "customers": customers}
    base.update(scn)
    return Session("quan", TUNING, base, 1)


def cook_once(stock, customer):
    s = session(STOVE, stock, [customer])
    rows = s.step(press())
    started = [r for r in rows if r["name"] == "cook_started"]
    return s, started


@unittest.skipUnless(V12, SKIP)
class CookByInstance(unittest.TestCase):
    def test_consumes_exact_reserved_ids(self):
        # C1 giữ I2 (không phải con tươi nhất) -> bếp tiêu đúng I2, I1 còn lại trong kho
        stock = [item("I1", "ca_loc", 90), item("I2", "ca_loc", 80)]
        s, started = cook_once(stock, reserved_customer("C1", "T1", "ca_loc_nuong_trui", ["I2"]))
        self.assertEqual(len(started), 1)
        used = started[0]["data"]["items"]
        self.assertEqual([(x["id"], x["kind"]) for x in used], [("I2", "ca_loc")])
        self.assertAlmostEqual(used[0]["fresh"], float(quan_after(80)), delta=0.01)
        left = s.snapshot()["stock"]
        self.assertEqual([x["id"] for x in left], ["I1"])
        self.assertAlmostEqual(left[0]["fresh"], float(quan_after(90)), delta=0.01, msg="hàng còn trong kho vẫn hao")
        c = s.snapshot()["customers"][0]
        self.assertEqual((c["order_status"], c["reserved"]), ("assigned", []))

    def test_items_sorted_by_kind_then_id(self):
        ids = {"I10": "ca_linh", "I2": "ca_linh", "I3": "ca_linh", "I7": "bong_dien_dien"}
        stock = [item(i, k, 100) for i, k in ids.items()]
        _, started = cook_once(stock, reserved_customer("C1", "T1", "lau_ca_linh_dien_dien", list(ids)))
        self.assertEqual([(x["kind"], x["id"]) for x in started[0]["data"]["items"]],
                         [("bong_dien_dien", "I7"), ("ca_linh", "I2"), ("ca_linh", "I3"), ("ca_linh", "I10")])
        self.assertEqual([x["id"] for x in started[0]["data"]["items"] if x["kind"] == "ca_linh"],
                         sorted(["I10", "I2", "I3"], key=id_key))


@unittest.skipUnless(V12, SKIP)
class PriceByFreshness(unittest.TestCase):
    def check(self, dish_id, stock):
        c = reserved_customer("C1", "T1", dish_id, [x["id"] for x in stock])
        s, started = cook_once(stock, c)
        want = locked_price(dish_id, [quan_after(x["fresh"]) for x in stock])
        self.assertEqual(started[0]["data"]["base_price"], want)
        self.assertEqual(s.snapshot()["stoves"][0]["dish"]["base_price"], want, "payload món mang giá đã chốt")
        self.assertEqual(s.snapshot()["customers"][0]["base_price"], want)
        return want

    def test_single_item_price_floor(self):
        # fresh 97.5 lấy từ mẫu kho của ticket: sau 1 tick hao ở quán 97.4958… -> floor(60 × 0.97495…) = 58
        self.assertEqual(self.check("ca_loc_nuong_trui", [item("I2", "ca_loc", 97.5)]), 58)

    def test_average_over_instances(self):
        # gỏi: (100 + 61)/2 − 1/240 = 80.4958… -> floor(40 × 0.80495…) = 32
        self.assertEqual(self.check("goi_bong_sung", [item("I1", "bong_sung", 100), item("I2", "bong_sung", 61)]), 32)

    def test_full_fresh_loses_one_tick_before_cooking(self):
        # hàng 100 trong kho quán hao ở bước 1 TRƯỚC tương tác -> 99.9958… -> floor(60 × 0.99995…) = 59
        self.assertEqual(self.check("ca_loc_nuong_trui", [item("I1", "ca_loc", 100)]), 59)

    def test_price_locked_at_cook_start_not_changed_by_waiting(self):
        stock = [item("I1", "ca_loc", 97.5)]
        s, started = cook_once(stock, reserved_customer("C1", "T1", "ca_loc_nuong_trui", ["I1"]))
        price = started[0]["data"]["base_price"]
        for _ in range(ticks(MENU["ca_loc_nuong_trui"]["cook_s"]) + 300):
            s.step(idle())
        st = s.snapshot()["stoves"][0]
        self.assertEqual((st["state"], st["dish"]["base_price"]), ("ready", price), "món chín không hao, giá giữ nguyên")


@unittest.skipUnless(V12, SKIP)
class TipOnLockedPrice(unittest.TestCase):
    def test_tip_and_paid_use_fresh_price(self):
        locked = 58  # giá đã chốt theo độ tươi, nằm trong payload món
        c = reserved_customer("C1", "T1", "ca_loc_nuong_trui", [], order_status="assigned", base_price=None)
        s = Session("quan", TUNING, {"player": {"pos": list(TABLE)}, "random_customers": False, "stock": [],
                                     "customers": [c],
                                     "hand": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui",
                                              "base_price": locked}}, 1)
        rows = s.step(press())
        tip = math.floor(locked * Fraction(str(Q["tip_rate"])))
        self.assertEqual([(r["name"], r["data"]["base_price"], r["data"]["tip"]) for r in rows],
                         [("served", locked, tip)])
        paid = None
        for _ in range(ticks(Q["eat_s"]) + 1):
            paid = paid or next((r for r in s.step(idle()) if r["name"] == "paid"), None)
        self.assertEqual((paid["data"]["base_price"], paid["data"]["amount"]), (locked, locked + tip))


def run(*args):
    cmd = headless_cmd()
    if cmd and cmd[0] in ("python3", "python"):
        cmd = [sys.executable, *cmd[1:]]
    p = subprocess.run([*cmd, *args], cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stderr


@unittest.skipUnless(V12, SKIP)
class HandoffV12(unittest.TestCase):
    """Smoke bàn giao kho cá thể theo mẫu TICKET-03 (gather một bước cập bến -> quan --inventory --ticks 0)."""

    def dock(self, w, fresh):
        scn = write_json(w.path("dock.json"), {"gather": {"hold": [item("I1", "ca_linh", fresh)],
                                                          "random_fish": False, "monsters": []}})
        inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
        inv = w.path("catch.json")
        code, err = run("--mode", "gather", "--seed", "42", "--scenario", scn, "--inputs", inp,
                        "--ticks", "1", "--out", w.path("g.jsonl"), "--inventory-out", inv)
        self.assertEqual(code, 0, err)
        with open(inv, encoding="utf-8") as f:
            return read_jsonl(w.path("g.jsonl")), inv, json.load(f)

    def open_quan(self, w, inv):
        code, err = run("--mode", "quan", "--seed", "42", "--inventory", inv, "--ticks", "0", "--out", w.path("q.jsonl"))
        self.assertEqual(code, 0, err)
        return snapshots(read_jsonl(w.path("q.jsonl")))[0]

    def test_file_matches_gather_end_and_quan_stock(self):
        with Workdir() as w:
            rows, inv, data = self.dock(w, 100)
            self.assertEqual(set(data), {"items"})
            self.assertEqual([(x["id"], x["kind"]) for x in data["items"]], [("I1", "ca_linh")])
            self.assertAlmostEqual(data["items"][0]["fresh"], float(gather_after(100)), delta=0.01,
                                   msg="hao một lần ở đầu bước gather trước khi cập bến")
            end = events(rows, "gather_end")[0]["data"]
            self.assertEqual(end["reason"], "docked")
            self.assertEqual([(x["id"], x["kind"]) for x in end["inventory"]["items"]], [("I1", "ca_linh")])
            self.assertAlmostEqual(end["inventory"]["items"][0]["fresh"], data["items"][0]["fresh"], delta=0.01)
            stock = self.open_quan(w, inv)["stock"]
            self.assertEqual([(x["id"], x["kind"]) for x in stock], [("I1", "ca_linh")])
            self.assertAlmostEqual(stock[0]["fresh"], data["items"][0]["fresh"], delta=0.01,
                                   msg="quán nhận nguyên độ tươi, ticks 0 chưa hao")

    def test_spoiled_item_still_handed_over(self):
        # mẫu ngưỡng của ticket: fresh 30 ươn ở bước đầu, vẫn chiếm chỗ và vẫn bàn giao sang quán
        with Workdir() as w:
            rows, inv, data = self.dock(w, 30)
            sp = events(rows, "spoiled")
            self.assertEqual([(r["tick"], r["data"]) for r in sp],
                             [(1, {"item_id": "I1", "kind": "ca_linh", "location": "hold"})])
            names = [r["name"] for r in events(rows)]
            self.assertLess(names.index("spoiled"), names.index("gather_end"))
            self.assertEqual([x["id"] for x in data["items"]], ["I1"])
            self.assertLess(data["items"][0]["fresh"], FRESH["spoiled_below"])
            stock = self.open_quan(w, inv)["stock"]
            self.assertEqual([x["id"] for x in stock], ["I1"], "kho quán nhận cả hàng ươn")

    def test_counted_inventory_file_rejected(self):
        with Workdir() as w:
            out = w.path("q.jsonl")
            for name, obj in {"counted_v10": {"items": {"ca_loc": 1}},
                              "dup_id": {"items": [item("I1", "ca_loc", 50), item("I1", "ca_linh", 50)]},
                              "fresh_out_of_range": {"items": [item("I1", "ca_loc", 100.5)]},
                              "unknown_kind": {"items": [item("I1", "ca_tra", 50)]},
                              "empty_id": {"items": [item("", "ca_loc", 50)]}}.items():
                inv = write_json(w.path(f"{name}.json"), obj)
                code, _ = run("--mode", "quan", "--seed", "1", "--inventory", inv, "--ticks", "0", "--out", out)
                self.assertEqual(code, 2, name)
                self.assertFalse(os.path.exists(out), f"{name}: phải thoát trước khi ghi JSONL")

    def test_empty_inventory_list(self):
        with Workdir() as w:
            inv = write_json(w.path("empty.json"), {"items": []})
            self.assertEqual(self.open_quan(w, inv)["stock"], [])


if __name__ == "__main__":
    unittest.main()
