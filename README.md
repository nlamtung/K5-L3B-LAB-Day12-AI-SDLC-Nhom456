# Day 12 — AI SDLC: Quán Ăn Chợ Nổi (Nhóm 456)

> **Nhóm 456 (5 thành viên)** · Game 2D quản lý quán ăn miền Tây Nam Bộ: Út Sen buổi sáng lặn bắt cá, hái rau trên sông Chín Khúc (`gather`) và buổi tối nấu ăn phục vụ khách trên nhà bè (`quan`).
> **Danh sách thành viên & quy ước nhóm:** [`TEAM.md`](TEAM.md) · **Hợp đồng tích hợp:** [`docs/contracts/README.md`](docs/contracts/README.md) · **Chi tiết kỹ thuật starter:** [`docs/STARTER.md`](docs/STARTER.md)

## Chạy nhanh từ clone sạch (≤ 3 lệnh, macOS / Linux)

Không cần cài đặt thư viện ngoài (chỉ dùng Python 3 thư viện chuẩn):

```bash
git clone https://github.com/nlamtung/K5-L3B-LAB-Day12-AI-SDLC-Nhom456.git && cd K5-L3B-LAB-Day12-AI-SDLC-Nhom456
PYTHONPATH=tests:. python3 -m unittest discover -s tests -v    # Chạy toàn bộ bộ test (1 lệnh)
python3 -m chonoi.live --mode gather                           # Chơi trực tiếp trên trình duyệt (đổi sang --mode quan cho buổi tối)
```

### Chạy nối 2 buổi (Headless / Live) qua file kho (Contract v1.2 — kho cá thể)
```bash
python3 -m chonoi.headless --mode gather --seed 42 --scenario docs/proof/phase-3/dock.json --inputs docs/proof/phase-3/dock-inputs.json --ticks 1 --out gather.jsonl --inventory-out catch.json
python3 -m chonoi.headless --mode quan --seed 42 --inventory catch.json --ticks 0 --out quan.jsonl
python3 -m chonoi.headless --mode day --seed 7 --days 2 --ticks 44400 --out day.jsonl      # vòng ngày gather → quan → shop
```
File kho v1.2 là mảng cá thể `{"items":[{"id":"I1","kind":"ca_linh","fresh":99.99166666666666}]}` (schema: [`docs/contracts/README.md`](docs/contracts/README.md));
file kho đếm cũ `{"items":{"ca_loc":1}}` bị từ chối với mã 2. Xem [`CHANGELOG.md`](CHANGELOG.md) để cập nhật fixture.

## Điều khiển & Cách tính điểm

- **Điều khiển (`chonoi.live`):**
  - `WASD` hoặc phím mũi tên: Bơi (`gather`) / Đi lại trong quán (`quan`).
  - `E` (`interact`): Cập bến hoặc hái rau ở mặt nước (`gather`); nấu, bưng món hoặc phục vụ khách (`quan`).
  - `Space` (`catch`): Bắt đàn cá khi đang lặn dưới nước (`gather`).
  - `R`: Chơi lại từ đầu.
- **Cách tính điểm (Test Contract v1.2):**
  - Công thức ở mọi snapshot và dòng `end`: `score = earned + 100 × floor(reputation)`.
  - Giá món chốt lúc bắt đầu nấu theo độ tươi: `base_price = floor(giá niêm yết × trung bình fresh / 100)`; boa tính trên giá đã chốt.
  - Độ tươi: giỏ −0.5/s, kho quán −0.25/s; dưới 30 là **ươn** (vẫn chiếm ô, không dùng nấu). HUD hiện thanh tươi, `%` theo loại và dấu ✕ cho hàng ươn.
  - Tiền (`money`, `earned`, `shift_earned`) tính bằng số nguyên (đơn vị nghìn đồng); boa (`tip`) = `floor(base_price × tip_rate)` khi tỷ lệ kiên nhẫn còn lại đạt `tip_min_patience_ratio` (cộng thêm `tip_reputation` vào uy tín). Khách bỏ đi vì hết kiên nhẫn trừ uy tín theo `left_reputation_delta`.

## Mở rộng đã làm (nhóm 5 người — yêu cầu ≥ 1 mục)

- **Cháy món (`burn` — khai `"extensions": ["burn"]`, `quan.burn_s: 20`):** Món chín để quá 20 s (`ready_ticks > 1200`) bị bỏ, nguyên liệu mất, bếp rảnh ngay, thử giữ lại 1 lần cho đơn (`reserved` hoặc `unfulfillable`), phát `dish_burnt`.
  - Bằng chứng & test: [`tests/test_quan_burn.py`](tests/test_quan_burn.py) (10/10 test pass), [`docs/proof/phase-2/test-suite.txt`](docs/proof/phase-2/test-suite.txt).

## Sáng tạo của nhóm

- **Nâng cấp giao diện Canvas 2D & hiệu ứng hạt (`chonoi/web/index.html`):** Sóng nước động trên mặt sông, bọt khí khi Út Sen lặn, khói bếp bay khi nấu, hiển thị trực quan trạng thái bếp/bàn/kiên nhẫn và bảng kết thúc buổi.
- **Âm thanh procedural bằng Web Audio API (zero-dependency):** Hiệu ứng âm thanh lặn/nổi (`dive`/`surface`), món chín (`dish_ready`), thu tiền (`paid`) kèm nút bật/tắt âm thanh trên màn hình.
- **Đảm bảo không ảnh hưởng lõi & headless:** Toàn bộ đồ họa và âm thanh chỉ nằm ở phía client trình duyệt (`chonoi/web/index.html`), **tắt hoàn toàn ở chế độ headless** và không thay đổi tick, RNG, sự kiện hay snapshot.
  - Bằng chứng lõi vẫn đúng & tất định từng byte: [`docs/proof/phase-1/test-suite.txt`](docs/proof/phase-1/test-suite.txt), [`docs/proof/phase-1/determinism.txt`](docs/proof/phase-1/determinism.txt), [`docs/verification/phase-1.md`](docs/verification/phase-1.md).

## Kiểm chứng & Tài liệu nhóm

- Kiểm tra danh sách thành viên: `python3 tools/check_team.py`
- Kỹ năng kiểm tra tự động của nhóm: `python3 .agents/skills/verify-contract/verify.py` · `python3 .agents/skills/qa-blackbox-check/run_qa.py`
- Tài liệu: [`docs/verification/phase-1.md`](docs/verification/phase-1.md) · [`phase-2.md`](docs/verification/phase-2.md) · [`phase-3.md`](docs/verification/phase-3.md) · [`ADR-0001`](docs/adr/0001-freshness-v12.md) · [`CHANGELOG.md`](CHANGELOG.md) · [`docs/clarify.md`](docs/clarify.md) · [`docs/ai-usage-log.md`](docs/ai-usage-log.md) · [`docs/standup.md`](docs/standup.md) · [`docs/retro.md`](docs/retro.md) · [`CREDITS.md`](CREDITS.md)
