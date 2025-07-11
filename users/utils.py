import asyncio
from aiogram import Bot
from decouple import config

TELEGRAM_TOKEN = config('TELEGRAM_BOT')
OPERATORS = config('OPERATORS_CHAT_IDS').split(',')

async def send_message(message, chat_ids):
    bot = Bot(TELEGRAM_TOKEN)
    for chat_id in chat_ids:
        await bot.send_message(chat_id, message)

async def send_order_message(message, chat_ids=None):
    recipients = chat_ids or OPERATORS
    await send_message(message, recipients)
