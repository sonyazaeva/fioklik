import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, types
import sqlite3 as sql
from aiogram.fsm.state import State, StatesGroup


logging.basicConfig(level=logging.INFO)  # базовые настройки для связи кода с тг
TOKEN = "8165202855:AAEEzi3GheY3K26A4YEQ1Wpk-TQQDfBB_Bs"
bot = Bot(token=TOKEN)
dp = Dispatcher()


class Form(StatesGroup):  # создаем состояние для дальнейшей регистрации (тут же можно состояния для других штук оставить)
    name = State()
    name_added = State()
    time = State()
    time_added = State()
    change_name = State()
    change_name_added = State()
    change_time = State()
    change_time_added = State()


db = sql.connect('users.db')  # создаем датабазу
cur = db.cursor()

async def send_prompt(bot: Bot, chat_id: int):
    f = open('notes.txt', encoding='utf-8')
    number = random.randrange(10) # поменять, когда будет больше промптов
    note = f.readlines()
    await bot.send_message(chat_id, text="вот тебе идея для заметки:\n\n" + note[number])
