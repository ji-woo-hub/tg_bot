from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ForceReply
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from datetime import datetime, timedelta

# States for ConversationHandler
DATE, TIME, LOCALE = range(3)

# Options
ROLES = ["Sugo 1", "Sugo 2", "Reserba 1", "Reserba 2", "Sign Language"]
LANGUAGES = ["Tagalog", "English"]
ITEMS_PER_PAGE = 5

# --- Start Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Enter Suguan", callback_data="activity")]]
    await update.message.reply_text(
        "Welcome! Choose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Enter Suguan button handler ---
async def start_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    # Ask for date
    await update.callback_query.edit_message_text(
        "Enter the date of your Suguan (YYYY-MM-DD):",
        reply_markup=ForceReply(selective=True)
    )
    return DATE

# --- Date Input ---
async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_text = update.message.text
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("❌ Invalid date format. Use YYYY-MM-DD:")
        return DATE
    context.user_data["date"] = date_text
    await update.message.reply_text(
        "Enter the time of your Suguan (HH:MM, 24-hour):",
        reply_markup=ForceReply(selective=True)
    )
    return TIME

# --- Time Input ---
async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_text = update.message.text
    try:
        datetime.strptime(time_text, "%H:%M")
    except ValueError:
        await update.message.reply_text("❌ Invalid time format. Use HH:MM (24-hour):")
        return TIME
    context.user_data["time"] = time_text
    await update.message.reply_text(
        "Enter the locale:",
        reply_markup=ForceReply(selective=True)
    )
    return LOCALE

# --- Locale Input ---
async def get_locale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["locale"] = update.message.text
    # Ask Role
    keyboard = [[InlineKeyboardButton(role, callback_data=f"ROLE_{role}")] for role in ROLES]
    await update.message.reply_text(
        "Select your role:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Role / Language Selection ---
async def handle_role_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("ROLE_"):
        context.user_data["role"] = data.split("_")[1]
        # Ask Language
        keyboard = [[InlineKeyboardButton(lang, callback_data=f"LANG_{lang}")] for lang in LANGUAGES]
        await query.edit_message_text(
            "Select language:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data.startswith("LANG_"):
        context.user_data["language"] = data.split("_")[1]
        await finalize_suguan(update, context)

# --- Finalize Suguan ---
async def finalize_suguan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dt_str = context.user_data["date"] + " " + context.user_data["time"]
    activity_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    remind_dt = activity_dt - timedelta(hours=3)

    if "activities" not in context.user_data:
        context.user_data["activities"] = []

    # Schedule reminder
    job = context.job_queue.run_once(
        reminder,
        when=remind_dt,
        chat_id=update.effective_chat.id,
        data=context.user_data
    )

    activity = {
        "date": context.user_data["date"],
        "time": context.user_data["time"],
        "locale": context.user_data["locale"],
        "role": context.user_data["role"],
        "language": context.user_data["language"],
        "job": job
    }
    context.user_data["activities"].append(activity)

    summary = (
        f"📌 **Suguan Scheduled**\n"
        f"Date: {activity['date']}\n"
        f"Time: {activity['time']}\n"
        f"Locale: {activity['locale']}\n"
        f"Role: {activity['role']}\n"
        f"Language: {activity['language']}\n\n"
        f"⏰ Reminder 3 hours before"
    )

    keyboard = [
        [InlineKeyboardButton("Cancel Suguan", callback_data="cancel")],
        [InlineKeyboardButton("Change Suguan", callback_data="change")]
    ]

    await update.callback_query.edit_message_text(
        summary,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Reminder Job ---
async def reminder(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    await context.bot.send_message(
        context.job.chat_id,
        f"⏰ **Reminder!**\nYour Suguan is in 3 hours.\n\n"
        f"📅 {data['date']} {data['time']}\n"
        f"📍 Locale: {data['locale']}\n"
        f"👤 Role: {data['role']}\n"
        f"📝 Language: {data['language']}",
        parse_mode="Markdown"
    )

# --- Cancel / Change ---
async def cancel_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    activities = context.user_data.get("activities", [])

    if data == "cancel" and activities:
        job = activities[-1]["job"]
        if job:
            job.schedule_removal()
        activities.pop(-1)
        await query.edit_message_text("❌ Your Suguan has been cancelled.")
    elif data == "change" and activities:
        job = activities[-1]["job"]
        if job:
            job.schedule_removal()
        activities.pop(-1)
        await query.edit_message_text("Let's change your Suguan. Enter the date (YYYY-MM-DD):")
        return DATE

# --- List Suguans with Pagination ---
async def list_suguans(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    activities = context.user_data.get("activities", [])
    if not activities:
        await update.message.reply_text("You have no scheduled Suguans.")
        return

    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    text = ""
    for i, act in enumerate(activities[start:end], start=start):
        text += (
            f"#{i+1} 📌 Suguan\n"
            f"Date: {act['date']}\n"
            f"Time: {act['time']}\n"
            f"Locale: {act['locale']}\n"
            f"Role: {act['role']}\n"
            f"Language: {act['language']}\n\n"
        )

    keyboard = []
    for i, act in enumerate(activities[start:end], start=start):
        keyboard.append([
            InlineKeyboardButton("Cancel", callback_data=f"cancel_{i}"),
            InlineKeyboardButton("Edit", callback_data=f"edit_{i}")
        ])

    pagination_buttons = []
    if start > 0:
        pagination_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page_{page-1}"))
    if end < len(activities):
        pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
    if pagination_buttons:
        keyboard.append(pagination_buttons)

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def paginate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("page_"):
        page = int(query.data.split("_")[1])
        await query.message.delete()
        await list_suguans(update, context, page=page)

# --- Main ---
def main():
    app = ApplicationBuilder().token("8470276015:AAFxZHzAF-4-Gcrg1YiTT853fYwvfZkj7fM").build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_activity, pattern="activity")],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            LOCALE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_locale)]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_role_language, pattern=r"ROLE_|LANG_"))
    app.add_handler(CallbackQueryHandler(cancel_change, pattern=r"cancel|change"))
    app.add_handler(CallbackQueryHandler(paginate, pattern=r"page_\d+"))
    app.add_handler(CommandHandler("my_suguans", list_suguans))

    app.run_polling()

if __name__ == "__main__":
    main()
