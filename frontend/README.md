# NeuraTriage EEG — Frontend

Giao diện cho hệ thống cảnh báo sớm đột quỵ qua EEG. Chạy bằng **React 18 +
Babel standalone** (in-browser JSX) — không cần build step.

## Cấu trúc

```
frontend/
├── index.html               ← entry point (Vercel serves this)
├── styles/
│   └── tokens.css           ← design tokens + login styles + utility classes
├── lib/
│   └── i18n.js              ← chuỗi đa ngôn ngữ VI/EN (window.I18N)
├── components/
│   ├── app-shell.jsx        ← sidebar + topbar layout (window.AppShell)
│   ├── eeg-waveform.jsx     ← generator + renderer sóng EEG
│   ├── visualizations.jsx   ← biểu đồ phụ trợ (RiskBars, BandPower, MFDFA…)
│   └── design-canvas.jsx    ← (legacy) khung artboard cho design exploration
└── screens/
    ├── login-screen.jsx     ← giao diện đăng nhập (hiện trước app)
    ├── live-monitor-a.jsx   ← màn theo dõi trực tiếp — biến thể A (Split)
    ├── live-monitor-b.jsx   ← biến thể B (Risk-first)
    ├── live-monitor-c.jsx   ← biến thể C (Research console)
    ├── device-screen.jsx    ← màn kết nối thiết bị
    └── other-screens.jsx    ← dashboard / patient / alerts / setup / insights / reports / settings
```

## Luồng app

1. Người dùng mở `index.html` → render `<LoginScreen>` (vì chưa có
   `localStorage.neuratriage_auth`).
2. Điền form (email + mật khẩu + role + layout) hoặc nhấn **demo mode** →
   `Root()` lưu user vào `localStorage` và chuyển sang `<AppFrame>`.
3. `AppFrame` render `<AppShell>` (sidebar nav) + 1 màn theo lựa chọn
   variant (A/B/C) cho Live Monitor.
4. Floating `<UserPill>` ở top-right hiển thị email + role + nút **Sign out**.
5. Sign out xoá `localStorage` → quay lại `<LoginScreen>`.

## Cách chạy local

**Không double-click file HTML** — trình duyệt chặn fetch `.jsx` qua
`file://` (CORS). Phải mở qua local server.

```bash
# Trong folder frontend/:
python -m http.server 8000
```

Rồi mở: <http://localhost:8000/>

Hoặc VS Code **Live Server**, hoặc `npx serve .`

## Production

Đã setup deploy lên **Vercel** qua `vercel.json` ở repo root
(`outputDirectory: "frontend"`). Mỗi lần `git push` → Vercel auto-redeploy.

## Lưu ý kỹ thuật

- Babel parse JSX trong trình duyệt → lần load đầu hơi chậm (~1–2s).
  Migrate sang Vite/Next.js khi muốn ship production tốc độ thật.
- Tất cả components expose qua `window.*` (vd `window.AppShell`,
  `window.LoginScreen`) — không dùng ES modules. Thêm component mới nhớ
  gán vào `window` để các file khác thấy.
- Auth hiện chỉ là **mock** (lưu vào `localStorage`, không có server).
  Khi tích hợp backend Flask (xem `../backend/`), thay `handleLogin` trong
  `index.html` bằng fetch tới API thật.
