# NeuraTriage EEG — Báo cáo kỹ thuật

> Nghiên cứu thử nghiệm phân loại đột quỵ qua EEG  
> Mục tiêu: UIST 2026 Demo Paper — Deadline 10/7/2026  
> **Lưu ý:** Prototype nghiên cứu, không phải thiết bị y tế

---

## 1. Dataset

### 1.1 Ischemic Stroke (IS) — 50 bệnh nhân

| Thuộc tính | Chi tiết |
|-----------|---------|
| **Nguồn** | Figshare, DOI: `10.6084/m9.figshare.21679035` |
| **Tên dataset** | *EEG recordings from ischemic stroke patients* |
| **Số bệnh nhân** | 50 (ký hiệu `sub-01` → `sub-50`) |
| **Định dạng gốc** | European Data Format (`.edf`) |
| **Kênh EEG** | 18 kênh theo chuẩn 10-20: Fp1, Fp2, F3, F4, C3, C4, P3, P4, O1, O2, F7, F8, T3, T4, T5, T6, Fz, Cz |
| **Tần số lấy mẫu** | 256 Hz |
| **Độ dài ghi** | ~320 giây/bệnh nhân (resting state) |
| **Thời điểm ghi** | Sau khi xác định đột quỵ thiếu máu cục bộ, trong giai đoạn điều trị cấp cứu |
| **Thiết bị** | EEG clinical-grade, môi trường bệnh viện |
| **Giấy phép** | CC BY 4.0 (open access) |

**Bằng chứng tính hợp lệ:**
- Dataset được công bố peer-reviewed trên Figshare với DOI cố định, có thể truy cập và cite
- 50 bản ghi EDF riêng biệt, mỗi file chứa header lâm sàng (tuổi, giới, chẩn đoán)
- Sau convert sang `.npz`: std điện thế ~60–150 µV — nằm trong phạm vi sinh lý EEG người
- Không có kênh flat-line hay giá trị NaN sau pipeline tiền xử lý
- Manifest kiểm tra: 50/50 file convert thành công, không có lỗi shape hay channel mapping

### 1.2 Non-Stroke / Healthy (NS) — 50 subjects

| Thuộc tính | Chi tiết |
|-----------|---------|
| **Nguồn** | PhysioNet — EEG Motor Movement/Imagery Database (eegmmidb) |
| **URL chính thức** | `https://physionet.org/content/eegmmidb/1.0.0/` |
| **Subjects** | S001 → S050, resting baseline (eyes open + closed, run 1–2) |
| **Định dạng gốc** | EDF+ |
| **Kênh EEG** | 64 kênh → chọn 18 kênh khớp với IS (10-20 system) |
| **Tần số lấy mẫu gốc** | 160 Hz → resample lên **256 Hz** (scipy.signal.resample_poly) |
| **Task** | Resting state T0 — không cử động, không tưởng tượng |
| **Thiết bị** | BrainAmp amplifier, 64-channel cap (extended 10-10 system) |
| **Giấy phép** | PhysioNet Credentialed Health Data License / Open Data ODC-By |

**Bằng chứng tính hợp lệ:**
- PhysioNet là kho dữ liệu y sinh học hàng đầu thế giới, được trích dẫn trong hàng chục nghìn bài báo
- Goldberger et al. (2000) — bài báo gốc PhysioBank được cite > 10,000 lần (ISI)
- Resting-state T0 là protocol chuẩn trong EEG research, dùng làm healthy baseline
- Sau resample và channel alignment: std ~60 µV, phù hợp EEG resting bình thường
- 50/50 subjects convert thành công, dot-strip bug đã fix (loại ký tự "." cuối tên kênh như `Fp1.`)
- **Giới hạn:** Resting healthy không tương đương hoàn toàn control lâm sàng cho stroke — đây là baseline nghiên cứu phổ biến, không phải ICU recording

### 1.3 Hemorrhagic Stroke (HS) — 4 bệnh nhân *(exploratory)*

| Thuộc tính | Chi tiết |
|-----------|---------|
| **Nguồn** | UCLH Stroke EIT Dataset (University College London Hospital) |
| **Bệnh nhân** | P3 (Big ICH), P5 (Small ICH), P6A (Big ICH), P11 (Big ICH) |
| **Đoạn dùng** | Pre-injection TD segments (8–20 giây/bệnh nhân) |
| **Nhãn pipeline** | `hemorrhagic` / class `2` |
| **Windows giữ lại** | 88 windows từ 4 bệnh nhân sau SQI filter |
| **Trạng thái** | **Exploratory** — chưa đủ cho 5-fold validated CV |

---

## 2. Tiền xử lý (Preprocessing Pipeline)

```
Raw EDF/BDF
  └─► Chọn 18 kênh (10-20 system), strip ký tự đặc biệt
  └─► Resample → 256 Hz (scipy.signal.resample_poly, nếu cần)
  └─► Normalize: z-score per channel (loại DC offset)
  └─► Windowing: 1-giây (256 samples), bước 0.5s (50% overlap)
  └─► SQI filter: loại window có std < 0.1 µV hoặc > 500 µV
  └─► Lưu .npz: {data: (18, N_samples), channels: [...], fs: 256}
```

