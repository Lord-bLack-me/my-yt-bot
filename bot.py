import os
import time
import random
import asyncio
import re
import html
import shutil
import logging
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Telegram & Utils
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

# Downloading
import yt_dlp

# --- CONFIGURATION ---
TOKEN = "8473786646:AAGP6kIuhrrR4LlDgCMzbcyYC-v1sVpo1qw" # REGENERATE THIS ASAP FOR SECURITY
STORAGE_DIR = "downloads"
start_time = time.time()
download_stats = {"total_downloads": 0, "total_size": 0}
executor = ThreadPoolExecutor(max_workers=10) # Multi-thread engine

# --- UTILS ---
def format_bytes(size):
    if not size: return "0B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    text = (f"👋 <b>ᴀssᴀʟᴀᴍᴜᴀʟᴀɪᴋᴜᴍ {update.message.from_user.mention_html()} ɪ ᴀᴍ ᴢᴜɪɪ ᴘʀᴏ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ </b>\n\n"
            "🚀 <b>Status:</b> Online & Optimized\n"
            "⚡ <b>Max Speed:</b> Unlimited (Turbo Sync Enabled)\n\n"
            "/ping | /stats | /clean | /sysinfo")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = time.strftime("%Hh %Mm %Ss", time.gmtime(time.time() - start_time))
    text = (f"📊 <b>SYSTEM REPORT:</b>\n"
            f"⏱ Uptime: {uptime}\n"
            f"📥 Total Downloads: {download_stats['total_downloads']}\n"
            f"📦 Total Data Processed: {format_bytes(download_stats['total_size'])}\n"
            f"⚙️ Status: Ultra-Stable")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def sysinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = ("🛠 <b>Technical Specs:</b>\n\n"
            "🔹 Core: yt-dlp Turbo Build\n"
            "🔹 Engine: Multi-Thread Sync\n"
            "🔹 Auto-Clear: Enabled (Termux/VPS Optimized)")
    await update.message.reply_text(info, parse_mode=ParseMode.HTML)

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = time.time()
    m = await update.message.reply_text("⚡")
    ms = round((time.time() - s) * 1000)
    await m.edit_text(f"🚀 <b>Latency:</b> <code>{ms}ms</code>", parse_mode=ParseMode.HTML)

