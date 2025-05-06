db = sql.connect('users.db')  # функция создаем датабазу
cur = db.cursor()
async def db_database():
    cur.execute('CREATE TABLE IF NOT EXISTS users ('
                'id INTEGER PRIMARY KEY AUTOINCREMENT, '
                'name TEXT, '
                'points INTEGER DEFAULT 0)')
    db.commit()


@dp.message(Command("create")) #хэндлер на команду /create для создания аккаунта
async def cmd_create(message: types.Message, state: FSMContext):
    await db_database()  # активируем создание датабазы, если ее нет
    await state.set_state(Form.name)
    await message.answer("давай познакомимся! скажи, как к тебе обращаться?")

@dp.message(Form.name)  # второй этап регистрации (ждем когда придет имя)
async def cmd_pocessname(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(f"ура! будем знакомы, {message.text}!")  # тут знакомство заканчивается
    username = message.text
    await state.set_state(Form.name_added)  # эта строка ограничивает ввод имени только одним сообщением после
    db.execute(f'INSERT INTO users VALUES ("{message.chat.id}", "{username}", "{0}")')
    db.commit()  # регистрация закончилась
