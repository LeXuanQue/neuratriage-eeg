# Literature review: P1 (cho `docs/full_paper_plan.md`)

_2026-10-06 · venue mục tiêu: HCI (CHI/IMWUT) · Nguồn tra cứu: WebSearch + Crossref API + arXiv API + Europe PMC (Semantic Scholar bị rate-limit)._

**Trạng thái kiểm chứng:** ✅ = metadata (tiêu đề/tác giả/năm/venue/DOI hoặc arXiv) đã kiểm qua API; 📄 = đã đọc abstract/trang chính; ⚠️ = chỉ có từ snippet tìm kiếm, phải đọc full text trước khi trích dẫn số liệu.

---

## Tóm tắt: gap nào còn mở?

| Hướng | Kết luận | Hệ quả cho paper |
|---|---|---|
| R1 SQI v2 (phổ/1/f) | **Gap đã đóng một phần.** Spectral slope để phát hiện artifact 1 kênh đã có (Fasol 2023). Phần **còn mở**: dùng nó làm *cổng quyết định* trong vòng real-time + trên headband thật + phát hiện drift/tiếp xúc kém | Không claim "thuật toán SQI mới". Claim: tích hợp vào gating, kiểm chứng trên TUAR + thiết bị thật |
| R2 conformal No-Decision | **Mở (cho EEG stroke).** Conformal chuẩn vỡ khi lệch phân phối theo bệnh nhân. Calibration cá nhân hóa +20 điểm % coverage (Chatterjee 2026). SCRC có sẵn khung lý thuyết | Bắt buộc calibrate patient-level. Mới là *kết hợp* quality-gate + conformal + nghiên cứu người dùng |
| R3 FM baseline | **Rò rỉ đã được xác nhận**: TUAB chung nguồn TUEG với LaBraM/CBraMod; BIOT pretrain có TUH. Model encode luôn danh tính dataset (Zare 2026: 1.000) | FM chạy trên TUSL **phải** gắn cờ leakage. Nếu dùng, chọn CBraMod (nhỏ, tốt ở ít kênh) |
| R4 / confound | **Hội tụ với văn liệu 2026:** "dataset identity" là shortcut phổ biến của EEG FM (Zare 2026). Probe SQI-only của mình là một *negative control rẻ*, cùng tinh thần | Trích dẫn để chứng minh vấn đề không chỉ của riêng mình. Đóng góp = negative control ở mức feature |
| Q5 HCI abstain | **Phát hiện quan trọng nhất:** abstain làm **tăng false negative** (bác sĩ chẩn đoán thiếu khi AI từ chối; Jabbour 2025, N=259) | Thiết kế No-Decision phải nói rõ "**chưa biết ≠ bình thường**" + hành động cụ thể. User study phải đo IS bị bỏ sót trong trạng thái No-Decision |

---

## Q1: SQI/artifact cho EEG ít kênh, aperiodic 1/f, TUAR

1. **Fasol, Escudero, Gonzalez-Sulser. "Single-Channel EEG Artifact Identification with the Spectral Slope." IEEE BIBM 2023.** DOI 10.1109/bibm58861.2023.10385840 (preprint bioRxiv 10.1101/2023.11.12.566749). ✅ ⚠️
   - Dùng độ dốc phổ 1 kênh để đánh dấu epoch nhiễm bẩn. Snippet: acc 94.2%, F1 86.4%, κ 0.83 (cần kiểm full text: dataset nào, có phải người hay chuột).
   - **→ Đây là prior art gần nhất của R1.** R1 không mới ở mức detector.
2. **Grosselin et al. "Quality Assessment of Single-Channel EEG for Wearable Devices." Sensors 19(3):601, 2019.** DOI 10.3390/s19030601 ✅ ⚠️
   - Classifier dựa trên so sánh phổ, 3 mức chất lượng, >90% accuracy; nhắm thiết bị đeo ít kênh.
3. **Donoghue et al. "Parameterizing neural power spectra into periodic and aperiodic components." Nature Neuroscience 2020.** DOI 10.1038/s41593-020-00744-x ✅
   - specparam/FOOOF, công cụ để tách 1/f.
4. **Hamid et al. "The Temple University Artifact Corpus: An Annotated Corpus of EEG Artifacts." IEEE SPMB 2020.** DOI 10.1109/spmb50085.2020.9353647 ✅ ⚠️
   - TUAR: snippet ghi 310 file, 5 loại artifact (mắt, nhai, run, electrode pop, cơ). **Cần kiểm:** TUAR có nhãn "drift/tiếp xúc kém" không. Nếu không có, R1 phải đánh giá drift trên log thiết bị + dữ liệu tiêm nhiễu.
