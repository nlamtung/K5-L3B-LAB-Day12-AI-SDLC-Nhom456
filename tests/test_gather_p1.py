"""Test luật buổi sáng (gather) Phase 1 — Lát 1 & Lát 2 (PRD-0 mục E, F, G)."""

import json
import unittest

from helpers import Workdir, events, frames, items, kinds, read_jsonl, run_headless, snapshots, write_json

# TICKET-03 (v1.2) [THAY THẾ]: giỏ / kho / lost là mảng cá thể {id, kind, fresh} — fixture và so sánh đổi theo,
# thứ tự và lượng giữ nguyên ý nghĩa P1.


class GatherSlice1OxygenAndFaint(unittest.TestCase):
    def test_dive_surface_and_oxygen_refill(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {"player": {"pos": [20, 0.4], "oxygen_ticks": 100}}})
            inp = write_json(w.path("in.json"), frames({"tick": 0, "move": [0, 1]}, {"tick": 20, "move": [0, -1]}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "60", "--scenario", sc,
                                     "--inputs", inp, "--snapshot-every", "1", "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            dives = events(rows, "dive")
            surfaces = events(rows, "surface")
            self.assertEqual(len(dives), 1)
            self.assertEqual(len(surfaces), 1)
            self.assertGreater(dives[0]["data"]["pos"][1], 0.5)
            self.assertLessEqual(surfaces[0]["data"]["pos"][1], 0.5)
            self.assertGreater(surfaces[0]["tick"], dives[0]["tick"])
            # Oxy sau khi nổi lên phải tăng lên
            snaps = {r["tick"]: r for r in snapshots(rows)}
            t_surf = surfaces[0]["tick"]
            self.assertGreater(snaps[t_surf]["player"]["oxygen_ticks"], snaps[t_surf - 1]["player"]["oxygen_ticks"])

    def test_choke_timing_exact_t_plus_59(self):
        """Chạm oxy 0 ở tick t và ở dưới nước liên tục -> choke lần đầu ở t + 59."""
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {"player": {"pos": [20, 10], "oxygen_ticks": 1, "hp": 3}}})
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "70", "--scenario", sc,
                                     "--snapshot-every", "1", "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            empty = events(rows, "oxygen_empty")
            chokes = events(rows, "choke")
            self.assertEqual(len(empty), 1)
            self.assertEqual(empty[0]["tick"], 1)
            self.assertEqual(empty[0]["data"], {"oxygen_ticks": 0})
            self.assertEqual(len(chokes), 1)
            self.assertEqual(chokes[0]["tick"], 60)  # t=1 -> t+59=60
            self.assertEqual(chokes[0]["data"], {"hp": 2})

    def test_surface_on_choke_tick_prevents_choke(self):
        """Nổi lên đúng bước đáng lẽ ngạt thì hồi oxy và không ngạt."""
        with Workdir() as w:
            # d = 0.55, đang bơi lên với vel = [0, -4] -> 1 bước giảm d đi 4/60 = 0.0667 -> d <= 0.5
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [20, 0.55], "vel": [0, -4], "oxygen_ticks": 0, "zero_oxy_ticks": 59, "hp": 1},
            }})
            inp = write_json(w.path("in.json"), frames({"tick": 0, "move": [0, -1]}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc,
                                     "--inputs", inp, "--snapshot-every", "1", "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual(events(rows, "choke"), [])
            self.assertEqual(events(rows, "faint"), [])
            self.assertEqual(len(events(rows, "surface")), 1)
            p = snapshots(rows)[-1]["player"]
            self.assertEqual(p["oxygen_ticks"], 6)
            self.assertEqual(p["zero_oxy_ticks"], 0)
            self.assertEqual(p["hp"], 1)

    def test_faint_drops_hold_lifo_and_writes_empty_inventory(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [20, 10], "oxygen_ticks": 0, "zero_oxy_ticks": 59, "hp": 1},
                "hold": items("ca_loc", "bong_sung", "ca_linh"),
            }})
            inv = w.path("inv.json")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "10", "--scenario", sc,
                                     "--inventory-out", inv, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual([e["name"] for e in events(rows)], ["choke", "faint", "gather_end"])
            faint = events(rows, "faint")[0]["data"]
            self.assertEqual((faint["cause"], faint["hp"]), ("choke", 0))
            self.assertEqual([(x["id"], x["kind"]) for x in faint["lost"]],
                             [("I3", "ca_linh"), ("I2", "bong_sung"), ("I1", "ca_loc")], "LIFO")
            end_ev = events(rows, "gather_end")[0]["data"]
            self.assertEqual(end_ev, {"reason": "fainted", "inventory": {"items": []}})
            self.assertEqual(rows[-1]["reason"], "fainted")
            with open(inv, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"items": []})


