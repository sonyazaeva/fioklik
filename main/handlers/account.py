import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
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

async def main() -> None: # весь этот блок контролирует новые апдейты в чате (чтобы все работало беспрерывно)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
