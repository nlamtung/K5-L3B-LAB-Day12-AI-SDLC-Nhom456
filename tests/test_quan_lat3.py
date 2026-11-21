"""Test Lát 3 quán (TV2) theo PRD-0 mục D, E, F: khách theo lịch phase_tick, chọn món, giữ chỗ, kiên nhẫn,
rời bàn (patience / closing), no_dish, fixture khách/đơn/bếp/tay và các mâu thuẫn → mã 2.

`BlackBox` chỉ chạy headless_cmd (dùng được với mọi ngôn ngữ). `Units` gọi thẳng QuanSim / contract (Python).
Số liệu đọc từ game.contract.json, không hard-code.
"""

import copy
import json
import os
import unittest

from helpers import ROOT, Workdir, events, read_jsonl, run_headless, snapshots, write_json


def tuning():
    with open(os.path.join(ROOT, "game.contract.json"), encoding="utf-8") as f:
        return json.load(f)["tuning"]


T = tuning()
Q, MENU = T["quan"], T["menu"]
TICK = 60
CUSTOMER_KEYS = ["id", "table_id", "dish_id", "order_tick", "state", "patience_ticks_left", "eat_ticks_left",
                 "order_status", "reserved", "base_price", "tip"]


def ticks(s):
    return int(round(s * TICK))


def cookable(stock):
    return sorted(d for d, m in MENU.items() if all(stock.get(k, 0) >= n for k, n in m["recipe"].items()))


def one_dish_stock():
    """Kho chỉ nấu được đúng một món (món có công thức ít nguyên liệu nhất)."""
    dish = min(sorted(MENU), key=lambda d: sum(MENU[d]["recipe"].values()))
    stock = dict(MENU[dish]["recipe"])
    assert cookable(stock) == [dish]
    return dish, stock


def plenty_stock():
    total = {}
    for m in MENU.values():
        for k, n in m["recipe"].items():
            total[k] = total.get(k, 0) + 5 * n
    return total


TABLE = sorted(t["id"] for t in Q["tables"])[0]
STOVE = sorted(s["id"] for s in Q["stoves"])[0]
DISH, DISH_STOCK = one_dish_stock()
PRICE = MENU[DISH]["price"]


def payload(order_id="C1", dish=DISH):
    return {"order_id": order_id, "dish_id": dish, "base_price": MENU[dish]["price"]}


def cust(**kw):
    return dict({"id": "C1", "table_id": TABLE, "dish_id": DISH}, **kw)


def run_quan(w, block, n_ticks, seed=1, every=10, extra=()):
    args = ["--mode", "quan", "--seed", str(seed), "--ticks", str(n_ticks), "--snapshot-every", str(every),
            "--out", w.path("q.jsonl"), *extra]
    if block is not None:
        args += ["--scenario", write_json(w.path("sc.json"), {"quan": block})]
    code, err = run_headless(*args)
    return code, err, (read_jsonl(w.path("q.jsonl")) if code == 0 else None)


def by_tick(rows):
    return {r["tick"]: r for r in snapshots(rows)}


