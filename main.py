import telebot
from telebot import types
import yt_dlp
import os
import time
import threading
import shutil
import logging
import json
from telebot.apihelper import ApiTelegramException

# ================= ⚙️ СИСТЕМНОЕ ЯДРО =================
TOKEN = "8463954141:AAHd96oRhacVPNF9BYHk5VuEwfKihC7jLn0"
BOT_VER = "Quantum v4.0"

# Папки и настройки
DOWNLOAD_PATH = "downloads_cache"
MAX_FILE_SIZE = 49 * 1024 * 1024  # 49 MB (Оставляем запас)

# Инициализация
if os.path.exists(DOWNLOAD_PATH): shutil.rmtree(DOWNLOAD_PATH)
os.makedirs(DOWNLOAD_PATH)

logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(TOKEN)

# Кэш метаданных (чтобы не парсить ссылку дважды при нажатии кнопок)
# Структура: {chat_id: {data}}
meta_cache = {}

# ================= 🎨 ДИЗАЙН И ТЕКСТЫ =================
TEXTS = {
    "welcome": (
        "🌌 <b>QUANTUM DOWNLOADER</b>\n"
        "<i>Система загрузки контента активирована.</i>\n\n"
        "Я умею извлекать видео и аудио из квантового пространства:\n"
        "💠 <b>YouTube</b> (Video / Shorts)\n"
        "💠 <b>TikTok</b> (No Watermark)\n"
        "💠 <b>Instagram</b> (Reels)\n"
        "💠 <b>RuTube / VK</b>\n\n"
        "📡 <i>Ожидаю входящую ссылку...</i>"
    ),
    "analyzing": "🔄 <b>АНАЛИЗ ПРОТОКОЛА...</b>\n<i>Устанавливаю соединение с сервером...</i>",
    "downloading": "📥 <b>ЗАГРУЗКА НА СЕРВЕР...</b>\n<i>Извлекаю биты данных [===------]</i>",
    "uploading": "📤 <b>ОТПРАВКА В TELEGRAM...</b>\n<i>Финальная стадия передачи.</i>",
    "error": "⛔ <b>СБОЙ СИСТЕМЫ</b>\nНе удалось обработать запрос. Ссылка повреждена или доступ закрыт.",
    "too_large": "⚠️ <b>ФАЙЛ СЛИШКОМ ВЕЛИК</b>\nТелеграм не принимает файлы >50 МБ от ботов.\nПопробуйте выбрать качество ниже.",
    "footer": f"🤖 Powered by {BOT_VER}"
}

# ================= 🧠 ЛОГИКА АНАЛИЗА (СЛОЖНАЯ) =================
def format_time(seconds):
    if not seconds: return "0:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0: return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def get_best_formats(info):
    """Сложная логика выбора форматов для меню"""
    formats = info.get('formats', [])
    buttons_data = []
    
    # 1. Добавляем Аудио
    buttons_data.append({"type": "audio", "label": "🎵 Audio (MP3)", "id": "bestaudio"})

    # 2. Фильтруем видео форматы
    seen_qualities = set()
    
    # Сортируем: сначала маленькие, потом большие
    sorted_formats = sorted(formats, key=lambda x: x.get('height') or 0)

    for f in sorted_formats:
        h = f.get('height')
        if not h or h < 144: continue # Пропускаем мусор
        if h in seen_qualities: continue # Не дублируем
        if f.get('ext') != 'mp4': continue # Только mp4 для стабильности
        
        # Определяем тип загрузки
        # Если есть видео+звук (acodec != none) -> Это Ракета (Быстрая отправка)
        # Если звука нет (acodec == none) -> Это Диск (Надо качать и клеить)
        has_sound = f.get('acodec') != 'none'
        icon = "🚀" if has_sound else "💾"
        
        size = f.get('filesize') or f.get('filesize_approx') or 0
        size_str = f"{round(size / 1024 / 1024, 1)} MB" if size else "N/A"
        
        label = f"{icon} {h}p • {size_str}"
        
        buttons_data.append({
            "type": "video",
            "label": label,
            "id": f['format_id'],
            "res": h,
            "is_rocket": has_sound,
            "url": f.get('url') # Прямая ссылка для ракеты
        })
        
        seen_qualities.add(h)
        if h >= 1080: break # Выше 1080 не показываем (слишком тяжелые)

    return buttons_data

