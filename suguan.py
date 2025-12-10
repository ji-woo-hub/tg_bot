from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Enter Suguan", callback_data="activity")]]
    await update.message.reply_text(
        "Welcome! Choose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def enter_suguan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("You clicked Enter Suguan!")
    
def main():
    app = ApplicationBuilder().token("8470276015:AAFxZHzAF-4-Gcrg1YiTT853fYwvfZkj7fM").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(enter_suguan, pattern="activity", per_message=True))
    app.run_polling()

if __name__ == "__main__":
    main()