class Arrivals(unittest.TestCase):
    def test_khach_dau_tien_den_dung_first_customer_tick(self):
        """F5: lượt khách ở first_customer_tick; bàn trống id nhỏ nhất; giữ đúng công thức; order_tick = phase_tick."""
        first = Q["first_customer_tick"]
        with Workdir() as w:
            code, err, rows = run_quan(w, {"stock": DISH_STOCK}, first + 1, every=1)
            self.assertEqual(code, 0, err)
            ev = events(rows, "customer_arrived")
            self.assertEqual([(e["tick"], e["data"]) for e in ev],
                             [(first, {"order_id": "C1", "table_id": TABLE, "dish_id": DISH})])
            self.assertEqual(events(rows, "no_dish"), [])
            s = by_tick(rows)
            self.assertEqual(s[first - 1]["customers"], [])
            c = s[first]["customers"][0]
            self.assertEqual(list(c), CUSTOMER_KEYS, "khách trong snapshot theo trường mục D")
            self.assertEqual((c["state"], c["order_status"], c["order_tick"]), ("waiting", "reserved", first))
            self.assertEqual(c["reserved"], MENU[DISH]["recipe"])
            self.assertEqual(c["patience_ticks_left"], ticks(Q["patience_s"]))
            self.assertEqual(s[first + 1]["customers"][0]["patience_ticks_left"], ticks(Q["patience_s"]) - 1,
                             "kiên nhẫn bắt đầu giảm từ bước sau")
            self.assertEqual(s[first]["stock"], DISH_STOCK, "stock là tồn vật lý, gồm cả phần giữ")
            self.assertEqual({t["id"]: t["customer_id"] for t in s[first]["tables"]}[TABLE], "C1")

    def test_lich_theo_phase_tick_ke_ca_khi_rut_ngan_ca(self):
        """D: lịch khách tính theo phase_tick kể cả khi rút ngắn ca."""
        first = Q["first_customer_tick"]
        with Workdir() as w:
            code, err, rows = run_quan(w, {"stock": DISH_STOCK, "time_left_ticks": first + 10}, first)
            self.assertEqual(code, 0, err)
            self.assertEqual([e["tick"] for e in events(rows, "customer_arrived")], [first])

    def test_no_dish_data_rong_khi_co_ban_ma_thieu_mon(self):
        with Workdir() as w:
            code, err, rows = run_quan(w, {"stock": {}}, Q["first_customer_tick"])
            self.assertEqual(code, 0, err)
            self.assertEqual([(e["tick"], e["data"]) for e in events(rows, "no_dish")], [(Q["first_customer_tick"], {})])
            self.assertEqual(snapshots(rows)[-1]["customers"], [])

    def test_random_customers_false_tat_khach_tu_sinh(self):
        with Workdir() as w:
            code, err, rows = run_quan(w, {"stock": DISH_STOCK, "random_customers": False}, Q["first_customer_tick"] + 5)
            self.assertEqual(code, 0, err)
            self.assertEqual(events(rows), [])

    def test_id_khach_moi_noi_tiep_id_fixture_va_giu_cho_duoc_nha(self):
        block = {"stock": DISH_STOCK, "customers": [cust(id="C7", patience_ticks_left=5)]}
        with Workdir() as w:
            code, err, rows = run_quan(w, block, Q["first_customer_tick"])
            self.assertEqual(code, 0, err)
            arr = events(rows, "customer_arrived")
            self.assertEqual([e["data"]["order_id"] for e in arr], ["C8"])
            self.assertEqual(arr[0]["data"]["dish_id"], DISH, "khách cũ rời thì phần giữ được nhả cho khách sau")

    def test_tat_dinh_cung_seed(self):
        n = Q["first_customer_tick"] + 3 * ticks(Q["customer_interval_s"]) + 1
        with Workdir() as w:
            outs = []
            for i in (1, 2):
                code, err = run_headless("--mode", "quan", "--seed", "9", "--ticks", str(n), "--out", w.path(f"o{i}.jsonl"),
                                         "--scenario", write_json(w.path("sc.json"), {"quan": {"stock": plenty_stock()}}))
                self.assertEqual(code, 0, err)
                with open(w.path(f"o{i}.jsonl"), "rb") as f:
                    outs.append(f.read())
            self.assertEqual(outs[0], outs[1])


