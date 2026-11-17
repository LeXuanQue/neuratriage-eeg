# Dàn ý paper UIST 2027 và bản đồ bằng chứng

_Lập 2026-11-16. Đi kèm `docs/uist2027_plan.md` (lịch, R1/R2) và `docs/user_study_protocol.md` (C4/C5). Nguyên tắc: **mỗi con số trong paper trỏ được về một file trong `results/`**. Claim nào chưa có file thì chưa được viết._

## 1. Câu chuyện

**Nút thắt của EEG trước viện là khâu thu tín hiệu và độ tin cậy, không phải bộ phân loại.** Chính dự án này là bằng chứng: model đầu tiên đạt AUC 0.99, nhưng phần lớn là nhận diện máy đo (SQI-only AUC 0.998). Paper đề xuất một **lớp tin cậy**: giúp người không chuyên đo đúng điện cực, và cho hệ thống im lặng với một cam kết đo được.

**Tên tạm:** *Know When to Measure Again: Actionable Abstention for Non-Expert EEG Triage*

**Đóng góp:**
1. **Hệ thống:** pipeline real-time không phụ thuộc thiết bị (headband BLE 2 kênh, Cyton 8 kênh, replay 18 kênh).
2. **Kỹ thuật:** SQI v2 theo từng kênh kèm lý do và hành động sửa, cùng No-Decision bằng conformal ở mức bệnh nhân với cam kết FAR ≤ α.
3. **Đánh giá kỹ thuật:** phát hiện và định vị artifact trên dữ liệu cùng máy có nhãn (TUAR); kiểm chứng đảm bảo FAR; kiểm tra an toàn rằng slowing không bị gate.
4. **Study 1:** người mới tập đo, có hoặc không có hướng dẫn.
5. **Study 2:** cách diễn đạt No-Decision và nguy cơ bỏ sót stroke.

## 2. Dàn ý

| Mục | Nội dung | Phụ thuộc |
|---|---|---|
| 1. Introduction | 32% bản ghi trước viện không dùng được (ELECTRA-STROKE). Câu chuyện "model của chính mình là máy dò thiết bị". Các đóng góp | Viết được ngay |
| 2. Related work | EEG stroke trước viện; phát hiện artifact trên EEG ít kênh; selective prediction và conformal (Chatterjee 2026); con người với AI khi AI từ chối trả lời (Jabbour 2025, Bondi 2022, Beede 2020); **hướng dẫn thu tín hiệu cho người không chuyên** (cần survey thêm, đặc biệt các bài UIST/CHI về guided capture) | `docs/lit_review.md` + bổ sung |
| 3. Bài học thiết kế | Chuỗi kiểm tra confound → 4 mục tiêu thiết kế: DG1 nói rõ điện cực nào, DG2 không phạt bệnh lý, DG3 im lặng có cam kết, DG4 "chưa biết ≠ bình thường" | E1–E3 |
| 4. Hệ thống | Kiến trúc; SQI v2; conformal; giao diện G; độ trễ | E4–E5 |
| 5. Đánh giá kỹ thuật | TUAR; định vị; kiểm tra an toàn; đảm bảo FAR; cỡ calibration | E6–E13 |
| 6. Study 1 | Người mới tập đo, B so với G | C4 |
| 7. Study 2 | Cách diễn đạt No-Decision | C5 |
| 8. Discussion | α là tham số thiết kế tương tác; từ chối trả lời không trung tính; lớp tin cậy dùng ngoài stroke; hạn chế | Tất cả |
| 9. Conclusion | | |

**Hình:**
1. Teaser: người đo + headband + bảng G.
2. Kiến trúc.
3. Chuỗi confound (AUC qua từng mức kiểm soát).
4. ROC artifact trên TUAR.
5. Ma trận nhầm lẫn của lý do và độ chính xác định vị kênh.
6. FAR theo α: conformal, heuristic, calib theo cửa sổ.
7. Kết quả Study 1.
8. Kết quả Study 2.

## 3. Bản đồ claim → bằng chứng

