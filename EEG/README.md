# NeuraTriage EEG — frontend

Project frontend cho hệ thống cảnh báo sớm đột quỵ qua EEG. Chạy bằng React 18 +
Babel standalone (in-browser JSX) — không cần build step.

## Cấu trúc

```
NeuraTriage EEG.html      ← entry point (mở file này)
tokens.css                ← design tokens (màu, font, spacing)
i18n.js                   ← chuỗi đa ngôn ngữ VI/EN (window.I18N)
design-canvas.jsx         ← khung "artboard" hiển thị nhiều màn hình cùng lúc
eeg-waveform.jsx          ← generator + renderer sóng EEG
visualizations.jsx        ← biểu đồ phụ trợ (RiskBars, BandPower, MFDFA, …)
app-shell.jsx             ← sidebar + topbar layout
screens/
  live-monitor-a.jsx      ← màn theo dõi trực tiếp — biến thể A
  live-monitor-b.jsx      ← biến thể B (risk-first)
  live-monitor-c.jsx      ← biến thể C (research console)
  device-screen.jsx       ← màn kết nối thiết bị
  other-screens.jsx       ← dashboard / patient / alerts / setup / insights / reports / settings
```

## Cách chạy

**Không double-click file HTML** — trình duyệt sẽ chặn fetch các file `.jsx`
qua giao thức `file://` (CORS). Phải mở qua local server.

### Cách 1 — Python (sẵn có trên macOS / Linux / Windows)

```bash
cd "đường/dẫn/tới/folder/này"
python3 -m http.server 8000
```

Rồi mở trình duyệt: <http://localhost:8000/NeuraTriage%20EEG.html>

### Cách 2 — VS Code Live Server

Cài extension **Live Server**, click chuột phải vào `NeuraTriage EEG.html`
→ *Open with Live Server*.

### Cách 3 — Node (nếu đã cài Node)

```bash
npx serve .
```

## Lưu ý

- File HTML có dấu cách trong tên → URL phải encode `%20`. Bạn có thể đổi
  tên thành `index.html` để khỏi gõ.
- Babel parse JSX trong trình duyệt nên lần load đầu hơi chậm (~1–2s).
  Khi muốn deploy production thật, nên migrate sang Vite để pre-compile.
- Tất cả components expose qua `window.*` (vd `window.AppShell`,
  `window.EEGStack`) — không dùng ES modules. Nếu thêm component mới, nhớ
  gán vào `window` để các file khác thấy được.