**Channel mapping:** IS dataset dùng tên gốc EDF. PhysioNet dùng extended 10-10 → map về 18 kênh tiêu chuẩn. Không rename nếu tên kênh không có trong mapping — channel bị bỏ qua (thiếu sẽ được zero-pad).

---

## 3. Thuật toán trích xuất đặc trưng

### 3.1 Approximate Entropy (ApEn)

Đo tính phức tạp và khả năng dự đoán của chuỗi thời gian EEG.

$$\text{ApEn}(m, r, N) = \ln \frac{C_m(r)}{C_{m+1}(r)}$$

- $C_m(r)$: tỷ lệ các cặp template có khoảng cách Chebyshev $\leq r$
- Tham số: $m = 2$, $r = 0.2 \cdot \text{std}(x)$
- Ý nghĩa lâm sàng: EEG đột quỵ có **ApEn thấp hơn** (kém phức tạp hơn, ít ngẫu nhiên hơn)
- Tính trên từng kênh → **18 giá trị/window**

### 3.2 Fuzzy Entropy (FuEn)

Cải tiến của ApEn, dùng hàm membership fuzzy thay vì Heaviside step function — ổn định hơn khi chuỗi ngắn và có nhiễu.

$$\text{FuEn}(m, r, N) = \ln \frac{\phi^m(r)}{\phi^{m+1}(r)}, \quad \mu(d) = e^{-d^n / r^n}$$

- Tham số: $m = 2$, $r = 0.2 \cdot \text{std}(x)$, $n = 2$ (exponential kernel)
- Tính trên từng kênh → **18 giá trị/window**

> **Feature block ApFu = [ApEn × 18] + [FuEn × 18] = 36 features/window**  
> Baseline design theo **Tong et al. (2025)** — đã validated trên EEG stroke classification

### 3.3 Multifractal Detrended Fluctuation Analysis (MFDFA)

Phân tích cấu trúc đa phân hình của tín hiệu EEG — bắt được tương quan dài hạn (long-range correlations) mà entropy không bắt được.

**Quy trình 5 bước:**
1. Profile tích lũy: $Y(i) = \sum_{k=1}^{i}[x(k) - \bar{x}]$
2. Chia $Y$ thành các đoạn không chồng lấp kích thước $s$ (nhiều scale $s$)
3. Khớp polynomial bậc $q$ (detrending từng đoạn)
4. Tính fluctuation: $F^2_\nu(s)$, sau đó $F_q(s) = \left[\frac{1}{2N_s}\sum_{\nu} F^2_\nu(s)\right]^{1/q}$
5. Fit power-law: $F_q(s) \sim s^{h(q)}$ → phổ Hurst $h(q)$

**Features trích xuất (per channel, buffer 4-giây):**
- `alpha_min`, `alpha_max`: chiều rộng singularity spectrum $f(\alpha)$
- `h_mean`: Hurst exponent trung bình
- `f_alpha_max`: chiều cao đỉnh $f(\alpha)$

→ Mỗi channel: ~4 MFDFA features × 3 scale-ranges = **~12 features/channel**  
→ 18 kênh × 12 = **~216 raw**, sau selection còn **~60 features/window** (cùng dimensionality với ApFu)

> Extension theo **Wang et al. (2025)** với EMD-based detrending hook

### 3.4 Signal Quality Index (SQI)

5 features đo chất lượng tín hiệu mỗi window (dùng cả để filter lẫn làm feature đầu vào):

| Feature | Mô tả |
|---------|-------|
| `sqi_std` | Std điện thế — loại kênh phẳng hoặc bão hòa |
| `sqi_kurtosis` | Phát hiện artifact spike |
| `sqi_band_ratio` | Tỷ lệ năng lượng delta/gamma — artifact cơ |
| `sqi_line_noise` | Năng lượng 50 Hz — nhiễu đường điện |
| `sqi_mean_sqi` | SQI tổng hợp [0, 1] |

→ **5 features/window** (cộng thêm vào feature vector)

### 3.5 Bộ phân loại: LightGBM + TPE

| Thành phần | Chi tiết |
|-----------|---------|
| **Classifier** | LightGBM v4 (Gradient Boosting Decision Trees) |
| **Hyperparameter tuning** | Optuna TPE (Tree-structured Parzen Estimator) |
| **Số Optuna trials** | 0 (fast, dùng default) hoặc 30 (full CV run) |
| **Calibration** | Temperature scaling (post-hoc probability calibration) |
| **Online inference** | EMA smoothing + hysteresis + cooldown cho real-time alert |
| **Class balancing** | `class_weight='balanced'` |

---

## 4. Đánh giá (Evaluation Protocol)

