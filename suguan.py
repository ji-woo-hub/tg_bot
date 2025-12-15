import sqlite3
from datetime import datetime, timedelta
from typing import Dict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# =========================
# CONFIG
# =========================
TOKEN = "8470276015:AAFxZHzAF-4-Gcrg1YiTT853fYwvfZkj7fM"
DB_FILE = "suguan.db"
REMINDER_HOURS = 3

# =========================
# STATES
# =========================
DATE, TIME, LOCALE, ROLE, LANGUAGE = range(5)

# =========================
# JOB TRACKER
# =========================
reminder_jobs: Dict[int, object] = {}

# =========================
# DATABASE
# =========================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT,
            day TEXT,
            time_24 TEXT,
            time_12 TEXT,
            locale TEXT,
            role TEXT,
            language TEXT,
            status TEXT
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_status
        ON schedules(user_id, status)
    """)
    conn.commit()
    conn.close()

# =========================
# UTILS
# =========================
def parse_datetime(date_str, time_str):
    return datetime.strptime(f"{date_str} {time_str}", "%m-%d-%Y %H:%M")

def format_12h(time_24):
    return datetime.strptime(time_24, "%H:%M").strftime("%I:%M %p").lstrip("0")

# =========================
# COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to the Suguan Scheduler Bot!\n\n"
        "Commands:\n"
        "• enter – create a new schedule\n"
        "• cancel – cancel an active schedule\n"
        "• history – show last 10 schedules"
    )

# =========================
# ENTER WORKFLOW
# =========================
async def enter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📅 Enter date (MM-DD-YYYY):")
    return DATE

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        d = datetime.strptime(update.message.text, "%m-%d-%Y")
        context.user_data["date"] = update.message.text
        context.user_data["day"] = d.strftime("%A")
        await update.message.reply_text("🕒 Enter time (24h HH:MM):")
        return TIME
    except ValueError:
        await update.message.reply_text("❌ Invalid date. Try again:")
        return DATE

async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        datetime.strptime(update.message.text, "%H:%M")
        context.user_data["time_24"] = update.message.text
        context.user_data["time_12"] = format_12h(update.message.text)
        await update.message.reply_text("📍 Enter locale:")
        return LOCALE
    except ValueError:
        await update.message.reply_text("❌ Invalid time. Try again:")
        return TIME

async def get_locale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["locale"] = update.message.text
    keyboard = [
        [InlineKeyboardButton("Sugo 1", callback_data="Sugo 1")],
        [InlineKeyboardButton("Sugo 2", callback_data="Sugo 2")],
        [InlineKeyboardButton("Reserba 1", callback_data="Reserba 1")],
        [InlineKeyboardButton("Reserba 2", callback_data="Reserba 2")],
        [InlineKeyboardButton("Sign Language", callback_data="Sign Language")],
    ]
    await update.message.reply_text(
        "🎭 Select role:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ROLE

async def get_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["role"] = query.data

    keyboard = [
        [InlineKeyboardButton("Tagalog", callback_data="Tagalog")],
        [InlineKeyboardButton("English", callback_data="English")],
    ]
    await query.edit_message_text(
        "🗣 Select language:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return LANGUAGE

async def get_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["language"] = query.data

    user_id = query.from_user.id

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO schedules
        (user_id, date, day, time_24, time_12, locale, role, language, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
    """, (
        user_id,
        context.user_data["date"],
        context.user_data["day"],
        context.user_data["time_24"],
        context.user_data["time_12"],
        context.user_data["locale"],
        context.user_data["role"],
        context.user_data["language"],
    ))
    schedule_id = cur.lastrowid
    conn.commit()
    conn.close()

    await query.edit_message_text("✅ Schedule saved!")

    schedule_reminder(
        context.application,
        schedule_id,
        user_id,
        context.user_data
    )

    return ConversationHandler.END

# =========================
# REMINDER
# =========================
def schedule_reminder(app, schedule_id, user_id, data):
    schedule_dt = parse_datetime(data["date"], data["time_24"])
    reminder_dt = schedule_dt - timedelta(hours=REMINDER_HOURS)

    if reminder_dt <= datetime.now():
        return

    delay = (reminder_dt - datetime.now()).total_seconds()

    job = app.job_queue.run_once(
        send_reminder,
        when=delay,
        data={"schedule_id": schedule_id, "user_id": user_id}
    )

    reminder_jobs[schedule_id] = job

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    schedule_id = job.data["schedule_id"]
    user_id = job.data["user_id"]

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        SELECT date, day, time_12, locale, role, language
        FROM schedules WHERE id=?
    """, (schedule_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return

    msg = (
        "⏰ Reminder: Your upcoming Suguan is in 3 hours!\n\n"
        f"📅 Date: {row[0]} ({row[1]})\n"
        f"🕒 Time: {row[2]}\n"
        f"📍 Locale: {row[3]}\n"
        f"🎭 Role: {row[4]}\n"
        f"🗣 Language: {row[5]}"
    )

    await context.bot.send_message(chat_id=user_id, text=msg)

    cur.execute("UPDATE schedules SET status='finished' WHERE id=?", (schedule_id,))
    conn.commit()
    conn.close()

    reminder_jobs.pop(schedule_id, None)

# =========================
# CANCEL
# =========================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date, time_12 FROM schedules
        WHERE user_id=? AND status='active'
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No active schedules.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{r[1]} {r[2]}", callback_data=str(r[0]))]
        for r in rows
    ]
    await update.message.reply_text(
        "Select schedule to cancel:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def confirm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    schedule_id = int(query.data)

    job = reminder_jobs.pop(schedule_id, None)
    if job:
        job.schedule_removal()

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("UPDATE schedules SET status='cancelled' WHERE id=?", (schedule_id,))
    conn.commit()
    conn.close()

    await query.edit_message_text("❌ Schedule cancelled.")

# =========================
# HISTORY
# =========================
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        SELECT date, day, time_12, locale, role, language, status
        FROM schedules
        WHERE user_id=?
        ORDER BY id DESC LIMIT 10
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No history.")
        return

    msg = "📜 Last 10 schedules:\n\n"
    for r in rows:
        msg += (
            f"{r[0]} ({r[1]}) | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]}\n"
        )

    await update.message.reply_text(msg)

# =========================
# STARTUP RELOAD
# =========================
async def reload_reminders(app):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, user_id, date, time_24
        FROM schedules WHERE status='active'
    """)
    rows = cur.fetchall()
    conn.close()

    for sid, uid, date, time_24 in rows:
        dt = parse_datetime(date, time_24)
        reminder = dt - timedelta(hours=REMINDER_HOURS)
        if reminder > datetime.now():
            delay = (reminder - datetime.now()).total_seconds()
            job = app.job_queue.run_once(
                send_reminder,
                when=delay,
                data={"schedule_id": sid, "user_id": uid}
            )
            reminder_jobs[sid] = job

# =========================
# MAIN
# =========================
def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("enter", enter)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            LOCALE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_locale)],
            ROLE: [CallbackQueryHandler(get_role)],
            LANGUAGE: [CallbackQueryHandler(get_language)],
        },
        fallbacks=[],
        per_message=True   # ✅ FIX
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(confirm_cancel))
    app.add_handler(CommandHandler("history", history))

    app.post_init = reload_reminders  # ✅ FIX

    app.run_polling()

if __name__ == "__main__":
    main()
