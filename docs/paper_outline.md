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
| E1 | Model gốc chủ yếu nhận diện máy đo: SQI-only AUC 0.998 | `results/source_confound_report.json` | ✅ |
| E2 | AUC giảm qua từng mức kiểm soát: Riemann khớp mắt 0.82, EEGNet 0.63–0.77 | `results/leave_source_out_*.json` | 🟡 các con số AUC chưa có CI (R5) |
| E3 | Ngưỡng cố định sinh 51–66 báo động giả/giờ | `results/clinical_utility.json`, `device_recalibration.json` | ✅ |
| E4 | Độ trễ end-to-end đủ cho real-time: Riemann 7 ms/chunk 0.5 s, end-to-end 18 kênh p95 65 ms (RTF 0.13); LightGBM features 98 ms/chunk (RTF 0.34); SQI v2 2 kênh 5.7 ms, 18 kênh 49 ms mỗi giây. CPU laptop Intel, không gồm mạng/trình duyệt | `results/latency_riemann.json`, `results/latency.json` | ✅ 2026-11-16 |
| E5 | Headband thật: v1 báo SQI ≈ 0.88 trên log bị drift, v2 phát hiện | `data/ble_signals_log.csv` | ❌ case study chưa chạy |
| E6 | SQI v2 phát hiện artifact tốt hơn v1 ít nhất 0.05 AUC (TUAR, nửa test) | `results/tuar_sqi_eval.json` | ⏳ đang tải TUAR |
| E7 | **Lý do đúng loại artifact** (musc/chew → muscle, eyem → transient/drift, elec → flat/drift/transient) | `results/tuar_sqi_eval.json` → `reason_accuracy_e7` | ⏳ code xong 2026-11-16, chờ TUAR |
| E8 | **Kênh tệ nhất trùng kênh có nhãn artifact**, so với mức ngẫu nhiên và với v1 | `results/tuar_sqi_eval.json` → `localization_e8` | ⏳ code xong 2026-11-16, chờ TUAR |
| E9 | Kiểm tra an toàn với ngưỡng đóng băng: slowing/IS không bị gate nhiều hơn | `results/sqi_v2_gate_check.json` | ⏳ hiện IS/NS chưa đạt, chạy lại sau khi chỉnh trên TUAR |
| E10 | Conformal giữ FAR ≤ α, heuristic và calib theo cửa sổ thì không | `results/conformal_no_decision.json` | ✅ |
| E11 | Đảm bảo vẫn đứng vững khi có cổng chất lượng SQI v2 | | ⏳ sau E6 |
| E12 | Cần bao nhiêu bệnh nhân để calibrate tại chỗ. **Dưới ⌈1/α⌉−1 bệnh nhân mỗi lớp thì không bao giờ báo động** (α = 0.1 → 9). FAR trung bình ≤ α ở mọi n, theo hình răng cưa đúng lý thuyết 1 − ⌈(n+1)(1−α)⌉/(n+1). Nhưng một lần calibrate với 9–20 bệnh nhân có **10–29% khả năng cho FAR thực > α + 0.05** (p90 tới 0.37). Đảm bảo trung bình ≠ đảm bảo cho từng site | `results/conformal_calibration_size.json` | ✅ 2026-11-16. Đưa vào Discussion: cần conformal có điều kiện theo tập calib nếu muốn đảm bảo cho từng site |
| E13 | Đo bao lâu thì quyết định được (FAR, độ nhạy, tỉ lệ No-Decision theo thời lượng ghi) | | ❌ phải kiểm trước thứ tự cửa sổ trong cache |
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
