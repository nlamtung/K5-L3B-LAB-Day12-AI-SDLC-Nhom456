# Ma trận truy vết Phase 3 (TICKET-03, Test Contract v1.2 — độ tươi)

Kiểm chứng trên nhánh Phase 3, toàn bộ bằng chứng trong [`docs/proof/phase-3/`](../proof/phase-3/).
Bộ test: **183/183 pass, 0 skip** ([test-suite.txt](../proof/phase-3/test-suite.txt)). Lệnh smoke và đầu ra thật: [smoke.txt](../proof/phase-3/smoke.txt).

| AC | Cách kiểm chứng | Bằng chứng | Kết quả |
|---|---|---|---|
| **AC-P3-01** `contract_version: "1.2"`, `freshness {initial 100, gather_decay_per_s 0.5, quan_decay_per_s 0.25, spoiled_below 30}` | `chonoi/contract.py::_validate_freshness`; `python3 .agents/skills/verify-contract/verify.py` | [game.contract.json](../../game.contract.json), [test-suite.txt](../proof/phase-3/test-suite.txt) | **Đạt** |
| **AC-P3-02** File kho cá thể `{"items":[{id,kind,fresh}]}`; kho đếm / sai schema / kind lạ / id trùng / fresh ngoài miền → mã 2, không ghi output | `test_integration_gather_quan::test_quan_rejects_bad_inventory_exit_2` (11 file sai), `test_quan_v12_fresh::HandoffV12::test_counted_inventory_file_rejected`; smoke `counted-v11.json` | [smoke.txt](../proof/phase-3/smoke.txt) (exit 2, không có output) | **Đạt** |
| **AC-P3-03** Smoke bàn giao: gather cập bến tick 0 → file → `quan --inventory --ticks 0` đúng id, kind, fresh sau một lần hao | mẫu của ticket ([dock.json](../proof/phase-3/dock.json)); `test_quan_v12_fresh::HandoffV12::test_file_matches_gather_end_and_quan_stock` | [catch.json](../proof/phase-3/catch.json), [gather.jsonl](../proof/phase-3/gather.jsonl), [quan.jsonl](../proof/phase-3/quan.jsonl) | **Đạt** (99.99166… cả hai đầu) |
| **AC-P3-04** Hao tươi: giỏ −0.5/s đầu bước, kho quán −0.25/s kể cả hàng đang giữ; hàng mới 100 hao từ bước sau; pause / Shop / món chín không hao | `test_fresh_v12::GatherFreshness::test_new_item_starts_at_100_and_decays_from_next_step`, `test_pause_stops_decay`, `QuanFreshness::test_reserved_items_decay_and_spoil_in_stock`, `FilePrecisionAndDay::test_day_handoff_same_tick_new_ids_next_day_and_no_decay_in_shop`, `test_quan_v12_fresh::PriceByFreshness::test_price_locked_at_cook_start_not_changed_by_waiting` | [test-suite.txt](../proof/phase-3/test-suite.txt) | **Đạt** |
| **AC-P3-05** `spoiled {item_id, kind, location}` đúng tick khi đi từ ≥ 30 xuống < 30, một lần, theo id; mẫu ngưỡng của ticket ra event ở tick 1 | mẫu [threshold.json](../proof/phase-3/threshold.json); `test_fresh_v12::test_spoiled_on_exact_boundary_tick` (tick 61 với 30.5), `test_spoiled_once_and_by_id_and_not_for_already_spoiled` (I2 trước I10) | [threshold.jsonl](../proof/phase-3/threshold.jsonl), [smoke.txt](../proof/phase-3/smoke.txt) | **Đạt** (khớp từng ký tự dòng mẫu) |
| **AC-P3-06** Id `I1, I2…` theo thứ tự vào giỏ, nối tiếp sau id đã nạp, xuyên pha/Ngày; `lost` là cá thể theo LIFO | `test_gather_p1::test_catch_fish_yield_cooldown_and_tie_break`, `test_fresh_v12::test_new_item_starts_at_100…` (I7 → I8), `test_gather_p2` (lost I5, I4), `test_day::test_money_earned_reputation_carry_over_days` (Ngày 2 → I4–I6) | [test-suite.txt](../proof/phase-3/test-suite.txt), [smoke.txt](../proof/phase-3/smoke.txt) | **Đạt** |
| **AC-P3-07** Giữ theo id: cá thể khả dụng tươi nhất, hòa theo id; hàng giữ vừa ươn → nhả, giữ lại đúng một lần theo `order_tick` rồi id bàn; thiếu → `unfulfillable` | `test_fresh_v12::QuanFreshness` (6 test) | [test-suite.txt](../proof/phase-3/test-suite.txt) | **Đạt** |
| **AC-P3-08** Nấu tiêu đúng id đang giữ; `base_price = floor(giá × fresh TB / 100)`; boa trên giá đã chốt; `cook_started.items` sắp kind rồi id | `test_quan_v12_fresh` (CookByInstance, PriceByFreshness, TipOnLockedPrice), `test_fresh_v12::test_cook_uses_reserved_ids_even_if_others_fresher`, `test_integration_gather_quan::test_quan_cooks_and_sells_with_ingredients_from_gather` | [test-suite.txt](../proof/phase-3/test-suite.txt) | **Đạt** |
| **AC-P3-09** day: bàn giao cùng tick, không hao thêm; Ngày đầu giữ id mẫu, Ngày kế cấp id mới; Shop hiện kho cá thể không hao | `test_day::test_dock_hands_over_stock_same_tick`, `test_fresh_v12::test_day_handoff_same_tick_new_ids_next_day_and_no_decay_in_shop`; smoke `--mode day --days 2` | [day2.jsonl](../proof/phase-3/day2.jsonl), [smoke.txt](../proof/phase-3/smoke.txt) | **Đạt** |
| **AC-P3-10** Scenario v1.2: `hold`/`stock` mảng cá thể, `reserved` mảng id trỏ tới cá thể chưa ươn, đủ công thức, không dùng chung; sai → mã 2 trước khi ghi | `test_fresh_v12::BadFixturesV12` (13 fixture sai, đã in lý do từng ca; 5 fixture hợp lệ) | [test-suite.txt](../proof/phase-3/test-suite.txt) | **Đạt** |
| **AC-P3-11** HUD đọc được độ tươi / nhận ra hàng ươn | `chonoi/web/index.html`: thanh tươi mỗi ô giỏ, ô ươn mờ + ✕, dòng giỏ/kho ghi `% tươi` và số món ươn theo loại; kiểm cú pháp JS (`node --check`) và `/state` trả kho cá thể + `freshness` | [smoke.txt](../proof/phase-3/smoke.txt) | **Đạt một phần** — chưa chụp màn hình trên trình duyệt |
| **AC-P3-12** Regression P1–P2 còn hiệu lực đạt; test đổi có lý do; tất định; hiệu năng | 183/183 pass; `day --days 2` chạy lại giống từng byte; 1 Ngày ≈ 0,13 s, 5 Ngày ≈ 1,7 s (≤ 20 s/Ngày) | [test-suite.txt](../proof/phase-3/test-suite.txt), [smoke.txt](../proof/phase-3/smoke.txt) | **Đạt** |
| **AC-P3-13** Ghi tác động, quyết định đổi schema, thứ tự tích hợp; CHANGELOG breaking change | [ADR-0001](../adr/0001-freshness-v12.md), [CHANGELOG.md](../../CHANGELOG.md), [docs/contracts/README.md](../contracts/README.md) | — | **Đạt** |
| Mở rộng Phase 3 (`current`, `reservations`) | — | — | **Chưa làm** (tùy chọn; nhóm đã có mở rộng `burn` từ Phase 2) |

