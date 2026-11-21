"""Test Phase 2 (v1.1) phần TV1: cá bơi/phản xạ/sinh cá, Cá Sấu Năm Chèo, nút kèo nèo & cá kèo."""

import json
import math
import unittest

from chonoi.contract import load_contract
from chonoi.ids import IdAllocator
from chonoi.rng import Streams
from chonoi.sim.gather import GatherSim
from helpers import Workdir, close, events, frames, items, kinds, read_jsonl, run_headless, snapshots, write_json


class GatherP2Fish(unittest.TestCase):
    def test_initial_8_fish_distinct_positions_and_6_nodes(self):
        with Workdir() as w:
            code, err = run_headless("--mode", "gather", "--seed", "7", "--ticks", "0", "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            s = snapshots(read_jsonl(w.path("o.jsonl")))[0]
            self.assertEqual(len(s["fish"]), 8)
            pts = {tuple(f["pos"]) for f in s["fish"]}
            self.assertEqual(len(pts), 8)
            self.assertEqual(len(s["nodes"]), 6)
            self.assertEqual({n["kind"] for n in s["nodes"]}, {"bong_dien_dien", "bong_sung", "keo_neo"})
            self.assertEqual(len(s["monsters"]), 1)
            self.assertEqual(s["monsters"][0]["id"], "M1")

    def test_fish_swim_reflect_at_edge_and_turn_at_120(self):
        with Workdir() as w:
            # Đặt 1 đàn cá linh gần mép phải x=95.98, heading=0 -> bước 1 chạm 96 và phản xạ về trái (heading=180)
            sc = write_json(w.path("sc.json"), {"gather": {
                "fish": [{"id": "F1", "kind": "ca_linh", "pos": [95.99, 6.0], "heading_deg": 0}],
                "monsters": [],
            }})
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "125", "--scenario", sc,
                                     "--snapshot-every", "1", "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            snaps = {r["tick"]: r for r in snapshots(read_jsonl(w.path("o.jsonl")))}
            f1 = snaps[1]["fish"][0]
            self.assertTrue(close(f1["heading_deg"], 180.0, 0.5), f1)
            self.assertLessEqual(f1["pos"][0], 96.0)
            # Tại tick 119 heading vẫn là 180, tick 120 đổi hướng theo seed
            self.assertTrue(close(snaps[119]["fish"][0]["heading_deg"], 180.0, 0.5))
            self.assertNotAlmostEqual(snaps[120]["fish"][0]["heading_deg"], 180.0, places=1)

    def test_fish_spawns_at_360_up_to_max_12_and_deterministic(self):
        with Workdir() as w:
            for i in (1, 2):
                code, err = run_headless("--mode", "gather", "--seed", "42", "--ticks", "1800",
                                         "--out", w.path(f"o{i}.jsonl"))
                self.assertEqual(code, 0, err)
            with open(w.path("o1.jsonl"), "rb") as a, open(w.path("o2.jsonl"), "rb") as b:
                self.assertEqual(a.read(), b.read())
            rows = read_jsonl(w.path("o1.jsonl"))
            spawns = events(rows, "fish_spawned")
            # Đầu ca 8 đàn, trần 12 -> sinh tối đa 4 đàn ở tick 360, 720, 1080, 1440 (tick 1800 đã đạt trần 12)
            self.assertEqual([e["tick"] for e in spawns], [360, 720, 1080, 1440])
            self.assertEqual(len(snapshots(rows)[-1]["fish"]), 12)

    def test_random_fish_false_keeps_fixture_fish_static(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "fish": [{"id": "F1", "kind": "ca_keo", "pos": [20, 24], "heading_deg": 0}],
                "random_fish": False,
                "monsters": [],
            }})
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "400", "--scenario", sc,
                                     "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual(events(rows, "fish_spawned"), [])
            self.assertEqual(snapshots(rows)[-1]["fish"][0]["pos"], [20, 24])


