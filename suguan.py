import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import asyncio

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
DATE, TIME, LOCALE, ROLE, LANGUAGE = range(5)

# Database setup
DB_FILE = "suguan.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    date TEXT,
                    day TEXT,
                    time TEXT,
                    locale TEXT,
                    role TEXT,
                    language TEXT,
                    status TEXT
                )''')
    conn.commit()
    conn.close()

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message explaining commands."""
    text = (
        "👋 Welcome to Suguan Scheduler Bot!\n\n"
        "Available commands (case-insensitive):\n"
        "/enter - Create a new schedule\n"
        "/cancel - Cancel an active schedule\n"
        "/history - Show last 10 schedules"
    )
    await update.message.reply_text(text)

# --- ENTER WORKFLOW ---
async def enter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the enter schedule workflow by asking for date."""
    await update.message.reply_text(
        "📅 Please enter the date of your schedule (MM-DD-YYYY):"
    )
    return DATE

async def enter_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle date input and ask for time."""
    date_text = update.message.text
    try:
        date_obj = datetime.strptime(date_text, "%m-%d-%Y")
        context.user_data['date'] = date_text
        context.user_data['day'] = date_obj.strftime("%A")  # Day of the week
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid date format. Please enter in MM-DD-YYYY format:"
        )
        return DATE

    await update.message.reply_text("🕒 Please enter the time (24-hour HH:MM):")
    return TIME

async def enter_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle time input and ask for locale."""
    time_text = update.message.text
    try:
        time_obj = datetime.strptime(time_text, "%H:%M")
        context.user_data['time'] = time_obj.strftime("%I:%M %p")  # 12-hour format
        context.user_data['time_24'] = time_text
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid time format. Please enter in 24-hour HH:MM format:"
        )
        return TIME

    await update.message.reply_text("📍 Please enter the locale of your schedule:")
    return LOCALE

async def enter_locale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle locale input and ask for role."""
    context.user_data['locale'] = update.message.text

    roles = [["Sugo 1", "Sugo 2"], ["Reserba 1", "Reserba 2"], ["Sign Language"]]
    await update.message.reply_text(
        "🎭 Please select your role:",
        reply_markup=ReplyKeyboardMarkup(roles, one_time_keyboard=True, resize_keyboard=True),
    )
    return ROLE

async def enter_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle role input and ask for language."""
    role = update.message.text
    if role not in ["Sugo 1", "Sugo 2", "Reserba 1", "Reserba 2", "Sign Language"]:
        await update.message.reply_text("❌ Invalid role. Please choose from buttons.")
        return ROLE
    context.user_data['role'] = role

    languages = [["Tagalog", "English"]]
    await update.message.reply_text(
        "🗣 Please select the language:",
        reply_markup=ReplyKeyboardMarkup(languages, one_time_keyboard=True, resize_keyboard=True),
    )
    return LANGUAGE

async def enter_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language input, save schedule, and set reminder."""
    language = update.message.text
    if language not in ["Tagalog", "English"]:
        await update.message.reply_text("❌ Invalid language. Please choose from buttons.")
        return LANGUAGE
    context.user_data['language'] = language

    # Save schedule to database
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO schedules (user_id, date, day, time, locale, role, language, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            update.message.from_user.id,
            context.user_data['date'],
            context.user_data['day'],
            context.user_data['time'],
            context.user_data['locale'],
            context.user_data['role'],
            context.user_data['language'],
            "active",
        ),
    )
    schedule_id = c.lastrowid
    conn.commit()
    conn.close()

    # Schedule reminder
    schedule_datetime = datetime.strptime(
        f"{context.user_data['date']} {context.user_data['time_24']}", "%m-%d-%Y %H:%M"
    )
    reminder_time = schedule_datetime - timedelta(hours=3)
    if reminder_time > datetime.now():
        context.application.create_task(send_reminder(update.message.from_user.id, schedule_id, reminder_time))

    summary = (
        f"✅ Schedule created!\n\n"
        f"📅 Date: {context.user_data['date']} ({context.user_data['day']})\n"
        f"🕒 Time: {context.user_data['time']}\n"
        f"📍 Locale: {context.user_data['locale']}\n"
        f"🎭 Role: {context.user_data['role']}\n"
        f"🗣 Language: {context.user_data['language']}"
    )

    await update.message.reply_text(summary, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- CANCEL WORKFLOW ---
async def cancel_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show active schedules as buttons to cancel."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT id, date, time, role FROM schedules WHERE user_id=? AND status='active'",
        (update.message.from_user.id,),
    )
    schedules = c.fetchall()
    conn.close()

    if not schedules:
        await update.message.reply_text("❌ No active schedules found.")
        return

    buttons = [[f"{s[0]}: {s[1]} {s[2]} ({s[3]})"] for s in schedules]
    await update.message.reply_text(
        "Select a schedule to cancel:",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True),
    )

    return "SELECT_CANCEL"

async def select_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle schedule cancellation."""
    text = update.message.text
    try:
        schedule_id = int(text.split(":")[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid selection. Please choose a button.")
        return "SELECT_CANCEL"

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE schedules SET status='canceled' WHERE id=?", (schedule_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Schedule canceled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- HISTORY ---
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show last 10 schedules."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT date, day, time, locale, role, language, status FROM schedules WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (update.message.from_user.id,),
    )
    schedules = c.fetchall()
    conn.close()

    if not schedules:
        await update.message.reply_text("❌ No schedules found.")
        return

    message = "📜 Last 10 schedules:\n\n"
    for s in schedules:
        message += (
            f"📅 {s[0]} ({s[1]})\n"
            f"🕒 {s[2]}\n"
            f"📍 {s[3]}\n"
            f"🎭 {s[4]}\n"
            f"🗣 {s[5]}\n"
            f"Status: {s[6]}\n\n"
        )

    await update.message.reply_text(message)

# --- REMINDER TASK ---
async def send_reminder(user_id, schedule_id, reminder_time):
    """Wait until reminder_time and send reminder."""
    now = datetime.now()
    wait_seconds = (reminder_time - now).total_seconds()
    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT date, day, time, locale, role, language, status FROM schedules WHERE id=?",
        (schedule_id,),
    )
    schedule = c.fetchone()
    conn.close()

    if not schedule or schedule[6] != "active":
        return  # canceled or deleted

    text = (
        f"⏰ Reminder: Your upcoming Suguan is in 3 hours!\n\n"
        f"📅 Date: {schedule[0]} ({schedule[1]})\n"
        f"🕒 Time: {schedule[2]}\n"
        f"📍 Locale: {schedule[3]}\n"
        f"🎭 Role: {schedule[4]}\n"
        f"🗣 Language: {schedule[5]}"
    )

    try:
        app = ApplicationBuilder().token("YOUR_BOT_TOKEN_HERE").build()
        await app.bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        logger.error(f"Failed to send reminder: {e}")

# --- MAIN FUNCTION ---
if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token("YOUR_BOT_TOKEN_HERE").build()

    # Conversation handler for /enter
    enter_conv = ConversationHandler(
        entry_points=[CommandHandler("enter", enter, filters=~filters.COMMAND | filters.Regex("(?i)^enter$"))],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_time)],
            LOCALE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_locale)],
            ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_role)],
            LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_language)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )

    # Conversation handler for /cancel
    cancel_conv = ConversationHandler(
        entry_points=[CommandHandler("cancel", cancel_schedule, filters=~filters.COMMAND | filters.Regex("(?i)^cancel$"))],
        states={
            "SELECT_CANCEL": [MessageHandler(filters.TEXT & ~filters.COMMAND, select_cancel)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(enter_conv)
    app.add_handler(cancel_conv)
    app.add_handler(CommandHandler("history", history, filters=~filters.COMMAND | filters.Regex("(?i)^history$")))

    print("Bot is running...")
    app.run_polling()