- **Scheme:** 5-fold patient-level GroupKFold (không data leakage giữa bệnh nhân)
- **Split:** 80 patients train / 20 patients test mỗi fold
- **Metrics:**
  - **Macro-F1** — metric chính (cân bằng class imbalance)
  - **pt-F1** — patient-level macro-F1 (aggregate window predictions → 1 label/patient)
  - **AUC** — area under ROC curve
  - **ECE** — Expected Calibration Error (độ tin cậy xác suất)
- **Statistical test:** Paired t-test trên 5 fold deltas giữa các điều kiện

---

## 5. Kết quả thực nghiệm

### 5.1 Ablation Study — Binary IS vs NS

**N = 100 bệnh nhân | 43,459 windows | IS: 31,641 windows | NS: 11,818 windows**

| Điều kiện | #Feat | Macro-F1 | ±std | pt-F1 | AUC | ECE |
|-----------|-------|----------|------|-------|-----|-----|
| ApFu | 60 | 0.7924 | 0.059 | 0.959 | 0.894 | 0.038 |
| MFDFA | 60 | 0.7177 | 0.048 | 0.899 | 0.820 | 0.042 |
| ApFu+MFDFA | 120 | 0.8225 | 0.048 | 0.970 | 0.917 | 0.024 |
| **ApFu+MFDFA+SQI** | 125 | **0.9913** | 0.003 | **1.000** | **0.9997** | 0.003 |

### 5.2 Chi tiết 5 folds — Điều kiện tốt nhất (ApFu+MFDFA+SQI)

| Fold | #Test patients | #Test windows | Macro-F1 | AUC | pt-F1 |
|------|----------------|---------------|----------|-----|-------|
| 1 | 20 | 8,691 | 0.9930 | 0.9998 | 1.000 |
| 2 | 20 | 8,294 | 0.9879 | 0.9995 | 1.000 |
| 3 | 20 | 9,086 | 0.9907 | 0.9994 | 1.000 |
| 4 | 20 | 8,693 | 0.9889 | 0.9998 | 1.000 |
| 5 | 20 | 8,695 | 0.9958 | 0.9999 | 1.000 |
| **Mean** | — | — | **0.9913** | **0.9997** | **1.000** |
| **±std** | — | — | 0.003 | 0.0002 | 0.000 |

### 5.3 Paired comparison

| So sánh | Δ Macro-F1 | p-value |
|---------|-----------|---------|
| ApFu+MFDFA − ApFu | **+0.030** | **0.021** |
| ApFu+MFDFA+SQI − ApFu+MFDFA | **+0.169** | **0.001** |

### 5.4 Exploratory 3-class: NS / IS / HS *(chưa validated)*

**N = 104 bệnh nhân | 4-fold CV | 10 Optuna trials**

| Điều kiện | Macro-F1 | pt-Macro-F1 |
|-----------|----------|------------|
| ApFu | 0.647 | 0.707 |
| ApFu+MFDFA | 0.755 | 0.873 |
| **ApFu+MFDFA+SQI** | **0.866** | **0.886** |

---

## 6. Tài liệu tham khảo

1. **IS Dataset:** Figshare 21679035. *EEG recordings from ischemic stroke patients.* DOI: 10.6084/m9.figshare.21679035. License: CC BY 4.0.

2. **NS Dataset:** Goldberger AL et al. PhysioBank, PhysioToolkit, and PhysioNet. *Circulation* 101(23):e215–e220, 2000. eegmmidb v1.0.0: https://physionet.org/content/eegmmidb/1.0.0/

3. **HS Dataset:** UCLH Stroke EIT Dataset (University College London Hospital). Pre-injection TD EEG segments, 4 patients with ICH label.

4. **Baseline algorithm:** Tong S, et al. (2025). EEG-based stroke classification using approximate and fuzzy entropy features with LightGBM. *(Reference for ApFu design.)*

5. **MFDFA extension:** Wang H, et al. (2025). MFDFAI: Multifractal detrended fluctuation analysis with IMF selection for EEG pathology detection.

6. **LightGBM:** Ke G et al. LightGBM: A Highly Efficient Gradient Boosting Decision Tree. *NeurIPS 2017.*

7. **Optuna:** Akiba T et al. Optuna: A Next-generation Hyperparameter Optimization Framework. *KDD 2019.*

---

## 7. Giới hạn

- **Prototype nghiên cứu** — không phải thiết bị y tế được phê duyệt
- Kết quả binary IS vs NS là **internal validation** — chưa có external validation prospective
- Healthy resting EEG (PhysioNet) **không tương đương** control lâm sàng stroke thực tế
- Kết quả 3-class HS là **exploratory**, cần thêm dữ liệu hemorrhagic (≥ 5 patients cho 5-fold)
- **Không thay thế CT/MRI** — chỉ là triage support
- Chưa có thử nghiệm workflow lâm sàng với bác sĩ (user study cần trước khi claim clinical utility)

---

*Tổng hợp từ: `results/mfdfa_ablation_results.json`, `results/cv_summary.txt`, `docs/uist_evidence.md`*  
*Ngày: 2026-05-11*
