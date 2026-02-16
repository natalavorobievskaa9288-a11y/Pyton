# -*- coding: utf-8 -*-
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
import sqlite3
import datetime
import time
import os

# ================= КОНФИГУРАЦИЯ =================
CONFIG = {
    # Токен (проверь, что он от этой же группы!)
    "token": "vk1.a.wshvI2ztLe5xObZOEVxC7jvywJISUuHO2GHqm_OS40jPFA8j0NBSs_QR4G5QSfuWXRkJihdrdUiEVTIPCb3wszdQTx7miFf71BSeB28NHeSU0ErnOMz77D8Qt0SHVjYuLf7FzgA0KgSp3eRUrdQFihhjAbE5uFM9zUzvOJBZkrBwXyY0j7zNLtjpBSSgJi0xDG10EBULjT2iQ5pxkJhxpg",
    
    # ИСПРАВЛЕННЫЙ ID ГРУППЫ (из твоих логов):
    "group_id": 1771275981,
    
    # ТВОЙ ID:
    "owner_id": 864765284,
    
    "db_file": "server_bot.db"
}

# ================= МЕНЕДЖЕР БАЗЫ ДАННЫХ =================
class Database:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                nickname TEXT DEFAULT 'Не указан',
                lvl INTEGER DEFAULT 0,
                prefix TEXT DEFAULT 'Игрок',
                reg_date TEXT,
                norma_days INTEGER DEFAULT 0,
                answers INTEGER DEFAULT 0,
                warns INTEGER DEFAULT 0
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS inactives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date_start TEXT,
                date_end TEXT,
                reason TEXT,
                status TEXT DEFAULT 'wait' 
            )
        ''')
        self.conn.commit()

    def get_user(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        result = self.cursor.fetchone()
        if not result:
            now = datetime.datetime.now().strftime("%d.%m.%Y")
            self.cursor.execute("INSERT INTO users (user_id, reg_date) VALUES (?, ?)", (user_id, now))
            self.conn.commit()
            return self.get_user(user_id)
        return result

    def update_user(self, user_id, column, value):
        if isinstance(value, str) and (value.startswith('+') or value.startswith('-')):
             self.cursor.execute(f"UPDATE users SET {column} = {column} + ? WHERE user_id = ?", (int(value), user_id))
        else:
            self.cursor.execute(f"UPDATE users SET {column} = ? WHERE user_id = ?", (value, user_id))
        self.conn.commit()

    def add_inactive(self, user_id, d_start, d_end, reason):
        self.cursor.execute("INSERT INTO inactives (user_id, date_start, date_end, reason) VALUES (?, ?, ?, ?)", 
                            (user_id, d_start, d_end, reason))
        self.conn.commit()
        return self.cursor.lastrowid

    def update_inactive_status(self, inactive_id, status):
        self.cursor.execute("UPDATE inactives SET status = ? WHERE id = ?", (status, inactive_id))
        self.conn.commit()
        
    def get_inactive(self, inactive_id):
        self.cursor.execute("SELECT * FROM inactives WHERE id = ?", (inactive_id,))
        return self.cursor.fetchone()

db = Database(CONFIG['db_file'])

# ================= КЛАВИАТУРЫ =================
class Keyboards:
    @staticmethod
    def main(is_admin=False):
        kb = VkKeyboard(one_time=False)
        kb.add_button("📜 Моя статистика", color=VkKeyboardColor.PRIMARY)
        kb.add_line()
        kb.add_button("📩 Отправить норму", color=VkKeyboardColor.POSITIVE)
        kb.add_button("🕓 Неактив", color=VkKeyboardColor.SECONDARY)
        if is_admin:
            kb.add_line()
            kb.add_button("👑 Админ Панель", color=VkKeyboardColor.NEGATIVE)
        return kb.get_keyboard()

    @staticmethod
    def admin_panel():
        kb = VkKeyboard(one_time=False)
        kb.add_button("🔍 Проверить норму", color=VkKeyboardColor.PRIMARY)
        kb.add_button("💤 Заявки неактив", color=VkKeyboardColor.PRIMARY)
        kb.add_line()
        kb.add_button("⚙ Управление", color=VkKeyboardColor.SECONDARY)
        kb.add_button("🔙 В меню", color=VkKeyboardColor.NEGATIVE)
        return kb.get_keyboard()

    @staticmethod
    def cancel():
        kb = VkKeyboard(one_time=False)
        kb.add_button("❌ Отмена", color=VkKeyboardColor.NEGATIVE)
        return kb.get_keyboard()

    @staticmethod
    def inactive_decision(inactive_id):
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("✅ Одобрить", color=VkKeyboardColor.POSITIVE, payload={"type": "inactive_ok", "id": inactive_id})
        kb.add_callback_button("❌ Отказать", color=VkKeyboardColor.NEGATIVE, payload={"type": "inactive_no", "id": inactive_id})
        return kb.get_keyboard()

# ================= ЛОГИКА БОТА =================
class AdminBot:
    def __init__(self):
        print("Авторизация в ВК...")
        self.vk_session = vk_api.VkApi(token=CONFIG['token'])
        self.vk = self.vk_session.get_api()
        self.longpoll = VkBotLongPoll(self.vk_session, CONFIG['group_id'])
        self.states = {} 
        self.temp_data = {} 

    def send(self, peer_id, text, keyboard=None, attachment=None):
        try:
            self.vk.messages.send(
                peer_id=peer_id,
                message=text,
                random_id=get_random_id(),
                keyboard=keyboard,
                attachment=attachment
            )
        except Exception as e:
            print(f"Ошибка отправки: {e}")

    def run(self):
        print(f"🤖 Бот запущен! Группа ID: {CONFIG['group_id']}")
        while True:
            try:
                for event in self.longpoll.listen():
                    if event.type == VkBotEventType.MESSAGE_EVENT:
                        self.handle_callback(event)
                    elif event.type == VkBotEventType.MESSAGE_NEW:
                        if event.from_user:
                            self.handle_message(event)
            except Exception as e:
                print(f"⚠ Ошибка API (перезапуск через 3с): {e}")
                time.sleep(3)

    def handle_callback(self, event):
        try:
            payload = event.object.payload
            user_id = event.obj.peer_id
            admin_data = db.get_user(user_id)
            if admin_data[2] < 1 and user_id != CONFIG['owner_id']:
                return

            if payload.get('type') == 'inactive_ok':
                in_id = payload['id']
                db.update_inactive_status(in_id, "Одобрено")
                req_data = db.get_inactive(in_id)
                self.vk.messages.edit(
                    peer_id=user_id,
                    conversation_message_id=event.obj.conversation_message_id,
                    message=f"✅ Заявка #{in_id} ОДОБРЕНА.", keyboard=None
                )
                self.send(req_data[1], f"✅ Ваш неактив (#{in_id}) одобрен!")

            elif payload.get('type') == 'inactive_no':
                in_id = payload['id']
                db.update_inactive_status(in_id, "Отказано")
                req_data = db.get_inactive(in_id)
                self.vk.messages.edit(
                    peer_id=user_id,
                    conversation_message_id=event.obj.conversation_message_id,
                    message=f"❌ Заявка #{in_id} ОТКЛОНЕНА.", keyboard=None
                )
                self.send(req_data[1], f"❌ Ваш неактив (#{in_id}) отклонен.")
        except: pass

    def handle_message(self, event):
        msg = event.object.message['text']
        user_id = event.object.message['from_id']
        user_db = db.get_user(user_id)
        is_admin = (user_db[2] > 0) or (user_id == CONFIG['owner_id'])
        
        if user_id == CONFIG['owner_id'] and user_db[2] == 0:
            db.update_user(user_id, 'lvl', 5)
            db.update_user(user_id, 'prefix', 'Создатель')
            self.send(user_id, "✨ Вы Создатель. Права выданы.")
            is_admin = True

        state = self.states.get(user_id)

        if msg == "❌ Отмена" or msg.lower() == "/cancel":
            self.states[user_id] = None
            self.send(user_id, "Отменено.", Keyboards.main(is_admin))
            return
        
        if msg == "🔙 В меню":
            self.states[user_id] = None
            self.send(user_id, "Главное меню", Keyboards.main(is_admin))
            return

        if state == "WAIT_NORM_PHOTO":
            if event.object.message['attachments']:
                self.send(user_id, "✅ Отчет отправлен.", Keyboards.main(is_admin))
                try:
                    self.vk.messages.send(peer_id=CONFIG['owner_id'], message=f"🔔 НОВЫЙ ОТЧЕТ от @id{user_id}", random_id=get_random_id(), forward_messages=event.object.message['id'])
                except: pass
                self.states[user_id] = None
            else:
                self.send(user_id, "❌ Пришлите фото!", Keyboards.cancel())
            return

        if state == "WAIT_INACTIVE_DATES":
            self.temp_data[user_id] = {'dates': msg}
            self.states[user_id] = "WAIT_INACTIVE_REASON"
            self.send(user_id, "📝 Причина неактива:", Keyboards.cancel())
            return

        if state == "WAIT_INACTIVE_REASON":
            dates = self.temp_data[user_id].get('dates')
            in_id = db.add_inactive(user_id, dates, dates, msg)
            self.send(user_id, "✅ Заявка отправлена.", Keyboards.main(is_admin))
            self.states[user_id] = None
            self.send(CONFIG['owner_id'], f"💤 ЗАЯВКА #{in_id}\n👤 @id{user_id}\n📅 {dates}\n💬 {msg}", Keyboards.inactive_decision(in_id))
            return

        if msg.lower().startswith("/nick "):
            db.update_user(user_id, 'nickname', msg[6:])
            self.send(user_id, f"✅ Ник: {msg[6:]}")
            return

        if msg == "📜 Моя статистика":
            text = f"📊 СТАТИСТИКА\n👤 {user_db[1]}\n🔰 {user_db[3]}\n✅ Норма: {user_db[5]}\n✉ Ответов: {user_db[6]}"
            self.send(user_id, text)
        
        elif msg == "📩 Отправить норму":
            self.states[user_id] = "WAIT_NORM_PHOTO"
            self.send(user_id, "📸 Жду скриншот.", Keyboards.cancel())

        elif msg == "🕓 Неактив":
            self.states[user_id] = "WAIT_INACTIVE_DATES"
            self.send(user_id, "📅 Даты (с..по):", Keyboards.cancel())

        elif msg == "👑 Админ Панель" and is_admin:
            self.send(user_id, "Админ панель:", Keyboards.admin_panel())

        elif msg == "💤 Заявки неактив" and is_admin:
            conn = sqlite3.connect(CONFIG['db_file'])
            cur = conn.cursor()
            cur.execute("SELECT * FROM inactives WHERE status='wait' LIMIT 5")
            rows = cur.fetchall()
            conn.close()
            if rows:
                for r in rows: self.send(user_id, f"Заявка #{r[0]}\nUser: @id{r[1]}\nПричина: {r[4]}", Keyboards.inactive_decision(r[0]))
            else: self.send(user_id, "Нет заявок.")

        elif msg.startswith("!setlvl") and is_admin:
            try:
                parts = msg.split()
                target = int(parts[1]) if parts[1].isdigit() else int(parts[1].split('|')[0].replace('[id', ''))
                lvl = int(parts[2])
                db.get_user(target)
                db.update_user(target, 'lvl', lvl)
                titles = {1:"Мл.Модер", 5:"Гл.Админ"}
                db.update_user(target, 'prefix', titles.get(lvl, "Админ"))
                self.send(user_id, f"✅ Выдан {lvl} уровень.")
                self.send(target, f"🎉 Вам выдан {lvl} уровень!")
            except: self.send(user_id, "Ошибка команды.")

        else:
            if not is_admin: self.send(user_id, "Меню", Keyboards.main(is_admin))
            
if __name__ == "__main__":
    bot = AdminBot()
    bot.run()
