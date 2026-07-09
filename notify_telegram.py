import os
import sys
from telegram import Bot
import asyncio

async def send_report(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    bot = Bot(token=os.getenv('TELEGRAM_TOKEN'))
    # 分段处理过长消息，防止 Telegram API 报错
    for i in range(0, len(content), 4000):
        await bot.send_message(chat_id=os.getenv('TELEGRAM_CHAT_ID'), text=content[i:i+4000])

if __name__ == "__main__":
    asyncio.run(send_report(sys.argv[1]))
