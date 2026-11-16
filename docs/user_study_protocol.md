# Protocol user study: NeuraTriage EEG (C4 + C5)

_Bản nháp 2026-11-16, dùng cho hồ sơ đạo đức và để pre-register trước khi chạy. Các mục trong `[ngoặc vuông]` phải điền theo quy định của trường. Liên kết với `docs/uist2027_plan.md` mục 1 (C4, C5) và mục 4 (R2)._

## 0. Tóm tắt

| | Study 1 (C4) | Study 2 (C5) |
|---|---|---|
| Câu hỏi | Lý do và lời khuyên theo từng kênh có giúp người không chuyên thu được EEG dùng được nhanh hơn so với chỉ báo chất lượng theo kênh không? | Cách diễn đạt No-Decision có làm người ra quyết định bỏ sót stroke không? |
| Người tham gia | 16 người đo không có kinh nghiệm EEG + 4 người đeo thiết bị (khoẻ mạnh) | 40–60 người có chuyên môn y (bác sĩ, điều dưỡng, sinh viên y năm cuối) |
| Thiết kế | Trong-chủ-thể, 2 điều kiện, đối trọng thứ tự | Hỗn hợp: cách diễn đạt (giữa chủ thể) × đầu ra AI (trong chủ thể) |
| Hình thức | Trực tiếp, khoảng 60 phút | Online, khoảng 25 phút |
| Kết quả chính | Thời gian đến khi có 60 s tín hiệu dùng được, do người chấm độc lập đánh giá | Tỉ lệ kích hoạt quy trình stroke ở ca stroke khi AI trả No-Decision |
| Rủi ro | Tối thiểu (EEG bề mặt, không xâm lấn) | Tối thiểu (tình huống giả định, không có dữ liệu bệnh nhân) |

**Không phải nghiên cứu lâm sàng.** Không có bệnh nhân, không có chẩn đoán, không trả kết quả y tế cho người tham gia.

---

## 1. Study 1: người mới tập đo EEG

### 1.1 Câu hỏi và giả thuyết

Động lực: 32% bản ghi EEG trước viện trong ELECTRA-STROKE không dùng được, chủ yếu do chất lượng tín hiệu. SQI v2 (`backend/sqi_v2.py`) chấm từng kênh và đưa ra lý do kèm hành động sửa.

- **H1 (chính):** khi có lý do và lời khuyên cho từng kênh (điều kiện G), thời gian đến khi có tín hiệu dùng được ngắn hơn so với khi chỉ có chỉ báo chất lượng theo kênh (điều kiện B).
- **H2:** tỉ lệ thu được tín hiệu dùng được trong giới hạn thời gian cao hơn ở G.
- **H3:** người đo xác định đúng nguyên nhân lỗi nhiều hơn ở G.
- **H4:** tải nhận thức (NASA-TLX) thấp hơn và khả dụng (SUS) cao hơn ở G.

### 1.2 Người tham gia

**Người đo (operator), N = 16:**
- Tiêu chí nhận: ≥ 18 tuổi; chưa từng tự đặt điện cực EEG.
- Ưu tiên có 2–4 người là nhân viên cấp cứu hoặc điều dưỡng, gần với người dùng thật nhất.
- Tuyển qua [kênh của trường].

**Người đeo (wearer), N = 4:**
- Người khoẻ mạnh, ≥ 18 tuổi, đeo headband cho nhiều người đo.
- Loại trừ: tổn thương da vùng trán, dị ứng với gel/nước muối.
- Người đeo cũng ký phiếu đồng ý riêng.

**Cỡ mẫu:** kiểm định cặp, hiệu ứng d = 0.8, α = 0.05, power 0.8 cần khoảng 15 người. Chọn 16 để chia đều 2 thứ tự đối trọng. d = 0.8 là giả định, **pilot với 2–3 người** (không tính vào mẫu) để kiểm tra lại trước khi chạy chính thức.

### 1.3 Thiết bị và điều kiện

- **Thiết bị:** Brain-Life Focus+ (2 kênh AF3/AF4), stream BLE vào app (`backend/app/services/device_source.py`).
- **Điều kiện B (baseline mạnh, đổi 2026-11-16):** giao diện hiện tại cộng với **chỉ báo chất lượng theo từng kênh**, gồm thanh điểm và nhãn Đạt/Kém, giống chỉ báo tiếp xúc của headband tiêu dùng. **Không** có lý do, lời khuyên hay chỉ định kênh cần sửa.
  - Lý do đổi: reviewer có thể cho rằng "chỉ báo theo kênh đã có sẵn" (kiểm tra trở kháng trong phần mềm EEG lâm sàng, chỉ báo tiếp xúc trên headband tiêu dùng). Với B mạnh, khác biệt duy nhất giữa hai điều kiện là **lý do kèm hành động**, tức đúng phần đóng góp mới.
  - URL: `?condition=B`.
