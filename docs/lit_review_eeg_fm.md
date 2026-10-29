# Literature review P2: Trustworthy EEG Foundation Models (+ thiết bị mới thay Focus+)

_2026-10-22 · nối tiếp `docs/lit_review.md` (Q1–Q5, không lặp lại) · Nguồn: WebSearch + arXiv API + Crossref API + đọc trang abs/HTML._

**Trạng thái kiểm chứng:** ✅ = metadata đã kiểm qua arXiv API/Crossref; 📄 = đã đọc abstract hoặc một phần full text; ⚠️ = chỉ có snippet tìm kiếm hoặc aggregator, phải đọc full text trước khi trích số liệu.

---

## Tóm tắt: gap cho hướng flagship

| Hướng | Văn liệu nói gì | Gap còn mở |
|---|---|---|
| Q6 FM landscape | FM 2025–2026 scale lên 21k–60k giờ (FEMBA, LUNA, REVE). CBraMod chỉ 4M tham số, pretrain TUEG trên 4×A5000 trong ~5 ngày | Không thiếu model. Thiếu **đánh giá nghiêm** |
| Q7 Benchmark | **Mâu thuẫn:** EEG-Arena (20k eval) nói FM thắng baseline ở hầu hết tác vụ. Zare 2026 + Compass nói baseline cổ điển hoặc encoder random vẫn ngang hoặc hơn trên cohort ngoài | Khác biệt nằm ở **protocol** (in-distribution vs external cohort, có kiểm soát leakage hay không) |
| Q8 Cross-site / TTA | EA giúp cross-subject trong BCI. TTA cho FM **không ổn định**, gradient-based thường làm tệ hơn (NeuroAdapt-Bench) | EA/RA theo subject **xóa nhãn mức subject** (mình đã đo: riemann_rc = 0.5). Văn liệu EA là BCI, chưa ai nêu xung đột này cho tác vụ chẩn đoán |
| Q9 Leakage TUEG | CBraMod và LUNA pretrain trên TUEG rồi đánh giá trên TUAB/TUEV/TUAR/TUSL, **không nêu loại trừ subject**. Brain4FMs né bằng cách bỏ hẳn dữ liệu TUH ở downstream | **Chưa có split công khai loại trừ subject TUEG khỏi downstream TUH**, nên chưa ai đo được độ lớn của leakage |
| Q10 Trạng thái mắt | Tìm 2 vòng, **không thấy công trình nào kiểm định eyes-open/closed như shortcut** trong EEG lâm sàng | Kết quả của mình (0.95 tụt xuống 0.65–0.82 khi khớp trạng thái mắt) là đóng góp mới |
| Q11 Ít kênh | FM channel-flexible tốt hơn (EEG-Arena). Có biến thể tiny 7.8M (FEMBA) | Chưa có FM nào được đánh giá trên **headband trán 2–4 kênh + protocol cross-site** |
| Q12 Đa phương thức | EEG+fNIRS pretraining mới có 1 công trình (DGIST 2025, ⚠️). Multimodal 2026 phần lớn là EEG + biểu diễn thời-tần + text | **Chưa có FM EEG+fNIRS+PPG**. Chưa có headset lai được kiểm định cho thiếu máu não cấp |
| Q13 EEG-to-text | Teacher forcing thổi phồng ≥3×, input nhiễu cho kết quả gần như EEG thật (Jo 2024) | Không theo hướng này. **Mượn phương pháp**: baseline nhiễu/random là negative control bắt buộc |

**Phát biểu gap flagship (đề xuất):** _Chưa có EEG foundation model nào được pretrain trên TUEG với **danh sách loại trừ subject công khai**, rồi đánh giá đồng thời bằng (i) leave-source-out, (ii) khớp trạng thái mắt, (iii) negative control (dataset identity, encoder random, input nhiễu), và (iv) biến thể ít kênh trên thiết bị thật._ Mỗi thành phần đã có ở đâu đó trong văn liệu; **sự kết hợp và bộ benchmark công khai thì chưa có.**

---

## Q6: Toàn cảnh EEG foundation model

