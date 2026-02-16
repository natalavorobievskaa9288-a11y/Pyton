import telebot
from telebot import types
import yt_dlp
import logging
import threading
import time
import os
import shutil

# ================= КОНФИГ =================
TOKEN = "8342888953:AAFSTtk4Bj527mxjljOr4jvGYjZ6NHq2v6M"
BOT_USERNAME = "ТвойБот" # Поменяй на имя

# Папка для временных файлов (для 1080p)
DOWNLOAD_PATH = "temp_downloads"
if os.path.exists(DOWNLOAD_PATH): shutil.rmtree(DOWNLOAD_PATH)
os.makedirs(DOWNLOAD_PATH)

logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(TOKEN)

# Память для хранения инфы о видео (чтобы не парсить дважды)
# {chat_id: {info_dict}}
users_cache = {}

# ================= ГЕНЕРАЦИЯ МЕНЮ (КАК НА СКРИНЕ) =================
def format_size(bytes_size):
    if not bytes_size: return "N/A"
    mb = bytes_size / (1024 * 1024)
    return f"{round(mb, 1)} MB"

def create_quality_keyboard(formats, chat_id, video_id):
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    # Сортируем форматы
    # Нам нужны: audio, 144, 240, 360, 480, 720, 1080
    available_buttons = []
    
    # 1. Аудио (MP3)
    markup.add(types.InlineKeyboardButton(f"🎵 MP3", callback_data=f"dl_audio"))

    # 2. Видео
    # Собираем уникальные качества
    seen_heights = set()
    buttons_row = []
    
    for f in formats:
        h = f.get('height')
        if not h or h in seen_heights: continue
        
        filesize = f.get('filesize') or f.get('filesize_approx')
        size_str = format_size(filesize)
        
        # ЛОГИКА РАКЕТЫ:
        # Если есть прямая ссылка и файл есть видео+звук (acodec != none) -> Ракета 🚀
        # Если нужно клеить ffmpeg -> Дискетка 💾
        icon = "🚀" if f.get('acodec') != 'none' and f.get('vcodec') != 'none' else "📥"
        if f.get('ext') != 'mp4': continue # Берем только mp4 для простоты
        
        btn_text = f"{icon} {h}p ({size_str})"
        callback = f"dl_video_{f['format_id']}"
        
        buttons_row.append(types.InlineKeyboardButton(btn_text, callback_data=callback))
        seen_heights.add(h)
        
        # Ограничим до 1080p (выше телеграм не переварит обычно)
        if h >= 1080: break

    # Добавляем кнопки рядами по 2 или 3
    markup.add(*buttons_row)
    
    # Кнопка WebApp
    markup.add(types.InlineKeyboardButton("📺 Смотреть онлайн (Без скачивания)", web_app=types.WebAppInfo(f"https://yewtu.be/watch?v={video_id}")))
    
    return markup

# ================= АНАЛИЗ ССЫЛКИ =================
def process_url(url, chat_id, message_id):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # ПОЛУЧАЕМ ТОЛЬКО JSON (ЭТО БЫСТРО, 1-2 сек)
            info = ydl.extract_info(url, download=False)
            
            # Сохраняем в кэш
            users_cache[chat_id] = info
            
            title = info.get('title', 'Video')
            author = info.get('uploader', 'Unknown')
            thumb = info.get('thumbnail', None)
            formats = info.get('formats', [])
            video_id = info.get('id')
            
            # Формируем текст сообщения (как на скрине)
            msg_text = (
                f"🎬 <b>{title}</b>\n"
                f"👤 {author}\n\n"
                f"✅ <b>Видео найдено!</b>\n"
                f"Выберите качество ниже:\n"
                f"🚀 — Моментальная отправка\n"
                f"📥 — Скачивание на сервер (дольше)"
            )
            
            markup = create_quality_keyboard(formats, chat_id, video_id)
            
            # Если есть картинка - шлем с картинкой, иначе текст
            bot.delete_message(chat_id, message_id)
            if thumb:
                bot.send_photo(chat_id, thumb, caption=msg_text, reply_markup=markup, parse_mode='HTML')
            else:
                bot.send_message(chat_id, msg_text, reply_markup=markup, parse_mode='HTML')

    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {str(e)}", chat_id, message_id)

