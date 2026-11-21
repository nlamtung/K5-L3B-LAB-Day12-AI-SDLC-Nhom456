# Giao diện "Chợ nổi Rạch Sen" — bằng chứng (1280×720)

Bản gộp: khung giao diện của TV3 (màn hình, HUD ≥ 18px, khung Bếp Út Sen, cảnh báo) + ảnh 2D miền Tây và menu chọn món tại bếp của TV1 (nlamtung) + nền tảng TV4.

Ảnh chụp bằng Chrome headless từ `python3 -m chonoi.live` với scenario thật trong thư mục này
(`?menu=0&intro=0` chỉ để chụp thẳng vào màn chơi). Giao diện chỉ đọc `/state`, không đổi luật; toàn bộ suite 183 test OK.

| Ảnh | Nội dung | Yêu cầu ticket |
|---|---|---|
| [1-menu.png](1-menu.png) | Menu chính Chơi / Thoát; sim tự tạm dừng khi menu mở | TICKET-02: menu chính |
| [2-day-intro.png](2-day-intro.png) | Má Tư đọc kế hoạch D1, danh sách cần lấy, tự chuyển sau 4 s | TICKET-02: DayIntro |
| [3-gather.png](3-gather.png) | Sông phù sa, bình minh, dừa nước, nhà sàn; "Thủy quái!" + viền tím; oxy < 25% nhấp nháy; độ sâu và vùng; đã lấy/cần; giỏ có độ tươi | TICKET-02 HUD sáng, TICKET-03 độ tươi |
| [4-quan.png](4-quan.png) | Nhà bè (ảnh 2D của TV1) với đèn dây vàng; kiên nhẫn từng bàn đổi màu; tiến độ bếp, "cháy sau N s"; kho khả dụng + hàng ươn; khung "Bếp Út Sen" góc nhìn thứ nhất | TICKET-02 HUD quán, burn, TICKET-03 |
| [5-shop.png](5-shop.png) | Chợ nâng cấp: cấp, giá, tự đóng, kho dư | TICKET-02 Shop |

Màn khác (đã kiểm bằng chạy mã giao diện trên `/state` thật): menu chọn món tại bếp (E ở bếp rảnh; Enter = đơn cũ nhất đúng luật), EveningIntro, DayResult, Summary, menu Pause (Tiếp tục / Về menu / Cài đặt), màn kết thúc buổi.
Chữ HUD ≥ 18 px; giữ Tương phản cao (H), âm thanh, 3 cảnh báo của TV4.
