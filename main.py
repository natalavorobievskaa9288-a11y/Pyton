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

# ================= ШАБЛОНЫ СООБЩЕНИЙ =================
TEMPLATE_NORMA = """📋 Скопируй шаблон ниже, заполни и отправь:

1 - NickName:
2 - Уровень администратора:
3 - Должность:
4 - Дата отчёта:
5 - /astats:"""

TEMPLATE_EXTRA = """📋 Скопируй шаблон ниже, заполни и отправь:

1. NickName:
2. Уровень админ-прав:
3. Должность:
4. За какой день подается отчёт:
5. Какая работа была проделана:
6. Скриншоты проделанной работы:"""

TEMPLATE_INACTIVE = """📋 Скопируй шаблон ниже, заполни и отправь:

1. Ваш NickName:
2. Уровень админ прав:
3. Занимаемая должность:
4. Подменяющее лицо:
5. Кто из главной администрации предупрежден:
6. Дата неактива (какие дни):
7. Причина неактива:"""

# Приветствие для обычных пользователей
WELCOME_TEXT_USER = """👋 Добро пожаловать в бота Admin Assistant!

🤖 Я помогаю сдавать отчеты и брать неактивы.

━━━━━━━━━━━━━━━━━━━━━━
📝 ШАБЛОНЫ ОТЧЕТОВ:
━━━━━━━━━━━━━━━━━━━━━━

1️⃣ НОРМА (ежедневный отчет)
Отчёт скидываем строго по форме, до 00:30 
иначе отчёт будет не засчитан.

2️⃣ ДОП. ОТЧЕТ (дополнительная работа)
Описание проделанной работы + скриншоты.

3️⃣ НЕАКТИВ (заявление на отсутствие)
Указать подменяющее лицо и причину.

━━━━━━━━━━━━━━━━━━━━━━
📱 КАК РАБОТАТЬ:
━━━━━━━━━━━━━━━━━━━━━━

• Используй кнопки для подачи отчетов
• Все заявки проверяются руководством
• Статистика сохраняется автоматически

👇 Выбери действие на клавиатуре:"""

# Приветствие для администраторов
WELCOME_TEXT_ADMIN = """👋 Добро пожаловать, Администратор!

🤖 Бот Admin Assistant - Система управления.

━━━━━━━━━━━━━━━━━━━━━━
📝 ШАБЛОНЫ ОТЧЕТОВ:
━━━━━━━━━━━━━━━━━━━━━━

1️⃣ НОРМА | 2️⃣ ДОП. ОТЧЕТ | 3️⃣ НЕАКТИВ

━━━━━━━━━━━━━━━━━━━━━━
👑 КОМАНДЫ АДМИНИСТРАТОРА:
━━━━━━━━━━━━━━━━━━━━━━

!setlvl [ID] [LVL] — Выдать админку
!dellvl [ID] — Снять админку
!nick [Ник] — Установить ник

/approve [ID] — Одобрить заявку
/reject [ID] — Отклонить заявку

━━━━━━━━━━━━━━━━━━━━━━
📱 УПРОЩЕНИЕ ДЛЯ АДМИНОВ:
━━━━━━━━━━━━━━━━━━━━━━

• Заявки приходят автоматически
• Одобрение/отклонение через команды
• Полная статистика по админам

👇 Выбери действие на клавиатуре:"""

