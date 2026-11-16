# Kế hoạch UIST 2027 full paper

_Lập 2026-11-16. Thay phần venue của `docs/full_paper_plan.md` (bản đó nhắm CHI/IMWUT). Các mục R1–R5, tiêu chí "bỏ" và rủi ro ở bản cũ vẫn giữ nguyên giá trị._

**Hạn (uist.acm.org, đọc 2026-11-16):** abstract 31/3/2027, full paper 7/4/2027, supplementary 9/4/2027. Hội nghị ở Vienna, 27–29/10/2027. Trang chưa ghi múi giờ, phải kiểm lại khi CFP 2027 được đăng.

## 1. Định vị (đã chốt 2026-11-16)

**Một lớp tin cậy cho EEG ít kênh do người không chuyên đo, với stroke trước viện là ca ứng dụng.**

UIST chấm điểm hệ thống và kỹ thuật tương tác kèm đánh giá với người dùng, không chấm AUC. Kết quả IS-vs-NS bị trùng hoàn toàn giữa nhãn và nguồn dữ liệu (SQI-only AUC 0.998), nên không thể làm đóng góp chính. Lớp tin cậy cũng là phần dùng lại được cho các ứng dụng EEG khác (động kinh, giấc ngủ, mê sảng ICU, neurofeedback), tức là nền cho startup.

### Đóng góp

| # | Đóng góp | Trạng thái |
|---|---|---|
| C1 | **Hệ thống:** pipeline real-time không phụ thuộc thiết bị (BLE headband AF3/AF4, Cyton 8 kênh, replay) | Có sẵn |
| C2 | **Kỹ thuật "No-Decision có hành động đi kèm":** SQI v2 theo từng kênh, có mã lý do (R1), kết hợp conformal risk control ở mức bệnh nhân (R2). Giao diện chỉ ra *điện cực nào, làm gì*, kèm cam kết FAR ≤ α | Bắt đầu 2026-11-16 |
| C3 | **Đánh giá kỹ thuật:** phát hiện artifact trên TUAR (v1 so với v2), đường risk–coverage, tiêm nhiễu khi replay, độ trễ | Chưa làm |
| C4 | **Study 1, người mới tập đo:** đo trên người khoẻ, có và không có hướng dẫn. Kết quả chính: thời gian đến khi tín hiệu dùng được, tỉ lệ bản ghi dùng được | Chưa làm, cần hồ sơ đạo đức |
| C5 | **Study 2, cách diễn đạt No-Decision:** nghiên cứu bằng tình huống mô phỏng, đo tỉ lệ bỏ sót ca IS khi hệ thống từ chối trả lời (kiểm tra kết quả của Jabbour 2025) | Chưa làm, cần hồ sơ đạo đức |

**Không claim:** độ chính xác chẩn đoán stroke, đặc biệt trên headband 2 kênh; "validated"; số 0.99.

## 2. Lịch 20 tuần

| Tuần (bắt đầu) | Việc | Cổng |
|---|---|---|
| 1–2 (16/11) | Nộp hồ sơ đạo đức cho C4 và C5. Viết protocol. Sửa các chỗ paper v2 còn sai so với code | Hồ sơ đã nộp |
| 1–6 | R1 SQI v2 (TDD) → tải TUAR → đánh giá v1 so với v2. R2 conformal ở mức bệnh nhân | Đối chiếu tiêu chí "bỏ" của R1/R2 |
| 5–9 (14/12) | Giao diện hướng dẫn chỉnh điện cực, 2 cách diễn đạt No-Decision. Pilot với 2–3 người | Pilot không lộ lỗi lớn |
| 9–14 (11/1) | Chạy C4 (N≈12–16, trong-chủ-thể, đối trọng thứ tự) và C5 | Dữ liệu thật đủ N |
| 14–20 (22/2) | Viết bằng skill `ml-paper-writing`, hình bằng `academic-plotting`, video, bản ẩn danh | Abstract 31/3, paper 7/4 |

Có thể cắt nếu thiếu thời gian: R3 (baseline EEGNet/Riemann đã có), R4, cohort NEDC.

## 3. R1: SQI v2, đặc tả

Module riêng `backend/sqi_v2.py`. **Không thay `compute_sqi`**, vì model đang triển khai được huấn luyện trên các feature SQI v1.