| Model | Venue | Dữ liệu pretrain | TUEG? | Cỡ / compute | Trạng thái |
|---|---|---|---|---|---|
| BENDR (Kostas et al.) | Front. Hum. Neurosci. 2021, DOI 10.3389/fnhum.2021.653659 | TUEG | ⚠️ có (theo trí nhớ, cần kiểm) | Nhỏ | ✅ |
| BIOT (Yang et al.) | arXiv 2305.10351 (NeurIPS 2023 ⚠️) | Có TUH | Có | — | ✅ |
| LaBraM (Jiang, Zhao, Lu) | ICLR 2024, arXiv 2405.18765 | ~2.500 giờ, ~20 dataset | ⚠️ chưa rõ trên trang abs | Base/Large/Huge | ✅ 📄 |
| EEGPT | NeurIPS 2024, DOI 10.52202/079017-1239 | — | — | — | ✅ (P1) |
| **CBraMod** (Wang et al.) | ICLR 2025, arXiv 2412.07236 | **TUEG: 69.652 recording, 14.987 subject, 27.062 giờ thô → >9.000 giờ sau làm sạch; 19 kênh 10-20, resample 200 Hz, đoạn 30 s** | **Có** | **4.0M tham số; 4× RTX A5000, ~5 ngày** | ✅ 📄 |
| FEMBA (Tegon et al.) | EMBC 2025, arXiv 2502.06438 | >21.000 giờ, >5.000 người | ⚠️ | 7.8M–389M (Mamba hai chiều); TUAB 81.82% bal-acc / AUROC 0.892 ⚠️ | ✅ |
| CSBrain (Zhou et al.) | arXiv 2506.23075 (NeurIPS 2025 ⚠️) | — | ⚠️ | — | ✅ |
| **REVE** (El Ouahidi et al.) | arXiv 2510.21585 (có trên papers.neurips.cc 2025) | **>60.000 giờ, 92 dataset, ~25.000 subject** | ⚠️ chưa rõ | Mã hóa vị trí 4D cho mọi kiểu đặt điện cực; giấy phép CC BY-NC-ND | ✅ 📄 |
| **LUNA** (Döner et al.) | NeurIPS 2025 (arXiv 2510.22257, camera-ready) | **TUEG + Siena, >21.000 giờ** | **Có** | Query + cross-attention, chi phí tuyến tính theo số kênh; giảm 300× FLOPs. SOTA TUAR (AUROC 0.921) và TUSL | ✅ 📄 |
| DeeperBrain | arXiv 2601.06134 (2026) | — | — | — | ✅ |
| FoME | arXiv 2409.12454 | — | — | — | ✅ |

**Hệ quả compute cho máy của mình:** quy mô CBraMod (4M tham số, ~9.000 giờ TUEG) chạy được trên **một GPU 24–32 GB** trong khoảng 1–2 tuần. Đây là ước lượng từ 4×A5000 trong 5 ngày, chưa đo. Quy mô REVE hoặc FEMBA-389M thì nên thuê cụm.

## Q7: Benchmark và negative control

1. **EEG-Arena: "Benchmarking EEG Foundation Models at Scale: Lessons from 20,000 Evaluations."** Chen, Peng, Qin, …, Wu. arXiv 2609.32743 (2026). ✅ 📄
   - 30 FM + 25 baseline có giám sát, 57 tác vụ, 23 dataset, >20.000 lượt đánh giá.
   - FM thắng ở hầu hết tác vụ (nhất là cấu hình không bipolar). Pretraining giúp tối ưu sớm hơn. **Số tham số không dự đoán được hiệu năng.** Thêm dữ liệu pretrain thì tiếp tục có lợi. Model linh hoạt về kênh thắng model cố định kênh.
   - ⚠️ Abstract không nói về chồng lấn TUEG/TUAB. Phải đọc full text (91 trang) trước khi trích kết luận "FM thắng".
2. **Brain4FMs.** Shen et al. arXiv 2602.11558 (2026). ✅ 📄
   - 17 FM. Chọn dataset downstream **tách khỏi TUH** để tránh chồng lấn. Loại khỏi phân tích chính: NeuroLM/LaBraM trên SEED-IV, MVPFormer trên SWEC (do đã thấy trong pretrain).
   - Split theo subject (khoảng 3:1:1). FM thắng baseline ở phần lớn tác vụ lâm sàng, nhưng LocCNN thắng hầu hết FM ở Parkinson. Hoán vị kênh làm giảm mạnh ở tác vụ động kinh. **Không có phân tích riêng cho ít kênh.**