Trạng thái: ✅ có file, 🟡 có nhưng thiếu một phần, ⏳ chờ dữ liệu, ❌ chưa chạy.

| # | Claim | Bằng chứng | Trạng thái |
|---|---|---|---|
| E1 | Model gốc chủ yếu nhận diện máy đo: SQI-only AUC 0.999 (entropy 0.904), 100 bệnh nhân. Cùng máy TUSL (29 bệnh nhân): SQI 0.771, entropy 0.823 | `results/source_confound_report_crosscohort.json`, `results/source_confound_report_tusl_samerig.json` (file `source_confound_report.json` hiện là bản TUSL) | ✅ |
| E2 | AUC giảm qua từng mức kiểm soát, kèm CI 95% bootstrap theo bệnh nhân. Trong cùng nguồn: features 0.993, Riemann 0.999. Đổi nguồn: features 0.90–0.99, Riemann 0.90–1.00. Khớp tuổi: 0.89–0.99. **Khớp trạng thái mắt** (control mở mắt): features **0.57 [0.46, 0.68]** và **0.73 [0.60, 0.84]**; Riemann **0.82 [0.71, 0.90]** và **0.82 [0.72, 0.90]**. EEGNet 0.63–0.77 (chưa có CI) | `results/lso_ci_{main,age,eyes}.json`, `results/leave_source_out_eyes_eegnet.json` | ✅ 2026-11-17 (feature + Riemann). EEGNet chưa chạy lại vì chậm |
| E3 | Ngưỡng cố định sinh 51–66 báo động giả/giờ | `results/clinical_utility.json`, `device_recalibration.json` | ✅ |
| E4 | Độ trễ end-to-end đủ cho real-time: Riemann 7 ms/chunk 0.5 s, end-to-end 18 kênh p95 65 ms (RTF 0.13); LightGBM features 98 ms/chunk (RTF 0.34); SQI v2 2 kênh 5.7 ms, 18 kênh 49 ms mỗi giây. CPU laptop Intel, không gồm mạng/trình duyệt | `results/latency_riemann.json`, `results/latency.json` | ✅ 2026-11-16 |
| E5 | Headband thật (19 s, AF3/AF4): **v1 cho qua 100% cửa sổ** (SQI 0.95). v2 với ngưỡng drift đóng băng (2.19–2.99): chỉ gắn cờ drift AF3 ở cửa sổ kết thúc 9 s (Δdrift 2.76) và 3 cửa sổ transient. 10 s đầu có Δdrift 1.6–2.8, nằm ở chân ramp: ngưỡng chỉnh trên kênh sạch lâm sàng **lỏng với headband khô** | `results/headband_case_study.json` (có `timeline`) | ✅ 2026-11-17. Ghi vào Limitations |
| E6 | Phát hiện artifact (TUAR nửa test, 113 BN). **Luật tay v2 thua v1** (0.708 vs 0.743, −0.035 [−0.063, −0.008]). **Model học trên đặc trưng v2 hơn v1 +0.081 [0.048, 0.117]**, đạt luật bỏ hướng theo ước lượng điểm. Lợi ở eyem (+0.18), elec (+0.21) | `results/tuar_sqi_eval.json` | ✅ 2026-11-17 |
| E7 | Lý do: 50% kênh-cửa sổ artifact có lý do, 71% trong số đó đúng loại. 86% eyem không có lý do, 22% musc bị gọi là drift | `results/tuar_sqi_eval.json` → `reason_accuracy_e7` | ✅ 2026-11-17 |
| E8 | Kênh tệ nhất trúng kênh artifact 0.53, ngẫu nhiên 0.38, v1 0.54 (chênh [−0.044, 0.039]): hơn ngẫu nhiên, **không hơn v1** | `results/tuar_sqi_eval.json` → `localization_e8` | ✅ 2026-11-17 |
| E9 | An toàn với ngưỡng đóng băng (luật tay): IS bị gate 0.3% vs NS 15.7% (NS chủ yếu do điện lưới 60 Hz), TUSL slow 30.5% vs bckg 47.5%. **Đạt.** Điểm record v2 tách IS/NS AUC 0.61 (v1: 0.999). Scorer học thì **trượt**: IS 51% vs NS 0.3% (AUC 0.006), biến thể bỏ delta/alpha 45% vs 0.1% | `results/sqi_v2_gate_check.json`, `results/sqi_learned_scorer_eval_{all,no_brain_state}.json` | ✅ 2026-11-17 |
| E10 | Conformal giữ FAR ≤ α, heuristic và calib theo cửa sổ thì không | `results/conformal_no_decision.json` | ✅ |
| E11 | Đảm bảo vẫn đứng vững sau cổng SQI v2 (luật tay, ngưỡng đóng băng, tín hiệu thô). Cổng bỏ 16% cửa sổ control, 1% stroke; 7/50 control không còn cửa sổ nào → luôn No-Decision. FAR S1 0.039/0.079/0.155, S2 0.039/0.077/0.151 ở α = 0.05/0.1/0.2. **Đạt mọi trường hợp** | `results/conformal_quality_gate.json` | ✅ 2026-11-17 |
| E12 | Cần bao nhiêu bệnh nhân để calibrate tại chỗ. **Dưới ⌈1/α⌉−1 bệnh nhân mỗi lớp thì không bao giờ báo động** (α = 0.1 → 9). FAR trung bình ≤ α ở mọi n, theo hình răng cưa đúng lý thuyết 1 − ⌈(n+1)(1−α)⌉/(n+1). Nhưng một lần calibrate với 9–20 bệnh nhân có **10–29% khả năng cho FAR thực > α + 0.05** (p90 tới 0.37). Đảm bảo trung bình ≠ đảm bảo cho từng site | `results/conformal_calibration_size.json` | ✅ 2026-11-16. Đưa vào Discussion: cần conformal có điều kiện theo tập calib nếu muốn đảm bảo cho từng site |
| E13 | Đo bao lâu thì quyết định được. Split S2 (50 IS + 50 NS), phát lại từng bản ghi qua detector đang triển khai. **AUC bão hoà ngay từ 8 s** (0.79 → 0.80 ở 120 s). FAR ổn định ≤ α ở mọi T. Ghi lâu hơn không làm model chính xác hơn, nên chi phí thời gian nằm ở khâu đặt và chỉnh điện cực (Study 1), không ở thời lượng ghi. Cũng là dấu hiệu model bắt đặc tính tĩnh của bản ghi, có thể một phần là đặc tính nguồn, nên phải ghi rõ | `results/decision_time.json` | ✅ 2026-11-17 |
| E14 | Baseline mạnh (EEGNet, Riemann) cho câu hỏi "sao không dùng deep learning" | `results/leave_source_out_eyes_eegnet.json` | ✅ |
| E15 | Study 1, Study 2 | | ❌ chờ hồ sơ đạo đức |

