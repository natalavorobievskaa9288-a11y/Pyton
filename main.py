import telebot
from telebot import types
import yt_dlp
import os
import time
import threading
import logging
import random

# ================= КОНФИГ "МОЩЬ" =================
TOKEN = "8342888953:AAFSTtk4Bj527mxjljOr4jvGYjZ6NHq2v6M"

# Папка для временных файлов
DOWNLOAD_PATH = "downloads"
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# Настройка логов
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
bot = telebot.TeleBot(TOKEN)

# Лимит телеграма для ботов - 50 МБ (байт)
MAX_FILE_SIZE = 50 * 1024 * 1024 

# ================= КРАСИВЫЕ ТЕКСТЫ =================
WELCOME_TEXT = (
    "🚀 <b>ULTIMATE DOWNLOADER BOT</b>\n\n"
    "Я — машина для скачивания контента. Мне не важно, откуда ссылка.\n"
    "Просто кидай её сюда, и я достану видео в лучшем качестве.\n\n"
    "✅ <b>Поддерживаю:</b>\n"
    "🔴 YouTube (Video, Shorts)\n"
    "⚫ TikTok (No Watermark)\n"
    "🔵 VK Видео / Clips\n"
    "🟠 RuTube\n"
    "📸 Instagram (Reels)\n"
    "И еще 1000+ сайтов...\n\n"
    "👇 <i>Жду твою ссылку...</i>"
)

PROCESSING_MSGS = [
    "🚀 Запускаю двигатели...",
    "🛰 Устанавливаю соединение...",
    "⚡ Взламываю пентагон (шутка)...",
    "📥 Выкачиваю байты...",
    "💎 Полирую пиксели..."
]

# ================= ЛОГИКА СКАЧИВАНИЯ (ЯДРО) =================
def download_video_task(url, chat_id, message_id):
    """Функция выполняется в отдельном потоке"""
    file_path = None
    try:
        # 1. Меняем статус на "Скачивание"
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"⏳ <b>{random.choice(PROCESSING_MSGS)}</b>\n<i>Подождите, идет магия...</i>",
            parse_mode='HTML'
        )

        # 2. Настройка yt-dlp (МОЩНЫЕ НАСТРОЙКИ)
        ydl_opts = {
            'format': 'best[ext=mp4]/best', # Лучшее качество в MP4
            'outtmpl': f'{DOWNLOAD_PATH}/%(id)s_%(title).50s.%(ext)s', # Имя файла
            'noplaylist': True, # Не качать плейлисты целиком
            'max_filesize': MAX_FILE_SIZE, # Не качать если больше 50мб (сразу отбой)
            'quiet': True,
            'no_warnings': True,
            # Маскировка под браузер (чтобы Ютуб не банил)
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'nocheckcertificate': True,
        }

        info_dict = None
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Сначала получаем инфу
            info_dict = ydl.extract_info(url, download=True)
            
            # Определяем путь к скачанному файлу
            if 'entries' in info_dict:
                # Если это плейлист (иногда бывает), берем первый
                video_info = info_dict['entries'][0]
            else:
                video_info = info_dict

            filename = ydl.prepare_filename(video_info)
            file_path = filename

        # 3. Проверяем файл перед отправкой
        if not os.path.exists(file_path):
            raise Exception("Файл не найден после скачивания")

        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ <b>Файл слишком большой!</b>\nTelegram запрещает ботам отправлять файлы больше 50 МБ.\nРазмер этого видео: {round(file_size/1024/1024, 1)} МБ.",
                parse_mode='HTML'
            )
            os.remove(file_path)
            return

        # 4. Отправляем в Телеграм
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="📤 <b>Загружаю в Telegram...</b>", parse_mode='HTML')
        
        with open(file_path, 'rb') as video:
            # Получаем название и автора для подписи
            caption = f"🎥 <b>{video_info.get('title', 'Video')}</b>\n👤 {video_info.get('uploader', 'Unknown')}"
            
            bot.send_video(
                chat_id, 
                video, 
                caption=caption[:1024], # Обрезаем если слишком длинное
                parse_mode='HTML',
                supports_streaming=True
            )

        # 5. Успех - удаляем сообщение о загрузке
        bot.delete_message(chat_id, message_id)
        logging.info(f"Success: {url}")

    except yt_dlp.utils.DownloadError as e:
        bot.edit_message_text(chat_id, message_id, text=f"❌ <b>Ошибка при скачивании:</b>\nНеверная ссылка или доступ закрыт.", parse_mode='HTML')
        logging.error(f"DL Error: {e}")
    except Exception as e:
        bot.edit_message_text(chat_id, message_id, text=f"❌ <b>Системная ошибка:</b>\n{str(e)}", parse_mode='HTML')
        logging.error(f"Global Error: {e}")
    finally:
        # 6. Уборка мусора (ОБЯЗАТЕЛЬНО)
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

# ================= ОБРАБОТЧИКИ БОТА =================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Клавиатура
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("👨‍💻 Разработчик", url="https://t.me/durov") # Поставь свою ссылку
    markup.add(btn1)
    
    bot.send_message(
        message.chat.id, 
        WELCOME_TEXT, 
        parse_mode='HTML', 
        reply_markup=markup
    )

@bot.message_handler(content_types=['text'])
def handle_text(message):
    url = message.text.strip()
    
    # Простейшая проверка на ссылку
    if not (url.startswith("http://") or url.startswith("https://")):
        bot.send_message(message.chat.id, "🤨 <b>Это не ссылка!</b>\nПришли мне ссылку на TikTok, YouTube или RuTube.", parse_mode='HTML')
        return

    # Отправляем сообщение "Ожидайте"
    msg = bot.send_message(message.chat.id, "🔎 <b>Анализирую ссылку...</b>", parse_mode='HTML')
    
    # Запускаем поток, чтобы бот не тормозил
    threading.Thread(
        target=download_video_task, 
        args=(url, message.chat.id, msg.message_id),
        daemon=True
    ).start()

# ================= ЗАПУСК =================
if __name__ == "__main__":
    logging.info("🚀 BOT STARTED SUCCESSFULLY")
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            logging.error(f"Bot crashed: {e}")
            time.sleep(5)