3. **Zare. "A Negative-Control Protocol for Clinical EEG Foundation-Model Benchmarks."** arXiv 2607.24519 (2026). ✅ 📄 (P1 đã nêu, ở đây bổ sung số liệu)
   - CAUEEG (NC/MCI/dementia, 1.187 recording, macro-AUROC): **classical 0.734 > BIOT 0.677 > CBraMod 0.669 > REVE 0.568**. **Encoder random 0.667 > REVE 0.570.**
   - CHB-MIT: REVE 0.793 so với comparator tốt nhất 0.739, nhưng khoảng tin cậy 95% của hiệu số là [−0.36, +11.22] điểm %, cắt qua 0, nên chưa kết luận được REVE hơn.
   - Khuyến nghị: khớp montage, kiểm tra trùng bệnh nhân, dùng comparator mạnh, thêm control cho biểu diễn (encoder random, decode dataset identity), báo CI cho hiệu số ghép cặp.
4. **EEG-FM-Compass.** Liu et al. arXiv 2601.17883 (2026). ✅ ⚠️
   - 12 FM, 13 dataset, 9 paradigm BCI. Linear probe thường không đủ, model chuyên biệt train từ đầu vẫn cạnh tranh. Thêm EA khi train hoặc fine-tune giúp đa số model trên BNCI2014001 (snippet).

**Diễn giải mâu thuẫn:** EEG-Arena đo trên nhiều tác vụ in-distribution. Zare đo trên cohort ngoài, có control. **Protocol quyết định kết luận**, đây đúng là luận điểm "trustworthy" của mình.

## Q8: Chuyển giữa site, alignment, test-time adaptation

1. **Junqueira et al. "A Systematic Evaluation of Euclidean Alignment with Deep Learning for EEG Decoding."** arXiv 2401.10746. ✅ 📄
   - EA cải thiện accuracy trung bình cho mọi model và dataset cross-subject, hội tụ nhanh hơn 70%. **Bối cảnh: BCI, nhãn thay đổi trong cùng một subject.**
2. **NeuroTTT.** Wang et al. arXiv 2509.26301 (2025). ✅ 📄 TTA dựa trên entropy có thể hơn TTT tự giám sát toàn tham số trong cross-subject khó.
3. **Lee, Pradeepkumar, Sun. "Test-Time Adaptation for EEG Foundation Models: A Systematic Study under Real-World Distribution Shifts" (NeuroAdapt-Bench).** arXiv 2604.16926. ✅ 📄
   - Venue: trang PMLR ghi MLHC 2026 (PMLR 340), một trang khác ghi ICML 2026. ⚠️ **Xác nhận venue trước khi trích.**
   - TTA từ các lĩnh vực khác **cho kết quả không nhất quán, thường làm tệ hơn**; phương pháp dựa trên gradient tệ nhất; phương pháp không tối ưu (T3A) ổn định hơn. Có kịch bản lệch cực mạnh: Ear-EEG.
4. NeuroOnline. Li et al. arXiv 2607.03925 (2026). ✅ ⚠️ Chưa đọc abstract.
5. Bối cảnh cũ: Xu et al. 2020, *Cross-Dataset Variability Problem in EEG Decoding With Deep Learning* (Front. Hum. Neurosci., PMC7188358). ⚠️ Motor imagery, có pre-alignment online.

**Nối với dữ liệu của mình (insight quan trọng):** EA/RA theo **từng subject** đưa trung bình mỗi subject về gốc tọa độ. Với BCI thì vô hại vì nhãn thay đổi theo trial. Với **chẩn đoán**, nhãn không đổi trong suốt một subject, nên alignment xóa luôn tín hiệu cần học (riemann_rc của mình đúng bằng 0.5). **Cần alignment theo site, tính trên control hoặc trên phần bất biến với lớp, không theo subject.** Chưa thấy công trình nào nêu điểm này cho tác vụ chẩn đoán. ⚠️ Mức chắc chắn trung bình.

## Q9: Leakage pretraining TUEG

- CBraMod: pretrain trên TUEG. Câu duy nhất liên quan: _"The majority of downstream datasets are sourced from institutions different from the pretraining dataset."_ TUAB/TUEV trích cùng nguồn (Obeid & Picone 2016) nhưng **không nêu loại trừ**. ✅ 📄
- LUNA: pretrain TUEG + Siena, báo SOTA trên **TUAR và TUSL (đều thuộc TUH)**. Trang abs không nói loại trừ. ⚠️ Cần đọc full text.
- Brain4FMs: tránh hẳn dữ liệu TUH ở downstream. Đây là cách né, không phải cách đo.
- **Gap đo được:** công bố **danh sách subject TUEG đã loại trừ** khỏi pretraining + split downstream TUAB/TUSL/TUAR/TUEV tương ứng, rồi so (a) pretrain có subject downstream với (b) pretrain đã loại trừ. Converter `scripts/tuab_to_npz.py` của mình đã tách subject từ tên file (`<subj>_<sess>_<tok>.edf`). ⚠️ **Phải kiểm tra mã subject có thống nhất giữa TUEG và các sub-corpus/phiên bản không** (TUH từng đổi định dạng giữa v1 và v2).