5. **Obeid & Picone. "The Temple University Hospital EEG Data Corpus." Frontiers in Neuroscience 2016.** DOI 10.3389/fnins.2016.00196 ✅ (trích dẫn gốc cho TUH)
6. Bối cảnh lâm sàng của 1/f trong stroke: spectral exponent liên quan "EEG slowing" sau stroke (bioRxiv 10.1101/2021.08.09.455664; bioRxiv 10.1101/2024.11.07.622359). ⚠️ Mới đọc snippet. **Cảnh báo thiết kế:** stroke làm *tăng* exponent, drift cũng đẩy công suất về tần số thấp. Một SQI dựa trên 1/f có thể vô tình **gate luôn bệnh lý**. R1 phải kiểm tra rằng SQI v2 không loại bỏ nhiều window IS hơn NS (đo tỉ lệ gate theo lớp).

## Q2: Conformal / selective prediction cho EEG, non-exchangeability

1. **Chatterjee, Razin, Wu, …, Sun. "Making Conformal Predictors Robust in Healthcare Settings: a Case Study on EEG Classification." AIME 2026.** arXiv 2602.19483 ✅ 📄
   - Dùng TUAB/TUEV (ContraWR). Conformal chuẩn **không đạt coverage** khi split theo bệnh nhân. Calibration cá nhân hóa cải thiện coverage >20 điểm %. Code có trong PyHealth.
   - **→ Prior art gần nhất của R2.** Khác biệt của mình: mục tiêu là *tỉ lệ cảnh báo sai* (risk control) chứ không phải prediction set; kết hợp với quality gate; có đánh giá con người.
2. **Angelopoulos, Bates, et al. "Conformal Risk Control." arXiv 2208.02814** ✅ (thường được trích là ICLR 2024. ⚠️ Venue cần xác nhận lại trên trang chính thức.)
3. **Xu, Guo, Wei. "Selective Conformal Risk Control." arXiv 2512.12844 (2025).** ✅ 📄
   - Hai pha: chọn mẫu tự tin rồi áp CRC trên tập được chọn. SCRC-T có đảm bảo finite-sample. **Gần như đúng khung R2 cần**, nên dùng làm phương pháp nền thay vì tự chế.
4. Cohen et al. "Cross-Validation Conformal Risk Control." arXiv 2401.11974 (IEEE ISIT 2024) ✅. Hữu ích khi N nhỏ (không phải tách riêng tập calibration).

## Q3: EEG foundation models, rò rỉ pretraining, ít kênh

1. **LaBraM**: Jiang, Zhao, Lu. ICLR 2024. arXiv 2405.18765 ✅
2. **BIOT**: Yang, Westover, Sun. "Cross-data Biosignal Learning in the Wild." arXiv 2305.10351 ✅ (NeurIPS 2023 ⚠️ cần xác nhận)
3. **CBraMod**: Wang, Zhao, Luo et al. ICLR 2025. arXiv 2412.07236 ✅
4. **EEGPT**: Wang, Liu, He et al. NeurIPS 2024. DOI 10.52202/079017-1239 ✅
5. **Kokate, Aristimunha, Truong, Delorme. "Channel Adaptation for EEG Foundation Models." arXiv 2604.23091 (2026).** ✅ 📄
   - CBraMod 5M tham số thắng các model lớn hơn tới 31× trên 4/5 dataset. Có hiện tượng bất đối xứng probe/SFT: adapter kênh bên ngoài gây negative transfer khi fine-tune.
6. **Zare. "A Negative-Control Protocol for Clinical EEG Foundation-Model Benchmarks: Dataset Identity and External-Cohort Stress Testing." arXiv 2607.24519 (2026).** ✅ 📄
   - Cả 5 encoder decode **danh tính dataset = 1.000**. Encoder khởi tạo ngẫu nhiên có lúc thắng FM trên tác vụ lâm sàng. **Hội tụ trực tiếp với confound probe của mình.**