## Lý do cập nhật test cũ (luật v1.2 thay thế)
Tất cả là đổi **fixture và cách so** sang kho cá thể; ý nghĩa từng test giữ nguyên. Mỗi file có ghi chú `TICKET-03 (v1.2) [THAY THẾ]` ở đầu.
- `test_smoke_p1`, `test_qa_regression_p1`, `test_python_starter_units`, `test_gather_p1`, `test_gather_p2`, `test_day`, `test_integration_gather_quan`:
  `hold`/file kho từ mảng kind / object đếm → mảng cá thể; `{"items":{}}` → `{"items":[]}`; so id + kind chính xác, fresh ±0.01;
  `lost` so theo id (LIFO). Các bộ file kho sai thêm ca v1.2 (kho đếm cũ, id trùng, fresh ngoài miền…).
- `test_quan_lat3`, `test_quan_kitchen`, `test_quan_service`, `test_quan_p2_kitchen`, `test_quan_burn`: `stock` → mảng cá thể, `reserved` → mảng id;
  **giá chốt theo độ tươi**: hàng 100 hao 1 tick ở quán trước khi nấu nên giá thấp hơn niêm yết 1 đơn vị (120 → 119, 40 → 39) — kỳ vọng tính từ `freshness` trong contract.
- `test_quan_v12_fresh` (Tiberu2611 viết trước): không sửa, nay chạy (trước skip chờ v1.2).

## Đánh giá ngắn
- **Đạt:** toàn bộ lõi v1.2 — schema/adapter, Lặn, Quán, day, scenario, regression P1–P2, tất định, hiệu năng.
- **Chưa đạt / còn thiếu:** chưa kiểm HUD bằng mắt trên trình duyệt; chưa làm mở rộng Phase 3.
- **Điều cần chỉnh cho Phase 4:** các skill QA ghi log vào `docs/proof/phase-1/` (đè bằng chứng cũ) — nên cho nhận đường dẫn theo phase.
