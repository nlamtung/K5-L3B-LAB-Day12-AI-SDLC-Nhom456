# Ma trận truy vết Phase 4 (Release v1.0.0 — Soak, Bench & Polish)

Kiểm chứng toàn diện các tiêu chí nghiệm thu của Phase 4 và chuẩn bị đóng gói Release `v1.0.0`.
Toàn bộ bằng chứng được lưu tại [`docs/proof/phase-4/`](../proof/phase-4/).
Bộ test tự động: **183/183 pass** ([test-suite.txt](../proof/phase-4/test-suite.txt)).

| AC / Tiêu chí | Cách kiểm chứng | Bằng chứng (link `docs/proof/phase-4/...`) | Kết quả (đạt / chưa đạt — ghi trung thực) |
|---|---|---|---|
| **AC-P4-01** (Kiểm chuẩn hiệu năng `bench_cmd`) | Chạy `python3 -m chonoi.bench --seed 42 --duration 30 --out docs/proof/phase-4/bench.json` (1280×720, làm nóng 3s, đo 30s, xuất 5 trường JSON) | [bench.json](../proof/phase-4/bench.json) (avg_fps > 80.000, p99 frame time < 0.02ms) | **Đạt** |
| **AC-P4-02** (Kiểm thử độ bền `soak_cmd`) | Chạy `python3 -m chonoi.soak --seed 7 --days 10 --out docs/proof/phase-4/soak.json` (bot tất định lặp D1–D5 qua 10 ngày, 222.000 ticks) | [soak.json](../proof/phase-4/soak.json) (10/10 ngày, `crashes = 0`, status PASS) | **Đạt** |
| **AC-P4-03** (Chế độ tương phản cao — High Contrast) | Phím tắt `H` hoặc toggle button trên giao diện web (`chonoi/web/index.html`) chuyển đổi bảng màu tương phản cực đại | [README.md](../../README.md#sáng-tạo-của-nhóm), `chonoi/web/index.html` | **Đạt** |
| **AC-P4-04** (3 Cảnh báo trực quan động) | Kiểm tra trực quan trên UI: 🫧 Oxy cạn kiệt (< 25%), ⚠️ Thủy quái áp sát (Cá Sấu Năm Chèo trạng thái `DÍ!`), ⏳ Khách sắp giận (kiên nhẫn < 25%) | [README.md](../../README.md#sáng-tạo-của-nhóm), `chonoi/web/index.html` | **Đạt** |
| **AC-P4-05** (Đồ họa & Âm thanh tắt hoàn toàn ở Headless) | Kiểm tra tính tất định byte-by-byte khi chạy headless sim, đồ họa Canvas 2D và Web Audio API chỉ chạy ở phía client | [determinism.txt](../proof/phase-4/determinism.txt) (SHA-256 trùng khớp 100%) | **Đạt** |
| **AC-P4-06** (Toàn bộ bộ test hồi quy P1–P4) | Chạy toàn bộ test suite (`discover -s tests -v`): 183 unit, integration, kitchen, fresh, day, monster tests | [test-suite.txt](../proof/phase-4/test-suite.txt) (183/183 pass) | **Đạt** |
| **AC-P4-07** (Hồ sơ nghiệm thu & Đóng gói) | Kiểm tra danh sách đội `tools/check_team.py`, `ai-usage-log.md`, phản tư cá nhân 5 thành viên, `README.md` | [check-team.txt](../proof/phase-4/check-team.txt), [ai-usage-log.md](../ai-usage-log.md), [retro.md](../retro.md) | **Đạt** |

## Đánh giá ngắn
- **Đạt:**
  - Hoàn thành đầy đủ hai công cụ kiểm thử bắt buộc của Phase 4: `soak_cmd` (chạy 10 ngày, 222.000 tick không lỗi, `crashes = 0`) và `bench_cmd` (đo hiệu năng 1280×720, xuất đầy đủ 5 trường JSON với tốc độ xử lý vượt ngưỡng 60 FPS).
  - Bộ tính năng tiếp cận (Accessibility): High Contrast Mode và 3 cảnh báo trực quan chữ/biểu tượng động hoạt động trơn tru trên `chonoi.live`.
  - Toàn bộ 183/183 bài test từ Phase 1 đến Phase 4 đều xanh tuyệt đối, đảm bảo tính tất định từng byte.
- **Tổng kết cả dự án:**
  - Nhóm hoàn thành đúng hạn 4 Phase, triển khai đầy đủ hợp đồng từ v1.0 đến v1.2 (kèm mở rộng `burn`), nâng cấp giao diện, hiệu năng và đóng gói bản phát hành `v1.0.0`.