# ================= СКАЧИВАНИЕ =================
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    chat_id = call.message.chat.id
    if chat_id not in users_cache:
        bot.answer_callback_query(call.id, "❌ Данные устарели, отправь ссылку снова")
        return

    info = users_cache[chat_id]
    url = info.get('webpage_url')
    
    # 1. ОБРАБОТКА АУДИО
    if call.data == "dl_audio":
        bot.answer_callback_query(call.id, "🎵 Качаю аудио...")
        msg = bot.send_message(chat_id, "🎵 <b>Загрузка аудио...</b>", parse_mode='HTML')
        threading.Thread(target=download_audio, args=(url, chat_id, msg.message_id)).start()
        return

    # 2. ОБРАБОТКА ВИДЕО
    if call.data.startswith("dl_video_"):
        format_id = call.data.split("_")[2]
        
        # Ищем выбранный формат в кэше
        selected_format = next((f for f in info['formats'] if f['format_id'] == format_id), None)
        
        if not selected_format:
            bot.answer_callback_query(call.id, "Ошибка формата")
            return

        # ПРОВЕРКА НА МОМЕНТАЛЬНОСТЬ (ROCKET)
        # Если есть url и размер < 50мб, пробуем кинуть ссылкой
        direct_url = selected_format.get('url')
        filesize = selected_format.get('filesize') or 0
        
        is_rocket = (selected_format.get('acodec') != 'none') # Есть звук
        
        if is_rocket and filesize < 50*1024*1024:
            bot.answer_callback_query(call.id, "🚀 Отправляю моментально...")
            try:
                bot.send_video(chat_id, direct_url, caption=f"🎬 {info['title']}", supports_streaming=True)
                return
            except:
                # Если телеграм отверг ссылку, переходим к скачиванию
                pass

        # Если не вышло моментально - качаем
        bot.answer_callback_query(call.id, "📥 Скачиваю на сервер...")
        msg = bot.send_message(chat_id, f"📥 <b>Скачиваю {selected_format.get('height')}p...</b>\n<i>Это может занять время на Bothost</i>", parse_mode='HTML')
        threading.Thread(target=download_full, args=(url, format_id, chat_id, msg.message_id)).start()

# --- ФУНКЦИЯ ФИЗИЧЕСКОГО СКАЧИВАНИЯ ---
def download_full(url, format_id, chat_id, message_id):
    try:
        filename = f"{DOWNLOAD_PATH}/{chat_id}_{format_id}.mp4"
        
        ydl_opts = {
            'format': f"{format_id}+bestaudio/best", # Склеить видео+звук
            'outtmpl': filename,
            'noplaylist': True,
            'max_filesize': 50*1024*1024
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        if os.path.exists(filename):
            bot.edit_message_text("📤 Загружаю в Telegram...", chat_id, message_id)
            with open(filename, 'rb') as f:
                bot.send_video(chat_id, f, caption="✅ Готово")
            bot.delete_message(chat_id, message_id)
            os.remove(filename)
        else:
            bot.edit_message_text("❌ Не удалось скачать (возможно, лимит размера)", chat_id, message_id)
            
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {str(e)}", chat_id, message_id)
        # Чистка
        if os.path.exists(filename): os.remove(filename)

# --- ФУНКЦИЯ АУДИО ---
def download_audio(url, chat_id, message_id):
    try:
        filename = f"{DOWNLOAD_PATH}/{chat_id}.mp3"
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': filename,
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
            'max_filesize': 50*1024*1024
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        if os.path.exists(filename):
            bot.edit_message_text("📤 Отправляю...", chat_id, message_id)
            with open(filename, 'rb') as f:
                bot.send_audio(chat_id, f)
            bot.delete_message(chat_id, message_id)
            os.remove(filename)
    except Exception as e:
        bot.edit_message_text("❌ Ошибка аудио", chat_id, message_id)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    url = message.text.strip()
    if "http" in url:
        msg = bot.send_message(message.chat.id, "🔎 <b>Анализирую форматы...</b>", parse_mode='HTML')
        threading.Thread(target=process_url, args=(url, message.chat.id, msg.message_id)).start()

if __name__ == "__main__":
    bot.infinity_polling()