## Q10: Trạng thái mắt như shortcut

- Tìm 2 vòng, **không thấy nghiên cứu nào kiểm định eyes-open/closed như shortcut** cho phân loại EEG lâm sàng giữa các dataset.
- Liên quan gián tiếp: Mattiev et al. 2022 (Bioengineering, PMC9854523): EO/EC hay được dùng làm tác vụ validation và cross-validation dễ overfit theo subject. ⚠️
- **→ Kết quả eye-state control của mình (`results/leave_source_out_eyes_*.json`) là đóng góp mới.** Nên đưa thành một trục bắt buộc của benchmark flagship.

## Q11: Ít kênh / thiết bị đeo

1. Kokate et al. 2026 (arXiv 2604.23091, đã có ở P1): CBraMod 5M thắng model lớn hơn tới 31× trên 4/5 dataset; adapter kênh gây negative transfer khi fine-tune.
2. EEG-Arena: model linh hoạt về kênh thắng ở hầu hết cấu hình kênh. ✅
3. FEMBA tiny 7.8M tham số khả thi cho thiết bị hạn chế tài nguyên. ⚠️
4. SingLEM (FM 1 kênh) và FAVC-Net (sinh 13 kênh ảo từ Fp1/Fp2/F7/F8): ⚠️ **chỉ thấy trên aggregator, chưa xác minh được trên arXiv.** Không trích.
5. **Số liệu của chính mình (TUSL cùng thiết bị ghi, N=29, chỉ mang tính định hướng):** top-4 [F3, C4, C3, FP2] AUC 0.853 ≈ đủ 18 kênh 0.846; bộ kiểu Focus+ [F7, F8, T3, T4] **0.794, yếu nhất**; proxy AF3/AF4 (FP1/FP2) chỉ 0.690.
- **Gap:** chưa FM nào được đánh giá trên headband trán 2–4 kênh với protocol cross-site.

## Q12: Đa phương thức (EEG + fNIRS + PPG)

1. **DGIST (Computers in Biology and Medicine, 2025):** pretrain biểu diễn chung + riêng cho EEG và fNIRS, ~1.250 giờ, 918 người, dùng được dữ liệu chỉ EEG, chỉ fNIRS hoặc ghép cặp. ⚠️ **Chưa có DOI, chỉ thấy trang thư viện DGIST.**
2. Bakhtiarvand et al. "Multimodal Pretraining for Generalizable EEG Representation Learning." arXiv 2607.21384 (2026). ✅ 📄
   - "Đa phương thức" ở đây là EEG thô + thời-tần + text, **không có fNIRS hay PPG**.
   - CHB-MIT AUROC 0.874–0.878, nhưng **leave-one-subject-out chỉ đạt balanced accuracy 0.558**. Thêm một ví dụ cho thấy protocol quyết định kết quả.
3. Uchitel et al. "Wearable, Integrated EEG–fNIRS Technologies: A Review." Sensors 2021, DOI 10.3390/s21186106. ✅ (ADC dùng chung, không dây, thiết kế dạng vi mạch)
4. Kassab et al. "Multichannel wearable fNIRS-EEG system for long-term clinical monitoring." Human Brain Mapping 2017, DOI 10.1002/hbm.23849. ✅ ⚠️ 128 kênh quang + 32 EEG, bộ điều khiển 650 g đeo hông, pin ~24 h, thử trên 1 bệnh nhân TIA.
5. van Bohemen et al. "Safety, feasibility, and acceptability of a novel device to monitor ischaemic stroke patients." arXiv 2403.17362. ✅ 📄 EEG + ECG, **153 giờ dùng ở khoa không có biến cố bất lợi**, khó chịu là vấn đề chính (17 lần).
6. NCT03034902: EEG–fNIRS lai để tìm vùng thiếu máu ở stroke bán cấp, 5 bệnh nhân, thiết bị thương mại (microEEG + NIRScout). ⚠️
- **Gap:** chưa có FM nào cho EEG+fNIRS+PPG. Chưa có headset lai đeo được, được kiểm định cho thiếu máu cấp.

