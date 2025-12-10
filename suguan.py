# basic
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Step 1: /start command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Enter Suguan", callback_data="enter_suguan")]]
    await update.message.reply_text(
        "Welcome! Choose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Step 2: Handle button click ---
async def enter_suguan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("You clicked Enter Suguan!")

# --- Step 3: Main ---
def main():
    app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(enter_suguan, pattern="enter_suguan"))

    app.run_polling()

if __name__ == "__main__":
    main()