class Leaving(unittest.TestCase):
    def test_het_kien_nhan_roi_ban_tru_uy_tin(self):
        block = {"stock": DISH_STOCK, "random_customers": False, "customers": [cust(patience_ticks_left=5)]}
        with Workdir() as w:
            code, err, rows = run_quan(w, block, 8, every=1)
            self.assertEqual(code, 0, err)
            rep = Q["reputation_initial"] + Q["left_reputation_delta"]
            self.assertEqual([(e["tick"], e["data"]) for e in events(rows, "customer_left")],
                             [(5, {"order_id": "C1", "table_id": TABLE, "reason": "patience", "reputation": rep})])
            s = by_tick(rows)
            self.assertEqual(s[4]["customers"][0]["patience_ticks_left"], 1)
            self.assertEqual(s[5]["customers"], [], "chỉ liệt kê khách còn ngồi")
            self.assertAlmostEqual(s[5]["reputation"], rep, delta=0.01)
            self.assertIsNone({t["id"]: t["customer_id"] for t in s[5]["tables"]}[TABLE])

    def test_het_ca_khach_cho_roi_closing_khong_tru_uy_tin(self):
        block = {"stock": DISH_STOCK, "random_customers": False, "time_left_ticks": 3, "customers": [cust()]}
        with Workdir() as w:
            code, err, rows = run_quan(w, block, 10)
            self.assertEqual(code, 0, err)
            ev = [(e["tick"], e["name"]) for e in events(rows)]
            self.assertEqual(ev, [(3, "customer_left"), (3, "quan_end")], "dọn xong mới phát quan_end")
            left = events(rows, "customer_left")[0]["data"]
            self.assertEqual((left["reason"], left["reputation"]), ("closing", Q["reputation_initial"]))
            self.assertEqual(rows[-1]["reason"], "time")

    def test_khach_roi_bo_mon_cua_don_tren_bep_va_tay(self):
        for where in ("stove", "hand"):
            block = {"stock": {}, "random_customers": False,
                     "customers": [cust(order_status="assigned", patience_ticks_left=1)]}
            if where == "stove":
                block["stoves"] = [{"id": STOVE, "state": "ready", "dish": payload()}]
            else:
                block["hand"] = payload()
            with Workdir() as w:
                code, err, rows = run_quan(w, block, 1, every=1)
                self.assertEqual(code, 0, (where, err))
                s = by_tick(rows)
                self.assertEqual(s[0]["customers"][0]["reserved"], {}, "đơn assigned giữ rỗng")
                self.assertEqual(events(rows, "customer_left")[0]["data"]["reason"], "patience")
                self.assertIsNone(s[1]["hand"])
                st = s[1]["stoves"][0]
                self.assertEqual((st["state"], st["dish"]), ("idle", None), where)


