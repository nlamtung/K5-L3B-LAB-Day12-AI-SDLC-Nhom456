# Presceltooo (Đỗ Duy Tùng) — phản tư cá nhân (≤ 200 từ)

Vai thực tế: TV4 — Scrum/Release, `client/ui` & Sáng tạo đồ họa/âm thanh.

- Tôi đã làm (kèm link commit):
  - Dựng Canvas 2D mượt mà, hệ thống hạt (bọt khí, khói bếp) và âm thanh procedural Web Audio: [df0ce82](https://github.com/nlamtung/K5-L3B-LAB-Day12-AI-SDLC-Nhom456/commit/df0ce82) · [PR #5](https://github.com/nlamtung/K5-L3B-LAB-Day12-AI-SDLC-Nhom456/pull/5)
  - Cập nhật nhật ký sử dụng AI TV4 đầy đủ theo phase: [4b676ff](https://github.com/nlamtung/K5-L3B-LAB-Day12-AI-SDLC-Nhom456/commit/4b676ff) · [PR #9](https://github.com/nlamtung/K5-L3B-LAB-Day12-AI-SDLC-Nhom456/pull/9)
  - Hoàn thiện Chế độ Tương phản Cao (High Contrast), 3 Cảnh báo tiếp cận trực quan và HUD Cá Sấu Năm Chèo: [PR #14](https://github.com/nlamtung/K5-L3B-LAB-Day12-AI-SDLC-Nhom456/pull/14)
- Tôi đã review (kèm link): Rà soát `docs/superpowers/specs/2026-11-21-faux-3d-canvas-ui-design.md`, kiểm tra chéo các mốc headless test và live browser đảm bảo zero-dependency.
- AI sai ở đâu và tôi phát hiện thế nào: Ban đầu AI đề xuất dùng Blender CLI không có trong môi trường; sau đó cơ chế bắt sự kiện âm thanh bị kẹt sau 40 sự kiện do cửa sổ trượt server. Tôi phát hiện qua `/requesting-code-review` và sửa sang `lastProcessedTick`.
- Điều tôi học được: Phối hợp AI theo chu trình Brainstorming -> Plan -> Execute -> Review giúp phát hiện lỗi tiềm ẩn sớm; luôn kiểm thử thực tế trên browser song song với headless test.
