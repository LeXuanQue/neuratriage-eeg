# Kế hoạch danh mục dự án neuroscience (từ NeuraTriage)

_2026-10-29 · dựa trên: memory dự án, `docs/lit_review_eeg_fm.md` (P2), git log, kiểm tra máy._

## 1. Hiện trạng NeuraTriage

| Mảng | Trạng thái | Nguồn kiểm |
|---|---|---|
| App FastAPI + UI + WS + device BLE | Xong. Live device **chỉ SQI/No-Decision**, không ra IS/NS (cố ý) | memory 07-09 → 08-20 |
| Model | `model.joblib` binary (đã sửa lỗi đơn vị V/µV) + Riemann (4 ms/hop) | memory 10-06 |
| Test | 164–175 pass ở lần chạy cuối (10-06). **Chưa chạy lại hôm nay** | memory |
| Bằng chứng | Cascade AUC feat 0.99→0.95→0.94→0.65 khi khớp trạng thái mắt; Riemann giữ ~0.82; ngưỡng cố định → 51–66 false alert/giờ; recalibrate spec80 → sens 0.86, ~10 FA/h | `results/*.json` |
| Paper | Bản gốc đã nộp. `EEGStroke_TAPS_binary_v2_2026-10-06.docx` (12 trang) **chưa tracked**, còn placeholder ACM + NOTE ở references | memory |
| Git | Nhánh `feat/fastapi-rewrite`, **chưa có upstream (chưa push)**. Chưa commit: `README.md`, `channel_mapper.py`; 9 file `dataset_hemorrhagic/*` xoá trên đĩa chưa stage; nhiều docx/zip untracked | `git status` |
| Việc tồn | User study (venue HCI bắt buộc), model 3-class (user muốn lại), fNIRS+PPG fusion, `PROGRESS.md` stale từ 05-29 | memory |
| Hoạt động gần nhất | 10-07: recalibration. 10-22: survey P2 **và** một phiên Cyton: `backend/app/services/cyton_sim.py` + `test_cyton_sim.py` (untracked), preset `openbci_cyton` trong `channel_mapper.py` (uncommitted), sweep 6 montage 8-kênh trên TUSL → `results/cyton_montage/*.json` (thư mục `results/` bị gitignore). Memory chưa ghi phiên này | mtime, `git status` |

## 2. Ràng buộc thực tế (đã kiểm tra)

- **Không có GPU** (`nvidia-smi` không tồn tại), RAM 15.7 GB, C: trống 42 GB, F: trống 116 GB. Khuyến nghị RTX 5090 trong survey **chưa thành hiện thực** → mọi việc cần pretrain phải chờ.
- Ưu tiên: neuroscience chỉ chiếm tối đa ~40% quỹ giờ, các việc khác được ưu tiên trước.
- Hệ quả: danh mục phải (a) chạy được trên CPU ở giai đoạn đầu, (b) mỗi dự án để lại một artifact công khai đọc được trong 5 phút (repo + README + hình), (c) tối đa ~40% quỹ giờ.

## 3. Danh mục dự án

| ID | Dự án | Tái dùng được | Cần mới | Compute | Đầu ra | Rủi ro chính |
|---|---|---|---|---|---|---|
| N0 | Đóng NeuraTriage | toàn bộ | commit/push, dọn untracked, chốt user study | CPU | repo sạch + demo video | user study chưa có kế hoạch |
| N1 | **EEG shortcut audit** (bài ngắn) | LSO harness, probe SQI, eye-state, unit bug, harmonization âm tính | 2 control còn thiếu: dataset-identity probe, noise-input | CPU | workshop/TMLR-style paper + repo | tính mới so với Q10 cần kiểm lại ngay trước khi nộp |
| N2A | **EEG-FM Trust Bench**, pha không GPU | LSO harness, TUH access, `F:\tuh_data` | H1: đối chiếu subject ID TUEG↔TUAB/TUSL qua `headers.tar.gz`; H2: linear probe checkpoint công khai (CBraMod 4M) + encoder random trên các cặp source | CPU (4M tham số, suy luận) | bảng H1/H2 + code | checkpoint/giấy phép **chưa kiểm**; có thể không có split subject công khai |
| N3 | **Sinh lý fNIRS+PPG của Focus+** | `BrainLifeAsciiDecoder` đã nhận header 0x25/0x27/0x28 nhưng bỏ qua | decoder PPG/fNIRS, nghiệm pháp (nhịp thở, nín thở ngắn), HbO qua Beer–Lambert nếu biết bước sóng | CPU | "hemodynamic SQI" + hình đáp ứng | không rõ fNIRS ra intensity thô hay đã xử lý; bước sóng chưa biết |
| N4 | Thiết bị mở, bước đệm | **Đã làm 10-22:** simulator Cyton + chọn montage 8-kênh đối xứng (FP1,FP2,F3,F4,C3,C4,T3,T4), sweep 6 montage | Board thật (ADS1299), nút eye-state, trở kháng, LSL; kiểm lại sweep (N=29, CI chồng nhau) | CPU | prototype + test H4/H5 | giá/nguồn hàng chưa kiểm; chênh giữa các montage nhỏ so với N=29, không đủ để kết luận "tốt nhất" |
| N2B | Pretrain TUEG có danh sách loại trừ công khai | N2A | GPU | GPU | FM + danh sách | **chặn bởi GPU** |
| N5 | Mech-interp EEG-FM: FM mã hoá site/eye-state hay bệnh? | N2A, skills `saelens`/`nnsight` | probing + SAE | GPU ưu tiên | phân tích | phụ thuộc N2A |

