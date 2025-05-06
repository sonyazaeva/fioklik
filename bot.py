import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram import F
import requests
import sqlite3 as sql
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from urllib.parse import quote


logging.basicConfig(level=logging.INFO)  # базовые настройки для связи кода с тг
bot = Bot(token="8165202855:AAEEzi3GheY3K26A4YEQ1Wpk-TQQDfBB_Bs")
dp = Dispatcher()


class Form(StatesGroup):  # создаем состояние для дальнейшей регистрации (тут же можно состояния для других штук оставить)
    name = State()
    name_added = State()
    time = State()
    time_added = State()


@dp.message(Command("start"))  # хэндлер на команду /start
async def cmd_start(message: types.Message):
    await message.answer("привет! я Фёклик — друг, который всегда найдёт, чем тебя занять :)\n\n"
                         "каждый день в определенное время я буду присылать тебе идеи для заметок. "
                         "за каждую заметку ты будешь получать баллы, с помощью которых сможешь открыть новые функции. "
                         "например, я буду делиться с тобой мемами, анекдотами и многим-многим другим, что сделает твой день веселее и интереснее.\n\n"
                         "я бы хотел, чтобы наше общение было более постоянным, поэтому если ты будешь забывать писать заметки, то будешь терять баллы :(\n\n"
                         "поэтому, пожалуйста, не забывай открывать чатик и писать что-то. не бойся, я напомню тебе о потере страйка!\n\n"
                         "о том, что я умею делать, ты можешь узнать, нажав /commands!"
                         "а чтобы создать аккаунт, нажми /create)")


db = sql.connect('users.db')  # создаем датабазу
cur = db.cursor()
async def db_database():
    cur.execute('CREATE TABLE IF NOT EXISTS users ('
                'id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE, '
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
        cur.execute(f"SELECT COUNT(*) FROM users WHERE {chat_id} = ?", (chat_id,))
        return cur.fetchone()[0] > 0

    chat_id = message.chat.id
    if not checker():
        username = message.text
        db.execute(f'INSERT INTO users VALUES ("{chat_id}", "{username}", "{0}", "{0}", "{0}")')
        await state.set_state(Form.time)
        await message.answer(f"ура! будем знакомы, {username}!\n"
                             f"теперь я каждый день буду присылать тебе идеи для заметок. напиши удобное для тебя время в формате 00:00, например 18:00")  # тут знакомство заканчивается
        db.commit()
    else:
        await message.answer('похоже, у тебя уже есть аккаунт! \n\n'
                             'ты можешь посмотреть свою статистику по команде /stats')


@dp.message(Form.time)  # третий этап регистрации (ждем когда придет удобное время)
async def cmd_processtime(message: types.Message, state: FSMContext):
    hours, mins = map(int, message.text.split(':'))
    chat_id = message.chat.id
    await state.update_data(time_hours=hours, time_mins=mins)
    db.execute(f'UPDATE users SET time_hours = ? WHERE id = ?', (hours, chat_id))
    db.execute(f'UPDATE users SET time_mins = ? WHERE id = ?', (mins, chat_id))
    await message.answer(f'отлично, теперь каждый день в {message.text} я буду присылать тебе идею для заметки о прошедшем дне) '
                         f'не забывай отвечать мне, чтобы зарабатывать очки для открытия новых функций!')
    db.commit()
    await state.set_state(Form.time_added)


@dp.message(Command("commands"))  # хэндлер на команду /commands
async def cmd_commands(message: types.Message):
    await message.answer("по команде /note я пришлю тебе идею для заметки :)")


@dp.message(Command("note"))  # хэндлер на команду /note
async def cmd_note(message: types.Message):
    f = open('notes.txt', encoding='utf-8')
    number = random.randrange(10)
    note = f.readlines()
    await message.answer("вот тебе идея для заметки:\n\n" + note[number])


@dp.message(Command("fun")) # хэндлер на картиночки
async def cmd_fun(message: types.Message):
    photo_url = 'some_url'
    safe_url = quote(photo_url, safe=':/')
    image = requests.get(safe_url).text
    await message.answer_photo(photo=image)


@dp.message(Command('chat_id')) # айди
async def get_chat_id(message: types.Message):
    chat_id = message.chat.id
    await message.answer(f'айди этого чата: {chat_id}')


@dp.message(Command('stats')) # статистико
async def get_stats(message: types.Message):
    chat_id = message.chat.id
    cur.execute(f"SELECT name FROM users WHERE {chat_id} = ?", (chat_id,))
    acc = cur.fetchone()
    cur.execute(f"SELECT points FROM users WHERE {chat_id} = ?", (chat_id,))
    points = cur.fetchone()
    if acc and points:
        await message.answer(f'твой юзернейм: {acc[0]}\n'
                             f'твой баланс: {points[0]}')
    else:
        await message.answer('видимо, у тебя еще нет аккаунта.\n'
                             'ты можешь создать его по команде /create')


@dp.message(F.text)  # хэндлер на любой текст
async def cmd_dontknow(message: types.Message):
    await message.answer(
        "я пока не понимаю твои сообщения, но уже скоро смогу быть твои другом!\n\nо том, что я умею делать, ты можешь узнать, нажав /commands!")


async def main():  # весь этот блок контролирует новые апдейты в чате (чтобы все работало беспрерывно)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
