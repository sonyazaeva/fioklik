import logging
import sys
import asyncio
import random
import os
import sqlite3 as sql
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.types import InlineKeyboardButton
from datetime import datetime, timedelta
import csv

# --- привязываем код к тг ---
logging.basicConfig(level=logging.INFO)  # базовые настройки для связи кода с тг
TOKEN = "8165202855:AAEEzi3GheY3K26A4YEQ1Wpk-TQQDfBB_Bs"
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# --- переменные для курсора и связи с датабазами ---
db = sql.connect("users.db")
cur = db.cursor()
prdb = sql.connect("saved_prompts.db")
cucur = prdb.cursor()

# --- создаем датабазу users.db ---
cur.execute(
    "CREATE TABLE IF NOT EXISTS users ("
    "id INTEGER PRIMARY KEY, "
    "name TEXT, "
    "points INTEGER DEFAULT 0, "
    "timezone TEXT DEFAULT NONE, "
    "time_hours INTEGER DEFAULT 0, "
    "time_mins INTEGER DEFAULT 0, "
    "save_status TEXT, "
    "strike INTEGER DEFAULT 0, "
    "functions TEXT,"
    "prompt_num INTEGER DEFAULT 0)"
)
db.commit()

# --- создаем датабазу saved_prompts.db ---
cucur.execute(
    "CREATE TABLE IF NOT EXISTS saved_prompts ("
    "id INTEGER PRIMARY KEY, "
    "prompt TEXT, "
    "response TEXT, "
    "date DATETIME)"
)
prdb.commit()


# --- состояния, которые используются для регистрации ---
class Form(StatesGroup):
    started = State()  # регистрация началась > ждем имя
    name_set = State()  # имя установлено > предлагаем выбрать таймзону
    timezone_set = State()  # подверждаем выбор таймзоны > ждем время
    time_set = State()  # время установлено > конец!

    # --- состояния, которые используются для других команд ---
    save = State()
    change_name = State()
    change_time = State()
    timezone_changing = State()
    alt_timezone = State()
    handle_function = State()
    handle_answer = State()
    set_pause = State()
    set_resume = State()


# --- словарь с функциями из магазина, их ценой и индексом в "шифре" ---
function_dict = {
    "meme": {"text": "мемы", "price": 10, "index": 0},
    "anec": {"text": "анекдоты", "price": 14, "index": 1},
    "quote": {"text": "цитаты", "price": 20, "index": 2},
    "test": {"text": "тестики", "price": 28, "index": 3},
    "music": {"text": "музыка", "price": 38, "index": 4},
}


# --- РАСПИСАНИЕ ---

# --- отправка идеи для заметки в выбранное время ---
async def send_prompt(bot: Bot, chat_id: int):
    cur.execute(f"SELECT save_status FROM users WHERE id = ?", (chat_id,))
    save_status = cur.fetchone()
    if save_status[0] == "sending":
        f = open("notes.txt", encoding="utf-8")
        number = random.randrange(200)
        db.execute(
            f"UPDATE users SET prompt_num = ? WHERE id = ?",
            (
                number,
                chat_id,
            ),
        )
        note = f.readlines()
        current_prompt = note[number]
        await bot.send_message(
            chat_id,
            text=f"вот тебе идея для заметки:\n<b>{current_prompt}</b>\n\n"
                 f"у тебя есть целый день, чтобы написать заметку и получить баллы! "
                 f"когда захочешь это сделать, нажми /save, и напиши заметку отдельным сообщением.",
            parse_mode="HTML",
        )
        db.execute(
            f"UPDATE users SET save_status = ? WHERE id = ?", ("saving", chat_id)
        )
        db.commit()

        scheduler.add_job(
            send_alert,
            trigger="date",
            run_date=datetime.now() + timedelta(hours=22) - timedelta(seconds=5),
            id='alert' + str(chat_id),
            kwargs={"bot": bot, "chat_id": chat_id},
        )
        scheduler.add_job(
            fine,
            trigger="date",
            run_date=datetime.now() + timedelta(days=1),
            id='fine' + str(chat_id),
            kwargs={"bot": bot, "chat_id": chat_id},
        )


# --- отправка предупреждения об истечении времени ---
async def send_alert(bot: Bot, chat_id: int):
    cur.execute(f"SELECT save_status FROM users WHERE id = ?", (chat_id,))
    save_status = cur.fetchone()
    if save_status[0] == "saving":
        await bot.send_message(
            chat_id,
            text=f"у тебя осталось два часа, чтобы написать заметку!",
            parse_mode="HTML",
        )


# --- штраф при отсутствии заметки к окончанию времени ---
async def fine(bot: Bot, chat_id: int):
    cur.execute(f"SELECT save_status FROM users WHERE id = ?", (chat_id,))
    save_status = cur.fetchone()
    if save_status[0] == "saving":
        cur.execute(f"SELECT points FROM users WHERE id = ?", (chat_id,))
        points = cur.fetchone()
        if points[0] != 0:
            db.execute(
                f"UPDATE users SET points = ? WHERE id = ?", (points[0] - 1, chat_id)
            )
            db.execute(f"UPDATE users SET strike = ? WHERE id = ?", (0, chat_id))
            await bot.send_message(
                chat_id,
                text=f"сегодня я не получил заметку от тебя, поэтому ты теряешь один балл и свой страйк :(",
                parse_mode="HTML",
            )
        else:
            await bot.send_message(
                chat_id, text=f"мне грустно без тебя :(", parse_mode="HTML"
            )
    db.execute(f"UPDATE users SET save_status = ? WHERE id = ?", ("sending", chat_id))
    db.commit()


