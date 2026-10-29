    # NeuraTriage — Process, Challenges, Results & Future Works

> EEG stroke-triage research prototype (UIST 2026 poster, deadline **2026-07-10**)
> **Không phải thiết bị y tế** — internal research evidence, không phải clinical claim.

---

## III. Process

### Quá trình nghiên cứu gồm các bước nào?

| # | Bước | Nội dung chính | Trạng thái |
|---|------|----------------|------------|
| 1 | **Thu thập & chuẩn hoá data** | IS (Figshare, 50 BN), NS (PhysioNet, 50), HS (UCLH EIT, 4 — exploratory); EDF/BDF → npz | ✅ Xong (HS thiếu) |
| 2 | **Tiền xử lý** | 18 kênh 10-20, resample 256 Hz, window 1s/overlap 50%, SQI filter, z-score | ✅ Xong |
| 3 | **Trích xuất đặc trưng** | ApEn+FuEn (36), MFDFA (~60), SQI (5) | ✅ Xong |
| 4 | **Model & tuning** | LightGBM v4 + Optuna TPE + temperature scaling | ✅ Xong |
| 5 | **Đánh giá (CV)** | 5-fold patient-level GroupKFold; Macro-F1/pt-F1/AUC/ECE; paired t-test | ✅ Binary validated |
| 6 | **Mở rộng 3-class (NS/IS/HS)** | Thêm HS → 4-fold exploratory | 🟡 Exploratory (chưa validated) |
| 7 | **Acquisition thật (device)** | Brain-Life Focus+ BLE → stream live | 🔴 Chưa stream được |
| 8 | **Báo cáo & UIST** | technical_report, uist_evidence, poster | 🟡 Đang tiến hành |

### Mình đang ở bước nào?

- **Binary IS-vs-NS (Bước 1–5): đã validated** với 5-fold patient-level CV.
- **Đang ở Bước 6–7:** mở rộng 3-class NS/IS/HS (mới exploratory vì thiếu HS) **và** chuẩn bị acquisition trên thiết bị thật.
- Bước 8 song song: viết báo cáo/poster cho UIST.

### Roadmap / Outline

```
NeuraTriage (research)
│
├── [1] DATA ─────────── ✅  IS×50 · NS×50 · HS×4(exploratory)
├── [2] PREPROCESS ───── ✅  18ch · 256Hz · 1s window · SQI filter
├── [3] FEATURES ─────── ✅  ApFu(36) · MFDFA(~60) · SQI(5)
├── [4] MODEL ────────── ✅  LightGBM + Optuna TPE + calibration
├── [5] EVAL (binary) ── ✅  5-fold GroupKFold → Macro-F1 0.99
│
├── [6] 3-CLASS ──────── 🟡 ★ ĐANG Ở ĐÂY ★  NS/IS/HS 4-fold exploratory
│        └─ chặn: thiếu bệnh nhân HS cho 5-fold validated
│
├── [7] REAL DEVICE ──── 🔴 ★ ĐANG Ở ĐÂY ★  Brain-Life Focus+ BLE
│        └─ chặn: thiếu UUID/packet/scaling → phải probe máy thật
│
└── [8] REPORT/UIST ──── 🟡  technical_report · poster (deadline 07-10)
```

---

## IV. Challenges

### Đang trục trặc ở bước nào? Tại sao?

#### 1. Về DATA — lớp HS (hemorrhagic) thiếu (chặn Bước 6)

- HS chỉ có **4 bệnh nhân / 88 windows** (UCLH: P3, P5, P6A, P11) → đủ 4-fold *exploratory* nhưng **chưa đủ** 5-fold patient-level CV.
- Hệ quả: kết quả 3-class NS/IS/HS **chưa validated**, chỉ là xu hướng dương.
- NS dùng healthy resting (PhysioNet) **không tương đương** control lâm sàng non-stroke thực tế → baseline chưa sát.
- IS hiện 50 BN là *internal*, **chưa có external validation** cohort độc lập.

#### 2. Về SOURCES — tài liệu thiết bị không đủ (chặn Bước 7)

- Spec PDF Brain-Life Focus+ chỉ là **Public Version**: có phần cứng (2 kênh EEG **differential** AF3/AF4/T7/T8, 256 Hz, "not a medical device") nhưng **thiếu GATT UUID / packet format / µV scaling** → **không viết được decoder** từ tài liệu.
- Buộc đi hướng **discovery-first** (probe máy thật mới lấy được thông số).

#### 3. Về DEVICES — phần cứng & lệch phân phối (chặn Bước 7)

- Cần **headband vật lý** + môi trường Bluetooth thật để probe (`bleak`, backend-side); không demo cloud được.
- **Lệch phân phối nghiêm trọng:** model train trên **18 kênh monopolar**, thiết bị chỉ **2 kênh differential** → 16/18 kênh impute NaN → khác phân phối training ⇒ live path **chỉ exploratory**, chưa đáng tin.
- Mapping kênh thật (AF3/AF4/T7/T8 → nhãn nào) **chưa xác nhận** với vendor.

