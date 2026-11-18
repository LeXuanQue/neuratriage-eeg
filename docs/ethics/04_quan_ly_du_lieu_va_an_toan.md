# Kế hoạch quản lý dữ liệu, quy trình an toàn, tài liệu tuyển và giải thích sau phiên

_Bản nháp 2026-11-17. Mục `[ngoặc vuông]` cần điền. Quy định về dữ liệu cá nhân cần đối chiếu với văn bản hiện hành (Nghị định 13/2023/NĐ-CP và luật/nghị định thay thế nếu có); nhóm chưa kiểm tra văn bản mới nhất._

---

## A. Kế hoạch quản lý dữ liệu

### A1. Dữ liệu thu thập

| Dữ liệu | Study | Định danh? | Nơi tạo |
|---|---|---|---|
| Họ tên, liên hệ, chữ ký | 1 | Có | Phiếu đồng ý giấy |
| Bảng nối mã ↔ danh tính | 1, 2 (nếu có bồi dưỡng) | Có | Chủ nhiệm |
| Tín hiệu EEG thô 2 kênh của người đeo | 1 | Mã W.. | App (`data/study_logs/`) |
| Nhật ký thao tác, thời điểm, điều kiện giao diện | 1 | Mã P.. | App (`data/study_logs/P*.jsonl`) |
| Bảng hỏi NASA-TLX, SUS, tin cậy | 1 | Mã | Giấy hoặc biểu mẫu |
| Ghi âm think-aloud và phỏng vấn | 1 (tuỳ chọn) | **Có (giọng nói)** | Máy ghi âm |
| Bản chép ghi âm | 1 | Mã, đã bỏ tên riêng | Nhóm |
| Kết quả chấm EEG | 1 | Không (đoạn đã xáo trộn) | Người chấm độc lập |
| Câu trả lời khảo sát | 2 | Mã ngẫu nhiên C.. | Nền tảng khảo sát |

Dữ liệu sức khoẻ và sinh trắc được xếp vào nhóm **dữ liệu cá nhân nhạy cảm**. Nghiên cứu chỉ thu tối thiểu cần thiết: không thu ngày sinh (chỉ nhóm tuổi), không ghi hình, không thu IP.

### A2. Lưu trữ và quyền truy cập

- **Phiếu giấy** và **bảng nối mã**: tủ có khoá / file mã hoá riêng, chỉ chủ nhiệm truy cập.
- **Dữ liệu số**: máy của nhóm, ổ mã hoá (BitLocker/VeraCrypt hoặc tương đương), sao lưu lên [dịch vụ lưu trữ của trường]. **Không** đưa dữ liệu thô lên dịch vụ đám mây ngoài danh sách được trường cho phép, không chuyển ra nước ngoài.
- Thư mục log của app (`data/study_logs/`) được loại khỏi kho mã nguồn (git), không bao giờ commit.
- **Người chấm độc lập** chỉ nhận thư mục các đoạn EEG đã cắt và xáo trộn (`rating/epochs/`) và bảng chấm trống (`ratings_template.csv`). Người chấm **không** nhận các file khoá (`raw_key.jsonl`, `epoch_key.csv`) hay log gốc `P*.jsonl`, nên không biết đoạn thuộc người nào hay giao diện nào.
- Người phân tích làm việc trên dữ liệu đã mã hoá; chỉ chủ nhiệm nối lại mã khi người tham gia yêu cầu rút dữ liệu.

### A3. Thời hạn lưu và xoá

| Dữ liệu | Thời hạn |
|---|---|
| Ghi âm | Xoá sau khi chép và kiểm tra, tối đa [3] tháng |
| Bảng nối mã | Xoá sau [khi công bố / 1 năm], sau đó dữ liệu thành ẩn danh |
| Phiếu đồng ý | Giữ [5] năm theo quy định |
| Dữ liệu đã mã hoá | Giữ [5] năm, sau đó xoá an toàn |

### A4. Rút lui và yêu cầu của người tham gia

- Rút lui trước [ngày bắt đầu phân tích]: xoá toàn bộ dữ liệu của người đó, ghi lại số lượng (không ghi lý do).
- Sau ngày đó: dữ liệu đã nằm trong phân tích tổng hợp không tách ra được; dữ liệu chưa dùng vẫn được xoá.
- Người tham gia có thể yêu cầu xem dữ liệu của mình qua chủ nhiệm.

### A5. Chia sẻ và công bố

- Bài báo chỉ có số liệu tổng hợp và trích dẫn không định danh.
- Kế hoạch phân tích đăng ký trước trên OSF; mã phân tích công khai.
- EEG của người đeo chỉ được công bố nếu người đó đồng ý riêng (phiếu Study 1 Phần B, mục 9), sau khi bỏ mọi thông tin ngoài mã và tín hiệu.
- Không công bố ghi âm.

### A6. Sự cố dữ liệu

Nếu mất thiết bị hoặc nghi lộ dữ liệu: báo chủ nhiệm trong 24 giờ, chủ nhiệm báo [hội đồng đạo đức / bộ phận phụ trách dữ liệu của trường] và cơ quan có thẩm quyền theo thời hạn luật định, thông báo cho người bị ảnh hưởng.

---

## B. Quy trình an toàn cho người đeo (Study 1)

### B1. Thiết bị