# --- обвление использования разовых функций ---
async def new_day(chat_id: int):
    cur.execute(f"SELECT functions FROM users WHERE id = ?", (chat_id,))
    functions_code = cur.fetchone()
    new_code = functions_code[0].replace('3', '2')
    cur.execute(f"UPDATE users SET functions = ? WHERE id = ?", (new_code, chat_id,))
    db.commit()


# --- перевод времени по Москве ---
async def timezone_converter(timezone, hours):
    if timezone < 3:
        send_time = (hours + (3 - timezone)) % 24
    else:
        x = (hours - (timezone - 3)) % 24
        if x < 0:
            send_time = 24 + x
        else:
            send_time = x
    return send_time


# --- хэндлер на /cancel ---
@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("все действия отменены :)")


# --- хэндлер на команду /start: регистрация ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    chat_id = message.chat.id

    # --- проверяем, нет ли пользователя в базе ---
    def checker():
        cur.execute("SELECT COUNT(*) FROM users WHERE id = ?", (chat_id,))
        return cur.fetchone()[0] > 0

    if checker():  # если пользователь уже зарегистрирован
        cur.execute(f"SELECT name FROM users WHERE id = ?", (chat_id,))
        username = cur.fetchone()
        await message.answer(
            f"<b>{username[0]}</b>, как здорово, что ты тут!", parse_mode="HTML"
        )
    else:  # если пользователь не зарегистрирован
        await state.set_state(Form.started)
        await message.answer(
            "привет! я Фёклик — друг, который всегда найдёт, чем тебя занять :)\n\n"
            "каждый день в определенное время я буду присылать тебе идеи для заметок. "
            "за каждую заметку ты будешь получать баллы, с помощью которых сможешь открыть новые функции. "
            "например, я буду делиться с тобой мемами, анекдотами и многим-многим другим, что сделает твой день веселее и интереснее.\n\n"
            "а сейчас давай познакомимся! скажи, как к тебе обращаться?"
        )


