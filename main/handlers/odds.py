import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, types
from aiogram import F
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

@dp.message(F.text)  # хэндлер на любой текст
async def cmd_dontknow(message: types.Message):
    await message.answer(
        "я пока не понимаю твои сообщения, но уже скоро смогу быть твои другом!\n\nо том, что я умею делать, ты можешь узнать, нажав /commands!")


async def main() -> None: # весь этот блок контролирует новые апдейты в чате (чтобы все работало беспрерывно)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
