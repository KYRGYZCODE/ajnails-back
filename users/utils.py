import asyncio
from aiogram import Bot
from decouple import config

TELEGRAM_TOKEN = config('TELEGRAM_BOT')
OPERATORS = config('OPERATORS_CHAT_IDS').split(',')

async def send_order_message(message):
    bot = Bot(TELEGRAM_TOKEN)
    for op in OPERATORS:
        await bot.send_message(op, message)
