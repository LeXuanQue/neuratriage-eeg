# NeuraTriage — Brief bảo vệ trước hội đồng

> Mục tiêu: nắm chắc toàn bộ dự án, trình bày tự tin, và trả lời được câu hỏi khó.
> Nguyên tắc vàng khi bảo vệ: **trung thực về phạm vi**. Điểm mạnh lớn nhất của đề
> tài này trước hội đồng không phải con số accuracy, mà là **sự nghiêm ngặt về
> phương pháp** (biết rõ giới hạn của chính mình). Đừng over-claim.

---

## 0. Pitch 30 giây (học thuộc)

> "Đột quỵ — *thời gian là não*. Phân biệt sớm trước khi tới CT/MRI giúp định tuyến
> bệnh nhân nhanh hơn. Chúng tôi xây một **hệ thống hỗ-trợ-triage EEG thời gian thực**:
> trích đặc trưng phi tuyến đa thang (MFDFA) kết hợp Entropy, phân loại bằng
> LightGBM, và — phần cốt lõi HCI — một **lớp cảnh báo chống alarm-fatigue** với
> SQI gating, EMA và hysteresis. Chúng tôi đánh giá nghiêm ngặt theo **patient-level
> CV** cho bài toán **nhị phân ischemic vs non-stroke**, và **thành thật chỉ ra một
> confound thiết bị** mà phần lớn nghiên cứu cùng lĩnh vực bỏ qua. Đây là **prototype
> nghiên cứu, không phải thiết bị y tế.**"

English version: *"Stroke is a time-critical emergency. We built a real-time
EEG triage-support prototype that fuses multifractal (MFDFA) and entropy features
with an alarm-fatigue-aware alerting layer (SQI gating, EMA, hysteresis). We
validate binary ischemic-vs-non-stroke under strict patient-level cross-validation
and we explicitly characterize an acquisition confound that most prior work hides.
It is a research prototype, not a medical device."*

---

## 1. Vấn đề & động lực (clinical)

- Đột quỵ là nguyên nhân hàng đầu gây tử vong/tàn tật. **"Time is brain"** — mỗi phút
  chậm tái tưới máu là mất neuron không hồi phục (Powers et al., 2019).
- **Gold standard** xác chẩn: CT không cản quang (loại trừ xuất huyết) + MRI. Nhưng
  cần hạ tầng bệnh viện cố định → **không triển khai được trên xe cứu thương**.
- **EEG**: portable, non-invasive, nhạy với thiếu máu cục bộ vỏ não sớm → ứng viên
  cho "sensing layer" ở giai đoạn **pre-hospital triage**.
- Khoảng trống thực tế: thuật toán offline đạt accuracy cao nhưng **chưa thành công cụ
  tương tác dùng được** trong môi trường cấp cứu hỗn loạn (nhiễu, alarm fatigue).

## 2. Ba rào cản (khung lập luận của bài)

1. **Clinical utility**: triage tối thiểu phải tách stroke / non-stroke đáng tin trong
   điều kiện nhiễu thực tế (phân biệt IS/HS là mong muốn nhưng thiếu dữ liệu HS công khai).
2. **Algorithmic robustness**: các subtype chia sẻ "EEG slowing" → đặc trưng đơn miền
   không đủ; cần đa-thang phi tuyến.
3. **Operational / methodological**: (a) "data leakage" do chia dữ liệu ở mức cửa sổ
   thay vì mức bệnh nhân → thổi phồng accuracy (Brookshire 2024); (b) artifact khi xe
   chạy → báo động giả → **alarm fatigue** (Cvach 2012).

## 3. Đóng góp (cách bạn định vị)

1. **Hybrid feature pipeline** — fuse Entropy (ApEn/FuEn) cục bộ + MFDFA dài hạn.
2. **Leakage-resistant evaluation** — patient-level CV (không bệnh nhân nào ở cả train
   lẫn test).
3. **Operationally-aware interaction design** (đóng góp HCI/UIST chính) — SQI gating →
   No-Decision, EMA smoothing, hysteresis, cooldown → chống alarm fatigue.
4. **Honesty về confound** — chủ động đo và báo cáo confound thiết bị (điểm cộng lớn
   về tính nghiêm ngặt).

## 4. Phương pháp kỹ thuật (nắm số liệu)

- **Dữ liệu**: 50 bệnh nhân ischemic (`dataset_ischemic/`) + 50 non-stroke resting
  PhysioNet (`dataset_healthy/`); 4 bệnh nhân hemorrhagic UCLH-EIT (exploratory).
- **Tiền xử lý**: 18 kênh, 256 Hz, lọc nhân quả 1–35 Hz, **SQI** (line noise, clipping,
  điện cực rơi).
