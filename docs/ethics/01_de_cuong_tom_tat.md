# Đề cương tóm tắt gửi Hội đồng đạo đức

_Bản nháp 2026-11-17. Nguồn: `docs/user_study_protocol.md`. Mục `[ngoặc vuông]` cần điền. Đề nghị xét duyệt **rút gọn** (nghiên cứu rủi ro tối thiểu)._

## 1. Thông tin chung

| | |
|---|---|
| Tên đề tài | Đánh giá giao diện hướng dẫn thu tín hiệu EEG cho người không chuyên và cách diễn đạt kết quả "Chưa xác định" của hệ thống hỗ trợ phân loại đột quỵ |
| Chủ nhiệm | [Họ tên, học hàm, đơn vị] |
| Nghiên cứu viên | [Họ tên, vai trò] |
| Cố vấn lâm sàng | [Bác sĩ thần kinh, đơn vị] (duyệt tình huống Study 2) |
| Đơn vị chủ trì | [Trường / khoa] |
| Địa điểm | Study 1: [phòng thí nghiệm, địa chỉ]. Study 2: trực tuyến |
| Thời gian dự kiến | [tháng 12/2026] – [tháng 3/2027] |
| Kinh phí | [nguồn] |

## 2. Bối cảnh và lý do

Điện não đồ (EEG) đo trước khi nhập viện có thể giúp phân loại người bệnh nghi đột quỵ, nhưng trong nghiên cứu lớn nhất ở xe cấp cứu, khoảng một phần ba bản ghi do nhân viên cấp cứu đo không dùng được, chủ yếu vì chất lượng tín hiệu. Nhóm nghiên cứu đã phát triển một phần mềm:

1. chấm chất lượng từng kênh EEG theo thời gian thực, nói rõ **kênh nào** có vấn đề, **vì sao**, và **cần làm gì**;
2. cho phép hệ thống trả lời "Chưa xác định" (No-Decision) với tỉ lệ báo động nhầm được kiểm soát.

Hai câu hỏi chỉ trả lời được khi có người tham gia:
- Hướng dẫn theo từng kênh có giúp người chưa từng đo EEG thu được tín hiệu tốt nhanh hơn không? (Study 1)
- Cách diễn đạt "Chưa xác định" có khiến người ra quyết định bỏ sót đột quỵ không? (Study 2)

**Đây không phải nghiên cứu lâm sàng.** Không có người bệnh, không chẩn đoán, không trả kết quả y tế.

## 3. Mục tiêu

- **Study 1:** so sánh thời gian đến khi có 60 giây tín hiệu dùng được giữa hai giao diện: (B) chỉ báo chất lượng theo kênh, (G) chỉ báo kèm lý do và lời khuyên.
- **Study 2:** so sánh tỉ lệ quyết định kích hoạt quy trình đột quỵ khi hệ thống trả "Chưa xác định", giữa hai cách diễn đạt.

## 4. Thiết kế và quy trình

### Study 1 (trực tiếp, khoảng 60 phút cho người đo)

- **Người tham gia:**
  - 16 người đo (operator): ≥ 18 tuổi, chưa từng tự đặt điện cực EEG.
  - 4 người đeo (wearer): khoẻ mạnh, ≥ 18 tuổi, không tổn thương da trán, không dị ứng nước muối/gel.
  - Thêm 2–3 người đo thử (pilot), cùng quy trình, không tính vào phân tích.
