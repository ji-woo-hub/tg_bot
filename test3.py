./bootenv/bin/python - << 'EOF'
from telegram import Bot
import asyncio

TOKEN = "8470276015:AAFxZHzAF-4-Gcrg1YiTT853fYwvfZkj7fM"
USER_ID = 707790130   # replace with number

async def test():
    bot = Bot(TOKEN)
    await bot.send_message(
        chat_id=USER_ID,
        text="✅ Test message: bot can send messages!"
    )

asyncio.run(test())
EOF
