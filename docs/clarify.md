# Clarify — câu hỏi và câu trả lời (PO ghi, cả nhóm dùng chung)

> Nguồn: [`docs/prd/PRD-0.md`](prd/PRD-0.md) (chép từ lab board). Lát 3 được code trước khi có PRD (Q1–Q13 là giả định ban đầu),
> sau đó đối chiếu PRD-0 và sửa. Câu còn mở (Q14+) cần hỏi **Anh Năm hàng xóm** trên lab board; chưa có trả lời thì giữ giả định.

## Đã chốt theo PRD-0

| # | Câu hỏi | Giả định ban đầu | PRD-0 nói | Kết quả |
|---|---|---|---|---|
| Q1 | Lịch khách tính theo tick nào? | `duration − time_left` | D: "lịch khách tính theo phase_tick kể cả khi rút ngắn ca"; F: dùng phase_tick sau tăng | **Sai → đã sửa** (`QuanSim.phase_tick`) |
| Q2 | Tới lượt mà hết bàn? | Bỏ lượt, không sự kiện | F5: "Không còn bàn thì bỏ lượt" | Đúng |
| Q3 | Khách chọn món thế nào? | Ngẫu nhiên đều theo seed, món sắp theo id | F5: "Chọn đều theo seed trong 3 món đủ nguyên liệu khả dụng"; E: id món theo mã Unicode | Đúng |
| Q4 | `no_dish` data? | `{table_id}` | E: `{}` khi có bàn mà thiếu món | **Sai → đã sửa** |
| Q5 | Giữ chỗ có trừ `stock`? | Không; khả dụng = stock − Σ reserved | D: stock "gồm cả phần giữ chỗ"; F5: "tồn vật lý trừ phần giữ" | Đúng |
| Q6 | Kiên nhẫn & rời bàn trong bước? | Giảm và rời ngay ở đầu bước | F1 giảm kiên nhẫn; F4 (sau interact) mới xét rời; "Phục vụ đúng tick kiên nhẫn về 0 vẫn hợp lệ" | **Sai → đã sửa** (`_tick_patience` + `_settle_customers`) |
| Q7 | Tên/data sự kiện khách đến, rời? | `customer_arrived {customer_id,…}`, `customer_left {customer_id,table_id,dish_id}` | E: `customer_arrived {order_id,table_id,dish_id}`, `customer_left {order_id,table_id,reason,reputation}` | **Sai data → đã sửa** |
| Q8 | `random_customers: false`? | Tắt khách tự sinh | D: "tắt khách tự sinh, vẫn dùng khách fixture" | Đúng |
| Q9 | Trạng thái khách? | `waiting`/`eating` | D: state `waiting`/`eating` + `order_status` `reserved/assigned/unfulfillable/served` | **Thiếu → đã thêm** |
| Q10 | `reserved` của khách fixture? | Luôn suy ra, cấm khai | D: được khai; thiếu ở đơn reserved thì cấp theo công thức; khai khác công thức → mã 2 | **Sai → đã sửa** |
| Q11 | Trường khách fixture? | 7 trường, `price` | D: 11 trường, `base_price`, mặc định waiting / order_tick 0 / kiên nhẫn đầy / reserved | **Sai → đã sửa** |
| Q12 | `hand` dạng gì? | null / chuỗi / `{dish_id}` | D: payload `{order_id,dish_id,base_price}` hoặc null | **Sai → đã sửa** |
| Q13 | Hết ca thì khách chờ? | (chưa xử lý) | F4: rời với `closing`, không trừ uy tín; dọn xong mới `quan_end`; không có lượt khách mới | **Đã thêm** |

## Còn mở (hỏi Anh Năm)

| # | Ngày | Câu hỏi | Giả định đang dùng | Ai quyết | Code |
|---|---|---|---|---|---|
| Q14 | 2026-11-21 | Khách chưa chốt giá/boa thì `base_price`, `tip` trong snapshot là gì? | `null` cho tới khi lát 4 chốt (giá khi bắt đầu nấu, boa khi phục vụ) | TV2 + TV3 | `QuanSim._spawn_customer`, `_customer_from_scenario` |
| Q15 | 2026-11-21 | `stoves[].dish` có dạng gì? | Payload món `{order_id,dish_id,base_price}` như `hand` (suy từ "bếp và tay giữ cùng đơn", "món không khớp đơn") | TV2 + TV3 | `scenario._payload` |
| Q16 | 2026-11-21 | Tiền tố id khách mới? | `C` (C1, C2, … nối sau id fixture lớn nhất) | TV2 | `_spawn_customer` |
| Q17 | 2026-11-21 | Khách fixture `waiting` với `patience_ticks_left: 0` có hợp lệ? | Hợp lệ; rời ở bước 1 (sau interact) với `patience` | TV2 | `scenario._validate_customer` |
| Q18 | 2026-11-21 | Ràng buộc `order_tick` của khách fixture? | Chỉ cần nguyên không âm | TV2 | `scenario._validate_customer` |
| Q19 | 2026-11-21 | `payload.base_price` có phải bằng `menu.price`? | Chỉ kiểm nguyên dương (PRD nói "chốt giá", có thể đổi ở phase sau) | TV2 + TV3 | `scenario._payload` |

## Phase 3 (TICKET-03, v1.2 độ tươi) — giả định đã dùng

| # | Ngày | Câu hỏi | Giả định đang dùng | Ai quyết | Code |
|---|---|---|---|---|---|
| Q25 | 2026-11-21 | Biểu diễn độ tươi để so ngưỡng 30 và floor giá chính xác? | 240 đơn vị nguyên / điểm (ticket gợi ý): giỏ −2/tick, quán −1/tick; giá tính `Fraction` trên tổng đơn vị. Giá trị đọc vào lệch lưới giữ dạng `Fraction` | khanhduyvu1 (ADR-0001) | `chonoi/fresh.py` |
| Q26 | 2026-11-21 | Trong một tick gather, `node_regrown` hay `spoiled` trước? | Cùng bước 1: hồi nút (`node_regrown`) rồi mới hao giỏ (`spoiled`) — theo thứ tự liệt kê "hồi nút và độ tươi" | khanhduyvu1 | `GatherSim.step` |
| Q27 | 2026-11-21 | Hàng giữ vừa ươn, giữ lại thất bại: có event riêng không? | Không có event mới; chỉ đổi `order_status` sang `unfulfillable` (thấy trong snapshot). Đơn `unfulfillable` không tự quay lại `reserved` khi kho đổi | khanhduyvu1 | `QuanSim._tick_freshness` |
| Q28 | 2026-11-21 | Nhiều đơn cùng bị ươn: nhả hết rồi mới giữ lại, hay xử lý lần lượt? | Lần lượt theo `order_tick` rồi id bàn: mỗi đơn nhả phần giữ của mình rồi thử giữ lại ngay | khanhduyvu1 | `QuanSim._tick_freshness` |
| Q29 | 2026-11-21 | Thứ tự id trong `customers[].reserved` (snapshot)? | Sắp theo id (I2 trước I10) | khanhduyvu1 | `QuanSim.reserve_for` |
| Q30 | 2026-11-21 | Event `gather` / `fish_caught` có thêm id cá thể không? | Giữ nguyên data v1.1 (`amount` / `yield`); id cá thể thấy trong `hold` snapshot | khanhduyvu1 | `GatherSim.step` |
| Q31 | 2026-11-21 | Khách bị cháy món (mở rộng `burn`) có giá cũ không? | `base_price` về `null`, chốt lại theo độ tươi ở lần nấu sau | khanhduyvu1 | `QuanSim._burn` |
