import os
import sys
import asyncio
import sqlite3
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums import ParseMode

print("=== Начало запуска бота ===")

# ------------------- Настройки -------------------
TOKEN = os.getenv("TELEGRAM_TOKEN")  # твой токен
OWNER_ID = 5534388849                # твой Telegram ID
DB_PATH = "bot_data.db"

print(f"TOKEN exists: {bool(TOKEN)}")
print(f"OWNER_ID: {OWNER_ID}")

if not TOKEN:
    print("ERROR: TELEGRAM_TOKEN не установлен!")
    sys.exit(1)

# ------------------- Память бота -------------------
user_machine = {}
user_last_action = {}
user_pending_issue = {}

# ------------------- Машины -------------------
machines = {
    "GRUSHA": "ГРУША",
}

# ------------------- Кнопки -------------------
print("Создание клавиатур...")
try:
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
    print("Клавиатуры созданы успешно")
except Exception as e:
    print(f"ERROR при создании клавиатур: {e}")
    sys.exit(1)

# ------------------- SQLite -------------------
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                machine_id TEXT,
                type TEXT,
                value TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        print(f"База данных инициализирована: {DB_PATH}")
    except Exception as e:
        print(f"ERROR при инициализации БД: {e}")

def save_record(user_id, machine_id, type_, value):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO records (user_id, machine_id, type, value) VALUES (?, ?, ?, ?)",
            (user_id, machine_id, type_, value)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка при записи в DB: {e}")

# ------------------- Хэндлеры -------------------
async def start_handler(message: types.Message):
    try:
        args = message.text.split()
        machine_code = args[1] if len(args) > 1 else "unknown"
        machine_name = machines.get(machine_code, machine_code)
        user_machine[message.from_user.id] = machine_code
        await message.answer(f"Привет! Вы подключились к машине {machine_name}", reply_markup=menu_kb)
    except Exception as e:
        print(f"ERROR в start_handler: {e}")

async def callback_handler(callback: types.CallbackQuery, bot: Bot):
    try:
        user_id = callback.from_user.id
        machine_code = user_machine.get(user_id, "unknown")
        machine_name = machines.get(machine_code, machine_code)
        data = callback.data

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

        elif data.startswith("coffee_") or data.startswith("service_"):
            type_, value = data.split("_")
            save_record(user_id, machine_code, type_, value)
            await callback.message.answer(f"Спасибо! Ваш рейтинг {type_} = {value} ✅", reply_markup=menu_kb)
            user_last_action.pop(user_id, None)

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
                save_record(user_id, machine_code, "issue", issue_type)
                await callback.message.answer(f"Спасибо! Проблема '{issue_type}' сохранена ✅", reply_markup=menu_kb)
                await bot.send_message(OWNER_ID, f"Проблема с машиной {machine_name} от пользователя {user_id}:\n{issue_type}")

        await callback.answer()
    except Exception as e:
        print(f"ERROR в callback_handler: {e}")

async def message_handler(message: types.Message, bot: Bot):
    try:
        user_id = message.from_user.id

        if user_id in user_last_action:
            type_, machine_code = user_last_action[user_id]
            machine_name = machines.get(machine_code, machine_code)

            if type_ == "review":
                save_record(user_id, machine_code, type_, message.text)
                await message.answer("Спасибо! Ваш отзыв сохранён ✅", reply_markup=menu_kb)
            elif type_ == "issue" and user_id in user_pending_issue:
                save_record(user_id, machine_code, "issue", message.text)
                await message.answer("Спасибо! Проблема сохранена ✅", reply_markup=menu_kb)
                await bot.send_message(OWNER_ID, f"Проблема с машиной {machine_name} от пользователя {user_id}:\n{message.text}")
                user_pending_issue.pop(user_id, None)

            user_last_action.pop(user_id, None)
        else:
            await message.answer("Нажмите кнопку меню, чтобы выбрать действие.")
    except Exception as e:
        print(f"ERROR в message_handler: {e}")

# ------------------- Bot и Dispatcher -------------------
print("Инициализация бота и диспетчера...")
try:
    bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    
    dp.message.register(start_handler, Command("start"))
    dp.callback_query.register(callback_handler)
    dp.message.register(message_handler)
    
    print("Бот и диспетчер инициализированы успешно")
except Exception as e:
    print(f"ERROR при инициализации бота/диспетчера: {e}")
    sys.exit(1)

# ------------------- Flask и Webhook -------------------
app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "POST":
        try:
            update = types.Update(**request.get_json())
            asyncio.run(dp.feed_webhook_update(bot, update))
        except Exception as e:
            print(f"Ошибка при обработке апдейта: {e}")
        return "ok", 200
    else:
        return "Bot is alive!", 200

@app.route("/health", methods=["GET"])
def health_check():
    return {"status": "ok", "bot": "running"}, 200

# ------------------- Main -------------------
if __name__ == "__main__":
    print("=== Запуск Flask приложения ===")
    
    # Инициализируем базу данных
    init_db()
    
    # Получаем порт из переменной окружения
    port = int(os.environ.get("PORT", 10000))
    print(f"Запуск на порту: {port}")
    print(f"Хост: 0.0.0.0")
    
    # Запускаем Flask
    try:
        app.run(host="0.0.0.0", port=port, debug=False)
        print("Flask приложение запущено")
    except Exception as e:
        print(f"ERROR при запуске Flask: {e}")
        sys.exit(1)