- **Điều kiện G (guidance):** như B, thêm điểm chất lượng từng kênh, lý do và lời khuyên của SQI v2 (`guidance()`).
  - Hai điều kiện dùng chung phần còn lại của giao diện. Người đo không được biết điều kiện nào là "mới".
  - Ngưỡng SQI v2 phải được **đóng băng** (sau khi chỉnh trên TUAR) trước pilot.

### 1.4 Lỗi được dựng sẵn

Để hướng dẫn có tác dụng, mỗi lượt đo bắt đầu với **3 lỗi dựng sẵn**, chọn ngẫu nhiên từ danh sách dưới đây. Hai điều kiện có cùng tập lỗi, chỉ khác thứ tự.

| Lỗi | Cách dựng | Lý do SQI v2 tương ứng |
|---|---|---|
| Điện cực khô | Không làm ướt một điện cực | `drift` / `flat` |
| Băng lỏng | Nới một bên băng đầu | `drift` / `transient` |
| Cắn hàm | Người đeo cắn hàm theo tín hiệu của người điều phối | `muscle` |
| Nhiễu điện | Đặt bộ sạc đang cắm điện gần thiết bị | `line_noise` |

Lỗi "cắn hàm" kéo dài suốt thời gian người đo chưa yêu cầu người đeo thả lỏng. Người đeo được tập trước để làm giống nhau giữa các lượt.

### 1.5 Quy trình (khoảng 60 phút)

1. Giới thiệu, ký phiếu đồng ý (5 phút).
2. Huấn luyện chung 5 phút: cách đeo headband, nhiệm vụ là gì. Không giải thích các lý do của SQI v2.
3. **Lượt 1:** điều kiện thứ nhất, người đeo A.
   - Nhiệm vụ: *"Thu được 60 giây tín hiệu tốt nhanh nhất có thể."*
   - Giới hạn 8 phút. Người đo nói to suy nghĩ (think-aloud), có ghi âm nếu được đồng ý.
4. NASA-TLX và SUS cho điều kiện thứ nhất.
5. **Lượt 2:** điều kiện thứ hai, người đeo B, tập lỗi mới.
6. NASA-TLX và SUS cho điều kiện thứ hai.
7. Phỏng vấn bán cấu trúc 10 phút, có mẫu câu hỏi ở phụ lục A.

**Đối trọng:** 2 thứ tự điều kiện (BG/GB) × ghép người đeo × tập lỗi, phân bổ bằng hình vuông Latin trên 16 người đo.

**Vệ sinh:** lau điện cực bằng cồn 70% giữa các lượt.

### 1.6 Đo lường

- **Chính, thời gian đến khi dùng được (TTU):** thời điểm sớm nhất mà 60 s liên tiếp được đánh giá là dùng được.
  - **Người chấm độc lập** (có kinh nghiệm đọc EEG) chấm từng đoạn 10 s là dùng được hoặc không, trên bản ghi đã lưu. Người chấm **không biết** đoạn đó thuộc điều kiện nào.
  - Không dùng SQI v2 làm thước đo chính, vì làm vậy sẽ thiên vị cho điều kiện G.
  - Một người chấm thứ hai chấm 20% bản ghi để tính Cohen's κ.
- **Phụ:**
  - Thành công trong 8 phút (có hoặc không).
  - Tỉ lệ đoạn dùng được trong 60 s cuối.
  - TTU theo tiêu chí SQI v1 và SQI v2 (chỉ để tham khảo, ghi rõ là có thiên vị).
  - Số hành động sửa, lấy từ log của app.
  - Xác định đúng nguyên nhân lỗi: người đo nói ra nguyên nhân, hai người mã hoá từ bản ghi âm.
  - NASA-TLX, SUS, độ tin cậy vào hệ thống (thang Jian et al. 2000).

### 1.7 Phân tích (pre-register)