- **Thiết bị:** băng đô EEG tiêu dùng Brain-Life Focus+ (2 điện cực ở trán, chạy pin, kết nối Bluetooth, **không nối điện lưới**). Không phải thiết bị y tế, không dùng để chẩn đoán.
- **Nhiệm vụ:** người đo đặt băng đô cho người đeo và cố thu được 60 giây tín hiệu tốt nhanh nhất có thể, tối đa 8 phút mỗi lượt. Mỗi người đo làm 2 lượt, mỗi lượt một giao diện, thứ tự được đối trọng.
- **Lỗi dựng sẵn:** mỗi lượt bắt đầu với 3 lỗi có chủ đích, vô hại: một điện cực không làm ướt, băng đầu hơi lỏng, người đeo cắn hàm theo hiệu lệnh, bộ sạc đang cắm điện đặt gần thiết bị.
- **Đo lường:** thời gian đến khi tín hiệu dùng được (một người chấm độc lập, không biết giao diện), thành công trong 8 phút, nguyên nhân lỗi người đo nêu ra, bảng hỏi NASA-TLX, SUS, mức tin cậy, phỏng vấn 10 phút. Ghi âm suy nghĩ thành lời (think-aloud) **chỉ khi có đồng ý riêng**.
- **Người đeo:** tham gia nhiều phiên. Tối đa [4] phiên mỗi ngày, nghỉ ít nhất [10] phút giữa các phiên, kiểm tra da trán trước và sau mỗi phiên (xem `04_quan_ly_du_lieu_va_an_toan.md`).

### Study 2 (trực tuyến, khoảng 25 phút)

- **Người tham gia:** ≥ 40 (mục tiêu 60) bác sĩ cấp cứu/thần kinh, điều dưỡng cấp cứu, sinh viên y năm cuối.
- **Nhiệm vụ:** đọc 24 tình huống giả định về nghi đột quỵ trước viện, mỗi tình huống kèm màn hình kết quả của hệ thống (**kết quả do nhóm nghiên cứu soạn sẵn, không phải của người bệnh thật, có thể sai**). Với mỗi tình huống, trả lời: có kích hoạt quy trình đột quỵ không, độ tự tin, mức ảnh hưởng của kết quả EEG.
- **Phân nhóm ngẫu nhiên:** hai nhóm thấy hai cách diễn đạt khác nhau của "Chưa xác định". Người tham gia **không được báo trước** điều này để không ảnh hưởng câu trả lời; trang cuối giải thích đầy đủ (xem mục 6).
- **Tình huống:** do nhóm soạn, cố vấn thần kinh duyệt đáp án và độ khó. Không dùng hồ sơ bệnh nhân thật.

## 5. Nguy cơ và lợi ích

| Nguy cơ | Mức | Biện pháp giảm |
|---|---|---|
| Kích ứng da trán do điện cực, nước muối, cồn lau | Thấp | Loại trừ người có tổn thương da/dị ứng; điện cực lau cồn 70% và để khô trước khi đặt; kiểm tra da trước/sau mỗi phiên; dừng ngay nếu đỏ, rát |
| Mỏi, khó chịu do đeo nhiều lượt, cắn hàm theo hiệu lệnh | Thấp | Giới hạn số phiên/ngày, nghỉ giữa phiên, cắn hàm tối đa [30] giây mỗi lần, người đeo được dừng bất kỳ lúc nào |
| Điện giật | Không đáng kể | Thiết bị chạy pin; bộ sạc dùng làm nguồn nhiễu đặt **gần** thiết bị, **không nối** với thiết bị hay người đeo |
| Căng thẳng do bị bấm giờ, bị quan sát | Thấp | Nói rõ là đánh giá giao diện, không đánh giá năng lực cá nhân; kết quả cá nhân không chia sẻ cho ai |
| Lộ danh tính, dữ liệu sinh trắc | Thấp | Mã hoá danh tính, lưu mã hoá, không đưa lên dịch vụ ngoài trường (xem `04_…`) |
| Hiểu lầm bản ghi EEG là xét nghiệm | Thấp | Phiếu đồng ý ghi rõ không ai đọc EEG theo nghĩa lâm sàng, không trả kết quả |
| Study 2: thông tin không đầy đủ về phân nhóm | Thấp | Trang giải thích cuối khảo sát; cho phép rút dữ liệu sau khi đọc giải thích |

**Lợi ích:** không có lợi ích trực tiếp cho người tham gia ngoài [bồi dưỡng]. Lợi ích xã hội: góp phần làm EEG trước viện dùng được bởi người không chuyên, và làm rõ cách trình bày kết quả AI để tránh bỏ sót đột quỵ.