Không khuyến nghị: seizure detection TUSZ, sleep staging, tái hiện BCI IV 2a. Đông người làm, không phân biệt, và bạn đã có EEGNet/Riemann baseline.

## 4. Thứ tự và lịch (29/10 → 31/12, ~9 tuần)

Xếp theo tín hiệu portfolio trên mỗi giờ, và N1/N2A dùng lại hạ tầng có sẵn nên rẻ nhất.

| Tuần | Việc | Xong khi |
|---|---|---|
| 1 | N0: chạy lại pytest, commit README+channel_mapper, quyết định 9 file hemorrhagic, push nhánh, gỡ placeholder v2 | repo push được, test xanh |
| 2–3 | N1: 2 control còn thiếu, viết bài | bản nháp đầy đủ + hình |
| 4–6 | N2A: H1 từ headers (không tải EDF), H2 probe | 2 bảng kết quả, kể cả kết quả âm |
| 1–2 (song song) | Hồ sơ đạo đức + phiếu đồng ý chung cho user study và N3; đọc DUA của TUH | biết trường có yêu cầu gì, biết được phép dùng Colab với TUH không |
| 7–8 | N3: decode + nghiệm pháp, **ghi người khác chỉ sau khi hồ sơ đạo đức xong**; trước đó thử trên bản thân | hình đáp ứng PPG/fNIRS |
| 9 | Gộp README portfolio | link công khai cho 3 dự án |

N4 để sau T1/2027 (cần mua phần cứng). N2B/N5 chờ GPU.

## 5. Quyết định của user (2026-10-29)

1. **User study: làm** ("cũng được" — hiểu là đồng ý; xác nhận lại nếu ý khác). Cần: câu hỏi nghiên cứu (Jabbour 2025: abstention làm tăng false negative của bác sĩ → cách diễn đạt No-Decision), thiết kế, đối tượng, cỡ mẫu, chấp thuận đạo đức.
2. **GPU: không mua, dùng Google Colab.** Hệ quả:
   - N5 (probing/SAE) và fine-tune/probe FM chạy được trên Colab.
   - **N2B (pretrain TUEG 27k giờ) không khả thi trên Colab** (phiên bị ngắt, đĩa tạm, không đủ ngân sách tính toán). Hạ xuống: chỉ pretrain mô hình nhỏ trên tập con, hoặc bỏ.
   - ⚠️ **Dữ liệu TUH có DUA.** Chưa xác nhận DUA có cho phép đưa lên Google Drive/Colab hay không. Không upload EDF/npz/feature TUH lên Colab cho tới khi đọc DUA. Dữ liệu công khai (Oslo, PhysioNet, Figshare) thì không bị vướng điểm này.
3. **N3: ghi trên bản thân và người khác.** Bắt buộc có: phiếu đồng ý có văn bản, xác nhận quy định đạo đức của trường (có cần hội đồng không?), dữ liệu ẩn danh, không đưa ra bất kỳ nhận định y tế nào cho người tham gia. Gộp chung hồ sơ đạo đức với user study (mục 1) để làm một lần.

## 6. Việc phải kiểm trước khi cam kết

- Tính mới của N1 và N2A: đã tìm 2 vòng ở P2 (10-22) nhưng chưa đọc full text EEG-Arena, LUNA, LaBraM, REVE (xem mục "Việc còn phải làm" của `lit_review_eeg_fm.md`).
- Deadline venue cho N1: chưa tra, không đoán.
- Mã subject TUH có thống nhất giữa TUEG và TUAB/TUSL không (quyết định N2A-H1 làm được hay không).

## 7. Tìm thêm 2026-10-29 (để paper đáng tin hơn)

Đã đọc: Peterson et al., "Differentiating Ischemic Stroke Patients from Healthy Subjects Using a Large-Scale, Retrospective EEG Database and Machine Learning Methods" (PDF từ par.nsf.gov/servlets/purl/10540688; năm và venue **chưa xác định được** từ PDF) và Chatterjee et al., arXiv 2602.19483 (AIME 2026; mới đọc abstract).