- **H1:** Wilcoxon signed-rank trên TTU ghép cặp. Lượt quá 8 phút được gán 8 phút; với kiểm định theo hạng, cách gán này là bảo thủ. Phân tích độ nhạy: mô hình Cox có frailty theo người đo, coi lượt quá giờ là censored.
- **H2:** McNemar.
- **H3:** GLMM logistic, đúng/sai ~ điều kiện + (1 | người đo) + (1 | loại lỗi).
- **H4:** Wilcoxon signed-rank.
- Báo cáo effect size kèm CI 95% bằng bootstrap theo người đo. Kiểm tra hiệu ứng thứ tự (B trước so với G trước).
- **Không** phân tích tìm kiếm thêm khi chưa đánh dấu là exploratory.

---

## 2. Study 2: cách diễn đạt No-Decision

### 2.1 Câu hỏi và giả thuyết

Jabbour et al. (2025, N = 259 bác sĩ) cho thấy khi AI từ chối trả lời, bác sĩ chẩn đoán thiếu tăng 18% so với không có AI. R2 (`backend/conformal_triage.py`) đẩy phần lớn ca stroke khó vào No-Decision thay vì báo "bình thường" (miss ≤ α). Vì vậy cách diễn đạt No-Decision quyết định ca đó có bị bỏ sót hay không.

- **H5 (chính):** với ca stroke mà AI trả No-Decision, tỉ lệ kích hoạt quy trình stroke ở nhóm **diễn đạt có hành động (F-A)** cao hơn ở nhóm **diễn đạt trơn (F-P)**.
- **H6:** ở nhóm F-P, tỉ lệ kích hoạt khi AI trả No-Decision thấp hơn so với khi không có AI (lặp lại kết quả của Jabbour).
- **H7:** ở nhóm F-A, tỉ lệ đó không thấp hơn khi không có AI (kiểm định non-inferiority, biên 10 điểm %).

### 2.2 Người tham gia

- Bác sĩ cấp cứu/thần kinh, điều dưỡng cấp cứu, sinh viên y năm cuối. **Tối thiểu N = 40** (20 mỗi nhóm), mục tiêu 60.
- Tuyển qua [mạng lưới của cố vấn lâm sàng], ghi rõ vai trò và số năm kinh nghiệm để phân tích theo nhóm.
- **Cỡ mẫu:** mỗi người xem 5 ca stroke có No-Decision, nên phân tích dùng GLMM với khoảng 200–300 quyết định. Với N = 40, chỉ đủ phát hiện khác biệt lớn (khoảng 20 điểm %). Vì vậy H5 được báo cáo kèm ước lượng hiệu ứng và CI, không chỉ p-value. Đây là giới hạn đã biết trước.

### 2.3 Tài liệu

- **24 tình huống giả định** về nghi stroke trước viện: 12 stroke, 12 giống stroke (hạ đường huyết, co giật sau cơn, migraine có tiền triệu, liệt Bell…).
  - Mỗi tình huống gồm tuổi, giới, thời điểm khởi phát, sinh hiệu, mô tả thăm khám kiểu NIHSS rút gọn, và màn hình kết quả của hệ thống EEG.
  - Thông tin lâm sàng được viết để **mơ hồ vừa phải**, tránh ca quá dễ.
  - **Cố vấn lâm sàng (thần kinh) duyệt** đáp án đúng và độ khó trước khi chạy. Bắt buộc, chưa có người.
- **Đầu ra AI**, trong chủ thể, mỗi người xem đủ 4 loại:

  | Đầu ra | Số ca | Ghi chú |
  |---|---|---|
  | Không có AI | 6 (3 stroke, 3 giống stroke) | Mốc so sánh |
  | Báo động | 4 | 3 đúng, 1 sai, để không dạy người tham gia tin tuyệt đối |
  | Yên tâm | 4 | 3 đúng, 1 sai |
  | No-Decision | 10 (5 stroke, 5 giống stroke) | Đối tượng chính của H5 |

  Tổng: 12 stroke (3 + 3 + 1 + 5) và 12 giống stroke (3 + 1 + 3 + 5).

- **Cách diễn đạt No-Decision**, giữa chủ thể:
  - **F-P (trơn):** "Không đủ chắc chắn để đưa ra kết quả."
  - **F-A (có hành động):** "**Chưa xác định — không có nghĩa là bình thường.** Tín hiệu hiện tại chưa đủ để loại trừ stroke. Tiếp tục quy trình stroke chuẩn. Có thể đo lại sau khi chỉnh điện cực AF4." Có thêm lý do (`ambiguous` / `quality`) dưới dạng chữ, không hiển thị xác suất (theo Bondi et al. 2022).
  - Hai bản được dịch và kiểm tra bởi [người song ngữ]. Study chạy bằng tiếng Việt.
