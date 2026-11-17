# Kịch bản video demo (UIST 2027)

_Bản nháp 2026-11-17. Hai bản: **video chính** (khoảng 2 phút 30) và **video preview 30 giây**. Kiểm tra độ dài và định dạng trong CFP của UIST 2027 trước khi dựng; thường là MP4 H.264, có phụ đề. Bản nộp phải **ẩn danh**: không tên người, trường, logo, URL GitHub, không lộ mặt người tham gia study._

## Nguyên tắc

- **Chỉ quay tín hiệu thật.** Màn hình lấy từ app đang chạy: headband thật, hoặc phát lại bản ghi thật. Không dựng hình giả. Nếu dùng nút chèn nhiễu của demo, ghi rõ trên hình *"simulated artifact"*.
- **Không hiện điểm rủi ro của ca nằm trong dữ liệu train như bằng chứng.** Cảnh quyết định dùng màn hình No-Decision và màn hình kết quả Study 2.
- Lời thoại tiếng Anh (paper tiếng Anh), phụ đề cứng. Giọng đọc: [người trong nhóm hoặc TTS].
- Người đeo trong video là thành viên nhóm đã đồng ý quay, **không phải người tham gia study**. Khi nộp ẩn danh thì che mặt hoặc quay từ sau và bên.

## Video chính (khoảng 2:30)

| # | Thời gian | Hình | Lời thoại / phụ đề |
|---|---|---|---|
| 1 | 0:00–0:12 | Xe cấp cứu hoặc ảnh minh hoạ trung tính; chữ: *"1 in 3 prehospital EEG recordings were unusable"* (ELECTRA-STROKE) | "EEG could help route suspected stroke patients, but in the ambulance a third of recordings are unusable." |
| 2 | 0:12–0:25 | Tay người đo đặt headband 2 kênh lên trán người đeo; màn hình chỉ báo chất lượng (điều kiện B): một kênh "Poor" | "A quality bar tells you *something* is wrong. It does not tell you what to do." |
| 3 | 0:25–0:50 | Điều kiện G, headband thật, điện cực AF3 khô. Panel: *"FIX THIS — AF3 — Baseline drift: press the electrode firmly or re-wet it."* Người đo làm ướt điện cực, thanh AF3 chuyển xanh | "Our interface scores every channel every second, names the electrode, the reason, and one action." |
| 4 | 0:50–1:05 | Người đeo cắn hàm theo hiệu lệnh → panel *"Muscle noise: ask the patient to relax the jaw"* → thả lỏng → hết | "Each reason maps to a fix a non-expert can do." |
| 5 | 1:05–1:20 | Chữ trên nền trơn: *"Stroke slows the EEG. A quality check must not call that bad contact."* + hình nhỏ: E9 (stroke 0.3% vs. control 15.7% windows withheld) | "The quality check is built so that stroke-like slowing is never penalised. A score we learned from artifact labels failed exactly this test, so we did not ship it." |
| 6 | 1:20–1:45 | Sơ đồ từ teaser (nửa phải): Acquire → Decide → Alert / Clear / No-Decision | "Then the system decides per patient, with a conformal rule calibrated on site: false alerts stay below the target, even on recording sources it has never seen." |
| 7 | 1:45–2:05 | Màn hình Study 2: `nd_plain.png` rồi `nd_action_quality.png` cạnh nhau | "When it cannot decide, it says so — and says what that means: not normal, keep the stroke pathway, re-measure after fixing AF4." |
| 8 | 2:05–2:20 | Kết quả Study 1 (biểu đồ TTU B vs. G) và Study 2 (tỉ lệ kích hoạt). **Chờ có số liệu** | [Một câu kết quả mỗi study] |
| 9 | 2:20–2:30 | Tiêu đề paper, không tên tác giả | "Know when to measure again." |

## Video preview (30 giây)

| Thời gian | Hình | Phụ đề |
|---|---|---|
| 0–8 s | Cảnh 3 rút gọn: panel chỉ AF3, người đo sửa, thanh chuyển xanh | *Which electrode. Why. What to do.* |
| 8–18 s | Cảnh 6 rút gọn: Alert / Clear / No-Decision | *A decision with a guarantee — or an honest No-Decision.* |
| 18–26 s | Cảnh 7: màn hình No-Decision có hành động | *"Not normal. Keep the stroke pathway."* |
| 26–30 s | Tiêu đề | *Know When to Measure Again* |

## Cách quay màn hình

- **Headband thật (cảnh 3, 4):** chạy backend (`neuratriage-backend` trong `.claude/launch.json`), mở `app.html?participant=P99&condition=G&trial=1&source=device`. Mã `P99` chỉ dùng để quay; xoá log `data/study_logs/P99.jsonl` và file raw tương ứng sau khi quay.
- **Điều kiện B (cảnh 2):** cùng URL với `condition=B`.
- **Phát lại (nếu không có headband):** `source=replay`, ghi chú *"replayed clinical recording"* trên hình.
- Quay ở 1440×900, tỉ lệ thiết bị 2 (rõ chữ). Giao diện tiếng Anh: chọn ngôn ngữ trong menu avatar.
- Hình tĩnh có sẵn: `figures/uist2027/fig_teaser.png`, `docs/study2/screens/*.png`.

## Việc cần làm

- [ ] Kiểm tra quy định video trong CFP UIST 2027 (độ dài, dung lượng, phụ đề)
- [ ] Quay cảnh 2–4 với headband thật (cần thiết bị và một người đeo trong nhóm)
- [ ] Thu lời thoại, dựng, phụ đề
- [ ] Thêm cảnh 8 khi có kết quả hai study
- [ ] Kiểm tra ẩn danh trước khi nộp