class GatherSlice2NodesAndFish(unittest.TestCase):
    def test_gather_tie_break_regrow_and_immediate_reharvest(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [20, 0]},
                "nodes": [
                    {"id": "N10", "kind": "bong_sung", "pos": [22, 0]},
                    {"id": "N2", "kind": "bong_dien_dien", "pos": [18, 0]},
                ],
                "fish": [],
                "random_fish": False,
            }})
            # N2 và N10 cùng cách 2.0m (đúng mép interact_radius) -> chọn N2 trước; N2 mọc lại sau 20*60=1200 tick
            inp = write_json(w.path("in.json"), frames(
                {"tick": 0, "interact": True},
                {"tick": 1, "interact": False},
                {"tick": 1200, "interact": True},
            ))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1201", "--scenario", sc,
                                     "--inputs", inp, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            gathers = events(rows, "gather")
            regrowns = events(rows, "node_regrown")
            self.assertEqual(len(gathers), 2)
            self.assertEqual(gathers[0]["tick"], 1)
            self.assertEqual(gathers[0]["data"], {"node_id": "N2", "kind": "bong_dien_dien", "amount": 1})
            self.assertEqual(len(regrowns), 1)
            self.assertEqual(regrowns[0]["tick"], 1201)
            self.assertEqual(regrowns[0]["data"], {"node_id": "N2"})
            # Hái ngay ở tick mọc lại (1201) -> N2 vẫn thắng N10 theo id_key
            self.assertEqual(gathers[1]["tick"], 1201)
            self.assertEqual(gathers[1]["data"]["node_id"], "N2")

    def test_gather_hold_full_keeps_node_ready(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [12, 0]},
                "hold": items(*["ca_loc"] * 12),
                "nodes": [{"id": "N1", "kind": "bong_dien_dien", "pos": [12, 0]}],
            }})
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc,
                                     "--inputs", inp, "--snapshot-every", "1", "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual(events(rows, "gather"), [])
            hf = events(rows, "hold_full")
            self.assertEqual(len(hf), 1)
            self.assertEqual(hf[0]["data"], {"action": "gather", "node_id": "N1", "required": 1, "free": 0})
            self.assertTrue(snapshots(rows)[-1]["nodes"][0]["ready"])

    def test_catch_fish_yield_cooldown_and_tie_break(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [20, 10]},
                "fish": [
                    {"id": "F10", "kind": "ca_loc", "pos": [22, 10]},
                    {"id": "F2", "kind": "ca_linh", "pos": [18, 10]},
                ],
                "random_fish": False,
                "nodes": [],
            }})
            # Bắt F2 ở tick 0 (event tick 1), cooldown 30 -> tick 29 chưa bắt được, tick 30 (event tick 31) bắt F10
            inp = write_json(w.path("in.json"), frames(
                {"tick": 0, "catch": True},
                {"tick": 1, "catch": False},
                {"tick": 29, "catch": True},
                {"tick": 30, "catch": False},
                {"tick": 31, "catch": True},
            ))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "32", "--scenario", sc,
                                     "--inputs", inp, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            caught = events(rows, "fish_caught")
            self.assertEqual(len(caught), 2)
            self.assertEqual(caught[0]["tick"], 1)
            self.assertEqual(caught[0]["data"], {"fish_id": "F2", "kind": "ca_linh", "yield": 3})
            self.assertEqual(caught[1]["tick"], 32)
            self.assertEqual(caught[1]["data"], {"fish_id": "F10", "kind": "ca_loc", "yield": 1})
            last = snapshots(rows)[-1]
            self.assertEqual(last["fish"], [])
            self.assertEqual(kinds(last["hold"]), ["ca_linh", "ca_linh", "ca_linh", "ca_loc"])
            self.assertEqual([x["id"] for x in last["hold"]], ["I1", "I2", "I3", "I4"], "id cấp theo thứ tự vào giỏ")

    def test_catch_hold_full_keeps_fish_and_no_cooldown_and_no_fallback(self):
        """Gần nhất là ca_linh (cần 3) khi chỉ còn 2 ô -> hold_full, không bắt ca_loc xa hơn, giữ nguyên cooldown."""
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [20, 10]},
                "hold": items(*["bong_sung"] * 10),
                "fish": [
                    {"id": "F1", "kind": "ca_linh", "pos": [20.5, 10]},
                    {"id": "F2", "kind": "ca_loc", "pos": [21.5, 10]},
                ],
                "nodes": [],
            }})
            inp = write_json(w.path("in.json"), frames({"tick": 0, "catch": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc,
                                     "--inputs", inp, "--snapshot-every", "1", "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual(events(rows, "fish_caught"), [])
            hf = events(rows, "hold_full")
            self.assertEqual(len(hf), 1)
            self.assertEqual(hf[0]["data"], {"action": "catch", "fish_id": "F1", "required": 3, "free": 2})
            last = snapshots(rows)[-1]
            self.assertEqual(len(last["fish"]), 2)
            self.assertEqual(last["player"]["catch_cd_ticks"], 0)

    def test_catch_on_last_tick_included_in_inventory(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [20, 10]},
                "fish": [{"id": "F1", "kind": "ca_loc", "pos": [20, 10]}],
                "time_left_ticks": 1,
            }})
            inp = write_json(w.path("in.json"), frames({"tick": 0, "catch": True}))
            inv = w.path("inv.json")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "5", "--scenario", sc,
                                     "--inputs", inp, "--inventory-out", inv, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual([e["name"] for e in events(rows)], ["fish_caught", "gather_end"])
            with open(inv, encoding="utf-8") as f:
                saved = json.load(f)["items"]
            self.assertEqual([(x["id"], x["kind"]) for x in saved], [("I1", "ca_loc")])
            self.assertEqual(saved[0]["fresh"], 100, "bắt ở bước cuối: hàng mới, chưa hao")


if __name__ == "__main__":
    unittest.main()