# ================= БАЗА ДАННЫХ =================
class Database:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.migrate_database()

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
                warns INTEGER DEFAULT 0,
                notifications INTEGER DEFAULT 1
            )
        ''')
        
        # Таблица заявок
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                content TEXT,
                attachments TEXT,
                status TEXT DEFAULT 'pending',
                admin_id INTEGER,
                admin_comment TEXT,
                created_at TEXT,
                reviewed_at TEXT
            )
        ''')
        self.conn.commit()

    def migrate_database(self):
        """Миграция БД - добавление столбца notifications если его нет"""
        try:
            # Проверяем есть ли столбец notifications
            self.cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in self.cursor.fetchall()]
            
            if 'notifications' not in columns:
                print("🔄 Миграция БД: добавление столбца notifications...")
                self.cursor.execute("ALTER TABLE users ADD COLUMN notifications INTEGER DEFAULT 1")
                self.conn.commit()
                print("✅ Миграция завершена!")
        except Exception as e:
            print(f"⚠️ Ошибка миграции: {e}")

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

    def get_all_admins(self):
        self.cursor.execute("SELECT * FROM users WHERE lvl > 0 ORDER BY lvl DESC")
        return self.cursor.fetchall()

    # === РАБОТА С ЗАЯВКАМИ ===
    
    def create_request(self, user_id, req_type, content, attachments=None):
        """Создать новую заявку"""
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        self.cursor.execute('''
            INSERT INTO requests (user_id, type, content, attachments, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, req_type, content, attachments, now))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_request(self, req_id):
        """Получить заявку по ID"""
        self.cursor.execute("SELECT * FROM requests WHERE id = ?", (req_id,))
        return self.cursor.fetchone()

    def get_pending_requests(self):
        """Получить все ожидающие заявки"""
        self.cursor.execute("SELECT * FROM requests WHERE status = 'pending' ORDER BY created_at DESC")
        return self.cursor.fetchall()

    def update_request_status(self, req_id, status, admin_id, comment=None):
        """Обновить статус заявки"""
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        self.cursor.execute('''
            UPDATE requests 
            SET status = ?, admin_id = ?, admin_comment = ?, reviewed_at = ?
            WHERE id = ?
        ''', (status, admin_id, comment, now, req_id))
        self.conn.commit()

    def get_user_requests(self, user_id):
        """Получить все заявки пользователя"""
        self.cursor.execute("SELECT * FROM requests WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (user_id,))
        return self.cursor.fetchall()

db = Database(CONFIG['db_file'])

# ================= КЛАВИАТУРЫ =================
class Keyboards:
    @staticmethod
    def main(is_admin=False):
        kb = VkKeyboard(one_time=False)
        
        kb.add_button("📩 Норма", color=VkKeyboardColor.POSITIVE)
        kb.add_button("📈 Доп. отчёт", color=VkKeyboardColor.PRIMARY)
        kb.add_line()
        kb.add_button("🕓 Неактив", color=VkKeyboardColor.SECONDARY)
        kb.add_button("📜 Статистика", color=VkKeyboardColor.SECONDARY)
        
        if is_admin:
            kb.add_line()
            kb.add_button("👑 Админ-панель", color=VkKeyboardColor.NEGATIVE)
        
        kb.add_line()
        kb.add_button("⚙️ Настройки", color=VkKeyboardColor.PRIMARY)
        kb.add_button("ℹ️ Помощь", color=VkKeyboardColor.PRIMARY)
        
        return kb.get_keyboard()

    @staticmethod
    def cancel():
        kb = VkKeyboard(one_time=False)
        kb.add_button("❌ Отмена", color=VkKeyboardColor.NEGATIVE)
        return kb.get_keyboard()

    @staticmethod
    def admin_panel():
        kb = VkKeyboard(one_time=False)
        kb.add_button("📋 Заявки", color=VkKeyboardColor.POSITIVE)
        kb.add_button("👥 Админы", color=VkKeyboardColor.PRIMARY)
        kb.add_line()
        kb.add_button("➖ Снять админку", color=VkKeyboardColor.NEGATIVE)
        kb.add_button("❓ Как проверять", color=VkKeyboardColor.PRIMARY)
        kb.add_line()
        kb.add_button("⬅️ Назад в меню", color=VkKeyboardColor.SECONDARY)
        return kb.get_keyboard()

    @staticmethod
    def settings(notifications_on=True):
        kb = VkKeyboard(one_time=False)
        
        if notifications_on:
            kb.add_button("🔔 Уведомления: ВКЛ", color=VkKeyboardColor.POSITIVE)
        else:
            kb.add_button("🔕 Уведомления: ВЫКЛ", color=VkKeyboardColor.NEGATIVE)
        
        kb.add_line()
        kb.add_button("⬅️ Назад в меню", color=VkKeyboardColor.SECONDARY)
        return kb.get_keyboard()

# ================= ЛОГИКА БОТА =================
class AdminBot:
    def __init__(self):
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("🔐 Авторизация в ВК...")
        try:
            self.vk_session = vk_api.VkApi(token=CONFIG['token'])
            self.vk = self.vk_session.get_api()
            self.longpoll = VkBotLongPoll(self.vk_session, CONFIG['group_id'])
            self.states = {} 
            self.temp_data = {} 
            print("✅ Авторизация успешна!")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        except Exception as e:
            print(f"❌ Ошибка авторизации: {e}")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            raise

    def send(self, peer_id, text, keyboard=None, attachment=None):
        try:
            params = {
                'peer_id': peer_id,
                'message': text,
                'random_id': get_random_id()
            }
            
            if keyboard:
                params['keyboard'] = keyboard
            if attachment:
                params['attachment'] = attachment
            
            self.vk.messages.send(**params)
            print(f"✅ Отправлено → {peer_id}")
        except vk_api.exceptions.ApiError as e:
            if e.code == 912:
                print(f"❌ ОШИБКА 912: Включи статус 'Бот' в группе!")
            else:
                print(f"❌ VK API Error [{e.code}]: {e.error}")
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")

    def send_to_admins(self, message, attachment=None):
        """Отправить уведомление всем админам с включенными уведомлениями"""
        admins = db.get_all_admins()
        
        # Всегда отправляем владельцу
        self.send(CONFIG['owner_id'], message, attachment=attachment)
        
        # Отправляем другим админам если у них включены уведомления
        for admin in admins:
            if admin[0] != CONFIG['owner_id'] and admin[8] == 1:
                self.send(admin[0], message, attachment=attachment)

    def run(self):
        print(f"🤖 Бот запущен успешно!")
        print(f"📱 Группа: https://vk.com/club{CONFIG['group_id']}")
        print(f"👤 Владелец: @id{CONFIG['owner_id']}")
        print("⏳ Ожидание сообщений...")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        while True:
            try:
                for event in self.longpoll.listen():
                    if event.type == VkBotEventType.MESSAGE_NEW:
                        if event.from_user:
                            self.handle_message(event)
                        
            except Exception as e:
                print(f"\n⚠️ Ошибка: {e}")
                import traceback
                traceback.print_exc()
                print("🔄 Перезапуск через 3 секунды...\n")
                time.sleep(3)

    def handle_message(self, event):
        msg = event.object.message['text'].strip()
        user_id = event.object.message['from_id']
        
        print(f"\n{'='*50}")
        print(f"📨 Новое сообщение")
        print(f"👤 От: {user_id}")
        print(f"💬 Текст: '{msg}'")
        
        # Получаем данные пользователя
        user_db = db.get_user(user_id)
        
        # Проверка прав админа
        is_admin = (user_db[2] > 0) or (user_id == CONFIG['owner_id'])
        
        # Даем права владельцу только ОДИН РАЗ при первой регистрации
        if user_id == CONFIG['owner_id'] and user_db[2] == 0:
            db.update_user(user_id, 'lvl', 7)
            db.update_user(user_id, 'prefix', 'Создатель')
            is_admin = True
            print("👑 Владельцу выданы права Создателя (первый запуск)")

        state = self.states.get(user_id)
        print(f"🔄 Состояние: {state if state else 'Нет'}")

        # === СБРОС СОСТОЯНИЯ ПРИ НАЖАТИИ КНОПОК ГЛАВНОГО МЕНЮ ===
        main_menu_buttons = [
            "📩 Норма", "📈 Доп. отчёт", "🕓 Неактив", "📜 Статистика",
            "👑 Админ-панель", "⚙️ Настройки", "ℹ️ Помощь",
            "📋 Заявки", "👥 Админы", "➖ Снять админку", "❓ Как проверять"
        ]
        
        if msg in main_menu_buttons and state:
            print("🔄 Сброс состояния (нажата кнопка меню)")
            self.states[user_id] = None
            self.temp_data.pop(user_id, None)
            state = None

        # === ОБРАБОТКА ПРИЧИНЫ ОТКЛОНЕНИЯ ===
        if state and state.startswith("WAIT_REJECT_REASON_"):
            req_id = int(state.split("_")[-1])
            request = db.get_request(req_id)
            
            if request:
                # Отклоняем заявку
                db.update_request_status(req_id, 'rejected', user_id, msg)
                
                # Уведомляем пользователя
                req_type_names = {'norma': 'НОРМА', 'extra': 'ДОП. ОТЧЕТ', 'inactive': 'НЕАКТИВ'}
                self.send(
                    request[1],
                    f"❌ Ваша заявка #{req_id} ({req_type_names.get(request[2], 'ЗАЯВКА')}) ОТКЛОНЕНА\n\n"
                    f"Причина: {msg}\n\n"
                    f"Решение принял: @id{user_id}"
                )
                
                self.send(user_id, f"✅ Заявка #{req_id} отклонена. Причина отправлена пользователю.", Keyboards.admin_panel())
                print(f"❌ Заявка #{req_id} отклонена админом @id{user_id}")
            
            self.states[user_id] = None
            print(f"{'='*50}\n")
            return

        # === КОМАНДЫ СТАРТА ===
        msg_lower = msg.lower()
        start_commands = ["начать", "start", "/start", "меню", "menu", "привет", "hello", "hi"]
        
        if msg_lower in start_commands or msg == "ℹ️ Помощь":
            print("✅ Команда СТАРТА/ПОМОЩЬ")
            self.states[user_id] = None
            self.temp_data.pop(user_id, None)
            
            # Разное приветствие для админов и пользователей
            welcome_text = WELCOME_TEXT_ADMIN if is_admin else WELCOME_TEXT_USER
            self.send(user_id, welcome_text, Keyboards.main(is_admin))
            print(f"{'='*50}\n")
            return

        # === КОМАНДА ОТМЕНЫ ===
        if msg in ["❌ Отмена", "отмена", "отменить"] or msg_lower in ["/cancel", "cancel"]:
            print("🚫 Отмена действия")
            self.states[user_id] = None
            self.temp_data.pop(user_id, None)
            self.send(user_id, "❌ Действие отменено.", Keyboards.main(is_admin))
            print(f"{'='*50}\n")
            return
        
        # === КОМАНДЫ ОДОБРЕНИЯ/ОТКЛОНЕНИЯ (ТОЛЬКО ДЛЯ АДМИНОВ) ===
        
        if msg.startswith("/approve ") and is_admin:
            try:
                req_id = int(msg.split()[1])
                request = db.get_request(req_id)
                
                if not request:
                    self.send(user_id, f"❌ Заявка #{req_id} не найдена")
                    print(f"{'='*50}\n")
                    return
                
                if request[5] != 'pending':
                    self.send(user_id, f"❌ Заявка #{req_id} уже обработана (статус: {request[5]})")
                    print(f"{'='*50}\n")
                    return
                
                # Одобряем заявку
                db.update_request_status(req_id, 'approved', user_id, "Одобрено")
                
                # Уведомляем пользователя
                req_type_names = {'norma': 'НОРМА', 'extra': 'ДОП. ОТЧЕТ', 'inactive': 'НЕАКТИВ'}
                self.send(
                    request[1],
                    f"✅ Ваша заявка #{req_id} ({req_type_names.get(request[2], 'ЗАЯВКА')}) ОДОБРЕНА!\n\n"
                    f"Решение принял: @id{user_id}"
                )
                
                # Обновляем статистику (если норма)
                if request[2] == 'norma':
                    user = db.get_user(request[1])
                    db.update_user(request[1], 'norma_days', user[5] + 1)
                
                self.send(user_id, f"✅ Заявка #{req_id} успешно одобрена!", Keyboards.admin_panel())
                print(f"✅ Заявка #{req_id} одобрена админом @id{user_id}")
                
            except (ValueError, IndexError):
                self.send(user_id, "❌ Использование: /approve [ID заявки]\nПример: /approve 5")
            print(f"{'='*50}\n")
            return
        
        if msg.startswith("/reject ") and is_admin:
            try:
                req_id = int(msg.split()[1])
                request = db.get_request(req_id)
                
                if not request:
                    self.send(user_id, f"❌ Заявка #{req_id} не найдена")
                    print(f"{'='*50}\n")
                    return
                
                if request[5] != 'pending':
                    self.send(user_id, f"❌ Заявка #{req_id} уже обработана (статус: {request[5]})")
                    print(f"{'='*50}\n")
                    return
                
                # Запрашиваем причину отклонения
                self.states[user_id] = f"WAIT_REJECT_REASON_{req_id}"
                self.send(
                    user_id,
                    f"❌ Вы отклоняете заявку #{req_id}\n\n"
                    f"Напишите причину отклонения (сообщение получит автор заявки):",
                    Keyboards.cancel()
                )
                print(f"⏳ Ожидание причины отклонения для заявки #{req_id}")
                
            except (ValueError, IndexError):
                self.send(user_id, "❌ Использование: /reject [ID заявки]\nПример: /reject 5")
            print(f"{'='*50}\n")
            return
        
        # === ОБРАБОТКА СОСТОЯНИЙ (Диалоги) ===
        
        # 1. ОБРАБОТКА НОРМЫ
        if state == "WAIT_NORMA_TEXT":
            print("📝 Получен текст нормы")
            self.temp_data[user_id] = {'text': msg, 'nickname': user_db[1]}
            self.states[user_id] = "WAIT_NORMA_PHOTO"
            self.send(user_id, "📸 Отлично! Теперь прикрепите скриншот /astats\n(время в игре)", Keyboards.cancel())
            print(f"{'='*50}\n")
            return
            
        if state == "WAIT_NORMA_PHOTO":
            if event.object.message.get('attachments'):
                print("✅ Получен скриншот нормы → создание заявки")
                
                # Сохраняем attachments
                attachments = []
                for att in event.object.message['attachments']:
                    if att['type'] == 'photo':
                        photo = att['photo']
                        attachments.append(f"photo{photo['owner_id']}_{photo['id']}")
                
                # Создаем заявку
                req_id = db.create_request(
                    user_id,
                    'norma',
                    self.temp_data[user_id]['text'],
                    ','.join(attachments) if attachments else None
                )
                
                # Отправляем админам на проверку
                admin_message = (
                    f"📩 НОВАЯ НОРМА (Заявка #{req_id})\n\n"
                    f"От: @id{user_id} ({self.temp_data[user_id]['nickname']})\n\n"
                    f"{self.temp_data[user_id]['text']}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ Одобрить: /approve {req_id}\n"
                    f"❌ Отклонить: /reject {req_id}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━"
                )
                
                self.send_to_admins(admin_message, ','.join(attachments) if attachments else None)
                
                self.send(user_id, f"✅ Норма отправлена на проверку!\n\n📝 Номер заявки: #{req_id}\nОжидайте решения руководства.", Keyboards.main(is_admin))
                self.states[user_id] = None
                self.temp_data.pop(user_id, None)
            else:
                print("⚠️ Скриншот не прикреплен")
                self.send(user_id, "❌ Пожалуйста, прикрепите скриншот /astats!\nИли нажмите «Отмена»", Keyboards.cancel())
            print(f"{'='*50}\n")
            return

        # 2. ОБРАБОТКА ДОП. РЕПОРТА
        if state == "WAIT_EXTRA_TEXT":
            print("📝 Получен текст доп. отчета")
            self.temp_data[user_id] = {'text': msg, 'nickname': user_db[1]}
            self.states[user_id] = "WAIT_EXTRA_PHOTO"
            self.send(user_id, "📸 Теперь прикрепите доказательства (скриншоты работы).", Keyboards.cancel())
            print(f"{'='*50}\n")
            return

        if state == "WAIT_EXTRA_PHOTO":
            if event.object.message.get('attachments'):
                print("✅ Получены доказательства → создание заявки")
                
                # Сохраняем attachments
                attachments = []
                for att in event.object.message['attachments']:
                    if att['type'] == 'photo':
                        photo = att['photo']
                        attachments.append(f"photo{photo['owner_id']}_{photo['id']}")
                
                # Создаем заявку
                req_id = db.create_request(
                    user_id,
                    'extra',
                    self.temp_data[user_id]['text'],
                    ','.join(attachments) if attachments else None
                )
                
                # Отправляем админам на проверку
                admin_message = (
                    f"📈 НОВЫЙ ДОП. ОТЧЕТ (Заявка #{req_id})\n\n"
                    f"От: @id{user_id} ({self.temp_data[user_id]['nickname']})\n\n"
                    f"{self.temp_data[user_id]['text']}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ Одобрить: /approve {req_id}\n"
                    f"❌ Отклонить: /reject {req_id}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━"
                )
                
                self.send_to_admins(admin_message, ','.join(attachments) if attachments else None)
                
                self.send(user_id, f"✅ Дополнительный отчет отправлен на проверку!\n\n📝 Номер заявки: #{req_id}\nОжидайте решения.", Keyboards.main(is_admin))
                self.states[user_id] = None
                self.temp_data.pop(user_id, None)
            else:
                print("⚠️ Скриншоты не прикреплены")
                self.send(user_id, "❌ Прикрепите скриншоты проделанной работы!", Keyboards.cancel())
            print(f"{'='*50}\n")
            return

        # 3. ОБРАБОТКА НЕАКТИВА
        if state == "WAIT_INACTIVE_TEXT":
            print("📝 Получена заявка на неактив → создание заявки")
            
            # Создаем заявку
            req_id = db.create_request(user_id, 'inactive', msg)
            
            # Отправляем админам на проверку
            admin_message = (
                f"💤 НОВЫЙ НЕАКТИВ (Заявка #{req_id})\n\n"
                f"От: @id{user_id} ({user_db[1]})\n\n"
                f"{msg}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Одобрить: /approve {req_id}\n"
                f"❌ Отклонить: /reject {req_id}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )
            
            self.send_to_admins(admin_message)
            
            self.send(user_id, f"✅ Заявка на неактив отправлена на проверку!\n\n📝 Номер заявки: #{req_id}\nОжидайте подтверждения.", Keyboards.main(is_admin))
            self.states[user_id] = None
            print(f"{'='*50}\n")
            return

        # === ОБРАБОТКА КНОПОК МЕНЮ ===

        if msg == "📩 Норма":
            print("🔵 Начата подача нормы")
            self.states[user_id] = "WAIT_NORMA_TEXT"
            self.send(user_id, TEMPLATE_NORMA, Keyboards.cancel())
        
        elif msg == "📈 Доп. отчёт":
            print("🔵 Начата подача доп. отчета")
            self.states[user_id] = "WAIT_EXTRA_TEXT"
            self.send(user_id, TEMPLATE_EXTRA, Keyboards.cancel())

        elif msg == "🕓 Неактив":
            print("🔵 Начата подача неактива")
            self.states[user_id] = "WAIT_INACTIVE_TEXT"
            self.send(user_id, TEMPLATE_INACTIVE, Keyboards.cancel())

        elif msg == "📜 Статистика":
            print("📊 Запрошена статистика")
            
            # Получаем историю заявок
            requests = db.get_user_requests(user_id)
            approved = sum(1 for r in requests if r[5] == 'approved')
            pending = sum(1 for r in requests if r[5] == 'pending')
            rejected = sum(1 for r in requests if r[5] == 'rejected')
            
            text = f"""📊 ТВОЯ СТАТИСТИКА:
            
👤 Ник: {user_db[1]}
🔰 Ранг: {user_db[3]} (Lvl {user_db[2]})
📅 Регистрация: {user_db[4]}
✅ Одобренных норм: {user_db[5]}

📋 ЗАЯВКИ:
✅ Одобрено: {approved}
⏳ На проверке: {pending}
❌ Отклонено: {rejected}"""
            self.send(user_id, text, Keyboards.main(is_admin))

        elif msg == "⚙️ Настройки":
            print("⚙️ Открыты настройки")
            notifications_on = user_db[8] == 1
            
            text = f"""⚙️ НАСТРОЙКИ

🔔 Уведомления о заявках: {"✅ Включены" if notifications_on else "❌ Выключены"}

{'ℹ️ Вы получаете уведомления о всех новых заявках' if notifications_on else 'ℹ️ Уведомления отключены. Проверяйте заявки вручную через "📋 Заявки"'}

{'(Только для администраторов)' if is_admin else ''}"""
            
            self.send(user_id, text, Keyboards.settings(notifications_on))

        elif msg in ["🔔 Уведомления: ВКЛ", "🔕 Уведомления: ВЫКЛ"]:
            if is_admin:
                # Переключаем уведомления
                new_state = 0 if user_db[8] == 1 else 1
                db.update_user(user_id, 'notifications', new_state)
                
                status = "включены" if new_state == 1 else "выключены"
                self.send(user_id, f"✅ Уведомления {status}", Keyboards.settings(new_state == 1))
                print(f"⚙️ Уведомления {status} для @id{user_id}")
            else:
                self.send(user_id, "❌ Настройка уведомлений доступна только администраторам", Keyboards.settings(True))

        elif msg == "👑 Админ-панель" and is_admin:
            print("⚙️ Открыта админ-панель")
            pending_count = len(db.get_pending_requests())
            text = f"""👑 АДМИН-ПАНЕЛЬ

📋 Заявок на проверке: {pending_count}

⚙️ Команды:
/approve [ID] — Одобрить заявку
/reject [ID] — Отклонить заявку
!setlvl [ID] [LVL] — Выдать админку
!dellvl [ID] — Снять админку

💡 Не знаете как проверять заявки?
Нажмите "❓ Как проверять"

📊 Используй кнопки для управления:"""
            self.send(user_id, text, Keyboards.admin_panel())

        elif msg == "❓ Как проверять" and is_admin:
            print("💡 Показана инструкция по проверке")
            text = """💡 КАК ПРОВЕРЯТЬ ЗАЯВКИ

📩 Когда приходит заявка, вы видите:
━━━━━━━━━━━━━━━━━━━━━━
📩 НОВАЯ НОРМА (Заявка #5)
От: @id123456 (Петров)
[Содержимое + скриншот]

✅ Одобрить: /approve 5
❌ Отклонить: /reject 5
━━━━━━━━━━━━━━━━━━━━━━

🎯 ОДОБРИТЬ ЗАЯВКУ:
1. Скопируй команду: /approve 5
2. Отправь боту
3. Готово! ✅

🎯 ОТКЛОНИТЬ ЗАЯВКУ:
1. Скопируй команду: /reject 5
2. Отправь боту
3. Бот попросит причину
4. Напиши причину (например: "Недостаточно часов")
5. Готово! ❌

💡 СОВЕТ: Копируй команды прямо из сообщения с заявкой!"""
            self.send(user_id, text, Keyboards.admin_panel())

        elif msg == "📋 Заявки" and is_admin:
            print("📋 Запрошен список заявок")
            requests = db.get_pending_requests()
            
            if requests:
                text = f"📋 ЗАЯВКИ НА ПРОВЕРКЕ ({len(requests)}):\n\n"
                
                for req in requests[:10]:
                    req_id, req_user_id, req_type, content, attachments, status, _, _, created_at, _ = req
                    
                    req_type_names = {'norma': '📩', 'extra': '📈', 'inactive': '💤'}
                    user = db.get_user(req_user_id)
                    
                    text += f"{req_type_names.get(req_type, '📝')} Заявка #{req_id}\n"
                    text += f"От: @id{req_user_id} ({user[1]})\n"
                    text += f"Дата: {created_at}\n"
                    text += f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                text += f"\n💡 Для проверки используйте:\n"
                text += f"✅ /approve [ID] — одобрить\n"
                text += f"❌ /reject [ID] — отклонить\n\n"
                text += f"Пример: /approve {requests[0][0]}"
                
                self.send(user_id, text, Keyboards.admin_panel())
            else:
                self.send(user_id, "📭 Нет заявок на проверке", Keyboards.admin_panel())

        elif msg == "👥 Админы" and is_admin:
            print("📋 Запрошен список админов")
            admins = db.get_all_admins()
            if admins:
                text = "👥 СПИСОК АДМИНИСТРАЦИИ:\n\n"
                for admin in admins:
                    notif_icon = "🔔" if admin[8] == 1 else "🔕"
                    text += f"• @id{admin[0]} - {admin[1]}\n"
                    text += f"  🔰 {admin[3]} (Lvl {admin[2]})\n"
                    text += f"  ✅ Норм: {admin[5]} | {notif_icon}\n\n"
                self.send(user_id, text, Keyboards.admin_panel())
            else:
                self.send(user_id, "📭 Администраторов пока нет", Keyboards.admin_panel())

        elif msg == "➖ Снять админку" and is_admin:
            print("➖ Режим снятия админки")
            self.send(
                user_id,
                "➖ СНЯТЬ АДМИНИСТРАТОРСКИЕ ПРАВА\n\n"
                "Используй команду:\n"
                "!dellvl [ID пользователя]\n\n"
                "Пример:\n"
                "!dellvl 123456\n"
                "!dellvl @id123456",
                Keyboards.admin_panel()
            )

        elif msg == "⬅️ Назад в меню":
            print("🔙 Возврат в меню")
            welcome_text = WELCOME_TEXT_ADMIN if is_admin else WELCOME_TEXT_USER
            self.send(user_id, welcome_text, Keyboards.main(is_admin))

        # === КОМАНДЫ ЧАТА ===

        elif msg.startswith("!nick "):
            new_nick = msg[6:].strip()
            if new_nick:
                db.update_user(user_id, 'nickname', new_nick)
                self.send(user_id, f"✅ Ваш ник обновлен: {new_nick}")
                print(f"✏️ Установлен ник: {new_nick}")
            else:
                self.send(user_id, "❌ Использование: !nick [Ваш игровой ник]")

        elif msg.startswith("!setlvl") and is_admin:
            try:
                parts = msg.split()
                if len(parts) < 3:
                    self.send(user_id, "❌ Использование: !setlvl [ID] [Уровень 0-7]\nПример: !setlvl 123456 3")
                    print(f"{'='*50}\n")
                    return
                
                # Парсим ID
                if '[id' in parts[1]:
                    target = int(parts[1].split('|')[0].replace('[id', ''))
                else:
                    target = int(parts[1])
                
                lvl = int(parts[2])
                
                if lvl < 0 or lvl > 7:
                    self.send(user_id, "❌ Уровень должен быть от 0 до 7")
                    print(f"{'='*50}\n")
                    return
                
                # Нельзя изменить уровень владельца
                if target == CONFIG['owner_id'] and user_id != CONFIG['owner_id']:
                    self.send(user_id, "❌ Нельзя изменить права создателя!")
                    print(f"{'='*50}\n")
                    return
                
                db.get_user(target)
                db.update_user(target, 'lvl', lvl)
                
                roles = {
                    0: "Игрок",
                    1: "Мл.Модератор", 
                    2: "Модератор",
                    3: "Ст.Модератор",
                    4: "Администратор",
                    5: "Куратор",
                    6: "Зам. Гл. Админа",
                    7: "Гл. Администратор"
                }
                role_name = roles.get(lvl, "Спец.Админ")
                db.update_user(target, 'prefix', role_name)
                
                self.send(user_id, f"✅ Игроку @id{target} выдан уровень {lvl} ({role_name})")
                
                if lvl > 0:
                    welcome_msg = WELCOME_TEXT_ADMIN
                    self.send(target, f"🎉 Поздравляем!\n\nВам выдан администраторский уровень: {lvl}\n🔰 Должность: {role_name}\n\n{welcome_msg}", Keyboards.main(True))
                else:
                    self.send(target, f"ℹ️ Ваш уровень изменен на: {lvl} ({role_name})", Keyboards.main(False))
                
                print(f"👑 Выдан уровень {lvl} ({role_name}) пользователю @id{target}")
                
            except ValueError:
                self.send(user_id, "❌ Неверный формат! Используй: !setlvl [ID] [Уровень]\nПример: !setlvl 123456 3")
                print("❌ Ошибка формата команды")
            except Exception as e:
                self.send(user_id, f"❌ Ошибка: {e}")
                print(f"❌ Ошибка setlvl: {e}")

        elif msg.startswith("!dellvl") and is_admin:
            try:
                parts = msg.split()
                if len(parts) < 2:
                    self.send(user_id, "❌ Использование: !dellvl [ID]\nПример: !dellvl 123456")
                    print(f"{'='*50}\n")
                    return
                
                # Парсим ID
                if '[id' in parts[1]:
                    target = int(parts[1].split('|')[0].replace('[id', ''))
                else:
                    target = int(parts[1])
                
                # Нельзя снять права с владельца
                if target == CONFIG['owner_id']:
                    self.send(user_id, "❌ Нельзя снять права с создателя!")
                    print(f"{'='*50}\n")
                    return
                
                target_user = db.get_user(target)
                
                if target_user[2] == 0:
                    self.send(user_id, f"❌ У @id{target} нет администраторских прав")
                    print(f"{'='*50}\n")
                    return
                
                # Снимаем права
                db.update_user(target, 'lvl', 0)
                db.update_user(target, 'prefix', 'Игрок')
                
                self.send(user_id, f"✅ С игрока @id{target} ({target_user[1]}) сняты администраторские права")
                self.send(target, f"ℹ️ С вас сняты администраторские права.\nВаш уровень: 0 (Игрок)", Keyboards.main(False))
                
                print(f"➖ Сняты права с @id{target}")
                
            except ValueError:
                self.send(user_id, "❌ Неверный формат! Используй: !dellvl [ID]\nПример: !dellvl 123456")
                print("❌ Ошибка формата команды")
            except Exception as e:
                self.send(user_id, f"❌ Ошибка: {e}")
                print(f"❌ Ошибка dellvl: {e}")

        else:
            # Если команда не понятна и нет активного диалога
            if state is None:
                print("⚠️ Неизвестная команда")
                self.send(user_id, "❓ Не понимаю команду.\nИспользуй кнопки меню или напиши «Начать»", Keyboards.main(is_admin))

        print(f"{'='*50}\n")

if __name__ == "__main__":
    try:
        print("\n" + "="*50)
        print("  ADMIN ASSISTANT BOT v3.0")
        print("  Полностью исправленная версия")
        print("="*50 + "\n")
        bot = AdminBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n⛔ Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