**Peterson (TUH, cùng bệnh viện cho cả hai lớp):**
- Dữ liệu: TUH EEG. Healthy = "TUH EEG segmentation" có xem lại thủ công báo cáo (ref 14, tên chưa rõ). Stroke = tìm từ khoá trong **báo cáo** (tắc MCA/ICA/PCA/ACA) rồi duyệt tay. 1,385 healthy + 374 stroke, 2,401 bản ghi, AUC 0.95, sens 93% / spec 86%.
- Tiền xử lý: resample 100 Hz, bandpass 1–40 Hz, cửa sổ 3 phút bắt đầu ở phút 1. Feature gồm tỉ số công suất phổ, sample entropy, BSI. Chia train/val theo subject ID, đã kiểm không trùng.
- **Điểm yếu của chính bài đó:** tuổi stroke trung bình 63.8 ± 15.2, còn healthy chỉ có tuổi từ một tập con do bài khác công bố, đọc được "mean age of 46" (câu bị cắt). Tức là tuổi lệch rõ. "Healthy" là bản ghi EEG lâm sàng bình thường, không phải người khoẻ mạnh. Feature là "proprietary". Có tác giả thuộc công ty phát triển công nghệ này. Chưa thấy tuyên bố chia sẻ nhãn hay code trong các đoạn đã trích.
- **Điều đáng làm:** cách gán nhãn bằng từ khoá báo cáo là con đường cho cohort IS **cùng thiết bị**, đúng route A/NEDC trong memory. **Mâu thuẫn cần giải quyết:** memory ghi TUEG v2.0.x chỉ có EDF. `F:\tuh_data\reports` đang **trống**. Peterson ghi có "matching clinical reports", nên báo cáo có tồn tại ở một phân phối nào đó của TUH. Chưa biết phân phối nào, và chưa kiểm remote.

**Mâu thuẫn trên đã giải quyết (liệt kê remote chỉ đọc, 2026-10-29):** máy chủ TUH chỉ có TUEG `v2.0.1` và `v2.0.2` (không có v1.x). `DOCS` của hai bản này chỉ có `headers.tar.gz` và các `sessions_*.list`, **không có báo cáo lâm sàng**. Vậy cách gán nhãn bằng từ khoá báo cáo như Peterson **không làm được qua tài khoản này**. **Dịch vụ tìm báo cáo của NEDC đã xác nhận tồn tại** (trang `isip.piconepress.com/projects/nedc/html/tuh_eeg/`, đọc 2026-10-29): "We no longer distribute reports with our corpora" nhưng cho tìm từ khoá trên báo cáo đã ẩn danh. Cách làm: gửi email tới `help@nedcdata.org` (subject "Python Script") một script Python **chỉ dùng thư viện chuẩn**, nhận danh sách tên file, NEDC chạy trên báo cáo và trả lại **danh sách file khớp**. Có ví dụ `query.tar.gz` trên trang. Trang không nêu phiên bản nào có báo cáo, không có ví dụ từ khoá/ICD, và không nêu điều khoản DUA về báo cáo.
- **Hệ quả:** làm được bước từ khoá của Peterson, nhưng **không thể duyệt tay báo cáo** như họ đã làm, vì bạn không nhận được báo cáo. Nhãn sẽ nhiễu hơn (phủ định "no infarct", "history of stroke", tiền sử). Phải dựng regex xử lý phủ định, ước lượng độ chính xác bằng tập nhỏ có nhãn, và gọi đây là weak label.
- **Chưa làm:** gửi email (là việc của bạn, mình không gửi thay). Mình có thể soạn script theo kiểu TDD để bạn xem trước khi gửi. Các sub-corpus có sẵn (`tuh_eeg_abnormal`, `_slowing`, `_events`, `_artifact`) chỉ cho nhãn bất thường/làm chậm, không phải IS. Cách chạy rsync trên Windows nay là MSYS2 (xem memory `reference_tuh_rsync_windows.md`).

**Chatterjee (conformal, AIME 2026):** dữ liệu lệch theo bệnh nhân làm vỡ độ phủ conformal chuẩn; calibration cá nhân hoá tăng coverage hơn 20 điểm phần trăm (theo abstract). Bài nói về seizure và tập dự đoán, không phải abstention. Tên các phương pháp và dataset **chưa đọc**. Một công thức CRC có abstain cho lệch theo bệnh nhân có vẻ chưa ai làm, nhưng đó là kết luận từ một lượt tìm, chưa phải khẳng định.

**Không tìm thấy:** dataset công khai nào có stroke cấp + control cùng thiết bị (năm 2026 cũng không). Không có bài nào về shortcut learning riêng cho EEG stroke. Có một bài GRU–TCN (arXiv 2025) báo hiệu năng giảm trên cohort ngoài mật độ thấp, ghi là do thiết bị/montage (chưa đọc).
