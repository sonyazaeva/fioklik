import asyncio
import logging
import sys
import random
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram import F
import requests
import sqlite3 as sql
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from urllib.parse import quote
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from aiogram.types import FSInputFile


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

@dp.message(Command("create")) #хэндлер на команду /create для создания аккаунта
async def cmd_create(message: types.Message, state: FSMContext):
    await db_database()
    await state.set_state(Form.name)
    await message.answer("давай познакомимся! скажи, как к тебе обращаться?")

@dp.message(Form.name)  # второй этап регистрации (ждем когда придет имя)
async def cmd_processname(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Form.name_added)

    def checker():
        cur.execute("SELECT COUNT(*) FROM users WHERE id = ?", (chat_id,))
        return cur.fetchone()[0] > 0

    chat_id = message.chat.id
    if not checker():
        username = message.text
        db.execute(f'INSERT INTO users VALUES ("{chat_id}", "{username}", "{0}", "{0}", "{0}")')
        await message.answer(f"ура! будем знакомы, {username}!\n"
                             f"теперь я каждый день буду присылать тебе идеи для заметок. напиши удобное для тебя время в формате 00:00, например, 6:00 для утра или 18:00 для вечера")  # тут знакомство заканчивается
        db.commit()
        await state.set_state(Form.time)
    else:
        await message.answer('похоже, у тебя уже есть аккаунт! \n\n'
                             'ты можешь посмотреть свою статистику по команде /stats')


@dp.message(Form.time)  # третий этап регистрации (ждем когда придет удобное время)
async def cmd_processtime(message: types.Message, state: FSMContext):
    hours, mins = map(int, message.text.split(':'))
    chat_id = message.chat.id
    await state.update_data(time_hours=hours, time_mins=mins)
    if 0 <= hours < 24 and 0 <= mins < 60 :
        db.execute(f'UPDATE users SET time_hours = ? WHERE id = ?', (hours, chat_id))
        db.execute(f'UPDATE users SET time_mins = ? WHERE id = ?', (mins, chat_id))
    else:
        await message.answer("пожалуйста, введи время в правильном формате, например 6:00 для утра или 18:00 для вечера")

    bot = Bot(TOKEN)
    scheduler = AsyncIOScheduler()
    timezone="Europe/Moscow"
    scheduler.add_job(send_prompt, trigger="cron", hour=hours,minute=mins,start_date=datetime.now(), id=str(chat_id), kwargs={
                    "bot": bot,
                    "chat_id": chat_id},
                      )
    scheduler.start()

    await message.answer(f'отлично, теперь каждый день в {message.text} я буду присылать тебе идею для заметки о прошедшем дне) '
                         f'не забывай отвечать мне, чтобы зарабатывать очки для открытия новых функций!')
    db.commit()
    await state.set_state(Form.time_added)
