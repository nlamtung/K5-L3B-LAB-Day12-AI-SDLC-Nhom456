"""Bộ test hồi quy (Regression & Acceptance Criteria) cho Phase 1 — Phụ trách bởi TV5 (QA Lead).

Kiểm tra:
- AC-P1-01: Hợp đồng đội và cấu hình repo (TEAM.md, game.contract.json).
- AC-P1-07: Tính tất định từng byte (Determinism) của headless output qua nhiều seed khác nhau.
- AC-P1-08: Ràng buộc mã thoát (Exit code 0 khi hoàn thành, 2 khi kịch bản/dữ liệu mâu thuẫn).
- Các ca kiểm thử biên (Boundary conditions): ticks=0, oxy chạm đáy, giỏ đầy.
"""

import hashlib
import json
import os
import subprocess
import sys
import unittest

from helpers import ROOT, Workdir, read_jsonl, run_headless, write_json


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


class QARegressionPhase1(unittest.TestCase):
    def test_ac_p1_01_team_and_contract_integrity(self):
        """AC-P1-01: Cấu hình game.contract.json và TEAM.md phải hợp lệ và khớp nhau."""
        cmd = [sys.executable, os.path.join(ROOT, "tools", "check_team.py")]
        res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"check_team.py thất bại: {res.stderr}")
        self.assertIn("OK: 5 thành viên", res.stdout)

        with open(os.path.join(ROOT, "game.contract.json"), encoding="utf-8") as f:
            contract = json.load(f)
        self.assertEqual(contract.get("team_size"), 5)
        self.assertIn("tuning", contract)
        self.assertIn("gather", contract["tuning"])
        self.assertIn("quan", contract["tuning"])

    def test_ac_p1_07_byte_level_determinism_gather(self):
        """AC-P1-07: Chạy 2 lần cùng seed gather (hết ca) phải tạo file JSONL và file kho giống hệt từng byte."""
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {"time_left_ticks": 60}})
            out1 = w.path("run1.jsonl")
            out2 = w.path("run2.jsonl")
            inv1 = w.path("inv1.json")
            inv2 = w.path("inv2.json")

            code1, err1 = run_headless("--mode", "gather", "--seed", "12345", "--ticks", "70",
                                       "--scenario", sc, "--out", out1, "--inventory-out", inv1)
            code2, err2 = run_headless("--mode", "gather", "--seed", "12345", "--ticks", "70",
                                       "--scenario", sc, "--out", out2, "--inventory-out", inv2)

            self.assertEqual(code1, 0, err1)
            self.assertEqual(code2, 0, err2)

            # So sánh hash SHA-256 từng byte
            self.assertEqual(sha256_file(out1), sha256_file(out2), "Output JSONL không tất định từng byte")
            self.assertEqual(sha256_file(inv1), sha256_file(inv2), "Output Inventory không tất định từng byte")

    def test_ac_p1_07_byte_level_determinism_quan(self):
        """AC-P1-07: Chạy 2 lần cùng seed quan với cùng kho đầu vào phải tạo file JSONL giống hệt từng byte."""
        with Workdir() as w:
            # v1.2 (TICKET-03): file kho là mảng cá thể
            inv = write_json(w.path("inv.json"), {"items": [{"id": "I1", "kind": "ca_loc", "fresh": 100}, {"id": "I2", "kind": "ca_loc", "fresh": 100}, {"id": "I3", "kind": "bong_sung", "fresh": 100}, {"id": "I4", "kind": "bong_sung", "fresh": 100}]})
            out1 = w.path("quan1.jsonl")
            out2 = w.path("quan2.jsonl")

            code1, err1 = run_headless("--mode", "quan", "--seed", "9999", "--ticks", "200",
                                       "--inventory", inv, "--out", out1)
            code2, err2 = run_headless("--mode", "quan", "--seed", "9999", "--ticks", "200",
                                       "--inventory", inv, "--out", out2)

            self.assertEqual(code1, 0, err1)
            self.assertEqual(code2, 0, err2)
            self.assertEqual(sha256_file(out1), sha256_file(out2), "Output JSONL quan không tất định từng byte")

    def test_ac_p1_08_exit_code_2_on_invalid_scenario_data(self):
        """AC-P1-08: Dữ liệu kịch bản sai hoặc mâu thuẫn phải trả mã thoát 2."""
        with Workdir() as w:
            # 1. Sai trường chưa hỗ trợ
            sc_bad_field = write_json(w.path("sc_bad.json"), {"gather": {"unknown_field_xyz": 123}})
            code, _ = run_headless("--mode", "gather", "--seed", "1", "--ticks", "60",
                                   "--scenario", sc_bad_field, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 2, "Trường không hỗ trợ trong scenario phải trả về mã 2")

            # 2. Sai mode kịch bản (truyền gather vào quan)
            code_mode, _ = run_headless("--mode", "quan", "--seed", "1", "--ticks", "60",
                                        "--scenario", sc_bad_field, "--out", w.path("o2.jsonl"))
            self.assertEqual(code_mode, 2, "Kịch bản lệch mode phải trả về mã 2")

            # 3. Đồng thời truyền cả --inventory và scenario.quan.stock
            sc_conflict = write_json(w.path("sc_conflict.json"), {"quan": {"stock": [{"id": "I1", "kind": "ca_loc", "fresh": 100}]}})
            inv_file = write_json(w.path("inv.json"), {"items": [{"id": "I1", "kind": "ca_loc", "fresh": 100}]})
            code_conflict, _ = run_headless("--mode", "quan", "--seed", "1", "--ticks", "60",
                                            "--scenario", sc_conflict, "--inventory", inv_file,
                                            "--out", w.path("o3.jsonl"))
            self.assertEqual(code_conflict, 2, "Khai đồng thời cả --inventory và quan.stock phải trả về mã 2")

    def test_boundary_zero_ticks_generates_initial_fixture(self):
        """Kiểm tra biên --ticks 0: khởi tạo fixture hợp lệ, ghi snapshot 0 và kết thúc mã 0."""
        with Workdir() as w:
            out = w.path("zero.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "0", "--out", out)
            self.assertEqual(code, 0, err)
            lines = read_jsonl(out)
            self.assertGreaterEqual(len(lines), 1)
            self.assertEqual(lines[0]["type"], "snapshot")
            self.assertEqual(lines[0]["tick"], 0)

    def test_boundary_faint_clears_hold_and_writes_empty_inventory(self):
        """Kiểm tra biên ngất (faint): khi hết máu, buổi sáng kết thúc ngay với kho rỗng."""
        with Workdir() as w:
            # Khởi tạo người chơi ở dưới nước d=10, chỉ còn 1 Máu và 1 tick oxy
            sc = write_json(w.path("sc_faint.json"), {
                "gather": {
                    "player": {"pos": [20, 10], "oxygen_ticks": 1, "hp": 1},
                    "hold": [{"id": "I1", "kind": "ca_loc", "fresh": 100}, {"id": "I2", "kind": "bong_sung", "fresh": 100}]  # v1.2: cá thể
                }
            })
            out = w.path("faint.jsonl")
            inv_out = w.path("inv_out.json")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "100",
                                     "--scenario", sc, "--out", out, "--inventory-out", inv_out)
            self.assertEqual(code, 0, err)
            with open(inv_out, encoding="utf-8") as f:
                inv_data = json.load(f)
            self.assertEqual(inv_data, {"items": []}, "Ngất xỉu phải ghi file kho hoàn toàn rỗng (v1.2: mảng rỗng)")


if __name__ == "__main__":
    unittest.main()
