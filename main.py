import telebot
from telebot import types
import cloudscraper
from bs4 import BeautifulSoup
import time
import threading
import json
import os
import logging

# ================= НАСТРОЙКИ =================

# Твой токен
TOKEN = "8114726970:AAH8PkCdmUCWRipiWLbpteiYjX9Zyleb4FQ"

# Твои ссылки (уже вставлены)
URLS = {
    "jb_admins": {
        "name": "👮‍♂️ Жалобы на Администрацию",
        "url": "https://forum.blackrussia.online/forums/Жалобы-на-администрацию.2330/"
    },
    "jb_leaders": {
        "name": "😎 Жалобы на Лидеров",
        "url": "https://forum.blackrussia.online/forums/Жалобы-на-лидеров.2331/"
    },
    "jb_players": {
        "name": "🎮 Жалобы на Игроков",
        "url": "https://forum.blackrussia.online/forums/Жалобы-на-игроков.2332/"
    },
    "appeals": {
        "name": "⚖️ Обжалование наказаний",
        "url": "https://forum.blackrussia.online/forums/Обжалование-наказаний.2333/"
    }
}

# Файл базы данных
DB_FILE = "users_db.json"
# Время между проверками (в секундах). 60-120 сек оптимально.
CHECK_INTERVAL = 90

# Настройка бота и логов
bot = telebot.TeleBot(TOKEN)
logging.basicConfig(level=logging.INFO)

# Создаем "умный" браузер
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

# Глобальные переменные
data_lock = threading.Lock()
# Сюда будем запоминать ID последней темы
last_known_threads = {key: None for key in URLS.keys()}

# ================= РАБОТА С БАЗОЙ ДАННЫХ =================
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_db(data):
    with data_lock:
        with open(DB_FILE, 'w') as f:
            json.dump(data, f)

def get_user_subs(user_id):
    db = load_db()
    return db.get(str(user_id), [])

def toggle_sub(user_id, category):
    db = load_db()
    s_id = str(user_id)
    if s_id not in db:
        db[s_id] = []
    
    if category in db[s_id]:
        db[s_id].remove(category)
        res = False # Отписался
    else:
        db[s_id].append(category)
        res = True # Подписался
    save_db(db)
    return res

# ================= ПАРСЕР ФОРУМА =================
def check_forum_update(category_key):
    url = URLS[category_key]['url']
    try:
        # Запрос через CloudScraper
        response = scraper.get(url)
        
        if response.status_code != 200:
            logging.error(f"Ошибка доступа к {category_key}: {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем все темы на странице
        threads = soup.select('.structItem--thread')
        
        for thread in threads:
            # Пропускаем закрепленные темы (Важно, Правила и т.д.)
            classes = thread.get('class', [])
            if 'structItem-status--sticky' in classes:
                continue
            
            # Ищем заголовок
            title_tag = thread.select_one('.structItem-title a')
            if not title_tag:
                continue

            title = title_tag.text.strip()
            link = "https://forum.blackrussia.online" + title_tag['href']
            
            # Получаем ID темы из ссылки (цифры в конце)
            # Пример: .../zhaloba.12345/ -> 12345
            try:
                thread_id = link.split('.')[-1].replace('/', '')
            except:
                thread_id = link # Если не вышло, берем всю ссылку как ID
            
            # Автор темы
            author_tag = thread.select_one('.username')
            author = author_tag.text.strip() if author_tag else "Аноним"

            return {
                "id": thread_id,
                "title": title,
                "link": link,
                "author": author
            }
        return None
    except Exception as e:
        logging.error(f"Ошибка парсинга {category_key}: {e}")
        return None

# ================= ФОНОВАЯ ПРОВЕРКА =================
def monitor_loop():
    logging.info("Мониторинг форума запущен...")
    
    # Сначала делаем "холостой" проход, чтобы запомнить текущие последние темы
    # и не спамить при запуске бота старыми темами.
    logging.info("Инициализация данных...")
    for cat_key in URLS:
        latest = check_forum_update(cat_key)
        if latest:
            last_known_threads[cat_key] = latest['id']
    
    while True:
        try:
            db = load_db()
            
            for cat_key, cat_data in URLS.items():
                latest = check_forum_update(cat_key)
                
                if latest:
                    # Если ID сохранен и он отличается от полученного -> НОВАЯ ТЕМА
                    if last_known_threads[cat_key] is not None and latest['id'] != last_known_threads[cat_key]:
                        
                        logging.info(f"Новая тема в {cat_key}: {latest['title']}")
                        last_known_threads[cat_key] = latest['id']
                        
                        # Красивое сообщение
                        msg = (
                            f"🔔 <b>НОВАЯ ЖАЛОБА!</b>\n"
                            f"📂 Раздел: {cat_data['name']}\n"
                            f"👤 Автор: <code>{latest['author']}</code>\n\n"
                            f"📝 <b>{latest['title']}</b>\n"
                            f"🔗 <a href='{latest['link']}'>ПЕРЕЙТИ К ТЕМЕ</a>"
                        )
                        
                        # Рассылка
                        for user_id, subs in db.items():
                            if cat_key in subs:
                                try:
                                    bot.send_message(user_id, msg, parse_mode='HTML')
                                except Exception as e:
                                    logging.error(f"Не удалось отправить юзеру {user_id}: {e}")
                    
                    # Если база была пуста (первый запуск), просто обновляем
                    elif last_known_threads[cat_key] is None:
                        last_known_threads[cat_key] = latest['id']
            
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            logging.error(f"Ошибка в цикле мониторинга: {e}")
            time.sleep(60)

# ================= МЕНЮ БОТА =================
def get_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    subs = get_user_subs(user_id)
    
    for key, data in URLS.items():
        # Ставим галочку или крестик
        status = "✅" if key in subs else "❌"
        btn_text = f"{status} {data['name']}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"sub_{key}"))
        
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.send_message(
        message.chat.id,
        "👋 <b>Привет! Я бот-мониторинг форума.</b>\n\n"
        "Я буду присылать уведомления о новых жалобах.\n"
        "Нажми на кнопки ниже, чтобы подписаться на разделы:",
        reply_markup=get_keyboard(message.chat.id),
        parse_mode='HTML'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('sub_'))
def callback_sub(call):
    key = call.data.split('_', 1)[1] # Берем все после sub_
    user_id = call.message.chat.id
    
    if key in URLS:
        is_subbed = toggle_sub(user_id, key)
        
        # Обновляем кнопки без лишних сообщений
        try:
            bot.edit_message_reply_markup(
                chat_id=user_id,
                message_id=call.message.message_id,
                reply_markup=get_keyboard(user_id)
            )
            # Всплывающее уведомление
            text = "Подписка оформлена!" if is_subbed else "Подписка отменена!"
            bot.answer_callback_query(call.id, text)
        except:
            pass

# ================= ЗАПУСК =================
if __name__ == "__main__":
    # Запускаем мониторинг в отдельном потоке
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    
    print("Бот запущен!")
    bot.infinity_polling()
