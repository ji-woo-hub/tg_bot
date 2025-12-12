import sqlite3
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

import asyncio  # <-- Needed for async scheduling

# --- Conversation States ---
DATE, TIME, LOCALE, ROLE, LANGUAGE = range(5)

# --- Role and Language options ---
ROLES = ["Sugo 1", "Sugo 2", "Reserba 1", "Reserba 2", "Sign Language"]
LANGUAGES = ["Tagalog", "English"]

DB_FILE = "suguan.db"


# --- Initialize database ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            day TEXT,
            time_24 TEXT,
            time_12 TEXT,
            locale TEXT,
            role TEXT,
            language TEXT,
            active INTEGER
        )
    ''')
    conn.commit()
    conn.close()


# --- /start command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Suguan Reminder Bot!\n\n"
        "You can use the following commands (case-insensitive):\n"
        "- enter : schedule a new Suguan\n"
        "- cancel : cancel an active Suguan\n"
        "- history : see last 10 schedules"
    )


# --- /enter workflow ---
async def enter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Enter the date of your Suguan (MM-DD-YYYY):"
    )
    return DATE


async def date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    try:
        date_obj = datetime.strptime(text, "%m-%d-%Y")
    except ValueError:
        await update.message.reply_text("❌ Invalid format. Use MM-DD-YYYY:")
        return DATE

    context.user_data["date"] = text
    context.user_data["day"] = date_obj.strftime("%A")
    await update.message.reply_text(
        "Enter the time of your Suguan (HH:MM in 24-hour format, e.g., 14:30):"
    )
    return TIME


async def time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    try:
        time_obj = datetime.strptime(text, "%H:%M")
    except ValueError:
        await update.message.reply_text("❌ Invalid time format. Use HH:MM (24-hour):")
        return TIME

    context.user_data["time_24"] = text
    context.user_data["time_12"] = time_obj.strftime("%I:%M %p")
    await update.message.reply_text("Enter the locale of your Suguan:")
    return LOCALE


async def locale_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["locale"] = update.message.text

    keyboard = [[InlineKeyboardButton(role, callback_data=f"ROLE_{role}")] for role in ROLES]
    await update.message.reply_text(
        "Select your role:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ROLE


async def role_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    role = query.data.split("_", 1)[1]
    context.user_data["role"] = role

    keyboard = [[InlineKeyboardButton(lang, callback_data=f"LANG_{lang}")] for lang in LANGUAGES]
    await query.edit_message_text(
        "Select the language:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return LANGUAGE


async def language_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    language = query.data.split("_", 1)[1]
    context.user_data["language"] = language

    # Save schedule to database
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO schedules (date, day, time_24, time_12, locale, role, language, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        context.user_data["date"],
        context.user_data["day"],
        context.user_data["time_24"],
        context.user_data["time_12"],
        context.user_data["locale"],
        context.user_data["role"],
        context.user_data["language"],
        1
    ))
    schedule_id = c.lastrowid
    conn.commit()
    conn.close()

    context.user_data["schedule_id"] = schedule_id  # Save for async reminder

    # --- FIX: schedule reminder asynchronously ---
    async def schedule_reminder():
        dt_str = f"{context.user_data['date']} {context.user_data['time_24']}"
        dt_obj = datetime.strptime(dt_str, "%m-%d-%Y %H:%M")
        remind_time = dt_obj - timedelta(hours=3)
        if remind_time > datetime.now():
            chat_id = query.message.chat_id
            context.application.job_queue.run_once(
                reminder, remind_time, chat_id=chat_id, data=schedule_id
            )

    asyncio.create_task(schedule_reminder())
    # --- END FIX ---

    summary = (
        f"📌 **Suguan Scheduled**\n"
        f"Date: {context.user_data['date']} ({context.user_data['day']})\n"
        f"Time: {context.user_data['time_12']}\n"
        f"Locale: {context.user_data['locale']}\n"
        f"Role: {context.user_data['role']}\n"
        f"Language: {context.user_data['language']}\n\n"
        f"⏰ Reminder will be sent 3 hours before the Suguan"
    )
    await query.edit_message_text(summary, parse_mode="Markdown")
    return ConversationHandler.END


# --- Reminder job ---
async def reminder(context: ContextTypes.DEFAULT_TYPE):
    schedule_id = context.job.data
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT date, day, time_12, locale, role, language, active FROM schedules WHERE id=?', (schedule_id,))
    row = c.fetchone()
    conn.close()

    if row and row[6]:  # active
        date, day, time_12, locale, role, language, active = row
        message = (
            f"⏰ Reminder: Your upcoming Suguan is in 3 hours!\n\n"
            f"📅 Date: {date} ({day})\n"
            f"🕒 Time: {time_12}\n"
            f"📍 Locale: {locale}\n"
            f"🎭 Role: {role}\n"
            f"🗣 Language: {language}"
        )
        await context.bot.send_message(context.job.chat_id, message)


# --- /cancel workflow ---
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, date, time_12, role FROM schedules WHERE active=1 ORDER BY id')
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("You have no active Suguans to cancel.")
        return

    keyboard = [[InlineKeyboardButton(f"{row[1]} | {row[2]} | {row[3]}", callback_data=f"CANCEL_{row[0]}")] for row in rows]
    await update.message.reply_text(
        "Select a Suguan to cancel:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cancel_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    schedule_id = int(query.data.split("_")[1])

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE schedules SET active=0 WHERE id=?', (schedule_id,))
    conn.commit()
    conn.close()

    await query.edit_message_text("❌ The Suguan has been cancelled.")


# --- /history workflow ---
async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT date, day, time_12, locale, role, language, active FROM schedules ORDER BY id DESC LIMIT 10')
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No history found.")
        return

    messages = []
    for row in rows:
        date, day, time_12, locale, role, language, active = row
        status = "Active" if active else "Done/Cancelled"
        messages.append(
            f"📌 {status}\nDate: {date} ({day})\nTime: {time_12}\nLocale: {locale}\nRole: {role}\nLanguage: {language}\n"
        )

    await update.message.reply_text("\n\n".join(messages))


# --- Main function ---
def main():
    init_db()
    app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("(?i)^enter$"), enter_command)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_input)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, time_input)],
            LOCALE: [MessageHandler(filters.TEXT & ~filters.COMMAND, locale_input)],
            ROLE: [CallbackQueryHandler(role_input, pattern="ROLE_")],
            LANGUAGE: [CallbackQueryHandler(language_input, pattern="LANG_")],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex("(?i)^cancel$"), cancel_command))
    app.add_handler(MessageHandler(filters.Regex("(?i)^history$"), history_command))
    app.add_handler(CallbackQueryHandler(cancel_selection, pattern="CANCEL_"))

    app.run_polling()


if __name__ == "__main__":
    main()
