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
| C4 | **Study 1, người mới tập đo** (protocol: `docs/user_study_protocol.md`): đo trên người khoẻ, có và không có hướng dẫn. Kết quả chính: thời gian đến khi tín hiệu dùng được, tỉ lệ bản ghi dùng được | Chưa làm, cần hồ sơ đạo đức |
| C5 | **Study 2, cách diễn đạt No-Decision:** nghiên cứu bằng tình huống mô phỏng, đo tỉ lệ bỏ sót ca IS khi hệ thống từ chối trả lời (kiểm tra kết quả của Jabbour 2025) | Chưa làm, cần hồ sơ đạo đức |

**Không claim:** độ chính xác chẩn đoán stroke, đặc biệt trên headband 2 kênh; "validated"; số 0.99.

Dàn ý paper và bản đồ claim → bằng chứng: `docs/paper_outline.md`.

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

### Kết quả R1 trên TUAR (2026-11-17)

- **Luật bỏ hướng: đạt theo ước lượng điểm.** Model học trên đặc trưng v2 hơn v1 +0.081 AUC [0.048, 0.117]. Luật tay đang triển khai thì thua v1 (−0.035).
- **Scorer học không triển khai được:** trượt kiểm tra an toàn E9 (gate 51% cửa sổ stroke, 0.3% control), kể cả biến thể bỏ đặc trưng trạng thái não. Tracker giữ luật tay, vốn đạt E9 và E11.
- **Hướng viết:** R1 chuyển trọng tâm sang tương tác (lý do + hành động theo kênh, Study 1) và bài học DG2: học điểm chất lượng từ nhãn artifact lâm sàng biến nó thành bộ phát hiện nguồn/bệnh lý. Chi tiết: `docs/paper_outline.md` mục 6.

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
- Nếu cặp IS/NS vẫn không đạt, paper ghi rõ là hạn chế: SQI v2 có thể gate nhiều hơn trên máy đo không có high-pass phần cứng. Hướng dẫn trong giao diện vẫn có giá trị, vì lý do `drift` đi kèm hành động "ấn chặt/làm ướt điện cực".

## 4. R2: No-Decision có đảm bảo conformal

**Code:**
- `backend/conformal_triage.py`: 22 test, trong đó có kiểm chứng Monte Carlo cho đảm bảo FAR ≤ α.
- `scripts/conformal_no_decision.py` → `results/conformal_no_decision.json`.

**Cách làm:**
- Conformal phân lớp (Mondrian) ở **mức bệnh nhân**. Điểm không phù hợp của lớp "đối chứng" là p, của lớp "stroke" là 1 − p, mỗi lớp có ngưỡng riêng.
- Tập dự đoán chỉ có một lớp → báo động hoặc yên tâm. Có cả hai lớp → No-Decision lý do `ambiguous`. Không lớp nào → No-Decision lý do `conflict`. Thiếu tín hiệu dùng được → No-Decision lý do `quality`.
- Đảm bảo: P(báo động | đối chứng) ≤ α và P(yên tâm | stroke) ≤ α, với điều kiện bệnh nhân exchangeable và đã qua cổng chất lượng.

**Bối cảnh đánh giá:**
- Model Riemann đang triển khai, chạy trên **nguồn chưa thấy, có khớp trạng thái mắt**. S1: 24 IS + 50 NS. S2: 50 IS + 50 NS.
- Mô phỏng calibration tại chỗ: chia ngẫu nhiên một nửa bệnh nhân làm calib, nửa còn lại làm test, lặp 2000 lần.

**Kết quả (2026-11-16):**

| Split, α | FAR conformal | FAR heuristic 0.8/0.2 | FAR khi calib theo cửa sổ, báo nếu bất kỳ cửa sổ nào | Độ nhạy | Ca IS rơi vào No-Decision |
|---|---|---|---|---|---|
| S1, 0.10 | 0.077 | 0.299 | 0.281 | 0.29 | 64% |
| S1, 0.20 | 0.191 | 0.299 | 0.471 | 0.57 | 29% |
| S2, 0.10 | 0.076 | 0.160 | 0.242 | 0.21 | 71% |
| S2, 0.20 | 0.186 | 0.160 | 0.516 | 0.67 | 15% |

- **Đảm bảo đứng vững** ở mọi split và mọi α, tức FAR trung bình ≤ α. Theo quy tắc bỏ hướng: giữ R2, được gọi là "guarantee".
- **Heuristic hiện tại không kiểm soát được FAR**: S1 là 0.30, vượt cả α = 0.2.
- **Calib theo cửa sổ rồi báo động khi có bất kỳ cửa sổ nào vượt ngưỡng làm vỡ đảm bảo** (FAR 0.24–0.52). Đây là bằng chứng trên dữ liệu thật rằng phải calibrate ở mức bệnh nhân. Hệ quả cho chế độ streaming: phải quyết định trên điểm gộp của cả phiên đo, không quyết định theo từng cửa sổ.
- **Cái giá:** với AUC khoảng 0.8 và chỉ 12–25 bệnh nhân calib mỗi lớp, α = 0.1 đẩy 64–71% ca IS vào No-Decision. α = 0.05 gần như không bao giờ quyết định. α là một **tham số thiết kế tương tác** (đánh đổi giữa FAR và tỉ lệ No-Decision), và giao diện phải cho thấy đánh đổi đó.
- **Liên hệ C5:** hầu hết ca IS bị giữ lại nằm ở No-Decision chứ không bị báo là bình thường (miss ≤ α). Vì vậy cách diễn đạt No-Decision ("chưa biết ≠ bình thường", kèm hành động tiếp theo) là chỗ quyết định có bỏ sót bệnh nhân hay không. Đây đúng là câu hỏi Jabbour 2025 đặt ra.

**Hạn chế:**
- Trong mỗi split, ca IS và ca NS vẫn đến từ các nguồn khác nhau (NS là physionet_eo), nên khả năng phân biệt của model một phần vẫn đến từ khác biệt nguồn.
- Đảm bảo FAR chỉ áp dụng cho quần thể đối chứng đó.
- Chưa có cổng chất lượng SQI v2 trong lượt chạy này. Sẽ thêm sau khi ngưỡng drift được chỉnh trên TUAR.