class Fixtures(unittest.TestCase):
    def test_reserved_mac_dinh_theo_cong_thuc(self):
        for c in (cust(), cust(reserved=MENU[DISH]["recipe"])):
            with Workdir() as w:
                code, err, rows = run_quan(w, {"stock": DISH_STOCK, "customers": [c]}, 0)
                self.assertEqual(code, 0, err)
                got = snapshots(rows)[0]["customers"][0]
                self.assertEqual(got["reserved"], MENU[DISH]["recipe"])
                self.assertEqual((got["state"], got["order_status"], got["order_tick"]), ("waiting", "reserved", 0))

    def test_giu_qua_ton_exit_2_ke_ca_kho_tu_inventory(self):
        with Workdir() as w:
            self.assertEqual(run_quan(w, {"stock": {}, "customers": [cust()]}, 0)[0], 2)
            self.assertFalse(os.path.exists(w.path("q.jsonl")))
            inv = write_json(w.path("inv.json"), {"items": {}})
            self.assertEqual(run_quan(w, {"customers": [cust()]}, 0, extra=("--inventory", inv))[0], 2)
            ok = write_json(w.path("ok.json"), {"items": DISH_STOCK})
            self.assertEqual(run_quan(w, {"customers": [cust()]}, 0, extra=("--inventory", ok))[0], 0)

    def test_fixture_hop_le_exit_0(self):
        eating = cust(state="eating", order_status="served", eat_ticks_left=1, base_price=PRICE, tip=0)
        blocks = [
            {"customers": [eating]},
            {"customers": [cust(order_status="unfulfillable")]},
            {"customers": [cust(order_status="assigned")], "hand": payload()},
            {"customers": [cust(order_status="assigned")],
             "stoves": [{"id": STOVE, "state": "cooking", "dish": payload(), "cook_ticks_left": 1}]},
            {"customers": [cust(order_status="assigned")],
             "stoves": [{"id": STOVE, "state": "ready", "dish": payload(), "ready_ticks": 7}]},
            {"customers": [cust(patience_ticks_left=0)]},
            {"hand": None, "reputation": Q["reputation_min"], "random_customers": True},
            {"stoves": [{"id": STOVE, "pos": [1, 1]}], "tables": [{"id": TABLE, "pos": [3, 4]}]},
        ]
        for block in blocks:
            with Workdir() as w:
                code, err, _ = run_quan(w, dict(block, stock=plenty_stock()), 1)
                self.assertEqual(code, 0, (block, err))

    def test_fixture_mau_thuan_exit_2(self):
        """D: trường sai, liên kết thiếu, bộ đếm âm/mâu thuẫn, món ngoài phạm vi, giữ khác công thức,
        bếp và tay giữ cùng đơn, món không khớp đơn, id cập nhật không tồn tại, tọa độ ngoài miền."""
        other = next(d for d in sorted(MENU) if d != DISH)
        eating = cust(state="eating", order_status="served", eat_ticks_left=1, base_price=PRICE, tip=0)
        assigned = cust(order_status="assigned")
        cooking = {"id": STOVE, "state": "cooking", "dish": payload(), "cook_ticks_left": 1}
        bad = [
            {"customers": [cust(state="dancing")]}, {"customers": [cust(order_status="done")]},
            {"customers": [cust(dish_id="pho_bo")]}, {"customers": [{"id": "C1", "table_id": TABLE}]},
            {"customers": [cust(mood="vui")]}, {"customers": [cust(price=10)]},
            {"customers": [cust(patience_ticks_left=-1)]}, {"customers": [cust(patience_ticks_left=ticks(Q["patience_s"]) + 1)]},
            {"customers": [cust(order_tick=-1)]}, {"customers": [cust(eat_ticks_left=5)]},
            {"customers": [cust(reserved={"ca_linh": 1})]}, {"customers": [cust(reserved={})]},
            {"customers": [cust(order_status="unfulfillable", reserved=MENU[DISH]["recipe"])]},
            {"customers": [cust(state="eating", order_status="reserved", eat_ticks_left=1, base_price=PRICE, tip=0)]},
            {"customers": [cust(order_status="served")]},
            {"customers": [dict(eating, eat_ticks_left=0)]},
            {"customers": [{k: v for k, v in eating.items() if k != "tip"}]},
            {"customers": [{k: v for k, v in eating.items() if k != "base_price"}]},
            {"customers": [dict(eating, eat_ticks_left=ticks(Q["eat_s"]) + 1)]},
            {"customers": [assigned]},  # assigned nhưng không có món ở bếp/tay
            {"customers": [assigned], "hand": payload(), "stoves": [cooking]},  # bếp và tay giữ cùng đơn
            {"customers": [assigned], "hand": payload(dish=other)},  # món không khớp đơn
            {"customers": [assigned], "hand": payload(order_id="C9")},  # liên kết thiếu
            {"customers": [cust()], "hand": payload()},  # đơn reserved mà đã có món
            {"hand": payload()},  # tham chiếu id không tạo thực thể
            {"customers": [assigned], "hand": {"order_id": "C1", "dish_id": DISH}},
            {"customers": [assigned], "hand": dict(payload(), base_price=0)},
            {"customers": [assigned], "hand": DISH},
            {"stoves": [{"id": STOVE, "state": "cooking", "cook_ticks_left": 5}]},
            {"customers": [assigned], "stoves": [dict(cooking, cook_ticks_left=0)]},
            {"customers": [assigned], "stoves": [dict(cooking, cook_ticks_left=ticks(MENU[DISH]["cook_s"]) + 1)]},
            {"customers": [assigned], "stoves": [dict(cooking, state="ready", cook_ticks_left=3)]},
            {"stoves": [{"id": STOVE, "state": "idle", "dish": payload()}]},
            {"stoves": [{"id": STOVE, "ready_ticks": 3}]}, {"stoves": [{"id": STOVE, "state": "burnt"}]},
            {"stoves": [{"id": "B9"}]}, {"tables": [{"id": "T9"}]},
            {"stoves": [{"id": STOVE, "pos": [99, 1]}]}, {"tables": [{"id": TABLE, "pos": [1, 99]}]},
            {"tables": [{"id": TABLE, "seats": 2}]},
            {"reputation": Q["reputation_max"] + 1}, {"reputation": Q["reputation_min"] - 1}, {"reputation": "cao"},
            {"random_customers": "yes"},
        ]
        with Workdir() as w:
            for block in bad:
                block = dict(block, stock=plenty_stock())
                self.assertEqual(run_quan(w, block, 0)[0], 2, block)
            self.assertFalse(os.path.exists(w.path("q.jsonl")), "lỗi fixture phải thoát trước khi ghi JSONL")


