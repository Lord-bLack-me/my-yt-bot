import os
import time
import asyncio
import re
import shutil
import logging
import requests
from datetime import datetime

# Environment for OAuth
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Telegram & Utils
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

# Downloading
import yt_dlp

# Google Drive Integration
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- CONFIGURATION ---
STORAGE_DIR = "." 
TOKEN = "7735000998:AAHGMHhMx1bdapB05XUEfFBreZ2jrxDN1_s"
SCOPES = ['https://www.googleapis.com/auth/drive.file']
STORAGE_DIR = "downloads"
start_time = time.time()
cloud_stats = {"total_uploads": 0, "total_size": 0}

# --- UTILS ---
def format_bytes(size):
    if not size: return "0B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"

# --- GOOGLE DRIVE AUTH ---
def get_drive_service():
    creds = None
    token_path = 'token.json'
    creds_path = 'credentials.json'

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES, redirect_uri='http://localhost:8080/')
            auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
            print(f"\n🔗 AUTH LINK: {auth_url}\n")
            response_url = input("👉 Paste FULL redirect URL: ").strip()
            flow.fetch_token(authorization_response=response_url)
            creds = flow.credentials
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

# --- DRIVE ENGINE ---
async def upload_to_drive(file_path, file_name):
    loop = asyncio.get_running_loop()
    def _upload():
        service = get_drive_service()
        file_metadata = {'name': file_name}
        media = MediaFileUpload(file_path, resumable=True, chunksize=10*1024*1024)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        f_id = file.get('id')
        service.permissions().create(fileId=f_id, body={'type': 'anyone', 'role': 'reader'}).execute()
        return service.files().get(fileId=f_id, fields='webContentLink').execute(), f_id

    file_data, file_id = await loop.run_in_executor(None, _upload)
    cloud_stats["total_uploads"] += 1
    cloud_stats["total_size"] += os.path.getsize(file_path)
    return file_data.get('webContentLink'), file_id

async def auto_delete_drive_file(file_id, delay=3600):
    await asyncio.sleep(delay)
    try:
        loop = asyncio.get_running_loop()
        service = get_drive_service()
        await loop.run_in_executor(None, lambda: service.files().delete(fileId=file_id).execute())
    except: pass

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (f"👋 <b>Namaste! Gemini Hybrid Ultra Engine</b>\n\n"
            "🚀 <b>Status:</b> Online & Optimized\n"
            "⚡ <b>Max Speed:</b> Unlimited\n"
            "☁️ <b>Cloud:</b> Enabled (>2GB Support)\n\n"
            "/ping | /stats | /cloud | /clean | /sysinfo")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = time.strftime("%Hh %Mm %Ss", time.gmtime(time.time() - start_time))
    await update.message.reply_text(f"📊 <b>SYSTEM REPORT:</b>\n⏱ Uptime: {uptime}\n⚙️ Status: Ultra-Stable", parse_mode=ParseMode.HTML)

async def sysinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = ("🛠 <b>Technical Specs:</b>\n\n"
            "🔹 Core: yt-dlp Private Build\n"
            "🔹 Cloud: Google Drive API v3\n"
            "🔹 Buffering: 10MB Resumable Chunks\n"
            "🔹 Timeout: 3600s Extended")
    await update.message.reply_text(info, parse_mode=ParseMode.HTML)

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = time.time()
    m = await update.message.reply_text("⚡")
    ms = round((time.time() - s) * 1000)
    await m.edit_text(f"🚀 <b>Latency:</b> <code>{ms}ms</code>", parse_mode=ParseMode.HTML)

async def clean_drive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🧹 <b>Cleaning Drive...</b>", parse_mode=ParseMode.HTML)
    try:
        service = get_drive_service()
        results = service.files().list(pageSize=100).execute()
        files = results.get('files', [])
        if not files: return await msg.edit_text("✅ Drive is already clean!")
        for f in files: service.files().delete(fileId=f['id']).execute()
        await msg.edit_text(f"🗑 <b>Deleted {len(files)} files.</b>", parse_mode=ParseMode.HTML)
    except Exception as e: await msg.edit_text(f"❌ Error: {e}")

