# -*- coding: utf-8 -*-
"""
ADMIN ASSISTANT BOT v8.2
Исправления v8.2:
- КРИТИЧЕСКИЙ БАГИ: WAIT_REJECT_ID перехватывался блоком WAIT_REJECT_* → бот молчал при вводе числа
- Порядок проверки состояний исправлен (ID-состояния проверяются ДО WAIT_REJECT_N)
- Расширенные приветствия для игроков и администраторов
- Улучшены описания шаблонов при входе в разделы
"""
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
import sqlite3
import datetime
import time
import json

# ═══════════════════════════════════════════════
#  КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════
CONFIG = {
    "token":    "vk1.a.Z9pCqT1rlC8JsFxbrZMhhmvbPe764cfFlF9N1z5RG4nrLfO9E8YisGaABMzphZNjMOZ01Y4A25SAdRZnvVSO2mxmOUq2AiOsPkNmmQXH_6ghpstHBPiPjxZv-c6t8JL8JV1qbmOpFPTTSOx8_CAfsKFaMqa9_-BXqLW4LbeR2fyyncJMlHHpTsfcjLWXtZYJu1rJSUDPp4zoCoVcOpaE5A",
    "group_id": 236066012,
    "owner_id": 864765284,
    "db_file":  "server_bot.db",
}

ROLES    = {0: "Игрок", 1: "Модератор", 2: "Администратор"}
REQ_NAMES = {'norma': 'НОРМА', 'extra': 'ДОП. РЕПОРТ', 'inactive': 'НЕАКТИВ'}
REQ_EMOJI = {'norma': '📩',    'extra': '📈',           'inactive': '💤'}

TEMPLATES = {
    'norma': (
        "📩 ПОДАЧА НОРМЫ\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 Скопируй шаблон, заполни и отправь:\n\n"
        "1 - NickName:\n"
        "2 - Уровень адм. прав:\n"
        "3 - Должность:\n"
        "4 - Дата отчёта:\n"
        "5 - /astats:\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ После текста прикрепи скриншот /astats!\n"
        "Без скриншота заявка не будет принята."
    ),
    'extra': (
        "📈 ДОПОЛНИТЕЛЬНЫЙ РЕПОРТ\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 Скопируй шаблон, заполни и отправь:\n\n"
        "1. NickName:\n"
        "2. Уровень адм. прав:\n"
        "3. Должность:\n"
        "4. За какой день:\n"
        "5. Что сделано:\n"
        "6. Скриншоты:\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ После текста прикрепи скриншоты работы!\n"
        "Без доказательств заявка не будет принята."
    ),
    'inactive': (
        "💤 ЗАЯВЛЕНИЕ НА НЕАКТИВ\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 Скопируй шаблон, заполни и отправь:\n\n"
        "1. Ваш NickName:\n"
        "2. Уровень адм. прав:\n"
        "3. Занимаемая должность:\n"
        "4. Подменяющее лицо:\n"
        "5. Кто из главной администрации предупрежден:\n"
        "6. Дата неактива (какие дни):\n"
        "7. Причина неактива:\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ Неактив без заявки считается прогулом!\n"
        "Подавай заявку ЗАРАНЕЕ, минимум за 24 часа."
    ),
}

# ─── Расширенное приветствие для ИГРОКОВ ───────────────────────────────────
WELCOME_USER = (
    "👋 Добро пожаловать в Admin Assistant!\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "🎮 ЧТО ТАКОЕ ЭТОТ БОТ?\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Это официальный бот для подачи отчётов и заявлений.\n"
    "Все заявки поступают напрямую администрации сервера.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "📋 ВИДЫ ЗАЯВОК:\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "📩 НОРМА\n"
    "   Ежедневный рабочий отчёт.\n"
    "   Подаётся каждый день до 00:30.\n"
    "   Требуется скриншот /astats.\n\n"
    "📈 ДОП. РЕПОРТ\n"
    "   Отчёт о дополнительной работе:\n"
    "   помощь игрокам, баны, проверки и т.д.\n"
    "   Требуются скриншоты как доказательство.\n\n"
    "💤 НЕАКТИВ\n"
    "   Заявление на временное отсутствие.\n"
    "   Подаётся ЗАРАНЕЕ, минимум за 24 часа.\n"
    "   Без заявки — прогул и взыскание.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚙️ ПОЛЕЗНЫЕ КОМАНДЫ:\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "!nick [Ник]    — Установить игровой ник\n"
    "                 Пример: !nick ProPlayer\n\n"
    "/cancel [ID]   — Удалить свою заявку\n"
    "                 Пример: /cancel 5\n\n"
    "/edit [ID]     — Редактировать заявку\n"
    "                 Пример: /edit 5\n\n"
    "📜 Статистика  — Посмотреть свои заявки\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "❗ ВАЖНО:\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "• Заявки рассматриваются в течение суток\n"
    "• Ты получишь уведомление о решении\n"
    "• Не забудь установить ник: !nick [твой ник]\n\n"
    "👇 Выбери действие:"
)

# ─── Расширенное приветствие для АДМИНИСТРАТОРОВ ───────────────────────────
WELCOME_ADMIN = (
    "👋 Добро пожаловать, Администратор!\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "📋 КАК РАБОТАЕТ БОТ?\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Игроки подают заявки через бота.\n"
    "Ты получаешь уведомление и выносишь решение.\n"
    "Все действия логируются и сохраняются.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "📩 ПОДАЧА СВОИХ ОТЧЁТОВ:\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "📩 Норма      — ежедневный отчёт (до 00:30)\n"
    "📈 Доп. репорт — дополнительная работа\n"
    "💤 Неактив    — заявление на отсутствие\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "👑 ПРОВЕРКА ЗАЯВОК (LVL 1+):\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "1. Нажми «👑 Админ-панель» → «📋 Заявки»\n"
    "2. Выбери категорию заявок\n"
    "3. Нажми «✅ Одобрить заявку» или «❌ Отказать заявке»\n"
    "4. Введи номер (ID) заявки\n\n"
    "Или используй команды:\n"
    "/approve [ID] — одобрить (пример: /approve 5)\n"
    "/reject [ID]  — отклонить (пример: /reject 5)\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "🔧 УПРАВЛЕНИЕ СОСТАВОМ (LVL 2+):\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "!setlvl [ID] [1/2] — Выдать/изменить уровень\n"
    "   1 = Модератор | 2 = Администратор\n"
    "   Пример: !setlvl 123456 1\n\n"
    "!dellvl [ID]       — Снять права\n"
    "   Пример: !dellvl 123456\n\n"
    "!nick [Ник]        — Установить свой ник\n"
    "   Пример: !nick AdminName\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚙️ НАСТРОЙКИ:\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "• Уведомления о заявках — вкл/выкл\n"
    "• Формат заявок — карточки или текст\n\n"
    "👇 Выбери действие:"
)


