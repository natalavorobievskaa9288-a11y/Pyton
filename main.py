import telebot
from telebot import types
import yt_dlp
import os
import time
import threading
import logging
import random
import shutil

# ================= КОНФИГ =================
TOKEN = "8342888953:AAFSTtk4Bj527mxjljOr4jvGYjZ6NHq2v6M"
DEVELOPER_NAME = "MAHIRO OYAMA"
DEVELOPER_URL = "https://t.me/mahiro_oyama" # Ссылка на профиль (можешь поменять)

# Папка для загрузок
DOWNLOAD_PATH = "fast_downloads"
# Очищаем папку при запуске, чтобы удалить старый мусор
if os.path.exists(DOWNLOAD_PATH):
    shutil.rmtree(DOWNLOAD_PATH)
os.makedirs(DOWNLOAD_PATH)

# Логи
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
bot = telebot.TeleBot(TOKEN)

# Лимит (50 МБ), но мы стараемся качать файлы меньше
MAX_FILE_SIZE = 49 * 1024 * 1024 

# ================= ТЕКСТЫ =================
WELCOME_TEXT = (
    "🚀 <b>FAST DOWNLOADER</b>\n"
    "<i>By MAHIRO OYAMA</i>\n\n"
    "Я помогу тебе смотреть YouTube без тормозов прямо здесь.\n"
    "Кидай ссылку на:\n"
    "🔹 <b>YouTube</b> (обхожу замедление)\n"
    "🔹 <b>TikTok</b> (без водяных знаков)\n"
    "🔹 <b>Shorts / Reels</b>\n\n"
    "⚡️ <i>Отправь ссылку, и я скачаю это максимально быстро.</i>"
)

# ================= ЛОГИКА СКАЧИВАНИЯ =================
def download_video_task(url, chat_id, message_id):
    file_path = None
    try:
        # 1. Быстрый ответ
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"⚡ <b>Загрузка...</b>\n<i>Качаю в Telegram для обхода замедления.</i>",
            parse_mode='HTML'
        )

        # 2. Настройки YT-DLP для СКОРОСТИ
        # Мы берем формат b (best), но ограничиваем высоту до 720p или 480p.
        # Это критически важно для скорости на слабом хостинге.
        ydl_opts = {
            'format': 'best[ext=mp4][height<=?720]/best[ext=mp4]/best', # Приоритет 720p MP4
            'outtmpl': f'{DOWNLOAD_PATH}/%(id)s.%(ext)s',
            'noplaylist': True,
            'max_filesize': MAX_FILE_SIZE,
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            # Маскировка под iPhone (часто быстрее отдает видео)
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            # Многопоточная загрузка (ускоряет YouTube)
            'concurrent_fragment_downloads': 4,
        }

        info_dict = None
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Получаем инфу и качаем сразу
            info_dict = ydl.extract_info(url, download=True)
            
            if 'entries' in info_dict:
                video_info = info_dict['entries'][0]
            else:
                video_info = info_dict

            filename = ydl.prepare_filename(video_info)
            file_path = filename

        # 3. Проверка файла
        if not os.path.exists(file_path):
            raise Exception("Файл не создался")

        file_size = os.path.getsize(file_path)
        
        # Если файл больше 50 МБ
        if file_size > MAX_FILE_SIZE:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"⚠️ <b>Видео слишком длинное/тяжелое!</b>\nTelegram не дает ботам грузить >50 МБ.\nПопробуй видео покороче.",
                parse_mode='HTML'
            )
            os.remove(file_path)
            return

        # 4. Отправка видео
        bot.edit_message_text(chat_id, message_id, "📤 <b>Отправляю...</b>", parse_mode='HTML')
        
        with open(file_path, 'rb') as video:
            title = video_info.get('title', 'Video')
            author = video_info.get('uploader', 'Unknown')
            # Ссылка на профиль автора видео
            webpage_url = video_info.get('webpage_url', url)

            caption = (
                f"🎬 <a href='{webpage_url}'>{title}</a>\n"
                f"👤 <b>{author}</b>\n\n"
                f"🤖 Скачано через бота от {DEVELOPER_NAME}"
            )
            
            bot.send_video(
                chat_id, 
                video, 
                caption=caption, 
                parse_mode='HTML',
                supports_streaming=True # Позволяет смотреть сразу, не дожидаясь полной загрузки
            )

        # 5. Удаляем сервисное сообщение
        bot.delete_message(chat_id, message_id)

    except Exception as e:
        err_msg = str(e)
        if "File is larger than" in err_msg:
            text = "❌ Видео слишком большое для Telegram."
        elif "Sign in" in err_msg:
            text = "❌ YouTube требует вход (18+ или защита). Не могу скачать."
        else:
            text = "❌ Не удалось скачать. Ссылка нерабочая или хостинг блокирует."
            
        bot.edit_message_text(chat_id, message_id, text=text)
        logging.error(f"Error: {e}")

    finally:
        # Всегда удаляем файл после попытки
        if file_path and os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass

# ================= ОБРАБОТЧИКИ =================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(f"👑 {DEVELOPER_NAME}", url=DEVELOPER_URL)
    markup.add(btn)
    
    bot.send_message(
        message.chat.id, 
        WELCOME_TEXT, 
        parse_mode='HTML', 
        reply_markup=markup
    )

@bot.message_handler(content_types=['text'])
def handle_text(message):
    url = message.text.strip()
    
    if not (url.startswith("http://") or url.startswith("https://") or "youtu" in url or "tiktok" in url):
        # Игнорируем обычный текст, чтобы не спамить
        return

    # Мгновенная реакция
    msg = bot.send_message(message.chat.id, "🚀 <b>Связываюсь с сервером...</b>", parse_mode='HTML')
    
    # Запуск в потоке
    threading.Thread(
        target=download_video_task, 
        args=(url, message.chat.id, msg.message_id),
        daemon=True
    ).start()

# ================= START =================
if __name__ == "__main__":
    # Чистим старые вебхуки если были
    try: bot.remove_webhook()
    except: pass
    
    logging.info(f"Bot by {DEVELOPER_NAME} started!")
    bot.infinity_polling()
