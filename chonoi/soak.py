"""Chạy kiểm thử độ bền (Soak test) lặp chu kỳ ngày:
python3 -m chonoi.soak --seed 7 --days 10 --out soak.json

Kiểm tra:
- Khả năng chạy liên tục nhiều ngày (mặc định 10 ngày lặp D1-D5) không bị treo, không crash.
- Tính toàn vẹn trạng thái tích lũy (tiền, điểm, nâng cấp) xuyên ngày.
- Báo cáo số ngày hoàn thành, số tick, số lỗi crash (crashes = 0).
"""

import argparse
import json
import os
import sys
import time

from .contract import load_contract
from .inputs import InputPlayer
from .runner import make_session


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"lỗi: {message}\n")
        sys.exit(2)


def _int(name):
    def conv(s):
        try:
            return int(s)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{name} phải là số nguyên")
    return conv


def run_soak(seed=7, days=10, out="soak.json", tuning=None):
    if tuning is None:
        tuning = load_contract()["tuning"]

    day_plan_len = len(tuning.get("day_plan", []))
    if day_plan_len == 0:
        raise ValueError("tuning không có day_plan hợp lệ")

    t_start = time.perf_counter()
    crashes = 0
    days_completed = 0
    total_ticks = 0

    cur_money = 0
    cur_earned = 0
    cur_reputation = tuning["quan"]["reputation_initial"]
    cur_upgrades = {}

    days_remaining = days
    round_idx = 0

    while days_remaining > 0:
        round_idx += 1
        batch_days = min(days_remaining, day_plan_len)

        scenario = {
            "day": {
                "money": cur_money,
                "earned": cur_earned,
                "reputation": cur_reputation,
                "upgrades": dict(cur_upgrades),
            }
        }

        try:
            session = make_session("day", tuning, scenario, seed + round_idx, days=batch_days)
            player = InputPlayer([])

            while not session.done:
                frame = player.advance(session.tick)
                session.step(frame)
                total_ticks += 1

            days_completed += session.days_completed
            cur_money = session.money
            cur_earned = session.earned
            cur_reputation = session.reputation
            cur_upgrades = dict(session.upgrades)
            days_remaining -= batch_days

        except Exception as e:
            sys.stderr.write(f"Crash trong soak test ở round {round_idx}: {e}\n")
            crashes += 1
            break

    elapsed = time.perf_counter() - t_start
    tps = total_ticks / elapsed if elapsed > 0 else 0.0

    score = cur_earned + tuning["score"]["reputation_multiplier"] * int(cur_reputation)

    res = {
        "seed": seed,
        "days_requested": days,
        "days_completed": days_completed,
        "total_ticks": total_ticks,
        "duration_s": round(elapsed, 4),
        "ticks_per_s": round(tps, 2),
        "crashes": crashes,
        "status": "PASS" if crashes == 0 and days_completed == days else "FAIL",
        "final_score": score,
        "final_money": cur_money,
        "final_reputation": round(cur_reputation, 2),
    }

    if out:
        out_dir = os.path.dirname(out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)

    return res


def main(argv=None) -> int:
    p = _Parser(prog="chonoi.soak")
    p.add_argument("--seed", type=_int("seed"), default=7)
    p.add_argument("--days", type=_int("days"), default=10)
    p.add_argument("--out", default="soak.json")
    a = p.parse_args(argv)

    try:
        res = run_soak(seed=a.seed, days=a.days, out=a.out)
        print(f"SOAK TEST HOÀN TẤT: {res['days_completed']}/{res['days_requested']} ngày, {res['total_ticks']} ticks, crashes={res['crashes']} -> {res['status']}")
        return 0 if res["crashes"] == 0 else 1
    except Exception as e:
        sys.stderr.write(f"Lỗi khởi chạy soak test: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
