# khanhduyvu1 (Vũ Duy Khánh) — phản tư cá nhân (≤ 200 từ)

Vai thực tế: TV2 — PO · Change Request v1.2 (Độ tươi).

- Tôi đã làm (kèm link commit):
  - Lập tài liệu phân tích thay đổi kiến trúc độ tươi: [bc81bdd](https://github.com/nlamtung/K5-L3B-LAB-Day12-AI-SDLC-Nhom456/commit/bc81bdd) (`docs/adr/0001-freshness-v12.md`)
  - Cài đặt toàn bộ lõi v1.2 độ tươi: [e3ebe7d](https://github.com/nlamtung/K5-L3B-LAB-Day12-AI-SDLC-Nhom456/commit/e3ebe7d) (kho cá thể trong `inventory.py`, `fresh.py` 240 đơn vị/điểm, hao tươi ở giỏ/kho, giữ chỗ theo id tươi nhất, nhả và giữ lại khi ươn, giá theo độ tươi)
  - Nâng cấp HUD hiển thị thanh độ tươi và dấu ươn: [9c1dc7e](https://github.com/nlamtung/K5-L3B-LAB-Day12-AI-SDLC-Nhom456/commit/9c1dc7e)
- Tôi đã review (kèm link): Rà soát hợp đồng tích hợp Lát 3–4, nghiệm thu test suite Phase 3 với 14 bài test độc lập `test_fresh_v12.py` qua PR #13.
- AI sai ở đâu và tôi phát hiện thế nào: Ban đầu AI import nhầm `TUNING` trước khi định nghĩa gây lỗi import toàn cục; ở Phase 1 AI đoán sai quy tắc lịch khách khi chưa đọc PRD. Tôi phát hiện khi chạy test suite và đọc kỹ diff.
- Điều tôi học được: Quy trình AI SDLC đòi hỏi chốt kỹ hợp đồng dữ liệu và đọc kỹ TICKET/PRD trước khi giao việc cho AI, giúp kiểm soát tốt các breaking changes lớn như độ tươi v1.2.