7. Benchmark về leakage: Brain4FMs (arXiv 2602.11558), "Benchmarking EEG FMs at Scale: 20,000 evaluations" (arXiv 2609.32743), EEG-FM-Compass (arXiv 2601.17883). ✅ Snippet nêu: TUAB chung nguồn TUEG với LaBraM/CBraMod; BIOT có TUH trong pretraining; một số benchmark loại kết quả bị chồng lấn. ⚠️ Cần đọc để trích đúng câu.
8. Tai. "Pretrained, Frozen, Still Leaking." arXiv 2606.09189 ✅. Embedding FM rò rỉ thuộc tính phổ (bối cảnh privacy, ít liên quan).
9. Baseline cổ điển: **EEGNet**, Lawhern et al. arXiv 1611.08024 (J. Neural Eng. 2018 ⚠️ xác nhận DOI).

**Kết luận R3:** TUSL thuộc TUH. Mọi FM pretrain trên TUEG có thể đã thấy bản ghi TUSL. Hoặc (a) chỉ báo cáo FM kèm cờ leakage, hoặc (b) bỏ FM và dùng EEGNet + pyRiemann. Với paper HCI, (b) + một câu giải thích là đủ.

## Q4: Phát hiện stroke bằng EEG trước viện, confound giữa các site

1. **van Stigt et al. "Prehospital Detection of Large Vessel Occlusion Stroke With EEG: Results of the ELECTRA-STROKE Study." Neurology 2023.** DOI 10.1212/WNL.0000000000207831 ✅ 📄
   - N=212, 8 điện cực khô, nhân viên cấp cứu đo sau 1 giờ tập huấn. Tỉ lệ theta/alpha có AUC 0.80 cho LVO.
   - **Chỉ 68% bản ghi đủ chất lượng; trung vị chỉ 14% dữ liệu sạch.** Chất lượng dùng CNN tự động.
   - **→ Bằng chứng mạnh nhất cho luận điểm HCI của mình:** nút thắt trước viện là *chất lượng tín hiệu và việc xử lý nó*, không phải classifier.
2. **Tong, Zhang, Chen, Shi et al. "A novel stroke classification model based on EEG feature fusion." Scientific Reports 2025.** DOI 10.1038/s41598-025-92807-x (PMC12022236) ✅ 📄
   - ApFu + TPE-LightGBM, NS/IS/HS, F1 0.967. Dữ liệu **ZJU4H, một bệnh viện** (một site, nên không có kiểu confound chéo nguồn như mình).
   - **Đây là phương pháp gốc pipeline mình kế thừa.** ⚠️ Chưa rõ split theo window hay theo bệnh nhân. Cần đọc full text: nếu theo window thì có thể nhắc nhẹ trong RW 2.4 (leakage).
3. Proof-of-concept MeVO/LVO (Frontiers in Neurology 2025, 10.3389/fneur.2025.1509443): n=4 dương tính / 23 âm tính. ⚠️ Mới đọc snippet.
4. Headband U. Alberta (2020, tin tức, có gyroscope/accelerometer) và Zeit Medical (công ty): **không phải peer-reviewed, không trích như bằng chứng**. Chỉ có thể nhắc như bối cảnh thương mại.
5. **Gap:** không tìm thấy công trình EEG stroke trước viện nào **kiểm định confound nguồn bằng negative control** như probe SQI-only. ⚠️ Mức chắc chắn trung bình: tìm 2 vòng, chưa quét PubMed hệ thống.

## Q5: HCI, alarm fatigue, trạng thái abstain trong CDSS

1. **Jabbour, Fouhey, Banovic, et al. "Selective Prediction Reduces the Negative Effects of Automation Bias Overall but Increases False Negatives." arXiv 2508.07617 (2025).** ✅ 📄
   - N=259 bác sĩ. AI sai kéo accuracy 66%→56%. Selective prediction kéo lại 64%. **Nhưng khi được báo AI abstain: chẩn đoán thiếu +18%, điều trị thiếu +35%** so với không có AI.
   - **→ Thách thức trực tiếp với No-Decision.** Đây là câu hỏi nghiên cứu HCI mạnh nhất cho paper.
2. **Bondi et al. "Role of Human-AI Interaction in Selective Prediction." AAAI 2022.** arXiv 2112.06751 ✅ 📄
   - *Cách* thông báo việc defer thay đổi độ chính xác của người. Báo là đã defer nhưng không lộ dự đoán AI → người làm tốt hơn.
3. **Beede et al. "A Human-Centered Evaluation of a Deep Learning System Deployed in Clinics for the Detection of Diabetic Retinopathy." CHI 2020.** DOI 10.1145/3313831.3376718 ✅
   - Ngưỡng chất lượng ảnh của model xung đột với môi trường thiếu thốn: ảnh "ungradable" bị từ chối gây ách tắc. **Tương đồng trực tiếp với SQI gate trong xe cứu thương.**
