# Credits

## Tài sản đồ họa & âm thanh
- **Đồ họa 2D (`chonoi/web/index.html`, `chonoi/web/assets/*.jpg`):** Bộ nền (`bg_gather.jpg`, `bg_quan.jpg`) và sprite 2D (`ut_sen_swim.jpg`, `ca_sau.jpg`, `fish_sheet.jpg`, `quan_props.jpg`, `plants_sheet.jpg`) do nhóm tự tạo bằng AI image generator phục vụ riêng cho lab, kết hợp vẽ bổ sung bằng HTML5 Canvas 2D (tắt hoàn toàn ở headless).
- **Âm thanh (`chonoi/web/index.html`):** Tự tổng hợp bằng Web Audio API procedural (zero-dependency, không dùng file audio ngoài).
- **Bối cảnh & nhân vật:** Bản gốc của lab Day 12 — Quán Ăn Chợ Nổi (VinUni AI20k).

## Công cụ AI đã sử dụng
- **Antigravity (Gemini):** Hỗ trợ phân tích yêu cầu, chia việc, lập trình `sim/gather`, xây dựng skills/regression tests (`verify-contract`, `qa-blackbox-check`) và kiểm chứng Phase 1.
- **Claude Code (Claude):** Hỗ trợ lập trình `sim/quan`, validation `scenario.py`, đối chiếu PRD-0 và kiểm thử tích hợp.
