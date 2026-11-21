# Thiết kế Kỹ thuật: Nâng cấp Đồ họa 2.5D Giả 3D (Stylized Low-Poly Canvas) cho Quán Ăn Chợ Nổi

**Ngày:** 2026-11-21  
**Tác giả:** TV4 (`Presceltooo`) & Antigravity  
**Module:** `client/ui` (`chonoi/web/index.html`)

## 1. Mục tiêu (Intent & Goals)
- Nâng cấp toàn diện mặt thị giác của game mô phỏng Chợ Nổi từ 2D flat sang phong cách **2.5D Isometric / Giả 3D (Faux-3D Stylized)** lấy cảm hứng từ các model render Blender.
- Tận dụng sức mạnh của HTML5 Canvas 2D: hiệu ứng đổ bóng đa hướng (drop shadows & ambient occlusion), vách vát khối hộp (beveled edges, isometric depth), texture vân gỗ và hiệu ứng quang học mặt nước (water caustics/refraction).
- **Ràng buộc:** Hoàn toàn chạy ở client web, không thêm thư viện ngoài (zero-dependency), không sửa server `live.py` hay schema hợp đồng, không ảnh hưởng đến chế độ headless.

## 2. Các thành phần nâng cấp chi tiết

### A. Cảnh Lặn Hái Sông Nước (`gather`)
- **Tầng nước & Chiều sâu:** Phân lớp 3 tầng nước (mặt sông sáng, tầng giữa lơ lửng rong rêu hạt nước, đáy sông sâu thẳm).
- **Thuyền & Bến:** Vẽ thuyền tam bản dạng khối 2.5D có lòng thuyền, mui vòm lá dừa, cọc bến đóng cừ tràm có vân và bóng râm trên mặt nước.
- **Thợ lặn Út Sen:** Vẽ dạng khối nhân vật đeo bình khí, kính lặn có viền kính phản quang, chân vịt uốn lượn khi bơi, đèn pin rọi nón ánh sáng định hướng.
- **Cá & Rong rau:** Cá có vây 3D, mắt ngọc và vảy bóng; bụi rau muống/bông súng nổi bề mặt có búp hoa và bóng râm chiếu xuống đáy.

### B. Cảnh Quán Ăn Chợ Nổi (`quan`)
- **Sàn tàu & Không gian:** Mặt sàn ghép ván gỗ có rãnh viền đổ bóng nổi, lan can thuyền beveled xung quanh với sóng nước vỗ quanh be thuyền.
- **Bếp nấu (Stoves):** Bếp lò đất nung Nam Bộ hình khối 2.5D với miệng lò đỏ lửa than, bóng đổ dài trên sàn, nồi đất hoặc chảo xào đang bốc khói nhiệt.
- **Bàn ăn & Khách (Tables & Customers):** Bàn tròn gỗ dày dặn có chân bàn và bóng râm; ghế ngồi; khách ăn dạng nhân vật 2.5D với biểu cảm khuôn mặt sống động, đĩa thức ăn 3D nổi trên bàn.
- **Người phục vụ:** Nhân vật bưng mâm có chiều cao khối, đổ bóng tròn dưới chân di chuyển theo hướng input.

### C. HUD & Trải nghiệm
- Bảng điều khiển viền kính mờ (glassmorphism), các thanh đo bo tròn có độ bóng sáng (specular highlight), typography rõ ràng, biểu tượng trực quan.
