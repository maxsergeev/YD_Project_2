import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Настройка логгера
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = "8184670348:AAEYR4KMpPCcWDtUuHGYLvidYaNryrwE3lE"
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "Diary_HSE_bot"
COLLECTION_NAME = "users"

# Инициализация MongoDB
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.server_info()  # Проверка подключения
    db = client[DB_NAME]
    users_collection = db[COLLECTION_NAME]
    logger.info("✅ Успешное подключение к MongoDB")
except ConnectionFailure as e:
    logger.error(f"❌ Ошибка подключения к MongoDB: {e}")
    raise
except Exception as e:
    logger.error(f"❌ Неожиданная ошибка: {e}")
    raise

# Клавиатура
keyboard = ReplyKeyboardMarkup(
    [
        ["/add", "/get"],
        ["/help"]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите команду..."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        await update.message.reply_html(
            rf"Привет {user.mention_html()}! Я твой персональный дневник📖" '\n'
            "Используй кнопки ниже для управления:",
            reply_markup=keyboard
        )
        logger.info(f"Пользователь {user.id} запустил бота")
    except Exception as e:
        logger.error(f"Ошибка в start: {e}")

async def add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("✍️ Опиши, что интересного произошло сегодня:")
        logger.info(f"Пользователь {update.effective_user.id} начал добавление записи")
    except Exception as e:
        logger.error(f"Ошибка в add_entry: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        result = users_collection.update_one(
            {"user_id": user_id},
            {
                "$push": {f"entries.{current_date}": text},
                "$setOnInsert": {"user_id": user_id}
            },
            upsert=True
        )
        
        if result.upserted_id:
            logger.info(f"Создан новый пользователь: {user_id}")
        
        await update.message.reply_text("✅ Запись успешно сохранена!", reply_markup=keyboard)
        logger.info(f"Пользователь {user_id} добавил запись за {current_date}")
    except Exception as e:
        logger.error(f"Ошибка сохранения записи: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при сохранении. Попробуйте позже.")

async def get_entries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("📅 Введи дату в формате ГГГГ-ММ-ДД:")
        logger.info(f"Пользователь {update.effective_user.id} запросил получение записей")
    except Exception as e:
        logger.error(f"Ошибка в get_entries: {e}")

def is_valid_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

async def handle_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        date_input = update.message.text
        
        if not is_valid_date(date_input):
            await update.message.reply_text("❌ Неверный формат даты! Используй ГГГГ-ММ-ДД")
            return

        user_data = users_collection.find_one(
            {"user_id": user_id},
            {f"entries.{date_input}": 1}
        )
        
        if not user_data or not user_data.get("entries", {}).get(date_input):
            await update.message.reply_text("📭 Записей за эту дату нет")
            return
            
        entries = user_data["entries"][date_input]
        formatted_entries = "\n".join([f"• {entry}" for entry in entries])
        await update.message.reply_text(
            f"📆 Записи за {date_input}:\n\n{formatted_entries}",
            reply_markup=keyboard
        )
        logger.info(f"Пользователь {user_id} получил записи за {date_input}")
    except Exception as e:
        logger.error(f"Ошибка получения записей: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при получении записей.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        help_text = (
            "🛠 Доступные команды:\n"
            "/start - Перезапустить бота\n"
            "/add - Добавить запись\n"
            "/get - Посмотреть записи\n"
            "/help - Эта справка"
        )
        await update.message.reply_text(help_text, reply_markup=keyboard)
        logger.info(f"Пользователь {update.effective_user.id} запросил помощь")
    except Exception as e:
        logger.error(f"Ошибка в help_command: {e}")

def main():
    try:
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        handlers = [
            CommandHandler("start", start),
            CommandHandler("add", add_entry),
            CommandHandler("get", get_entries),
            CommandHandler("help", help_command),
            MessageHandler(filters.Regex(r"^\d{4}-\d{2}-\d{2}$") & ~filters.COMMAND, handle_date),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
        ]
        
        for handler in handlers:
            application.add_handler(handler)
        
        logger.info("🤖 Бот запущен и готов к работе")
        application.run_polling()
        
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
    finally:
        if 'client' in locals():
            client.close()
            logger.info("Соединение с MongoDB закрыто")

if __name__ == "__main__":
    main()