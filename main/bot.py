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

# --- привязываем код к тг ---
logging.basicConfig(level=logging.INFO)  # базовые настройки для связи кода с тг
TOKEN = "8165202855:AAEEzi3GheY3K26A4YEQ1Wpk-TQQDfBB_Bs"
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# --- переменные для курсора и связи с датабазами ---
db = sql.connect('users.db')
cur = db.cursor()
prdb = sql.connect('saved_prompts.db')
cucur = prdb.cursor()
listik = []

# --- создаем датабазу users.db ---
cur.execute('CREATE TABLE IF NOT EXISTS users ('
                'id INTEGER PRIMARY KEY, '
                'name TEXT, '
                'points INTEGER DEFAULT 0, '
                'timezone TEXT DEFAULT NONE, '
                'time_hours INTEGER DEFAULT 0, '
                'time_mins INTEGER DEFAULT 0, '
                'save_status TEXT, '
                'strike INTEGER DEFAULT 0)'
                )
db.commit()

# --- создаем датабазу saved_prompts.db ---
cucur.execute('CREATE TABLE IF NOT EXISTS saved_prompts ('
                  'id INTEGER PRIMARY KEY, '
                  'prompt TEXT, '
                  'response TEXT, '
                  'date DATETIME)'
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
    save_added = State()
    change_name = State()
    change_name_added = State()
    change_time = State()
    change_time_added = State()
    timezone_changing = State()


# --- хэндлер на /cancel ---
@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer('все действия отменены :)')
  

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
        await message.answer(f'<b>{username[0]}</b>, как здорово, что ты тут!', parse_mode='HTML')
    else:  # если пользователь не зарегистрирован
        await state.set_state(Form.started)
        await message.answer('привет! я Фёклик — друг, который всегда найдёт, чем тебя занять :)\n\n'
                             'каждый день в определенное время я буду присылать тебе идеи для заметок. '
                             'за каждую заметку ты будешь получать баллы, с помощью которых сможешь открыть новые функции. '
                             'например, я буду делиться с тобой мемами, анекдотами и многим-многим другим, что сделает твой день веселее и интереснее.\n\n'
                             'я бы хотел, чтобы наше общение было более постоянным, поэтому если ты будешь забывать писать заметки, то будешь терять баллы :(\n\n'
                             'поэтому, пожалуйста, не забывай открывать чатик и писать что-то. не бойся, я напомню тебе о потере страйка!\n\n'
                             'а сейчас давай познакомимся! скажи, как к тебе обращаться?')


# --- второй этап: получаем имя и добавляем пользователя в базу, настраиваем таймзону ---
@dp.message(Form.started)
async def cmd_processname(message: types.Message, state: FSMContext) -> None:
    await state.set_state(Form.name_set)
    chat_id = message.chat.id
    username = message.text
    db.execute(f'INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (chat_id, username, 0, 'UTC +03:00', 0, 0, 'sending', 0))
    await message.answer(f'ура! будем знакомы, <b>{username}</b>! '
                         f'если что-то пошло не так, не переживай: ты сможешь изменить имя позже :)', parse_mode='HTML')

    # --- выбираем таймзону ---
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
    other = InlineKeyboardButton(text='другое!', callback_data='other')

    rows = [[utc_2, utc_3, utc_4],
            [utc_5, utc_6, utc_7],
            [utc_8, utc_9, utc_10],
            [utc_11, utc_12, other]]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(text='чтобы я вовремя присылал сообщения, выбери свой часовой пояс!\n\n'
                              'если ты находишься не в России, то сможешь установить другой часовой пояс потом :)',
                         reply_markup=keyboard)

# --- обрабатываем таймзону ---
@dp.callback_query(Form.name_set)
async def handle_timezone(callback_query: types.callback_query, state: FSMContext):
    chat_id = callback_query.from_user.id
    callback = callback_query.data
    if callback == 'other':
        timezone = 'UTC +03:00'
    else:
        timezone = callback
    cur.execute("UPDATE users SET timezone = ? WHERE id = ?", (timezone, chat_id))
    await callback_query.answer(':з')
    await timezone_confirmation(callback_query.message, callback)
    await state.set_state(Form.timezone_set)

# --- подтверждаем выбор часового пояса ---
async def timezone_confirmation(message: types.Message, callback) -> None:
    if callback == 'other':
        await message.answer(f'часовой пояс пока не выбран, но я установил <b>UTC +03:00</b> по умолчанию. '
                             f'ты всегда сможешь изменить его в настройках аккаунта.\n\n'
                             f'а сейчас, пожалуйста, напиши, в какое время тебе будет удобно получать идеи для заметок? '
                             f'укажи его в формате 00:00. например, 06:00 для утра или 18:00 для вечера',
                             parse_mode='HTML')
    else:
        await message.answer(f'часовой пояс <b>{callback}</b> выбран! '
                             f'ты всегда сможешь изменить его в настройках аккаунта.\n\n'
                             f'а сейчас, пожалуйста, напиши, в какое время тебе будет удобно получать идеи для заметок? '
                             f'укажи его в формате 00:00. например, 06:00 для утра или 18:00 для вечера',
                             parse_mode='HTML')


# --- третий этап регистрации: получаем время ---
@dp.message(Form.timezone_set)
async def cmd_processtime(message: types.Message, state: FSMContext) -> None:
    # --- проверяем соответствие формата введенного времени ---
    try:
        hours, mins = map(int, message.text.split(':'))
    except ValueError:
        await message.answer("пожалуйста, введи время в правильном формате, например 06:00 для утра или 18:00 для вечера")

    chat_id = message.chat.id
    await state.update_data(time_hours=hours, time_mins=mins)

    if 0 <= hours < 24 and 0 <= mins < 60:
        db.execute(f'UPDATE users SET time_hours = ? WHERE id = ?', (hours, chat_id))
        db.execute(f'UPDATE users SET time_mins = ? WHERE id = ?', (mins, chat_id))
        db.commit()
    else:
        await message.answer("пожалуйста, введи время в правильном формате, например 06:00 для утра или 18:00 для вечера")

    cur.execute(f"SELECT timezone FROM users WHERE id = ?", (chat_id,))
    timezone = cur.fetchone()[0]
    scheduler.add_job(send_prompt, trigger="cron", hour=int(timezone[5:7]) + hours - 3, minute=mins,
                      id=str(chat_id), kwargs={"bot": bot, "chat_id": chat_id}, )

    await message.answer(f'отлично, теперь каждый день в <b>{message.text}</b> я буду присылать тебе идею для заметки о прошедшем дне) '
                         f'не забывай отвечать мне, чтобы зарабатывать очки для открытия новых функций!\n\n'
                         f'рад, что мы познакомились! вот, что я теперь о тебе знаю:', parse_mode='HTML')
    await cmd_account(message)
    await cmd_commands(message)
    await cmd_info(message)
    await state.set_state(Form.time_set)


# --- хэндлер на команду /account ---
@dp.message(Command('account'))
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
    if acc:
        await message.answer(
            f"твой юзернейм: <b>{acc[0]}</b>\n"
            f"твой баланс: <b>{points[0]}</b>\n"
            f"твой страйк: <b>{strike[0]}</b>\n"
            f"выбранное время: <b>{h}:{m}</b>\n"
            f"часовой пояс: <b>{tmz[0]}</b>\n\n"
            f"если ты хочешь что-то изменить, нажми /edit_account",
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


# --- отправка идеи для заметки в выбранное время ---
async def send_prompt(bot: Bot, chat_id: int):
    cur.execute(f"SELECT save_status FROM users WHERE id = ?", (chat_id,))
    save_status = cur.fetchone()
    if save_status[0] == 'sending':
        f = open('notes.txt', encoding='utf-8')
        number = random.randrange(200)
        listik.append(number)
        note = f.readlines()
        current_prompt = note[number]
        await bot.send_message(chat_id, text=f"вот тебе идея для заметки:\n<b>{current_prompt}</b>\n\n"
                                             f"чтобы сохранить свой ответ, воспользуйся командой /save", parse_mode='HTML')
        db.execute(f'UPDATE users SET save_status = ? WHERE id = ?', ('saving', chat_id))
        db.commit()
        scheduler.add_job(send_alert, trigger="date", run_date=datetime.now() + timedelta(hours=22) - timedelta(seconds=5),
                          kwargs={"bot": bot, "chat_id": chat_id}, )
        scheduler.add_job(fine, trigger="date", run_date=datetime.now() + timedelta(days=1),
                          kwargs={"bot": bot, "chat_id": chat_id}, )


# --- хэндлер на команду /save ---
@dp.message(Command('save'))
async def cmd_save(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    cur.execute(f"SELECT save_status FROM users WHERE id = ?", (chat_id,))
    save_status = cur.fetchone()
    if save_status[0] == 'saving':
        await state.set_state(Form.save)
        f = open('notes.txt', encoding='utf-8')
        note = f.readlines()
        current_prompt = note[listik[0]]
        await message.answer(f"ура! ты хочешь написать заметку о сегодняшнем дне! давай я напомню тебе мою идею: <b>{current_prompt}</b>\n\n"
                             "оставь заметку отдельным сообщением. ты можешь отправить только одно сообщение!", parse_mode='HTML')
    else:
        await message.answer("кажется, сегодня ты уже написал заметку :( приходи завтра!")

@dp.message(Form.save)
async def save_prompt(message: types.Message, state: FSMContext):
    await state.update_data(save=message.text)
    f = open('notes.txt', encoding='utf-8')
    note = f.readlines()
    current_prompt = note[listik[0]]
    chat_id = message.chat.id
    user_response = message.text
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    cucur.execute('''
                INSERT OR REPLACE INTO saved_prompts 
                (id, prompt, response, date)
                VALUES (?, ?, ?, ?)
            ''', (chat_id, current_prompt, user_response, current_time))
    prdb.commit()
    await state.clear()

    db.execute(f'UPDATE users SET save_status = ? WHERE id = ?', ('waiting', chat_id))
    cur.execute(f"SELECT points FROM users WHERE id = ?", (chat_id,))
    points = cur.fetchone()
    if points[0] > 6:
        db.execute(f'UPDATE users SET points = ? WHERE id = ?', (points[0] + 3, chat_id))
    else:
        db.execute(f'UPDATE users SET points = ? WHERE id = ?', (points[0] + 2, chat_id))
    cur.execute(f"SELECT strike FROM users WHERE id = ?", (chat_id,))
    strike = cur.fetchone()
    db.execute(f'UPDATE users SET strike = ? WHERE id = ?', (strike[0] + 1, chat_id))
    db.commit()

    await message.answer("отлично! твоя заметка сохранена! "
                         'приходи завтра, чтобы снова оставить заметку :)\n\n'
                         'а чтобы проверить баланс, нажми /account')
    await state.set_state(Form.save_added)

# --- отправка предупреждения об истечении времени ---
async def send_alert(bot: Bot, chat_id: int):
    cur.execute(f"SELECT save_status FROM users WHERE id = ?", (chat_id,))
    save_status = cur.fetchone()
    if save_status[0] == 'saving':
        await bot.send_message(chat_id, text=f"у тебя осталось два часа, чтобы написать заметку!", parse_mode='HTML')

# --- штраф при отсутствии заметки к окончанию времени ---
async def fine(bot: Bot, chat_id: int):
    cur.execute(f"SELECT save_status FROM users WHERE id = ?", (chat_id,))
    save_status = cur.fetchone()
    if save_status[0] == 'saving':
        cur.execute(f"SELECT points FROM users WHERE id = ?", (chat_id,))
        points = cur.fetchone()
        if points[0] != 0:
            db.execute(f'UPDATE users SET points = ? WHERE id = ?', (points[0] - 1, chat_id))
            db.execute(f'UPDATE users SET strike = ? WHERE id = ?', (0, chat_id))
            await bot.send_message(chat_id, text=f"сегодня я не получил заметку от тебя, поэтому ты теряешь один балл и свой страйк :(", parse_mode='HTML')
        else:
            await bot.send_message(chat_id, text=f"мне грустно без тебя :(", parse_mode='HTML')
    db.execute(f'UPDATE users SET save_status = ? WHERE id = ?', ('sending', chat_id))
    db.commit()


# --- хэндлер на команду /change_name ---
@dp.message(Command("change_name"))
async def cmd_change_name(message: types.Message, state: FSMContext):
    def checker():
        cur.execute("SELECT COUNT(*) FROM users WHERE id = ?", (chat_id,))
        return cur.fetchone()[0] > 0
    chat_id = message.chat.id
    if not checker():
        await message.answer('кажется, у тебя пока нет аккаунта :(\n\n'
                             '<b>чтобы создать его нажми /start</b>', parse_mode='HTML')
    else:
        await state.set_state(Form.change_name)
        await message.answer("ты можешь выбрать новое имя!")

# --- второй этап: получаем новое имя и обновляем базу ---
@dp.message(Form.change_name)
async def cmd_processchangedname(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    chat_id = message.chat.id
    username = message.text
    db.execute(f'UPDATE users SET name = ? WHERE id = ?', (username, chat_id))
    db.commit()
    await message.answer(f"ура! твоё новое имя: <b>{username}</b>", parse_mode='HTML')
    await state.set_state(Form.change_name_added)


# --- хэндлер на команду /change_time ---
@dp.message(Command("change_time"))
async def cmd_change_time(message: types.Message, state: FSMContext):
    def checker():
        cur.execute("SELECT COUNT(*) FROM users WHERE id = ?", (chat_id,))
        return cur.fetchone()[0] > 0
    chat_id = message.chat.id
    if not checker():
        await message.answer('кажется, у тебя пока нет аккаунта :(\n\n'
                             '<b>чтобы создать его нажми /start</b>', parse_mode='HTML')
    else:
        await state.set_state(Form.change_time)
        await message.answer("ты можешь выбрать другое время! пожалуйста, введи его в формате 00:00, "
                             "например, 06:00 для утра или 18:00 для вечера")

# --- второй этап: получаем новое время и обновляем базу ---
@dp.message(Form.change_time)
async def cmd_processchangedtime(message: types.Message, state: FSMContext):
    chat_id = message.chat.id

    # --- проверяем соответствие формата введенного времени ---
    try:
        hours, mins = map(int, message.text.split(':'))
        await state.update_data(time_hours=hours, time_mins=mins)
    except ValueError:
        await message.answer("пожалуйста, введи время в правильном формате, например 06:00 для утра или 18:00 для вечера")

    if 0 <= hours < 24 and 0 <= mins < 60:
        db.execute(f'UPDATE users SET time_hours = ? WHERE id = ?', (hours, chat_id))
        db.execute(f'UPDATE users SET time_mins = ? WHERE id = ?', (mins, chat_id))
        db.commit()
    else:
        await message.answer("пожалуйста, введи время в правильном формате, например 06:00 для утра или 18:00 для вечера")

    cur.execute(f"SELECT timezone FROM users WHERE id = ?", (chat_id,))
    timezone = cur.fetchone()[0]
    scheduler.reschedule_job(job_id=str(chat_id), trigger="cron", hour=int(timezone[5:7]) + hours - 3, minute=mins)

    await message.answer(f"ура! в следующий раз я пришлю тебе идею для заметки уже в <b>{message.text}</b>)", parse_mode='HTML')
    await state.set_state(Form.change_time_added)


# --- хэндлер на команду change_timezone ---
@dp.message(Command('change_timezone'))
async def choose_timezone(message: types.Message, state: FSMContext):
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
    other = InlineKeyboardButton(text='другое!', callback_data='other')

    rows = [
        [utc_2, utc_3, utc_4],
        [utc_5, utc_6, utc_7],
        [utc_8, utc_9, utc_10],
        [utc_11, utc_12, other],
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(text='выбери часовой пояс, в котором ты находишься, чтобы я вовремя присылал сообщения!',
                         reply_markup=keyboard)
    await state.set_state(Form.timezone_changing)


async def change_timezone_confirmation(message: types.Message, timezone):
    chat_id = message.chat.id
    if timezone != 'other':
        await message.answer(f'часовой пояс {timezone} установлен!\n\n')
        cur.execute(f"SELECT time_hours FROM users WHERE id = ?", (chat_id,))
        hours = cur.fetchone()[0]
        cur.execute(f"SELECT time_mins FROM users WHERE id = ?", (chat_id,))
        mins = cur.fetchone()[0]
        scheduler.reschedule_job(job_id=str(chat_id), trigger="cron", hour=int(timezone[5:7]) + hours - 3, minute=mins)
    else:
        await choose_alt_timezone(message)


@dp.callback_query(Form.timezone_changing)
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
    await change_timezone_confirmation(callback_query.message, timezone)


# --- альтернативные зоны ---
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
    utc_neg3 = InlineKeyboardButton(text='UTC -03:00', callback_data='UTC -03:00')
    utc_neg2 = InlineKeyboardButton(text='UTC -02:00', callback_data='UTC -02:00')
    utc_neg1 = InlineKeyboardButton(text='UTC -01:00', callback_data='UTC -01:00')
    utc_0 = InlineKeyboardButton(text='UTC +00:00', callback_data='UTC +00:00')
    utc_1 = InlineKeyboardButton(text='UTC +01:00', callback_data='UTC +01:00')
    utc_13 = InlineKeyboardButton(text='UTC +13:00', callback_data='UTC +13:00')
    utc_14 = InlineKeyboardButton(text='UTC +14:00', callback_data='UTC +14:00')

    lines = [
        [utc_neg12, utc_neg11, utc_neg10],
        [utc_neg9, utc_neg8, utc_neg7],
        [utc_neg6, utc_neg5, utc_neg4],
        [utc_neg3, utc_neg2, utc_neg1],
        [utc_neg2, utc_neg1, utc_0],
        [utc_1, utc_13, utc_14]
    ]
    alt_keyboard = types.InlineKeyboardMarkup(inline_keyboard=lines)
    await message.answer(text='ого! а ты совсем далеко! вот другие часовые пояса, выбирай свой:',
                         reply_markup=alt_keyboard)


async def alt_timezone_confirmation(message: types.Message, alt_timezone: str):
    await message.answer(f'часовой пояс {alt_timezone} установлен!\n\n')


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

    cur.execute(f"SELECT time_hours FROM users WHERE id = ?", (chat_id,))
    hours = cur.fetchone()[0]
    cur.execute(f"SELECT time_mins FROM users WHERE id = ?", (chat_id,))
    mins = cur.fetchone()[0]
    if alt_timezone[4] == '+':
        scheduler.reschedule_job(job_id=str(chat_id), trigger="cron", hour=int(alt_timezone[5:7]) + hours - 3, minute=mins)
    elif alt_timezone[4] == '-':
        scheduler.reschedule_job(job_id=str(chat_id), trigger="cron", hour=int(alt_timezone[5:7]) - hours - 3, minute=mins)

    await callback_query.answer(':з')
    await alt_timezone_confirmation(callback_query.message, alt_timezone)


# --- хэндлер на команду /commands ---
@dp.message(Command("commands"))
async def cmd_commands(message: types.Message):
    await message.answer(
        "давай расскажу о том, что я умею!\n\n"
        "<b>/account</b> — проверить свои имя, баланс и доступные функции или отредактировать аккаунт\n"
        "<b>/shop</b> — открыть магазин и купить какую-нибудь функцию (мне уже не терпится отправить тебе мем!) \n"
        "<b>/info</b> — узнать о том, как все устроено и как зарабатывать очки", parse_mode='HTML'
    )


# --- хэндлер на команду /info ---
@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    await message.answer(
        "<b>как тут все устроено?</b>\n\n"
        "каждый день в то время, которые ты установил при регистрации, я буду присылать тебе идею для заметки. "
        "чтобы оставить заметку, тебе нужно отправить команду /save. за неё ты будешь получать 2 балла.\n\n"
        "если каждый день в течение недели ты будешь оставлять заметки, то дальше каждая следующая будет приносить тебе целых 3 балла) "
        "правда если ты пропустишь один день, то у тебя снимется 1 балл и страйк обнулится... "
        "не бойся, я напомню тебе об этом за два часа до конца суток с момента отправки идеи :)\n\n"
        "если ты поймешь, что время, в которое я присылаю тебе идею, не самое удобное, "
        "то всегда сможешь изменить его в настройках аккаунта с помощью /change_time\n\n"
        "<b>зачем нужны баллы?</b>\n\n"
        "я могу отправлять не только идеи для заметок, но и другие штуки) "
        "чтобы открыть новую функцию, копи баллы и покупай в магазине с помощью /shop. "
        "открыв новую функцию, ты сможешь вызывать её один раз в день "
        "и получать какую-то прихолюху (мем, анекдот, тестик или волчью цитатку).\n\nвот так вот :)", parse_mode='HTML'
    )


# --- берем картиночки ---
def get_image():
    images = [x for x in os.listdir(r'fioklik_images')]
    return os.path.join(r'fioklik_images', random.choice(images))


# --- хэндлер на /fun ---
@dp.message(Command("fun"))
async def cmd_fun(message: types.Message):
    image_path = get_image()
    if image_path:
        photo = FSInputFile(image_path)
        await message.answer_photo(photo, caption='картиночка для тебя :з')


# --- обработка неизвестных сообщений ---
@dp.message(F.text)
async def cmd_dontknow(message: types.Message):
    await message.answer(
        'кажется, я тебя не понимаю( попробуй выбрать одну из доступных комманд, нажав /commands')


# --- запуск поллинга и расписания---
async def main() -> None:
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
