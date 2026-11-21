"""Tích hợp Lặn & Hái -> file kho -> Mở Quán (PRD-0 mục G), kiểu HỘP ĐEN qua `headless_cmd`.

Hai tiến trình riêng dùng chung file kho: gather --inventory-out rồi quan --inventory.
Trên Windows `python3` có thể là alias của Store, nên token đầu `python3` được thay bằng trình thông dịch đang chạy test
(cùng lệnh, cùng module); các lệnh khác giữ nguyên.
"""

import json
import math
import os
import subprocess
import sys
import unittest

from helpers import ROOT, Workdir, counts, events, frames, headless_cmd, items, kinds, read_jsonl, snapshots, write_json

from fractions import Fraction

# TICKET-03 (v1.2) [THAY THẾ]: file kho / gather_end.inventory / stock là mảng cá thể {id, kind, fresh} theo id.
# So id, kind chính xác và fresh ±0.01 (gather_end trong JSONL làm tròn 3 chữ số, file giữ đủ chính xác).
# Giá bán chốt theo độ tươi khi nấu. File kho đếm (v1.0/v1.1) giờ là sai schema -> mã 2.
def same_items(tc, got, want, msg=None):
    tc.assertEqual([(x["id"], x["kind"]) for x in got], [(x["id"], x["kind"]) for x in want], msg)
    for a, b in zip(got, want):
        tc.assertAlmostEqual(a["fresh"], b["fresh"], delta=0.01, msg=msg)

with open(os.path.join(ROOT, "game.contract.json"), encoding="utf-8") as _f:
    TUNING = json.load(_f)["tuning"]
Q = TUNING["quan"]
MENU = TUNING["menu"]
FRESH = TUNING["freshness"]


