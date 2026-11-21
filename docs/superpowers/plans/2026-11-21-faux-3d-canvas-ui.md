# Faux-3D Canvas UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nâng cấp toàn diện giao diện `chonoi/web/index.html` sang đồ họa giả 3D 2.5D (Faux-3D / Stylized Low-Poly) bằng Canvas 2D thuần.

**Architecture:** Mở rộng module vẽ của `chonoi/web/index.html` với các hàm vẽ khối 2.5D isometric, ánh sáng gradient, bóng đổ ambient/drop shadows, hiệu ứng khúc xạ nước và hạt khói/bọt khí.

**Tech Stack:** HTML5 Canvas 2D, Web Audio API, Vanilla JavaScript, CSS3.

**Spec:** `docs/superpowers/specs/2026-11-21-faux-3d-canvas-ui-design.md`

## Global Constraints
- Zero-dependency: không import external scripts/stylesheets/images/fonts từ internet.
- Chế độ headless và test suite của starter không bị ảnh hưởng (không sửa `chonoi/live.py` hay backend).
- Giữ nguyên cấu trúc API endpoint `/state` và `/input`.

## Review Focus
1. Render loop duy trì ổn định 60 FPS không bị lag do tính toán gradient/shadow quá mức.
2. Tương thích đầy đủ devicePixelRatio (Retina displays không bị mờ/lệch tọa độ).
3. Khi resize cửa sổ trình duyệt, tỷ lệ và vị trí các khối 2.5D tự co giãn mượt mà.
4. Trạng thái kết nối mất mạng / offline được hiển thị trang nhã, không đè vỡ layout.
5. Âm thanh Web Audio API tự động kích hoạt mượt mà khi người dùng nhấn phím hoặc click chuột.

---

### Task 1: Cài đặt hệ thống Render Khối 2.5D & Vật liệu Shading trong `chonoi/web/index.html`

**Files:**
- Modify: `chonoi/web/index.html`

**Interfaces:**
- Produces: `drawBlock(ctx, x, y, w, h, depth, topColor, sideColor, frontColor)`, `drawShadow(ctx, x, y, rX, rY, blur)`

- [ ] **Step 1: Viết các hàm tiện ích dựng khối isometric và đổ bóng 2.5D**
- [ ] **Step 2: Nâng cấp cảnh Lặn Sông Nước (`drawGather`) sang đồ họa giả 3D (Thuyền tam bản khối, tia sáng dưới nước, cá và Út Sen có chiều sâu)**
- [ ] **Step 3: Nâng cấp cảnh Quán Ăn Chợ Nổi (`drawQuan`) sang đồ họa giả 3D (Sàn ván gỗ beveled, bếp lò đất nung đỏ lửa than, bàn tròn có bóng râm, khách 2.5D)**
- [ ] **Step 4: Kiểm tra trực quan và chạy kiểm thử không có hồi quy regression**

Run: `PYTHONPATH=tests:. python3 -m unittest discover -s tests -v`
Expected: PASS 93/93 tests.

- [ ] **Step 5: Commit thay đổi lên nhánh `feat/tv4-canvas-audio-ui`**

```bash
git add chonoi/web/index.html docs/superpowers/
git commit -m "feat(ui): nâng cấp toàn diện đồ họa 2.5D giả 3D canvas cho cả hai cảnh gather và quan"
```