## 4. Thứ tự chạy

1. **Ngay, trước khi TUAR xong:** sửa `scripts/tuar_sqi_eval.py` để lưu lý do đứng đầu và kênh tệ nhất của mỗi cửa sổ, thêm phần đánh giá E7/E8 (viết test trước).
2. **Ngay, rẻ:** E12, E4, CI cho E2.
3. **Sau khi TUAR xong:** E6 → đóng băng ngưỡng → E9, E11, E7, E8.
4. **Khi có thời gian:** E5 (cần decode log BLE), E13 (kiểm thứ tự cửa sổ trước).
5. **Tuỳ chọn:** R4 (probe chuyển giao từ TUSL).

## 5. Ghi chú smoke test (2026-11-16, KHÔNG phải kết quả)

Chạy trọn luồng trên 20 bản ghi TUAR đầu (12 bệnh nhân; nửa test chỉ 5 bệnh nhân) để kiểm tra code. 0 lỗi, 0 sự kiện lệch kênh. Các con số dưới đây chỉ là **tín hiệu cảnh báo sớm**, không được trích dẫn:

- **Ngưỡng drift chỉnh trên nửa calib:** bắt đầu ở 1.83, rất xa mức 0.4 chỉnh trên dữ liệu tổng hợp.
- **AUC phát hiện artifact:** v2 không hơn v1. Luật cố định: 0.75 so với 0.79. Model học: 0.59 so với 0.77, với N rất nhỏ. Nếu kết quả trên toàn bộ dữ liệu vẫn vậy, R1 sẽ **không đạt** quy tắc bỏ hướng.
- **E7:** v2 chỉ đưa ra lý do ở 51% cửa sổ artifact. Khi có đưa thì 76% đúng loại. Artifact do mắt (eyem) thường bị gọi là `muscle` hoặc không được gắn cờ.
- **E8:** v2 chỉ đúng kênh 0.51, v1 là 0.59, mức ngẫu nhiên là 0.31. Cả hai đều hơn ngẫu nhiên, nhưng chưa thấy v2 hơn v1.

