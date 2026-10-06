# Kế hoạch: tìm thuật toán mới → hoàn thành full paper

_Lập 2026-10-06. Bản paper gốc: `EEGStroke_TAPS_binary.docx` (ACM 2 cột, ~4.6k từ)._

> **Đã chốt 2026-10-06: venue = hội nghị HCI (CHI/IMWUT).** Hệ quả: P4 user study là **bắt buộc** (bắt đầu thủ tục IRB/đạo đức ngay, chạy song song P1–P3). R2 được đóng khung như một **thiết kế tương tác** (No-Decision có cam kết FAR mà người dùng hiểu được), không phải đóng góp ML thuần. Q5 (HCI alarm fatigue/abstain) được nâng lên ưu tiên ngang Q1–Q2.

> **Cập nhật sau P1 (2026-10-06, chi tiết + citation: `docs/lit_review.md`):**
> - **RQ HCI chính mới (H-ND):** Jabbour 2025 (N=259 bác sĩ) cho thấy khi AI abstain, bác sĩ *chẩn đoán thiếu* +18%. Câu hỏi trọng tâm của user study: *No-Decision có làm bỏ sót IS không, và cách diễn đạt nó ("chưa biết ≠ bình thường" + hành động đo lại/chỉnh điện cực) có giảm điều đó không?* Thêm điều kiện so sánh hai cách diễn đạt No-Decision vào P4.
> - **R1 hạ cấp** thành "tích hợp + kiểm định" (spectral slope đã có: Fasol 2023). Thêm kiểm tra bắt buộc: SQI v2 **không gate IS nhiều hơn NS**, vì stroke cũng làm tăng exponent 1/f.
> - **R2** dựng trên Selective Conformal Risk Control + calibration patient-level (Chatterjee 2026: conformal chuẩn vỡ coverage khi split theo bệnh nhân).
> - **R3 bỏ FM:** leakage TUH đã được xác nhận trong các benchmark 2026. Chỉ giữ EEGNet + pyRiemann.
> - **Motivation:** ELECTRA-STROKE (Neurology 2023): 32% bản ghi trước viện không dùng được → nút thắt là chất lượng tín hiệu và cách xử lý nó.

## 0. Điểm xuất phát (đọc từ repo, không đoán)

| Hạng mục | Hiện trạng | Nguồn |
|---|---|---|
| Kết quả chính IS-vs-NS | Entropy 0.79 → +SQI gate 0.99, **nhưng confound nguồn 100%** (SQI-only AUC 0.998) | paper §6.1, §6.3 |
| Kiểm soát cùng máy (TUSL, N=29) | Entropy AUC 0.82 > SQI 0.77 → không còn shortcut | `results/source_confound_report.json`, paper §8 |
| Headband 2 kênh (mô phỏng) | AUC 0.80 → 0.86–0.89 khi abstain 50–70% | `results/headband_eval.json` |
| AF3/AF4 thật (proxy FP1/FP2) | AUC 0.69 — yếu | `results/qeeg_AF3AF4_fp.json` |
| Thiết bị thật | Đã stream AF3/AF4 qua BLE, **chỉ SQI/No-Decision** | `backend/app/services/device_source.py` |
| SQI | Log drift thật (94–98% delta, không có alpha) vẫn đạt SQI ≈ 0.88 | `data/ble_signals_log*.csv` |
| No-Decision | Ngưỡng SQI 0.55 + heuristic `|p−0.5|`, không có đảm bảo thống kê | `scripts/run_headband_eval.py` |
| User study | Chưa làm (§5.8 chỉ là protocol) | paper |

**Chỗ paper đang sai so với code (phải sửa dù chọn hướng nào):** §5.7 ghi montage F3/F4/T7/T8 bipolar và "chưa có thiết bị thật". Thực tế là AF3/AF4 và đã stream live. Bảng 1 còn ô "–". Venue vẫn để "[Conference]".

## 1. Nguyên tắc chọn thuật toán

Chỉ theo đuổi thuật toán thỏa cả 3 điều kiện:
1. **Vá đúng một lỗ hổng đã đo được** của paper, không làm cho có.
2. **Chạy được trên dữ liệu đang có** (50 IS + 50 NS, TUSL, TUH artifact/abnormal qua rsync) và CPU.
3. **Có tiêu chí "bỏ" viết trước khi chạy**, để không p-hack trên N=29.

> ⚠️ Giới hạn không vượt được: confound giữa nguồn và nhãn là 100% (mọi IS đến từ một rig, mọi NS từ rig khác). **Không thuật toán nào tách được** pathology khỏi rig khi hai biến trùng nhau hoàn toàn. Đây là bài toán identifiability. Chỉ có **dữ liệu** mới gỡ được (cohort cùng rig). Paper không được ngụ ý rằng domain adaptation đã giải quyết chuyện này.

