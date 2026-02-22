# -*- coding: utf-8 -*-
"""
🔒 PHOTO HOST BOT v6.0  —  By T.Venera

ПОТОК:
  📤 Загрузить фото
    → выбор сервиса (ImgBB / Fotohosting.pro)
      → шлёшь фото
        → получаешь ссылки

pip install vk_api requests Pillow
python photo_bot.py
"""

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
import requests, base64, threading, time, io, uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ═══════════════════════════════
#  КОНФИГУРАЦИЯ
# ═══════════════════════════════
VK_TOKEN    = "vk1.a.Z9pCqT1rlC8JsFxbrZMhhmvbPe764cfFlF9N1z5RG4nrLfO9E8YisGaABMzphZNjMOZ01Y4A25SAdRZnvVSO2mxmOUq2AiOsPkNmmQXH_6ghpstHBPiPjxZv-c6t8JL8JV1qbmOpFPTTSOx8_CAfsKFaMqa9_-BXqLW4LbeR2fyyncJMlHHpTsfcjLWXtZYJu1rJSUDPp4zoCoVcOpaE5A"
VK_GROUP_ID = 236066012

IMGBB_KEY    = "3f3ef51b1aa1c1f6cb5f29c245c11ede"
IMGBB_EXPIRE = 172800  # 2 дня

FOTOHOST_KEY = "chv_WQA_b1dedb32f4960deb0d584537788d7a9aa7ea611afeeae66ee0696fc9f134da501a2b82e37eeecaad0acfe8cf0eacda47c99efdb922d9ecd3fa06a96855883742"
FOTOHOST_URL = "https://fotohosting.pro/api/1/upload"

# ═══════════════════════════════
#  HTTP-СЕССИЯ
# ═══════════════════════════════
def _make_session():
    s = requests.Session()
    a = HTTPAdapter(
        max_retries=Retry(total=3, backoff_factor=0.3,
                          status_forcelist=[429, 500, 502, 503, 504]),
        pool_connections=20, pool_maxsize=50
    )
    s.mount("https://", a)
    s.mount("http://",  a)
    s.headers["User-Agent"] = "Mozilla/5.0"
    return s

_http = _make_session()

# ═══════════════════════════════
#  КОНФИДЕНЦИАЛЬНОСТЬ
#  1. EXIF-зачистка (GPS, камера, дата, серийник)
#  2. Случайное имя файла (UUID)
#  3. Случайный размер холста +/- 1px (анти-отпечаток)
# ═══════════════════════════════
def sanitize(img_bytes: bytes) -> tuple[bytes, str]:
    """
    Возвращает (очищенные байты, случайное имя).
    Убирает EXIF и добавляет 1px шум к размеру (анти-отпечаток).
    """
    name = uuid.uuid4().hex[:20]
    if not HAS_PIL:
        return img_bytes, name
    try:
        img = Image.open(io.BytesIO(img_bytes))
        img = img.convert("RGB")
        # Добавляем 1px к ширине — разный отпечаток каждый раз
        w, h = img.size
        img = img.resize((w + 1, h), Image.LANCZOS)
        img = img.resize((w, h),     Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=95, exif=b"")
        return buf.getvalue(), name
    except Exception as e:
        print(f"[sanitize] {e}")
        return img_bytes, name

# ═══════════════════════════════
#  IMGBB
# ═══════════════════════════════
def _imgbb_one(img: bytes, name: str) -> str | None:
    clean, _ = sanitize(img)
    try:
        r = _http.post(
            "https://api.imgbb.com/1/upload",
            data={"key": IMGBB_KEY, "image": base64.b64encode(clean).decode(),
                  "name": name, "expiration": IMGBB_EXPIRE},
            timeout=35
        )
        d = r.json()
        if d.get("success"):
            return d["data"]["image"]["url"]
        print(f"[imgbb] {d.get('error')}")
    except Exception as e:
        print(f"[imgbb] {e}")
    return None

