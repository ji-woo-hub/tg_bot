import sqlite3
from datetime import datetime, timedelta
import logging
import asyncio

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- SQLite Setup ---
conn = sqlite3.connect("suguan.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute(
    """
CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    day TEXT NOT NULL,
    time_24 TEXT NOT NULL,
    time_12 TEXT NOT NULL,
    locale TEXT NOT NULL,
    role TEXT NOT NULL,
    language TEXT NOT NULL,
    status TEXT NOT NULL
)
"""
)
conn.commit()

# --- Conversation states ---
DATE, TIME, LOCALE, ROLE, LANGUAGE = range(5)

# --- Roles & Languages ---
ROLE_OPTIONS = ["Sugo 1", "Sugo 2", "Reserba 1", "Reserba 2", "Sign Language"]
LANGUAGE_OPTIONS = ["Tagalog", "English"]

# --- Track reminder jobs ---
reminder_jobs = {}  # schedule_id -> Job


# --- Helper Functions ---
def convert_to_12hr(time_str):
    """Convert 24-hour time HH:MM to 12-hour AM/PM format."""
    t = datetime.strptime(time_str, "%H:%M")
    return t.strftime("%I:%M %p")


def schedule_reminder(application, schedule_id, user_id, reminder_time):
    """Schedules a reminder 3 hours before the actual schedule and keeps track of the Job."""
    async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
        cursor.execute(
            "SELECT date, day, time_12, locale, role, language, status FROM schedules WHERE id=?",
            (schedule_id,)
        )
        row = cursor.fetchone()
        if row and row[6] == "active":  # Only send if still active
            date, day, time_12, locale, role, language, _ = row
            msg = (
                f"⏰ Reminder: Your upcoming Suguan is in 3 hours!\n\n"
                f"📅 Date: {date} ({day})\n"
                f"🕒 Time: {time_12}\n"
                f"📍 Locale: {locale}\n"
                f"🎭 Role: {role}\n"
                f"🗣 Language: {language}"
            )
            await application.bot.send_message(chat_id=user_id, text=msg)
        reminder_jobs.pop(schedule_id, None)

    delay = (reminder_time - datetime.now()).total_seconds()
    if delay > 0:
        job = application.job_queue.run_once(lambda ctx: asyncio.create_task(send_reminder(ctx)), when=delay)
        reminder_jobs[schedule_id] = job


# --- /start handler ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "Welcome to Suguan Scheduler Bot!\n\n"
        "Available commands:\n"
        "- enter → start a new schedule\n"
        "- cancel → cancel an active schedule\n"
        "- history → view last 10 schedules\n\n"
        "All commands are case-insensitive and do NOT require a / except /start."
    )
    await update.message.reply_text(welcome_text)


# --- Enter workflow handlers ---
async def enter_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter the date of your schedule (MM-DD-YYYY):")
    return DATE


async def enter_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    try:
        date_obj = datetime.strptime(user_input, "%m-%d-%Y")
        day_of_week = date_obj.strftime("%A")
        context.user_data["date"] = user_input
        context.user_data["day"] = day_of_week
        await update.message.reply_text("Enter the time of your schedule in 24-hour format (HH:MM):")
        return TIME
    except ValueError:
        await update.message.reply_text("Invalid date format. Please enter as MM-DD-YYYY.")
        return DATE


async def enter_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    try:
        time_obj = datetime.strptime(user_input, "%H:%M")
        context.user_data["time_24"] = user_input
        context.user_data["time_12"] = convert_to_12hr(user_input)
        await update.message.reply_text("Enter the locale of your schedule:")
        return LOCALE
    except ValueError:
        await update.message.reply_text("Invalid time format. Please enter as HH:MM (24-hour).")
        return TIME