**Quy tắc nếu muốn chỉnh luật lý do** (ví dụ thêm lý do riêng cho artifact do mắt): chỉ được phát triển trên **nửa calib**, chốt bằng văn bản, rồi mới chạy nửa test một lần.

**Phương án dự phòng nếu R1 không đạt:** đóng góp C2 chuyển trọng tâm từ "SQI v2 phát hiện tốt hơn" sang "đặt chất lượng tín hiệu theo từng kênh vào vòng tương tác, kèm lời khuyên hành động". Bộ chấm điểm theo kênh khi đó có thể dùng v1, và giá trị được chứng minh bằng Study 1. Báo cáo trung thực kết quả âm của R1.

## 6. Kết quả TUAR đầy đủ (2026-11-17) và kế hoạch scorer học

**Kết quả nửa test (113 bệnh nhân, 157 bản ghi, 532k kênh-cửa sổ, ngưỡng drift đóng băng 2.19):**

- **Luật bỏ hướng (đã đăng ký trước): ĐẠT.** Model học trên đặc trưng v2 hơn v1: AUC 0.827 so với 0.746, chênh **+0.081 [0.048, 0.117]**. Cận dưới CI chạm sát 0.05 nên chỉ đạt theo ước lượng điểm.
- **Luật cố định (bản đang triển khai): THUA v1.** Kênh: 0.708 so với 0.743, chênh −0.035 [−0.063, −0.008]. Cửa sổ: 0.747 so với 0.818. Nghĩa là đặc trưng v2 có thông tin, nhưng bộ trọng số chỉnh tay không khai thác được.
- **Theo loại:** v2 hơn rõ ở eyem (+0.18), elec (+0.21), chew_elec, eyem_musc. Ngang ở musc, chew. Kém ở shiv (−0.09, CI cắt 0).
- **E7:** 50% kênh-cửa sổ artifact có lý do; trong đó **71% đúng loại**. musc thường bị gọi là `drift` (17.5k/79k), eyem phần lớn không gắn cờ.
- **E8:** v2 trúng kênh 0.53, v1 0.54, ngẫu nhiên 0.38. Cả hai hơn ngẫu nhiên, v2 không hơn v1 (chênh [−0.044, 0.039]).

**Kế hoạch scorer học (chốt trước khi nhìn bất kỳ con số nào của nó):**

1. Fit `fit_logistic` trên `V2_FEATURES` với **nửa calib** TUAR. Ngưỡng hoạt động = phân vị 95% của P(artifact) trên kênh-cửa sổ sạch của nửa calib (cùng logic với ngưỡng drift: 5% báo nhầm trên kênh sạch). Đóng băng hệ số ra JSON.
2. Đánh giá **một lần** trên nửa test: AUC so với v1 học theo đúng cách đó, CI bootstrap theo bệnh nhân. Báo cáo đây là phân tích bổ sung, không phải luật đăng ký trước.
3. **Cổng an toàn E9** với scorer học: IS không bị gate nhiều hơn NS, TUSL slow không bị gate nhiều hơn bckg. Nếu trượt, thử **một** biến thể đã định sẵn: bỏ đặc trưng trạng thái não (`delta_ratio`, `alpha_peak`) rồi lặp lại bước 1–3. Nếu vẫn trượt, giữ luật cố định và viết R1 theo phương án dự phòng.
4. Chỉ triển khai scorer học vào ChannelQualityTracker khi qua cả bước 2 và 3. Lý do (reasons) và lời khuyên vẫn lấy từ luật, scorer học chỉ quyết định điểm và cổng.