def process_url(url, chat_id, message_id):
    try:
        # Настройки для БЫСТРОГО парсинга (без скачивания)
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Сохраняем в кэш сессии
            meta_cache[chat_id] = info
            
            # Данные для карточки
            title = info.get('title', 'Без названия')
            author = info.get('uploader', 'Неизвестно')
            duration = format_time(info.get('duration'))
            views = info.get('view_count', 0)
            thumb = info.get('thumbnail')
            
            # Формируем клавиатуру
            markup = types.InlineKeyboardMarkup(row_width=2)
            btns = get_best_formats(info)
            
            btn_objects = []
            for btn in btns:
                # Callback: type|format_id
                # Используем короткий callback, чтобы не переполнить лимит телеграма
                cb_data = f"dl|{btn['type']}|{btn['id']}"
                btn_objects.append(types.InlineKeyboardButton(btn['label'], callback_data=cb_data))
            
            markup.add(*btn_objects)
            
            # Добавляем кнопку WebApp для обхода блокировок
            web_url = f"https://yewtu.be/watch?v={info.get('id')}"
            markup.add(types.InlineKeyboardButton("📺 Смотреть Онлайн (No Lag)", web_app=types.WebAppInfo(web_url)))

            # Текст карточки
            caption = (
                f"🎬 <b>{title}</b>\n\n"
                f"👤 Автор: <code>{author}</code>\n"
                f"⏱ Время: {duration} | 👀 Просмотры: {views}\n\n"
                f"👇 <b>Выберите формат загрузки:</b>\n"
                f"🚀 — <i>Мгновенная отправка (Direct)</i>\n"
                f"💾 — <i>Загрузка через сервер (High Quality)</i>"
            )

            bot.delete_message(chat_id, message_id)
            if thumb:
                bot.send_photo(chat_id, thumb, caption=caption, reply_markup=markup, parse_mode='HTML')
            else:
                bot.send_message(chat_id, caption, reply_markup=markup, parse_mode='HTML')

    except Exception as e:
        logging.error(e)
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=TEXTS['error'], parse_mode='HTML')

# ================= 📥 ДВИЖОК ЗАГРУЗКИ =================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        chat_id = call.message.chat.id
        data = call.data.split("|") # dl | type | id
        
        if len(data) != 3 or chat_id not in meta_cache:
            bot.answer_callback_query(call.id, "⚠️ Сессия истекла. Отправьте ссылку снова.")
            return

        dl_type = data[1]
        fmt_id = data[2]
        info = meta_cache[chat_id]
        
        # --- ЛОГИКА АУДИО ---
        if dl_type == "audio":
            bot.answer_callback_query(call.id, "🎵 Обработка аудио...")
            msg = bot.send_message(chat_id, "🎵 <b>Конвертация аудио...</b>", parse_mode='HTML')
            threading.Thread(target=download_engine, args=(info, 'audio', fmt_id, chat_id, msg.message_id)).start()
            return

        # --- ЛОГИКА ВИДЕО ---
        # Ищем формат в JSON
        selected_format = next((f for f in info['formats'] if f['format_id'] == fmt_id), None)
        
        if not selected_format:
            bot.answer_callback_query(call.id, "Ошибка формата")
            return

        # 🚀 ПОПЫТКА 1: DIRECT STREAM (Мгновенно)
        # Если есть прямая ссылка и есть звук - пробуем кинуть ссылку телеграму
        if selected_format.get('url') and selected_format.get('acodec') != 'none':
            bot.answer_callback_query(call.id, "🚀 Запускаю Direct Stream...")
            try:
                bot.send_video(
                    chat_id, 
                    selected_format['url'], 
                    caption=f"🎬 <b>{info['title']}</b>\n{TEXTS['footer']}",
                    parse_mode='HTML',
                    supports_streaming=True
                )
                return # УСПЕХ!
            except ApiTelegramException:
                # Если Телеграм отверг ссылку (например, YouTube IP ban), идем к Попытке 2
                pass

        # 💾 ПОПЫТКА 2: PHYSICAL DOWNLOAD (Через сервер)
        bot.answer_callback_query(call.id, "📥 Переход в режим загрузки...")
        msg = bot.send_message(chat_id, TEXTS['downloading'], parse_mode='HTML')
        threading.Thread(target=download_engine, args=(info, 'video', fmt_id, chat_id, msg.message_id)).start()

    except Exception as e:
        print(e)