4. **Sivaraman et al. "Ignore, Trust, or Negotiate: Understanding Clinician Acceptance of AI-Based Treatment Recommendations in Health Care." CHI 2023.** DOI 10.1145/3544548.3581075 ✅
5. Zhang et al. "Fatigue-Aware Learning to Defer via Constrained Optimisation." arXiv 2604.00904 (2026) ✅ 📄. Mô hình hóa mệt mỏi tích lũy trong L2D. Có thể trích cho alarm fatigue (gián tiếp).
6. Hussain et al. "Development and translation of human-AI interaction models into working prototypes for clinical decision-making." DIS 2024. DOI 10.1145/3643834.3660697 ✅

---

## Hệ quả cho thiết kế (đưa vào plan)

1. **Câu hỏi nghiên cứu HCI chính (mới):** *No-Decision có gây bỏ sót stroke như Jabbour 2025 không, và cách diễn đạt nó (lý do + hành động "chỉnh điện cực/đo lại", không hiện xác suất) có giảm được không?* Đây là đóng góp CHI-grade, mạnh hơn bản thân thuật toán.
2. **R1 hạ cấp từ "thuật toán mới" thành "tích hợp + kiểm định".** Bắt buộc thêm kiểm tra: SQI v2 không gate IS nhiều hơn NS (vì 1/f của stroke và drift chồng nhau).
3. **R2 dựng trên SCRC/CRC + calibration patient-level** (Chatterjee 2026), không tự chế.
4. **R3: bỏ FM** (leakage TUH được xác nhận). Giữ EEGNet + pyRiemann.
5. **Motivation trong Intro:** ELECTRA-STROKE (32% bản ghi không dùng được) + Beede 2020 (ngưỡng chất lượng va chạm thực địa) + Zare 2026 (shortcut danh tính dataset).

## Việc còn phải làm trước khi trích dẫn

- Đọc full text: Fasol 2023 (dataset), Hamid 2020 TUAR (có drift không), Tong 2025 (kiểu split), Jabbour 2025 (thiết kế study, để mượn protocol).
- Xác nhận venue: Conformal Risk Control (ICLR 2024?), BIOT (NeurIPS 2023?), EEGNet DOI.
- Quét PubMed có hệ thống cho Q4 ("EEG" AND "stroke" AND ("prehospital" OR "ambulance"), 2023–2026) để củng cố claim gap.

## Sources
- [Fasol 2023 bioRxiv](https://www.biorxiv.org/content/10.1101/2023.11.12.566749v1.full) · [Grosselin 2019](https://doi.org/10.3390/s19030601) · [TUAR NSF PAR](https://par.nsf.gov/biblio/10199675-temple-university-artifact-corpus-annotated-corpus-eeg-artifacts) · [Wearable artifact review](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12473706/)
- [Chatterjee 2026](https://arxiv.org/abs/2602.19483) · [SCRC](https://arxiv.org/abs/2512.12844) · [Conformal Risk Control](https://arxiv.org/abs/2208.02814)
- [Zare 2026](https://arxiv.org/abs/2607.24519) · [Channel adaptation](https://arxiv.org/abs/2604.23091) · [Brain4FMs](https://arxiv.org/abs/2602.11558) · [20k evaluations](https://arxiv.org/abs/2609.32743) · [EEG-FM-Compass](https://arxiv.org/abs/2601.17883) · [LaBraM](https://arxiv.org/abs/2405.18765) · [CBraMod](https://arxiv.org/abs/2412.07236) · [BIOT](https://arxiv.org/abs/2305.10351)
- [ELECTRA-STROKE](https://pmc.ncbi.nlm.nih.gov/articles/PMC10791060/) · [Tong 2025](https://www.nature.com/articles/s41598-025-92807-x) · [MeVO/LVO PoC](https://www.frontiersin.org/journals/neurology/articles/10.3389/fneur.2025.1509443/xml) · [Spectral exponent stroke](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9038588/)
- [Jabbour 2025](https://arxiv.org/abs/2508.07617) · [Bondi 2022](https://arxiv.org/abs/2112.06751) · [Beede 2020](https://research.google/pubs/a-human-centered-evaluation-of-a-deep-learning-system-deployed-in-clinics-for-the-detection-of-diabetic-retinopathy/) · [Sivaraman 2023](https://dl.acm.org/doi/10.1145/3544548.3581075) · [Fatigue-aware L2D](https://arxiv.org/abs/2604.00904) · [Hussain DIS 2024](https://dl.acm.org/doi/10.1145/3643834.3660697)