- **Đặc trưng**: dual-window — 1 s cho Entropy, 4 s cho MFDFA; vector **125 chiều**
  (gồm Fuzzy Asymmetric Index, bất đối xứng bán cầu).
- **Mô hình**: LightGBM tối ưu bằng **TPE (Optuna)**.
- **Online detector**: hop 0.5 s, ring buffer, lọc nhân quả; **SQI gate 0.55, EMA β=0.35,
  θ_high=0.80, θ_low=0.60, cooldown 15 s** (xem `eeg_stroke_pipeline.py` RealTimeConfig).
- **Đánh giá**: patient-level 5-fold CV, 30 Optuna trials; metric: macro-F1, patient-F1,
  AUC, ECE; paired test cho từng thành phần.

## 5. Hệ thống / App (phần "UIST")

- FastAPI backend phục vụ UI React (port 8501): login, live WS/replay, upload, inference,
  hồ sơ bệnh nhân/thiết bị/cảnh báo, báo cáo PDF.
- Màn **Theo dõi trực tiếp**: risk-score stream + SQI + "Vì sao hệ thống nghĩ thế?"
  (top signals, confidence) + topomap + SHAP + phổ năng lượng + **trạng thái No-Decision**
  khi SQI thấp.
- Đây là điểm khác biệt với các nghiên cứu chỉ báo accuracy: **biến classifier tĩnh thành
  công cụ hỗ-trợ-quyết-định đáng tin**.

## 6. Kết quả (số liệu thật — nói đúng phạm vi)

- **Binary IS vs NS (validated — đây là TOÀN BỘ phạm vi của bài)**: macro-F1 — ApFu 0.79
  → +MFDFA 0.82 (+0.03, p=0.021) → +SQI 0.99. (`fig_ablation`)
- Phân biệt IS/HS (xuất huyết) **ngoài phạm vi** — chỉ nêu ở Future work, KHÔNG trình bày
  như kết quả. (Nếu hội đồng hỏi về HS: "đó là hướng mở rộng tương lai khi có cohort HS
  người đủ lớn.")
- **Phát hiện confound (điểm trung thực)**: chỉ **5 đặc trưng SQI** (chất lượng tín hiệu,
  KHÔNG phải bệnh lý) đã tách 2 lớp ở **AUC 0.998** (`fig_confound`,
  `results/source_confound_report.json`).

## 7. Hạn chế (chủ động nêu trước khi hội đồng hỏi)

1. **Confound thiết bị (chính)**: IS và NS từ 2 nguồn/rig khác nhau; source trùng 100%
   với label → AUC ≈1.0 phần lớn phản ánh "máy nào ghi" chứ không thuần bệnh lý.
   Patient-level split chống leakage *trong* cohort, **không** chống confound *giữa* cohort.
2. **Chưa có user study hoàn chỉnh** — §V hiện là protocol; chưa có bằng chứng usability
   với paramedic/clinician.
3. **HS underpowered**: 4 bệnh nhân / 88 cửa sổ, exploratory.
4. **Healthy resting EEG** không phải control non-stroke lâm sàng hoàn hảo.
5. Metric nội bộ, **chưa phải validation cấp triển khai**.

## 8. Future work (hướng đi tiếp)

- Khử confound bằng **same-rig controls** (vd TUH: stroke + neuro-normal cùng máy).
- Hướng **within-subject rig-invariant** (bất đối xứng bán cầu trong cùng bệnh nhân).
- Thu cohort HS người thật để 3-class thành validated.
- Chạy **user study** (NASA-TLX, decision time, false-alarm acknowledgement).
- Monitoring liên tục trong xe cứu thương; đánh giá prospective gắn với workflow.

---

## 9. ⭐ Q&A CHUẨN BỊ — câu hỏi hội đồng hay hỏi

**Q1. AUC ~1.0 — quá đẹp, có phải overfit/leakage?**
→ "Đúng, và chúng tôi đã *chủ động chứng minh* điều đó. Chỉ 5 đặc trưng chất lượng tín
hiệu — không mã hoá bệnh lý — đã đạt AUC 0.998, nghĩa là model có thể 'đi tắt' theo
thiết bị. Vì IS và NS đến từ 2 nguồn khác nhau, con số tuyệt đối không nên đọc là độ
chính xác chẩn đoán. Đặc trưng bệnh lý thuần (entropy) cho AUC 0.906 — con số trung
thực hơn. Đây là lý do chúng tôi đề xuất same-rig controls cho bước tiếp theo."
*(Trả lời thế này biến điểm yếu thành điểm cộng về nghiêm ngặt.)*

**Q2. Tại sao đổi từ 3-class xuống binary?**
→ "Dữ liệu hemorrhagic công khai cực hiếm; chúng tôi chỉ có 4 bệnh nhân — không đủ cho
patient-level CV. Trình bày 3-class như validated sẽ là over-claim. Nên chúng tôi
validate binary và để 3-class ở mức exploratory một cách minh bạch."

**Q3. Vì sao EEG mà không dùng CT/MRI?**
→ "Không thay thế CT/MRI — bổ trợ. CT/MRI là gold standard nhưng cố định tại bệnh viện.
EEG portable, dùng ở pha *pre-hospital* để định tuyến nhanh, rồi vẫn xác chẩn bằng
imaging. Hệ thống của chúng tôi là *triage-support*, không phải chẩn đoán."

**Q4. SQI gating đẩy 0.79→0.99 — vậy MFDFA có thực sự đóng góp?**
→ "MFDFA đóng góp +0.03 macro-F1 (p=0.021) khi *chưa* có SQI gating — có ý nghĩa thống
kê. Khi đã gating thì SQI áp đảo. Điều này hợp lý: ở điều kiện tín hiệu kém (thực địa),
MFDFA mới phát huy; ở tín hiệu sạch, gating đủ tốt."

**Q5. Đóng góp HCI/UIST ở đâu, đây có phải chỉ là bài ML?**
→ "Đóng góp chính là *lớp tương tác*: SQI gating → No-Decision, EMA, hysteresis,
cooldown — thiết kế để chống alarm fatigue, một vấn đề HCI có tài liệu. Hình
alert-state timeline cho thấy hệ thống chặn báo động giả khi có artifact. Classifier
chỉ là một thành phần."

**Q6. Có user study chưa?**
→ "Chưa hoàn chỉnh — đây là hạn chế chúng tôi nêu rõ. §V đã có protocol (N≈8–12
paramedic, đo decision time, false-alarm acknowledgement, NASA-TLX). Đây là bước tiếp
theo trước camera-ready."