## 6. Thông tin không đầy đủ (incomplete disclosure) và giải thích sau

- **Study 1:** người đo biết thiết bị "có thể được cố ý đặt lệch hoặc gây nhiễu", nhưng không biết lỗi cụ thể nào và không biết giao diện nào là giao diện mới. Sau phiên, người điều phối giải thích các lỗi đã dựng và mục đích so sánh.
- **Study 2:** người tham gia biết kết quả hệ thống trong tình huống là giả lập và có thể sai, nhưng không biết có hai cách diễn đạt. Trang cuối giải thích hai cách diễn đạt và lý do, và cho chọn rút dữ liệu.
- Lý do cần thiết: nếu biết trước, người tham gia sẽ chú ý khác thường vào đúng yếu tố đang được đo, làm sai kết quả. Việc không báo trước không gây hại và được giải thích đầy đủ ngay sau đó.

## 7. Đồng ý tham gia

- Study 1: phiếu thông tin và đồng ý bằng giấy, ký trước khi bắt đầu; người đeo có phiếu riêng (`02_phieu_dong_y_study1.md`).
- Study 2: đồng ý điện tử ở trang đầu khảo sát (`03_phieu_dong_y_study2.md`).
- Các mục tuỳ chọn tách riêng: ghi âm, chia sẻ dữ liệu EEG ẩn danh công khai, liên hệ cho nghiên cứu sau.
- Tự nguyện, rút lui bất kỳ lúc nào không cần lý do, không ảnh hưởng đến học tập, công việc hay bồi dưỡng.
- **Tránh ép buộc:** người tuyển không phải giảng viên chấm điểm hay cấp trên trực tiếp của người tham gia; kết quả cá nhân không gửi cho trường hay nơi làm việc.

## 8. Dữ liệu

Tóm tắt; chi tiết trong `04_quan_ly_du_lieu_va_an_toan.md`. Mã người tham gia (P01, W01, C001…), bảng nối mã với danh tính lưu riêng và mã hoá, dữ liệu lưu trên máy của nhóm (ổ mã hoá), giữ [5] năm, chỉ công bố số liệu tổng hợp và trích dẫn ẩn danh.

## 9. Xung đột lợi ích

Nhóm nghiên cứu phát triển phần mềm được đánh giá và có kế hoạch thương mại hoá. Biện pháp:
- công khai trong phiếu đồng ý và trong bài báo;
- thước đo chính của Study 1 do **người chấm độc lập** (không thuộc nhóm phát triển) đánh giá, không biết giao diện;
- kế hoạch phân tích được **đăng ký trước** trên OSF sau khi được duyệt và trước phiên đầu tiên;
- kết quả được công bố dù thuận lợi hay không.

## 10. Bồi dưỡng

| Đối tượng | Mức | Ghi chú |
|---|---|---|
| Người đo | [mức] | Trả đủ kể cả khi dừng giữa chừng |
| Người đeo | [mức/phiên] | Trả theo số phiên đã tham gia |
| Study 2 | [mức hoặc không] | Không phụ thuộc việc làm hết khảo sát |

## 11. Tài liệu kèm theo

1. Phiếu thông tin và đồng ý Study 1 (người đo, người đeo)
2. Phiếu thông tin và đồng ý điện tử Study 2
3. Kế hoạch quản lý dữ liệu và quy trình an toàn
4. Tài liệu tuyển người, kịch bản giải thích sau phiên
5. Công cụ đo: NASA-TLX, SUS, thang tin cậy Jian et al. (2000), câu hỏi phỏng vấn (protocol, phụ lục A), 24 tình huống Study 2 [sau khi cố vấn duyệt]
6. Đề cương đầy đủ: `docs/user_study_protocol.md`
7. CV và chứng nhận đào tạo đạo đức nghiên cứu / GCP của nghiên cứu viên [nếu hội đồng yêu cầu]
