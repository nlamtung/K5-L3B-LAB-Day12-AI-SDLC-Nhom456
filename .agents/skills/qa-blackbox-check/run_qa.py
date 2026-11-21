#!/usr/bin/env python3
"""Script chạy kiểm thử hộp đen và thu thập bằng chứng cho phase."""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def run_tests(phase=4):
    print(f"=== BẮT ĐẦU CHẠY UNIT & REGRESSION TESTS (PHASE {phase}) ===")
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{os.path.join(ROOT, 'tests')}:{ROOT}"

    proof_dir = os.path.join(ROOT, "docs", "proof", f"phase-{phase}")
    os.makedirs(proof_dir, exist_ok=True)
    proof_file = os.path.join(proof_dir, "test-suite.txt")

    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)

    with open(proof_file, "w", encoding="utf-8") as f:
        f.write(f"STDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n")

    print(f"Log đã được ghi vào: {proof_file}")
    if proc.returncode == 0:
        print("PASS: Tất cả các test đã xanh!")
        return True
    else:
        print(f"CẢNH BÁO: Có test không pass (exit code {proc.returncode}). Xem chi tiết tại {proof_file}")
        return False


def main():
    import argparse
    p = argparse.ArgumentParser(description="Chạy kiểm thử QA theo phase")
    p.add_argument("--phase", type=int, default=4, help="Phase cần xuất proof (mặc định 4)")
    args = p.parse_args()

    ok = run_tests(phase=args.phase)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
