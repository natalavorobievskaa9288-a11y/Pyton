# -*- coding: utf-8 -*-
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
import sqlite3
import datetime
import time

# ================= КОНФИГУРАЦИЯ =================
CONFIG = {
    "token": "vk1.a.Z9pCqT1rlC8JsFxbrZMhhmvbPe764cfFlF9N1z5RG4nrLfO9E8YisGaABMzphZNjMOZ01Y4A25SAdRZnvVSO2mxmOUq2AiOsPkNmmQXH_6ghpstHBPiPjxZv-c6t8JL8JV1qbmOpFPTTSOx8_CAfsKFaMqa9_-BXqLW4LbeR2fyyncJMlHHpTsfcjLWXtZYJu1rJSUDPp4zoCoVcOpaE5A",
    "group_id": 236066012,
    "owner_id": 864765284,
    "db_file": "server_bot.db"
}

# ================= ШАБЛОНЫ =================
T_NORMA = "1. NickName:\n2. Ранг:\n3. Дата:\n4. Описание:\n5. /astats:"
T_EXTRA = "1. NickName:\n2. Ранг:\n3. Дата:\n4. Проделанная работа:"
T_INACTIVE = "1. NickName:\n2. Ранг:\n3. Даты неактива:\n4. Причина:"

# ================= БАЗА ДАННЫХ =================
class Database:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                nickname TEXT DEFAULT 'Игрок',
                lvl INTEGER DEFAULT 0,
                prefix TEXT DEFAULT 'Пользователь',
                reg_date TEXT,
                norma_days INTEGER DEFAULT 0
            )''')
        self.conn.commit()

    def get_user(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        res = self.cursor.fetchone()
        if not res:
            self.cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            self.conn.commit()
            return self.get_user(user_id)
        return res

    def update(self, user_id, col, val):
        self.cursor.execute(f"UPDATE users SET {col} = ? WHERE user_id = ?", (val, user_id))
        self.conn.commit()

db = Database(CONFIG['db_file'])

# ================= КЛАВИАТУРА =================
def get_main_keyboard(is_admin):
    kb = VkKeyboard(one_time=False) # Кнопки НЕ исчезают
    kb.add_button("📩 Норма", color=VkKeyboardColor.POSITIVE)
    kb.add_button("📈 Доп. отчет", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button("🕓 Неактив", color=VkKeyboardColor.SECONDARY)
    kb.add_button("📜 Профиль", color=VkKeyboardColor.SECONDARY)
    
    if is_admin:
        kb.add_line()
        kb.add_button("⚙ Админ-панель", color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()

def get_cancel_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button("❌ Отмена", color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()

# ================= БОТ =================
class Bot:
    def __init__(self):
        self.vk_session = vk_api.VkApi(token=CONFIG['token'])
        self.vk = self.vk_session.get_api()
        self.longpoll = VkBotLongPoll(self.vk_session, CONFIG['group_id'])
        self.states = {}
        self.temp = {}
        print("Бот запущен!")

    def send(self, uid, text, kb=None):
        try:
            self.vk.messages.send(peer_id=uid, message=text, random_id=get_random_id(), keyboard=kb)
        except Exception as e:
            print(f"Ошибка отправки: {e}")

    def run(self):
        while True:
            try:
                for event in self.longpoll.listen():
                    if event.type == VkBotEventType.MESSAGE_NEW and event.from_user:
                        self.handle(event)
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(2)

    def handle(self, event):
        user_id = event.object.message['from_id']
        text = event.object.message['text'].strip() # Убираем пробелы
        text_lower = text.lower()
        
        user_db = db.get_user(user_id)
        
        # Авто-выдача прав создателю
        is_admin = (user_db[2] > 0) or (user_id == CONFIG['owner_id'])
        if user_id == CONFIG['owner_id'] and user_db[2] == 0:
            db.update(user_id, 'lvl', 5)
            db.update(user_id, 'prefix', 'Создатель')
            is_admin = True
            self.send(user_id, "✅ Вы опознаны как Создатель!", get_main_keyboard(True))

        # === ГЛАВНАЯ КОМАНДА: НАЧАТЬ ===
        if text_lower in ['начать', 'start', 'меню', 'menu', 'привет']:
            self.states[user_id] = None
            self.send(user_id, "👋 Главное меню загружено.\nИспользуй кнопки:", get_main_keyboard(is_admin))
            return

        # === КОМАНДА ОТМЕНЫ ===
        if text_lower in ['отмена', '❌ отмена', '/cancel']:
            self.states[user_id] = None
            self.send(user_id, "Действие отменено.", get_main_keyboard(is_admin))
            return

        # === СМЕНА НИКА ===
        if text_lower.startswith('!nick ') or text_lower.startswith('/nick '):
            new_nick = text[6:]
            db.update(user_id, 'nickname', new_nick)
            self.send(user_id, f"✅ Ник изменен на: {new_nick}", get_main_keyboard(is_admin))
            return

        # === ЛОГИКА ДИАЛОГОВ (ЕСЛИ ЖДЕМ ОТВЕТ) ===
        state = self.states.get(user_id)

        if state == "WAIT_NORMA":
            self.temp[user_id] = text
            self.states[user_id] = "WAIT_PHOTO_NORMA"
            self.send(user_id, "📸 Теперь пришли скриншот /time или /astats", get_cancel_keyboard())
            return

        if state == "WAIT_PHOTO_NORMA":
            if event.object.message['attachments']:
                self.send(user_id, "✅ Норма отправлена!", get_main_keyboard(is_admin))
                # Пересылка создателю
                self.vk.messages.send(
                    peer_id=CONFIG['owner_id'], 
                    message=f"📩 НОРМА от @id{user_id}\n\n{self.temp[user_id]}",
                    random_id=get_random_id(),
                    forward_messages=event.object.message['id']
                )
                self.states[user_id] = None
            else:
                self.send(user_id, "❌ Нужен скриншот! (или напиши 'Отмена')")
            return

        if state == "WAIT_EXTRA":
            self.temp[user_id] = text
            self.states[user_id] = "WAIT_PHOTO_EXTRA"
            self.send(user_id, "📸 Прикрепи доказательства работы:", get_cancel_keyboard())
            return
            
        if state == "WAIT_PHOTO_EXTRA":
            if event.object.message['attachments']:
                self.send(user_id, "✅ Доп. отчет отправлен!", get_main_keyboard(is_admin))
                self.vk.messages.send(
                    peer_id=CONFIG['owner_id'], 
                    message=f"📈 ДОП. ОТЧЕТ от @id{user_id}\n\n{self.temp[user_id]}",
                    random_id=get_random_id(),
                    forward_messages=event.object.message['id']
                )
                self.states[user_id] = None
            else:
                self.send(user_id, "❌ Нужен скриншот!")
            return

        if state == "WAIT_INACTIVE":
            self.send(user_id, "✅ Заявка на неактив отправлена.", get_main_keyboard(is_admin))
            self.vk.messages.send(
                peer_id=CONFIG['owner_id'], 
                message=f"💤 НЕАКТИВ от @id{user_id}\n\n{text}",
                random_id=get_random_id()
            )
            self.states[user_id] = None
            return

        # === ОБРАБОТКА КНОПОК ===
        if text == "📩 Норма":
            self.states[user_id] = "WAIT_NORMA"
            self.send(user_id, f"📝 Скопируй и заполни:\n\n{T_NORMA}", get_cancel_keyboard())
        
        elif text == "📈 Доп. отчет":
            self.states[user_id] = "WAIT_EXTRA"
            self.send(user_id, f"📝 Скопируй и заполни:\n\n{T_EXTRA}", get_cancel_keyboard())

        elif text == "🕓 Неактив":
            self.states[user_id] = "WAIT_INACTIVE"
            self.send(user_id, f"📝 Причина и даты:\n\n{T_INACTIVE}", get_cancel_keyboard())

        elif text == "📜 Профиль":
            info = f"👤 Ник: {user_db[1]}\n🔰 Роль: {user_db[3]}\n📊 Уровень: {user_db[2]}"
            self.send(user_id, info, get_main_keyboard(is_admin))

        elif text == "⚙ Админ-панель" and is_admin:
            self.send(user_id, "Команды админа:\n!setlvl [ID] [LVL] - выдать права", get_main_keyboard(is_admin))

        elif text.startswith("!setlvl") and is_admin:
            try:
                parts = text.split()
                tid = int(parts[1].split('|')[0].replace('[id','').replace(']',''))
                tlvl = int(parts[2])
                db.update(tid, 'lvl', tlvl)
                name_role = "Администратор" if tlvl > 0 else "Игрок"
                db.update(tid, 'prefix', name_role)
                self.send(user_id, f"✅ Выдан уровень {tlvl}")
                self.send(tid, f"🎉 Вам выданы права: {name_role}", get_main_keyboard(True))
            except:
                self.send(user_id, "Ошибка команды. !setlvl ID LEVEL")

        else:
            # ЕСЛИ КОМАНДА НЕИЗВЕСТНА -> ПОКАЗАТЬ МЕНЮ
            self.send(user_id, "Я не понял команду. Вот меню:", get_main_keyboard(is_admin))

if __name__ == "__main__":
    bot = Bot()
    bot.run()
