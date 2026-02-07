import os
import sys
import asyncio
import sqlite3
from datetime import datetime
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

print("=" * 50)
print("ВЕРСИЯ КОДА: 2026-02-07 с командой /export")
print("=" * 50)

print("=== Начало запуска бота ===")

# ------------------- Настройки -------------------
TOKEN = os.getenv("TELEGRAM_TOKEN")
OWNER_ID = 5534388849
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
machines = {"GRUSHA": "ГРУША"}

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
    """Обработчик команды /start"""
    print(f"\n=== ПОЛУЧЕНА КОМАНДА /start ОТ {message.from_user.id} ===")
    print(f"Текст сообщения: '{message.text}'")
    print(f"User ID: {message.from_user.id}")
    print(f"Username: @{message.from_user.username}")
    
    try:
        args = message.text.split()
        machine_code = args[1] if len(args) > 1 else "unknown"
        machine_name = machines.get(machine_code, machine_code)
        user_machine[message.from_user.id] = machine_code
        
        print(f"Код машины: {machine_code}")
        print(f"Имя машины: {machine_name}")
        
        print("Отправляю ответ пользователю...")
        await message.answer(f"Привет! Вы подключились к машине {machine_name}", reply_markup=menu_kb)
        print("✅ Ответ успешно отправлен!")
        
    except Exception as e:
        print(f"❌ ERROR в start_handler: {e}")
        import traceback
        traceback.print_exc()

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
        import traceback
        traceback.print_exc()

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
        import traceback
        traceback.print_exc()

# ------------------- НОВАЯ ФУНКЦИЯ: Экспорт базы данных -------------------
async def export_database_handler(message: types.Message):
    """Обработчик команды /export для отправки бэкапа базы данных"""
    print(f"\n=== ПОЛУЧЕНА КОМАНДА /export ОТ {message.from_user.id} ===")
    
    # Проверяем, что команду отправляет владелец бота
    if message.from_user.id != OWNER_ID:
        print(f"❌ Отказ в доступе: пользователь {message.from_user.id} не является владельцем")
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        # Проверяем существование файла базы данных
        if not os.path.exists(DB_PATH):
            print(f"❌ Файл базы данных не найден: {DB_PATH}")
            await message.answer("❌ Файл базы данных не найден.")
            return
        
        # Получаем размер файла
        file_size = os.path.getsize(DB_PATH)
        print(f"Размер файла базы данных: {file_size} байт")
        
        # Создаем объект файла для отправки
        document = FSInputFile(DB_PATH)
        
        print(f"Отправляю файл базы данных пользователю {message.from_user.id}...")
        
        # Отправляем файл
        await message.answer_document(
            document=document,
            caption=f"📋 Бэкап базы данных\n"
                   f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                   f"Размер: {file_size} байт"
        )
        
        print("✅ Файл базы данных успешно отправлен!")
        
    except Exception as e:
        print(f"❌ ERROR в export_database_handler: {e}")
        import traceback
        traceback.print_exc()
        await message.answer(f"❌ Ошибка при отправке базы данных: {str(e)}")

# ------------------- Bot и Dispatcher -------------------
print("Инициализация бота и диспетчера...")
try:
    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Регистрируем все обработчики
    dp.message.register(start_handler, Command("start"))
    dp.message.register(export_database_handler, Command("export"))  # НОВЫЙ ОБРАБОТЧИК
    dp.callback_query.register(callback_handler)
    dp.message.register(message_handler)
    
    print("Бот и диспетчер инициализированы успешно")
    print(f"Зарегистрировано обработчиков команд: {len(dp.message.handlers)}")
except Exception as e:
    print(f"ERROR при инициализации бота/диспетчера: {e}")
    sys.exit(1)

# ------------------- Flask и Webhook -------------------
app = Flask(__name__)

# Создаем глобальный event loop для обработки асинхронных задач
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "POST":
        try:
            print("\n" + "=" * 50)
            print("📨 ПОЛУЧЕН POST-ЗАПРОС ОТ TELEGRAM")
            print(f"Время получения: {datetime.now().strftime('%H:%M:%S')}")
            
            update_data = request.get_json()
            
            # Определяем тип сообщения
            if "message" in update_data:
                msg_text = update_data["message"].get("text", "Нет текста")
                user_id = update_data["message"]["from"]["id"]
                print(f"📝 Сообщение от user_id={user_id}: '{msg_text}'")
            elif "callback_query" in update_data:
                callback_data = update_data["callback_query"]["data"]
                user_id = update_data["callback_query"]["from"]["id"]
                print(f"🔄 Callback от user_id={user_id}: '{callback_data}'")
            else:
                print(f"❓ Неизвестный тип update: {update_data.keys()}")
            
            update = types.Update(**update_data)
            print("⏳ Начинаю обработку update...")
            
            # Используем существующий event loop
            loop.run_until_complete(dp.feed_webhook_update(bot, update))
            
            print("✅ Update успешно обработан")
            print("=" * 50 + "\n")
            
        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА при обработке апдейта: {e}")
            import traceback
            traceback.print_exc()
            print("=" * 50 + "\n")
        return "ok", 200
    else:
        return "Bot is alive!", 200

@app.route("/health", methods=["GET"])
def health_check():
    return {"status": "ok", "bot": "running", "version": "2026-02-07-with-export"}, 200

# ------------------- Main -------------------
async def on_startup():
    """Установка вебхука при запуске"""
    webhook_url = "https://coffee-telegram-bot-1-tf7w.onrender.com/"
    print(f"\n⏳ Устанавливаю вебхук на: {webhook_url}")
    try:
        await bot.set_webhook(webhook_url)
        print("✅ Вебхук успешно установлен")
    except Exception as e:
        print(f"❌ Ошибка при установке вебхука: {e}")

if __name__ == "__main__":
    # Устанавливаем вебхук при запуске
    loop.run_until_complete(on_startup())
    
    print("\n=== Запуск Flask приложения ===")
    
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
        print("\n" + "=" * 50)
        print("✅ Бот запущен и готов к работе!")
        print(f"Доступные команды:")
        print(f"  /start - начать работу с ботом")
        print(f"  /export - получить бэкап базы данных (только для владельца)")
        print("=" * 50)
    except Exception as e:
        print(f"ERROR при запуске Flask: {e}")
        sys.exit(1)