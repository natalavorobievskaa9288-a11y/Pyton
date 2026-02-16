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
    # Твой токен:
    "token": "vk1.a.wshvI2ztLe5xObZOEVxC7jvywJISUuHO2GHqm_OS40jPFA8j0NBSs_QR4G5QSfuWXRkJihdrdUiEVTIPCb3wszdQTx7miFf71BSeB28NHeSU0ErnOMz77D8Qt0SHVjYuLf7FzgA0KgSp3eRUrdQFihhjAbE5uFM9zUzvOJBZkrBwXyY0j7zNLtjpBSSgJi0xDG10EBULjT2iQ5pxkJhxpg",
    
    # ID твоей группы:
    "group_id": 1771275401,
    
    # ТВОЙ ID (Я вставил его сюда):
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
        # Таблица пользователей
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
        # Таблица неактивов
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

# Инициализация БД
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
        # Кнопки под сообщением (Inline)
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
            print(f"Ошибка отправки сообщения пользователю {peer_id}: {e}")

    def run(self):
        print(f"🤖 Бот запущен! Работаем в группе ID: {CONFIG['group_id']}")
        
        while True:
            try:
                for event in self.longpoll.listen():
                    # 1. Нажатие на кнопки (Callback)
                    if event.type == VkBotEventType.MESSAGE_EVENT:
                        self.handle_callback(event)

                    # 2. Новое сообщение
                    elif event.type == VkBotEventType.MESSAGE_NEW:
                        if event.from_user:
                            self.handle_message(event)
            except Exception as e:
                print(f"⚠ Ошибка соединения или API: {e}")
                time.sleep(3) # Ждем 3 секунды и пробуем снова

    def handle_callback(self, event):
        try:
            payload = event.object.payload
            user_id = event.obj.peer_id
            
            # Проверка прав
            admin_data = db.get_user(user_id)
            if admin_data[2] < 1 and user_id != CONFIG['owner_id']:
                self.vk.messages.sendMessageEventAnswer(
                    event_id=event.object.event_id,
                    user_id=user_id,
                    peer_id=user_id,
                    event_data='{"type": "show_snackbar", "text": "❌ У вас нет прав!"}'
                )
                return

            if payload.get('type') == 'inactive_ok':
                in_id = payload['id']
                db.update_inactive_status(in_id, "Одобрено")
                req_data = db.get_inactive(in_id)
                requester_id = req_data[1]
                
                self.vk.messages.edit(
                    peer_id=user_id,
                    conversation_message_id=event.obj.conversation_message_id,
                    message=f"✅ Заявка #{in_id} ОДОБРЕНА администратором @id{user_id}.",
                    keyboard=None
                )
                self.send(requester_id, f"✅ Ваш неактив (#{in_id}) был одобрен!")

            elif payload.get('type') == 'inactive_no':
                in_id = payload['id']
                db.update_inactive_status(in_id, "Отказано")
                req_data = db.get_inactive(in_id)
                requester_id = req_data[1]

                self.vk.messages.edit(
                    peer_id=user_id,
                    conversation_message_id=event.obj.conversation_message_id,
                    message=f"❌ Заявка #{in_id} ОТКЛОНЕНА администратором @id{user_id}.",
                    keyboard=None
                )
                self.send(requester_id, f"❌ Ваш неактив (#{in_id}) был отклонен.")
        except Exception as e:
            print(f"Ошибка в callback: {e}")

    def handle_message(self, event):
        msg = event.object.message['text']
        user_id = event.object.message['from_id']
        
        user_db = db.get_user(user_id)
        is_admin = (user_db[2] > 0) or (user_id == CONFIG['owner_id'])
        
        # Авто-выдача создателя
        if user_id == CONFIG['owner_id'] and user_db[2] == 0:
            db.update_user(user_id, 'lvl', 5)
            db.update_user(user_id, 'prefix', 'Создатель')
            self.send(user_id, "✨ Вы распознаны как Создатель. Права выданы.")
            is_admin = True

        state = self.states.get(user_id)

        # === ГЛОБАЛЬНЫЕ КОМАНДЫ ===
        if msg == "❌ Отмена" or msg.lower() == "/cancel":
            self.states[user_id] = None
            self.temp_data[user_id] = {}
            self.send(user_id, "Действие отменено.", Keyboards.main(is_admin))
            return
        
        if msg == "🔙 В меню":
            self.states[user_id] = None
            self.send(user_id, "Главное меню", Keyboards.main(is_admin))
            return

        # === ДИАЛОГИ (Сценарии) ===
        
        # 1. Подача нормы (Фото)
        if state == "WAIT_NORM_PHOTO":
            attachments = event.object.message['attachments']
            is_photo = False
            for att in attachments:
                if att['type'] == 'photo':
                    is_photo = True
                    break
            
            if is_photo:
                self.send(user_id, "✅ Отчет принят! Руководство проверит его.", Keyboards.main(is_admin))
                
                # Отправляем создателю уведомление (пересылаем фото)
                try:
                    admin_text = f"🔔 НОВЫЙ ОТЧЕТ\n👤 От: @id{user_id}\n📝 Статус: На проверке"
                    self.vk.messages.send(
                        peer_id=CONFIG['owner_id'],
                        message=admin_text,
                        random_id=get_random_id(),
                        forward_messages=event.object.message['id']
                    )
                except:
                    pass
                
                self.states[user_id] = None
            else:
                self.send(user_id, "❌ Прикрепите скриншот /astats! (Или нажмите Отмена)", Keyboards.cancel())
            return

        # 2. Неактив (Даты)
        if state == "WAIT_INACTIVE_DATES":
            self.temp_data[user_id] = {'dates': msg}
            self.states[user_id] = "WAIT_INACTIVE_REASON"
            self.send(user_id, "📝 Укажите причину неактива:", Keyboards.cancel())
            return

        # 3. Неактив (Причина)
        if state == "WAIT_INACTIVE_REASON":
            dates = self.temp_data[user_id].get('dates', 'Не указано')
            reason = msg
            
            in_id = db.add_inactive(user_id, dates, dates, reason)
            
            self.send(user_id, f"✅ Заявка #{in_id} отправлена на рассмотрение.", Keyboards.main(is_admin))
            self.states[user_id] = None
            
            # Уведомление создателю
            admin_msg = (
                f"💤 ЗАЯВКА НА НЕАКТИВ #{in_id}\n"
                f"👤 От: @id{user_id}\n"
                f"📅 Даты: {dates}\n"
                f"💬 Причина: {reason}"
            )
            # Отправляем админу сообщение с кнопками Одобрить/Отказать
            self.send(CONFIG['owner_id'], admin_msg, Keyboards.inactive_decision(in_id))
            return

        # 4. Смена ника
        if msg.lower().startswith("/nick "):
            new_nick = msg[6:]
            if len(new_nick) > 30:
                self.send(user_id, "❌ Слишком длинный ник.")
            else:
                db.update_user(user_id, 'nickname', new_nick)
                self.send(user_id, f"✅ Ваш ник изменен на: {new_nick}")
            return

        # === МЕНЮ И КНОПКИ ===

        if msg == "📜 Моя статистика":
            reg_dt = user_db[4]
            try:
                days = (datetime.datetime.now() - datetime.datetime.strptime(reg_dt, "%d.%m.%Y")).days
            except: days = 0

            text = (
                f"📊 ADMIN STATISTICS\n"
                f"➖➖➖➖➖➖➖➖➖➖\n"
                f"👤 Ник: {user_db[1]}\n"
                f"🆔 ID: {user_id}\n"
                f"🔰 Должность: {user_db[3]} (Lvl {user_db[2]})\n"
                f"📅 На посту: {days} дн. ({reg_dt})\n"
                f"➖➖➖➖➖➖➖➖➖➖\n"
                f"✅ Норма (дней): {user_db[5]}\n"
                f"✉ Ответов: {user_db[6]}\n"
                f"⚠ Выговоров: {user_db[7]}\n"
                f"➖➖➖➖➖➖➖➖➖➖\n"
                f"⚙ Для смены ника пиши: /nick Имя"
            )
            self.send(user_id, text)

        elif msg == "📩 Отправить норму":
            self.states[user_id] = "WAIT_NORM_PHOTO"
            self.send(user_id, "📸 Пожалуйста, отправьте скриншот вашей статистики (/astats).", Keyboards.cancel())

        elif msg == "🕓 Неактив":
            self.states[user_id] = "WAIT_INACTIVE_DATES"
            self.send(user_id, "📅 Введите даты неактива (Например: 20.02 - 22.02):", Keyboards.cancel())

        elif msg == "👑 Админ Панель" and is_admin:
            self.send(user_id, "🔒 Добро пожаловать в панель управления.", Keyboards.admin_panel())

        elif msg == "💤 Заявки неактив" and is_admin:
            conn = sqlite3.connect(CONFIG['db_file'])
            cur = conn.cursor()
            cur.execute("SELECT * FROM inactives WHERE status='wait' ORDER BY id DESC LIMIT 5")
            rows = cur.fetchall()
            conn.close()

            if not rows:
                self.send(user_id, "📭 Новых заявок на неактив нет.")
            else:
                self.send(user_id, f"Найдено {len(rows)} активных заявок:")
                for row in rows:
                    txt = (
                        f"🔹 Заявка #{row[0]}\n"
                        f"👤 User: @id{row[1]}\n"
                        f"📅 {row[2]}\n"
                        f"💬 {row[4]}"
                    )
                    self.send(user_id, txt, Keyboards.inactive_decision(row[0]))

        # Команды выдачи админки
        elif msg.startswith("!setlvl") and is_admin:
            # !setlvl @id 3
            try:
                parts = msg.split()
                if len(parts) < 3:
                    self.send(user_id, "Ошибка. Формат: !setlvl [ID] [Уровень]")
                    return
                
                target = parts[1]
                lvl = int(parts[2])
                
                target_id = user_id 
                if "[id" in target:
                    target_id = int(target.split('|')[0].replace('[id', ''))
                elif target.isdigit():
                    target_id = int(target)
                else:
                    self.send(user_id, "Укажите ID через упоминание @ или цифрами.")
                    return
                
                db.get_user(target_id)
                db.update_user(target_id, 'lvl', lvl)
                
                titles = {1: "Мл. Модератор", 2: "Модератор", 3: "Ст. Модератор", 4: "Администратор", 5: "Гл. Администратор"}
                title = titles.get(lvl, "Администратор")
                db.update_user(target_id, 'prefix', title)

                self.send(user_id, f"✅ Пользователю @id{target_id} выдан уровень {lvl} ({title}).")
                self.send(target_id, f"🎉 Вам выданы права администратора уровня {lvl}!")

            except Exception as e:
                self.send(user_id, f"❌ Ошибка: {e}")

        else:
            if not is_admin and state is None:
                self.send(user_id, "🏠 Главное меню", Keyboards.main(is_admin))

if __name__ == "__main__":
    bot = AdminBot()
    bot.run()