# --- CORE LOGIC ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtu" not in url: return
    
    msg = await update.message.reply_text("🧠 <b>AI Analyzing Content...</b>", parse_mode=ParseMode.HTML)
    try:
        ydl_opts = {'quiet': True, 'nocheckcertificate': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            v_id = info['id']
            formats = info.get('formats', [])
            
            # --- DYNAMIC RESOLUTION LOGIC ---
            rows = []
            available_resolutions = []
            
            # Sabhi available heights nikalna (sirf video formats se)
            for f in formats:
                height = f.get('height')
                if height and f.get('vcodec') != 'none':
                    if height not in available_resolutions:
                        available_resolutions.append(height)
            
            # Resolutions ko bade se chote order mein sort karna
            available_resolutions.sort(reverse=True)
            
            seen_res = set()
            for res in available_resolutions:
                if res in seen_res: continue
                
                # Best format match for size estimation
                f_match = [f for f in formats if f.get('height') == res and f.get('vcodec') != 'none']
                if f_match:
                    # Sabse badi file size wala format lena for accuracy
                    best_f = max(f_match, key=lambda x: x.get('filesize') or x.get('filesize_approx') or 0)
                    size = best_f.get('filesize') or best_f.get('filesize_approx')
                    size_str = format_bytes(size) if size else "N/A"
                    
                    rows.append(InlineKeyboardButton(f"🎬 {res}p - {size_str}", callback_data=f"dl|{res}|{v_id}"))
                    seen_res.add(res)
            # --------------------------------

            # Format Keyboard into 1 column
            keyboard = [[btn] for btn in rows]
            
            # MP3 Size Estimation
            audio_f = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
            # Fallback size handle karna agar audio format na mile
            mp3_size = None
            if audio_f:
                mp3_size = audio_f[0].get('filesize') or audio_f[0].get('filesize_approx')
            mp3_str = format_bytes(mp3_size) if mp3_size else "7MB"
            
            keyboard.append([InlineKeyboardButton(f"🎵 MP3 Audio - {mp3_str}", callback_data=f"dl|mp3|{v_id}")])
            keyboard.append([InlineKeyboardButton("☁️ Cloud Upload (Original Quality)", callback_data=f"dl|cloud|{v_id}")])

            await msg.delete()
            caption = (f"📹 <b>{info['title']}</b>\n"
                       f"⏱ Duration: {info.get('duration_string')}\n"
                       f"👁 {info.get('view_count', 0):,} | 👍 {info.get('like_count', 0):,}\n\n"
                       f"<b>Formats for Download ⤵️</b>")
            
            await update.message.reply_photo(
                photo=info['thumbnail'], 
                caption=caption, 
                reply_markup=InlineKeyboardMarkup(keyboard), 
                parse_mode=ParseMode.HTML
            )
    except Exception as e: await msg.edit_text(f"❌ Analysis Error: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Engine Starting...")
    _, quality, v_id = query.data.split("|")
    url = f"https://www.youtube.com/watch?v={v_id}"
    
    file_path = ""
    try:
        await query.message.edit_caption(caption="⏳ <b>Initializing Turbo Engine...</b>", parse_mode=ParseMode.HTML)
        
        # Download Thumb
        thumb_path = f"{STORAGE_DIR}/thumb_{v_id}.jpg"
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            r = requests.get(info['thumbnail'])
            with open(thumb_path, 'wb') as f: f.write(r.content)

        ydl_opts = {
            'outtmpl': f'{STORAGE_DIR}/{v_id}_%(title)s.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': True, 'nocheckcertificate': True,
            'max_filesize': 2000*1024*1024 # 2GB limit for TG
        }
        
        if quality == "mp3":
            ydl_opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]})
        elif quality == "cloud":
            ydl_opts.update({'format': 'bestvideo+bestaudio/best'})
        else:
            ydl_opts.update({'format': f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}]'})

        await query.message.edit_caption(caption="📥 <b>Status:</b> Downloading data from YouTube...", parse_mode=ParseMode.HTML)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])
            file_path = ydl.prepare_filename(info)
            if quality == "mp3": file_path = file_path.rsplit('.', 1)[0] + ".mp3"
            elif not os.path.exists(file_path): 
                file_path = file_path.rsplit('.', 1)[0] + ".mp4"

        file_size_mb = os.path.getsize(file_path) / (1024*1024)

        if quality == "cloud" or file_size_mb > 1950:
            await query.message.edit_caption(caption="☁️ <b>Target: Cloud.</b> Uploading to Google Drive...", parse_mode=ParseMode.HTML)
            link, d_id = await upload_to_drive(file_path, info['title'])
            btn = [[InlineKeyboardButton("🖥 Open Stream / Download", url=link)]]
            await query.message.reply_text(f"✅ <b>Cloud Delivery Ready!</b>\n\n📦 <b>{info['title']}</b>\n📏 Size: {format_bytes(os.path.getsize(file_path))}", reply_markup=InlineKeyboardMarkup(btn), parse_mode=ParseMode.HTML)
            asyncio.create_task(auto_delete_drive_file(d_id))
        else:
            await query.message.edit_caption(caption="📤 <b>Status:</b> Sending file to Telegram...", parse_mode=ParseMode.HTML)
            with open(file_path, 'rb') as f:
                thumb = open(thumb_path, 'rb') if os.path.exists(thumb_path) else None
                if quality == "mp3": 
                    await context.bot.send_audio(query.message.chat_id, f, title=info['title'], thumbnail=thumb, connect_timeout=1000, read_timeout=1000, write_timeout=1000)
                else: 
                    await context.bot.send_video(query.message.chat_id, f, caption=f"✅ {info['title']}", supports_streaming=True, thumbnail=thumb, connect_timeout=1000, read_timeout=1000, write_timeout=1000)
                if thumb: thumb.close()

        await query.message.delete()
    except Exception as e: 
        await query.message.reply_text(f"❌ <b>Critical Error:</b> {e}")
    finally:
        if file_path and os.path.exists(file_path): os.remove(file_path)
        if 'thumb_path' in locals() and os.path.exists(thumb_path): os.remove(thumb_path)

# --- MAIN ---
def main():
    if not os.path.exists(STORAGE_DIR): os.makedirs(STORAGE_DIR)
    
    # Extreme Timeout Configuration to prevent "Timed Out" errors
    req = HTTPXRequest(connect_timeout=600, read_timeout=3600, write_timeout=3600, pool_timeout=600)
    
    app = Application.builder().token(TOKEN).request(req).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("cloud", lambda u, c: u.message.reply_text(f"☁️ <b>Cloud Stats:</b>\nUploads: {cloud_stats['total_uploads']}\nSize: {format_bytes(cloud_stats['total_size'])}", parse_mode=ParseMode.HTML)))
    app.add_handler(CommandHandler("clean", clean_drive))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("sysinfo", sysinfo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 Gemini Heavy Engine Online. Extreme Timeouts Enabled.")
    app.run_polling()

if __name__ == "__main__":
    main()

