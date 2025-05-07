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


@dp.message(Command("start"))  # хэндлер на команду /start
async def cmd_start(message: types.Message):
    await message.answer("привет! я Фёклик — друг, который всегда найдёт, чем тебя занять :)\n\n"
                         "каждый день в определенное время я буду присылать тебе идеи для заметок. "
                         "за каждую заметку ты будешь получать баллы, с помощью которых сможешь открыть новые функции. "
                         "например, я буду делиться с тобой мемами, анекдотами и многим-многим другим, что сделает твой день веселее и интереснее.\n\n"
                         "я бы хотел, чтобы наше общение было более постоянным, поэтому если ты будешь забывать писать заметки, то будешь терять баллы :(\n\n"
                         "поэтому, пожалуйста, не забывай открывать чатик и писать что-то. не бойся, я напомню тебе о потере страйка!\n\n"
                         "о том, что я умею делать, ты можешь узнать, нажав /commands!\n"
                         "а чтобы создать аккаунт, нажми /create)")


async def db_database():
    cur.execute('CREATE TABLE IF NOT EXISTS users ('
                'id INTEGER PRIMARY KEY, '
                'name TEXT, '
                'points INTEGER DEFAULT 0,'
                'time_hours INTEGER DEFAULT 0,'
                'time_mins INTEGER DEFAULT 0)')
    db.commit()


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


async def send_prompt(bot: Bot, chat_id: int):
    f = open('notes.txt', encoding='utf-8')
    number = random.randrange(10) # поменять, когда будет больше промптов
    note = f.readlines()
    await bot.send_message(chat_id, text="вот тебе идея для заметки:\n\n" + note[number])


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


@dp.message(Command("commands"))  # хэндлер на команду /commands
async def cmd_commands(message: types.Message):
    await message.answer('вот, что я уже умею!\n\n'
                         'create — создать аккаунт! давай скорее познакомимся\n'
                         '/account — проверить свои имя, баланс и доступные функции\n'
                         '/commands — узнать, что я умею делать')


def get_image():
    images = [x for x in os.listdir(r'C:\Users\sofiy\PycharmProjects\telegrambot\codes\images\photos')]

    return os.path.join(r'C:\Users\sofiy\PycharmProjects\telegrambot\codes\images\photos', random.choice(images))

@dp.message(Command("fun")) # хэндлер на картиночки
async def cmd_fun(message: types.Message):
    image_path = get_image()
    if image_path:
        photo = FSInputFile(image_path)
        await message.answer_photo(photo, caption='картиночка для тебя :з')

@dp.message(Command('chat_id')) # айди
async def get_chat_id(message: types.Message):
    chat_id = message.chat.id
    await message.answer(f'айди этого чата: {chat_id}')


@dp.message(Command('account')) # статистико аккаунто
async def get_account(message: types.Message):
    chat_id = message.chat.id
    cur.execute(f"SELECT name FROM users WHERE id = ?", (chat_id,))
    acc = cur.fetchone()
    cur.execute(f"SELECT points FROM users WHERE id = ?", (chat_id,))
    points = cur.fetchone()
    cur.execute(f"SELECT time_hours FROM users WHERE id = ?", (chat_id,))
    time_h = cur.fetchone()
    h = "%s" % str(time_h[0]) if time_h[0] >= 10 else "0%s" % str(time_h[0])
    cur.execute(f"SELECT time_mins FROM users WHERE id = ?", (chat_id,))
    time_m = cur.fetchone()
    m = "%s" % str(time_m[0]) if time_m[0] >= 10 else "0%s" % str(time_m[0])
    if acc:
        await message.answer(f'твой юзернейм: {acc[0]}\n'
                             f'твой баланс: {points[0]}\n'
                             f'выбранное время: {h}:{m}')
    else:
        await message.answer('видимо, у тебя еще нет аккаунта.\n'
                             'ты можешь создать его по команде /create')


@dp.message(F.text)  # хэндлер на любой текст
async def cmd_dontknow(message: types.Message):
    await message.answer(
        "я пока не понимаю твои сообщения, но уже скоро смогу быть твои другом!\n\nо том, что я умею делать, ты можешь узнать, нажав /commands!")


async def main() -> None: # весь этот блок контролирует новые апдейты в чате (чтобы все работало беспрерывно)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