**Kết quả scorer học (chạy 2026-11-17 theo đúng kế hoạch trên):**

- Bước 2 đạt: fit trên nửa calib, ngưỡng P(artifact) 0.786. Nửa test AUC 0.829, hơn v1 học cùng cách **+0.081 [0.057, 0.109]**, hơn v1 cố định +0.086. Báo nhầm trên kênh sạch 6.1%.
- Bước 3 **trượt nặng**: IS bị gate 51% cửa sổ, NS 0.3%. Điểm trung bình tách IS/NS với AUC 0.006, tức gần như phát hiện nguồn hoàn hảo (ngược chiều). Hệ số lớn nhất: `drift_excess` +2.65, `aperiodic_exponent` +2.48. TUSL slow vs bckg thì vẫn đạt (14% vs 26.5%), nên lỗi chủ yếu là **khác nguồn/thiết bị**, nhưng hệ quả như nhau: giữ quyết định của đúng nhóm cần giúp.
- Biến thể định sẵn (bỏ `delta_ratio`, `alpha_peak`): +0.042 [0.022, 0.067] trên TUAR, E9 vẫn trượt (45% vs 0.1%, AUC 0.001).
- **Kết luận theo kế hoạch:** không triển khai, tracker giữ luật tay. Không thử biến thể thứ ba (sẽ là chọn sau khi nhìn dữ liệu). Code scorer giữ lại, có test, tắt mặc định (chỉ bật khi có `results/sqi_v2_learned_scorer.json`).
- **Cách viết R1 trong paper:** đặc trưng v2 có thông tin (+0.08), luật tay không khai thác được; học điểm chất lượng từ nhãn artifact lâm sàng biến chỉ số chất lượng thành bộ phát hiện nguồn/bệnh lý. Đây là bằng chứng cho DG2 ("phải chặn bằng thiết kế, rồi kiểm tra"), một phát hiện có giá trị cho cộng đồng hơn là "v2 tốt hơn v1".

## 7. Lý do `eye` (cử động mắt / chớp mắt), kế hoạch chốt 2026-11-17 trước khi nhìn dữ liệu

Vấn đề: 86% kênh-cửa sổ eyem trên TUAR không có lý do nào.

1. **Thiết kế:** thêm lý do `eye` với lời khuyên "nhờ người bệnh nhắm mắt và giữ yên". **Trọng số 0**: không đổi điểm kênh, nên không đổi cổng chất lượng, E9 (tỉ lệ gate), E11 và AUC phát hiện. Theo thiết kế, nó không thể giữ quyết định của người bệnh stroke. Nó chỉ đổi nhãn hiển thị trong điều kiện G (panel đã hiện lý do đầu tiên của mỗi kênh kể cả khi kênh đạt).
2. **Phát triển chỉ trên nửa calib TUAR:** chọn quy tắc từ các đặc trưng đã cache (không học model). Ngưỡng đặt để `eye` bật trên ≤ 5% kênh-cửa sổ sạch của nửa calib.
3. **Đánh giá một lần trên nửa test.** Chỉ đưa vào app nếu đạt cả bốn:
   - (a) tỉ lệ kênh-cửa sổ eyem có lý do đúng loại (`eye`, `transient`, `drift`) tăng so với hiện tại;
   - (b) `eye` bật trên ≤ 7% kênh-cửa sổ sạch của nửa test;
   - (c) E7 tổng (đúng loại trong số có lý do) không giảm quá 2 điểm so với 71%;
   - (d) **kiểm tra an toàn lý do:** `eye` không bật trên IS nhiều hơn NS, và không bật trên TUSL slow nhiều hơn bckg (tính theo tỉ lệ kênh-cửa sổ). Nếu trượt, panel sẽ gọi slowing của người bệnh stroke là "cử động mắt", nên không đưa vào.
4. Nếu không đạt: báo cáo kết quả âm, code giữ lại nhưng tắt.