# --- второй этап: получаем имя и добавляем пользователя в базу, настраиваем таймзону ---
@dp.message(Form.started)
async def cmd_processname(message: types.Message, state: FSMContext) -> None:
    await state.set_state(Form.name_set)
    chat_id = message.chat.id
    username = message.text
    db.execute(
        f"INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (chat_id, username, 0, "UTC +03:00", 0, 0, "sending", 0, "00000", 0),
    )
    await message.answer(
        f"ура! будем знакомы, <b>{username}</b>! "
        f"если что-то пошло не так, не переживай: ты сможешь изменить имя позже :)",
        parse_mode="HTML",
    )

    # --- выбираем таймзону ---
    utc_0 = InlineKeyboardButton(text="UTC +00:00", callback_data="UTC +00:00")
    utc_1 = InlineKeyboardButton(text="UTC +01:00", callback_data="UTC +01:00")
    utc_2 = InlineKeyboardButton(text="UTC +02:00", callback_data="UTC +02:00")
    utc_3 = InlineKeyboardButton(text="UTC +03:00 (Москва)", callback_data="UTC +03:00")
    utc_4 = InlineKeyboardButton(text="UTC +04:00", callback_data="UTC +04:00")
    utc_5 = InlineKeyboardButton(text="UTC +05:00", callback_data="UTC +05:00")
    utc_6 = InlineKeyboardButton(text="UTC +06:00", callback_data="UTC +06:00")
    utc_7 = InlineKeyboardButton(text="UTC +07:00", callback_data="UTC +07:00")
    utc_8 = InlineKeyboardButton(text="UTC +08:00", callback_data="UTC +08:00")
    utc_9 = InlineKeyboardButton(text="UTC +09:00", callback_data="UTC +09:00")
    utc_10 = InlineKeyboardButton(text="UTC +10:00", callback_data="UTC +10:00")
    utc_11 = InlineKeyboardButton(text="UTC +11:00", callback_data="UTC +11:00")
    utc_12 = InlineKeyboardButton(text="UTC +12:00", callback_data="UTC +12:00")

    rows = [
        [utc_0, utc_1, utc_2],
        [utc_3],
        [utc_4, utc_5, utc_6],
        [utc_7, utc_8, utc_9],
        [utc_10, utc_11, utc_12],
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(
        text="чтобы я вовремя присылал сообщения, выбери свой часовой пояс!\n\n"
        "я ещё не окончил первый класс, поэтому умею считать только до 12 :(",
        reply_markup=keyboard,
    )


# --- обрабатываем таймзону ---
@dp.callback_query(Form.name_set)
async def handle_timezone(callback_query: types.callback_query, state: FSMContext):
    chat_id = callback_query.from_user.id
    timezone = callback_query.data
    db.execute("UPDATE users SET timezone = ? WHERE id = ?", (timezone, chat_id))
    db.commit()
    await timezone_confirmation(callback_query.message, timezone, callback_query)
    await state.set_state(Form.timezone_set)


# --- подтверждаем выбор часового пояса ---
async def timezone_confirmation(
    message: types.Message, timezone, callback_query: types.callback_query
) -> None:
    await callback_query.answer(":з")
    await message.answer(
        f"часовой пояс <b>{timezone}</b> выбран! "
        f"ты всегда сможешь изменить его в настройках аккаунта.\n\n"
        f"а сейчас, пожалуйста, напиши, в какое время тебе будет удобно получать идеи для заметок? "
        f"укажи его в формате 00:00. например, 06:00 для утра или 18:00 для вечера",
        parse_mode="HTML",
    )


# --- третий этап регистрации: получаем время ---
@dp.message(Form.timezone_set)
async def cmd_processtime(message: types.Message, state: FSMContext) -> None:
    # --- проверяем соответствие формата введенного времени ---
    try:
        hours, mins = map(int, message.text.split(":"))
        chat_id = message.chat.id
        await state.update_data(time_hours=hours, time_mins=mins)
    except ValueError:
        await message.answer(
            "пожалуйста, введи время в правильном формате, например 06:00 для утра или 18:00 для вечера"
        )

    if 0 <= hours < 24 and 0 <= mins < 60:
        db.execute(f"UPDATE users SET time_hours = ? WHERE id = ?", (hours, chat_id))
        db.execute(f"UPDATE users SET time_mins = ? WHERE id = ?", (mins, chat_id))
        db.commit()
        cur.execute(f"SELECT timezone FROM users WHERE id = ?", (chat_id,))
        timezone = cur.fetchone()[0]
        send_time = await timezone_converter(int(timezone[5:7]), hours)
        scheduler.add_job(
            send_prompt,
            trigger="cron",
            hour=send_time,
            minute=mins,
            id=str(chat_id),
            kwargs={"bot": bot, "chat_id": chat_id},
        )

        set_at_midnight = await timezone_converter(int(timezone[5:7]), 0)
        scheduler.add_job(
            new_day,
            trigger="cron",
            hour=set_at_midnight,
            minute=00,
            id='night' + str(chat_id),
            kwargs={"chat_id": chat_id},
        )

        h = "%s" % str(hours) if hours >= 10 else "0%s" % str(hours)
        m = "%s" % str(mins) if mins >= 10 else "0%s" % str(mins)
        await message.answer(
            f"отлично, теперь каждый день в <b>{h}:{m}</b> я буду присылать тебе идею для заметки о прошедшем дне) "
            f"не забывай отвечать мне, чтобы зарабатывать баллы и открывать новые функции!\n\n"
            f"рад, что мы познакомились! держи стикерпак в честь знакомства: https://t.me/addstickers/fioklik :)",
            parse_mode="HTML",
        )
        await cmd_account(message)
        await cmd_commands(message)
        await cmd_info(message)
        await state.set_state(Form.time_set)
    else:
        await message.answer("пожалуйста, введи время в правильном формате, например 06:00 для утра или 18:00 для вечера")


# --- берём доступные функции ---
async def cmd_available_func(message: types.Message):
    chat_id = message.chat.id
    cur.execute(f"SELECT functions FROM users WHERE id = ?", (chat_id,))
    functions_code = cur.fetchone()[0]
    availible = []
    for key, value in function_dict.items():
        if functions_code[value["index"]] == "2":
            func = f"{value['text']}"
            availible.append(func)
    str_av = ", ".join(availible)
    if len(str_av) == 0:
        return "функций пока нет :("
    else:
        return str_av


# --- хэндлер на команду /account ---
@dp.message(Command("account"))
async def cmd_account(message: types.Message) -> None:
    chat_id = message.chat.id
    cur.execute(f"SELECT name FROM users WHERE id = ?", (chat_id,))
    acc = cur.fetchone()
    cur.execute(f"SELECT points FROM users WHERE id = ?", (chat_id,))
    points = cur.fetchone()
    cur.execute(f"SELECT strike FROM users WHERE id = ?", (chat_id,))
    strike = cur.fetchone()
    cur.execute(f"SELECT timezone FROM users WHERE id = ?", (chat_id,))
    tmz = cur.fetchone()
    cur.execute(f"SELECT time_hours FROM users WHERE id = ?", (chat_id,))
    time_h = cur.fetchone()
    h = "%s" % str(time_h[0]) if time_h[0] >= 10 else "0%s" % str(time_h[0])
    cur.execute(f"SELECT time_mins FROM users WHERE id = ?", (chat_id,))
    time_m = cur.fetchone()
    m = "%s" % str(time_m[0]) if time_m[0] >= 10 else "0%s" % str(time_m[0])
    func = await cmd_available_func(message)
    if acc:
        await message.answer(
            f"вот что я тебе знаю :)\n\n"
            f"твой юзернейм: <b>{acc[0]}</b>\n"
            f"твой баланс: <b>{points[0]}</b>\n"
            f"твой страйк: <b>{strike[0]}</b>\n"
            f"выбранное время: <b>{h}:{m}</b>\n"
            f"часовой пояс: <b>{tmz[0]}</b>\n"
            f"доступные функции: {func}\n\n"
            f"если ты хочешь изменить имя, время или часовой пояс, нажми /edit_account",
            parse_mode="HTML",
        )


# --- хэндлер на команду /commands ---
@dp.message(Command("commands"))
async def cmd_commands(message: types.Message):
    await message.answer(
        "давай расскажу о том, что я умею!\n\n"
        "<b>/account</b> — проверить свои имя, баланс и доступные функции или отредактировать аккаунт\n"
        "<b>/shop</b> — открыть магазин и купить какую-нибудь функцию (мне уже не терпится отправить тебе мем!)\n"
        "<b>/info</b> — узнать о том, как все устроено и как зарабатывать баллы\n"
        "<b>/cancel</b> — отменить любое действие",
        parse_mode="HTML",
    )


# --- хэндлер на команду /info ---
@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    await message.answer(
        "<b>как тут все устроено?</b>\n\n"
        "каждый день в то время, которые ты установил при регистрации, я буду присылать тебе идею для заметки. "
        "чтобы оставить заметку, тебе нужно отправить команду /save. за каждую заметку ты будешь получать 2 балла.\n\n"
        "если каждый день в течение недели ты будешь оставлять заметки, то дальше каждая следующая будет приносить тебе целых 3 балла) "
        "правда, за каждый пропущенный день, у тебя будет сниматься 1 балл и обнуляться страйк... "
        "не бойся, я напомню тебе о заметке за два часа до конца суток с момента отправки идеи :)\n\n"
        "<b>зачем нужны баллы?</b>\n\n"
        "я могу отправлять не только идеи для заметок, но и другие штуки) "
        "чтобы открыть новую функцию, копи баллы и покупай в магазине с помощью /shop. "
        "открыв новую функцию, ты сможешь вызывать её один раз в день "
        "и получать какую-то прихолюху (мем, анекдот, тестик или волчью цитатку).\n\n"
        "есть ещё несколько особых команд, о которых я расскажу тебе позже! вот так вот :)",
        parse_mode="HTML",
    )


# --- хэндлер на команду /edit_account ---
@dp.message(Command("edit_account"))
async def cmd_edit_account(message: types.Message) -> None:
    await message.answer(
        f"ух, как мы сейчас все поменяем!\n\n"
        f"<b>/change_name</b> - изменить имя\n"
        f"<b>/change_time</b> - изменить время, в которое ты хочешь получать идеи для заметок\n"
        f"<b>/change_timezone</b> - изменить часовой пояс\n",
        parse_mode="HTML",
    )


# --- хэндлер на команду /change_name ---
@dp.message(Command("change_name"))
async def cmd_change_name(message: types.Message, state: FSMContext):
    def checker():
        cur.execute("SELECT COUNT(*) FROM users WHERE id = ?", (chat_id,))
        return cur.fetchone()[0] > 0

    chat_id = message.chat.id
    if not checker():
        await message.answer(
            "кажется, у тебя пока нет аккаунта :(\n\n"
            "<b>чтобы создать его нажми /start</b>",
            parse_mode="HTML",
        )
    else:
        await state.set_state(Form.change_name)
        await message.answer("ты можешь выбрать новое имя!")


# --- второй этап: получаем новое имя и обновляем базу ---
@dp.message(Form.change_name)
async def cmd_processchangedname(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    chat_id = message.chat.id
    username = message.text
    db.execute(f"UPDATE users SET name = ? WHERE id = ?", (username, chat_id))
    db.commit()
    await message.answer(f"ура! твоё новое имя: <b>{username}</b>", parse_mode="HTML")
    await state.clear()


# --- хэндлер на команду /change_time ---
@dp.message(Command("change_time"))
async def cmd_change_time(message: types.Message, state: FSMContext):
    def checker():
        cur.execute("SELECT COUNT(*) FROM users WHERE id = ?", (chat_id,))
        return cur.fetchone()[0] > 0

    chat_id = message.chat.id
    if not checker():
        await message.answer(
            "кажется, у тебя пока нет аккаунта :(\n\n"
            "<b>чтобы создать его нажми /start</b>",
            parse_mode="HTML",
        )
    else:
        await state.set_state(Form.change_time)
        await message.answer(
            "ты можешь выбрать другое время! пожалуйста, введи его в формате 00:00, "
            "например, 06:00 для утра или 18:00 для вечера"
        )


# --- второй этап: получаем новое время и обновляем базу ---
@dp.message(Form.change_time)
async def cmd_processchangedtime(message: types.Message, state: FSMContext):
    chat_id = message.chat.id

    # --- проверяем соответствие формата введенного времени ---
    try:
        hours, mins = map(int, message.text.split(":"))
        await state.update_data(time_hours=hours, time_mins=mins)
    except ValueError:
        await message.answer(
            "пожалуйста, введи время в правильном формате, например 06:00 для утра или 18:00 для вечера"
        )
    if 0 <= hours < 24 and 0 <= mins < 60:
        db.execute(f"UPDATE users SET time_hours = ? WHERE id = ?", (hours, chat_id))
        db.execute(f"UPDATE users SET time_mins = ? WHERE id = ?", (mins, chat_id))
        db.commit()

        cur.execute(f"SELECT timezone FROM users WHERE id = ?", (chat_id,))
        timezone = cur.fetchone()[0]
        send_time = await timezone_converter(int(timezone[5:7]), hours)
        scheduler.reschedule_job(
            job_id=str(chat_id),
            trigger="cron",
            hour=send_time,
            minute=mins,
        )

        h = "%s" % str(hours) if hours >= 10 else "0%s" % str(hours)
        m = "%s" % str(mins) if mins >= 10 else "0%s" % str(mins)
        await message.answer(
            f"ура! в следующий раз я пришлю тебе идею для заметки уже в <b>{h}:{m}</b>)",
            parse_mode="HTML",
        )
        await state.clear()
    else:
        await message.answer(
            "пожалуйста, введи время в правильном формате, например 06:00 для утра или 18:00 для вечера"
        )


# --- хэндлер на команду /change_timezone ---
@dp.message(Command("change_timezone"))
async def choose_timezone(message: types.Message, state: FSMContext):
    utc_0 = InlineKeyboardButton(text="UTC +00:00", callback_data="UTC +00:00")
    utc_1 = InlineKeyboardButton(text="UTC +01:00", callback_data="UTC +01:00")
    utc_2 = InlineKeyboardButton(text="UTC +02:00", callback_data="UTC +02:00")
    utc_3 = InlineKeyboardButton(text="UTC +03:00 (Москва)", callback_data="UTC +03:00")
    utc_4 = InlineKeyboardButton(text="UTC +04:00", callback_data="UTC +04:00")
    utc_5 = InlineKeyboardButton(text="UTC +05:00", callback_data="UTC +05:00")
    utc_6 = InlineKeyboardButton(text="UTC +06:00", callback_data="UTC +06:00")
    utc_7 = InlineKeyboardButton(text="UTC +07:00", callback_data="UTC +07:00")
    utc_8 = InlineKeyboardButton(text="UTC +08:00", callback_data="UTC +08:00")
    utc_9 = InlineKeyboardButton(text="UTC +09:00", callback_data="UTC +09:00")
    utc_10 = InlineKeyboardButton(text="UTC +10:00", callback_data="UTC +10:00")
    utc_11 = InlineKeyboardButton(text="UTC +11:00", callback_data="UTC +11:00")
    utc_12 = InlineKeyboardButton(text="UTC +12:00", callback_data="UTC +12:00")

    rows = [
        [utc_0, utc_1, utc_2],
        [utc_3],
        [utc_4, utc_5, utc_6],
        [utc_7, utc_8, utc_9],
        [utc_10, utc_11, utc_12],
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(
        text="выбери часовой пояс, в котором ты находишься, чтобы я вовремя присылал сообщения!",
        reply_markup=keyboard,
    )
    await state.set_state(Form.timezone_changing)


# --- третий этап: подтверждаем новый часовой пояс и переустанавливаем функции по времени ---
async def change_timezone_confirmation(message: types.Message, timezone):
    chat_id = message.chat.id
    await message.answer(f"часовой пояс {timezone} установлен!\n\n")
    cur.execute(f"SELECT time_hours FROM users WHERE id = ?", (chat_id,))
    hours = cur.fetchone()[0]
    cur.execute(f"SELECT time_mins FROM users WHERE id = ?", (chat_id,))
    mins = cur.fetchone()[0]
    send_time = await timezone_converter(int(timezone[5:7]), hours)
    scheduler.reschedule_job(
        job_id=str(chat_id),
        trigger="cron",
        hour=send_time,
        minute=mins,
    )
    set_at_midnight = await timezone_converter(int(timezone[5:7]), 0)
    scheduler.reschedule_job(
        job_id='night' + str(chat_id),
        trigger="cron",
        hour=set_at_midnight,
        minute=0,
    )


# --- второй этап: получаем новый часовой пояс и обновляем базу ---
@dp.callback_query(Form.timezone_changing)
async def handle_timezone(callback_query: types.callback_query):
    chat_id = callback_query.from_user.id
    username = callback_query.from_user.username
    timezone = callback_query.data
    cur.execute("SELECT 1 FROM users WHERE id = ?", (chat_id,))
    if cur.fetchone():
        db.execute("UPDATE users SET timezone = ? WHERE id = ?", (timezone, chat_id))
    else:
        db.execute("INSERT INTO users VALUES (?, ?, ?)", (chat_id, username, timezone))
    db.commit()
    await callback_query.answer(":з")
    await change_timezone_confirmation(callback_query.message, timezone)


# --- хэндлер на команду /save ---
@dp.message(Command("save"))
async def cmd_save(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    cur.execute(f"SELECT save_status FROM users WHERE id = ?", (chat_id,))
    save_status = cur.fetchone()
    if save_status[0] == "saving":
        await state.set_state(Form.save)
        f = open("notes.txt", encoding="utf-8")
        note = f.readlines()
        cur.execute(f"SELECT prompt_num FROM users WHERE id = ?", (chat_id,))
        number = cur.fetchone()
        current_prompt = note[number[0]]
        await message.answer(
            f"ура! ты хочешь написать заметку о сегодняшнем дне! давай я напомню тебе мою идею:\n<b>{current_prompt}</b>\n\n"
            "оставь заметку отдельным сообщением. ты можешь отправить только одно сообщение!",
            parse_mode="HTML",
        )
    elif save_status[0] == "waiting":
        await message.answer(
            "сегодня ты уже не можешь написать заметку :( приходи завтра!"
        )
    elif save_status[0] == "sending":
        await message.answer(
            "пожалуйста, дождись пока я отправлю тебе идею для заметки или измени время в аккаунте)"
        )
    elif save_status[0] == "pause":
        await message.answer(
            "пока у тебя остановлена функция отправки идеи, ты не можешь сохранять новые заметик :(\n\n"
            "если ты хочешь её включить, нажми /resume"
        )


# --- второй этап: получаем заметку, обновляем обе базы ---
@dp.message(Form.save)
async def save_prompt(message: types.Message, state: FSMContext):
    await state.update_data(save=message.text)
    f = open("notes.txt", encoding="utf-8")
    chat_id = message.chat.id
    note = f.readlines()
    cur.execute(f"SELECT prompt_num FROM users WHERE id = ?", (chat_id,))
    number = cur.fetchone()
    current_prompt = note[number[0]]
    chat_id = message.chat.id
    user_response = message.text
    current_time = datetime.now().strftime("%d-%m")

    await message.answer(
        "отлично! твоя заметка сохранена! "
        "приходи завтра, чтобы снова оставить заметку :)\n\n"
        "а чтобы проверить баланс, нажми /account"
    )

    # --- вспоминаем был ли вопрос раньше ---
    cucur.execute(
        f"SELECT response, date FROM saved_prompts WHERE id = ? AND prompt = ?",
        (
            chat_id,
            current_prompt,
        ),
    )
    repeat_response = cucur.fetchone()
    months = {
        "01": "января",
        "02": "февраля",
        "03": "марта",
        "04": "апреля",
        "05": "мая",
        "06": "июня",
        "07": "июля",
        "08": "августа",
        "09": "сентября",
        "10": "октября",
        "11": "ноября",
        "12": "декабря",
    }
    if repeat_response:
        d, m = repeat_response[1].split("-")
        await message.answer(
            f"кстати, этот вопрос уже попадался раньше, помнишь? "
            f"вот, какой был ответ у тебя был {d} {months[m]}:\n\n"
            f"<b>{repeat_response[0]}</b>",
            parse_mode="HTML",
        )

    # --- сохраняем новый ответ в базе ---
    cucur.execute(
        """
                INSERT OR REPLACE INTO saved_prompts 
                (id, prompt, response, date)
                VALUES (?, ?, ?, ?)
            """,
        (chat_id, current_prompt, user_response, current_time),
    )
    prdb.commit()
    await state.clear()

    # --- обновляем информацию в базе пользователей ---
    db.execute(f"UPDATE users SET save_status = ? WHERE id = ?", ("waiting", chat_id))
    cur.execute(f"SELECT points FROM users WHERE id = ?", (chat_id,))
    points = cur.fetchone()
    cur.execute(f"SELECT strike FROM users WHERE id = ?", (chat_id,))
    strike = cur.fetchone()
    if strike[0] > 6:
        db.execute(
            f"UPDATE users SET points = ? WHERE id = ?", (points[0] + 3, chat_id)
        )
    else:
        db.execute(
            f"UPDATE users SET points = ? WHERE id = ?", (points[0] + 2, chat_id)
        )
    db.execute(f"UPDATE users SET strike = ? WHERE id = ?", (strike[0] + 1, chat_id))
    db.commit()


# --- хэндлер на команду /pause ---
@dp.message(Command("pause"))
async def cmd_pause(message: types.Message, state: FSMContext) -> None:
    cur.execute(f"SELECT save_status FROM users WHERE id = ?", (message.chat.id,))
    if cur.fetchone()[0] != "pause":
        ok = InlineKeyboardButton(text="ок", callback_data="ок")
        cancel = InlineKeyboardButton(text="отмена", callback_data="отмена")
        row = [[ok, cancel]]
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=row)
        await state.set_state(Form.set_pause)
        await message.answer(
            text=f"когда функция отправки идей будет остановлена, я сниму с твоего баланса 3 балла и обнулю твой страйк, "
                 f"чтобы всё было честно :) хорошо?", reply_markup=keyboard
        )
    else:
        await message.answer(
            "ой, кажется, функция отправки идей для заметок уже остановлена. "
            "если ты хочешь снова включить её, нажми /resume"
        )


# --- третий этап: останавливаем и удаляем функции по расписанию ---
async def pause_approvement(message: types.Message, answer):
    if answer == "отмена":
        await message.answer(text=f"ладно, тогда я продолжу присылать тебе идеи!")
    elif answer == "ок":
        scheduler.pause_job(str(message.chat.id))
        if not scheduler.get_job('fine' + str(message.chat.id)):
            scheduler.remove_job('fine' + str(message.chat.id))
            scheduler.remove_job('alert' + str(message.chat.id))
        cur.execute(f"SELECT points FROM users WHERE id = ?", (message.chat.id,))
        points = cur.fetchone()[0]
        db.execute("UPDATE users SET points = ? WHERE id = ?",(points - 3, message.chat.id))
        db.execute("UPDATE users SET strike = ? WHERE id = ?",(0, message.chat.id))
        db.execute(f"UPDATE users SET save_status = ? WHERE id = ?", ("pause", message.chat.id))
        db.commit()
        await message.answer("функция остановлена) "
                             "когда снова захочешь получать от меня идеи для заметок, нажми /resume")


# --- второй этап: обрабатываем ответ ---
@dp.callback_query(Form.set_pause)
async def set_pause(callback_query: types.callback_query, state: FSMContext):
    await callback_query.answer(":з")
    await callback_query.message.edit_reply_markup(reply_markup=None)
    answer = callback_query.data
    await pause_approvement(callback_query.message, answer)
    await state.clear()


# --- хэндлер на команду /resume ---
@dp.message(Command("resume"))
async def cmd_resume(message: types.Message, state: FSMContext) -> None:
    cur.execute(f"SELECT save_status FROM users WHERE id = ?", (message.chat.id,))
    if cur.fetchone()[0] == "pause":
        yes = InlineKeyboardButton(text="да", callback_data="да")
        no = InlineKeyboardButton(text="нет", callback_data="нет")
        row = [[yes, no]]
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=row)
        await state.set_state(Form.set_resume)
        await message.answer(
            text=f"ты хочешь снова получать от меня идеи для заметок?", reply_markup=keyboard
        )
    else:
        await message.answer(
            f"ой, кажется, функция отправки идей для заметок уже включена. "
            f"если ты хочешь отключить её, нажми /pause)",
            parse_mode="HTML",
        )


# --- третий этап: включаем функции по расписанию ---
async def resume_approvement(message: types.Message, answer):
    if answer == "нет":
        await message.answer(text=f"пиши, когда захочешь снова получать от меня идеи!")

    elif answer == "да":
        scheduler.resume_job(str(message.chat.id))
        db.execute(
            f"UPDATE users SET save_status = ? WHERE id = ?",
            ("sending", message.chat.id),
        )
        db.commit()
        cur.execute(f"SELECT time_hours FROM users WHERE id = ?", (message.chat.id,))
        time_h = cur.fetchone()
        h = "%s" % str(time_h[0]) if time_h[0] >= 10 else "0%s" % str(time_h[0])
        cur.execute(f"SELECT time_mins FROM users WHERE id = ?", (message.chat.id,))
        time_m = cur.fetchone()
        m = "%s" % str(time_m[0]) if time_m[0] >= 10 else "0%s" % str(time_m[0])
        await message.answer(
            f"ура, я очень рад, что ты снова хочешь писать мне заметки! "
            f"я буду присылать тебе идеи каждый день в <b>{h}:{m}</b>, как и раньше)",
            parse_mode="HTML",
        )


# --- второй этап: обрабатываем ответ ---
@dp.callback_query(Form.set_resume)
async def set_resume(callback_query: types.callback_query, state: FSMContext):
    await callback_query.answer(":з")
    await callback_query.message.edit_reply_markup(reply_markup=None)
    answer = callback_query.data
    await resume_approvement(callback_query.message, answer)
    await state.clear()


# --- хэндлер на команду /shop ---
@dp.message(Command("shop"))
async def cmd_shop(message: types.Message, state: FSMContext) -> None:
    chat_id = message.chat.id
    cur.execute(f"SELECT functions FROM users WHERE id = ?", (chat_id,))
    functions_code = cur.fetchone()[0]
    functions_code = functions_code.replace("1", "0")
    db.execute(
        "UPDATE users SET functions = ? WHERE id = ?", (functions_code, chat_id)
    )
    db.commit()

    menu = []
    for key, value in function_dict.items():
        if functions_code[value["index"]] == "0":
            button = InlineKeyboardButton(
                text=f"{value['text']} - {value['price']}", callback_data=value["text"]
            )
            menu.append([button])

    menu_keyboard = types.InlineKeyboardMarkup(inline_keyboard=menu)
    await message.answer(
        text="рад видеть тебя в магазине функций! ниже - функции и их цена. "
             "нажми на ту, которую хочешь купить!",
        reply_markup=menu_keyboard,
    )
    await state.set_state(Form.handle_function)


# --- третий этап: подтверждение покупки ---
async def function_confirmation(message: types.Message, function):
    ok = InlineKeyboardButton(text="ок", callback_data="ок")
    cancel = InlineKeyboardButton(text="отмена", callback_data="отмена")
    row = [[ok, cancel]]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=row)
    await message.answer(
        text=f"ты выбрал {function}. подтверди покупку, нажав ок", reply_markup=keyboard
    )
    # --- запоминаем функцию, которую хотят купить ---
    chat_id = message.chat.id
    cur.execute(f"SELECT functions FROM users WHERE id = ?", (chat_id,))
    functions_code = cur.fetchone()[0]

    status_dict = {"мемы": f"{functions_code[0]}", "анекдоты": f"{functions_code[1]}", "цитаты": f"{functions_code[2]}",
                   "тестики": f"{functions_code[3]}", "музыка": f"{functions_code[4]}", f"{function}": "1"}

    new_code = f"{status_dict['мемы']}{status_dict['анекдоты']}{status_dict['цитаты']}{status_dict['тестики']}{status_dict['музыка']}"
    db.execute("UPDATE users SET functions = ? WHERE id = ?", (new_code, chat_id))
    db.commit()


# --- второй этап: обрабатываем ответ ---
@dp.callback_query(Form.handle_function)
async def handle_function(callback_query: types.callback_query, state: FSMContext):
    function = callback_query.data
    await callback_query.answer(":з")
    await callback_query.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.handle_answer)
    await function_confirmation(callback_query.message, function)


