"""Mở rộng Phase 2 "Cháy món" (burn) — TICKET-02 mục 3 và 4.4/4.5, phần bếp của lát 4.

Luật: burn_s hữu hạn (preset mở rộng 20 s = 1.200 tick). Món ready có ready_ticks > burn ticks thì bỏ món,
nguyên liệu mất, bếp rảnh ngay; thử giữ lại ngay nguyên liệu cho đơn từ kho khả dụng (tồn − phần đang giữ):
đủ -> order_status "reserved", thiếu -> "unfulfillable" (khách chờ tiếp tới hết kiên nhẫn). Đúng burn ticks vẫn bưng được.
Event dish_burnt {stove_id, order_id, dish_id, order_status sau xử lý}. Xét chín/cháy theo id bếp TRƯỚC di chuyển và tương tác.

Lõi dùng burn_s: null -> toàn bộ test skip cho tới khi nhóm bật mở rộng này trong game.contract.json.
"""

import unittest

from chonoi.contract import load_contract
from chonoi.inputs import InputState
from chonoi.runner import Session

from helpers import stock_of

TUNING = load_contract()["tuning"]
Q = TUNING["quan"]
MENU = TUNING["menu"]
BURN_ON = Q.get("burn_s") is not None
STOVE = {s["id"]: s["pos"] for s in Q["stoves"]}["B1"]
DISH = "ca_loc_nuong_trui"
RECIPE = MENU[DISH]["recipe"]
# TICKET-03 (v1.2) [THAY THẾ]: kho là mảng cá thể, reserved là mảng id. RECIPE_STOCK là kho vừa đủ một suất
# (cá thể I1…); giữ lại sau cháy lấy cá thể khả dụng tươi nhất -> reserved == RECIPE_IDS.
RECIPE_STOCK = stock_of(RECIPE)
RECIPE_IDS = [it["id"] for it in RECIPE_STOCK]


def ticks(seconds):
    return int(round(seconds * 60))


BURN = ticks(Q["burn_s"]) if BURN_ON else None


def idle():
    return InputState((0.0, 0.0), {}, set())


def press():
    return InputState((0.0, 0.0), {"interact": True}, {"interact"})


def payload(cid="C1"):
    return {"order_id": cid, "dish_id": DISH, "base_price": MENU[DISH]["price"]}


def assigned(cid="C1", table_id="T1", **kw):
    c = {"id": cid, "table_id": table_id, "dish_id": DISH, "order_tick": 0, "state": "waiting",
         "patience_ticks_left": ticks(Q["patience_s"]), "order_status": "assigned", "reserved": []}
    c.update(kw)
    return c


def ready_stove(age):
    return {"id": "B1", "state": "ready", "dish": payload(), "cook_ticks_left": 0, "ready_ticks": age}


def session(age, stock=None, customers=None, pos=None, **scn):
    base = {"player": {"pos": list(pos or Q["start_pos"])}, "random_customers": False,
            "stock": stock or [], "customers": customers or [assigned()], "stoves": [ready_stove(age)]}
    base.update(scn)
    return Session("quan", TUNING, base, 1)


def b1(s):
    return next(x for x in s.snapshot()["stoves"] if x["id"] == "B1")


def c1(s):
    return next((c for c in s.snapshot()["customers"] if c["id"] == "C1"), None)