- **Đầu vào:** cửa sổ thô `(n_kênh, n_mẫu)`, mặc định 4 s, chưa bandpass. Drift < 0.5 Hz và đường dốc 1/f cần cửa sổ dài hơn 1 s của v1.
- **Feature theo từng kênh, không phụ thuộc đơn vị đo:**
  - tỉ lệ drift: phương sai phần < 0.5 Hz chia phương sai toàn phần;
  - số mũ aperiodic và R² của fit log–log trên 2–40 Hz, bỏ dải alpha và dải điện lưới;
  - tỉ lệ dải điện lưới, tỉ lệ cao tần, kurtosis, tỉ lệ mẫu bị bão hoà, phẳng tương đối;
  - đỉnh alpha: chỉ báo cáo, **không phạt** vì người bệnh stroke có thể mất alpha.
- **Đầu ra:** điểm 0–1 cho từng kênh kèm mã lý do (`flat`, `clipping`, `line_noise`, `muscle`, `drift`, `transient`), điểm cả cửa sổ, kênh tệ nhất.
- **Ràng buộc bắt buộc:** slowing kiểu stroke (delta 1–4 Hz tăng, số mũ dốc hơn) **không** bị gate như drift. Có test tổng hợp ngay. Khi có dữ liệu thật, phải kiểm thêm rằng SQI v2 không gate IS nhiều hơn NS.
- **Đánh giá trên TUAR:** AUC phát hiện artifact ở mức bệnh nhân, so v1 với v2, cả luật cố định lẫn bộ kết hợp logistic học trên fold train. Bỏ hướng này nếu v2 không hơn v1 ít nhất 0.05 AUC.

### Trạng thái R1 (2026-11-16)

**Code:**
- `backend/sqi_v2.py`: 35 test tổng hợp.
- `scripts/tuar_sqi_eval.py`: 19 test cho các hàm thuần. Chưa chạy vì chưa có dữ liệu TUAR.
- `scripts/sqi_v2_gate_check.py` → `results/sqi_v2_gate_check.json`.

**Review đã sửa:**
- Drift trước đây đo bằng tỉ lệ năng lượng < 0.5 Hz, nên phạt cả phổ 1/f dốc. Nay đổi thành **phần vượt so với đường 1/f ngoại suy** (`drift_excess`).
- Nhãn TUAR từng cộng chồng các sự kiện overlap. Nay tính theo hợp các khoảng thời gian.
- Thêm cảnh báo khi kênh trong file CSV không khớp với montage.
- Thêm lý do `missing` cho mẫu NaN.
- Kênh phẳng nay hiện ra với model học.
- Feature đuôi nặng được chuẩn hoá bằng quantile.
- Một EDF lỗi không còn làm hỏng cả lượt chạy.

**Kiểm tra an toàn trên dữ liệu thật** (cửa sổ 4 s, ngưỡng drift `drift_excess` 0.4→1.2 mới chỉnh trên dữ liệu tổng hợp):

| Cặp | Bị gate | Kết luận |
|---|---|---|
| TUSL slow / bckg (**cùng máy**) | 34% / 74% | Đạt: slowing không bị gate nhiều hơn |
| IS / NS (**khác máy**) | 26.0% / 19.5% | **Không đạt**. Phần lớn do lý do `drift` (IS 4.8 so với NS 2.4 kênh mỗi cửa sổ) |

- Drift ở IS rải đều mọi kênh, cao nhất ở O1/O2/T3/T4. Drift ở NS tập trung ở kênh trán và thái dương, tức kiểu chuyển động mắt. Phổ dưới 1 Hz của hai cohort khác nhau rõ.
- Vì nhãn trùng hoàn toàn với máy đo, **không thể biết** drift ở IS là do máy hay do bệnh. Không chỉnh ngưỡng để "qua", vì như vậy là p-hacking.
- AUC IS-vs-NS chỉ từ điểm v2 của cả bản ghi là 0.43. So với SQI-only AUC 0.998 của v1, v2 mang shortcut máy đo ít hơn nhiều.
- Bản drift cũ (tỉ lệ thô) cho IS 9.9% / NS 17.0%, nhưng sai về nguyên lý.

**Việc tiếp theo, chốt trước khi chạy:**
- Chỉnh ngưỡng drift trên **một nửa số bệnh nhân TUAR** (cùng máy, có nhãn).
- Đóng băng ngưỡng, rồi đánh giá trên nửa còn lại và chạy lại cả hai kiểm tra an toàn.
- Nếu cặp IS/NS vẫn không đạt, Paper ghi rõ là hạn chế: SQI v2 có thể gate nhiều hơn trên máy đo không có high-pass phần cứng. Hướng dẫn trong giao diện vẫn có giá trị, vì lý do `drift` đi kèm hành động "ấn chặt/làm ướt điện cực".
