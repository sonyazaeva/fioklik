def get_image():
    images = [x for x in os.listdir(r'C:\Users\sofiy\PycharmProjects\telegrambot\codes\images\photos')]

    return os.path.join(r'C:\Users\sofiy\PycharmProjects\telegrambot\codes\images\photos', random.choice(images))

@dp.message(Command("fun")) # хэндлер на картиночки
async def cmd_fun(message: types.Message):
    image_path = get_image()
    if image_path:
        photo = FSInputFile(image_path)
        await message.answer_photo(photo, caption='картиночка для тебя :з')

  async def main() -> None: # весь этот блок контролирует новые апдейты в чате (чтобы все работало беспрерывно)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
