"""`--mode day` (TICKET-02 mục 2, Test Contract v1.1 mục 4) — vòng ngày, Shop, nâng cấp, pause — TV3.

Tự skip cho tới khi game.contract.json có tuning.day_plan và tuning.shop. Mọi số đọc từ tuning.
"""

import os
import subprocess
import sys
import unittest

from chonoi.contract import load_contract
from chonoi.inputs import InputState

from helpers import ROOT, Workdir, counts, events, frames, headless_cmd, items, kinds, read_jsonl, snapshots, write_json

# TICKET-03 (v1.2) [THAY THẾ]: gather.hold / stock là mảng cá thể {id, kind, fresh}. Fixture đổi sang items(...),
# so lượng bằng counts(...), so id khi luật v1.2 quy định id (Ngày đầu giữ id mẫu, Ngày kế cấp id mới).
HOLD3 = items("ca_loc", "bong_sung", "bong_sung")  # I1, I2, I3

TUNING = load_contract()["tuning"]
DAY_READY = "day_plan" in TUNING and "shop" in TUNING
SKIP = "chờ contract v1.1 có tuning.day_plan và tuning.shop"
if DAY_READY:
    from chonoi.sim.day import DaySession
    SHOP = TUNING["shop"]
    PLAN = {e["day"]: e for e in TUNING["day_plan"]}
    G, Q = TUNING["gather"], TUNING["quan"]


def inp(interact=False, shop_done=False, pause=False, buy=None):
    edges = {n for n, on in (("interact", interact), ("shop_done", shop_done), ("pause", pause)) if on}
    return InputState((0.0, 0.0), {}, edges, buy)


def names(rows):
    return [r["name"] for r in rows]


def price(kind, level):
    return next(e for e in SHOP["upgrades"][kind] if e["level"] == level)["price"]


def to_shop(s):
    """Bước không input tới khi vào Shop; trả các dòng event đã qua."""
    rows = []
    while s.phase != "shop":
        rows += s.step(inp())
    return rows


def docked(days=1, quan_ticks=3, **day):
    """Ngày cập bến ngay ở bước 0 với giỏ dựng sẵn, ca quán rút ngắn để nhanh tới Shop."""
    scn = {"gather": {"hold": [dict(it) for it in HOLD3]}, "quan": {"time_left_ticks": quan_ticks}}
    if day:
        scn["day"] = day
    s = DaySession(TUNING, scn, 1, days)
    s.step(inp(interact=True))
    return s


