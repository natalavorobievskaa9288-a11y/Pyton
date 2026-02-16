import telebot
import qrcode
import random
import string
from io import BytesIO

# Твой токен уже вставлен
TOKEN = "8114726970:AAH8PkCdmUCWRipiWLbpteiYjX9Zyleb4FQ"

bot = telebot.TeleBot(TOKEN)

# --- Клавиатура (кнопки) ---
def main_keyboard():
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = telebot.types.KeyboardButton("🔐 Пароль")
    btn2 = telebot.types.KeyboardButton("🎲 Кубик")
    keyboard.add(btn1, btn2)
    return keyboard

# --- Команда /start ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id, 
        f"Привет, {message.from_user.first_name}! 🤖\n\n"
        "Я умею:\n"
        "1. Делать **QR-коды** (просто напиши текст или ссылку).\n"
        "2. Генерировать **пароли** (жми кнопку).\n"
        "3. Кидать **кубик** (жми кнопку).",
        reply_markup=main_keyboard(),
        parse_mode='Markdown'
    )

# --- Генерация пароля ---
@bot.message_handler(func=lambda message: message.text == "🔐 Пароль")
def generate_password(message):
    chars = string.ascii_letters + string.digits + "!@#$%"
    password = ''.join(random.choice(chars) for _ in range(12))
    bot.reply_to(message, f"Твой пароль: `{password}`", parse_mode='Markdown')

# --- Игра в кубик ---
@bot.message_handler(func=lambda message: message.text == "🎲 Кубик")
def send_dice(message):
    bot.send_dice(message.chat.id)

# --- Генерация QR-кода ---
@bot.message_handler(content_types=['text'])
def make_qr(message):
    # Если это не служебная команда, делаем QR
    if message.text.startswith('/'):
        return

    msg = bot.send_message(message.chat.id, "🎨 Рисую QR-код...")
    
    try:
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(message.text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        bio = BytesIO()
        bio.name = 'qr.png'
        img.save(bio, 'PNG')
        bio.seek(0)

        bot.send_photo(message.chat.id, photo=bio, caption="✅ Готово!")
        bot.delete_message(message.chat.id, msg.message_id)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

# --- Запуск ---
if __name__ == '__main__':
    print("Бот запускается...")
    try:
        bot.infinity_polling(none_stop=True)
    except Exception as e:
        print(f"Ошибка при запуске: {e}")