## 2. Các hướng thuật toán (xếp theo ưu tiên)

### R1. SQI v2: kiểm tra độ hợp lý phổ ★ MUST
- **Lỗ hổng:** SQI hiện tại chỉ phát hiện flatline/clip/line noise/HF noise. Drift chậm và tiếp xúc điện cực kém lọt qua (log thiết bị thật).
- **Ý tưởng:** thêm feature aperiodic 1/f (offset/exponent, kiểu specparam/FOOOF), trần cho tỉ lệ công suất delta, năng lượng drift < 0.5 Hz, sự có mặt của đỉnh alpha, kurtosis. Sau đó gộp thành một điểm chất lượng đã hiệu chỉnh.
- **Dữ liệu kiểm chứng:** **TUAR (TUH Artifact Corpus)**: artifact có nhãn và cùng rig với TUSL. Thêm log thiết bị thật làm case study.
- **Metric:** AUC phát hiện artifact (SQI v1 so với v2), và mức giảm tỉ lệ cảnh báo giả trên replay có tiêm nhiễu.
- **Bỏ nếu:** v2 không hơn v1 ≥ 0.05 AUC trên TUAR (patient-level).
- **Vì sao hợp paper:** đây là lõi của đóng góp HCI/sensing (gating), và quan trọng hơn trên headband thật.

### R2. No-Decision có đảm bảo bằng conformal ★ MUST
- **Lỗ hổng:** abstention hiện là heuristic. Không có cam kết kiểu "tỉ lệ cảnh báo sai ≤ α".
- **Ý tưởng:** split conformal / **conformal risk control** với lớp calibration ở **mức bệnh nhân**, Mondrian theo lớp. Hợp nhất SQI v2 và độ tự tin của model thành **một** luật abstain có đảm bảo.
- **Bẫy cần nói rõ:** các window trong cùng một bệnh nhân không exchangeable. Phải calibrate theo đơn vị bệnh nhân, hoặc gộp window trước khi calibrate.
- **Metric:** đường risk–coverage, kiểm tra coverage/FAR thực nghiệm so với mục tiêu α, so với baseline `|p−0.5|`.
- **Bỏ nếu:** FAR thực nghiệm vượt α > 2 điểm % trên các fold (đảm bảo không đứng vững với N nhỏ). Khi đó báo cáo như một heuristic, không gọi là "guarantee".
- **Lợi thế:** bạn đã làm conformal ở dự án QEC, tái sử dụng được kiến thức.

### R3. Baseline mạnh để chặn phản biện "sao không dùng deep learning?" ★ MUST (gọn)
- Riemannian tangent-space (pyRiemann), rẻ và hợp số kênh ít; EEGNet; band-power + LR.
- **Một** EEG foundation model, chỉ linear probe embedding frozen để chạy được trên CPU. Ứng viên: LaBraM, BIOT (chịu được số kênh thay đổi, hợp 2 kênh), CBraMod, EEGPT.
- ⚠️ **Rò rỉ pretraining:** nhiều FM được pretrain trên TUH, có thể đã thấy các bản ghi TUSL (không nhãn). Phải kiểm tra danh sách pretraining và nêu rõ trong paper.
- **Bỏ:** không fine-tune toàn phần (N=29 + CPU = overfit và tốn thời gian).

### R4. Probe chuyển giao cùng rig → cohort IS/NS ◇ SHOULD
- Train trên TUSL slow-vs-bckg (**không** dùng feature SQI), áp zero-shot lên 50 IS / 50 NS.
- Nếu AUC > 0.5 một cách có ý nghĩa thì có bằng chứng rằng tín hiệu pathology học từ một rig khác vẫn chuyển giao được. Chỉ là bằng chứng **gián tiếp**: delta/slowing vẫn có thể khác giữa hai rig, phải viết đúng mức đó.

### R5. Thống kê cho mọi con số ★ MUST
- Bootstrap CI ở mức bệnh nhân, CV 5-fold lặp × 5 seed, DeLong cho so sánh AUC. Tính AUC/ECE cho cấu hình ungated để lấp ô "–" ở Bảng 1.

### Không làm trong paper này (ghi vào Future Work)
- Fusion fNIRS/PPG: không có dữ liệu stroke có nhãn cho các modality này.
- Phân loại 3 lớp IS/HS: chỉ có 4 bệnh nhân HS.
- Fine-tune FM toàn phần.
- Sửa skew detrend train/online: phải validate lại model. Chỉ làm nếu có thời gian, và ghi rõ trong Limitations.

### Track dữ liệu (song song, tùy chọn): cách duy nhất gỡ confound thật
- Dịch vụ keyword-search báo cáo của NEDC (infarct / ischemic / ICD 433–437) → giao với TUAB-abnormal → cohort IS **cùng rig** gán nhãn yếu. Cần gửi yêu cầu tới NEDC, có độ trễ, nên bắt đầu sớm.

