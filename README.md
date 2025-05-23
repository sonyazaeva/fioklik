# fioklikBot
### О проекте
Команда: Иван Дергаев, София Заева, Манушак Закарян, Мария Самус

Асинхронный telegram-бот для ежедневной рефлексии, который умеет отправлять разные забавы (мемы, анекдоты, цитаты, personality test’ы и музыку). Для открытия новых функций создана система очков за регулярную активность и магазин.

### Структура репозитория
**```bot.py``` - основной файл**

```requirements.txt``` - зависимости

```notes.txt``` - идеи для заметок

```anecdotes.txt``` - анекдоты

```wolf.txt``` - цитаты

```test.tsv``` - таблица с тестами и ссылками

```images/``` - папка с мемами

```music/``` - папка с музыкой

### Подготовка и запуск проекта
1. Загрузите файлы из репозитория (bot.py и вспомогательные файлы) в одну директорию.
2. Установите зависимости из файла requirements.txt:
```
pip install -r requirements.txt
```
3. Впишите токен бота в соответсвующую строку файла bot.py:
```
BOT_TOKEN='токен_бота'
```

### Ссылки
Для написания бота использовались:
- [документация aiogram](https://docs.aiogram.dev/en/v3.20.0.post0/) (создание хэндлеров, кнопок, обработка состояний)
- [обзор и туториал на aiogram](https://www.youtube.com/watch?v=pd-0G0MigUA) (пояснения к докуменатции)
- [гайд по работе с базами данных на sqlite3](https://habr.com/ru/amp/publications/754400/) (для создания баз:))
-  [туториалы с канала Сурена Хореняна](https://youtube.com/@surenkhorenyan?si=vQQSQpagEgfpKUAH) (для доработки бота и дополнительной информации о написании бота на aiogram)
-  [документация scheduler'а](https://apscheduler.readthedocs.io/en/stable/modules/schedulers/base.html#apscheduler.schedulers.base.BaseScheduler.scheduled_job)
