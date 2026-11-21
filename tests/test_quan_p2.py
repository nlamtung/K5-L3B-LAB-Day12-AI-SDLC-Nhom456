"""Test Phase 2 — phần TV2 (TICKET-02): 2 bếp / 4 bàn / 6 món / 6 nguyên liệu, kế hoạch Ngày (day_plan),
lọc món theo kế hoạch trong day, kiểm scenario khối `day` (Test Contract v1.1 mục 4.3).

`BlackBox` chỉ chạy headless_cmd. `Units` gọi thẳng QuanSim / contract / scenario (Python).
Số kỳ vọng của bảng kế hoạch D1–D5 chép từ TICKET-02 mục 2 để kiểm dữ liệu trong game.contract.json.
"""

import copy
import json
import os
import unittest

from helpers import ROOT, Workdir, events, frames, read_jsonl, run_headless, snapshots, write_json


def tuning():
    with open(os.path.join(ROOT, "game.contract.json"), encoding="utf-8") as f:
        return json.load(f)["tuning"]


T = tuning()
Q, MENU = T["quan"], T["menu"]
TICK = 60

# TICKET-02 mục 2, bảng "Món và số suất kế hoạch" / "Nguyên liệu cần" / "Số ô cần".
TICKET_PLAN = {
    1: ({"ca_loc_nuong_trui": 3, "goi_bong_sung": 3}, {"ca_loc": 3, "bong_sung": 6}, 9),
    2: ({"ca_loc_nuong_trui": 2, "lau_ca_linh_dien_dien": 2}, {"ca_loc": 2, "ca_linh": 6, "bong_dien_dien": 2}, 10),
    3: ({"goi_bong_sung": 2, "canh_chua_ca_loc": 2, "ca_keo_nuong": 2},
        {"bong_sung": 4, "ca_loc": 2, "bong_dien_dien": 2, "ca_keo": 4}, 12),
    4: ({"lau_mam": 1, "ca_loc_nuong_trui": 2, "goi_bong_sung": 1},
        {"ca_linh": 2, "ca_keo": 1, "keo_neo": 1, "bong_dien_dien": 1, "ca_loc": 2, "bong_sung": 2}, 9),
    5: ({"lau_mam": 1, "lau_ca_linh_dien_dien": 1, "ca_loc_nuong_trui": 1},
        {"ca_linh": 5, "ca_keo": 1, "keo_neo": 1, "bong_dien_dien": 2, "ca_loc": 1}, 10),
}


def ticks(s):
    return int(round(s * TICK))


def plenty_stock():
    total = {}
    for m in MENU.values():
        for k, n in m["recipe"].items():
            total[k] = total.get(k, 0) + 5 * n
    return total


def run_quan(w, block, n_ticks, seed=1, every=10, extra=()):
    args = ["--mode", "quan", "--seed", str(seed), "--ticks", str(n_ticks), "--snapshot-every", str(every),
            "--out", w.path("q.jsonl"), *extra]
    if block is not None:
        args += ["--scenario", write_json(w.path("sc.json"), {"quan": block})]
    code, err = run_headless(*args)
    return code, err, (read_jsonl(w.path("q.jsonl")) if code == 0 else None)


