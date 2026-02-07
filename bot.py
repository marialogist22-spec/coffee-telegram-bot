import os
import sys
import asyncio
import sqlite3
import csv
import io
from datetime import datetime
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

print("=" * 50)
print("ВЕРСИЯ КОДА: 2026-02-07 с улучшенным экспортом и веб-интерфейсом")
print("=" * 50)

print("=== Начало запуска бота ===")

# ------------------- Настройки -------------------
TOKEN = os.getenv("TELEGRAM_TOKEN")
OWNER_ID = 5534388849
DB_PATH = "bot_data.db"
# Установите свой пароль для админки (замените на сложный пароль)
ADMIN_PASSWORD = "coffegrusha123"

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

# ------------------- УЛУЧШЕННАЯ ФУНКЦИЯ: Экспорт базы данных -------------------
async def export_database_handler(message: types.Message):
    """Обработчик команды /export для отправки бэкапов базы данных"""
    print(f"\n=== ПОЛУЧЕНА КОМАНДА /export ОТ {message.from_user.id} ===")
    
    # Проверяем, что команду отправляет владелец бота
    if message.from_user.id != OWNER_ID:
        print(f"❌ Отказ в доступе: пользователь {message.from_user.id} не является владельцем")
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        # 1. Отправляем оригинальный файл базы данных SQLite
        if not os.path.exists(DB_PATH):
            print(f"❌ Файл базы данных не найден: {DB_PATH}")
            await message.answer("❌ Файл базы данных не найден.")
            return
        
        file_size = os.path.getsize(DB_PATH)
        print(f"Размер файла базы данных: {file_size} байт")
        
        document = FSInputFile(DB_PATH)
        print(f"Отправляю файл базы данных пользователю {message.from_user.id}...")
        
        await message.answer_document(
            document=document,
            caption=f"📁 Оригинальная база данных SQLite\n"
                   f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                   f"Размер: {file_size} байт"
        )
        print("✅ SQLite файл успешно отправлен!")
        
        # 2. Создаем и отправляем CSV-файл
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM records ORDER BY timestamp DESC")
        records = cursor.fetchall()
        conn.close()

        if records:
            # Создаем CSV в памяти
            output = io.StringIO()
            csv_writer = csv.writer(output)
            
            # Заголовки столбцов
            csv_writer.writerow(['ID', 'User ID', 'Machine', 'Type', 'Value', 'Timestamp'])
            # Данные
            csv_writer.writerows(records)
            
            # Преобразуем в байты и отправляем как файл
            csv_data = io.BytesIO(output.getvalue().encode('utf-8'))
            csv_file = types.BufferedInputFile(csv_data.getvalue(), filename="bot_data.csv")
            
            await message.answer_document(
                document=csv_file,
                caption="📊 Данные в формате CSV (открывается в Excel/Google Sheets)"
            )
            print("✅ CSV-файл успешно создан и отправлен!")
            
            # 3. Отправляем краткую статистику
            stats_message = (
                f"📈 Статистика данных:\n"
                f"• Всего записей: {len(records)}\n"
                f"• Последняя запись: {records[0][5] if len(records[0]) > 5 else 'N/A'}\n"
                f"• Файл CSV содержит {len(records)} строк"
            )
            await message.answer(stats_message)
            
        else:
            await message.answer("📭 База данных пуста. Нет данных для экспорта.")

    except Exception as e:
        print(f"❌ ERROR в export_database_handler: {e}")
        import traceback
        traceback.print_exc()
        await message.answer(f"❌ Ошибка при экспорте данных: {str(e)}")

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
    dp.message.register(export_database_handler, Command("export"))
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
    return {"status": "ok", "bot": "running", "version": "2026-02-07-with-export-and-webview"}, 200