**Q7. Dataset chuyển trạng thái pre→post stroke?**
→ "Gần như không tồn tại công khai — không ai ghi được EEG nền trước khi đột quỵ xảy ra.
Cái khả thi là continuous monitoring *sau* nhập viện. Chúng tôi nêu đây là giới hạn dữ
liệu của lĩnh vực, không riêng đề tài."

**Q8. ECE/calibration thế nào, có đáng tin để cảnh báo?**
→ "ECE thấp (~0.005 ở cấu hình đầy đủ), nhưng vì confound nên độ tin của xác suất tuyệt
đối cần đọc thận trọng; chúng tôi dùng hysteresis + cooldown để giảm cảnh báo dao động."

**Q9. Tại sao patient-level CV quan trọng?**
→ "Nếu chia ở mức cửa sổ, các cửa sổ của *cùng một bệnh nhân* rơi vào cả train lẫn test
→ model học 'chữ ký cá nhân' chứ không phải bệnh lý → accuracy ảo. Patient-level đảm bảo
test trên bệnh nhân hoàn toàn mới."

**Q10. Điểm mới so với ApFu-TPELGBM (Tong 2025) và MFDFA (Wang 2025)?**
→ "Hai nhóm đó dùng *hoặc* entropy *hoặc* MFDFA; chúng tôi *fuse* cả hai, thêm lớp
tương tác vận hành (SQI/alarm-fatigue) mà các bài thuần thuật toán bỏ qua, và đánh giá
leakage-resistant + minh bạch confound."

---

## 10. Bản đồ figure → luận điểm (dùng khi trình slide)

| Figure | Dùng cho slide |
|--------|----------------|
| `fig_ui` / `fig_ui_live` | "Hệ thống thật, chạy được" — demo giao diện triage |
| `fig_alert_timeline` | Đóng góp HCI: No-Decision/EMA/hysteresis chống alarm fatigue |
| `fig_ablation` | Kết quả binary + vai trò từng thành phần |
| `fig_confound` | Tính nghiêm ngặt: tự phơi bày confound (gây ấn tượng mạnh) |
| Architecture (Gemini) | Tổng quan pipeline 4 tầng |

## 11. Ba câu chốt cuối buổi (nếu được hỏi "đóng góp lớn nhất?")
1. Một **prototype tương tác hoàn chỉnh, chạy thật**, không chỉ thuật toán offline.
2. **Thiết kế chống alarm-fatigue** (SQI gating/hysteresis) cho bối cảnh pre-hospital.
3. **Sự trung thực phương pháp**: tự đo và công bố confound — điều phần lớn literature né.