class BlackBox(unittest.TestCase):
    def test_bo_cuc_2_bep_4_ban_trong_snapshot(self):
        with Workdir() as w:
            code, err, rows = run_quan(w, None, 0)
            self.assertEqual(code, 0, err)
            s = snapshots(rows)[0]
            self.assertEqual([(x["id"], x["pos"]) for x in s["stoves"]], [("B1", [2, 8]), ("B2", [5, 8])])
            self.assertEqual([(x["id"], x["pos"]) for x in s["tables"]],
                             [("T1", [9, 2]), ("T2", [13, 2]), ("T3", [9, 6]), ("T4", [13, 6])])
            self.assertTrue(all(x["customer_id"] is None for x in s["tables"]))

    def test_khach_ngoi_ban_trong_id_nho_nhat_lan_luot_4_ban(self):
        """Lượt 120 + 900·k: T1, T2, T3, T4; lượt thứ 5 (3720) trùng lúc C1 hết kiên nhẫn -> C5 ngồi lại T1."""
        first, iv, pat = Q["first_customer_tick"], ticks(Q["customer_interval_s"]), ticks(Q["patience_s"])
        last = first + 4 * iv
        self.assertEqual(first + pat, last, "số chuẩn: khách đầu hết kiên nhẫn đúng lượt thứ 5")
        with Workdir() as w:
            code, err, rows = run_quan(w, {"stock": plenty_stock()}, last)
            self.assertEqual(code, 0, err)
            seq = [(e["tick"], e["name"], e["data"].get("order_id"), e["data"].get("table_id")) for e in events(rows)]
            self.assertEqual(seq, [(first, "customer_arrived", "C1", "T1"), (first + iv, "customer_arrived", "C2", "T2"),
                                   (first + 2 * iv, "customer_arrived", "C3", "T3"),
                                   (first + 3 * iv, "customer_arrived", "C4", "T4"),
                                   (last, "customer_left", "C1", "T1"), (last, "customer_arrived", "C5", "T1")])

    def test_mon_moi_ca_keo_nuong_khi_chi_co_ca_keo(self):
        with Workdir() as w:
            code, err, rows = run_quan(w, {"stock": dict(MENU["ca_keo_nuong"]["recipe"])}, Q["first_customer_tick"])
            self.assertEqual(code, 0, err)
            self.assertEqual(events(rows, "customer_arrived")[0]["data"]["dish_id"], "ca_keo_nuong")

    def test_kho_ca_keo_keo_neo_noi_gather_sang_quan(self):
        """6 nguyên liệu đi qua file kho: gather cập bến tick 0 -> quán đọc đúng (schema kho không đổi)."""
        with Workdir() as w:
            sc = write_json(w.path("dock.json"), {"gather": {"hold": ["ca_keo", "keo_neo", "ca_keo"]}})
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            inv = w.path("kho.json")
            code, err = run_headless("--mode", "gather", "--seed", "42", "--scenario", sc, "--inputs", inp, "--ticks", "1",
                                     "--out", w.path("g.jsonl"), "--inventory-out", inv)
            self.assertEqual(code, 0, err)
            with open(inv, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"items": {"ca_keo": 2, "keo_neo": 1}})
            code, err, rows = run_quan(w, None, 0, extra=("--inventory", inv))
            self.assertEqual(code, 0, err)
            self.assertEqual(snapshots(rows)[0]["stock"], {"ca_keo": 2, "keo_neo": 1})

    def test_nguyen_lieu_la_van_bi_tu_choi(self):
        with Workdir() as w:
            inv = write_json(w.path("inv.json"), {"items": {"ca_ho": 1}})
            self.assertEqual(run_quan(w, None, 0, extra=("--inventory", inv))[0], 2)


