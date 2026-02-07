import asyncio
import csv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ------------------- Настройки -------------------
import os

TOKEN = os.getenv("TELEGRAM_TOKEN")
OWNER_ID = 5534388849 # твой числовой Telegram ID

# ------------------- Память бота -------------------
user_machine = {}         # какая машина у пользователя
user_last_action = {}     # для отзывов/оценок/тех. проблем
user_pending_issue = {}   # для "другая проблема"

# ------------------- Машины -------------------
machines = {
    "GRUSHA": "ГРУША",
    # добавляй новые машины, например "BT002": "КОРЗИНКА"
}

# ------------------- Кнопки -------------------
menu_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="☕ Оценить кофе", callback_data="rate_coffee")],
    [InlineKeyboardButton(text="⭐ Оценить сервис", callback_data="rate_service")],
    [InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data="leave_review")],
    [InlineKeyboardButton(text="🛠 Техническая проблема", callback_data="tech_issue")]
])

def rating_kb(prefix):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(i), callback_data=f"{prefix}_{i}") for i in range(1, 6)]
    ])

issue_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Закончилось вода", callback_data="issue_water")],
    [InlineKeyboardButton(text="Не отдал сдачу", callback_data="issue_change")],
    [InlineKeyboardButton(text="Не приготовил кофе", callback_data="issue_no_coffee")],
    [InlineKeyboardButton(text="Емкость с отходами переполнена", callback_data="issue_trash")],
    [InlineKeyboardButton(text="Другая проблема", callback_data="issue_other")]
])

# ------------------- CSV -------------------
def save_to_csv(user_id, machine_id, type_, value):
    with open("data.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([user_id, machine_id, type_, value])

# ------------------- Обработчики -------------------
async def start_handler(message: types.Message, command: CommandStart):
    machine_code = command.args if command.args else "unknown"
    machine_name = machines.get(machine_code, machine_code)
    user_machine[message.from_user.id] = machine_code
    await message.answer(f"Привет! Вы подключились к машине {machine_name}", reply_markup=menu_kb)

async def callback_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    machine_code = user_machine.get(user_id, "unknown")
    machine_name = machines.get(machine_code, machine_code)
    data = callback.data

    # Меню
    if data == "rate_coffee":
        await callback.message.answer(f"Оцените кофе на машине {machine_name} (1–5):", reply_markup=rating_kb("coffee"))
        user_last_action[user_id] = ("coffee", machine_code)
    elif data == "rate_service":
        await callback.message.answer(f"Оцените сервис на машине {machine_name} (1–5):", reply_markup=rating_kb("service"))
        user_last_action[user_id] = ("service", machine_code)
    elif data == "leave_review":
        await callback.message.answer(f"Напишите ваш отзыв для машины {machine_name}:")
        user_last_action[user_id] = ("review", machine_code)
    elif data == "tech_issue":
        await callback.message.answer(f"Выберите проблему для машины {machine_name}:", reply_markup=issue_kb)
        user_last_action[user_id] = ("issue", machine_code)

    # Оценки через кнопки 1–5
    elif data.startswith("coffee_") or data.startswith("service_"):
        type_ = data.split("_")[0]
        value = data.split("_")[1]
        save_to_csv(user_id, machine_code, type_, value)
        await callback.message.answer(f"Спасибо! Ваш рейтинг {type_} = {value} ✅", reply_markup=menu_kb)
        user_last_action.pop(user_id, None)

    # Технические проблемы
    elif data.startswith("issue_"):
        issue_type = {
            "issue_water": "Закончилось вода",
            "issue_change": "Не отдал сдачу",
            "issue_no_coffee": "Не приготовил кофе",
            "issue_trash": "Емкость с отходами переполнена",
            "issue_other": "Другая проблема"
        }.get(data, "Другая проблема")

        if issue_type == "Другая проблема":
            await callback.message.answer("Опишите проблему:")
            user_pending_issue[user_id] = machine_code
        else:
            save_to_csv(user_id, machine_code, "issue", issue_type)
            await callback.message.answer(f"Спасибо! Проблема '{issue_type}' сохранена ✅", reply_markup=menu_kb)
            await callback.bot.send_message(OWNER_ID, f"Проблема с машиной {machine_name} от пользователя {user_id}:\n{issue_type}")

    await callback.answer()  # убираем "часики" на кнопке

async def message_handler(message: types.Message):
    user_id = message.from_user.id

    if user_id in user_last_action:
        type_, machine_code = user_last_action[user_id]
        machine_name = machines.get(machine_code, machine_code)

        if type_ == "review":
            save_to_csv(user_id, machine_code, type_, message.text)
            await message.answer("Спасибо! Ваш отзыв сохранён ✅", reply_markup=menu_kb)
        elif type_ == "issue" and user_id in user_pending_issue:
            save_to_csv(user_id, machine_code, "issue", message.text)
            await message.answer("Спасибо! Проблема сохранена ✅", reply_markup=menu_kb)
            await message.bot.send_message(OWNER_ID, f"Проблема с машиной {machine_name} от пользователя {user_id}:\n{message.text}")
            user_pending_issue.pop(user_id)

        user_last_action.pop(user_id, None)
    else:
        await message.answer("Нажмите кнопку меню, чтобы выбрать действие.")

# ------------------- Запуск -------------------
async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.message.register(start_handler, CommandStart())
    dp.callback_query.register(callback_handler)
    dp.message.register(message_handler)
    print("Бот запускается…")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
import os
import asyncio

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
app = Flask(__name__)

@app.route("/", methods=["POST"])
def webhook():
    update = types.Update(**request.get_json())
    asyncio.run(dp.process_update(update))
    return "ok"

@app.route("/")
def home():
    return "Bot is alive!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