# ═══════════════════════════════════════════════
#  ПАРСИНГ ID
# ═══════════════════════════════════════════════
def parse_id(text: str) -> int:
    t = text.strip()
    if t.startswith('[id') and '|' in t:
        return int(t.split('|')[0].replace('[id', ''))
    if t.lower().startswith('@id'):
        return int(t[3:])
    return int(t)


# ═══════════════════════════════════════════════
#  БАЗА ДАННЫХ
# ═══════════════════════════════════════════════
class DB:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cur  = self.conn.cursor()
        self._init()

    def _init(self):
        self.cur.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                nickname   TEXT    DEFAULT 'Не указан',
                lvl        INTEGER DEFAULT 0,
                prefix     TEXT    DEFAULT 'Игрок',
                reg_date   TEXT,
                norma_days INTEGER DEFAULT 0,
                answers    INTEGER DEFAULT 0,
                warns      INTEGER DEFAULT 0,
                notif_on   INTEGER DEFAULT 1,
                notif_fmt  INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS requests (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER,
                type          TEXT,
                content       TEXT,
                attachments   TEXT,
                status        TEXT DEFAULT 'pending',
                admin_id      INTEGER,
                admin_comment TEXT,
                created_at    TEXT,
                reviewed_at   TEXT
            );
        ''')
        self.conn.commit()
        self._migrate()

    def _migrate(self):
        self.cur.execute("PRAGMA table_info(users)")
        cols = {r[1] for r in self.cur.fetchall()}
        added = []
        for col, typ in [('notif_on','INTEGER DEFAULT 1'), ('notif_fmt','INTEGER DEFAULT 1')]:
            if col not in cols:
                try:
                    self.cur.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
                    added.append(col)
                except Exception as e:
                    print(f"  [DB] миграция {col}: {e}")
        if added:
            self.conn.commit()
            print(f"  [DB] добавлены колонки: {added}")
        self.cur.execute("UPDATE users SET lvl=2 WHERE lvl>2")
        self.cur.execute("UPDATE users SET prefix='Администратор' WHERE lvl=2 AND prefix NOT IN ('Администратор')")
        self.cur.execute("UPDATE users SET prefix='Модератор' WHERE lvl=1 AND prefix NOT IN ('Модератор')")
        self.cur.execute("UPDATE users SET prefix='Игрок' WHERE lvl=0 AND prefix NOT IN ('Игрок')")
        self.conn.commit()

    def user(self, uid):
        self.cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        row = self.cur.fetchone()
        if not row:
            now = datetime.datetime.now().strftime("%d.%m.%Y")
            self.cur.execute("INSERT INTO users (user_id,reg_date) VALUES (?,?)", (uid, now))
            self.conn.commit()
            return self.user(uid)
        return row

    def set(self, uid, col, val):
        self.cur.execute(f"UPDATE users SET {col}=? WHERE user_id=?", (val, uid))
        self.conn.commit()

    def admins(self):
        self.cur.execute("SELECT * FROM users WHERE lvl>0 ORDER BY lvl DESC")
        return self.cur.fetchall()

    def req_add(self, uid, rtype, content, att=None):
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        self.cur.execute(
            "INSERT INTO requests (user_id,type,content,attachments,created_at) VALUES (?,?,?,?,?)",
            (uid, rtype, content, att, now))
        self.conn.commit()
        return self.cur.lastrowid

    def req_get(self, rid):
        self.cur.execute("SELECT * FROM requests WHERE id=?", (rid,))
        return self.cur.fetchone()

    def req_pending(self, rtype=None):
        if rtype:
            self.cur.execute(
                "SELECT * FROM requests WHERE status='pending' AND type=? ORDER BY created_at DESC", (rtype,))
        else:
            self.cur.execute("SELECT * FROM requests WHERE status='pending' ORDER BY created_at DESC")
        return self.cur.fetchall()

    def req_status(self, rid, status, admin_id, comment=None):
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        self.cur.execute(
            "UPDATE requests SET status=?,admin_id=?,admin_comment=?,reviewed_at=? WHERE id=?",
            (status, admin_id, comment, now, rid))
        self.conn.commit()

    def req_delete(self, rid):
        self.cur.execute("DELETE FROM requests WHERE id=?", (rid,))
        self.conn.commit()

    def req_update(self, rid, content=None, att=None):
        if content is not None and att is not None:
            self.cur.execute("UPDATE requests SET content=?,attachments=? WHERE id=?", (content, att, rid))
        elif content is not None:
            self.cur.execute("UPDATE requests SET content=? WHERE id=?", (content, rid))
        self.conn.commit()

    def user_reqs(self, uid):
        self.cur.execute(
            "SELECT * FROM requests WHERE user_id=? ORDER BY created_at DESC LIMIT 10", (uid,))
        return self.cur.fetchall()


db = DB(CONFIG['db_file'])


# ═══════════════════════════════════════════════
#  КЛАВИАТУРЫ
# ═══════════════════════════════════════════════
class KB:

    @staticmethod
    def main(is_admin=False):
        k = VkKeyboard(one_time=False)
        k.add_button("📩 Норма",       color=VkKeyboardColor.POSITIVE)
        k.add_button("📈 Доп. репорт", color=VkKeyboardColor.PRIMARY)
        k.add_line()
        k.add_button("💤 Неактив",    color=VkKeyboardColor.SECONDARY)
        k.add_button("📜 Статистика", color=VkKeyboardColor.SECONDARY)
        if is_admin:
            k.add_line()
            k.add_button("👑 Админ-панель", color=VkKeyboardColor.NEGATIVE)
            k.add_line()
            k.add_button("⚙️ Настройки", color=VkKeyboardColor.PRIMARY)
            k.add_button("ℹ️ Помощь",    color=VkKeyboardColor.SECONDARY)
        else:
            k.add_line()
            k.add_button("ℹ️ Помощь", color=VkKeyboardColor.PRIMARY)
        return k.get_keyboard()

    @staticmethod
    def cancel():
        k = VkKeyboard(one_time=False)
        k.add_button("❌ Отмена", color=VkKeyboardColor.NEGATIVE)
        return k.get_keyboard()

    @staticmethod
    def admin_panel():
        k = VkKeyboard(one_time=False)
        k.add_button("📋 Заявки",         color=VkKeyboardColor.POSITIVE)
        k.add_button("👥 Админы",          color=VkKeyboardColor.PRIMARY)
        k.add_line()
        k.add_button("➕ Добавить админа", color=VkKeyboardColor.POSITIVE)
        k.add_button("➖ Снять права",     color=VkKeyboardColor.NEGATIVE)
        k.add_line()
        k.add_button("❓ Как проверять",   color=VkKeyboardColor.PRIMARY)
        k.add_line()
        k.add_button("⬅️ Назад в меню",   color=VkKeyboardColor.SECONDARY)
        return k.get_keyboard()

    @staticmethod
    def settings(notif_on: int, notif_fmt: int):
        k = VkKeyboard(one_time=False)
        if notif_on:
            k.add_button("🔕 Выключить уведомления", color=VkKeyboardColor.NEGATIVE)
        else:
            k.add_button("🔔 Включить уведомления",  color=VkKeyboardColor.POSITIVE)
        k.add_line()
        if notif_fmt == 1:
            k.add_button("📄 Переключить на текст",    color=VkKeyboardColor.SECONDARY)
        else:
            k.add_button("📨 Переключить на карточки", color=VkKeyboardColor.POSITIVE)
        k.add_line()
        k.add_button("⬅️ Назад в меню", color=VkKeyboardColor.SECONDARY)
        return k.get_keyboard()

    @staticmethod
    def req_filter():
        k = VkKeyboard(one_time=False)
        k.add_button("✉️ Норма",       color=VkKeyboardColor.POSITIVE)
        k.add_button("📊 Доп. репорт", color=VkKeyboardColor.PRIMARY)
        k.add_line()
        k.add_button("😴 Неактив",    color=VkKeyboardColor.SECONDARY)
        k.add_button("📋 Все заявки", color=VkKeyboardColor.PRIMARY)
        k.add_line()
        k.add_button("⬅️ Назад в меню", color=VkKeyboardColor.SECONDARY)
        return k.get_keyboard()

    @staticmethod
    def approve_kb(rid: int):
        k = VkKeyboard(one_time=False)
        k.add_button(f"✅ Одобрить #{rid}", color=VkKeyboardColor.POSITIVE)
        k.add_button(f"❌ Отказать #{rid}", color=VkKeyboardColor.NEGATIVE)
        k.add_line()
        k.add_button("⬅️ Назад в меню", color=VkKeyboardColor.SECONDARY)
        return k.get_keyboard()

    @staticmethod
    def req_actions():
        k = VkKeyboard(one_time=False)
        k.add_button("✅ Одобрить заявку", color=VkKeyboardColor.POSITIVE)
        k.add_button("❌ Отказать заявке", color=VkKeyboardColor.NEGATIVE)
        k.add_line()
        k.add_button("🔄 Обновить список", color=VkKeyboardColor.PRIMARY)
        k.add_button("⬅️ Назад в меню",   color=VkKeyboardColor.SECONDARY)
        return k.get_keyboard()


# ═══════════════════════════════════════════════
#  БОТ
# ═══════════════════════════════════════════════
class Bot:
    def __init__(self):
        print("=" * 55)
        print("  ADMIN ASSISTANT BOT v8.2")
        print("=" * 55)
        print("[INIT] Авторизация в VK...")
        self.vk_s   = vk_api.VkApi(token=CONFIG['token'])
        self.vk     = self.vk_s.get_api()
        self.lp     = VkBotLongPoll(self.vk_s, CONFIG['group_id'])
        self.states = {}
        self.tmp    = {}
        print("[INIT] Авторизация успешна!")
        print(f"[INIT] Группа: vk.com/club{CONFIG['group_id']}")
        print(f"[INIT] Владелец: @id{CONFIG['owner_id']}")
        print("[INIT] Ожидаю сообщения...\n" + "=" * 55)

    def send(self, pid, text, kb=None, att=None):
        p = {'peer_id': pid, 'message': text, 'random_id': get_random_id()}
        if kb:  p['keyboard'] = kb
        if att: p['attachment'] = att
        try:
            self.vk.messages.send(**p)
        except vk_api.exceptions.ApiError as e:
            print(f"[ERR] send API [{e.code}]: {e}")
        except Exception as e:
            print(f"[ERR] send: {e}")

    def _card(self, pid, req):
        rid   = req['id']
        ruid  = req['user_id']
        rtype = req['type']
        att   = req['attachments']
        u     = db.user(ruid)
        text  = (
            f"{REQ_EMOJI.get(rtype,'📝')} #{rid} — {REQ_NAMES.get(rtype,'ЗАЯВКА')}\n"
            f"👤 @id{ruid} ({u['nickname']})\n"
            f"📅 {req['created_at']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{req['content']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"ID для решения: #{rid}"
        )
        p = {'peer_id': pid, 'message': text, 'random_id': get_random_id()}
        if att: p['attachment'] = att
        try:
            self.vk.messages.send(**p)
        except vk_api.exceptions.ApiError:
            p.pop('attachment', None)
            cnt = len(att.split(',')) if att else 0
            if cnt:
                p['message'] += f"\n📸 Фото ({cnt} шт.) — прикреплено отдельно"
            try:
                self.vk.messages.send(**p)
                if att:
                    self.vk.messages.send(
                        peer_id=pid,
                        message="📸 Фото к заявке:",
                        attachment=att,
                        random_id=get_random_id()
                    )
            except Exception as e2:
                print(f"[ERR] card retry: {e2}")
        except Exception as e:
            print(f"[ERR] card: {e}")

    def _do_approve(self, uid, rid, lvl):
        req = db.req_get(rid)
        if not req:
            self.send(uid, f"❌ Заявка #{rid} не найдена"); return
        if req['status'] != 'pending':
            self.send(uid, f"❌ Заявка #{rid} уже обработана ({req['status']})"); return
        db.req_status(rid, 'approved', uid, "Одобрено")
        if req['type'] == 'norma':
            db.set(req['user_id'], 'norma_days', db.user(req['user_id'])['norma_days'] + 1)
        self.send(req['user_id'],
            f"✅ Заявка #{rid} ({REQ_NAMES.get(req['type'],'?')}) ОДОБРЕНА!\n"
            f"Решение принял: @id{uid}")
        self.send(uid, f"✅ Заявка #{rid} одобрена!", KB.req_actions())
        print(f"[ACTION] Заявка #{rid} одобрена @id{uid}")

    def _notify(self, req_id, fwd_msg_id=None):
        req = db.req_get(req_id)
        if not req:
            return
        rtype = req['type']
        ruid  = req['user_id']
        nick  = db.user(ruid)['nickname']
        print(f"[NOTIFY] Отправка заявки #{req_id} администраторам...")

        def _one(admin_id, can_mod, fmt):
            if fmt == 1:
                if fwd_msg_id and admin_id == CONFIG['owner_id']:
                    header = (
                        f"🆕 Новая заявка #{req_id} — {REQ_NAMES.get(rtype,'?')}\n"
                        f"👤 @id{ruid} ({nick}) • {req['created_at']}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"ID для решения: #{req_id}"
                    )
                    try:
                        self.vk.messages.send(
                            peer_id=admin_id,
                            message=header,
                            forward_messages=fwd_msg_id,
                            keyboard=KB.approve_kb(req_id),
                            random_id=get_random_id()
                        )
                        print(f"[NOTIFY]   → @id{admin_id} (fwd)")
                        return
                    except Exception:
                        pass
                self._card(admin_id, req)
                self.send(admin_id,
                    f"👆 Новая заявка #{req_id}. Выберите действие:",
                    KB.approve_kb(req_id))
                print(f"[NOTIFY]   → @id{admin_id} (карточка)")
            else:
                text = (
                    f"{REQ_EMOJI.get(rtype,'📝')} #{req_id} — {REQ_NAMES.get(rtype,'?')}\n"
                    f"👤 @id{ruid} ({nick})\n📅 {req['created_at']}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n{req['content']}"
                )
                if req['attachments']:
                    cnt = len(req['attachments'].split(','))
                    text += f"\n📸 Фото: {cnt} шт."
                self.send(admin_id, text, KB.approve_kb(req_id))
                print(f"[NOTIFY]   → @id{admin_id} (текст)")

        ow = db.user(CONFIG['owner_id'])
        _one(CONFIG['owner_id'], True, ow['notif_fmt'])

        for a in db.admins():
            if a['user_id'] == CONFIG['owner_id']:
                continue
            if not a['notif_on']:
                continue
            _one(a['user_id'], a['lvl'] >= 1, a['notif_fmt'])

    @staticmethod
    def _att(atts):
        out = []
        for a in atts:
            if a['type'] == 'photo':
                ph = a['photo']
                s  = f"photo{ph['owner_id']}_{ph['id']}"
                if 'access_key' in ph:
                    s += f"_{ph['access_key']}"
                out.append(s)
        return out

    def run(self):
        while True:
            try:
                for event in self.lp.listen():
                    etype = event.type
                    if etype == VkBotEventType.MESSAGE_NEW and event.from_user:
                        self._msg(event)
                    elif etype == VkBotEventType.MESSAGE_EVENT:
                        print(f"[CB] MESSAGE_EVENT: {event.object}")
            except Exception as e:
                print(f"[ERR] Цикл: {e}")
                import traceback; traceback.print_exc()
                print("[ERR] Перезапуск через 3 сек...")
                time.sleep(3)

    def _msg(self, event):
        obj    = event.object.message
        msg    = obj['text'].strip()
        uid    = obj['from_id']
        msg_id = obj['id']

        u        = db.user(uid)
        lvl      = u['lvl']
        is_owner = (uid == CONFIG['owner_id'])

        if is_owner and lvl == 0:
            db.set(uid, 'lvl', 2)
            db.set(uid, 'prefix', 'Администратор')
            lvl = 2
            u   = db.user(uid)

        is_admin  = is_owner or (lvl > 0)
        can_mod   = is_owner or (lvl >= 1)
        can_admin = is_owner or (lvl >= 2)

        state = self.states.get(uid)
        ml    = msg.lower()

        print(f"\n[MSG] uid={uid} lvl={lvl} state={state or '-'}")
        print(f"[MSG] Текст: '{msg[:70]}'")
        if obj.get('attachments'):
            print(f"[MSG] Вложений: {len(obj['attachments'])}")

        # ══ ОТМЕНА ══════════════════════════════════════════════════════════
        if msg == "❌ Отмена":
            print(f"[ACTION] Отмена (был state={state})")
            if state:
                self.states.pop(uid, None)
                self.tmp.pop(uid, None)
                self.send(uid, "❌ Действие отменено.", KB.main(is_admin))
            else:
                self.send(uid, "❌ Нечего отменять.", KB.main(is_admin))
            return

        # ══ Набор кнопок меню (для сброса состояния) ════════════════════════
        MENU = {
            "📩 Норма","📈 Доп. репорт","💤 Неактив","📜 Статистика",
            "👑 Админ-панель","⚙️ Настройки","ℹ️ Помощь",
            "📋 Заявки","👥 Админы","➕ Добавить админа","➖ Снять права",
            "❓ Как проверять","⬅️ Назад в меню",
            "✉️ Норма","📊 Доп. репорт","😴 Неактив","📋 Все заявки",
            "🔕 Выключить уведомления","🔔 Включить уведомления",
            "📄 Переключить на текст","📨 Переключить на карточки",
            "✅ Одобрить заявку","❌ Отказать заявке","🔄 Обновить список",
        }
        if msg in MENU and state and not state.startswith("WAIT_REJECT"):
            print(f"[ACTION] Сброс state={state} (кнопка меню)")
            self.states.pop(uid, None)
            self.tmp.pop(uid, None)
            state = None

        # ════════════════════════════════════════════════════════════════════
        #  СОСТОЯНИЯ  (КРИТИЧНО: порядок проверок имеет значение!)
        #  WAIT_APPROVE_ID и WAIT_REJECT_ID должны идти ДО WAIT_REJECT_*
        #  иначе "ID" не парсится как int и бот молчит
        # ════════════════════════════════════════════════════════════════════

        # ── Ожидание ID для одобрения ──────────────────────────────────────
        if state == "WAIT_APPROVE_ID":
            print(f"[STATE] Обработка WAIT_APPROVE_ID, введено: '{msg}'")
            try:
                rid = int(msg.strip().lstrip('#'))
                print(f"[STATE] Одобрение #{rid} от @id{uid}")
                if not can_mod:
                    self.send(uid, "❌ Нужен LVL 1+")
                    self.states.pop(uid, None)
                    return
                self._do_approve(uid, rid, lvl)
            except ValueError:
                self.send(uid,
                    f"❌ Введи числовой номер заявки!\n\n"
                    f"Пример: 8\n"
                    f"Или с решёткой: #8\n\n"
                    f"Или нажми «❌ Отмена» для выхода.",
                    KB.cancel())
                return  # не сбрасываем состояние — даём ввести ещё раз
            self.states.pop(uid, None)
            return

        # ── Ожидание ID для отклонения ─────────────────────────────────────
        if state == "WAIT_REJECT_ID":
            print(f"[STATE] Обработка WAIT_REJECT_ID, введено: '{msg}'")
            try:
                rid = int(msg.strip().lstrip('#'))
                print(f"[STATE] Начало отклонения #{rid} от @id{uid}")
                if not can_mod:
                    self.send(uid, "❌ Нужен LVL 1+")
                    self.states.pop(uid, None)
                    return
                req = db.req_get(rid)
                if not req:
                    self.send(uid, f"❌ Заявка #{rid} не найдена. Введи другой ID или «❌ Отмена»:", KB.cancel())
                    return  # не сбрасываем — даём ввести ещё раз
                if req['status'] != 'pending':
                    self.send(uid, f"❌ Заявка #{rid} уже обработана ({req['status']}). Введи другой ID или «❌ Отмена»:", KB.cancel())
                    return
                self.states[uid] = f"WAIT_REJECT_{rid}"
                self.send(uid,
                    f"❌ Отклонение заявки #{rid}\n\n"
                    f"Напишите причину отказа (игрок её увидит):",
                    KB.cancel())
            except ValueError:
                self.send(uid,
                    f"❌ Введи числовой номер заявки!\n\n"
                    f"Пример: 8\n"
                    f"Или с решёткой: #8\n\n"
                    f"Или нажми «❌ Отмена» для выхода.",
                    KB.cancel())
                return  # не сбрасываем состояние — даём ввести ещё раз
            return

        # ── Причина отклонения (ПОСЛЕ проверок _ID выше!) ──────────────────
        # Состояние WAIT_REJECT_5, WAIT_REJECT_11 и т.д. (число в конце)
        if state and state.startswith("WAIT_REJECT_"):
            # Достаём числовой ID из конца строки состояния
            suffix = state.split("_")[-1]
            if not suffix.isdigit():
                # Защита: если вдруг suffix не число — сбрасываем
                print(f"[ERR] Невалидный state: {state}, сброс")
                self.states.pop(uid, None)
                self.send(uid, "❌ Ошибка состояния. Попробуйте заново.", KB.main(is_admin))
                return
            rid = int(suffix)
            print(f"[STATE] Причина отклонения для #{rid}: '{msg[:50]}'")
            req = db.req_get(rid)
            if req and req['status'] == 'pending':
                db.req_status(rid, 'rejected', uid, msg)
                self.send(req['user_id'],
                    f"❌ Заявка #{rid} ({REQ_NAMES.get(req['type'],'?')}) ОТКЛОНЕНА\n\n"
                    f"Причина: {msg}\n"
                    f"Решение принял: @id{uid}")
                self.send(uid, f"✅ Заявка #{rid} отклонена.", KB.req_actions())
                print(f"[ACTION] Заявка #{rid} отклонена @id{uid}")
            else:
                self.send(uid, "❌ Заявка не найдена или уже обработана.", KB.admin_panel())
            self.states.pop(uid, None)
            return

        # ID нового администратора
        if state == "WAIT_ADMIN_ID":
            print(f"[STATE] Ввод ID: '{msg}'")
            try:
                tid = parse_id(msg)
                self.tmp[uid] = {'tid': tid}
                self.states[uid] = "WAIT_ADMIN_LVL"
                self.send(uid,
                    f"✅ ID пользователя: {tid}\n\n"
                    f"Введите уровень:\n\n"
                    f"1 — Модератор (одобрение/отклонение заявок)\n"
                    f"2 — Администратор (полный доступ)\n"
                    f"0 — Снять права (сделать Игроком)",
                    KB.cancel())
            except ValueError:
                self.send(uid,
                    "❌ Неверный формат ID!\n\n"
                    "Поддерживаемые форматы:\n"
                    "• 123456\n• @id123456\n• [id123456|Имя] (упоминание VK)\n\n"
                    "Попробуйте ещё раз или нажмите «❌ Отмена»",
                    KB.cancel())
            return

        if state == "WAIT_ADMIN_LVL":
            print(f"[STATE] Ввод уровня: '{msg}'")
            try:
                lvl_new = int(msg.strip())
                if lvl_new not in (0, 1, 2):
                    self.send(uid, "❌ Введите 0, 1 или 2:", KB.cancel()); return
                tid = self.tmp[uid]['tid']
                if tid == CONFIG['owner_id'] and not is_owner:
                    self.send(uid, "❌ Нельзя изменить права создателя!", KB.admin_panel())
                    self.states.pop(uid, None); self.tmp.pop(uid, None); return
                db.user(tid)
                db.set(tid, 'lvl', lvl_new)
                role = ROLES.get(lvl_new, 'Игрок')
                db.set(tid, 'prefix', role)
                self.send(uid, f"✅ @id{tid} → {role} (Lvl {lvl_new})", KB.admin_panel())
                if lvl_new > 0:
                    self.send(tid, f"🎉 Вам выдан уровень {lvl_new} ({role})!\n\n{WELCOME_ADMIN}", KB.main(True))
                else:
                    self.send(tid, "ℹ️ Ваши права сняты.", KB.main(False))
                self.states.pop(uid, None); self.tmp.pop(uid, None)
            except ValueError:
                self.send(uid, "❌ Введите 0, 1 или 2:", KB.cancel())
            return

        if state == "WAIT_NORMA_TEXT":
            self.tmp[uid] = {'text': msg, 'nick': u['nickname']}
            self.states[uid] = "WAIT_NORMA_PHOTO"
            self.send(uid,
                "📸 Теперь прикрепите скриншот /astats:\n\n"
                "⚠️ Без скриншота заявка не будет принята!",
                KB.cancel())
            return

        if state == "WAIT_NORMA_PHOTO":
            if obj.get('attachments'):
                att = self._att(obj['attachments'])
                rid = db.req_add(uid, 'norma', self.tmp[uid]['text'], ','.join(att) or None)
                self.states.pop(uid, None); self.tmp.pop(uid, None)
                self.send(uid,
                    f"✅ Норма отправлена на проверку!\n\n"
                    f"📝 Номер заявки: #{rid}\n"
                    f"Чтобы удалить — /cancel {rid}\n"
                    f"Чтобы изменить — /edit {rid}",
                    KB.main(is_admin))
                self._notify(rid, msg_id)
            else:
                self.send(uid,
                    "❌ Нужен скриншот /astats!\n\n"
                    "Прикрепите фото к сообщению или нажмите «❌ Отмена»",
                    KB.cancel())
            return

        if state == "WAIT_EXTRA_TEXT":
            self.tmp[uid] = {'text': msg, 'nick': u['nickname']}
            self.states[uid] = "WAIT_EXTRA_PHOTO"
            self.send(uid,
                "📸 Прикрепите скриншоты проделанной работы:\n\n"
                "⚠️ Без доказательств заявка не будет принята!",
                KB.cancel())
            return

        if state == "WAIT_EXTRA_PHOTO":
            if obj.get('attachments'):
                att = self._att(obj['attachments'])
                rid = db.req_add(uid, 'extra', self.tmp[uid]['text'], ','.join(att) or None)
                self.states.pop(uid, None); self.tmp.pop(uid, None)
                self.send(uid,
                    f"✅ Доп. репорт отправлен!\n\n"
                    f"📝 Номер заявки: #{rid}\n"
                    f"Чтобы удалить — /cancel {rid}",
                    KB.main(is_admin))
                self._notify(rid, msg_id)
            else:
                self.send(uid,
                    "❌ Прикрепите скриншоты или нажмите «❌ Отмена»",
                    KB.cancel())
            return

        if state == "WAIT_INACTIVE_TEXT":
            rid = db.req_add(uid, 'inactive', msg)
            self.states.pop(uid, None)
            self.send(uid,
                f"✅ Заявка на неактив отправлена!\n\n"
                f"📝 Номер заявки: #{rid}\n"
                f"Чтобы удалить — /cancel {rid}",
                KB.main(is_admin))
            self._notify(rid)
            return

        if state and state.startswith("EDIT_"):
            parts = state.split("_")
            rid   = int(parts[1])
            rtype = parts[2]
            phase = parts[3] if len(parts) > 3 else "text"
            if phase == "text":
                self.tmp[uid]['edit_text'] = msg
                if rtype in ('norma', 'extra'):
                    self.states[uid] = f"EDIT_{rid}_{rtype}_photo"
                    self.send(uid, "📸 Прикрепите новое фото:", KB.cancel())
                else:
                    db.req_update(rid, content=msg)
                    self.send(uid, f"✅ Заявка #{rid} обновлена!", KB.main(is_admin))
                    self.states.pop(uid, None); self.tmp.pop(uid, None)
            elif phase == "photo":
                if obj.get('attachments'):
                    att = self._att(obj['attachments'])
                    db.req_update(rid, self.tmp[uid]['edit_text'], ','.join(att))
                    self.send(uid, f"✅ Заявка #{rid} обновлена с новым фото!", KB.main(is_admin))
                    self.states.pop(uid, None); self.tmp.pop(uid, None)
                else:
                    self.send(uid, "❌ Прикрепите фото или нажмите «❌ Отмена»", KB.cancel())
            return

        # ════════════════════════════════════════════════════════════════════
        #  КНОПКИ ОДОБРИТЬ / ОТКАЗАТЬ (нажатие на карточке заявки #N)
        # ════════════════════════════════════════════════════════════════════

        if msg.startswith("✅ Одобрить #") and is_admin:
            if not can_mod:
                self.send(uid, "❌ Нужен LVL 1+"); return
            try:
                rid = int(msg.replace("✅ Одобрить #", "").strip())
                print(f"[BTN] Одобрить #{rid} от @id{uid}")
                self._do_approve(uid, rid, lvl)
            except (ValueError, IndexError):
                self.send(uid, "❌ Ошибка при разборе ID заявки")
            return

        if msg.startswith("❌ Отказать #") and is_admin:
            if not can_mod:
                self.send(uid, "❌ Нужен LVL 1+"); return
            try:
                rid = int(msg.replace("❌ Отказать #", "").strip())
                print(f"[BTN] Отказать #{rid} от @id{uid}")
                req = db.req_get(rid)
                if not req:
                    self.send(uid, f"❌ Заявка #{rid} не найдена"); return
                if req['status'] != 'pending':
                    self.send(uid, f"❌ Уже обработана ({req['status']})"); return
                self.states[uid] = f"WAIT_REJECT_{rid}"
                self.send(uid,
                    f"❌ Отклонение заявки #{rid}\n\n"
                    f"Напишите причину отказа (игрок её увидит):",
                    KB.cancel())
            except (ValueError, IndexError):
                self.send(uid, "❌ Ошибка при разборе ID заявки")
            return

        # Кнопки из req_actions() — универсальные
        if msg == "✅ Одобрить заявку" and is_admin:
            if not can_mod: self.send(uid, "❌ Нужен LVL 1+"); return
            self.states[uid] = "WAIT_APPROVE_ID"
            self.send(uid,
                "✅ ОДОБРЕНИЕ ЗАЯВКИ\n\n"
                "Введите ID заявки (число):\n\n"
                "Пример: 8\n"
                "Или с решёткой: #8",
                KB.cancel())
            return

        if msg == "❌ Отказать заявке" and is_admin:
            if not can_mod: self.send(uid, "❌ Нужен LVL 1+"); return
            self.states[uid] = "WAIT_REJECT_ID"
            self.send(uid,
                "❌ ОТКЛОНЕНИЕ ЗАЯВКИ\n\n"
                "Введите ID заявки (число):\n\n"
                "Пример: 8\n"
                "Или с решёткой: #8",
                KB.cancel())
            return

        if msg == "🔄 Обновить список" and is_admin:
            n = len(db.req_pending('norma'))
            e = len(db.req_pending('extra'))
            i = len(db.req_pending('inactive'))
            self.send(uid,
                f"🔄 Обновлено!\n\n"
                f"📋 Заявок на проверке: {n+e+i}\n"
                f"📩 Норма: {n} | 📈 Доп.: {e} | 💤 Неактив: {i}\n\n"
                f"Выберите категорию в «📋 Заявки»",
                KB.admin_panel())
            return

        # ════════════════════════════════════════════════════════════════════
        #  ТЕКСТОВЫЕ КОМАНДЫ
        # ════════════════════════════════════════════════════════════════════

        if ml in ("начать","start","/start","меню","menu","привет","hello") or msg == "ℹ️ Помощь":
            self.states.pop(uid, None); self.tmp.pop(uid, None)
            self.send(uid, WELCOME_ADMIN if is_admin else WELCOME_USER, KB.main(is_admin))
            return

        if msg.startswith("/cancel "):
            try:
                rid = int(msg.split()[1])
                req = db.req_get(rid)
                if not req: self.send(uid, f"❌ Заявка #{rid} не найдена"); return
                if int(req['user_id']) != uid: self.send(uid, "❌ Нельзя удалить чужую заявку!"); return
                if req['status'] != 'pending': self.send(uid, f"❌ Заявка #{rid} уже обработана"); return
                db.req_delete(rid)
                self.send(uid, f"🗑 Заявка #{rid} ({REQ_NAMES.get(req['type'],'?')}) удалена")
                try:
                    self.vk.messages.send(peer_id=CONFIG['owner_id'],
                        message=f"🔴 Заявка #{rid} удалена игроком @id{uid}",
                        random_id=get_random_id())
                except Exception:
                    pass
            except (ValueError, IndexError):
                self.send(uid, "❌ Использование: /cancel [ID]\nПример: /cancel 5")
            return

        if msg.startswith("/edit "):
            try:
                rid = int(msg.split()[1])
                req = db.req_get(rid)
                if not req: self.send(uid, f"❌ Заявка #{rid} не найдена"); return
                if int(req['user_id']) != uid: self.send(uid, "❌ Нельзя редактировать чужую!"); return
                if req['status'] != 'pending': self.send(uid, "❌ Уже обработана — создайте новую."); return
                rtype = req['type']
                self.states[uid] = f"EDIT_{rid}_{rtype}_text"
                self.tmp[uid] = {'nick': u['nickname']}
                self.send(uid,
                    f"✏️ Редактирование заявки #{rid} ({REQ_NAMES.get(rtype,'?')})\n\n{TEMPLATES.get(rtype,'')}",
                    KB.cancel())
            except (ValueError, IndexError):
                self.send(uid, "❌ Использование: /edit [ID]")
            return

        if msg.startswith("/approve ") and is_admin:
            if not can_mod: self.send(uid, "❌ Нужен LVL 1+"); return
            try:
                rid = int(msg.split()[1])
                print(f"[CMD] /approve #{rid} от @id{uid}")
                self._do_approve(uid, rid, lvl)
            except (ValueError, IndexError):
                self.send(uid, "❌ Использование: /approve [ID]")
            return

        if msg.startswith("/reject ") and is_admin:
            if not can_mod: self.send(uid, "❌ Нужен LVL 1+"); return
            try:
                rid = int(msg.split()[1])
                req = db.req_get(rid)
                if not req: self.send(uid, f"❌ Заявка #{rid} не найдена"); return
                if req['status'] != 'pending': self.send(uid, f"❌ Уже обработана ({req['status']})"); return
                self.states[uid] = f"WAIT_REJECT_{rid}"
                self.send(uid, f"❌ Отклонение заявки #{rid}\nНапишите причину:", KB.cancel())
            except (ValueError, IndexError):
                self.send(uid, "❌ Использование: /reject [ID]")
            return

        if msg.startswith("!nick "):
            nick = msg[6:].strip()
            if nick:
                db.set(uid, 'nickname', nick)
                self.send(uid, f"✅ Ник установлен: {nick}")
            else:
                self.send(uid, "❌ Использование: !nick [Ник]")
            return

        if msg.startswith("!setlvl") and is_admin:
            if not can_admin: self.send(uid, "❌ Нужен LVL 2+"); return
            try:
                parts = msg.split()
                if len(parts) < 3: self.send(uid, "❌ Использование: !setlvl [ID] [0/1/2]"); return
                tid   = parse_id(parts[1])
                lvl_n = int(parts[2])
                if lvl_n not in (0, 1, 2): self.send(uid, "❌ Уровень: 0, 1 или 2"); return
                if tid == CONFIG['owner_id'] and not is_owner:
                    self.send(uid, "❌ Нельзя изменить права создателя!"); return
                db.user(tid); db.set(tid, 'lvl', lvl_n)
                role = ROLES.get(lvl_n, 'Игрок')
                db.set(tid, 'prefix', role)
                self.send(uid, f"✅ @id{tid} → {role} (Lvl {lvl_n})")
                if lvl_n > 0:
                    self.send(tid, f"🎉 Уровень {lvl_n} ({role})!\n\n{WELCOME_ADMIN}", KB.main(True))
                else:
                    self.send(tid, "ℹ️ Права сняты.", KB.main(False))
            except ValueError:
                self.send(uid, "❌ Использование: !setlvl [ID] [0/1/2]")
            return

        if msg.startswith("!dellvl") and is_admin:
            if not can_admin: self.send(uid, "❌ Нужен LVL 2+"); return
            try:
                parts = msg.split()
                if len(parts) < 2: self.send(uid, "❌ Использование: !dellvl [ID]"); return
                tid = parse_id(parts[1])
                if tid == CONFIG['owner_id']: self.send(uid, "❌ Нельзя снять права создателя!"); return
                tu = db.user(tid)
                if tu['lvl'] == 0: self.send(uid, f"❌ У @id{tid} нет прав"); return
                db.set(tid, 'lvl', 0); db.set(tid, 'prefix', 'Игрок')
                self.send(uid, f"✅ С @id{tid} ({tu['nickname']}) сняты права")
                self.send(tid, "ℹ️ Ваши администраторские права сняты.", KB.main(False))
            except ValueError:
                self.send(uid, "❌ Использование: !dellvl [ID]")
            return

        # ════════════════════════════════════════════════════════════════════
        #  КНОПКИ МЕНЮ
        # ════════════════════════════════════════════════════════════════════

        if msg == "📩 Норма":
            self.states[uid] = "WAIT_NORMA_TEXT"
            self.send(uid, TEMPLATES['norma'], KB.cancel())

        elif msg == "📈 Доп. репорт":
            self.states[uid] = "WAIT_EXTRA_TEXT"
            self.send(uid, TEMPLATES['extra'], KB.cancel())

        elif msg == "💤 Неактив":
            self.states[uid] = "WAIT_INACTIVE_TEXT"
            self.send(uid, TEMPLATES['inactive'], KB.cancel())

        elif msg == "📜 Статистика":
            reqs = db.user_reqs(uid)
            a  = sum(1 for r in reqs if r['status'] == 'approved')
            p  = sum(1 for r in reqs if r['status'] == 'pending')
            rj = sum(1 for r in reqs if r['status'] == 'rejected')
            self.send(uid,
                f"📊 СТАТИСТИКА\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 Ник:         {u['nickname']}\n"
                f"🔰 Ранг:        {u['prefix']} (Lvl {u['lvl']})\n"
                f"📅 Регистрация: {u['reg_date']}\n"
                f"✅ Норм сдано:  {u['norma_days']}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n📋 ЗАЯВКИ:\n\n"
                f"✅ Одобрено:    {a}\n"
                f"⏳ На проверке: {p}\n"
                f"❌ Отклонено:   {rj}\n\n"
                f"💡 /cancel [ID] — удалить заявку\n"
                f"   /edit [ID]   — редактировать",
                KB.main(is_admin))

        elif msg == "⚙️ Настройки" and is_admin:
            notif_on  = u['notif_on']
            notif_fmt = u['notif_fmt']
            self.send(uid,
                f"⚙️ НАСТРОЙКИ АДМИНИСТРАТОРА\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🔔 Уведомления о заявках:\n"
                f"   {'✅ Включены' if notif_on else '❌ Выключены'}\n\n"
                f"📨 Формат получения заявок:\n"
                f"   {'✅ По одной (с фото)' if notif_fmt == 1 else '📄 Сплошным текстом'}\n\n"
                f"Нажмите кнопку чтобы переключить:",
                KB.settings(notif_on, notif_fmt))

        elif msg == "🔕 Выключить уведомления" and is_admin:
            db.set(uid, 'notif_on', 0)
            u = db.user(uid)
            self.send(uid, "🔕 Уведомления выключены", KB.settings(0, u['notif_fmt']))

        elif msg == "🔔 Включить уведомления" and is_admin:
            db.set(uid, 'notif_on', 1)
            u = db.user(uid)
            self.send(uid, "🔔 Уведомления включены", KB.settings(1, u['notif_fmt']))

        elif msg == "📄 Переключить на текст" and is_admin:
            db.set(uid, 'notif_fmt', 0)
            u = db.user(uid)
            self.send(uid, "📄 Формат изменён: сплошным текстом", KB.settings(u['notif_on'], 0))

        elif msg == "📨 Переключить на карточки" and is_admin:
            db.set(uid, 'notif_fmt', 1)
            u = db.user(uid)
            self.send(uid, "📨 Формат изменён: по одной карточке (с фото)", KB.settings(u['notif_on'], 1))

        elif msg == "👑 Админ-панель" and is_admin:
            cnt = len(db.req_pending())
            role_desc = ROLES.get(lvl, 'Неизвестно')
            self.send(uid,
                f"👑 АДМИН-ПАНЕЛЬ\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📋 Заявок на проверке: {cnt}\n"
                f"🔰 Ваша роль: {role_desc} (LVL {lvl})",
                KB.admin_panel())

        elif msg == "📋 Заявки" and is_admin:
            n = len(db.req_pending('norma'))
            e = len(db.req_pending('extra'))
            i = len(db.req_pending('inactive'))
            self.send(uid,
                f"📋 ЗАЯВКИ НА ПРОВЕРКЕ: {n+e+i}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📩 Норма:       {n}\n"
                f"📈 Доп. репорт: {e}\n"
                f"💤 Неактив:     {i}\n\n"
                f"Выберите категорию:",
                KB.req_filter())

        elif msg in ("✉️ Норма","📊 Доп. репорт","😴 Неактив","📋 Все заявки") and is_admin:
            rmap = {
                "✉️ Норма":        "norma",
                "📊 Доп. репорт":  "extra",
                "😴 Неактив":      "inactive",
                "📋 Все заявки":   None,
            }
            rtype = rmap[msg]
            reqs  = db.req_pending(rtype)
            lbl   = REQ_NAMES.get(rtype, 'ВСЕ') if rtype else 'ВСЕ'
            print(f"[BTN] Фильтр '{lbl}': {len(reqs)} заявок")

            if not reqs:
                self.send(uid, f"📭 Нет заявок: {lbl}", KB.admin_panel())
                return

            fmt = u['notif_fmt']
            self.send(uid,
                f"📋 Загружаю «{lbl}»: {len(reqs)} заявок...",
                KB.admin_panel())

            if fmt == 1:
                for req in reqs[:10]:
                    self._card(uid, req)
                    time.sleep(0.3)
                if len(reqs) > 10:
                    self.send(uid, f"...и ещё {len(reqs)-10} заявок")
                self.send(uid,
                    f"👆 Показано {min(len(reqs),10)} из {len(reqs)} заявок «{lbl}».\n"
                    f"Выберите действие:",
                    KB.req_actions())
            else:
                text = f"📋 ЗАЯВКИ «{lbl}» ({len(reqs)}):\n\n"
                for req in reqs[:10]:
                    ru = db.user(req['user_id'])
                    text += (
                        f"{REQ_EMOJI.get(req['type'],'📝')} #{req['id']} — "
                        f"{REQ_NAMES.get(req['type'],'?')}\n"
                        f"👤 @id{req['user_id']} ({ru['nickname']})\n"
                        f"📅 {req['created_at']}\n"
                        f"{req['content']}\n"
                    )
                    if req['attachments']:
                        text += f"📸 Фото: {len(req['attachments'].split(','))} шт.\n"
                    text += "━━━━━━━━━━━━━━━━━━━━━━\n"
                if len(reqs) > 10:
                    text += f"\n...и ещё {len(reqs)-10} заявок"
                self.send(uid, text, KB.req_actions())

        elif msg == "👥 Админы" and is_admin:
            admins = db.admins()
            if admins:
                text = "👥 АДМИНИСТРАЦИЯ:\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                for a in admins:
                    ni    = "🔔" if a['notif_on'] else "🔕"
                    a_lvl = min(int(a['lvl']), 2)
                    role  = ROLES.get(a_lvl, 'Игрок')
                    text += f"• @id{a['user_id']} — {a['nickname']}\n  🔰 {role} (Lvl {a_lvl}) {ni} | ✅ Норм: {a['norma_days']}\n\n"
                self.send(uid, text, KB.admin_panel())
            else:
                self.send(uid, "📭 Администраторов нет", KB.admin_panel())

        elif msg == "➕ Добавить админа" and is_admin:
            if not can_admin:
                self.send(uid, "❌ Нужен LVL 2+ для выдачи прав", KB.admin_panel()); return
            self.states[uid] = "WAIT_ADMIN_ID"
            self.send(uid,
                "➕ ДОБАВИТЬ АДМИНИСТРАТОРА\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Напишите ID пользователя:\n\n"
                "• 123456\n• @id123456\n• [id123456|Имя]\n\nДля отмены — «❌ Отмена»",
                KB.cancel())

        elif msg == "➖ Снять права" and is_admin:
            if not can_admin:
                self.send(uid, "❌ Нужен LVL 2+ для снятия прав", KB.admin_panel()); return
            self.send(uid,
                "➖ СНЯТЬ ПРАВА\n\nКоманда: !dellvl [ID]\nПример:  !dellvl 123456",
                KB.admin_panel())

        elif msg == "❓ Как проверять" and is_admin:
            self.send(uid,
                "💡 КАК ПРОВЕРЯТЬ ЗАЯВКИ\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "1️⃣ Нажмите «📋 Заявки»\n\n"
                "2️⃣ Выберите категорию:\n"
                "   ✉️ Норма | 📊 Доп. | 😴 Неактив | 📋 Все\n\n"
                "3️⃣ После загрузки списка нажмите:\n"
                "   ✅ Одобрить заявку — бот спросит ID\n"
                "   ❌ Отказать заявке — бот спросит ID и причину\n\n"
                "4️⃣ Введи номер (ID) заявки — цифры из карточки\n"
                "   Например: 8  или  #8\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "Текстовые команды (тоже работают):\n"
                "/approve 5 → одобрить заявку #5\n"
                "/reject 5  → отклонить #5\n\n"
                "⚙️ Формат заявок — в «⚙️ Настройки»",
                KB.admin_panel())

        elif msg == "⬅️ Назад в меню":
            if is_admin:
                self.send(uid, "👑 Главное меню", KB.main(True))
            else:
                self.send(uid, "👋 Главное меню", KB.main(False))

        else:
            if not state:
                self.send(uid,
                    "❓ Не понимаю команду.\nИспользуй кнопки или напиши «Начать»",
                    KB.main(is_admin))


# ═══════════════════════════════════════════════
if __name__ == "__main__":
    try:
        Bot().run()
    except KeyboardInterrupt:
        print("\n[STOP] Бот остановлен")
    except Exception as e:
        print(f"\n[FATAL] {e}")
        import traceback; traceback.print_exc()
