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
    # Твой токен:
    "token": "vk1.a.Z9pCqT1rlC8JsFxbrZMhhmvbPe764cfFlF9N1z5RG4nrLfO9E8YisGaABMzphZNjMOZ01Y4A25SAdRZnvVSO2mxmOUq2AiOsPkNmmQXH_6ghpstHBPiPjxZv-c6t8JL8JV1qbmOpFPTTSOx8_CAfsKFaMqa9_-BXqLW4LbeR2fyyncJMlHHpTsfcjLWXtZYJu1rJSUDPp4zoCoVcOpaE5A",
    
    # ID ТВОЕЙ ГРУППЫ:
    "group_id": 236066012,
    
    # Твой ID (Куда будут приходить отчеты):
    "owner_id": 864765284,
    
    "db_file": "server_bot.db"
}

# ================= ШАБЛОНЫ СООБЩЕНИЙ =================
TEMPLATE_NORMA = """Скопируй шаблон ниже, заполни и отправь:

1 - NickName:
2 - Уровень администратора:
3 - Должность:
4 - Дата отчёта:
5 - /astats:"""

TEMPLATE_EXTRA = """Скопируй шаблон ниже, заполни и отправь:

1. NickName:
2. Уровень админ-прав:
3. Должность:
4. За какой день подается отчёт:
5. Какая работа была проделана:
6. Скриншоты проделанной работы:"""

TEMPLATE_INACTIVE = """Скопируй шаблон ниже, заполни и отправь:

1. Ваш NickName:
2. Уровень админ прав:
3. Занимаемая должность:
4. Подменяющее лицо:
5. Кто из главной администрации предупрежден:
6. Дата неактива (какие дни):
7. Причина неактива:"""

WELCOME_TEXT = """👋 Добро пожаловать в бота Admin Assistant!

Я помогаю сдавать отчеты и брать неактивы.
Используй кнопки внизу для управления.

📌 Доступные команды:
!nick [Ник] — Установить свой ник
!setlvl [ID] [LVL] — Выдать админку (только для гл. админа)
Начать — Вызов этого меню

👇 Выберите действие на клавиатуре:"""

# ================= БАЗА ДАННЫХ =================
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
        self.cursor.execute(f"UPDATE users SET {column} = ? WHERE user_id = ?", (value, user_id))
        self.conn.commit()

db = Database(CONFIG['db_file'])

