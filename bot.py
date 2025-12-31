import os, time, requests, asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ===================== CONFIG =====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ACTIVATION_CODE = "MY_SECRET_403"
ADMIN_USERNAME = "DARK_NET_403"

HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = (5, 10)
MAX_WORKERS = 20
MAX_PAGES = 200

session = requests.Session()
session.headers.update(HEADERS)

AUTHORIZED_USERS = set()
USER_STATE = {}

# ===================== AUTHOR INFO =====================
AUTHOR_INFO_TEXT = (
    "🤖 Telegram Website Cloner Bot\n\n"
    "👤 Made by: Ariyan Rabbi\n"
    "🌐 Facebook: <a href=\"https://www.facebook.com/share/1MZXv7dUUf/">Ariyan Rabbi</a>\n"
    "💻 GitHub: <a href=\"https://github.com/DARK-NET-403">DARK-NET</a>\n\n"
)

# 🔥 REAL-TIME QUEUE
MESSAGE_QUEUE = Queue()

# 🌈 RAINBOW LOADER
RAINBOW = ["🔴","🟡","🟢","🔵","🟣","🟠"]
SPINNER = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

# ===================== UTILS =====================
def normalize_path(path):
    path = path.lstrip("/")
    if path == "" or path.endswith("/"):
        return path + "index.html"
    if "." not in os.path.basename(path):
        return path + "/index.html"
    return path

def safe_mkdir(p):
    os.makedirs(p, exist_ok=True)

def get_folder_size(path):
    total = 0
    for r, _, fs in os.walk(path):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(r, f))
            except:
                pass
    return total

def count_files_folders(path):
    fc = dc = 0
    for r, d, f in os.walk(path):
        fc += len(f)
        dc += len(d)
    return fc, dc

# ===================== START =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    # 1️⃣ First message → Author info (HTML enabled)
    await update.message.reply_text(
        AUTHOR_INFO_TEXT,
        parse_mode="HTML"
    )

    # 2️⃣ Second message → Activation / Menu
    if uid not in AUTHORIZED_USERS:
        USER_STATE[uid] = "ACTIVATION"
        await update.message.reply_text("🔐 Enter Activation Code:")
    else:
        await show_menu(update)

# ===================== MENU =====================
async def show_menu(update: Update):
    keyboard = [
        ["🌐 Clone Website"],
        ["📞 Contact Admin"],
        ["❌ Exit"]
    ]
    await update.message.reply_text(
        "📌 Select Option:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ===================== HANDLER =====================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    if USER_STATE.get(uid) == "ACTIVATION":
        if text == ACTIVATION_CODE:
            AUTHORIZED_USERS.add(uid)
            USER_STATE[uid] = "MENU"
            await update.message.reply_text("✅ Bot Activated Successfully!")
            await show_menu(update)
        else:
            await update.message.reply_text("❌ Invalid Activation Code")
        return

    if uid not in AUTHORIZED_USERS:
        return

    if text == "🌐 Clone Website":
        USER_STATE[uid] = "URL"
        await update.message.reply_text("🔗 Send Website URL:")
        return

    if text == "📞 Contact Admin":
        await update.message.reply_text(f"https://t.me/{ADMIN_USERNAME}")
        return

    if text == "❌ Exit":
        USER_STATE.clear()
        AUTHORIZED_USERS.clear()
        await update.message.reply_text("👋 Bot Closed")
        return

    if USER_STATE.get(uid) == "URL":
        USER_STATE[uid] = "BUSY"
        await update.message.reply_text("🚀 Clone started...")
        asyncio.create_task(run_clone_async(text, update))

# ===================== RAINBOW LIVE LOADER =====================
async def live_loader(update):
    i = 0
    last_msg = None
    uid = update.effective_user.id

    while USER_STATE.get(uid) == "BUSY":
        await asyncio.sleep(0.3)

        file_msg = None
        if not MESSAGE_QUEUE.empty():
            file_msg = MESSAGE_QUEUE.get()

        spin = SPINNER[i % len(SPINNER)]
        color = RAINBOW[i % len(RAINBOW)]
        i += 1

        text = (
            f"{color} {spin} Downloading...\n"
            f"{file_msg if file_msg else 'Scanning files...'}"
        )

        try:
            if last_msg:
                await last_msg.edit_text(text)
            else:
                last_msg = await update.message.reply_text(text)
        except:
            pass

# ===================== ASYNC WRAPPER =====================
async def run_clone_async(url, update):
    loader_task = asyncio.create_task(live_loader(update))

    result = await asyncio.to_thread(clone_website_sync, url)

    USER_STATE[update.effective_user.id] = "DONE"
    await loader_task

    await update.message.reply_text(result)

# ===================== CLONER (SYNC) =====================
def clone_website_sync(url):
    if not url.startswith("http"):
        url = "http://" + url

    domain = urlparse(url).netloc.replace("www.", "")
    BASE_DIR = f"/storage/emulated/0/{domain}"

    visited = set()
    files = set()
    queue = deque([url])

    # -------- CRAWL HTML --------
    while queue and len(visited) < MAX_PAGES:
        u = queue.popleft()
        if u in visited:
            continue
        visited.add(u)

        try:
            r = session.get(u, timeout=TIMEOUT)
            if "text/html" not in r.headers.get("Content-Type", ""):
                continue
            soup = BeautifulSoup(r.text, "html.parser")
        except:
            continue

        html_path = normalize_path(urlparse(u).path)
        save_html = os.path.join(BASE_DIR, html_path)
        safe_mkdir(os.path.dirname(save_html))

        with open(save_html, "w", encoding="utf-8", errors="ignore") as f:
            f.write(str(soup))

        MESSAGE_QUEUE.put(f"📄 {html_path}")

        for tag in soup.find_all(["a","link","script","img","source"]):
            src = tag.get("href") or tag.get("src")
            if not src:
                continue
            full = urljoin(u, src)
            p = urlparse(full)
            if p.netloc.replace("www.","") != domain:
                continue
            clean = p.scheme + "://" + p.netloc + p.path
            if clean not in visited:
                queue.append(clean)
            files.add(clean)

    # -------- DOWNLOAD FILES --------
    def download(u):
        try:
            r = session.get(u, timeout=TIMEOUT, stream=True)
            if r.status_code != 200:
                return
            fp = normalize_path(urlparse(u).path)
            save = os.path.join(BASE_DIR, fp)
            safe_mkdir(os.path.dirname(save))
            if os.path.exists(save):
                return
            with open(save, "wb") as f:
                for c in r.iter_content(8192):
                    if c:
                        f.write(c)

            MESSAGE_QUEUE.put(f"📥 {fp}")
        except:
            pass

    with ThreadPoolExecutor(MAX_WORKERS) as exe:
        exe.map(download, files)

    size = get_folder_size(BASE_DIR)
    fc, dc = count_files_folders(BASE_DIR)

    return (
        f"✅ Download Completed!\n\n"
        f"📁 Path: {BASE_DIR}\n"
        f"📄 Files: {fc}\n"
        f"📂 Folders: {dc}\n"
        f"📦 Size: {size/1024/1024:.2f} MB"
    )

# ===================== RUN =====================
print("🤖 Bot is running...")
print("🟢 Waiting for users...")

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.run_polling()