# --- пятый этап: (не) продаём функцию ---
async def purchase_approvement_confirmation(message: types.Message, answer):
    chat_id = message.chat.id
    cur.execute(f"SELECT functions FROM users WHERE id = ?", (chat_id,))
    functions_code = cur.fetchone()[0]

    if answer == "отмена":
        functions_code = functions_code.replace("1", "0")
        db.execute(
            "UPDATE users SET functions = ? WHERE id = ?", (functions_code, chat_id)
        )
        await message.answer(text=f"покупка отменена :)")

    elif answer == "ок":
        cur.execute(f"SELECT points FROM users WHERE id = ?", (chat_id,))
        points = cur.fetchone()[0]
        index = functions_code.find("1")

        for key, value in function_dict.items():
            if value["index"] == index:
                if points >= value["price"]:
                    db.execute(
                        "UPDATE users SET points = ? WHERE id = ?",
                        (points - value["price"], chat_id),
                    )
                    functions_code = functions_code.replace("1", "2")
                    db.execute(
                        "UPDATE users SET functions = ? WHERE id = ?",
                        (functions_code, chat_id),
                    )
                    await message.answer(
                        text=f"теперь тебе доступна функция <b>{value['text']}</b>. ты можешь воспользоваться ей один раз в день, "
                        f"нажав на команду <b>/{key}</b>",
                        parse_mode="HTML",
                    )
                elif points < value["price"]:
                    functions_code = functions_code.replace("1", "0")
                    await message.answer(
                        text=f"к сожалению, тебе пока не хватает баллов, чтобы купить эту функцию :(",
                        parse_mode="HTML",
                    )
    db.commit()