## Q13: Độ tin cậy của EEG-to-text

1. **Jo et al. "Are EEG-to-Text Models Working?"** arXiv 2405.06459 (2024). ✅ 📄
   - Teacher forcing ngầm khi đánh giá thổi phồng điểm **≥3×**. **Input nhiễu thuần cho điểm gần bằng EEG thật.** Đề xuất: đánh giá cả có lẫn không teacher forcing, bắt buộc baseline nhiễu.
2. Zhang et al. "Is EEG-to-Text Feasible in Real-World Scenarios? …" ACL 2026, arXiv 2607.18749. ✅ ⚠️ Chưa đọc. Snippet: một số hệ vẫn phụ thuộc teacher forcing.
- **Kết luận:** không theo hướng này. Nhưng **"baseline nhiễu/random"** cùng tinh thần với encoder random của Zare và probe SQI-only của mình → đưa vào benchmark flagship như negative control bắt buộc.

---

## Hệ quả cho THIẾT BỊ MỚI thay Focus+

Rút từ văn liệu ở trên và số liệu của chính dự án.

| Quyết định | Đề xuất | Căn cứ |
|---|---|---|
| **Vị trí điện cực** | Tối thiểu **F3, F4, C3, C4** (+ T7/T8 cho bất đối xứng/BSI; + Fp1/Fp2 nếu muốn theo dõi chớp mắt để làm SQI) | Ablation TUSL: top-4 fronto-central ≈ 18 kênh (0.853 vs 0.846); bộ trán-cực + thái dương kiểu Focus+ yếu nhất (0.794); AF3/AF4 proxy 0.69. ELECTRA-STROKE: delta-BSI là chỉ số phụ tốt nhất (AUC 0.91, CI rộng, chỉ 6 ca LVO) |
| **Montage** | **Monopolar, chung một tham chiếu** (không phải 2 kênh vi sai) | Khớp tập 19 kênh 10-20 mà CBraMod/LUNA pretrain trên TUEG → **dùng FM ngay**. Focus+ vi sai làm 16/18 kênh thành NaN |
| **ADC** | TI **ADS1299** (24-bit, 8 kênh, có lead-off detection để đo trở kháng) | Rashid et al. 2018 (Sensors, DOI 10.3390/s18113721) ✅: ADS1299 + điện cực ướt Ag/AgCl tương đương máy phòng lab ở <40 Hz. Board EVM **không dùng cho chẩn đoán** |
| **Điện cực** | Điện cực khô **chủ động** (active, phủ vàng) hoặc semi-dry | Snippet: điện cực khô thụ động khó đạt chất lượng; điện cực khô chủ động tốt hơn ⚠️ |
| **Chất lượng tại chỗ** | Đo trở kháng liên tục + SQI trên thiết bị, phản hồi ngay cho người đeo | ELECTRA-STROKE: dù nhân viên đã tập huấn, **32% bản ghi không đủ chất lượng**, trung vị chỉ 14% dữ liệu sạch |
| **Đa phương thức** | fNIRS 2 kênh trán + PPG, **dùng chung đồng hồ lấy mẫu** với EEG | Thiếu máu = tưới máu → fNIRS đúng đích. Uchitel 2021 (ADC dùng chung), Kassab 2017 |
| **Metadata bắt buộc trong luồng dữ liệu** | Nút đánh dấu **mắt mở/nhắm**, cấu hình lọc firmware, đơn vị µV, fs, ID thiết bị, phiên bản firmware | Xóa đúng 3 shortcut đã tìm ra: lọc low-pass ở bệnh viện, trạng thái mắt, đơn vị V/µV |
| **Giao thức** | Tài liệu BLE công khai + stream qua **LSL** | Tránh lặp lại việc phải lấy ngược giao thức Focus+. LSL là chuẩn của cộng đồng nghiên cứu |
| **Độ thoải mái** | Nhẹ, ít điểm tì | van Bohemen 2024: khó chịu là vấn đề chính khi đeo dài |
| **Pháp lý** | Ghi rõ "không phải thiết bị y tế" cho tới khi được chứng nhận | Chẩn đoán = thiết bị y tế (NĐ 98/2021). ⚠️ Cần xác nhận với chuyên gia pháp lý |

