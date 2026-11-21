# Phase 4 UI Accessibility, Warnings & DoD Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hoàn thiện toàn diện các hạng mục của TV4 (`Presceltooo`) cho Phase 2–4: Chế độ tương phản cao (High Contrast), 3 cảnh báo trực quan chữ/icon (Thủy quái, Oxy cạn, Khách sắp giận), hỗ trợ HUD Cá Sấu Năm Chèo & Pause, bổ sung phản tư `docs/members/Presceltooo.md` và cập nhật `README.md`.

**Architecture:** Mở rộng giao diện `chonoi/web/index.html` với High Contrast palette, alert banners, HUD monsters & pause overlay; cập nhật tài liệu phát hành và hoàn thành DoD cá nhân của TV4.

**Tech Stack:** HTML5 Canvas 2D, Vanilla JavaScript, CSS3.

**Spec:** `phase_2_3_4_plan.md` mục Pod Phase 4 (TV4).

## Global Constraints
- Zero-dependency: không dùng thư viện ngoài, không tải ảnh/font ngoài.
- Không sửa backend (`sim/`, `live.py`), không phá vỡ Test Contract headless (toàn bộ test suite giữ nguyên 100% pass).
- Tài liệu phản tư `docs/members/Presceltooo.md` viết ngắn gọn, đúng format và ≤ 200 từ.

## Review Focus
1. Chế độ High Contrast chuyển đổi tức thì khi bấm nút hoặc phím tắt `H`, tăng tối đa độ tương phản cho người khiếm thị.
2. 3 cảnh báo (Quái gần, Oxy cạn < 25%, Khách sắp giận < 25%) xuất hiện đúng ngữ cảnh, nhấp nháy thu hút sự chú ý.
3. Không làm giảm FPS của vòng lặp render Canvas 2D.
4. Đảm bảo toàn bộ 100+ tests hiện có tiếp tục PASS xanh.

---

### Task 1: Nâng cấp `chonoi/web/index.html` với High Contrast, 3 Cảnh báo & HUD Quái / Pause

**Files:**
- Modify: `chonoi/web/index.html`

- [ ] **Step 1: Thêm nút chuyển High Contrast và phím tắt `H`, phím `P`/`Esc` cho Pause**
- [ ] **Step 2: Triển khai 3 Banner cảnh báo chữ & icon (Thủy quái gần, Oxy cạn, Khách sắp giận)**
- [ ] **Step 3: Vẽ Cá Sấu Năm Chèo (M1, M2) và lớp phủ Pause/DaySummary**
- [ ] **Step 4: Chạy test suite kiểm tra regression**
- [ ] **Step 5: Commit với tài khoản TV4 `Presceltooo`**

### Task 2: Hoàn thiện DoD Tài liệu & Phản tư cá nhân của TV4

**Files:**
- Create: `docs/members/Presceltooo.md`
- Modify: `README.md`
- Modify: `docs/standup.md`

- [ ] **Step 1: Viết phản tư cá nhân `docs/members/Presceltooo.md` (≤ 200 từ, có link commit, AI sai ở đâu, bài học)**
- [ ] **Step 2: Cập nhật `README.md` phần hướng dẫn phím tắt (H: High Contrast, P: Pause) và tính năng Accessibility**
- [ ] **Step 3: Cập nhật `docs/standup.md` ghi nhận hoàn tất Phase 4 cho TV4**
- [ ] **Step 4: Chạy lại test suite để xác nhận 100% xanh**
- [ ] **Step 5: Commit và mở PR lên `main`**