# --- четвёртый этап: обрабатываем ответ ---
@dp.callback_query(Form.handle_answer)
async def handle_answer(callback_query: types.callback_query, state: FSMContext):
    await callback_query.answer(":з")
    await callback_query.message.edit_reply_markup(reply_markup=None)
    answer = callback_query.data
    await purchase_approvement_confirmation(callback_query.message, answer)
    await state.clear()


# --- берём мем ---
def get_image():
    images = [x for x in os.listdir(r"fioklik_images")]
    return os.path.join(r"fioklik_images", random.choice(images))


# --- хэндлер на /meme ---
@dp.message(Command("meme"))
async def cmd_meme(message: types.Message):
    chat_id = message.chat.id
    cur.execute(f"SELECT functions FROM users WHERE id = ?", (chat_id,))
    functions_code = cur.fetchone()[0]
    if functions_code[function_dict["meme"]["index"]] == "2":
        image_path = get_image()
        if image_path:
            photo = FSInputFile(image_path)
            await message.answer_photo(photo, caption="картиночка для тебя :з")
            new_code = f'3{functions_code[1:]}'
            db.execute(f"UPDATE users SET functions = ? WHERE id = ?", (new_code, chat_id, ))
            db.commit()
    elif functions_code[function_dict["meme"]["index"]] == "3":
        await message.answer(
            text="ты уже получал мем сегодня :)"
        )
    else:
        await message.answer(
            text=f"у тебя пока нет этой функции( купи её в магазине с помощью /shop"
        )


