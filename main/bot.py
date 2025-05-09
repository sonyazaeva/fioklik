import asyncio
import logging
import sys
import random
import os
import requests
import sqlite3 as sql
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from urllib.parse import quote
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

logging.basicConfig(level=logging.INFO)  # базовые настройки для связи кода с тг
TOKEN = "8165202855:AAEEzi3GheY3K26A4YEQ1Wpk-TQQDfBB_Bs"
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()


class Form(StatesGroup):  # создаем состояние для дальнейшей регистрации (тут же можно состояния для других штук оставить)
    name = State()
    name_added = State()
    timezone = State()
    alt_timezone = State()
    time = State()
    time_added = State()
    change_name = State()
    change_name_added = State()
    change_time = State()
    change_time_added = State()
    save = State()
    save_added = State()


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
                         "о том, что я умею делать, ты можешь узнать, нажав /commands!\n\n"
                         "<b>а чтобы создать аккаунт, нажми /create</b>", parse_mode='HTML')


async def db_database():
    cur.execute('CREATE TABLE IF NOT EXISTS users ('
                'id INTEGER PRIMARY KEY, '
                'name TEXT, '
                'points INTEGER DEFAULT 0, '
                'timezone TEXT, '
                'time_hours INTEGER DEFAULT 0, '
                'time_mins INTEGER DEFAULT 0)'
                )
    db.commit()

async def send_prompt(bot: Bot, chat_id: int):
    f = open('notes.txt', encoding='utf-8')
    number = random.randrange(55) # поменять, когда будет больше промптов
    note = f.readlines()
    await bot.send_message(chat_id, text=f"вот тебе идея для заметки:\n<b>{note[number]}</b>\n\n", parse_mode='HTML')

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
        db.execute(f'INSERT INTO users VALUES ("{chat_id}", "{username}", "{0}", "UTC +3","{0}", "{0}")')
        await message.answer(f"ура! будем знакомы, <b>{username}!</b>\n"
                             f"чтобы я каждый день присылал тебе идеи для заметок, сначала напиши удобное для тебя время в формате 00:00, "
                             f"например, 06:00 для утра или 18:00 для вечера",
                             parse_mode='HTML')  # тут знакомство заканчивается

        db.commit()
        await state.set_state(Form.time)
    else:
        await message.answer('<b>похоже, у тебя уже есть аккаунт!</b> \n\n'
                             'ты можешь посмотреть свою статистику по команде /stats', parse_mode='HTML')

@dp.message(Form.time)  # третий этап регистрации (ждем когда придет удобное время)
async def cmd_processtime(message: types.Message, state: FSMContext):
    hours, mins = map(int, message.text.split(':'))
    chat_id = message.chat.id
    await state.update_data(time_hours=hours, time_mins=mins)
    if 0 <= hours < 24 and 0 <= mins < 60:
        db.execute(f'UPDATE users SET time_hours = ? WHERE id = ?', (hours, chat_id))
        db.execute(f'UPDATE users SET time_mins = ? WHERE id = ?', (mins, chat_id))
    else:
        await message.answer("пожалуйста, введи время в правильном формате, например 06:00 для утра или 18:00 для вечера")
    scheduler.add_job(send_prompt, trigger="cron", hour=hours, minute=mins, id=str(chat_id), kwargs={
                    "bot": bot,
                    "chat_id": chat_id},
                      )
    await message.answer(f'отлично, теперь каждый день в <b>{message.text}</b> я буду присылать тебе идею для заметки о прошедшем дне) '
                         f'не забывай отвечать мне, чтобы зарабатывать очки для открытия новых функций!\n\n'
                         f'теперь тебе нужно выбрать часовой пояс, в котором ты находишься.\n\n'
                         f'<b>для этого вызови команду /timezone и нажми на нужную кнопку под сообщением.</b>', parse_mode='HTML')
    db.commit()
    await state.set_state(Form.time_added)

