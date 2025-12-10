from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    filters,
)
from datetime import datetime, timedelta

# Options
ROLES = ["Sugo 1", "Sugo 2", "Reserba 1", "Reserba 2", "Sign Language"]
LANGUAGES = ["Tagalog", "English"]
ITEMS_PER_PAGE = 5

# States
DATE, TIME, LOCALE = range(3)

# --- Start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Enter Suguan", callback_data="activity")]]
    await update.message.reply_text(
        "Welcome! Choose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Enter Suguan ---
async def start_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await ask_date(update, context)

# --- Ask Date ---
async def ask_date(update, context):
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Enter the date of your Suguan (YYYY-MM-DD):",
            reply_markup=ForceReply(selective=True)
        )
    else:
        await update.message.reply_text(
            "Enter the date of your Suguan (YYYY-MM-DD):",
            reply_markup=ForceReply(selective=True)
        )
    return DATE

# --- Get Date ---
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

# --- Get Time ---
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

# --- Get Locale ---
async def get_locale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["locale"] = update.message.text
    await ask_buttons(update, context, "Select role:", ROLES, "ROLE")

# --- Ask Buttons Helper ---
async def ask_buttons(update, context, question, options, state):
    keyboard = [[InlineKeyboardButton(opt, callback_data=f"{state}_{opt}")] for opt in options]
    if update.callback_query:
        await update.callback_query.edit_message_text(
            question,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            question,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# --- Handle Role/Language Selection ---
async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("ROLE_"):
        context.user_data["role"] = data.split("_")[1]
        await ask_buttons(update, context, "Select language:", LANGUAGES, "LANGUAGE")
    elif data.startswith("LANGUAGE_"):
        context.user_data["language"] = data.split("_")[1]
        await finalize_suguan(update, context)

# --- Finalize Suguan ---
async def finalize_suguan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dt_str = context.user_data["date"] + " " + context.user_data["time"]
    activity_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    remind_dt = activity_dt - timedelta(hours=3)

    if "activities" not in context.user_data:
        context.user_data["activities"] = []

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
        f"⏰ I will remind you 3 hours before."
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

# --- Reminder ---
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
async def cancel_or_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    activities = context.user_data.get("activities", [])

    if data.startswith("cancel_"):
        idx = int(data.split("_")[1])
        if idx < len(activities):
            job = activities[idx]["job"]
            if job:
                job.schedule_removal()
            activities.pop(idx)
            await query.edit_message_text("❌ Suguan cancelled.")
    elif data.startswith("edit_"):
        idx = int(data.split("_")[1])
        if idx < len(activities):
            job = activities[idx]["job"]
            if job:
                job.schedule_removal()
            activities.pop(idx)
            await query.edit_message_text("Let's edit your Suguan. Enter the date (YYYY-MM-DD):")
            return await ask_date(update, context)
    elif data == "cancel":
        if activities:
            job = activities[-1]["job"]
            if job:
                job.schedule_removal()
            activities.pop(-1)
        await query.edit_message_text("❌ Your Suguan has been cancelled.")
    elif data == "change":
        if activities:
            job = activities[-1]["job"]
            if job:
                job.schedule_removal()
            activities.pop(-1)
        await query.edit_message_text("Let's change your Suguan. Enter the date (YYYY-MM-DD):")
        return await ask_date(update, context)

# --- List Suguans ---
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

# --- Pagination handler ---
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

    # ConversationHandler for Suguan entry
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_activity, pattern="activity", per_message=True)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            LOCALE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_locale)],
        },
        fallbacks=[]
    )

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)  # conversation first
    app.add_handler(CallbackQueryHandler(handle_selection, pattern=r"ROLE_|LANGUAGE_", per_message=True))
    app.add_handler(CallbackQueryHandler(cancel_or_change, pattern=r"cancel|change|cancel_\d+|edit_\d+", per_message=True))
    app.add_handler(CallbackQueryHandler(paginate, pattern=r"page_\d+", per_message=True))
    app.add_handler(CommandHandler("my_suguans", list_suguans))

    # Start bot
    app.run_polling()

if __name__ == "__main__":
    main()