---

## Giả thuyết kiểm chứng được (cho giai đoạn thí nghiệm)

- **H1 (leakage):** FM pretrain trên TUEG **có** chứa subject downstream sẽ cho AUC trên TUAB/TUSL cao hơn bản đã loại trừ subject. Dự đoán: chênh dương, đo được.
- **H2 (protocol):** Dưới leave-source-out + khớp trạng thái mắt, lợi thế của FM so với Riemann (~0.82) thu hẹp hoặc biến mất (cùng hướng Zare 2026).
- **H3 (alignment):** Alignment theo subject có lợi cho BCI nhưng đưa tác vụ chẩn đoán về mức ngẫu nhiên. Alignment theo site, tính chỉ trên control, giữ được tín hiệu.
- **H4 (ít kênh):** Fine-tune FM trên 4 kênh fronto-central ≈ 18 kênh. Với 2 kênh trán-cực thì yếu, bất kể model nào. → Trực tiếp quyết định vị trí điện cực của thiết bị mới.
- **H5 (thiết bị):** SQI + phản hồi trở kháng trên thiết bị làm giảm tỉ lệ bản ghi không dùng được so với mốc 32% của ELECTRA-STROKE.

## Việc còn phải làm trước khi trích dẫn

- Đọc full text: EEG-Arena (có loại trừ TUH không), LUNA (có loại trừ subject TUSL/TUAR khỏi pretraining không), LaBraM (có TUEG không, cỡ Huge), REVE (TUEG có trong 92 dataset không).
- Xác nhận venue: NeuroAdapt-Bench (MLHC hay ICML 2026), REVE/CSBrain (NeurIPS 2025), BIOT (NeurIPS 2023).
- Tìm DOI bài EEG+fNIRS của DGIST; xác minh SingLEM và FAVC-Net trên arXiv.
- Kiểm tra mã subject TUH thống nhất giữa TUEG và TUAB/TUSL (để làm danh sách loại trừ cho H1).

## Sources
- FM: [CBraMod](https://arxiv.org/abs/2412.07236) · [LaBraM](https://arxiv.org/abs/2405.18765) · [BIOT](https://arxiv.org/abs/2305.10351) · [BENDR](https://doi.org/10.3389/fnhum.2021.653659) · [FEMBA](https://arxiv.org/abs/2502.06438) · [CSBrain](https://arxiv.org/abs/2506.23075) · [REVE](https://arxiv.org/abs/2510.21585) · [LUNA](https://arxiv.org/abs/2510.22257) · [DeeperBrain](https://arxiv.org/abs/2601.06134) · [FoME](https://arxiv.org/abs/2409.12454) · [EEGNet](https://doi.org/10.1088/1741-2552/aace8c)
- Benchmark: [EEG-Arena](https://arxiv.org/abs/2609.32743) · [Brain4FMs](https://arxiv.org/abs/2602.11558) · [Zare 2026](https://arxiv.org/abs/2607.24519) · [EEG-FM-Compass](https://arxiv.org/abs/2601.17883) · [Kokate 2026](https://arxiv.org/abs/2604.23091)
- Alignment/TTA: [EA systematic](https://arxiv.org/abs/2401.10746) · [NeuroTTT](https://arxiv.org/abs/2509.26301) · [NeuroAdapt-Bench](https://arxiv.org/abs/2604.16926) ([PMLR](https://proceedings.mlr.press/v340/lee26a.html)) · [NeuroOnline](https://arxiv.org/abs/2607.03925) · [Xu 2020](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7188358/) · [Mattiev 2022](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9854523/)
- Đa phương thức/thiết bị: [Bakhtiarvand 2026](https://arxiv.org/abs/2607.21384) · [Uchitel 2021](https://doi.org/10.3390/s21186106) · [Kassab 2017](https://doi.org/10.1002/hbm.23849) · [van Bohemen 2024](https://arxiv.org/abs/2403.17362) · [NCT03034902](https://clinicaltrials.gov/study/NCT03034902) · [Rashid 2018 ADS1299](https://doi.org/10.3390/s18113721) · [ELECTRA-STROKE](https://pmc.ncbi.nlm.nih.gov/articles/PMC10791060/)
- EEG-to-text: [Jo 2024](https://arxiv.org/abs/2405.06459) · [Zhang 2026 ACL](https://arxiv.org/abs/2607.18749)
