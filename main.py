import telebot
from telebot import types
from curl_cffi import requests
from bs4 import BeautifulSoup
import time
import threading
import json
import os
import logging
import random
from fake_useragent import UserAgent

# ================= КОНФИГ =================
TOKEN = "8114726970:AAH8PkCdmUCWRipiWLbpteiYjX9Zyleb4FQ"

# СЮДА ВСТАВЛЯТЬ КУКИ ОТ ПУСТОГО АККАУНТА (ТВИНКА), ЕСЛИ БЕЗ НИХ НЕ РАБОТАЕТ
# Не используй админские куки!
MY_COOKIE = "" 

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
CHECK_INTERVAL = 70 

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
bot = telebot.TeleBot(TOKEN)
ua = UserAgent()

# ================= БД =================
data_lock = threading.Lock()
# Статус по умолчанию
last_scan_info = {key: {"id": None, "title": "Запуск...", "check_time": "...", "status": "Wait"} for key in URLS.keys()}

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

# ================= ПАРСЕР =================
def parse_forum_category(cat_key):
    url = URLS[cat_key]['url']
    
    # Создаем новую сессию для каждого запроса (чтобы менять отпечатки)
    session = requests.Session()
    
    try:
        # Случайная задержка
        time.sleep(random.uniform(2, 5))
        
        headers = {
            'authority': 'forum.blackrussia.online',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'referer': 'https://forum.blackrussia.online/',
            'upgrade-insecure-requests': '1',
            'user-agent': ua.random # Генерируем случайный агент
        }
        
        if MY_COOKIE:
            headers['cookie'] = MY_COOKIE

        # impersonate="chrome110" лучше всего работает сейчас
        response = session.get(url, headers=headers, impersonate="chrome110", timeout=20)
        
        # Проверка на заглушку DDoS-Guard
        if "ddos-guard" in response.text.lower() or "just a moment" in response.text.lower():
            return {"error": "⛔ IP в бане (нужны куки)"}

        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}"}

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем темы
        threads = soup.select('.structItem--thread')
        
        # Если список пуст, возможно, нас перекинуло на страницу входа или ошибки
        if not threads:
            if "Log in" in response.text or "Войти" in response.text:
                return {"error": "Требует вход (Login)"}
            return {"error": "Не вижу тем (возможно, верстка)"}

        found_thread = None
        for thread in threads:
            classes = thread.get('class', [])
            # Пропускаем закрепленные и удаленные
            if 'structItem-status--sticky' in classes or 'is-deleted' in classes:
                continue

            title_tag = thread.select_one('.structItem-title a')
            author_tag = thread.select_one('.username')
            prefix_tag = thread.select_one('.label')
            
            if title_tag:
                # Игнорируем переадресации
                if "redirect" in title_tag['href']: continue
                
                found_thread = {
                    "id": link_to_id(title_tag['href']),
                    "title": title_tag.text.strip(),
                    "link": "https://forum.blackrussia.online" + title_tag['href'],
                    "author": author_tag.text.strip() if author_tag else "Аноним",
                    "prefix": prefix_tag.text.strip() if prefix_tag else "---"
                }
                break 

        return found_thread

    except Exception as e:
        logging.error(f"Err {cat_key}: {e}")
        return {"error": "Ошибка сети"}
    finally:
        session.close()

def link_to_id(link):
    try: return link.split('.')[-1].replace('/', '')
    except: return link

# ================= MONITOR LOOP =================
def monitor_loop():
    logging.info("🚀 STARTING MONITORING...")
    
    while True:
        try:
            db = load_db()
            
            for key, info in URLS.items():
                data = parse_forum_category(key)
                cur_time = time.strftime("%H:%M:%S")
                
                # Если вернулась ошибка
                if data and "error" in data:
                    last_scan_info[key] = {
                        "status": "ERROR", 
                        "check_time": cur_time, 
                        "title": data['error'], 
                        "id": None
                    }
                    continue
                
                # Если данные есть
                if data:
                    prev_id = last_scan_info[key].get('id')
                    
                    last_scan_info[key] = {
                        "status": "OK",
                        "id": data['id'],
                        "title": data['title'],
                        "check_time": cur_time
                    }
                    
                    # Если ID изменился - шлем уведомление
                    if prev_id and data['id'] != prev_id:
                        msg = (
                            f"🔥 <b>НОВАЯ ТЕМА</b>\n"
                            f"📂 {info['name']}\n"
                            f"🏷 <b>{data['prefix']}</b>\n"
                            f"👤 {data['author']}\n\n"
                            f"👉 <a href='{data['link']}'>{data['title']}</a>"
                        )
                        for uid, subs in db.items():
                            if key in subs:
                                try: bot.send_message(uid, msg, parse_mode='HTML')
                                except: pass
                else:
                    # Если просто вернулось None (пусто)
                    last_scan_info[key] = {
                        "status": "WARN",
                        "check_time": cur_time,
                        "title": "Пусто/Сбой",
                        "id": last_scan_info[key].get('id')
                    }

            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            logging.error(f"Loop error: {e}")
            time.sleep(60)

# ================= MENU =================
def main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    subs = get_user_subs(user_id)
    
    for key, data in URLS.items():
        status = "✅" if key in subs else "❌"
        # ИСПРАВЛЕНА ОШИБКА: теперь callback однозначный
        markup.add(types.InlineKeyboardButton(f"{status} {data['name']}", callback_data=f"sub:{key}"))
    
    markup.add(types.InlineKeyboardButton("📊 Статус бота", callback_data="check_logs"))
    return markup

def get_user_subs(uid):
    db = load_db()
    return db.get(str(uid), [])

@bot.message_handler(commands=['start'])
def start_h(m):
    bot.send_message(m.chat.id, "👋 Меню мониторинга:", reply_markup=main_menu(m.chat.id))

@bot.callback_query_handler(func=lambda call: True)
def callback_h(call):
    if call.data == "check_logs":
        report = "📊 <b>СТАТУС:</b>\n\n"
        
        for key, info in last_scan_info.items():
            st = info.get('status', 'Wait')
            if st == "OK": icon = "🟢"
            elif st == "ERROR": icon = "🔴"
            else: icon = "🟡"
            
            title = info.get('title', '...')
            if len(title) > 30: title = title[:30] + "..."
            
            report += f"{icon} <b>{URLS[key]['name']}</b>\n🕒 {info['check_time']}\nℹ️ {title}\n\n"
        
        if not MY_COOKIE:
            report += "⚠️ <i>Работа без куки (возможны сбои)</i>"
            
        bot.send_message(call.message.chat.id, report, parse_mode='HTML')
        bot.answer_callback_query(call.id)
        
    elif call.data.startswith("sub:"):
        # ИСПРАВЛЕНА ЛОГИКА ОБРАБОТКИ
        key = call.data.split(":")[1]
        
        if key in URLS:
            toggle_sub(call.message.chat.id, key)
            try:
                bot.edit_message_reply_markup(
                    call.message.chat.id, 
                    call.message.message_id, 
                    reply_markup=main_menu(call.message.chat.id)
                )
            except: pass
        else:
            bot.answer_callback_query(call.id, "Раздел не найден")

if __name__ == "__main__":
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    bot.infinity_polling()
