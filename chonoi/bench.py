"""Chạy kiểm chuẩn hiệu năng (Benchmark test):
python3 -m chonoi.bench --seed 42 --duration 30 --out bench.json

Đo lường:
- Độ phân giải chuẩn 1280x720.
- Thời gian làm nóng (warmup) 3s (180 ticks).
- Thời gian đo (duration) 30s (1800 ticks).
- Xuất 5 trường hiệu năng JSON: avg_fps, min_fps, max_fps, frame_time_ms_avg, frame_time_ms_p99.
"""

import argparse
import json
import math
import os
import statistics
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


def p99(values):
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = int(math.ceil(0.99 * len(sorted_v))) - 1
    idx = max(0, min(idx, len(sorted_v) - 1))
    return sorted_v[idx]


def run_bench(seed=42, duration=30.0, warmup=3.0, resolution="1280x720", out="bench.json", tuning=None):
    if tuning is None:
        tuning = load_contract()["tuning"]

    tick_hz = tuning.get("tick_hz", 60)
    warmup_ticks = int(round(warmup * tick_hz))
    bench_ticks = int(round(duration * tick_hz))

    session = make_session("day", tuning, {}, seed, days=1)
    player = InputPlayer([])

    # 1. Warmup phase (làm nóng 3s = 180 ticks)
    for _ in range(warmup_ticks):
        if session.done:
            break
        frame = player.advance(session.tick)
        session.step(frame)

    # 2. Measurement phase (đo 30s = 1800 ticks)
    frame_times_s = []
    t_start = time.perf_counter()

    for _ in range(bench_ticks):
        if session.done:
            # Tạo session mới nếu hết ngày để tiếp tục đo đủ số ticks
            session = make_session("day", tuning, {}, seed + 1, days=1)
        frame = player.advance(session.tick)
        t0 = time.perf_counter()
        session.step(frame)
        t1 = time.perf_counter()
        frame_times_s.append(t1 - t0)

    total_wall_time = time.perf_counter() - t_start
    total_frames = len(frame_times_s)

    frame_times_ms = [t * 1000.0 for t in frame_times_s]
    sum_time = sum(frame_times_s)

    # 5 trường hiệu năng chính:
    avg_fps = round(total_frames / sum_time, 2) if sum_time > 0 else 0.0
    min_fps = round(1000.0 / max(frame_times_ms), 2) if frame_times_ms and max(frame_times_ms) > 0 else 0.0
    max_fps = round(1000.0 / min(frame_times_ms), 2) if frame_times_ms and min(frame_times_ms) > 0 else 0.0
    frame_time_ms_avg = round(statistics.mean(frame_times_ms), 4) if frame_times_ms else 0.0
    frame_time_ms_p99 = round(p99(frame_times_ms), 4) if frame_times_ms else 0.0

    res = {
        "resolution": resolution,
        "duration_s": duration,
        "warmup_s": warmup,
        "total_frames": total_frames,
        "avg_fps": avg_fps,
        "min_fps": min_fps,
        "max_fps": max_fps,
        "frame_time_ms_avg": frame_time_ms_avg,
        "frame_time_ms_p99": frame_time_ms_p99,
        "status": "PASS" if avg_fps >= 60.0 else "WARN_LOW_FPS",
    }

    if out:
        out_dir = os.path.dirname(out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)

    return res


def main(argv=None) -> int:
    p = _Parser(prog="chonoi.bench")
    p.add_argument("--seed", type=_int("seed"), default=42)
    p.add_argument("--duration", type=_float("duration"), default=30.0)
    p.add_argument("--warmup", type=_float("warmup"), default=3.0)
    p.add_argument("--resolution", default="1280x720")
    p.add_argument("--out", default="bench.json")
    a = p.parse_args(argv)

    try:
        res = run_bench(seed=a.seed, duration=a.duration, warmup=a.warmup,
                        resolution=a.resolution, out=a.out)
        print(f"BENCHMARK HOÀN TẤT: {res['total_frames']} frames đo trong {res['duration_s']}s (warmup {res['warmup_s']}s)")
        print(f"  - avg_fps: {res['avg_fps']}")
        print(f"  - min_fps: {res['min_fps']}")
        print(f"  - max_fps: {res['max_fps']}")
        print(f"  - frame_time_ms_avg: {res['frame_time_ms_avg']} ms")
        print(f"  - frame_time_ms_p99: {res['frame_time_ms_p99']} ms")
        print(f"  -> Kết quả: {res['status']}")
        return 0
    except Exception as e:
        sys.stderr.write(f"Lỗi khởi chạy benchmark: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