- Ánh xạ tình huống với đầu ra AI được xoay vòng theo 4 danh sách, để mỗi tình huống xuất hiện với mọi loại đầu ra trên toàn mẫu.

### 2.4 Quy trình (online, khoảng 25 phút)

1. Thông tin và đồng ý điện tử.
2. Câu hỏi nền: vai trò, số năm kinh nghiệm, mức quen thuộc với AI.
3. Giải thích một trang về hệ thống, giống nhau cho cả hai nhóm, trừ định nghĩa No-Decision theo nhóm.
4. 24 tình huống theo thứ tự ngẫu nhiên. Mỗi tình huống hỏi:
   - (a) Có kích hoạt quy trình stroke và chuyển tới trung tâm đột quỵ không?
   - (b) Độ tự tin, thang 1–7.
   - (c) Mức ảnh hưởng của kết quả EEG tới quyết định, thang 1–7.
5. Câu hỏi cuối: tin cậy, khả dụng, và người tham gia hiểu "No-Decision" nghĩa là gì (câu tự luận).
6. Kiểm tra chú ý: 2 câu, loại theo quy tắc đã pre-register.

### 2.5 Phân tích (pre-register)

- **H5:** GLMM logistic, kích hoạt ~ cách diễn đạt + (1 | người tham gia) + (1 | tình huống), chỉ trên ca stroke có No-Decision. Báo cáo OR kèm CI 95%.
- **H6, H7:** GLMM trên ca stroke với đầu ra AI ∈ {không có AI, No-Decision} × cách diễn đạt. H7 dùng biên non-inferiority 10 điểm %, chốt trước khi chạy.
- **Phụ:**
  - Tỉ lệ kích hoạt ở ca giống stroke có No-Decision, để đo cái giá là báo động thừa.
  - Độ tự tin.
  - Phân tích theo vai trò (exploratory).
  - Mã hoá định tính câu trả lời về ý nghĩa của "No-Decision".

---

## 3. Đạo đức và dữ liệu (chung)

- **Mức rủi ro:** tối thiểu.
  - Study 1 dùng EEG bề mặt, không xâm lấn, không kích thích; cảm giác chỉ như đeo băng đô.
  - Study 2 chỉ dùng tình huống giả định, không có dữ liệu bệnh nhân thật.
- **Không trả kết quả y tế.** Bản ghi EEG của người đeo không được ai đọc theo nghĩa lâm sàng. Phiếu đồng ý ghi rõ: *"Đây không phải xét nghiệm; nhóm nghiên cứu sẽ không và không thể nhận xét gì về sức khoẻ của bạn."* Không có quy trình xử lý phát hiện tình cờ, vì không có ai đọc lâm sàng.
- **Tự nguyện:** rút lui bất kỳ lúc nào, không cần lý do. Dữ liệu đã thu sẽ bị xoá nếu người tham gia yêu cầu trước khi phân tích, tức trước [ngày].
- **Ẩn danh hoá:**
  - Mã người tham gia (`P01`, `W01`…), bảng nối mã với danh tính lưu riêng, có mã hoá.
  - EEG, log và phiếu hỏi chỉ mang mã.
  - Ghi âm think-aloud là tuỳ chọn có đồng ý riêng, được gỡ thành văn bản rồi xoá file âm thanh sau [N] tháng.
- **Lưu trữ:** máy của nhóm nghiên cứu, ổ được mã hoá. Không đưa dữ liệu thô lên dịch vụ đám mây ngoài [dịch vụ trường cho phép]. Giữ [N] năm theo quy định.
- **Công bố:** chỉ số liệu tổng hợp và trích dẫn ẩn danh. Có thể công bố dữ liệu EEG đã ẩn danh nếu người tham gia đồng ý riêng.
- **Bồi dưỡng:** [mức], không phụ thuộc kết quả hay việc hoàn thành.
- **Xung đột lợi ích:** nhóm nghiên cứu phát triển hệ thống được đánh giá và có kế hoạch thương mại hoá. Ghi rõ trong phiếu đồng ý và trong bài báo. Người chấm TTU không thuộc nhóm phát triển, nếu có thể.

---

## 4. Điều kiện tiên quyết kỹ thuật (trước pilot)