async def clean_storage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🧹 <b>Cleaning Local Storage...</b>", parse_mode=ParseMode.HTML)
    try:
        count = 0
        if os.path.exists(STORAGE_DIR):
            for file in os.listdir(STORAGE_DIR):
                file_path = os.path.join(STORAGE_DIR, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    count += 1
        await msg.edit_text(f"✅ <b>Storage Cleaned!</b> Removed {count} temporary files.", parse_mode=ParseMode.HTML)
    except Exception as e: 
        await msg.edit_text(f"❌ Error: {e}")

# --- CORE LOGIC ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtu" not in url: return
    
    msg = await update.message.reply_text("🔎", parse_mode=ParseMode.HTML)
    try:
        ydl_opts = {
            'quiet': True, 
            'nocheckcertificate': True,
            'format': 'bestvideo+bestaudio/best'
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            v_id = info['id']
            formats = info.get('formats', [])
            
            rows = []
            seen_res = set()
            
            audio_size = 0
            audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec'] == 'none']
            if audio_formats:
                best_audio = sorted(audio_formats, key=lambda x: x.get('abr') or 0, reverse=True)[0]
                audio_size = best_audio.get('filesize') or best_audio.get('filesize_approx') or 0

            for f in sorted(formats, key=lambda x: x.get('height') or 0, reverse=True):
                res = f.get('height')
                
                if res and res not in seen_res and f.get('vcodec') != 'none':
                    seen_res.add(res)
                    v_size = f.get('filesize') or f.get('filesize_approx') or 0
                    
                    if f.get('acodec') == 'none' or f.get('acodec') == None:
                        total_bytes = v_size + audio_size
                    else:
                        total_bytes = v_size

                    size_str = format_bytes(total_bytes) if total_bytes > 0 else "N/A"
                    rows.append([InlineKeyboardButton(f"🎬 {res}p - {size_str}", callback_data=f"dl|{res}|{v_id}")])

            keyboard = rows
            mp3_str = format_bytes(audio_size) if audio_size > 0 else "Audio"
            keyboard.append([InlineKeyboardButton(f"🎵 MP3 Audio - {mp3_str}", callback_data=f"dl|mp3|{v_id}")])

            await msg.delete()
            caption = (f"📹 <b>{info['title']}</b>\n"
                       f"⏱ Duration: {info.get('duration_string')}\n"
                       f"👁 {info.get('view_count', 0):,} | 👍 {info.get('like_count', 0):,}\n\n"
                       f"<b>Available Qualities ⤵️</b>")
            
            await update.message.reply_photo(
                photo=info['thumbnail'], 
                caption=caption, 
                reply_markup=InlineKeyboardMarkup(keyboard), 
                parse_mode=ParseMode.HTML
            )
    except Exception as e: 
        await msg.edit_text(f"❌ Analysis Error: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Engine Starting...")
    _, quality, v_id = query.data.split("|")
    url = f"https://www.youtube.com/watch?v={v_id}"
    
    file_path = ""
    thumb_path = ""
    try:
        await query.message.edit_caption(caption="⏳ <b>Initializing Turbo Engine...</b>", parse_mode=ParseMode.HTML)
        
        # Download Thumbnail
        thumb_path = f"{STORAGE_DIR}/thumb_{v_id}.jpg"
        with yt_dlp.YoutubeDL({'quiet': True, 'nocheckcertificate': True}) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            r = requests.get(info['thumbnail'], timeout=15)
            with open(thumb_path, 'wb') as f: f.write(r.content)

        ydl_opts = {
            'outtmpl': f'{STORAGE_DIR}/{v_id}_%(title)s.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': True, 
            'nocheckcertificate': True,
            'max_filesize': 2000*1024*1024, # 2GB Limit
            'geo_bypass': True
        }
        
        if quality == "mp3":
            ydl_opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]})
        else:
            ydl_opts.update({'format': f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}]'})

        await query.message.edit_caption(caption="📥 <b>Status:</b> Downloading Content...", parse_mode=ParseMode.HTML)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])
            temp_path = ydl.prepare_filename(info)
            if quality == "mp3": 
                file_path = os.path.splitext(temp_path)[0] + ".mp3"
            else:
                actual_path = os.path.splitext(temp_path)[0] + ".mp4"
                file_path = actual_path if os.path.exists(actual_path) else temp_path

        if not os.path.exists(file_path):
            raise Exception("File Download Failed - Path not found.")

        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024*1024)

        # Update stats
        download_stats["total_downloads"] += 1
        download_stats["total_size"] += file_size

        await query.message.edit_caption(caption=f"📤 <b>Size: {file_size_mb:.2f}MB</b>\n📦 <b>Sending to Telegram...</b>", parse_mode=ParseMode.HTML)
        
        with open(file_path, 'rb') as f:
            thumb = open(thumb_path, 'rb') if os.path.exists(thumb_path) else None
            if quality == "mp3": 
                await context.bot.send_audio(
                    query.message.chat_id, f, title=info['title'], thumbnail=thumb, 
                    connect_timeout=1000, read_timeout=1000, write_timeout=1000
                )
            else: 
                await context.bot.send_video(
                    query.message.chat_id, f, caption=f"✅ {info['title']}", supports_streaming=True, 
                    thumbnail=thumb, connect_timeout=1000, read_timeout=1000, write_timeout=1000
                )
            if thumb: thumb.close()

        await query.message.delete()
    except Exception as e: 
        await query.message.reply_text(f"❌ <b>Critical Error:</b> {e}")
    finally:
        if file_path and os.path.exists(file_path): os.remove(file_path)
        if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)

# --- MAIN ---
def main():
    if not os.path.exists(STORAGE_DIR): os.makedirs(STORAGE_DIR)
    
    req = HTTPXRequest(connect_timeout=600, read_timeout=3600, write_timeout=3600, pool_timeout=600)
    
    app = Application.builder().token(TOKEN).request(req).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("clean", clean_storage))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("sysinfo", sysinfo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 Turbo Sync Bot Engine Online.")
    app.run_polling()

if __name__ == "__main__":
    main()

