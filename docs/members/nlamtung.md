# nlamtung — phản tư cá nhân

- **Tôi đã làm:**
  - Thiết lập repo chung, điền `TEAM.md` & `game.contract.json`, chốt hợp đồng tích hợp `docs/contracts/README.md` (`0c643da`).
  - Cài đặt toàn bộ `chonoi/sim/gather.py` Lát 1–2 và `tests/test_gather_p1.py` (`cd5bce0`), hoàn thiện DoD Phase 1 & sửa lỗi `[object Object]` của `st.dish` trên UI (`6363ebc`).
  - Nâng cấp contract v1.1 (`f7a3543`), cài đặt cá bơi/sinh cá & Cá Sấu Năm Chèo `chonoi/sim/monsters.py` + `tests/test_gather_p2.py` (`d10af5d`), tích hợp khối `day` trong `scenario.py`, bật mở rộng `burn` và chốt tag `phase-2` (`32d868f`).
  - Rà soát DoD Phase 4, sửa schema `bench.py`/`soak.py` về đúng TICKET-04 v1.3, hoàn thiện `README.md`, `CHANGELOG.md`, `docs/retro.md` và gắn tag `phase-3`, `phase-4`.
- **Tôi đã review & hỗ trợ:** Review và gộp các PR của TV2, TV3, TV4, TV5 (PR #2–#16), xử lý xung đột `scenario.py` và điều phối phân công 5 người.
- **AI sai ở đâu & cách phát hiện:** AI từng bỏ sót 3 test P1 bị ảnh hưởng khi bật số liệu v1.1 và xuất thiếu trường `p1_low_fps`/`results[]` ở `bench.py`/`soak.py`; tôi phát hiện qua chạy full `unittest` và đối chiếu trực tiếp TICKET-04.
- **Bài học:** Luôn yêu cầu AI dừng lại hỏi khi thiếu đặc tả (PRD/TICKET), và đối chiếu schema JSON từng trường trước khi gắn tag phát hành.