@dp.message(Command('timezone'))
async def choose_timezone(message: types.Message):
    utc_2 = InlineKeyboardButton(text='UTC +02:00', callback_data='UTC +02:00')
    utc_3 = InlineKeyboardButton(text='UTC +03:00', callback_data='UTC +03:00')
    utc_4 = InlineKeyboardButton(text='UTC +04:00', callback_data='UTC +04:00')
    utc_5 = InlineKeyboardButton(text='UTC +05:00', callback_data='UTC +05:00')
    utc_6 = InlineKeyboardButton(text='UTC +06:00', callback_data='UTC +06:00')
    utc_7 = InlineKeyboardButton(text='UTC +07:00', callback_data='UTC +07:00')
    utc_8 = InlineKeyboardButton(text='UTC +08:00', callback_data='UTC +08:00')
    utc_9 = InlineKeyboardButton(text='UTC +09:00', callback_data='UTC +09:00')
    utc_10 = InlineKeyboardButton(text='UTC +10:00', callback_data='UTC +10:00')
    utc_11 = InlineKeyboardButton(text='UTC +11:00', callback_data='UTC +11:00')
    utc_12 = InlineKeyboardButton(text='UTC +12:00', callback_data='UTC +12:00')
    other = InlineKeyboardButton(text='другое!', callback_data='не')

    rowa, rowb, rowc, rowd = [utc_2, utc_3, utc_4], [utc_5, utc_6, utc_7], [utc_8, utc_9, utc_10], [utc_11, utc_12, other]
    rows = [rowa, rowb, rowc, rowd]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(text='Выбери тот часовой пояс, в котором ты находишься', reply_markup=keyboard)
async def timezone_confirmation(message: types.Message, timezone: str):
    await message.answer(f'часовой пояс {timezone} выбран!\n\n'
                         f'если тебе нужен другой часовой пояс, воспользуйся командой /alt_timezone\n\n'
                         f'если ты ошибся, снова воспользуйся /timezone')

@dp.callback_query()
async def handle_timezone(callback_query: types.callback_query):
        chat_id = callback_query.from_user.id
        username = callback_query.from_user.username
        timezone = callback_query.data

        cur.execute("SELECT 1 FROM users WHERE id = ?", (chat_id,))
        if cur.fetchone():
            cur.execute("UPDATE users SET timezone = ? WHERE id = ?", (timezone, chat_id))
        else:
            cur.execute("INSERT INTO users VALUES (?, ?, ?)", (chat_id, username, timezone))
        db.commit()
        await callback_query.answer(':з')
        await timezone_confirmation(callback_query.message, timezone)


@dp.message(Command('alt_timezone'))
async def choose_alt_timezone(message: types.Message):
            utc_neg12 = InlineKeyboardButton(text='UTC -12:00', callback_data='UTC -12:00')
            utc_neg11 = InlineKeyboardButton(text='UTC -11:00', callback_data='UTC -11:00')
            utc_neg10 = InlineKeyboardButton(text='UTC -10:00', callback_data='UTC -10:00')
            utc_neg930 = InlineKeyboardButton(text='UTC -09:30', callback_data='UTC -09:30')
            utc_neg9 = InlineKeyboardButton(text='UTC -09:00', callback_data='UTC -09:00')
            utc_neg8 = InlineKeyboardButton(text='UTC -08:00', callback_data='UTC -08:00')
            utc_neg7 = InlineKeyboardButton(text='UTC -07:00', callback_data='UTC -07:00')
            utc_neg6 = InlineKeyboardButton(text='UTC -06:00', callback_data='UTC -06:00')
            utc_neg5 = InlineKeyboardButton(text='UTC -05:00', callback_data='UTC -05:00')
            utc_neg4 = InlineKeyboardButton(text='UTC -04:00', callback_data='UTC -04:00')
            utc_neg330 = InlineKeyboardButton(text='UTC -03:30', callback_data='UTC -03:30')
            utc_neg3 = InlineKeyboardButton(text='UTC -03:00', callback_data='UTC -03:00')
            utc_neg2 = InlineKeyboardButton(text='UTC -02:00', callback_data='UTC -02:00')
            utc_neg1 = InlineKeyboardButton(text='UTC -01:00', callback_data='UTC -01:00')
            utc_0 = InlineKeyboardButton(text='UTC +00:00', callback_data='UTC +00:00')
            utc_1 = InlineKeyboardButton(text='UTC +01:00', callback_data='UTC +01:00')
            utc_330 = InlineKeyboardButton(text='UTC +03:30', callback_data='UTC +03:30')
            utc_430 = InlineKeyboardButton(text='UTC +04:30', callback_data='UTC +04:30')
            utc_530 = InlineKeyboardButton(text='UTC +05:30', callback_data='UTC +05:30')
            utc_545 = InlineKeyboardButton(text='UTC +05:45', callback_data='UTC +05:45')
            utc_630 = InlineKeyboardButton(text='UTC +06:30', callback_data='UTC +06:30')
            utc_845 = InlineKeyboardButton(text='UTC +08:45', callback_data='UTC +08:45')
            utc_930 = InlineKeyboardButton(text='UTC +09:30', callback_data='UTC +09:30')
            utc_1030 = InlineKeyboardButton(text='UTC +10:30', callback_data='UTC +10:30')
            utc_1245 = InlineKeyboardButton(text='UTC +12:45', callback_data='UTC +12:45')
            utc_13 = InlineKeyboardButton(text='UTC +13:00', callback_data='UTC +13:00')
            utc_14 = InlineKeyboardButton(text='UTC +14:00', callback_data='UTC +14:00')

            linesa = [utc_neg12, utc_neg11, utc_neg10, utc_neg930]
            linesb = [utc_neg9, utc_neg8, utc_neg7, utc_neg6]
            linesc = [utc_neg5, utc_neg4, utc_neg330, utc_neg3]
            linesd = [utc_neg2, utc_neg1, utc_0]
            linese = [utc_1, utc_330, utc_430, utc_530]
            linesf = [utc_545, utc_630, utc_845, utc_930]
            linesg = [utc_1030, utc_1245, utc_13, utc_14]
            lines = [linesa, linesb, linesc, linesd, linese, linesf, linesg]

            alt_keyboard = types.InlineKeyboardMarkup(inline_keyboard=lines)
            await message.answer(text='выбери другой часовой пояс:',
                                 reply_markup=alt_keyboard)
