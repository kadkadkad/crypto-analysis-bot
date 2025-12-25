# app.py - Gerçek YouTube Rapor Botu
import streamlit as st
from youtubesearchpython import VideosSearch
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
import google.generativeai as genai
from dotenv import load_dotenv
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io

# .env dosyasından anahtarları al
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

st.set_page_config(page_title="YouTube Rapor Botu", page_icon="📺", layout="centered")
st.title("📺 YouTube Günlük Rapor Botu")
st.markdown("### İstediğin kanalların son videolarını özetleyip mailine atar!")

# Kanal ekleme
if "channels" not in st.session_state:
    st.session_state.channels = []

col1, col2 = st.columns([4, 1])
with col1:
    new_channel = st.text_input("Kanal adı ekle (örneğin: DataDash, Barış Özcan)")
with col2:
    if st.button("Ekle"):
        if new_channel.strip():
            st.session_state.channels.append(new_channel.strip())
            st.success(f"✅ {new_channel} eklendi!")

if st.session_state.channels:
    st.write("### Takip edilen kanallar:")
    for ch in st.session_state.channels:
        st.write(f"• {ch}")

def get_latest_video(channel_name):
    try:
        search = VideosSearch(f"from:{channel_name}", limit=1)
        result = search.result()
        if result['result']:
            video = result['result'][0]
            return video['id'], video['title'], f"https://www.youtube.com/watch?v={video['id']}"
    except:
        pass
    return None, "Video bulunamadı", ""

def get_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=('tr', 'en'))
        return " ".join([t['text'] for t in transcript])
    except NoTranscriptFound:
        return "Altyazı bulunamadı"
    except:
        return "Altyazı alınamadı"

def generate_report():
    if not st.session_state.channels:
        st.error("Önce kanal ekle!")
        return

    full_report = f"YouTube Günlük Rapor - {datetime.now().strftime('%d %B %Y')}\n\n"
    model = genai.GenerativeModel('gemini-1.5-flash')

    for channel in st.session_state.channels:
        video_id, title, url = get_latest_video(channel)
        if video_id:
            transcript = get_transcript(video_id)
            if "bulunamadı" not in transcript.lower() and len(transcript) > 100:
                summary = model.generate_content(f"Bu videoyu Türkçe 4-5 madde özetle:\n{transcript[:30000]}").text
            else:
                summary = transcript

            full_report += f"📺 {channel}\n"
            full_report += f"🎥 {title}\n"
            full_report += f"🔗 {url}\n"
            full_report += f"📝 {summary}\n\n---\n\n"
        else:
            full_report += f"❌ {channel} - Son video bulunamadı\n\n"

    # PDF oluştur
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height-80, "YouTube Günlük Rapor")
    c.setFont("Helvetica", 11)
    y = height - 130
    for line in full_report.split('\n'):
        if y < 50:
            c.showPage()
            y = height - 50
        c.drawString(50, y, line[:100])
        y -= 15
    c.save()
    buffer.seek(0)

    # Mail gönder
    msg = MIMEMultipart()
    msg["From"] = os.getenv("EMAIL_USER")
    msg["To"] = os.getenv("EMAIL_TO")
    msg["Subject"] = f"YouTube Rapor • {datetime.now().strftime('%d.%m.%Y')}"

    html_body = full_report.replace('\n', '<br>')
    msg.attach(MIMEText(f"<pre>{html_body}</pre>", "html"))

    part = MIMEBase('application', 'octet-stream')
    part.set_payload(buffer.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment; filename="YouTube_Rapor.pdf"')
    msg.attach(part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS"))
            server.send_message(msg)
        st.success("✅ Rapor gönderildi! Mailini kontrol et")
        st.balloons()
    except Exception as e:
        st.error(f"Hata: {e}")

if st.button("🚀 GERÇEK RAPOR GÖNDER", type="primary", use_container_width=True):
    with st.spinner("Videolar çekiliyor ve özetleniyor... (30-60 saniye)"):
        generate_report()

st.info("Kanal ekle → 'GERÇEK RAPOR GÖNDER' butonuna bas → gerçek özetler mailine gelsin!")