def run(*args):
    cmd = headless_cmd()
    if cmd and cmd[0] in ("python3", "python"):
        cmd = [sys.executable, *cmd[1:]]
    p = subprocess.run([*cmd, *args], cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stderr


@unittest.skipUnless(DAY_READY, SKIP)
class DayLoop(unittest.TestCase):
    def test_start_of_day_events_and_snapshot(self):
        s = DaySession(TUNING, {}, 1, 1)
        rows = s.initial_rows
        self.assertEqual([(r["name"], r["tick"], r["phase"], r["day"]) for r in rows],
                         [("day_start", 0, "gather", 1), ("day_plan", 0, "gather", 1), ("phase_start", 0, "gather", 1)])
        self.assertEqual(rows[1]["data"], {"dishes": PLAN[1]["dishes"], "ingredients": PLAN[1]["ingredients"]})
        snap = s.snapshot()
        self.assertEqual((snap["mode"], snap["phase"], snap["phase_tick"], snap["day"]), ("day", "gather", 0, 1))
        self.assertEqual((snap["upgrades"], snap["active_upgrades"], snap["money"], snap["earned"]), ({}, {}, 0, 0))
        self.assertEqual(snap["reputation"], Q["reputation_initial"])
        self.assertEqual(snap["day_plan"]["dishes"], PLAN[1]["dishes"])

    def test_dock_hands_over_stock_same_tick(self):
        s = DaySession(TUNING, {"gather": {"hold": [dict(it) for it in HOLD3]}}, 1, 1)
        rows = s.step(inp(interact=True))
        self.assertEqual([(r["name"], r["phase"], r["tick"]) for r in rows],
                         [("gather_end", "gather", 1), ("phase_start", "quan", 1)])
        snap = s.snapshot()
        self.assertEqual((snap["phase"], snap["phase_tick"], snap["sim_tick"]), ("quan", 0, 1))
        self.assertEqual([x["id"] for x in snap["stock"]], ["I1", "I2", "I3"], "Ngày đầu giữ id mẫu, bàn giao theo id")
        self.assertEqual(counts(snap["stock"]), {"bong_sung": 2, "ca_loc": 1})
        end = next(r for r in rows if r["name"] == "gather_end")["data"]["inventory"]["items"]
        for got, want in zip(snap["stock"], end):
            self.assertAlmostEqual(got["fresh"], want["fresh"], delta=0.01, msg="bàn giao cùng tick, không hao thêm")

    def test_faint_still_opens_quan_with_empty_stock(self):
        scn = {"gather": {"player": {"pos": [50, 10], "oxygen_ticks": 0, "hp": 1, "zero_oxy_ticks": 59},
                          "hold": items("ca_loc")}}
        s = DaySession(TUNING, scn, 1, 1)
        rows = s.step(inp())
        end = next(r for r in rows if r["name"] == "gather_end")
        self.assertEqual(end["data"]["reason"], "fainted")
        self.assertEqual(names(rows)[-1], "phase_start")
        self.assertEqual((s.phase, s.snapshot()["stock"]), ("quan", []))

    def test_quan_end_opens_shop_same_tick(self):
        s = docked()
        rows = to_shop(s)
        self.assertEqual(names(rows)[-2:], ["quan_end", "phase_start"])
        self.assertEqual((rows[-2]["phase"], rows[-1]["phase"]), ("quan", "shop"))
        snap = s.snapshot()
        self.assertEqual((snap["phase"], snap["phase_tick"], snap["time_left_ticks"]), ("shop", 0, SHOP["max_ticks"]))
        self.assertEqual(counts(snap["stock"]), {"bong_sung": 2, "ca_loc": 1}, "Shop hiện kho dư của ca")

    def test_shop_auto_closes_and_day_completes(self):
        s = docked()
        to_shop(s)
        t0 = s.tick
        rows = []
        while not s.done:
            rows += s.step(inp())
        self.assertEqual([(r["name"], r["data"]) for r in rows], [("shop_end", {"reason": "time"})])
        self.assertEqual(s.tick - t0, SHOP["max_ticks"])
        end = s.end_row()
        self.assertEqual((end["reason"], end["days_completed"], end["mode"]), ("days_complete", 1, "day"))

    def test_buy_processed_before_shop_done_same_step(self):
        p1 = price("oxygen", 1)
        s = docked(money=p1, earned=p1)
        to_shop(s)
        rows = s.step(inp(shop_done=True, buy="oxygen"))
        self.assertEqual([(r["name"], r["data"]) for r in rows],
                         [("bought", {"upgrade": "oxygen", "level": 1, "price": p1, "money": 0}),
                          ("shop_end", {"reason": "done"})])
        self.assertEqual((s.money, s.earned), (0, p1), "trừ money, giữ earned")
        self.assertEqual(s.end_row()["score"], p1 + 100 * int(Q["reputation_initial"]))

    def test_upgrade_visible_now_active_next_day(self):
        p1 = price("oxygen", 1)
        s = docked(days=2, money=p1, earned=p1)
        to_shop(s)
        s.step(inp(buy="oxygen"))
        snap = s.snapshot()
        self.assertEqual((snap["upgrades"], snap["active_upgrades"]), ({"oxygen": 1}, {}))
        rows = s.step(inp(shop_done=True))
        self.assertEqual(names(rows), ["shop_end", "day_start", "day_plan", "phase_start"])
        self.assertEqual([r["day"] for r in rows], [1, 2, 2, 2])
        self.assertEqual(rows[2]["data"]["dishes"], PLAN[2]["dishes"])
        snap = s.snapshot()
        want = next(e for e in SHOP["upgrades"]["oxygen"] if e["level"] == 1)["oxygen_max_s"] * 60
        self.assertEqual((snap["day"], snap["phase"], snap["active_upgrades"]), (2, "gather", {"oxygen": 1}))
        self.assertEqual((snap["player"]["oxygen_max_ticks"], snap["player"]["oxygen_ticks"]), (want, want))

    def test_hp_upgrade_refills_to_new_max_next_day(self):
        p1 = price("hp", 1)
        s = docked(days=2, money=p1, earned=p1)
        to_shop(s)
        s.step(inp(buy="hp", shop_done=True))
        want = next(e for e in SHOP["upgrades"]["hp"] if e["level"] == 1)["hp_max"]
        p = s.snapshot()["player"]
        self.assertEqual((p["hp_max"], p["hp"]), (want, want))

    def test_buy_failed_reasons(self):
        p1 = price("oxygen", 1)
        top = max(e["level"] for e in SHOP["upgrades"]["oxygen"])
        cases = [({"money": p1 - 1, "earned": p1 - 1}, "oxygen", "funds"),
                 ({"money": 10_000, "earned": 10_000, "upgrades": {"oxygen": top}}, "oxygen", "max_level"),
                 ({"money": 10_000, "earned": 10_000}, "laser", "unknown"),
                 ({"money": 10_000, "earned": 10_000}, "sell:ca_loc", "unknown")]
        for day, action, reason in cases:
            with self.subTest(reason=reason, action=action):
                s = docked(**day)
                to_shop(s)
                money = s.money
                rows = s.step(inp(buy=action))
                self.assertEqual([(r["name"], r["data"]) for r in rows],
                                 [("buy_failed", {"action": action, "reason": reason})])
                self.assertEqual(s.money, money, "tiền và cấp giữ nguyên")

    def test_money_earned_reputation_carry_over_days(self):
        s = docked(days=2, money=50, earned=80, reputation=4.0)
        snap = s.snapshot()
        self.assertEqual((snap["money"], snap["earned"], snap["reputation"]), (50, 80, 4.0))
        to_shop(s)
        s.step(inp(shop_done=True))
        snap = s.snapshot()
        self.assertEqual((snap["day"], snap["money"], snap["earned"], snap["reputation"]), (2, 50, 80, 4.0))
        self.assertEqual(kinds(snap["hold"]), ["ca_loc", "bong_sung", "bong_sung"],
                         "giỏ Ngày mới dựng lại từ mẫu gather (TICKET-02 4.3), không mang kho dư Ngày trước")
        self.assertEqual([x["id"] for x in snap["hold"]], ["I4", "I5", "I6"],
                         "v1.2: Ngày kế cấp id mới theo thứ tự mảng, nối tiếp xuyên Ngày")
        self.assertEqual([x["fresh"] for x in snap["hold"]], [100, 100, 100], "kind/fresh ban đầu của mẫu")

    def test_pause_in_shop_freezes_timer_and_ignores_buy(self):
        s = docked(money=10_000, earned=10_000)
        to_shop(s)
        self.assertEqual(names(s.step(inp(pause=True))), ["paused"])
        left = s.snapshot()["time_left_ticks"]
        sim_tick = s.sim_tick
        for _ in range(SHOP["max_ticks"] + 5):
            self.assertEqual(s.step(inp(buy="oxygen", shop_done=True)), [], "đang pause: bỏ qua buy và shop_done")
        snap = s.snapshot()
        self.assertEqual((snap["state"], snap["time_left_ticks"], snap["sim_tick"]), ("paused", left, sim_tick))
        self.assertEqual(snap["upgrades"], {})
        rows = s.step(inp(pause=True, buy="oxygen"))
        self.assertEqual(names(rows), ["resumed", "bought"], "resume chạy gameplay ngay trong bước đó")

    def test_scenario_day_plan_override_recomputes_ingredients(self):
        dishes = {"goi_bong_sung": 1}
        s = DaySession(TUNING, {"day": {"day_plan": [{"day": 1, "dishes": dishes}]}}, 1, 1)
        plan = next(r for r in s.initial_rows if r["name"] == "day_plan")["data"]
        recipe = TUNING["menu"]["goi_bong_sung"]["recipe"]
        self.assertEqual(plan, {"dishes": dishes, "ingredients": dict(recipe)})

    def test_quan_in_day_only_serves_plan_dishes(self):
        # D1 không có lẩu: dù kho đủ lẩu, khách chỉ được gọi món trong kế hoạch
        hold = items("ca_linh", "ca_linh", "ca_linh", "bong_dien_dien", "ca_loc")
        s = DaySession(TUNING, {"gather": {"hold": hold}}, 1, 1)
        s.step(inp(interact=True))
        dishes = set()
        while s.phase == "quan" and len(dishes) < 1:
            dishes |= {r["data"]["dish_id"] for r in s.step(inp()) if r["name"] == "customer_arrived"}
        self.assertTrue(dishes)
        self.assertTrue(dishes <= set(PLAN[1]["dishes"]), dishes)


@unittest.skipUnless(DAY_READY, SKIP)
class DayHeadless(unittest.TestCase):
    def test_two_days_no_input_complete_and_deterministic(self):
        per_day = G["duration_s"] * 60 + Q["duration_s"] * 60 + SHOP["max_ticks"]
        with Workdir() as w:
            outs = []
            for i in (1, 2):
                out = w.path(f"d{i}.jsonl")
                code, err = run("--mode", "day", "--days", "2", "--seed", "5", "--ticks", str(3 * per_day),
                                "--snapshot-every", "600", "--out", out)
                self.assertEqual(code, 0, err)
                with open(out, "rb") as f:
                    outs.append(f.read())
            self.assertEqual(outs[0], outs[1], "cùng seed -> giống từng byte")
            rows = read_jsonl(w.path("d1.jsonl"))
            end = rows[-1]
            self.assertEqual((end["reason"], end["days_completed"], end["ticks"]), ("days_complete", 2, 2 * per_day))
            self.assertLessEqual(end["ticks"] / 2, 22200, "một Ngày không pause ≤ 22.200 tick")
            starts = [(r["day"], r["phase"]) for r in events(rows, "phase_start")]
            self.assertEqual(starts, [(1, "gather"), (1, "quan"), (1, "shop"), (2, "gather"), (2, "quan"), (2, "shop")])
            self.assertEqual([r["data"]["reason"] for r in events(rows, "shop_end")], ["time", "time"])
            self.assertTrue(all("day" in r for r in events(rows)), "vỏ event của day có trường day")
            snaps = snapshots(rows)
            self.assertTrue(all(k in snaps[0] for k in ("day", "day_plan", "upgrades", "active_upgrades")))

    def test_cli_rejects_bad_day_flags(self):
        with Workdir() as w:
            out = w.path("o.jsonl")
            inv = write_json(w.path("inv.json"), {"items": []})
            bad = [["--days", "0"], ["--days", "6"], ["--inventory", inv], ["--inventory-out", w.path("x.json")]]
            for extra in bad:
                with self.subTest(extra=extra):
                    self.assertEqual(run("--mode", "day", "--seed", "1", "--ticks", "0", "--out", out, *extra)[0], 2)
                    self.assertFalse(os.path.exists(out))

    def test_ticks_zero_builds_day_and_writes_start_events(self):
        with Workdir() as w:
            out = w.path("o.jsonl")
            code, err = run("--mode", "day", "--seed", "1", "--ticks", "0", "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            self.assertEqual([r.get("name", r["type"]) for r in rows],
                             ["day_start", "day_plan", "phase_start", "snapshot", "end"])
            self.assertEqual((rows[-1]["reason"], rows[-1]["days_completed"]), ("tick_limit", 0))


@unittest.skipUnless(DAY_READY, SKIP)
class DayScenario(unittest.TestCase):
    """Khối day của scenario (v1.1 mục 4.3), chạy hộp đen qua headless."""

    def test_ticket_example_opens_day_with_money_and_hold(self):
        # đúng ví dụ TICKET-02 mục 4.3: tương tác lúc ở bến đóng ca sáng ngay
        scn_obj = {"day": {"money": 200, "earned": 200},
                   "gather": {"hold": [dict(it) for it in HOLD3], "random_fish": False}}
        with Workdir() as w:
            scn = write_json(w.path("s.json"), scn_obj)
            inp_f = write_json(w.path("i.json"), frames({"tick": 0, "interact": True}))
            out = w.path("o.jsonl")
            code, err = run("--mode", "day", "--seed", "1", "--scenario", scn, "--inputs", inp_f, "--ticks", "1",
                            "--out", out)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(out)
            self.assertEqual([(r["name"], r["phase"]) for r in events(rows) if r["tick"] == 1],
                             [("gather_end", "gather"), ("phase_start", "quan")])
            snap = snapshots(rows)[-1]
            self.assertEqual((snap["phase"], snap["money"], snap["earned"]), ("quan", 200, 200))
            self.assertEqual(counts(snap["stock"]), {"bong_sung": 2, "ca_loc": 1})

    def test_scenario_upgrades_active_from_day_one(self):
        lv1 = next(e for e in SHOP["upgrades"]["hp"] if e["level"] == 1)
        s = DaySession(TUNING, {"day": {"upgrades": {"hp": 1}}}, 1, 1)
        snap = s.snapshot()
        self.assertEqual((snap["upgrades"], snap["active_upgrades"]), ({"hp": 1}, {"hp": 1}))
        self.assertEqual(snap["player"]["hp_max"], lv1["hp_max"])

    def test_bad_day_scenarios_exit_2(self):
        top = max(e["level"] for e in SHOP["upgrades"]["oxygen"])
        bad = {
            "quan_stock": {"quan": {"stock": items("ca_loc")}},
            "quan_reputation": {"quan": {"reputation": 4.0}},
            "money_gt_earned": {"day": {"money": 100, "earned": 50}},
            "money_without_earned": {"day": {"money": 100}},
            "unknown_upgrade": {"day": {"upgrades": {"laser": 1}}},
            "upgrade_over_max": {"day": {"upgrades": {"oxygen": top + 1}}},
            "unknown_day_key": {"day": {"gold": 1}},
            "wrong_block": {"river": {}},
            "plan_bad_ingredients": {"day": {"day_plan": [{"day": 1, "dishes": {"goi_bong_sung": 1},
                                                           "ingredients": {"bong_sung": 3}}]}},
            "plan_dish_off_menu": {"day": {"day_plan": [{"day": 1, "dishes": {"pho": 1}}]}},
        }
        with Workdir() as w:
            out = w.path("o.jsonl")
            for name, obj in bad.items():
                with self.subTest(name):
                    scn = write_json(w.path(f"{name}.json"), obj)
                    code, _ = run("--mode", "day", "--seed", "1", "--scenario", scn, "--ticks", "0", "--out", out)
                    self.assertEqual(code, 2)
                    self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