async def alt_timezone_confirmation(message: types.Message, alt_timezone: str):
    await message.answer(f'часовой пояс {alt_timezone} выбран!\n\n'
                         f'если тебе нужен другой часовой пояс, воспользуйся командой /alt_timezone\n\n'
                         f'если ты ошибся, снова воспользуйся /timezone')

@dp.callback_query()
async def handle_alt_timezone(callback_query: types.callback_query):
        chat_id = callback_query.from_user.id
        username = callback_query.from_user.username
        alt_timezone = callback_query.data

        cur.execute("SELECT 1 FROM users WHERE id = ?", (chat_id,))
        if cur.fetchone():
            cur.execute("UPDATE users SET timezone = ? WHERE id = ?", (alt_timezone, chat_id))
        else:
            cur.execute("INSERT INTO users VALUES (?, ?, ?)", (chat_id, username, alt_timezone))
        db.commit()
        await callback_query.answer(':з')
        await alt_timezone_confirmation(callback_query.message, alt_timezone)



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
    await message.answer(f"ура! твоё новое имя: </b>{username}</b>", parse_mode='HTML')
    db.commit()
    await state.set_state(Form.change_name_added)


@dp.message(Command("change_time"))  # хэндлер на команду /change_time
async def cmd_change_time(message: types.Message, state: FSMContext):
    def checker():
        cur.execute("SELECT COUNT(*) FROM users WHERE id = ?", (chat_id,))
        return cur.fetchone()[0] > 0
    chat_id = message.chat.id
    if not checker():
        await message.answer('кажется, у тебя пока нет аккаунта :(\n\n'
                             '<b>чтобы создать его нажми /create</b>', parse_mode='HTML')
    else:
        await state.set_state(Form.change_time)
        await message.answer("ты можешь выбрать другое время! пожалуйста, введи его в формате 00:00, "
                             "например, 06:00 для утра или 18:00 для вечера")

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
    scheduler.reschedule_job(job_id=str(chat_id), trigger="cron", hour=hours, minute=mins)
    await message.answer(f"ура! теперь я буду присылать тебе идеи для заметок о дне в <b>{message.text}</b>)", parse_mode='HTML')
    db.commit()
    await state.set_state(Form.change_time_added)


@dp.message(Command("commands"))  # хэндлер на команду /commands
async def cmd_commands(message: types.Message):
    await message.answer('вот, что я уже умею!\n\n'
                         '/create — создать аккаунт! давай скорее познакомимся :)\n'
                         '/account — проверить свои имя, баланс и доступные функции\n'
                         '/commands — узнать, что я умею делать\n'
                         '/fun - смешная картинка')


def get_image():
    images = [x for x in os.listdir(r'fioklik_images')]
    return os.path.join(r'fioklik_images', random.choice(images))

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
        await message.answer(f'твой юзернейм: <b>{acc[0]}</b>\n'
                             f'твой баланс: <b>{points[0]}</b>\n'
                             f'выбранное время: <b>{h}:{m}</b>', parse_mode='HTML')
    else:
        await message.answer('видимо, у тебя еще нет аккаунта.\n\n'
                             '<b>ты можешь создать его по команде /create</b>', parse_mode='HTML')


@dp.message(F.text)  # хэндлер на любой текст
async def cmd_dontknow(message: types.Message):
    await message.answer(
        "я пока не понимаю твои сообщения, но уже скоро смогу быть твои другом!\n\n"
        "о том, что я умею делать, ты можешь узнать, нажав /commands!")


async def main() -> None: # весь этот блок контролирует новые апдейты в чате (чтобы все работало беспрерывно)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