---

## Results (kết quả nghiên cứu)

> Kết quả khoa học (phân loại EEG), **không phải** trạng thái app. Tất cả là *internal validation* — chưa phải clinical claim.

### A. Task đã validated — Binary IS vs NS

- **Scheme:** 5-fold patient-level **GroupKFold** (không leak giữa bệnh nhân), 80 train / 20 test mỗi fold.
- **Cohort:** N = **100 BN** (50 IS + 50 NS), **43,459 windows** (IS 31,641 / NS 11,818).
- **Classifier:** LightGBM v4 + Optuna TPE + temperature scaling.

| Điều kiện | #Feat | Macro-F1 | ±std | pt-F1 | AUC | ECE |
|-----------|-------|----------|------|-------|-----|-----|
| ApFu (ApEn+FuEn) | 60 | 0.7924 | 0.059 | 0.959 | 0.894 | 0.038 |
| MFDFA | 60 | 0.7177 | 0.048 | 0.899 | 0.820 | 0.042 |
| ApFu+MFDFA | 120 | 0.8225 | 0.048 | 0.970 | 0.917 | 0.024 |
| **ApFu+MFDFA+SQI** | 125 | **0.9913** | 0.003 | **1.000** | **0.9997** | 0.003 |

**Paired t-test (5 fold deltas):**
- ApFu+MFDFA − ApFu: **Δ +0.030**, p = **0.021** → MFDFA thêm tín hiệu đo được khi chưa có SQI.
- ApFu+MFDFA+SQI − ApFu+MFDFA: **Δ +0.169**, p = **0.001** → SQI là yếu tố trội ở binary split (MFDFA gain co lại khi đã có SQI).

→ **Kết luận:** trên IS-vs-NS, ApFu+MFDFA+SQI đạt **Macro-F1 ~0.99**, **pt-F1 = 1.000**, calibration tốt (ECE 0.003), ổn định qua 5 fold (std 0.003).

### B. Task exploratory — 3-class NS / IS / HS *(chưa validated)*

- N = **104 BN**, 4-fold CV, 10 Optuna trials.

| Điều kiện | Macro-F1 | pt-Macro-F1 |
|-----------|----------|-------------|
| ApFu | 0.647 | 0.707 |
| ApFu+MFDFA | 0.755 | 0.873 |
| **ApFu+MFDFA+SQI** | **0.866** | **0.886** |

- MFDFA delta (no SQI): +0.108, p = 0.064 → **xu hướng dương exploratory**, chưa đạt ngưỡng thống kê.
- ⚠ Trình bày như *positive trend*, **không** claim "validated 3-class".

### C. Đóng góp phương pháp

- Feature: **ApEn+FuEn (36)** + **MFDFA (~60: singularity spectrum α-width, Hurst h_mean, f(α) peak)** + **SQI (5)**.
- Pipeline chuẩn hoá tái lập được (18 kênh, 256 Hz, window 1s/overlap 50%, SQI filter).
- 3 nguồn data đã tích hợp & cite: IS (Figshare DOI 10.6084/m9.figshare.21679035), NS (PhysioNet eegmmidb), HS (UCLH EIT).

---

## Future works

**1. Bổ sung dataset cho lớp còn thiếu (IS / HS):**
- **HS (thiếu nhất):** hiện **4 BN / 88 windows** → cần convert thêm **≥1 (lý tưởng ≥5) bệnh nhân ICH** (UCLH hoặc nguồn HS khác) để 3-class NS/IS/HS đạt **5-fold patient-level validated** thay vì exploratory.
- **IS / external validation:** thêm **cohort IS độc lập (site khác, prospective)** để external validation, tránh overfit nguồn đơn.
- **NS control:** thêm **non-stroke clinical/ICU control** thay healthy resting để baseline sát thực tế.

**2. Test trên thiết bị thật (Brain-Life Focus+):**
- Probe BLE (`ble_probe.py`) lấy UUID/packet/scaling → stream EEG **trực tiếp** (thay vì replay file).
- Đánh giá lại model trên **dữ liệu acquisition thật**; xử lý lệch phân phối 2-ch differential vs 18-ch monopolar (re-train/adapt hoặc đo độ rớt hiệu năng).

**3. Nâng chất lượng bằng chứng:**
- External validation + **prospective workflow** với bác sĩ; **clinician user study** trước khi claim clinical utility.
- Hoàn tất đánh giá cho **UIST 2026** (deadline **2026-07-10**); giữ tuyên bố ở mức "research prototype / triage support", không claim chẩn đoán.

---

> ⚠️ Lưu ý mojibake: file này viết UTF-8. Khi chỉnh sửa, kiểm tra lại dấu tiếng Việt (grep `?` giữa từ / từ bị mất dấu).
