"""Weekly report generation (PDF via reportlab) + SendGrid email delivery."""
from __future__ import annotations

import io
import logging
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import REPO_ROOT, get_settings
from ..models import Alert, EEGSession, EmergencyContact, Patient, WeeklyReport

logger = logging.getLogger("neuratriage.report")

REPORTS_DIR = REPO_ROOT / "data" / "reports"


# ─── helpers ──────────────────────────────────────────────────────────────────

def _week_bounds(week_start: date) -> tuple[datetime, datetime]:
    start = datetime(week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc)
    end = start + timedelta(days=7)
    return start, end


# ─── data aggregation ─────────────────────────────────────────────────────────

def _aggregate(db: Session, patient_id: str, week_start: date) -> dict:
    start, end = _week_bounds(week_start)

    sessions = (
        db.execute(
            select(EEGSession)
            .where(EEGSession.patient_id == patient_id)
            .where(EEGSession.started_at >= start)
            .where(EEGSession.started_at < end)
        )
        .scalars()
        .all()
    )

    session_ids = [s.id for s in sessions]
    alerts: list[Alert] = []
    if session_ids:
        alerts = (
            db.execute(
                select(Alert)
                .where(Alert.session_id.in_(session_ids))
                .order_by(Alert.created_at)
            )
            .scalars()
            .all()
        )

    sqi_values = [s.sqi_mean for s in sessions if s.sqi_mean is not None]
    ack_count = sum(1 for a in alerts if a.acknowledged)
    esc_count = sum(1 for a in alerts if not a.acknowledged and not a.dismissed)

    return {
        "sessions": sessions,
        "alerts": alerts,
        "session_count": len(sessions),
        "alert_count": len(alerts),
        "ack_count": ack_count,
        "escalation_count": esc_count,
        "sqi_mean": sum(sqi_values) / len(sqi_values) if sqi_values else None,
        "total_duration_sec": sum(s.duration_sec or 0 for s in sessions),
    }


# ─── email delivery ───────────────────────────────────────────────────────────

def _send_email(
    recipients: list[str],
    patient_name: str,
    week_label: str,
    pdf_bytes: bytes,
    agg: dict,
) -> None:
    settings = get_settings()
    if not settings.sendgrid_api_key:
        logger.warning("SENDGRID_API_KEY not set — skipping email send")
        return

    import base64
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import (
        Attachment, Disposition, FileContent, FileName, FileType, Mail,
    )

    subject = f"[NeuraTriage] Báo cáo EEG {week_label} — {patient_name}"
    sqi_str = f"{agg['sqi_mean']:.3f}" if agg["sqi_mean"] else "N/A"
    body_html = (
        f"<h2>NeuraTriage EEG — Báo cáo tuần {week_label}</h2>"
        f"<p>Bệnh nhân: <b>{patient_name}</b></p>"
        f"<ul>"
        f"<li>Số phiên: {agg['session_count']}</li>"
        f"<li>Cảnh báo: {agg['alert_count']} (đã ack: {agg['ack_count']})</li>"
        f"<li>SQI trung bình: {sqi_str}</li>"
        f"</ul>"
        f"<p>Chi tiết đính kèm dưới dạng PDF.</p>"
    )

    encoded = base64.b64encode(pdf_bytes).decode()
    attachment = Attachment(
        FileContent(encoded),
        FileName(f"neuratriage_{week_label.replace(' · ', '_')}.pdf"),
        FileType("application/pdf"),
        Disposition("attachment"),
    )

    sg = SendGridAPIClient(settings.sendgrid_api_key)
    for recipient in recipients:
        msg = Mail(
            from_email=(settings.sendgrid_from_email, settings.sendgrid_from_name),
            to_emails=recipient,
            subject=subject,
            html_content=body_html,
        )
        msg.attachment = attachment
        try:
            sg.send(msg)
            logger.info("Report email sent to %s", recipient)
        except Exception as exc:
            logger.error("SendGrid error for %s: %s", recipient, exc)
            raise


# ─── public API ───────────────────────────────────────────────────────────────

# Unicode-safe week label + PDF builder used by generate_and_save.
def _week_label(week_start: date) -> str:
    iso = week_start.isocalendar()
    return f"W{iso[1]:02d} - {iso[0]}"