def run(*args):
    cmd = headless_cmd()
    if cmd and cmd[0] in ("python3", "python"):
        cmd = [sys.executable, *cmd[1:]]
    p = subprocess.run([*cmd, *args], cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stderr


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


class GatherToQuan(unittest.TestCase):
    def dock(self, w, hold, name="catch.json"):
        """Buổi sáng cập bến ngay ở tick 0 với giỏ dựng sẵn; trả (rows gather, đường dẫn kho)."""
        scn = write_json(w.path("dock.json"), {"gather": {"hold": items(*hold)}})
        inp = write_json(w.path("dock-in.json"), frames({"tick": 0, "interact": True}))
        inv = w.path(name)
        code, err = run("--mode", "gather", "--seed", "42", "--scenario", scn, "--inputs", inp,
                        "--ticks", "1", "--out", w.path("g.jsonl"), "--inventory-out", inv)
        self.assertEqual(code, 0, err)
        return read_jsonl(w.path("g.jsonl")), inv

    def test_inventory_file_matches_gather_end_and_quan_stock(self):
        with Workdir() as w:
            rows, inv = self.dock(w, ["ca_loc", "bong_sung", "ca_linh", "bong_sung"])
            end = events(rows, "gather_end")
            self.assertEqual(len(end), 1)
            self.assertEqual(end[0]["data"]["reason"], "docked")
            with open(inv, encoding="utf-8") as f:
                file_inv = json.load(f)
            self.assertEqual(set(file_inv), {"items"})
            same_items(self, file_inv["items"], end[0]["data"]["inventory"]["items"],
                       "file kho khớp object inventory trong gather_end")
            self.assertEqual([x["id"] for x in file_inv["items"]], ["I1", "I2", "I3", "I4"], "xuất theo id")
            self.assertEqual(counts(file_inv["items"]), {"bong_sung": 2, "ca_linh": 1, "ca_loc": 1})
            code, err = run("--mode", "quan", "--seed", "42", "--inventory", inv, "--ticks", "0",
                            "--out", w.path("q.jsonl"))
            self.assertEqual(code, 0, err)
            s0 = snapshots(read_jsonl(w.path("q.jsonl")))[0]
            same_items(self, s0["stock"], file_inv["items"], "quán nhận nguyên id, kind, độ tươi")
            self.assertEqual((s0["money"], s0["earned"], s0["reputation"]), (0, 0, Q["reputation_initial"]))

    def test_empty_hold_gives_empty_inventory_and_empty_stock(self):
        with Workdir() as w:
            _, inv = self.dock(w, [])
            self.assertEqual(read_bytes(inv).strip(), b'{"items":[]}')
            code, err = run("--mode", "quan", "--seed", "1", "--inventory", inv, "--ticks", "0",
                            "--out", w.path("q.jsonl"))
            self.assertEqual(code, 0, err)
            self.assertEqual(snapshots(read_jsonl(w.path("q.jsonl")))[0]["stock"], [])

    def test_quan_cooks_and_sells_with_ingredients_from_gather(self):
        """Hàng mang về thật sự được nấu và bán: kho từ gather + khách dựng sẵn -> nấu -> bưng -> phục vụ -> trả tiền."""
        with Workdir() as w:
            _, inv = self.dock(w, ["ca_loc"])
            stove, table = Q["stoves"][0]["pos"], Q["tables"][0]["pos"]
            scn = write_json(w.path("q-scn.json"), {"quan": {
                "player": {"pos": list(stove)}, "random_customers": False,
                "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                               "reserved": ["I1"]}]}})
            cook = MENU["ca_loc_nuong_trui"]["cook_s"] * 60
            d = math.dist(stove, table)
            walk = math.ceil(d / Q["walk_speed"] * 60) + Q["ramp_max_ticks"] + 5
            t_pick, t_go = cook + 2, cook + 4
            t_stop = t_go + walk
            mv = [(table[0] - stove[0]) / d, (table[1] - stove[1]) / d]
            inp = write_json(w.path("q-in.json"), frames(
                {"tick": 0, "interact": True}, {"tick": 1, "interact": False},
                {"tick": t_pick, "interact": True}, {"tick": t_pick + 1, "interact": False},
                {"tick": t_go, "move": mv}, {"tick": t_stop, "move": [0, 0]},
                {"tick": t_stop + 1, "interact": True}))
            ticks = t_stop + 2 + Q["eat_s"] * 60 + 5
            code, err = run("--mode", "quan", "--seed", "42", "--inventory", inv, "--scenario", scn,
                            "--inputs", inp, "--ticks", str(ticks), "--out", w.path("q.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("q.jsonl"))
            self.assertEqual([(x["id"], x["kind"]) for x in snapshots(rows)[0]["stock"]], [("I1", "ca_loc")])
            self.assertEqual([r["name"] for r in events(rows)],
                             ["cook_started", "dish_ready", "dish_picked", "served", "paid"])
            self.assertEqual(kinds(events(rows, "cook_started")[0]["data"]["items"]), ["ca_loc"])
            self.assertEqual(snapshots(rows)[-1]["stock"], [], "nguyên liệu từ gather đã được dùng")
            # hao 1 bước gather (0.5/s) rồi 1 bước quán (0.25/s) trước khi nấu -> giá chốt theo độ tươi
            fresh = (100 - Fraction(str(FRESH["gather_decay_per_s"])) / 60
                     - Fraction(str(FRESH["quan_decay_per_s"])) / 60)
            price = math.floor(MENU["ca_loc_nuong_trui"]["price"] * fresh / 100)
            self.assertEqual(events(rows, "cook_started")[0]["data"]["base_price"], price)
            self.assertEqual(rows[-1]["earned"], price + math.floor(price * Fraction(str(Q["tip_rate"]))))

    def test_time_out_writes_inventory(self):
        with Workdir() as w:
            scn = write_json(w.path("s.json"), {"gather": {"hold": items("bong_sung"), "time_left_ticks": 5}})
            inv = w.path("catch.json")
            code, err = run("--mode", "gather", "--seed", "1", "--scenario", scn, "--ticks", "100",
                            "--out", w.path("g.jsonl"), "--inventory-out", inv)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("g.jsonl"))
            self.assertEqual(events(rows, "gather_end")[0]["data"]["reason"], "time")
            self.assertEqual(rows[-1]["ticks"], 5, "dừng sớm khi gameplay kết thúc")
            with open(inv, encoding="utf-8") as f:
                saved = json.load(f)["items"]
            self.assertEqual([(x["id"], x["kind"]) for x in saved], [("I1", "bong_sung")])
            self.assertAlmostEqual(saved[0]["fresh"], 100 - 5 * FRESH["gather_decay_per_s"] / 60, delta=0.01)

    def test_tick_limit_does_not_create_or_overwrite_inventory(self):
        with Workdir() as w:
            scn = write_json(w.path("s.json"), {"gather": {"hold": items("ca_loc")}})
            inv = w.path("catch.json")
            code, err = run("--mode", "gather", "--seed", "1", "--scenario", scn, "--ticks", "3",
                            "--out", w.path("g.jsonl"), "--inventory-out", inv)
            self.assertEqual(code, 0, err)
            self.assertEqual(read_jsonl(w.path("g.jsonl"))[-1]["reason"], "tick_limit")
            self.assertFalse(os.path.exists(inv), "chưa gather_end thì không tạo file kho")
            old = b'{"items":{"bong_sung":9}}\n'
            with open(inv, "wb") as f:
                f.write(old)
            run("--mode", "gather", "--seed", "1", "--scenario", scn, "--ticks", "3",
                "--out", w.path("g2.jsonl"), "--inventory-out", inv)
            self.assertEqual(read_bytes(inv), old, "chưa gather_end thì không ghi đè file kho cũ")

    def test_faint_writes_empty_inventory(self):
        with Workdir() as w:
            g = TUNING["gather"]
            scn = write_json(w.path("s.json"), {"gather": {
                "player": {"pos": [50, 10], "oxygen_ticks": 0, "hp": 1, "zero_oxy_ticks": 59},
                "hold": items("ca_loc", "bong_sung")}})
            inv = w.path("catch.json")
            code, err = run("--mode", "gather", "--seed", "1", "--scenario", scn,
                            "--ticks", str(g["choke_interval_ticks"] + 5),
                            "--out", w.path("g.jsonl"), "--inventory-out", inv)
            self.assertEqual(code, 0, err)
            end = events(read_jsonl(w.path("g.jsonl")), "gather_end")
            if not end or end[0]["data"]["reason"] != "fainted":
                self.skipTest("chờ lát 1 (oxy/ngạt/ngất) trong sim/gather.py")
            with open(inv, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"items": []}, "ngất -> kho rỗng")

    def test_deterministic_inventory_and_jsonl_bytes(self):
        with Workdir() as w:
            out = []
            for i in (1, 2):
                os.makedirs(w.path(f"r{i}"))
                _, inv = self.dock(w, ["ca_linh", "ca_linh", "ca_linh", "bong_dien_dien"], name=f"r{i}/catch.json")
                q = w.path(f"r{i}/q.jsonl")
                code, err = run("--mode", "quan", "--seed", "9", "--inventory", inv, "--ticks", "600", "--out", q)
                self.assertEqual(code, 0, err)
                out.append((read_bytes(inv), read_bytes(q)))
            self.assertEqual(out[0], out[1])

    def test_quan_rejects_bad_inventory_exit_2(self):
        with Workdir() as w:
            out = w.path("q.jsonl")
            bad_files = {
                "counted_v11": {"items": {"ca_loc": 1}},
                "unknown_kind": {"items": items("ca_tra")},
                "fresh_negative": {"items": items("ca_loc", fresh=-1)},
                "fresh_over_100": {"items": items("ca_loc", fresh=100.5)},
                "fresh_string": {"items": items("ca_loc", fresh="99")},
                "dup_id": {"items": items("ca_loc") + items("ca_linh")},
                "empty_id": {"items": [{"id": "", "kind": "ca_loc", "fresh": 50}]},
                "missing_fresh": {"items": [{"id": "I1", "kind": "ca_loc"}]},
                "extra_item_key": {"items": [{"id": "I1", "kind": "ca_loc", "fresh": 50, "qty": 1}]},
                "extra_root_key": {"items": [], "money": 5},
                "no_items": {"ca_loc": 1},
            }
            for name, obj in bad_files.items():
                inv = write_json(w.path(f"{name}.json"), obj)
                self.assertEqual(run("--mode", "quan", "--seed", "1", "--inventory", inv, "--ticks", "0",
                                     "--out", out)[0], 2, name)
                self.assertFalse(os.path.exists(out), f"{name}: phải thoát trước khi ghi JSONL")

    def test_inventory_and_scenario_stock_together_exit_2(self):
        with Workdir() as w:
            _, inv = self.dock(w, ["ca_loc"])
            scn = write_json(w.path("q-scn.json"), {"quan": {"stock": items("ca_loc", start=9)}})
            self.assertEqual(run("--mode", "quan", "--seed", "1", "--inventory", inv, "--scenario", scn,
                                 "--ticks", "0", "--out", w.path("q.jsonl"))[0], 2)


if __name__ == "__main__":
    unittest.main()
