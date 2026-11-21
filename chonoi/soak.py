"""Kiểm thử độ bền headless (Soak test — TICKET-04 mục 2, Test Contract v1.3):
python3 -m chonoi.soak --seed 7 --days 10 --out soak.json

Chạy N Ngày liên tục (mặc định 10 Ngày, lặp kế hoạch D1–D5 ở Ngày 6–10) trong một tiến trình headless.
Xuất đúng 5 trường JSON theo TICKET-04: days, days_completed, crashes, results[], duration_s.
Mỗi phần tử results[] có: day, earned, reputation, score tại lúc Shop đóng.
"""

import argparse
import json
import math
import os
import sys
import time

from .contract import load_contract
from .ids import IdAllocator
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
    results = []

    cur_money = 0
    cur_earned = 0
    cur_reputation = tuning["quan"]["reputation_initial"]
    cur_upgrades = {}
    shared_ids = IdAllocator()
    mult = tuning["score"]["reputation_multiplier"]

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
            session = make_session("day", tuning, scenario, seed + round_idx - 1, days=batch_days)
            # Nối tiếp IdAllocator xuyên chu kỳ lặp D1–D5
            session.ids = shared_ids
            player = InputPlayer([])

            while not session.done:
                frame = player.advance(session.tick)
                rows = session.step(frame)
                for ev in rows:
                    if ev.get("name") == "shop_end":
                        days_completed += 1
                        score = session.earned + mult * math.floor(session.reputation)
                        results.append({
                            "day": days_completed,
                            "earned": session.earned,
                            "reputation": round(session.reputation, 3),
                            "score": score,
                        })

            cur_money = session.money
            cur_earned = session.earned
            cur_reputation = session.reputation
            cur_upgrades = dict(session.upgrades)
            days_remaining -= batch_days
        except Exception as e:
            sys.stderr.write(f"Crash trong soak test ở chu kỳ {round_idx}: {e}\n")
            crashes += 1
            break

    duration_s = round(time.perf_counter() - t_start, 4)
    res = {
        "days": days,
        "days_completed": days_completed,
        "crashes": crashes,
        "results": results,
        "duration_s": duration_s,
    }

    if out:
        out_dir = os.path.dirname(out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return res


def main(argv=None) -> int:
    p = _Parser(prog="chonoi.soak")
    p.add_argument("--seed", type=_int("seed"), default=7)
    p.add_argument("--days", type=_int("days"), default=10)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)

    if a.days < 1:
        sys.stderr.write("đầu vào sai: --days phải >= 1\n")
        return 2

    try:
        res = run_soak(seed=a.seed, days=a.days, out=a.out)
        print(f"SOAK OK: days={res['days']}, days_completed={res['days_completed']}, "
              f"crashes={res['crashes']}, duration_s={res['duration_s']}")
        return 0 if res["crashes"] == 0 and res["days_completed"] == res["days"] else 1
    except Exception as e:
        sys.stderr.write(f"Lỗi chạy soak test: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