@unittest.skipUnless(BURN_ON, "mở rộng burn chưa bật (quan.burn_s = null trong lõi)")
class Burn(unittest.TestCase):
    def test_pick_up_at_exactly_burn_ticks(self):
        # đầu bước ready_ticks = BURN-1, bước 1 tăng lên đúng BURN -> chưa cháy, vẫn bưng được
        s = session(BURN - 1, pos=STOVE)
        rows = s.step(press())
        self.assertEqual([r["name"] for r in rows], ["dish_picked"])
        self.assertEqual(s.snapshot()["hand"], payload())

    def test_no_burn_while_age_not_over_limit(self):
        s = session(BURN - 1)
        self.assertEqual(s.step(idle()), [])
        self.assertEqual((b1(s)["state"], b1(s)["ready_ticks"]), ("ready", BURN))

    def test_burn_when_age_exceeds_limit_and_stove_free(self):
        s = session(BURN)  # bước này tăng lên BURN+1 > BURN -> cháy
        rows = s.step(idle())
        self.assertEqual([r["name"] for r in rows], ["dish_burnt"])
        self.assertEqual(rows[0]["tick"], 1)
        st = b1(s)
        self.assertEqual((st["state"], st["dish"]), ("idle", None), "bếp rảnh ngay")
        self.assertEqual(s.snapshot()["stock"], [], "nguyên liệu đã nấu bị mất, không hoàn lại")

    def test_burnt_order_re_reserved_when_stock_enough(self):
        s = session(BURN, stock=[dict(it) for it in RECIPE_STOCK])
        rows = s.step(idle())
        self.assertEqual(rows[0]["data"], {"stove_id": "B1", "order_id": "C1", "dish_id": DISH,
                                           "order_status": "reserved"})
        c = c1(s)
        self.assertEqual((c["order_status"], c["reserved"], c["state"]), ("reserved", RECIPE_IDS, "waiting"))
        self.assertEqual(c["order_tick"], 0, "giữ order_tick cũ để vẫn là đơn cũ nhất")
        self.assertEqual([x["id"] for x in s.snapshot()["stock"]], RECIPE_IDS, "giữ chỗ không trừ tồn vật lý")

    def test_burnt_order_unfulfillable_when_stock_short(self):
        s = session(BURN)
        rows = s.step(idle())
        self.assertEqual(rows[0]["data"]["order_status"], "unfulfillable")
        c = c1(s)
        self.assertEqual((c["order_status"], c["reserved"], c["state"]), ("unfulfillable", [], "waiting"))

    def test_available_stock_excludes_other_reservations(self):
        other = {"id": "C2", "table_id": "T2", "dish_id": DISH, "order_tick": 0, "state": "waiting",
                 "patience_ticks_left": ticks(Q["patience_s"]), "order_status": "reserved",
                 "reserved": list(RECIPE_IDS)}
        if "T2" not in {t["id"] for t in Q["tables"]}:
            self.skipTest("cần bàn T2 (contract v1.1)")
        s = session(BURN, stock=[dict(it) for it in RECIPE_STOCK], customers=[assigned(), other])
        rows = s.step(idle())
        self.assertEqual(rows[0]["data"]["order_status"], "unfulfillable",
                         "nguyên liệu trong kho đang được C2 giữ, không còn khả dụng cho C1")

    def test_burn_checked_before_interact_same_tick(self):
        # đứng ở bếp, bấm E đúng bước cháy: cháy trước, bếp idle -> E nấu lại đơn vừa giữ lại
        s = session(BURN, stock=[dict(it) for it in RECIPE_STOCK], pos=STOVE)
        rows = s.step(press())
        self.assertEqual([r["name"] for r in rows], ["dish_burnt", "cook_started"])
        self.assertEqual(rows[1]["data"]["order_id"], "C1")

    def test_burn_on_pick_attempt_one_tick_late(self):
        s = session(BURN, pos=STOVE)
        rows = s.step(press())
        self.assertEqual([r["name"] for r in rows], ["dish_burnt"], "trễ 1 tick: cháy trước, không bưng được")
        self.assertIsNone(s.snapshot()["hand"])

    def test_unfulfillable_customer_waits_then_leaves_with_penalty(self):
        s = session(BURN, customers=[assigned(patience_ticks_left=3)])
        names = []
        for _ in range(4):
            names += [(r["name"], r["data"].get("reason")) for r in s.step(idle())]
        self.assertEqual(names, [("dish_burnt", None), ("customer_left", "patience")])
        self.assertAlmostEqual(s.snapshot()["reputation"], Q["reputation_initial"] + Q["left_reputation_delta"])

    def test_unfulfillable_order_is_not_cooked(self):
        s = Session("quan", TUNING, {"player": {"pos": list(STOVE)}, "random_customers": False,
                                     "stock": [dict(it) for it in RECIPE_STOCK],
                                     "customers": [assigned(order_status="unfulfillable")]}, 1)
        self.assertEqual(s.step(press()), [], "đơn unfulfillable không được bếp lấy, kể cả khi kho có hàng")


if __name__ == "__main__":
    unittest.main()
