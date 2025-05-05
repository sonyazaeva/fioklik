import asyncio
import logging
from aiogram.filters.command import Command
from aiogram import F
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, Text
from aiogram.utils import executor


logging.basicConfig(level=logging.INFO)
bot = Bot(token="8165202855:AAEEzi3GheY3K26A4YEQ1Wpk-TQQDfBB_Bs")
dp = Dispatcher()


@dp.message(Command("start"))  # хэндлер на команду /start
async def cmd_start(message: types.Message):
    await message.answer("привет! я Фёклик — друг, который всегда найдёт, чем тебя занять :)\n\n"
                         "каждый день в определенное время я буду присылать тебе идеи для заметок. "
                         "за каждую заметку ты будешь получать баллы, с помощью которых сможешь открыть новые функции. "
                         "например, я буду делиться с тобой мемами, анекдотами и многим-многим другим, что сделает твой день веселее и интереснее.\n\n"
                         "я бы хотел, чтобы наше общение было более постоянным, поэтому если ты будешь забывать писать заметки, то будешь терять баллы( "
                         "поэтому, пожалуйста, не забывай открывать чатик и писать что-то. не бойся, я напомню тебе о потере страйка!\n\n"
                         "о том, что я умею делать, ты можешь узнать, нажав /commands!")


@dp.message(Command("commands"))  # хэндлер на команду /commands
async def cmd_commands(message: types.Message):
    await message.answer("тут будет список команд, когда я чему-нибудь научусь :)")


async def account_db(message: types.Message): # создаем базу данных с сообщениями
    async with aiosqlite.connect('user_messages.db') as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS MESSAGES (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                message TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.commit()


async def save_message(user_id, username, message): # пытаемся сохранять сообщения и ПД юзеров
    async with aiosqlite.connect('user_messages.db') as db:
        await db.execute('INSERT INTO MESSAGES (user_id, username, message) VALUES (?, ?, ?)',
                            (user_id, username, message))
        await db.commit()
    await save_message(user_id, username, message)


async def on_startup(_):
    await account_db()

@dp.message_handler(commands=["create"]) # предлагаем создать аккаунт, команда /create
async def cmd_create(message: types.Message):
    keyb = [
        [types.KeyboardButton(text="давай")],
        [types.KeyboardButton(text="не сегодня")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=keyb)
    await message.answer("хочешь создать аккаунт?", reply_markup=keyboard)

@dp.message(Text('давай')) # отвечаем на согласие
async def yappi(message: types.Message):
    userid = message.from_user.id
    username = message.from_user.username
    await save_message(userid, username, 'записываю тебя в книжечку...')
    await message.answer('записал тебя в книжечку :)')
    await message.edit_reply_markup(reply_markup=None)

@dp.message(Text('не сегодня')) # отвечаем на отказ
async def nope(message: types.Message):
    await message.answer('ну и пожалуйста, ну и не нужно :(')
    await message.edit_reply_markup(reply_markup=None)

if __name__ == '__main__':
    dp.startup.register(on_startup)
    executor.start_polling(dp)


@dp.message(F.text)  # хэндлер на любой текст
async def cmd_dontknow(message: types.Message):
    await message.answer("я пока не понимаю твои сообщения, но уже скоро смогу быть твои другом!\n\nо том, что я умею делать, ты можешь узнать, нажав /commands!")


async def main():  # весь этот блок контролирует новые апдейты в чате (чтобы все работало беспрерывно)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