- Brain-Life Focus+: chạy pin, Bluetooth, chỉ đo, không phát dòng điện vào người. Không sạc pin khi đang đeo.
- Bộ sạc dùng tạo nhiễu điện lưới: đặt trên bàn cách thiết bị [20–30] cm, **không nối** với thiết bị hay người đeo, không chạm người.

### B2. Vệ sinh

1. Trước mỗi phiên: lau điện cực bằng cồn 70%, **để khô hoàn toàn** trước khi đặt.
2. Nước muối sinh lý / gel điện cực: lọ mới mỗi ngày, que hoặc bông dùng một lần.
3. Sau phiên: lau da trán người đeo bằng khăn ẩm sạch, đưa khăn khô.

### B3. Kiểm tra da và giới hạn

| | |
|---|---|
| Trước phiên | Hỏi và nhìn da trán. Có đỏ, trầy, mụn viêm ở vị trí điện cực → không đeo phiên đó |
| Sau phiên | Nhìn lại, ghi vào sổ (mã người đeo, giờ, tình trạng da: bình thường / đỏ nhẹ / khác) |
| Giới hạn | Tối đa [4] phiên/ngày/người đeo, nghỉ ≥ [10] phút giữa phiên, cắn hàm ≤ [30] giây mỗi lần |
| Dừng phiên ngay | Người đeo báo rát, ngứa nhiều, đau đầu, chóng mặt; hoặc người điều phối thấy da đỏ rõ |
| Dừng trong ngày | Da đỏ kéo dài > 30 phút sau phiên |

### B4. Báo cáo sự cố

Mọi sự cố (kích ứng da cần nghỉ, ngất, chấn thương) được ghi vào sổ sự cố và báo hội đồng đạo đức trong [thời hạn hội đồng quy định]. Nghiên cứu tạm dừng nếu có [2] người đeo bị kích ứng cần nghỉ.

---

## C. Tài liệu tuyển người

### C1. Người đo (poster / tin nhắn nhóm)

> **Tìm người tham gia nghiên cứu về giao diện thiết bị đo não (EEG)**
> Bạn từ 18 tuổi trở lên và **chưa từng đặt điện cực EEG**? Chúng tôi cần 16 người thử dùng phần mềm hướng dẫn đặt băng đô EEG lên một người tình nguyện. Khoảng 60 phút, tại [địa điểm]. Không cần kiến thức y khoa. Bồi dưỡng: [mức].
> Chúng tôi đánh giá phần mềm, không đánh giá bạn. Tham gia là tự nguyện.
> Liên hệ: [tên, email/điện thoại]. Nghiên cứu đã được [hội đồng] chấp thuận, số [số].

### C2. Người đeo

> **Tìm 4 người tình nguyện đeo băng đô EEG**
> Người khoẻ mạnh từ 18 tuổi, không có bệnh da hay dị ứng ở vùng trán. Bạn ngồi yên khi người khác tập đặt băng đô EEG (thiết bị chỉ đo, chạy pin), khoảng [8–10] phiên × [15] phút trong [số ngày]. Bồi dưỡng: [mức/phiên]. Liên hệ: [...].

### C3. Study 2 (email qua cố vấn lâm sàng)

> Kính gửi anh/chị,
> Nhóm [đơn vị] mời anh/chị tham gia khảo sát trực tuyến khoảng 25 phút về cách trình bày kết quả của hệ thống hỗ trợ phân loại đột quỵ dựa trên EEG. Anh/chị đọc 24 tình huống giả định và cho biết quyết định của mình. Khảo sát không hỏi tên. Tham gia là tự nguyện và không liên quan đến công việc tại đơn vị.
> Đường dẫn: [link]. Nghiên cứu đã được [hội đồng] chấp thuận, số [số].
> [Tên chủ nhiệm, liên hệ]

**Tránh ép buộc:** email được gửi qua danh sách chung, không phải từ cấp trên trực tiếp; không ai biết ai đã tham gia.

---

## D. Giải thích sau phiên (Study 1, người điều phối nói)

> Cảm ơn bạn. Bây giờ tôi giải thích những gì chưa nói lúc đầu.
>
> 1. **Lỗi dựng sẵn.** Trước mỗi lượt, chúng tôi cố ý tạo 3 trong các lỗi sau: một điện cực không làm ướt, băng đầu hơi lỏng, người đeo cắn hàm, và một bộ sạc đặt gần thiết bị. Lượt của bạn có: [liệt kê]. Đây là các lỗi hay gặp ngoài thực tế, nên chúng tôi cần chúng để kiểm tra phần mềm.
> 2. **Hai giao diện.** Một giao diện chỉ cho biết kênh nào tốt hay kém. Giao diện kia thêm lý do và cách sửa. Chúng tôi muốn biết phần lý do và cách sửa có giúp người mới đo nhanh hơn không. Chúng tôi không nói trước giao diện nào là bản mới để bạn dùng cả hai một cách tự nhiên.
> 3. **Kết quả của bạn** chỉ là một phần của số liệu chung, không dùng để đánh giá bạn.
> 4. Xin đừng kể chi tiết các lỗi cho người có thể tham gia sau, để nghiên cứu công bằng.
>
> Bạn có câu hỏi gì không? Nếu sau khi nghe giải thích bạn muốn rút dữ liệu, bạn có thể nói ngay hoặc báo [chủ nhiệm] trước [ngày].