# --- хэндлер на /anec ---
@dp.message(Command("anec"))
async def cmd_anec(message: types.Message):
    chat_id = message.chat.id
    cur.execute(f"SELECT functions FROM users WHERE id = ?", (chat_id,))
    functions_code = cur.fetchone()[0]
    if functions_code[function_dict['anec']['index']] == '2':
        f = open('anecdotes.txt', encoding='utf-8')
        anecs = f.readlines()
        anec = anecs[random.randrange(45)]
        await bot.send_message(chat_id, text=f"держи анекдот дня:\n\n<b>{anec}</b>", parse_mode="HTML",)
        new_code = f'{functions_code[0]}3{functions_code[2:]}'
        db.execute(f"UPDATE users SET functions = ? WHERE id = ?", (new_code, chat_id,))
        db.commit()
    elif functions_code[function_dict["anec"]["index"]] == "3":
        await message.answer(text="ты уже получал анекдот сегодня :)")
    else:
        await message.answer(text=f"у тебя пока нет этой функции( купи её в магазине с помощью /shop")


# --- хэндлер на /quote ---
@dp.message(Command("quote"))
async def cmd_quote(message: types.Message):
    chat_id = message.chat.id
    cur.execute(f"SELECT functions FROM users WHERE id = ?", (chat_id,))
    functions_code = cur.fetchone()[0]
    if functions_code[function_dict["quote"]["index"]] == "2":
        f = open("wolf.txt", encoding="utf-8")
        number = random.randrange(50)
        quotes = f.readlines()
        await bot.send_message(
            chat_id,
            text=f"цитата дня для тебя:\n\n<b>{quotes[number]}</b>\n"
                 f"и помни: вместе мы стая.",
            parse_mode="HTML",
        )
        new_code = f'{functions_code[:2]}3{functions_code[3:]}'
        db.execute(f"UPDATE users SET functions = ? WHERE id = ?", (new_code, chat_id,))
        db.commit()
    elif functions_code[function_dict["quote"]["index"]] == "3":
        await message.answer(
            text="ты уже получал цитату сегодня :)"
        )
    else:
        await message.answer(
            text=f"у тебя пока нет этой функции( купи её в магазине с помощью /shop"
        )