| Việc | Trạng thái |
|---|---|
| Ngưỡng SQI v2 đóng băng trên TUAR | Đang chờ dữ liệu |
| Giao diện điều kiện G: điểm từng kênh + lý do + lời khuyên trong `screen-live.jsx` | Xong 2026-11-16: `ChannelQualityPanel`, message WS `channel_quality` (`app/services/channel_quality.py`) |
| Chế độ thí nghiệm: chọn điều kiện B/G, ẩn mọi gợi ý điều kiện nào là mới | Một phần: `?condition=B` chỉ hiện chỉ báo theo kênh (không lý do/lời khuyên); chưa khoá thanh điều hướng/tweaks trong lúc chạy study |
| Log sự kiện có timestamp ISO 8601: điểm SQI, thay đổi trạng thái, đánh dấu của người điều phối | Chưa làm |
| Lưu bản ghi thô theo mã người tham gia để người chấm đọc mù | Chưa làm |
| Công cụ chấm từng đoạn 10 s cho người chấm, không hiện điều kiện | Chưa làm |
| Tình huống giả định và màn hình đầu ra AI (Study 2) | Chưa làm, cần cố vấn lâm sàng |
| Nền tảng khảo sát online cho Study 2 | Chọn theo trường |

## 5. Lịch (khớp `docs/uist2027_plan.md`)

| Tuần | Việc |
|---|---|
| 1–2 (từ 16/11) | Điền các mục `[…]`, nộp hồ sơ đạo đức, tìm cố vấn lâm sàng và người chấm |
| 3–6 | Làm các điều kiện tiên quyết ở mục 4, viết tình huống giả định, pre-register (OSF) |
| 7–9 | Pilot Study 1 (2–3 người) và Study 2 (3–5 người), chỉnh tài liệu, **khoá protocol** |
| 9–14 | Chạy chính thức cả hai study, chấm TTU mù |
| 14–16 | Phân tích theo đúng kế hoạch đã pre-register |

## 6. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Hồ sơ đạo đức duyệt chậm | Nộp tuần 1–2. Study 2 rủi ro thấp hơn, có thể xin duyệt rút gọn riêng |
| Không tìm được cố vấn lâm sàng | Study 2 không chạy được nếu thiếu người này. Hỏi ngay qua [mạng lưới] |
| Thiếu bác sĩ tham gia | Chấp nhận sinh viên y năm cuối, phân tích theo vai trò |
| Thiết bị BLE mất kết nối giữa lượt | Ghi lại, lặp lượt với tập lỗi dự phòng. Pilot để ước lượng tần suất |
| Hiệu ứng trần (lượt nào cũng xong nhanh) | Pilot. Nếu cần, tăng số lỗi dựng sẵn từ 3 lên 4 trước khi khoá protocol |

---

## Phụ lục A. Câu hỏi phỏng vấn (Study 1)

1. Khi tín hiệu xấu, bạn dựa vào đâu để biết phải làm gì?
2. Có lúc nào hệ thống nói một điều nhưng bạn thấy khác không? Kể lại.
3. Với điều kiện có hướng dẫn: lời khuyên nào hữu ích, lời khuyên nào khó làm theo?
4. Nếu bạn là nhân viên cấp cứu trên xe, điều gì cần thay đổi để dùng được?
5. Bạn hiểu "No-Decision" nghĩa là gì?

## Phụ lục B. Tài liệu tham khảo

- **Jabbour, Fouhey, Banovic, et al.** "Selective Prediction Reduces the Negative Effects of Automation Bias Overall but Increases False Negatives." arXiv 2508.07617 (2025).
- **Bondi et al.** "Role of Human-AI Interaction in Selective Prediction." AAAI 2022.
- **Beede et al.** "A Human-Centered Evaluation of a Deep Learning System Deployed in Clinics for the Detection of Diabetic Retinopathy." CHI 2020.
- **ELECTRA-STROKE.** Neurology 2023: 32% bản ghi trước viện không dùng được.
- **Jian, Bisantz, Drury.** "Foundations for an empirically determined scale of trust in automated systems." 2000.
- **NASA-TLX** (Hart & Staveland 1988); **SUS** (Brooke 1996).

_Thông tin chi tiết và đã kiểm chứng của 4 tài liệu đầu nằm trong `docs/lit_review.md`. Jian 2000, NASA-TLX và SUS là các thang đo chuẩn, trích theo hiểu biết sẵn có, **chưa kiểm lại trong phiên này**. Phải kiểm lại trước khi đưa vào hồ sơ._
