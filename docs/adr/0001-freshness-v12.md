# ADR-0001: Kho cá thể và độ tươi (Change Request "Mùa Nước Nổi", Test Contract v1.2)

- Trạng thái: chấp nhận
- Ngày, người quyết: 2026-11-21, Vũ Duy Khánh (`khanhduyvu1`) — Phase 3

## Bối cảnh
TICKET-03 thay kho đếm theo loại `{"items": {kind: n}}` bằng kho cá thể `{"items": [{id, kind, fresh}]}`, thêm hao tươi,
hàng ươn (< 30), giữ chỗ theo id và giá theo độ tươi. Đây là breaking change của hợp đồng tích hợp gather → quan
(file kho, `gather_end.inventory`, snapshot `hold`/`stock`, `customers[].reserved`, `cook_started.items`, `lost`).

## Các lựa chọn đã cân nhắc
1. **Số thực (float) cho `fresh`** — đơn giản nhưng sai ở ngưỡng 30 và ở `floor` giá (vd. 30 − k/120 cộng dồn sai số).
2. **`Fraction` cho mọi cá thể** — chính xác nhưng chậm (≈ 40 cá thể × 22.200 tick/Ngày).
3. **Đơn vị nguyên: 240 đơn vị / điểm tươi** (ticket gợi ý) — giỏ −2/tick, quán −1/tick, ngưỡng 7.200; giá tính bằng
   `Fraction` trên tổng đơn vị. Giá trị đọc vào không đúng lưới giữ dạng `Fraction` (vẫn chính xác).

## Quyết định
- Chọn **phương án 3** (`chonoi/fresh.py`, lớp `Freshness`). Cá thể trong sim là `{id, kind, u}`; ra JSONL/file là `{id, kind, fresh}`.
- File kho v1.2 xuất theo id, `fresh` là float đủ chính xác (`k/240` đọc lại được đúng `k` đơn vị — giữ nhánh ở ngưỡng).
- Bên đọc chọn schema theo `contract_version` (`inventory.read_inventory(path, version)`); v1.2 từ chối kho đếm (mã 2).
- Id cá thể cấp bằng `IdAllocator.new("I")`: nối tiếp xuyên pha và Ngày (day dùng chung một allocator).
- Trong day bàn giao bản chính xác trong bộ nhớ (`GatherSim.handoff_items()`), không đi qua float.

## Hệ quả — bảng tác động

| Module | File cần đổi | Test bị ảnh hưởng | Người phụ trách |
|---|---|---|---|
| Adapter / schema | `chonoi/fresh.py` (mới), `chonoi/inventory.py`, `chonoi/contract.py`, `game.contract.json` (`1.2`, `freshness`) | `test_integration_gather_quan`, `test_smoke_p1`, `test_qa_regression_p1` (đổi fixture), `test_fresh_v12` (mới) | khanhduyvu1 |
| Lặn | `chonoi/sim/gather.py`, `chonoi/sim/monsters.py` (`lost` là cá thể) | `test_gather_p1`, `test_gather_p2` (đổi fixture/so sánh), `test_fresh_v12::GatherFreshness` | khanhduyvu1 |
| Quán | `chonoi/sim/quan.py` (kho cá thể, giữ theo id, ươn → giữ lại 1 lần, giá theo tươi) | `test_quan_lat3`, `test_quan_kitchen`, `test_quan_service`, `test_quan_p2_kitchen`, `test_quan_burn` (đổi fixture, giá chốt theo tươi); `test_quan_v12_fresh` (Tiberu2611 viết trước, nay chạy) | khanhduyvu1 |
| day | `chonoi/sim/day.py` (bàn giao cá thể, Ngày kế cấp id mới, Shop không hao) | `test_day` (đổi fixture, thêm kiểm id Ngày 2) | khanhduyvu1 |
| Scenario | `chonoi/scenario.py` (`hold`/`stock` là mảng cá thể, `reserved` là mảng id) | `test_fresh_v12::BadFixturesV12` | khanhduyvu1 |
| HUD | `chonoi/web/index.html` (thanh tươi, dấu ươn, % theo loại), `chonoi/live.py` (gửi `freshness`) | `test_live` (giữ nguyên) | khanhduyvu1 |
| QA | `tests/helpers.py` (`items`, `stock_of`, `counts`, `kinds`) | toàn bộ regression P1–P2 | khanhduyvu1 |

## Thứ tự tích hợp (giữ main chạy được)
1. `fresh.py` + `inventory.py` hỗ trợ **cả hai** schema theo `contract_version` (adapter).
2. Lặn → Quán → day chuyển sang cá thể; `contract_version` vẫn có thể để `1.1` cho tới bước 3.
3. Bật `contract_version: "1.2"` + `freshness`, cập nhật fixture test cũ (ghi lý do trong từng file test), chạy smoke file + day.
4. HUD đọc cả mảng cá thể lẫn object đếm cũ, nên không phụ thuộc thứ tự gộp.
