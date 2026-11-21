# Retro nhóm

## Phase 2 (nhanh)
- Điều tốt: Chia 2 người phụ trách trọn lõi Phase 2 (TV1 `gather`/`monsters`/`contract v1.1`, TV3 `quan`/`day`/`shop`/`pause`/`burn`) giúp merge không xung đột file code; mở rộng `burn` đã có sẵn test từ cuối P1 nên bật chạy xanh ngay.
- Điều tệ: `chonoi/scenario.py` khối `day` và cập nhật `test_smoke_p1.py` bị dồn sang bước tích hợp cuối; phần UI Menu/Pause/HUD vòng ngày của TV4 chưa kịp gộp trước tag `phase-2`.
- 1 hành động cho Phase 3: Ngay 5 phút đầu Phase 3, TV2 + TV1 chốt trước adapter `chonoi/inventory.py` v1.2 và `scenario.py` trên nhánh tích hợp rồi mới ghép `gather`/`quan`/`day` (TV1 chịu trách nhiệm chốt & merge sớm).

## Phase 4 (cuối)
- Rà lại hành động Phase 2: **Đã làm.** Ở Phase 3, TV2 (`khanhduyvu1`) tách hẳn `chonoi/fresh.py` + `inventory.py` v1.2, viết ADR-0001 trước rồi tích hợp đồng bộ 1 lượt nên PR #13 gộp sạch không vỡ test.
- Điều tốt / điều tệ:
  - *Tốt:* Chia tổ gối đầu 1–2 người/phase giảm rõ rệt xung đột file; bộ 183 test + 2 skills (`verify-contract`, `qa-blackbox-check`) bảo vệ tốt tính tất định từng byte qua 4 lần nâng cấp contract (v1.0 → v1.3); hoàn thành mở rộng `burn` và UI High Contrast + 3 cảnh báo.
  - *Tệ:* Một số giai đoạn merge song song giữa GitHub và local tạo commit merge phụ; ban đầu schema JSON của `bench.py`/`soak.py` lệch tên trường so với TICKET-04 (đã phát hiện khi rà soát DoD Phase 4 và sửa kịp trước khi tag).
- Số liệu:
  - *Số commit trên `main` theo người:* `Tiberu2611` (24), `nlamtung` (21+), `Presceltooo` / Do Duy Tung (6), `khanhduyvu1` / Khánh Vũ (5), `nguyenduong43` / Nguyen Tung Duong (5) — 5/5 thành viên đều đạt ≥ 3 commit có nội dung.
  - *Cách đọc code của nhau:* Review chéo qua Pull Request trên GitHub (16 PR), kết hợp chạy `unittest` & `verify-contract` trước khi merge.
  - *Token theo người:* Xem chi tiết tại [`docs/ai-usage-log.md`](ai-usage-log.md) (`nguyenduong43` ~65k, `Presceltooo` ~35k, các thành viên còn lại chưa đo trực tiếp từ IDE).
- Một lần AI sai và cách nhóm phát hiện:
  - Ở Phase 1, AI của TV2 code khi chưa có PRD-0 nên đoán sai 9/13 quy tắc (lịch khách, thứ tự rời bàn, tên trường event); ở Phase 4, AI sinh `bench.py`/`soak.py` sai tên trường JSON (`min_fps`/`days_requested` thay vì `p1_low_fps`/`days`/`results[]`). Cả hai đều được phát hiện bằng cách đối chiếu từng dòng với đặc tả TICKET và chạy kiểm chứng hộp đen trước khi gắn tag.
- Nếu làm lại, đổi gì: Chốt trước bảng schema JSON đầu ra cho từng lệnh CLI (`headless`, `bench`, `soak`) ngay 5 phút đầu mỗi phase và luôn kéo `origin/main` trước khi mở PR để tránh merge dư.