class GatherP2Monsters(unittest.TestCase):
    def test_day_3_spawns_two_crocodiles(self):
        tuning = load_contract()["tuning"]
        g1 = GatherSim(tuning, {}, Streams(1), IdAllocator(), day=1)
        g3 = GatherSim(tuning, {}, Streams(1), IdAllocator(), day=3)
        self.assertEqual([m["id"] for m in g1.monsters], ["M1"])
        self.assertEqual([m["id"] for m in g3.monsters], ["M1", "M2"])

    def test_monster_patrol_chase_hit_lifo_drop_invuln_and_recoil(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [60, 24], "hp": 3},
                # v1.2: giỏ là cá thể I1..I5; 5 -> mất floor(5/2)=2 theo LIFO (I5 rồi I4)
                "hold": items("ca_loc", "bong_sung", "ca_linh", "ca_keo", "keo_neo"),
                "random_fish": False,
                "monsters": [{"id": "M1", "kind": "ca_sau", "pos": [61, 24],
                              "waypoints": [[60, 24], [64, 24]], "target_idx": 1, "state": "patrol"}],
            }})
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "65", "--scenario", sc,
                                     "--snapshot-every", "1", "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            hits = events(rows, "monster_hit")
            # Chỉ 1 hit trong 65 tick do invuln 90 tick & recoil 60 tick
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["tick"], 1)
            self.assertEqual(hits[0]["data"]["monster_id"], "M1")
            self.assertEqual(hits[0]["data"]["hp"], 2)
            lost = hits[0]["data"]["lost"]  # v1.2: mảng cá thể theo thứ tự bỏ
            self.assertEqual([(x["id"], x["kind"]) for x in lost], [("I5", "keo_neo"), ("I4", "ca_keo")])
            snaps = {r["tick"]: r for r in snapshots(rows)}
            self.assertEqual(snaps[1]["player"]["invuln_ticks"], 90)
            self.assertEqual(snaps[1]["monsters"][0]["state"], "recoil")
            self.assertEqual(snaps[1]["monsters"][0]["state_ticks_left"], 60)
            # Sau 60 bước recoil (tại tick 61), về patrol
            self.assertEqual(snaps[61]["monsters"][0]["state"], "patrol")
            self.assertIsNone(snaps[61]["monsters"][0]["recoil_dir"])

    def test_monster_hit_causes_faint_and_empty_inventory(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [60, 24], "hp": 1},
                "hold": items("ca_loc", "bong_sung", "ca_linh"),  # mất 1 khi hit (I3), còn 2 khi faint LIFO
                "random_fish": False,
                "monsters": [{"id": "M1", "kind": "ca_sau", "pos": [60, 24],
                              "waypoints": [[60, 24], [64, 24]]}],
            }})
            inv = w.path("inv.json")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "10", "--scenario", sc,
                                     "--inventory-out", inv, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual([e["name"] for e in events(rows)], ["monster_hit", "faint", "gather_end"])
            self.assertEqual(kinds(events(rows, "monster_hit")[0]["data"]["lost"]), ["ca_linh"])
            faint = events(rows, "faint")[0]["data"]
            self.assertEqual((faint["cause"], faint["hp"]), ("monster", 0))
            self.assertEqual([x["id"] for x in faint["lost"]], ["I2", "I1"], "LIFO: vào sau bỏ trước")
            self.assertEqual(rows[-1]["reason"], "fainted")
            with open(inv, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"items": []}, "v1.2: kho rỗng là mảng rỗng")

    def test_monster_ignores_player_above_depth_10(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [60, 9.5], "hp": 3},
                "random_fish": False,
                "monsters": [{"id": "M1", "kind": "ca_sau", "pos": [60, 10.5],
                              "waypoints": [[60, 10.5], [64, 10.5]]}],
            }})
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "10", "--scenario", sc,
                                     "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual(events(rows, "monster_hit"), [])
            self.assertEqual(snapshots(rows)[-1]["monsters"][0]["state"], "patrol")


if __name__ == "__main__":
    unittest.main()
