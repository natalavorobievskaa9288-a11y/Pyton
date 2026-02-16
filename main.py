import telebot
from telebot import types
import yt_dlp
import logging
import threading
import time
from urllib.parse import quote

# ================= КОНФИГ =================
TOKEN = "8342888953:AAFSTtk4Bj527mxjljOr4jvGYjZ6NHq2v6M"

# Зеркало для обхода замедления (Invidious)
# yewtu.be - одно из самых стабильных
BYPASS_URL = "https://yewtu.be/watch?v=" 

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
bot = telebot.TeleBot(TOKEN)

# ================= ПРИВЕТСТВИЕ =================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    # Кнопка для теста WebApp
    web_btn = types.InlineKeyboardButton("📺 Тест обхода (WebApp)", web_app=types.WebAppInfo("https://yewtu.be"))
    markup.add(web_btn)
    
    bot.send_message(
        message.chat.id,
        "🇷🇺 <b>СИСТЕМА ЗАГРУЗКИ v3.0 (TURBO)</b>\n\n"
        "Я работаю по протоколу <b>Direct Stream</b>.\n"
        "Я не качаю файлы на диск — я заставляю Телеграм качать их напрямую.\n\n"
        "⚡ <b>Кидай ссылку на:</b>\n"
        "🔴 YouTube (Video/Shorts)\n"
        "⚫ TikTok\n"
        "🟣 Instagram Reels\n\n"
        "👇 <i>Жду ссылку...</i>",
        parse_mode='HTML',
        reply_markup=markup
    )

# ================= ОБРАБОТКА ССЫЛОК =================
def process_video(url, chat_id, message_id):
    try:
        # Настройки: НЕ качать, только получить JSON
        ydl_opts = {
            'format': 'best[ext=mp4]/best', # Ищем лучшее mp4
            'noplaylist': True,
            'quiet': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 1. Получаем инфу МГНОВЕННО (без скачивания)
            info = ydl.extract_info(url, download=False)
            
            video_url = info.get('url', None) # Прямая ссылка на файл
            title = info.get('title', 'Video')
            author = info.get('uploader', 'Unknown')
            video_id = info.get('id', '')
            duration = info.get('duration', 0)
            
            # Формируем кнопку для просмотра без замедления
            markup = types.InlineKeyboardMarkup()
            
            # Генерируем ссылку для WebApp (обход РКН через Invidious)
            if video_id:
                watch_url = f"{BYPASS_URL}{video_id}"
                btn_watch = types.InlineKeyboardButton(
                    text="📺 Смотреть онлайн (Без лагов)", 
                    web_app=types.WebAppInfo(watch_url)
                )
                markup.add(btn_watch)
            
            # Подпись
            caption = f"🎬 <b>{title}</b>\n👤 {author}\n⏱ {time.strftime('%M:%S', time.gmtime(duration))}"

            # 2. Пытаемся отправить ПРЯМУЮ ССЫЛКУ (Метод Instant)
            # Телеграм сам скачает видео по ссылке video_url
            if video_url:
                try:
                    bot.send_video(
                        chat_id, 
                        video=video_url, 
                        caption=caption, 
                        parse_mode='HTML',
                        reply_markup=markup,
                        supports_streaming=True
                    )
                    # Удаляем сообщение "Загрузка"
                    bot.delete_message(chat_id, message_id)
                    logging.info(f"Sent via URL: {url}")
                    return
                except Exception as e:
                    logging.error(f"Telegram refused direct URL: {e}")
                    # Если Телеграм не принял ссылку (бывает с YouTube), идем дальше
            
            # Если прямая ссылка не сработала (YouTube часто блокирует чужие IP)
            bot.edit_message_text(
                chat_id=chat_id, 
                message_id=message_id, 
                text="⚠️ <b>Прямая ссылка недоступна.</b>\nYouTube блокирует отправку файлом.\n\n👇 <b>Нажми кнопку ниже, чтобы смотреть без замедления:</b>",
                reply_markup=markup,
                parse_mode='HTML'
            )

    except Exception as e:
        bot.edit_message_text(chat_id, message_id, text=f"❌ Ошибка: {str(e)}")

@bot.message_handler(content_types=['text'])
def handle_url(message):
    url = message.text.strip()
    
    if not ("http" in url): 
        return

    # Моментальный ответ
    msg = bot.send_message(message.chat.id, "⚡ <b>Обработка запроса...</b>", parse_mode='HTML')
    
    # Запускаем в фоне
    threading.Thread(target=process_video, args=(url, message.chat.id, msg.message_id)).start()

# ================= ЗАПУСК =================
if __name__ == "__main__":
    bot.infinity_polling()
