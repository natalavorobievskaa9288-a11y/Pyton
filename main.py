import telebot
from telebot import types
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont
import wikipedia
import os

# Твой токен
TOKEN = "8114726970:AAH8PkCdmUCWRipiWLbpteiYjX9Zyleb4FQ"

bot = telebot.TeleBot(TOKEN)
wikipedia.set_lang("ru")  # Википедия на русском

# Словарь для хранения состояний пользователей
user_states = {}
user_photos = {}

# --- ГЛАВНОЕ МЕНЮ ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🧠 Найти в Википедии")
    btn2 = types.KeyboardButton("📸 Обработать фото")
    markup.add(btn1, btn2)
    
    bot.send_message(
        message.chat.id,
        f"Привет, {message.from_user.first_name}! 🚀\n\n"
        "Я стал умнее. Что будем делать?\n"
        "1. Отправь мне **Фото**, чтобы улучшить его или сделать мем.\n"
        "2. Напиши любой **Текст**, чтобы я нашел это в Википедии.",
        reply_markup=markup
    )

# --- ЛОГИКА ВИКИПЕДИИ ---
@bot.message_handler(func=lambda message: not message.photo)
def wiki_search(message):
    # Если нажали кнопки меню, просто игнорируем или даем подсказку
    if message.text == "🧠 Найти в Википедии":
        bot.send_message(message.chat.id, "Просто напиши мне слово или фразу!")
        return
    elif message.text == "📸 Обработать фото":
        bot.send_message(message.chat.id, "Просто отправь мне фотографию!")
        return

    # Ищем в вики
    try:
        msg = bot.send_message(message.chat.id, "🔍 Ищу информацию...")
        page = wikipedia.page(message.text)
        text = page.summary[:800] + "..." # Берем первые 800 символов
        
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton("Читать полностью", url=page.url)
        markup.add(btn)
        
        bot.edit_message_text(f"📚 **{page.title}**\n\n{text}", chat_id=message.chat.id, message_id=msg.message_id, reply_markup=markup, parse_mode="Markdown")
    except wikipedia.exceptions.DisambiguationError as e:
        bot.send_message(message.chat.id, "Слишком много значений. Уточните запрос.")
    except Exception:
        bot.send_message(message.chat.id, "Ничего не нашел по этому запросу 😔")

# --- ОБРАБОТКА ФОТО ---
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    # Скачиваем фото
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    # Сохраняем временно
    file_name = f"photo_{message.chat.id}.jpg"
    with open(file_name, 'wb') as new_file:
        new_file.write(downloaded_file)
    
    user_photos[message.chat.id] = file_name

    # Клавиатура выбора действия
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("✨ Улучшить качество", callback_data="enhance")
    btn2 = types.InlineKeyboardButton("⚫ Ч/Б фильтр", callback_data="bw")
    btn3 = types.InlineKeyboardButton("✏️ Контуры (Рисунок)", callback_data="contour")
    btn4 = types.InlineKeyboardButton("💬 Сделать Мем", callback_data="meme")
    markup.add(btn1, btn2, btn3, btn4)

    bot.reply_to(message, "Фото получено! Что сделаем?", reply_markup=markup)

# --- ОБРАБОТЧИК КНОПОК ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    
    if chat_id not in user_photos:
        bot.answer_callback_query(call.id, "Фото устарело, скинь новое!")
        return

    file_name = user_photos[chat_id]
    img = Image.open(file_name)
    bot.answer_callback_query(call.id, "Обрабатываю... ⏳")

    try:
        if call.data == "enhance":
            # Улучшаем резкость, цвет и контраст
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.5) # Резкость
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(1.2) # Насыщенность
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.1) # Контраст
            caption = "✨ Фото улучшено!"

        elif call.data == "bw":
            img = img.convert("L") # Черно-белое
            caption = "⚫ Ч/Б фильтр применен."

        elif call.data == "contour":
            img = img.filter(ImageFilter.CONTOUR)
            caption = "✏️ Эффект контуров."

        elif call.data == "meme":
            bot.send_message(chat_id, "Напиши текст, который нужно добавить на фото:")
            user_states[chat_id] = "waiting_for_meme_text"
            return # Выходим, ждем текст

        # Отправка результата (если это не мем)
        output_name = f"edited_{chat_id}.jpg"
        img.save(output_name)
        
        with open(output_name, 'rb') as f:
            bot.send_photo(chat_id, f, caption=caption)
        
        # Чистим мусор
        os.remove(output_name)

    except Exception as e:
        bot.send_message(chat_id, f"Ошибка обработки: {e}")

# --- ГЕНЕРАЦИЯ МЕМА (Наложение текста) ---
@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_for_meme_text")
def add_text_to_photo(message):
    chat_id = message.chat.id
    text = message.text
    file_name = user_photos.get(chat_id)

    if not file_name:
        bot.send_message(chat_id, "Сначала скинь фото!")
        return

    try:
        img = Image.open(file_name)
        width, height = img.size
        draw = ImageDraw.Draw(img)

        # Пытаемся подобрать размер шрифта (5% от высоты фото)
        fontsize = int(height * 0.05)
        # Используем стандартный шрифт (так как на сервере может не быть крутых)
        try:
            font = ImageFont.truetype("arial.ttf", fontsize)
        except:
            font = ImageFont.load_default() # Если нет шрифтов, берем системный

        # Рисуем текст внизу
        # Координаты (немного отступаем снизу)
        text_position = (10, height - fontsize - 20)
        
        # Рисуем черную обводку для читаемости
        draw.text((text_position[0]-2, text_position[1]-2), text, font=font, fill="black")
        draw.text((text_position[0]+2, text_position[1]-2), text, font=font, fill="black")
        
        # Рисуем белый текст
        draw.text(text_position, text, font=font, fill="white")

        output_name = f"meme_{chat_id}.jpg"
        img.save(output_name)

        with open(output_name, 'rb') as f:
            bot.send_photo(chat_id, f, caption="Твой мем готов! 😎")
        
        os.remove(output_name)
        user_states[chat_id] = None # Сбрасываем состояние

    except Exception as e:
        bot.send_message(chat_id, f"Не удалось нарисовать текст: {e}")

# Запуск
if __name__ == '__main__':
    # Очистка старых фото при перезапуске (опционально)
    for f in os.listdir():
        if f.startswith("photo_") or f.startswith("edited_") or f.startswith("meme_"):
            try: os.remove(f)
            except: pass
            
    bot.infinity_polling(none_stop=True)