class Units(unittest.TestCase):
    def _sim(self, scenario, seed=1, plan=None, tuning=T):
        from chonoi.ids import IdAllocator
        from chonoi.rng import Streams
        from chonoi.sim.quan import QuanSim
        return QuanSim(tuning, scenario, Streams(seed), IdAllocator(), plan_dishes=plan)

    # --- dữ liệu chuẩn ---------------------------------------------------------------
    def test_contract_6_mon_dung_cong_thuc_ticket(self):
        want = {"ca_loc_nuong_trui": ({"ca_loc": 1}, 6, 60), "goi_bong_sung": ({"bong_sung": 2}, 4, 40),
                "lau_ca_linh_dien_dien": ({"ca_linh": 3, "bong_dien_dien": 1}, 10, 120),
                "canh_chua_ca_loc": ({"ca_loc": 1, "bong_dien_dien": 1}, 8, 90),
                "ca_keo_nuong": ({"ca_keo": 2}, 6, 70),
                "lau_mam": ({"ca_linh": 2, "ca_keo": 1, "keo_neo": 1, "bong_dien_dien": 1}, 12, 200)}
        self.assertEqual({k: (v["recipe"], v["cook_s"], v["price"]) for k, v in MENU.items()}, want)

    def test_day_plan_khop_bang_ticket(self):
        plan = T["day_plan"]
        self.assertEqual([p["day"] for p in plan], [1, 2, 3, 4, 5])
        for p in plan:
            dishes, ingredients, slots = TICKET_PLAN[p["day"]]
            self.assertEqual(p["dishes"], dishes, p["day"])
            self.assertEqual(p["ingredients"], ingredients, p["day"])
            self.assertEqual(sum(p["ingredients"].values()), slots, p["day"])

    def test_plan_ingredients_tinh_tu_cong_thuc(self):
        from chonoi.day_plan import plan_ingredients
        for p in T["day_plan"]:
            self.assertEqual(plan_ingredients(p["dishes"], MENU), dict(sorted(p["ingredients"].items())))

    def test_contract_day_plan_sai_bi_tu_choi(self):
        from chonoi.contract import validate_tuning
        from chonoi.errors import BadInput
        for mutate in (lambda t: t["day_plan"][0]["ingredients"].update({"ca_loc": 4}),
                       lambda t: t["day_plan"].pop(),
                       lambda t: t["day_plan"].reverse(),
                       lambda t: t["day_plan"][1]["dishes"].update({"pho_bo": 1}),
                       lambda t: t["day_plan"][2]["dishes"].update({"goi_bong_sung": 0}),
                       lambda t: t["day_plan"][3].update({"note": "x"}),
                       lambda t: t.pop("day_plan")):
            t = copy.deepcopy(T)
            mutate(t)
            with self.assertRaises(BadInput):
                validate_tuning(t)

    # --- lọc món theo kế hoạch (day) ------------------------------------------------
    def test_day_chi_chon_mon_trong_ke_hoach(self):
        d1 = T["day_plan"][0]["dishes"]
        chosen = {self._sim({"stock": plenty_stock()}, seed, plan=d1)._choose_dish() for seed in range(1, 60)}
        self.assertEqual(chosen, set(d1))

    def test_day_thieu_mon_ke_hoach_thi_no_dish_du_mon_khac_nau_duoc(self):
        from chonoi.inputs import InputPlayer
        d1 = T["day_plan"][0]["dishes"]  # cá lóc nướng trui, gỏi bông súng
        sim = self._sim({"stock": dict(MENU["ca_keo_nuong"]["recipe"])}, plan=d1)
        self.assertIsNone(sim._choose_dish())
        p, ev = InputPlayer([]), []
        for k in range(Q["first_customer_tick"]):
            ev += sim.step(p.advance(k))
        self.assertEqual(ev, [("no_dish", {})])
        self.assertEqual(self._sim({"stock": dict(MENU["ca_keo_nuong"]["recipe"])})._choose_dish(), "ca_keo_nuong",
                         "quán chạy riêng vẫn dùng cả 6 món")

    def test_day_mon_dung_san_ngoai_ke_hoach_ma_2(self):
        from chonoi.errors import BadInput
        d1 = T["day_plan"][0]["dishes"]
        payload = {"order_id": "C1", "dish_id": "lau_mam", "base_price": MENU["lau_mam"]["price"]}
        bad = [{"customers": [{"id": "C1", "table_id": "T1", "dish_id": "lau_mam"}]},
               {"customers": [{"id": "C1", "table_id": "T1", "dish_id": "lau_mam", "order_status": "assigned"}],
                "hand": payload},
               {"customers": [{"id": "C1", "table_id": "T1", "dish_id": "lau_mam", "order_status": "assigned"}],
                "stoves": [{"id": "B2", "state": "ready", "dish": payload}]}]
        for sc in bad:
            with self.assertRaises(BadInput):
                self._sim(dict(sc, stock=plenty_stock()), plan=d1)
        with self.assertRaises(BadInput):
            self._sim({"stock": plenty_stock()}, plan={"pho_bo": 1})
        ok = self._sim({"stock": plenty_stock(),
                        "customers": [{"id": "C1", "table_id": "T1", "dish_id": "goi_bong_sung"}]}, plan=d1)
        self.assertEqual(ok.customers[0]["reserved"], MENU["goi_bong_sung"]["recipe"])

    # --- scenario khối day (v1.1 mục 4.3) ---------------------------------------------
    def _day(self, data):
        import tempfile
        from chonoi.scenario import load_scenario
        with tempfile.TemporaryDirectory() as d:
            p = write_json(os.path.join(d, "sc.json"), data)
            return load_scenario(p, "day", T)

    def test_scenario_day_hop_le(self):
        ex = {"day": {"money": 200, "earned": 200},
              "gather": {"hold": ["ca_loc", "bong_sung", "bong_sung"], "random_fish": False}}
        got = self._day(ex)  # ví dụ trong TICKET-02 mục 4.3
        self.assertEqual(got["day"], ex["day"])
        self.assertEqual(got["gather"], ex["gather"])
        for data in ({}, {"day": {}}, {"day": {"earned": 50}}, {"day": {"reputation": Q["reputation_max"]}},
                     {"day": {"upgrades": {"oxygen": 1, "hp": 2}}},
                     {"day": {"day_plan": [{"day": 2, "dishes": {"lau_mam": 2}}]}},
                     {"day": {"day_plan": [{"day": 1, "dishes": {"ca_keo_nuong": 1}, "ingredients": {"ca_keo": 2}}]}},
                     {"quan": {"customers": [{"id": "C1", "table_id": "T4", "dish_id": "lau_mam"}]}}):
            self._day(data)

    def test_scenario_day_mau_thuan_ma_2(self):
        from chonoi.errors import BadInput
        bad = [
            {"day": {"money": 300, "earned": 200}}, {"day": {"money": 100}}, {"day": {"money": -1, "earned": 0}},
            {"day": {"earned": 1.5}}, {"day": {"reputation": Q["reputation_max"] + 1}}, {"day": {"day": 2}},
            {"day": {"upgrades": {"laser": 1}}}, {"day": {"upgrades": {"hp": -1}}}, {"day": {"upgrades": []}},
            {"day": {"day_plan": [{"day": 1, "dishes": {"pho_bo": 1}}]}},
            {"day": {"day_plan": [{"day": 6, "dishes": {"lau_mam": 1}}]}},
            {"day": {"day_plan": [{"day": 1, "dishes": {"lau_mam": 1}, "ingredients": {"ca_linh": 2}}]}},
            {"day": {"day_plan": [{"day": 1, "dishes": {"lau_mam": 1}}, {"day": 1, "dishes": {"goi_bong_sung": 1}}]}},
            {"day": {"day_plan": [{"day": 1}]}}, {"day": {"day_plan": {"day": 1}}},
            {"quan": {"stock": {"ca_loc": 1}}}, {"quan": {"reputation": 3}},
            {"gather": {"hold": ["ca_ho"]}}, {"quan": {"tables": [{"id": "T9"}]}}, {"river": {}},
        ]
        for data in bad:
            with self.assertRaises(BadInput, msg=data):
                self._day(data)

    def test_mode_le_van_tu_choi_khoi_day(self):
        from chonoi.errors import BadInput
        import tempfile
        from chonoi.scenario import load_scenario
        with tempfile.TemporaryDirectory() as d:
            p = write_json(os.path.join(d, "sc.json"), {"day": {"money": 0}})
            for mode in ("gather", "quan"):
                with self.assertRaises(BadInput):
                    load_scenario(p, mode, T)


if __name__ == "__main__":
    unittest.main()
