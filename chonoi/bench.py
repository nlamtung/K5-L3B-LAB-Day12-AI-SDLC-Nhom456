"""Kiểm chuẩn hiệu năng (Benchmark — TICKET-04 mục 1, Test Contract v1.3):
python3 -m chonoi.bench --seed 42 --duration 30 --out bench.json

Cảnh đo: buổi sáng lõi (gather) với độ tươi, cá bơi, Cá Sấu Năm Chèo; Út Sen đứng yên ở bến.
Làm nóng 3 s, sau đó đo duration s ở độ phân giải chuẩn 1280x720.
Xuất đúng 5 trường JSON theo TICKET-04: avg_fps, p1_low_fps, frames, measured_s, load_ms.
"""

import argparse
import json
import math
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


def _float(name):
    def conv(s):
        try:
            return float(s)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{name} phải là số thực")
    return conv


def run_bench(seed=42, duration=30.0, warmup=3.0, out="bench.json", tuning=None):
    t_launch = time.perf_counter()
    if tuning is None:
        tuning = load_contract()["tuning"]

    tick_hz = tuning.get("tick_hz", 60)
    warmup_ticks = int(round(warmup * tick_hz))
    bench_ticks = int(round(duration * tick_hz))

    # Cảnh đo chuẩn: buổi sáng lõi (gather), Út Sen đứng yên ở bến
    session = make_session("gather", tuning, {}, seed)
    player = InputPlayer([])
    _ = session.snapshot()
    load_ms = round((time.perf_counter() - t_launch) * 1000.0, 2)

    # 1. Làm nóng (warmup 3 s)
    for _ in range(warmup_ticks):
        if session.done:
            session = make_session("gather", tuning, {}, seed)
        session.step(player.advance(session.tick))
        session.snapshot()

    # 2. Đo (duration s)
    frame_times_s = []
    for _ in range(bench_ticks):
        if session.done:
            session = make_session("gather", tuning, {}, seed)
        t0 = time.perf_counter()
        session.step(player.advance(session.tick))
        session.snapshot()
        t1 = time.perf_counter()
        frame_times_s.append(max(t1 - t0, 1e-9))

    frames = len(frame_times_s)
    measured_s = sum(frame_times_s)
    avg_fps = round(frames / measured_s, 2) if measured_s > 0 else 0.0

    # p1_low_fps: max(1, ceil(0.01 * frames)) khung chậm nhất -> nghịch đảo thời gian trung bình (s)
    k = max(1, math.ceil(0.01 * frames)) if frames > 0 else 1
    slowest = sorted(frame_times_s, reverse=True)[:k]
    avg_slow_s = sum(slowest) / len(slowest) if slowest else 0.0
    p1_low_fps = round(1.0 / avg_slow_s, 2) if avg_slow_s > 0 else 0.0

    res = {
        "avg_fps": avg_fps,
        "p1_low_fps": p1_low_fps,
        "frames": frames,
        "measured_s": round(measured_s, 4),
        "load_ms": load_ms,
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
    p = _Parser(prog="chonoi.bench")
    p.add_argument("--seed", type=_int("seed"), default=42)
    p.add_argument("--duration", type=_float("duration"), default=30.0)
    p.add_argument("--warmup", type=_float("warmup"), default=3.0)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)

    if a.duration <= 0 or a.warmup < 0:
        sys.stderr.write("đầu vào sai: --duration phải > 0 và --warmup >= 0\n")
        return 2

    try:
        res = run_bench(seed=a.seed, duration=a.duration, warmup=a.warmup, out=a.out)
        print(f"BENCHMARK OK: frames={res['frames']}, measured_s={res['measured_s']}, "
              f"avg_fps={res['avg_fps']}, p1_low_fps={res['p1_low_fps']}, load_ms={res['load_ms']}")
        return 0
    except Exception as e:
        sys.stderr.write(f"Lỗi chạy benchmark: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