# ================= КЛАВИАТУРЫ =================
class Keyboards:
    @staticmethod
    def main(is_admin=False):
        # one_time=False ВАЖНО, чтобы кнопки не исчезали
        kb = VkKeyboard(one_time=False)
        
        kb.add_button("📩 Норма", color=VkKeyboardColor.POSITIVE)
        kb.add_button("📈 Доп. отчёт", color=VkKeyboardColor.PRIMARY)
        kb.add_line()
        kb.add_button("🕓 Неактив", color=VkKeyboardColor.SECONDARY)
        kb.add_button("📜 Статистика", color=VkKeyboardColor.SECONDARY)
        
        if is_admin:
            kb.add_line()
            kb.add_button("👑 Админ-панель", color=VkKeyboardColor.NEGATIVE)
        return kb.get_keyboard()

    @staticmethod
    def cancel():
        kb = VkKeyboard(one_time=False)
        kb.add_button("❌ Отмена", color=VkKeyboardColor.NEGATIVE)
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
                    if event.type == VkBotEventType.MESSAGE_NEW and event.from_user:
                        self.handle_message(event)
            except Exception as e:
                print(f"⚠ Ошибка API (перезапуск через 3с): {e}")
                time.sleep(3)

    def handle_message(self, event):
        msg = event.object.message['text']
        user_id = event.object.message['from_id']
        user_db = db.get_user(user_id)
        
        # Проверка прав админа
        is_admin = (user_db[2] > 0) or (user_id == CONFIG['owner_id'])
        if user_id == CONFIG['owner_id'] and user_db[2] == 0:
            db.update_user(user_id, 'lvl', 5)
            db.update_user(user_id, 'prefix', 'Создатель')
            is_admin = True
            self.send(user_id, "✨ Вы распознаны как Создатель.", Keyboards.main(True))

        state = self.states.get(user_id)

        # === ГЛОБАЛЬНЫЕ КОМАНДЫ ===
        if msg.lower() in ["начать", "start", "/start", "меню"]:
            self.states[user_id] = None
            self.send(user_id, WELCOME_TEXT, Keyboards.main(is_admin))
            return

        if msg == "❌ Отмена" or msg.lower() == "/cancel":
            self.states[user_id] = None
            self.send(user_id, "Действие отменено.", Keyboards.main(is_admin))
            return
        
        # === ОБРАБОТКА СОСТОЯНИЙ (Диалоги) ===
        
        # 1. ОБРАБОТКА НОРМЫ
        if state == "WAIT_NORMA_TEXT":
            self.temp_data[user_id] = {'text': msg}
            self.states[user_id] = "WAIT_NORMA_PHOTO"
            self.send(user_id, "📸 Теперь прикрепите скриншот /astats (время в игре).", Keyboards.cancel())
            return
            
        if state == "WAIT_NORMA_PHOTO":
            if event.object.message['attachments']:
                # Пересылаем сообщение создателю
                self.vk.messages.send(
                    peer_id=CONFIG['owner_id'],
                    message=f"📩 НОВАЯ НОРМА от @id{user_id}\n\n{self.temp_data[user_id]['text']}",
                    random_id=get_random_id(),
                    forward_messages=event.object.message['id']
                )
                self.send(user_id, "✅ Норма успешно отправлена руководству!", Keyboards.main(is_admin))
                db.update_user(user_id, 'norma_days', int(user_db[5]) + 1)
                self.states[user_id] = None
            else:
                self.send(user_id, "❌ Пришлите скриншот, или нажмите Отмена.", Keyboards.cancel())
            return

        # 2. ОБРАБОТКА ДОП. РЕПОРТА
        if state == "WAIT_EXTRA_TEXT":
            self.temp_data[user_id] = {'text': msg}
            self.states[user_id] = "WAIT_EXTRA_PHOTO"
            self.send(user_id, "📸 Прикрепите доказательства (скриншоты).", Keyboards.cancel())
            return

        if state == "WAIT_EXTRA_PHOTO":
            if event.object.message['attachments']:
                self.vk.messages.send(
                    peer_id=CONFIG['owner_id'],
                    message=f"📈 ДОП. ОТЧЕТ от @id{user_id}\n\n{self.temp_data[user_id]['text']}",
                    random_id=get_random_id(),
                    forward_messages=event.object.message['id']
                )
                self.send(user_id, "✅ Доп. отчет отправлен!", Keyboards.main(is_admin))
                self.states[user_id] = None
            else:
                self.send(user_id, "❌ Пришлите скриншот работы.", Keyboards.cancel())
            return

        # 3. ОБРАБОТКА НЕАКТИВА
        if state == "WAIT_INACTIVE_TEXT":
            self.vk.messages.send(
                peer_id=CONFIG['owner_id'],
                message=f"💤 ЗАЯВЛЕНИЕ НА НЕАКТИВ от @id{user_id}\n\n{msg}",
                random_id=get_random_id()
            )
            self.send(user_id, "✅ Заявка на неактив отправлена руководству.", Keyboards.main(is_admin))
            self.states[user_id] = None
            return

        # === ОБРАБОТКА КНОПОК МЕНЮ ===

        if msg == "📩 Норма":
            self.states[user_id] = "WAIT_NORMA_TEXT"
            self.send(user_id, TEMPLATE_NORMA, Keyboards.cancel())
        
        elif msg == "📈 Доп. отчёт":
            self.states[user_id] = "WAIT_EXTRA_TEXT"
            self.send(user_id, TEMPLATE_EXTRA, Keyboards.cancel())

        elif msg == "🕓 Неактив":
            self.states[user_id] = "WAIT_INACTIVE_TEXT"
            self.send(user_id, TEMPLATE_INACTIVE, Keyboards.cancel())

        elif msg == "📜 Статистика":
            text = f"📊 ТВОЯ СТАТИСТИКА:\n👤 Ник: {user_db[1]}\n🔰 Ранг: {user_db[3]} (Lvl {user_db[2]})\n✅ Сдано норм: {user_db[5]}"
            self.send(user_id, text, Keyboards.main(is_admin))

        elif msg.startswith("!nick "):
            new_nick = msg[6:]
            db.update_user(user_id, 'nickname', new_nick)
            self.send(user_id, f"✅ Ваш ник обновлен: {new_nick}")

        elif msg.startswith("!setlvl") and is_admin:
            try:
                parts = msg.split()
                if '[id' in parts[1]:
                    target = int(parts[1].split('|')[0].replace('[id', ''))
                else:
                    target = int(parts[1])
                lvl = int(parts[2])
                db.get_user(target)
                db.update_user(target, 'lvl', lvl)
                roles = {0:"Игрок", 1:"Мл.Модер", 2:"Модер", 3:"Ст.Модер", 4:"Админ", 5:"Куратор", 6:"ЗГА", 7:"ГА"}
                role_name = roles.get(lvl, "Спец.Админ")
                db.update_user(target, 'prefix', role_name)
                
                self.send(user_id, f"✅ Игроку @id{target} выдан {lvl} уровень ({role_name}).")
                self.send(target, f"🎉 Вам выдан администраторский уровень: {lvl} ({role_name})!", Keyboards.main(True))
            except:
                self.send(user_id, "Ошибка! Пиши: !setlvl [ID] [Уровень (1-7)]")

        else:
            # Если команда не понятна, но мы не в режиме ожидания отчета
            if user_id not in self.states or self.states[user_id] is None:
                self.send(user_id, "ℹ Используйте кнопки меню.", Keyboards.main(is_admin))

if __name__ == "__main__":
    bot = AdminBot()
    bot.run()