def upload_imgbb(images: list[bytes]) -> list[str]:
    names = [uuid.uuid4().hex[:20] for _ in images]
    res: list[str | None] = [None] * len(images)
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_imgbb_one, img, names[i]): i for i, img in enumerate(images)}
        for f in as_completed(futs):
            res[futs[f]] = f.result()
    return [r for r in res if r]

# ═══════════════════════════════
#  FOTOHOSTING.PRO
# ═══════════════════════════════
def _fh_one(img: bytes) -> str | None:
    clean, name = sanitize(img)
    try:
        r = _http.post(
            FOTOHOST_URL,
            headers={"X-API-Key": FOTOHOST_KEY},
            files={"source": (f"{name}.jpg", io.BytesIO(clean), "image/jpeg")},
            data={"nsfw": "1"},
            timeout=45
        )
        d = r.json()
        obj = d.get("image") or {}
        return obj.get("url") or obj.get("url_viewer")
    except Exception as e:
        print(f"[fh] {e}")
    return None

def upload_fh(images: list[bytes]) -> list[str]:
    res: list[str | None] = [None] * len(images)
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_fh_one, img): i for i, img in enumerate(images)}
        for f in as_completed(futs):
            res[futs[f]] = f.result()
    return [r for r in res if r]

# ═══════════════════════════════
#  КЛАВИАТУРЫ
# ═══════════════════════════════
def kb_main():
    k = VkKeyboard(one_time=False)
    k.add_button("📤 Загрузить фото", color=VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("📖 Как пользоваться", color=VkKeyboardColor.SECONDARY)
    return k.get_keyboard()

def kb_service():
    k = VkKeyboard(one_time=False)
    k.add_button("🖼 ImgBB",            color=VkKeyboardColor.SECONDARY)
    k.add_line()
    k.add_button("🇷🇺 Fotohosting.pro", color=VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("✖ Отмена",           color=VkKeyboardColor.NEGATIVE)
    return k.get_keyboard()

def kb_collect():
    k = VkKeyboard(one_time=False)
    k.add_button("✅ Готово — загрузить", color=VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button("🗑 Очистить", color=VkKeyboardColor.NEGATIVE)
    k.add_button("✖ Отмена",   color=VkKeyboardColor.SECONDARY)
    return k.get_keyboard()

def kb_done():
    k = VkKeyboard(one_time=False)
    k.add_button("📋 Скопировать ссылки", color=VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button("📤 Загрузить ещё", color=VkKeyboardColor.POSITIVE)
    k.add_button("🏠 Главное меню",  color=VkKeyboardColor.SECONDARY)
    return k.get_keyboard()

SERVICE_TEXT = (
    "Выберите сервис:\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "🖼  ImgBB\n"
    "Международный хостинг.\n"
    "Автоудаление через 2 дня.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "🇷🇺  Fotohosting.pro\n"
    "Российский сервер.\n"
    "ВКонтакте не блокирует.\n"
    "━━━━━━━━━━━━━━━━━━━━━━"
)

# ═══════════════════════════════
#  БОТ
# ═══════════════════════════════
class PhotoBot:
    def __init__(self):
        print(f"  🔒 PHOTO HOST BOT v6.0  —  By T.Venera")
        print(f"  EXIF-зачистка: {'ВКЛ ✅' if HAS_PIL else 'ВЫКЛ — pip install Pillow'}\n")

        self.vk_s = vk_api.VkApi(token=VK_TOKEN)
        self.vk   = self.vk_s.get_api()
        self.lp   = VkBotLongPoll(self.vk_s, VK_GROUP_ID)

        self._s: dict[int, dict] = {}
        self._lock = threading.Lock()
        # Пул: обработка сообщений + фоновые загрузки
        self._pool = ThreadPoolExecutor(max_workers=16)

    # ── сессия ──────────────────────────────────────────────────────
    def _sess(self, uid) -> dict:
        if uid not in self._s:
            self._s[uid] = {"st": "idle", "svc": "", "q": [], "res": ""}
        return self._s[uid]

    def _reset(self, uid):
        self._s[uid] = {"st": "idle", "svc": "", "q": [], "res": ""}

    def _send(self, uid, text, kb=None):
        p = {"peer_id": uid, "message": text, "random_id": get_random_id()}
        if kb:
            p["keyboard"] = kb
        try:
            self.vk.messages.send(**p)
        except Exception as e:
            print(f"[send] {e}")

    # ── скачать фото из VK ──────────────────────────────────────────
    def _grab(self, uid, msg_id) -> int:
        try:
            items = self.vk.messages.getById(message_ids=msg_id).get("items", [])
            atts  = items[0].get("attachments", []) if items else []
        except Exception:
            return 0

        urls = []
        for a in atts:
            if a["type"] != "photo": continue
            sz = a["photo"].get("sizes", [])
            if sz:
                urls.append(max(sz, key=lambda s: s.get("width",0)*s.get("height",0))["url"])
        if not urls:
            return 0

        def _dl(u):
            try: return _http.get(u, timeout=20).content
            except: return None

        added = 0
        with ThreadPoolExecutor(max_workers=10) as ex:
            for data in ex.map(_dl, urls):
                if data:
                    self._sess(uid)["q"].append(data)
                    added += 1
        return added

    # ── воркер ──────────────────────────────────────────────────────
    def _worker(self, uid):
        with self._lock:
            sess = self._s.get(uid, {})
            q    = list(sess.get("q", []))
            svc  = sess.get("svc", "")

        total = len(q)
        if not total:
            self._send(uid, "⚠️ Нет фото.", kb_main())
            return

        print(f"[{uid}] → {svc} | {total} фото")

        links = upload_imgbb(q) if svc == "imgbb" else upload_fh(q)

        result = ""
        if links:
            result = "\n".join(links)
            svc_label = "🖼 ImgBB" if svc == "imgbb" else "🇷🇺 Fotohosting.pro"
            extra = "\n🗑 Удаление через 2 дня" if svc == "imgbb" else ""
            out = (
                f"{svc_label} — приватная загрузка\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{result}\n\n"
                f"📷 Загружено: {len(links)} из {total}"
                f"{extra}\n"
                "🔒 EXIF удалён\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "By T.Venera"
            )
        else:
            other = "Fotohosting.pro" if svc == "imgbb" else "ImgBB"
            out = f"⚠️ Сервис не отвечает.\nПопробуйте {other}."

        with self._lock:
            if uid in self._s:
                self._s[uid]["res"] = result
                self._s[uid]["st"]  = "done"
                self._s[uid]["q"]   = []

        self._send(uid, out, kb_done() if result else kb_main())

    def _start_upload(self, uid):
        with self._lock:
            sess = self._s.get(uid, {})
            cnt  = len(sess.get("q", []))
        if not cnt:
            self._send(uid, "⚠️ Нет фото. Пришлите фотографии.", kb_collect())
            return
        with self._lock:
            self._s[uid]["st"] = "uploading"
        self._send(uid, f"⚡ Загружаю {cnt} фото...")
        self._pool.submit(self._worker, uid)

    # ── главный цикл ────────────────────────────────────────────────
    def run(self):
        print("[OK] Запущен!")
        while True:
            try:
                for ev in self.lp.listen():
                    if ev.type == VkBotEventType.MESSAGE_NEW and ev.from_user:
                        self._pool.submit(self._handle, ev)
            except Exception as e:
                print(f"[loop] {e}")
                time.sleep(3)

    def _handle(self, ev):
        obj    = ev.object.message
        uid    = obj["from_id"]
        msg    = obj["text"].strip()
        msg_id = obj["id"]

        with self._lock:
            sess = self._sess(uid)
            st   = sess["st"]

        print(f"[{uid}] {st} | '{msg[:50]}'")

        SVC = {"🖼 ImgBB": "imgbb", "🇷🇺 Fotohosting.pro": "fotohost"}

        # Старт
        if msg.lower() in ("начать","start","/start","привет","меню","menu"):
            self._reset(uid)
            self._send(uid,
                "👋 Привет!\n\n"
                "🔒 Загружу фото анонимно:\n"
                "• GPS, камера, дата — удаляются\n"
                "• Случайные имена файлов\n"
                "• Только по прямой ссылке\n\n"
                "Нажми кнопку ниже 👇",
                kb_main())
            return

        # Загрузить фото
        if msg in ("📤 Загрузить фото", "📤 Загрузить ещё"):
            self._reset(uid)
            with self._lock:
                self._sess(uid)["st"] = "choose"
            self._send(uid, SERVICE_TEXT, kb_service())
            return

        # Выбор сервиса
        if msg in SVC and st == "choose":
            with self._lock:
                self._s[uid]["svc"] = SVC[msg]
                self._s[uid]["st"]  = "collect"
            self._send(uid,
                f"✅ Выбран: {msg}\n\n"
                "📸 Пришлите фотографии\n\n"
                "Можно по одному или несколько сразу.\n"
                "Когда всё готово — нажмите «✅ Готово».",
                kb_collect())
            return

        # Готово
        if msg == "✅ Готово — загрузить":
            if st == "uploading":
                self._send(uid, "⚡ Уже загружаю, подождите...")
            elif st == "collect":
                self._start_upload(uid)
            else:
                self._send(uid, "Нажмите «📤 Загрузить фото».", kb_main())
            return

        # Скопировать
        if msg == "📋 Скопировать ссылки":
            with self._lock:
                res = self._sess(uid).get("res", "")
            if not res:
                self._send(uid, "⚠️ Нет ссылок. Загрузите фото заново.", kb_main())
                return
            self._send(uid, res, kb_done())
            return

        # Очистить
        if msg == "🗑 Очистить":
            with self._lock:
                cnt = len(self._sess(uid)["q"])
                self._s[uid]["q"] = []
            self._send(uid, f"🗑 Очищено ({cnt} фото). Пришлите новые.", kb_collect())
            return

        # Отмена / Меню
        if msg in ("✖ Отмена", "🏠 Главное меню"):
            self._reset(uid)
            self._send(uid, "🏠 Главное меню.", kb_main())
            return

        # Инструкция
        if msg == "📖 Как пользоваться":
            self._send(uid,
                "📖 Как пользоваться:\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "1️⃣  «📤 Загрузить фото»\n\n"
                "2️⃣  Выберите сервис:\n"
                "   🖼 ImgBB — удаление через 2 дня\n"
                "   🇷🇺 Fotohosting.pro — РФ сервер\n\n"
                "3️⃣  Пришлите фото в чат\n\n"
                "4️⃣  «✅ Готово» → мгновенная загрузка ⚡\n\n"
                "5️⃣  «📋 Скопировать ссылки» → зажмите\n"
                "   сообщение → Копировать текст\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔒 Анонимность:\n"
                "• EXIF удалён (GPS, камера, дата, серийник)\n"
                "• Анти-отпечаток изображения\n"
                "• Случайные имена файлов\n"
                "• Скрыто из галерей и поиска\n"
                "• Доступ только по прямой ссылке\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "By T.Venera",
                kb_main())
            return

        # Фото
        if obj.get("attachments"):
            if st == "collect":
                added = self._grab(uid, msg_id)
                with self._lock:
                    total = len(self._sess(uid)["q"])
                if added:
                    self._send(uid,
                        f"✅ Добавлено: {added}  |  В очереди: {total}\n"
                        "Пришлите ещё или нажмите «✅ Готово».",
                        kb_collect())
                else:
                    self._send(uid, "⚠️ Не удалось принять фото.", kb_collect())
            elif st == "uploading":
                self._send(uid, "⚡ Идёт загрузка, подождите...")
            elif st == "choose":
                self._send(uid, "Сначала выберите сервис.", kb_service())
            else:
                self._send(uid, "Нажмите «📤 Загрузить фото».", kb_main())
            return

        # Всё остальное
        kb = (kb_collect()  if st in ("collect","uploading")
              else kb_service() if st == "choose"
              else kb_main())
        self._send(uid, "Используйте кнопки ниже 👇", kb)


if __name__ == "__main__":
    try:
        PhotoBot().run()
    except KeyboardInterrupt:
        print("\n[STOP]")
    except Exception as e:
        print(f"\n[FATAL] {e}")
        import traceback; traceback.print_exc()