class Units(unittest.TestCase):
    """Gọi thẳng QuanSim với tuning sửa (thêm bàn / đổi nhịp) để thử nhánh khó dựng qua headless."""

    def _sim(self, tuning, scenario, seed=1):
        from chonoi.ids import IdAllocator
        from chonoi.rng import Streams
        from chonoi.sim.quan import QuanSim
        return QuanSim(tuning, scenario, Streams(seed), IdAllocator())

    def _run(self, sim, n):
        from chonoi.inputs import InputPlayer
        p, out = InputPlayer([]), []
        for k in range(n):
            out += [(k + 1, name, data) for name, data in sim.step(p.advance(k))]
        return out

    def test_giu_cho_lam_khach_sau_khong_du_mon(self):
        t = copy.deepcopy(T)
        t["quan"]["tables"] = [{"id": "T1", "pos": [9, 2]}, {"id": "T2", "pos": [12, 2]}]
        sim = self._sim(t, {"stock": DISH_STOCK})
        first, iv = t["quan"]["first_customer_tick"], ticks(t["quan"]["customer_interval_s"])
        ev = self._run(sim, first + iv)
        self.assertEqual([(k, n, d) for k, n, d in ev],
                         [(first, "customer_arrived", {"order_id": "C1", "table_id": "T1", "dish_id": DISH}),
                          (first + iv, "no_dish", {})])
        self.assertEqual(sim.available_stock(), {k: 0 for k in DISH_STOCK})

    def test_het_ban_thi_bo_luot(self):
        t = copy.deepcopy(T)
        t["quan"]["tables"] = t["quan"]["tables"][:1]  # TICKET-02 có 4 bàn: dựng quán 1 bàn để lượt sau hết chỗ
        t["quan"]["customer_interval_s"] = 1
        sim = self._sim(t, {"stock": plenty_stock()})
        ev = self._run(sim, t["quan"]["first_customer_tick"] + 3 * TICK)
        self.assertEqual([n for _, n, _ in ev], ["customer_arrived"])

    def test_khach_moi_ngoi_ngay_ban_vua_trong_cung_tick(self):
        t = copy.deepcopy(T)
        t["quan"]["patience_s"] = 1
        t["quan"]["customer_interval_s"] = 1
        sim = self._sim(t, {"stock": plenty_stock()})
        first = t["quan"]["first_customer_tick"]
        ev = self._run(sim, first + TICK)
        self.assertEqual([(k, n) for k, n, _ in ev],
                         [(first, "customer_arrived"), (first + TICK, "customer_left"), (first + TICK, "customer_arrived")])
        self.assertEqual(ev[2][2]["order_id"], "C2")

    def test_uy_tin_kep_o_reputation_min(self):
        sim = self._sim(T, {"stock": DISH_STOCK, "random_customers": False, "reputation": Q["reputation_min"],
                            "customers": [cust(patience_ticks_left=1)]})
        ev = self._run(sim, 1)
        self.assertEqual(sim.reputation, Q["reputation_min"])
        self.assertEqual(ev[0][2]["reputation"], Q["reputation_min"])

    def test_chon_deu_trong_mon_du_nguyen_lieu(self):
        chosen = {self._sim(T, {"stock": plenty_stock()}, seed)._choose_dish() for seed in range(1, 120)}
        self.assertEqual(chosen, set(MENU), "nhiều seed thì món đủ nguyên liệu nào cũng có lúc được chọn")
        self.assertEqual({self._sim(T, {"stock": DISH_STOCK}, s)._choose_dish() for s in range(1, 10)}, {DISH})

    def test_contract_co_dinh_mon_bep_ban(self):
        from chonoi.contract import validate_tuning
        from chonoi.errors import BadInput
        validate_tuning(copy.deepcopy(T))
        # TICKET-02: bố cục chuẩn đổi sang 2 bếp B1–B2, 4 bàn T1–T4, 6 món — sửa đột biến cho khớp (thêm T5, đổi B2 -> B3).
        for mutate in (lambda t: t["menu"].pop(DISH),
                       lambda t: t["menu"][DISH]["recipe"].update({"ca_loc": 2, "bong_sung": 1}),
                       lambda t: t["quan"]["tables"].append({"id": "T5", "pos": [1, 1]}),
                       lambda t: t["quan"]["tables"].pop(),
                       lambda t: t["quan"]["stoves"].__setitem__(1, {"id": "B3", "pos": [5, 8]}),
                       lambda t: t["quan"]["tables"][0].__setitem__("pos", [99, 1]),
                       lambda t: t["quan"].__setitem__("reputation_initial", 9),
                       lambda t: t["quan"].__setitem__("carry_limit", 0)):
            t = copy.deepcopy(T)
            mutate(t)
            with self.assertRaises(BadInput):
                validate_tuning(t)


if __name__ == "__main__":
    unittest.main()
