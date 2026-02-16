import telebot
import qrcode
from io import BytesIO

TOKEN = "8114726970:AAH8PkCdmUCWRipiWLbpteiYjX9Zyleb4FQ"

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привет! Бот работает. Отправь текст для QR-кода.")

@bot.message_handler(content_types=['text'])
def make_qr(message):
    try:
        qr = qrcode.make(message.text)
        bio = BytesIO()
        qr.save(bio, 'PNG')
        bio.seek(0)
        bot.send_photo(message.chat.id, photo=bio)
    except Exception:
        bot.send_message(message.chat.id, "Ошибка.")

if __name__ == '__main__':
    bot.infinity_polling(none_stop=True)
