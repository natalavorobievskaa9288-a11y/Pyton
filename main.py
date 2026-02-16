import telebot
from telebot import types
from curl_cffi import requests # Используем вместо cloudscraper
from bs4 import BeautifulSoup
import time
import threading
import json
import os
import logging
import random

# ================= КОНФИГ =================
TOKEN = "8114726970:AAH8PkCdmUCWRipiWLbpteiYjX9Zyleb4FQ"

URLS = {
    "jb_admins": {
        "name": "👮‍♂️ Жалобы на АДМ",
        "url": "https://forum.blackrussia.online/forums/Жалобы-на-администрацию.2330/"
    },
    "jb_leaders": {
        "name": "😎 Жалобы на ЛД",
        "url": "https://forum.blackrussia.online/forums/Жалобы-на-лидеров.2331/"
    },
    "jb_players": {
        "name": "🎮 Жалобы на Игроков",
        "url": "https://forum.blackrussia.online/forums/Жалобы-на-игроков.2332/"
    },
    "appeals": {
        "name": "⚖️ Обжалования",
        "url": "https://forum.blackrussia.online/forums/Обжалование-наказаний.2333/"
    }
}

DB_FILE = "users_v2.json"
CHECK_INTERVAL = 60  # Проверяем раз в минуту

# Настройка логов
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
bot = telebot.TeleBot(TOKEN)

# ================= СЕССИЯ С ИМИТАЦИЕЙ БРАУЗЕРА =================
# curl_cffi позволяет имитировать отпечаток браузера Chrome
session = requests.Session()

# ================= ПЕРЕМЕННЫЕ ПАМЯТИ =================
data_lock = threading.Lock()
last_scan_info = {key: {"id": None, "title": "Нет данных", "check_time": "Не проверялось"} for key in URLS.keys()}

# ================= РАБОТА С БД =================
def load_db():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, 'r') as f: return json.load(f)
    except: return {}

def save_db(data):
    with data_lock:
        with open(DB_FILE, 'w') as f: json.dump(data, f)

def toggle_sub(user_id, category):
    db = load_db()
    s_id = str(user_id)
    if s_id not in db: db[s_id] = []
    
    if category in db[s_id]:
        db[s_id].remove(category)
        res = False
    else:
        db[s_id].append(category)
        res = True
    save_db(db)
    return res