def download_engine(info, type_content, fmt_id, chat_id, message_id):
    filename = f"{DOWNLOAD_PATH}/{chat_id}_{int(time.time())}"
    
    try:
        # Настройки yt-dlp для скачивания
        if type_content == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': filename,
                'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}],
                'max_filesize': MAX_FILE_SIZE
            }
            final_ext = ".mp3"
        else:
            # Для видео
            ydl_opts = {
                'format': f"{fmt_id}+bestaudio/best", # Склеить видео + аудио
                'outtmpl': filename,
                'max_filesize': MAX_FILE_SIZE,
                'merge_output_format': 'mp4'
            }
            final_ext = ".mp4"

        # КАЧАЕМ
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([info['webpage_url']])
            
        # Проверяем результат (yt-dlp может добавить расширение)
        final_path = filename + final_ext
        if not os.path.exists(final_path):
            # Иногда расширение другое, ищем файл
            for f in os.listdir(DOWNLOAD_PATH):
                if f.startswith(f"{chat_id}_"):
                    final_path = os.path.join(DOWNLOAD_PATH, f)
                    break
        
        if os.path.exists(final_path):
            file_size = os.path.getsize(final_path)
            if file_size > MAX_FILE_SIZE:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=TEXTS['too_large'], parse_mode='HTML')
                os.remove(final_path)
                return

            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=TEXTS['uploading'], parse_mode='HTML')
            
            with open(final_path, 'rb') as f:
                if type_content == 'audio':
                    bot.send_audio(chat_id, f, title=info['title'], performer=info['uploader'])
                else:
                    bot.send_video(
                        chat_id, f, 
                        caption=f"📼 <b>{info['title']}</b>\n💾 Size: {round(file_size/1024/1024, 1)} MB\n\n{TEXTS['footer']}",
                        parse_mode='HTML',
                        supports_streaming=True
                    )
            
            bot.delete_message(chat_id, message_id)
            # Чистка
            os.remove(final_path)
        else:
            raise Exception("Файл не найден")

    except Exception as e:
        logging.error(f"DL Error: {e}")
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ <b>Ошибка при загрузке.</b>\nВозможно, не хватает кодеков на сервере.", parse_mode='HTML')
        # Пытаемся почистить
        try:
            if os.path.exists(final_path): os.remove(final_path)
        except: pass

# ================= 🚀 ЗАПУСК БОТА =================

@bot.message_handler(commands=['start'])
def start_h(message):
    bot.send_message(message.chat.id, TEXTS['welcome'], parse_mode='HTML')

@bot.message_handler(content_types=['text'])
def text_h(message):
    url = message.text.strip()
    # Простейшая валидация
    if "http" in url:
        msg = bot.send_message(message.chat.id, TEXTS['analyzing'], parse_mode='HTML')
        threading.Thread(target=process_url, args=(url, message.chat.id, msg.message_id)).start()

if __name__ == "__main__":
    print(f"--- {BOT_VER} STARTED ---")
    try:
        bot.remove_webhook()
    except: pass
    bot.infinity_polling()