async def enter_locale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["locale"] = update.message.text
    keyboard = [[InlineKeyboardButton(role, callback_data=role)] for role in ROLE_OPTIONS]
    await update.message.reply_text("Select your role:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ROLE


async def enter_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["role"] = query.data

    keyboard = [[InlineKeyboardButton(lang, callback_data=lang)] for lang in LANGUAGE_OPTIONS]
    await query.edit_message_text("Select language:", reply_markup=InlineKeyboardMarkup(keyboard))
    return LANGUAGE


async def enter_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["language"] = query.data

    # Save to database
    user_id = update.effective_user.id
    data = context.user_data
    cursor.execute(
        """
        INSERT INTO schedules (user_id, date, day, time_24, time_12, locale, role, language, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, data["date"], data["day"], data["time_24"], data["time_12"],
         data["locale"], data["role"], data["language"], "active")
    )
    conn.commit()
    schedule_id = cursor.lastrowid

    # Schedule reminder 3 hours before
    schedule_datetime = datetime.strptime(f"{data['date']} {data['time_24']}", "%m-%d-%Y %H:%M")
    reminder_time = schedule_datetime - timedelta(hours=3)
    schedule_reminder(context.application, schedule_id, user_id, reminder_time)

    await query.edit_message_text(
        f"✅ Schedule created!\n\n"
        f"📅 Date: {data['date']} ({data['day']})\n"
        f"🕒 Time: {data['time_12']}\n"
        f"📍 Locale: {data['locale']}\n"
        f"🎭 Role: {data['role']}\n"
        f"🗣 Language: {data['language']}"
    )
    return ConversationHandler.END


async def enter_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Schedule creation canceled.")
    return ConversationHandler.END


# --- Cancel workflow ---
async def cancel_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute(
        "SELECT id, date, day, time_12, locale, role FROM schedules WHERE user_id=? AND status='active'",
        (user_id,)
    )
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("You have no active schedules.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{row[1]} {row[2]} {row[3]} - {row[4]} ({row[5]})", callback_data=str(row[0]))]
        for row in rows
    ]
    await update.message.reply_text("Select a schedule to cancel:", reply_markup=InlineKeyboardMarkup(keyboard))


async def cancel_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    schedule_id = int(query.data)

    # Update database
    cursor.execute("UPDATE schedules SET status='canceled' WHERE id=?", (schedule_id,))
    conn.commit()

    # Remove scheduled reminder if it exists
    job = reminder_jobs.pop(schedule_id, None)
    if job:
        job.schedule_removal()  # Remove from job queue

    await query.edit_message_text("✅ Schedule canceled, reminder removed.")


# --- History workflow ---
async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute(
        "SELECT date, day, time_12, locale, role, language, status FROM schedules WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (user_id,)
    )
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("No schedules found.")
        return

    messages = []
    for r in rows:
        messages.append(
            f"📅 {r[0]} ({r[1]})\n"
            f"🕒 {r[2]}\n"
            f"📍 {r[3]}\n"
            f"🎭 {r[4]}\n"
            f"🗣 {r[5]}\n"
            f"Status: {r[6]}\n"
            "----------------"
        )
    await update.message.reply_text("\n".join(messages))


# --- Main ---
def main():
    # Replace 'YOUR_BOT_TOKEN' with your actual token
    application = ApplicationBuilder().token("8470276015:AAFxZHzAF-4-Gcrg1YiTT853fYwvfZkj7fM").build()

    # ConversationHandler for enter workflow
    enter_handler = ConversationHandler(
        entry_points=[CommandHandler("enter", enter_start, filters=None),
                      MessageHandler(filters.Regex("(?i)^enter$"), enter_start)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_time)],
            LOCALE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_locale)],
            ROLE: [CallbackQueryHandler(enter_role)],
            LANGUAGE: [CallbackQueryHandler(enter_language)],
        },
        fallbacks=[CommandHandler("cancel", enter_cancel)],
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(enter_handler)
    application.add_handler(MessageHandler(filters.Regex("(?i)^cancel$"), cancel_schedule))
    application.add_handler(CallbackQueryHandler(cancel_selected, pattern=r"^\d+$"))
    application.add_handler(MessageHandler(filters.Regex("(?i)^history$"), show_history))

    # Run the bot
    application.run_polling()


if __name__ == "__main__":
    main()
