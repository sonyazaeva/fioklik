import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
import sqlite3 as sql
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

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

@dp.message(Command("change_name"))  # хэндлер на команду /change_name
async def cmd_change_name(message: types.Message, state: FSMContext):

    def checker():
        cur.execute("SELECT COUNT(*) FROM users WHERE id = ?", (chat_id,))
        return cur.fetchone()[0] > 0

    chat_id = message.chat.id
    if not checker():
        await message.answer('кажется, у тебя пока нет аккаунта :( чтобы создать его нажми /create')
    else:
        await state.set_state(Form.change_name)
        await message.answer("ты можешь выбрать новое имя!")

@dp.message(Form.change_name)  # ждем когда придет новое имя
async def cmd_processchangedname(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    chat_id = message.chat.id
    username = message.text
    db.execute(f'UPDATE users SET name = ? WHERE id = ?', (username, chat_id))
    await message.answer(f"ура! твоё новое имя: {username})")
    db.commit()
    await state.set_state(Form.change_name_added)


@dp.message(Command("change_time"))  # хэндлер на команду /change_time
async def cmd_change_time(message: types.Message, state: FSMContext):

    def checker():
        cur.execute("SELECT COUNT(*) FROM users WHERE id = ?", (chat_id,))
        return cur.fetchone()[0] > 0

    chat_id = message.chat.id
    if not checker():
        await message.answer('кажется, у тебя пока нет аккаунта :( чтобы создать его нажми /create')
    else:
        await state.set_state(Form.change_time)
        await message.answer("ты можешь выбрать другое время!")

@dp.message(Form.change_time)  # ждем когда придет новое время
async def cmd_processchangedtime(message: types.Message, state: FSMContext):
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
    scheduler.scheduled_job(send_prompt, trigger="cron", hour=hours, minute=mins, start_date=datetime.now(), id=str(chat_id), kwargs={
                    "bot": bot,
                    "chat_id": chat_id},
                      )
    scheduler.start()

    await message.answer(f"ура! теперь я буду присылать тебе идеи для записок о дне в {message.text})")
    db.commit()
    await state.set_state(Form.change_time_added)
