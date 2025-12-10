from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ForceReply
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, ContextTypes, filters
from datetime import datetime

DATE, TIME, LOCALE = range(3)

# --- Step 1: /start command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Enter Suguan", callback_data="enter_suguan")]]
    await update.message.reply_text(
        "Welcome! Choose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Step 2: CallbackQuery triggers conversation ---
async def enter_suguan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    # Manually start the ConversationHandler by sending the first question
    await update.callback_query.edit_message_text(
        "Enter the date of your Suguan (YYYY-MM-DD):",
        reply_markup=ForceReply(selective=True)
    )
    return DATE

# --- Step 3: Conversation states ---
async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['date'] = update.message.text
    await update.message.reply_text(
        "Enter the time of your Suguan (HH:MM, 24-hour):",
        reply_markup=ForceReply(selective=True)
    )
    return TIME

async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['time'] = update.message.text
    await update.message.reply_text(
        "Enter the locale of your Suguan:",
        reply_markup=ForceReply(selective=True)
    )
    return LOCALE

async def get_locale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['locale'] = update.message.text
    await update.message.reply_text("All done! ✅")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()

    # ConversationHandler: only MessageHandlers
    conv_handler = ConversationHandler(
        entry_points=[],  # no entry here
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            LOCALE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_locale)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(enter_suguan_callback, pattern="enter_suguan"))
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()