# --- берём тест ---
def get_test():
    tests = []
    with open ('tests.tsv', 'r', encoding='UTF-8') as tests_data:
        data = csv.reader(tests_data, delimiter='\t')
        for line in data:
            tests.append(line)
    return random.choice(tests)


# --- хэндлер на /test ---
@dp.message(Command("test"))
async def cmd_test(message: types.Message):
    chat_id = message.chat.id
    cur.execute(f"SELECT functions FROM users WHERE id = ?", (chat_id,))
    functions_code = cur.fetchone()[0]
    if functions_code[function_dict["test"]["index"]] == "2":
        test_path = get_test()
        if test_path:
            knopka = InlineKeyboardButton(text=f'{get_test()[0]}', url=f'{get_test()[1]}')
            knopki = [[knopka]]
            knopochka = types.InlineKeyboardMarkup(inline_keyboard=knopki)

            await message.answer(
                text='твой тестик на сегодня:',
                reply_markup=knopochka
            )

            new_code = f'{functions_code[:3]}3{functions_code[4]}'
            db.execute(f"UPDATE users SET functions = ? WHERE id = ?", (new_code, chat_id, ))
            db.commit()
    elif functions_code[function_dict["test"]["index"]] == "3":
        await message.answer(
            text="ты уже проходил тестик сегодня:)"
        )
    else:
        await message.answer(
            text=f"у тебя пока нет этой функции( купи её в магазине с помощью /shop"
        )


