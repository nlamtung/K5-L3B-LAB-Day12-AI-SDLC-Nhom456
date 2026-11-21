# Changelog

## v1.0.0 — Phase 4 (Test Contract v1.3 — Phát hành)
- Nâng `contract_version: "1.3"`, khai báo `bench_cmd` (`chonoi/bench.py`) và `soak_cmd` (`chonoi/soak.py`) trong `game.contract.json`.
- `bench_cmd` đo cảnh buổi sáng lõi (warm-up 3s + đo 30s), xuất đúng 5 trường `avg_fps, p1_low_fps, frames, measured_s, load_ms`.
- `soak_cmd` chạy 10 ngày lặp D1–D5 liên tục với `crashes = 0`, xuất `days, days_completed, crashes, results[], duration_s`.
- Nâng cấp UI tiếp cận: Chế độ tương phản cao (`H`), 3 cảnh báo trực quan động (oxy cạn, thủy quái gần, khách sắp giận), HUD Cá Sấu.
- Hoàn thiện hồ sơ nghiệm thu (`docs/verification/phase-4.md`, `docs/proof/phase-4/`, `docs/retro.md`, phản tư cá nhân) và đóng gói phát hành `v1.0.0`.

## Phase 3 — Test Contract v1.2 (TICKET-03 "Mùa Nước Nổi": độ tươi)

### ⚠️ Breaking change
- **Kho đếm → kho cá thể.** File kho, `gather_end.data.inventory`, snapshot `hold` (gather) và `stock` (quán, Shop) đổi từ
  `{"items": {"ca_loc": 1}}` / `["ca_loc"]` sang mảng cá thể:
  ```json
  {"items":[{"id":"I1","kind":"ca_linh","fresh":100},{"id":"I2","kind":"ca_loc","fresh":97.5}]}
  ```
  Kho rỗng là `{"items":[]}`. Với `contract_version: "1.2"`, file kho đếm cũ, sai schema, kind lạ, id trùng hoặc
  `fresh` ngoài `[0, 100]` → **mã 2**.
- **`customers[].reserved`** đổi từ map `{kind: n}` sang **mảng id cá thể**.
- **`cook_started.data.items`**, **`monster_hit.data.lost`**, **`faint.data.lost`** đổi từ mảng kind sang mảng cá thể
  (`items` sắp theo kind rồi id; `lost` theo thứ tự bỏ LIFO).
- **Giá món** chốt khi bắt đầu nấu: `base_price = floor(giá niêm yết × trung bình fresh / 100)` (trước là giá niêm yết).

### Thêm
- `game.contract.json`: `contract_version: "1.2"`, `tuning.freshness {initial: 100, gather_decay_per_s: 0.5,
  quan_decay_per_s: 0.25, spoiled_below: 30}`.
- Hao tươi: giỏ −0.5/s ở đầu bước gather, kho quán −0.25/s (cả hàng đang giữ) trước tương tác; pause, Shop, món chín không hao.
- Event `spoiled {item_id, kind, location: "hold"|"stock"}` đúng một lần khi đi từ ≥ 30 xuống < 30, theo id.
- Giữ chỗ theo id (cá thể khả dụng tươi nhất, hòa theo id); hàng giữ vừa ươn → nhả và giữ lại đúng một lần
  (theo `order_tick` rồi id bàn), thiếu → `unfulfillable`.
- Id cá thể `I1, I2, …` theo thứ tự vào giỏ, nối tiếp xuyên pha và Ngày; trong day Ngày kế cấp id mới cho mẫu `gather.hold`.
- HUD: thanh độ tươi trong ô giỏ, ô hàng ươn mờ kèm dấu ✕, dòng giỏ/kho ghi `% tươi` trung bình và số món ươn theo loại.

### Cách cập nhật fixture
| Trước (v1.1) | Sau (v1.2) |
|---|---|
| `"hold": ["ca_loc", "bong_sung"]` | `"hold": [{"id":"I1","kind":"ca_loc","fresh":100}, {"id":"I2","kind":"bong_sung","fresh":100}]` |
| `"stock": {"ca_loc": 1}` | `"stock": [{"id":"I1","kind":"ca_loc","fresh":100}]` |
| `"reserved": {"ca_loc": 1}` | `"reserved": ["I1"]` (hoặc bỏ trống cho đơn `reserved` để sim tự cấp) |
| `{"items": {}}` | `{"items": []}` |

Trong test dùng helper `tests/helpers.py`: `items("ca_loc", "bong_sung")`, `stock_of({"ca_loc": 1})`, `counts(...)`, `kinds(...)`.
Chi tiết quyết định và bảng tác động: [`docs/adr/0001-freshness-v12.md`](docs/adr/0001-freshness-v12.md).

## Phase 2 — Test Contract v1.1 (TICKET-02 "Một ngày ở chợ nổi")
- Số liệu chuẩn v1.1: 6 nguyên liệu (thêm `ca_keo`, `keo_neo`), 6 món, 6 nút `N1`–`N6`, 2 bếp `B1`–`B2`, 4 bàn `T1`–`T4`, 8 đàn cá bơi/phản xạ/sinh cá (trần 12), Cá Sấu Năm Chèo `M1`/`M2`.
- Thêm `--mode day`, `--days 1..5`, vòng `gather → quan → shop`, kế hoạch D1–D5, nâng cấp `oxygen`/`hp`, cơ chế `pause` ở cả 3 mode.
- Hoàn thành mở rộng bắt buộc **Cháy món (`burn`, `burn_s: 20`)** kèm 10 test trong `tests/test_quan_burn.py`.

## Phase 1 — Test Contract v1.0 (PRD-0)
- Hoàn thiện 2 chế độ lõi `gather` (oxy, ngạt, Máu, ngất LIFO, hái rau, bắt cá, cập bến) và `quan` (khách, giữ chỗ, bếp, bưng, phục vụ, boa, uy tín), nối nhau qua file kho nguyên tử.
- Thiết lập bộ test tự động, 2 skills (`verify-contract`, `qa-blackbox-check`) và giao diện Canvas 2D + Web Audio API zero-dependency.
