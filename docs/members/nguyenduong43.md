# nguyenduong43 (Nguyễn Tùng Dương) — phản tư cá nhân (≤ 200 từ)

Vai thực tế: QA Lead · Bench / Soak / Verification.

- Tôi đã làm (kèm link commit):
  - Xây dựng 2 skills tự động hóa trong `.agents/skills/` (`verify-contract`, `qa-blackbox-check`) và cập nhật `AGENTS.md`: [10f881d](https://github.com/nlamtung/K5-L3B-LAB-Day12-AI-SDLC-Nhom456/commit/10f881d)
  - Viết bộ test hồi quy `test_qa_regression_p1.py`, sửa `test_team_check.py` và xử lý sandbox `test_live.py`: [fee51f0](https://github.com/nlamtung/K5-L3B-LAB-Day12-AI-SDLC-Nhom456/commit/fee51f0)
  - Lập ma trận truy vết và thu thập bằng chứng Phase 1: [e09d700](https://github.com/nlamtung/K5-L3B-LAB-Day12-AI-SDLC-Nhom456/commit/e09d700)
  - Triển khai `chonoi/soak.py` (`soak_cmd` 10 ngày, 222k tick, `crashes=0`), `chonoi/bench.py` (`bench_cmd` 1280×720, 5 trường JSON), cập nhật skill QA theo phase, xuất proof `bench.json`, `soak.json` và lập ma trận `docs/verification/phase-4.md`.
- Tôi đã review (kèm link):
  - Review chéo PR #2 (gather), PR #3 & #4 (quan), PR #12 (day/shop/burn), PR #13 (v1.2 độ tươi) và PR #14 (High Contrast, 3 cảnh báo tiếp cận); giám sát 183/183 test luôn xanh.
- AI sai ở đâu và tôi phát hiện thế nào:
  - AI giả định file kho được ghi khi chưa hết ca; test phụ thuộc `TEAM.md` thật; `soak.py` truyền `days=10` vượt trần `day_plan` và gọi nhầm `player.frame` thay vì `advance`. Tôi phát hiện qua chạy test thực tế và sửa theo `PRD-0` & API khung.
- Điều tôi học được:
  - Hiểu sâu về kiểm thử phần mềm tất định, thiết kế harness kiểm chuẩn hiệu năng/độ bền và vai trò sống còn của QA trong quy trình AI SDLC song song.