## 3. Lộ trình theo pha (có cổng kiểm)

| Pha | Việc | Thời lượng | Cổng để sang pha sau |
|---|---|---|---|
| P0 | Chốt venue; commit nhánh `feat/fastapi-rewrite` (đang có diff lớn chưa commit); sửa 2 test cũ AF3/AF4; sửa §5.7/Bảng 1 cho khớp code | 2–3 ngày | Paper không còn câu nào sai so với code |
| P1 | **Survey tài liệu bằng skill `autoresearch`** cho Q1–Q5 (§4) → `docs/lit_review.md`, mọi citation đều verify được (DOI/arXiv) | 1 tuần | Mỗi hướng R1–R4 có ≥ 3 paper gần nhất + xác nhận gap còn mở |
| P2 | R1 + R2 + R5 (TDD: test trước, rồi `scripts/…`, kết quả ra `results/*.json`) | 2–3 tuần | Kết quả đối chiếu với tiêu chí "bỏ" đã viết trước |
| P3 | R3 baselines + R4 transfer probe | 1 tuần | Bảng so sánh đủ để phản biện |
| P4 | User study N=8–12 (nếu venue cần, xem §5) | 2 tuần + thời gian xin IRB/đạo đức | Dữ liệu thật, không bịa |
| P5 | Viết lại bằng skill `ml-paper-writing`: Methods (R1/R2), Results, Discussion, Limitations; vẽ hình bằng `academic-plotting`; anonymize; kiểm tra reference | 1–2 tuần | Đọc lại toàn bài: mỗi con số trỏ được về một file trong `results/` |

## 4. Câu hỏi survey cho P1

- **Q1** SQI/artifact detection cho EEG số kênh ít/wearable có dùng aperiodic 1/f hoặc tính hợp lý phổ không? Benchmark trên TUAR đang đạt bao nhiêu?
- **Q2** Conformal prediction / selective classification cho EEG hoặc tín hiệu y sinh dạng chuỗi: xử lý non-exchangeability trong cùng bệnh nhân thế nào?
- **Q3** EEG foundation models (LaBraM, BIOT, CBraMod, EEGPT, …): dữ liệu pretraining có chồng với TUSL/TUAR không? Hiệu năng linear probe khi số kênh ít ra sao?
- **Q4** Phát hiện stroke bằng EEG trước viện (2023–2026): thiết bị ít kênh, cách các nhóm khác báo cáo/xử lý confound giữa các site.
- **Q5** Nghiên cứu HCI về alarm fatigue và trạng thái "no-decision"/abstain trong giao diện hỗ trợ quyết định lâm sàng.

_Các tên paper nhắc trong file này (specparam, conformal risk control, LaBraM, BIOT, CBraMod, EEGPT, pyRiemann, EEGNet) là từ hiểu biết sẵn có, **chưa được verify trong phiên này**. P1 phải xác nhận năm, venue và chi tiết trước khi đưa vào references._

## 5. Khung đóng góp của paper sau khi xong

1. **SQI v2 nhận biết độ hợp lý phổ**, kiểm chứng trên artifact có nhãn cùng rig (R1).
2. **No-Decision kiểm soát rủi ro bằng conformal**: biến UX "không quyết định" thành cam kết FAR đo được (R2).
3. **Phương pháp minh bạch:** probe confound, đối chứng cùng rig, probe chuyển giao (R4), CI đầy đủ (R5).
4. **Hệ thống:** pipeline real-time, headband thật stream qua BLE (chỉ chất lượng), demo mode.

**Tuyệt đối không claim:** "stroke AUC" từ TUSL/TUAB; độ chính xác chẩn đoán trên headband 2 kênh; "validated"; số 0.99 như năng lực chẩn đoán.

**Venue ảnh hưởng P4:** paper hệ thống HCI (CHI/UIST/IMWUT) gần như bắt buộc có user study. Journal y sinh/ML (IEEE JBHI, TNSRE, …) thì R1/R2 + thống kê là trọng tâm và có thể không cần study.

## 6. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| N=29 (TUSL) nhỏ → kết quả dao động | Tiêu chí "bỏ" viết trước, CV lặp, CI; tăng N bằng một subset TUAB/TUAR |
| FM pretraining rò rỉ TUH | Kiểm tra danh sách pretraining; nếu không chắc, báo cáo kèm cờ cảnh báo |
| Conformal vỡ đảm bảo do window tương quan | Calibrate ở mức bệnh nhân; báo cáo FAR thực nghiệm |
| Ổ C chật, CPU-only | Dữ liệu đặt ở `F:\tuh_data`; FM chỉ linear probe |
| Song song với IELTS team + QIP poster | Mỗi pha có cổng rõ; P3/P4 có thể cắt |