# --- берём музыку ---
def get_music():
    music = [y for y in os.listdir('music')]
    return os.path.join('music', random.choice(music))


# --- хэндлер на /music ---
@dp.message(Command("music"))
async def cmd_music(message: types.Message):
    chat_id = message.chat.id
    cur.execute(f"SELECT functions FROM users WHERE id = ?", (chat_id,))
    functions_code = cur.fetchone()[0]
    if functions_code[function_dict["music"]["index"]] == "2":
        music_path = get_music()
        if music_path:
            audio = FSInputFile(music_path)
            await message.answer_audio(audio, caption="музыка для тебя :з")
            new_code = f'{functions_code[:4]}3'
            db.execute(f"UPDATE users SET functions = ? WHERE id = ?", (new_code, chat_id,))
            db.commit()
    elif functions_code[function_dict["music"]["index"]] == "3":
        await message.answer(
            text="ты уже получал музыку от меня сегодня :)"
        )
    else:
        await message.answer(
            text=f"у тебя пока нет этой функции( купи её в магазине с помощью /shop"
        )


# --- хэндлер на /givemeatank ---
@dp.message(Command("givemeatank"))
async def cmd_givemeatank(message: types.Message):
    chat_id = message.chat.id
    db.execute("UPDATE users SET points = ? WHERE id = ?", (100, chat_id))
    db.execute("UPDATE users SET strike = ? WHERE id = ?", (7, chat_id))
    db.commit()


# --- обработка неизвестных сообщений ---
@dp.message(F.text)
async def cmd_dontknow(message: types.Message):
    await message.answer(
        "кажется, я тебя не понимаю( попробуй выбрать одну из доступных команд, нажав /commands"
    )


# --- запуск поллинга и расписания---
async def main() -> None:
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