@app.route("/admin/<password>", methods=["GET"])
def admin_view(password):
    """Секретная страница для просмотра данных в браузере"""
    if password != ADMIN_PASSWORD:
        return """
        <html>
        <head><title>Доступ запрещен</title><meta charset="utf-8"></head>
        <body style="font-family: Arial; text-align: center; margin-top: 50px;">
            <h1>❌ Доступ запрещен</h1>
            <p>Неверный пароль или страница не существует.</p>
        </body>
        </html>
        """, 403
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Получаем общую статистику
        cursor.execute("SELECT COUNT(*) FROM records")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT 
                id, user_id, machine_id, type, value,
                datetime(timestamp, 'localtime') as local_time
            FROM records 
            ORDER BY timestamp DESC
            LIMIT 200
        """)
        records = cursor.fetchall()
        conn.close()
        
        # Создаем HTML-таблицу
        html = """
        <html>
        <head>
            <title>📊 Данные бота кофемашин</title>
            <meta charset="utf-8">
            <style>
                body { 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    margin: 20px; 
                    background-color: #f5f5f5;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                h1 { 
                    color: #333; 
                    border-bottom: 2px solid #4CAF50;
                    padding-bottom: 10px;
                }
                .stats {
                    background: #e8f5e9;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }
                table { 
                    border-collapse: collapse; 
                    width: 100%; 
                    margin-top: 20px;
                }
                th, td { 
                    border: 1px solid #ddd; 
                    padding: 10px; 
                    text-align: left; 
                }
                th { 
                    background-color: #4CAF50; 
                    color: white; 
                    position: sticky;
                    top: 0;
                }
                tr:nth-child(even) { background-color: #f9f9f9; }
                tr:hover { background-color: #f1f1f1; }
                .type-coffee { color: #8B4513; }
                .type-service { color: #1E90FF; }
                .type-review { color: #FF8C00; }
                .type-issue { color: #DC143C; }
                .footer {
                    margin-top: 20px;
                    text-align: center;
                    color: #666;
                    font-size: 0.9em;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📊 Данные бота кофемашин</h1>
                
                <div class="stats">
                    <p><strong>📈 Статистика:</strong></p>
                    <p>• Всего записей в базе: <b>{total_count}</b></p>
                    <p>• Показано на странице: <b>{shown_count}</b> (последние записи)</p>
                    <p>• Последнее обновление: <b>{current_time}</b></p>
                    <p>• Для полного экспорта используйте команду <code>/export</code> в Telegram</p>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>User ID</th>
                            <th>Машина</th>
                            <th>Тип</th>
                            <th>Значение/Текст</th>
                            <th>Время (местное)</th>
                        </tr>
                    </thead>
                    <tbody>
        """.format(
            total_count=total_count,
            shown_count=len(records),
            current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        type_classes = {
            'coffee': 'type-coffee',
            'service': 'type-service', 
            'review': 'type-review',
            'issue': 'type-issue'
        }
        
        for row in records:
            type_class = type_classes.get(row[3], '')
            html += f"""
                        <tr>
                            <td>{row[0]}</td>
                            <td>{row[1]}</td>
                            <td>{row[2]}</td>
                            <td class="{type_class}">{row[3]}</td>
                            <td>{row[4]}</td>
                            <td>{row[5]}</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
                
                <div class="footer">
                    <p>Бот кофемашин | Версия с веб-интерфейсом | Автоматическое обновление при новом запросе</p>
                    <p>Ссылка для доступа: https://coffee-telegram-bot-1-tf7w.onrender.com/admin/<b>ВАШ_ПАРОЛЬ</b></p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
        
    except Exception as e:
        return f"""
        <html>
        <head><title>Ошибка</title><meta charset="utf-8"></head>
        <body style="font-family: Arial; text-align: center; margin-top: 50px;">
            <h1>❌ Ошибка при загрузке данных</h1>
            <p>{str(e)}</p>
        </body>
        </html>
        """, 500

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
        print("\n" + "=" * 60)
        print("✅ Бот запущен и готов к работе!")
        print(f"Доступные команды в Telegram:")
        print(f"  /start   - начать работу с ботом")
        print(f"  /export  - получить бэкап базы данных (только для владельца)")
        print(f"\n🌐 Веб-интерфейс для просмотра данных:")
        print(f"  https://coffee-telegram-bot-1-tf7w.onrender.com/admin/{ADMIN_PASSWORD}")
        print(f"\n⚠️  НЕ ЗАБУДЬТЕ поменять пароль ADMIN_PASSWORD в коде!")
        print("=" * 60)
    except Exception as e:
        print(f"ERROR при запуске Flask: {e}")
        sys.exit(1)