def _build_pdf(patient: Patient, week_start: date, agg: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    def register_font() -> tuple[str, str]:
        regular_candidates = [
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        ]
        bold_candidates = [
            Path("C:/Windows/Fonts/arialbd.ttf"),
            Path("C:/Windows/Fonts/segoeuib.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        ]
        regular = next((p for p in regular_candidates if p.is_file()), None)
        bold = next((p for p in bold_candidates if p.is_file()), None)
        if not regular:
            return "Helvetica", "Helvetica-Bold"
        try:
            pdfmetrics.registerFont(TTFont("NTUnicode", str(regular)))
            if bold:
                pdfmetrics.registerFont(TTFont("NTUnicode-Bold", str(bold)))
                return "NTUnicode", "NTUnicode-Bold"
            return "NTUnicode", "NTUnicode"
        except Exception as exc:
            logger.warning("Could not register Unicode PDF font: %s", exc)
            return "Helvetica", "Helvetica-Bold"

    def text(value, default: str = "—") -> str:
        if value is None:
            return default
        value = str(value).strip()
        return value if value else default

    def para(value, style):
        return Paragraph(escape(text(value)), style)

    font_name, bold_font_name = register_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("nt_title", parent=styles["Heading1"], fontName=bold_font_name, fontSize=16, spaceAfter=6)
    sub_style = ParagraphStyle("nt_sub", parent=styles["Normal"], fontName=font_name, fontSize=10, textColor=colors.grey, spaceAfter=12)
    h2_style = ParagraphStyle("nt_h2", parent=styles["Heading2"], fontName=bold_font_name, fontSize=12, spaceBefore=12)
    body_style = ParagraphStyle("nt_body", parent=styles["Normal"], fontName=font_name, fontSize=9.5, leading=13)
    small_style = ParagraphStyle("nt_small", parent=body_style, fontSize=8, leading=10, textColor=colors.grey)
    cell_style = ParagraphStyle("nt_cell", parent=body_style, fontSize=8.5, leading=11)

    week_label = _week_label(week_start)
    dur_h = int(agg["total_duration_sec"] // 3600)
    dur_m = int((agg["total_duration_sec"] % 3600) // 60)
    dx = patient.diagnosis_history if isinstance(patient.diagnosis_history, dict) else {}
    vitals = dx.get("vitals") if isinstance(dx.get("vitals"), dict) else {}

    story = [
        Paragraph("NeuraTriage EEG - Báo cáo tuần", title_style),
        Paragraph(
            f"Bệnh nhân: <b>{escape(text(patient.full_name))}</b> &nbsp;·&nbsp; "
            f"Tuần: <b>{escape(week_label)}</b> &nbsp;·&nbsp; "
            f"Ngày tạo: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            sub_style,
        ),
        Spacer(1, 0.25 * cm),
        Paragraph("1. Thông tin bệnh nhân", h2_style),
    ]

    patient_rows = [
        ["Trường", "Giá trị"],
        ["Họ tên", patient.full_name],
        ["MRN", patient.mrn],
        ["Giường", patient.bed],
        ["Giới tính", patient.gender],
        ["Onset", f"{patient.onset_minutes} phút trước" if patient.onset_minutes is not None else None],
        ["Lý do vào viện", dx.get("chief_complaint")],
        ["Triệu chứng", dx.get("symptoms")],
        ["Tiền sử bệnh", dx.get("medical_history")],
        ["Thuốc đang dùng", dx.get("medications")],
        ["Dị ứng", dx.get("allergies")],
        ["Huyết áp", vitals.get("blood_pressure")],
        ["Nhịp tim", f"{vitals.get('heart_rate')} bpm" if vitals.get("heart_rate") is not None else None],
        ["SpO2", f"{vitals.get('spo2')}%" if vitals.get("spo2") is not None else None],
        ["Nhiệt độ", f"{vitals.get('temperature')} °C" if vitals.get("temperature") is not None else None],
        ["Đường huyết", vitals.get("glucose")],
        ["NIHSS", dx.get("nihss")],
        ["Ghi chú", patient.notes],
    ]

    def make_table(rows, col_widths, header_bg="#1a1a2e", stripe="#f7f9fb"):
        table = Table([[para(c, cell_style) for c in row] for row in rows], colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), bold_font_name),
            ("FONTNAME", (0, 1), (-1, -1), font_name),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(stripe)]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table

    story.append(make_table(patient_rows, [4.2 * cm, 11.8 * cm]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("2. Tổng quan tuần", h2_style))
    story.append(make_table([
        ["Chỉ số", "Giá trị"],
        ["Số phiên EEG", str(agg["session_count"])],
        ["Tổng thời gian theo dõi", f"{dur_h}h {dur_m}m"],
        ["Tổng cảnh báo", str(agg["alert_count"])],
        ["Đã xác nhận (ack)", str(agg["ack_count"])],
        ["Chưa xử lý (escalation)", str(agg["escalation_count"])],
        ["SQI trung bình", f"{agg['sqi_mean']:.3f}" if agg["sqi_mean"] is not None else "—"],
    ], [8 * cm, 8 * cm], stripe="#f5f5f5"))
    story.append(Spacer(1, 0.45 * cm))

    story.append(Paragraph("3. Chi tiết cảnh báo", h2_style))
    if not agg["alerts"]:
        story.append(Paragraph("Không có cảnh báo nào trong tuần này.", body_style))
    else:
        alert_rows = [["Thời gian", "Loại", "Xác suất", "SQI", "Trạng thái"]]
        for alert in agg["alerts"]:
            probs = alert.probabilities_smooth or [0, 0, 0]
            max_p = max(probs) if probs else 0
            status = "Đã ack" if alert.acknowledged else ("Đã bỏ qua" if alert.dismissed else "Chờ xử lý")
            alert_rows.append([
                alert.created_at.strftime("%m-%d %H:%M") if alert.created_at else "—",
                alert.alert_class.upper(),
                f"{max_p:.2f}",
                f"{alert.sqi_total:.2f}" if alert.sqi_total is not None else "—",
                status,
            ])
        story.append(make_table(alert_rows, [3.5 * cm, 3 * cm, 2.5 * cm, 2.5 * cm, 4.5 * cm], stripe="#fff3f3"))
        story.append(Spacer(1, 0.45 * cm))

    story.append(Paragraph("4. Khuyến nghị vận hành", h2_style))
    if agg["escalation_count"] > 0:
        rec = (
            f"<b>Cần chú ý:</b> Có {agg['escalation_count']} cảnh báo chưa được xử lý. "
            "Vui lòng xem lại trong hệ thống NeuraTriage và xác nhận theo quy trình nội bộ."
        )
    else:
        rec = "Tất cả cảnh báo đã được xử lý. Tiếp tục theo dõi theo lịch thường quy."
    story.append(Paragraph(rec, body_style))
    story.append(Spacer(1, 0.7 * cm))
    story.append(Paragraph(
        "Báo cáo này được tạo tự động bởi nguyên mẫu nghiên cứu NeuraTriage EEG. "
        "Kết quả chỉ hỗ trợ sàng lọc/nghiên cứu, không thay thế chẩn đoán lâm sàng, CT/MRI hoặc quyết định của bác sĩ.",
        small_style,
    ))

    doc.build(story)
    return buf.getvalue()


def generate_and_save(
    db: Session,
    patient_id: str,
    week_start: date,
    send_email: bool = True,
) -> WeeklyReport:
    """Generate PDF, persist to disk, send email, save record to DB."""
    patient = db.execute(
        select(Patient).where(Patient.id == patient_id)
    ).scalar_one_or_none()
    if not patient:
        raise ValueError(f"Patient {patient_id} not found")

    agg = _aggregate(db, patient_id, week_start)
    week_label = _week_label(week_start)
    pdf_bytes = _build_pdf(patient, week_start, agg)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_filename = f"report_{patient_id}_{week_start.isoformat()}.pdf"
    pdf_path = REPORTS_DIR / pdf_filename
    pdf_path.write_bytes(pdf_bytes)

    contacts = (
        db.execute(
            select(EmergencyContact)
            .where(EmergencyContact.patient_id == patient_id)
            .where(EmergencyContact.notify_weekly_report.is_(True))
        )
        .scalars()
        .all()
    )
    recipient_emails = [c.email for c in contacts if c.email]

    email_error: Optional[str] = None
    email_attempted = bool(
        send_email and recipient_emails and get_settings().sendgrid_api_key
    )
    if send_email and recipient_emails:
        try:
            _send_email(recipient_emails, patient.full_name, week_label, pdf_bytes, agg)
        except Exception as exc:
            email_error = str(exc)
            logger.error("Email delivery failed: %s", exc)

    if not send_email:
        status = "pdf_only"
    elif email_error:
        status = "failed"
    elif email_attempted:
        status = "sent"
    elif recipient_emails:
        status = "email_disabled"
    else:
        status = "no_recipients"

    report = WeeklyReport(
        patient_id=patient_id,
        patient_name=patient.full_name,
        week_start=week_start.isoformat(),
        week_label=week_label,
        session_count=agg["session_count"],
        alert_count=agg["alert_count"],
        ack_count=agg["ack_count"],
        escalation_count=agg["escalation_count"],
        sqi_mean=agg["sqi_mean"],
        pdf_path=str(pdf_path),
        pdf_size_bytes=len(pdf_bytes),
        status=status,
        recipient_emails=recipient_emails,
        sent_at=datetime.now(timezone.utc) if status == "sent" else None,
        error_message=email_error,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