# ================= ПАРСЕР (НОВЫЙ МЕТОД) =================
def parse_forum_category(cat_key):
    url = URLS[cat_key]['url']
    try:
        # Случайная задержка
        time.sleep(random.uniform(1, 3))
        
        # Запрос с имитацией Chrome 110 (обходит TLS Fingerprint)
        response = session.get(
            url, 
            impersonate="chrome110", 
            timeout=15
        )
        
        if response.status_code != 200:
            logging.error(f"FAIL {cat_key}: Code {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Находим темы
        threads = soup.select('.structItem--thread')
        
        if not threads:
            # Иногда защита выдает заглушку, проверяем это
            if "Just a moment" in response.text or "DDoS-Guard" in response.text:
                logging.warning(f"DETECTED PROTECTION on {cat_key}")
            else:
                logging.warning(f"Пустой список тем в {cat_key}. Возможно, верстка изменилась.")
            return None

        found_thread = None
        
        for thread in threads:
            classes = thread.get('class', [])
            
            # Пропускаем закрепы и удаленные
            if 'structItem-status--sticky' in classes or 'is-deleted' in classes:
                continue

            title_tag = thread.select_one('.structItem-title a')
            author_tag = thread.select_one('.username')
            
            # Получаем префикс
            prefix_tag = thread.select_one('.label')
            prefix = prefix_tag.text.strip() if prefix_tag else "Без префикса"
            
            if title_tag:
                # Дополнительная проверка: иногда форум кидает "Переадресацию" как тему
                if "redirect" in title_tag['href']:
                    continue

                found_thread = {
                    "id": link_to_id(title_tag['href']),
                    "title": title_tag.text.strip(),
                    "link": "https://forum.blackrussia.online" + title_tag['href'],
                    "author": author_tag.text.strip() if author_tag else "Аноним",
                    "prefix": prefix
                }
                break 

        return found_thread

    except Exception as e:
        logging.error(f"Error parsing {cat_key}: {e}")
        return None

def link_to_id(link):
    try:
        return link.split('.')[-1].replace('/', '')
    except:
        return link

# ================= ФОНОВЫЙ ПРОЦЕСС =================
def monitor_loop():
    logging.info("🚀 Мониторинг запущен (CURL_CFFI mode)")
    
    # Первый прогон
    for key in URLS:
        data = parse_forum_category(key)
        if data:
            last_scan_info[key] = {
                "id": data['id'],
                "title": data['title'],
                "check_time": time.strftime("%H:%M:%S")
            }
            logging.info(f"Init {key}: {data['title']}")
        else:
             logging.info(f"Init {key}: Не удалось получить данные")
    
    while True:
        try:
            db = load_db()
            
            for key, info in URLS.items():
                data = parse_forum_category(key)
                current_time = time.strftime("%H:%M:%S")
                
                if data:
                    prev_id = last_scan_info[key].get('id')
                    
                    last_scan_info[key] = {
                        "id": data['id'],
                        "title": data['title'],
                        "check_time": current_time
                    }
                    
                    if prev_id and data['id'] != prev_id:
                        logging.info(f"🔥 NEW THREAD in {key}: {data['title']}")
                        
                        msg = (
                            f"🔥 <b>НОВАЯ ЖАЛОБА</b>\n"
                            f"📂 {info['name']}\n"
                            f"🏷 <b>{data['prefix']}</b>\n"
                            f"👤 От: {data['author']}\n\n"
                            f"📝 <a href='{data['link']}'>{data['title']}</a>"
                        )
                        
                        for user_id, subs in db.items():
                            if key in subs:
                                try:
                                    bot.send_message(user_id, msg, parse_mode='HTML')
                                except: pass
                else:
                    last_scan_info[key]['check_time'] = f"{current_time} (Защита/Ошибка)"

            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            logging.error(f"Global Loop Error: {e}")
            time.sleep(60)

# ================= МЕНЮ =================
def main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    subs = get_user_subs(user_id)
    
    for key, data in URLS.items():
        status = "✅" if key in subs else "❌"
        markup.add(types.InlineKeyboardButton(f"{status} {data['name']}", callback_data=f"sub_{key}"))
    
    markup.add(types.InlineKeyboardButton("📊 Статус / Логи бота", callback_data="check_logs"))
    return markup

@bot.message_handler(commands=['start'])
def start_h(m):
    bot.send_message(
        m.chat.id, 
        "🤖 <b>Мониторинг BlackRussia</b>\nЖми кнопки для подписки на разделы.",
        reply_markup=main_menu(m.chat.id),
        parse_mode='HTML'
    )

def get_user_subs(uid):
    db = load_db()
    return db.get(str(uid), [])

@bot.callback_query_handler(func=lambda call: True)
def callback_h(call):
    if call.data == "check_logs":
        report = "📊 <b>ТЕКУЩИЙ СТАТУС БОТА:</b>\n\n"
        for key, info in last_scan_info.items():
            name = URLS[key]['name']
            last_t = info['title']
            check_t = info['check_time']
            if len(last_t) > 25: last_t = last_t[:25] + "..."
            
            report += f"🔹 <b>{name}</b>\n🕒 {check_t}\n👁 {last_t}\n\n"
        
        bot.send_message(call.message.chat.id, report, parse_mode='HTML')
        bot.answer_callback_query(call.id)
        
    elif call.data.startswith("sub_"):
        key = call.data.split("_")[1]
        toggle_sub(call.message.chat.id, key)
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id, 
                call.message.message_id, 
                reply_markup=main_menu(call.message.chat.id)
            )
        except: pass

if __name__ == "__main__":
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    bot.infinity_polling()
