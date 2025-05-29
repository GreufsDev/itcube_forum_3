import os
import sys
import asyncio
import logging
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from pathlib import Path

# Добавляем путь к корневой директории проекта
sys.path.append(str(Path(__file__).parent.parent))

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command, StateFilter
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
from aiogram.client.default import DefaultBotProperties

import database as db
from config import TELEGRAM_MAIN_BOT_TOKEN

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='bot.log',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

# Константы
UPLOAD_FOLDER = Path('uploads')
MIN_TITLE_LENGTH = 3
MIN_TEXT_LENGTH = 10
MAX_RETRIES = 3
RETRY_DELAY = 5

# Инициализация бота и диспетчера
bot = Bot(
    token=TELEGRAM_MAIN_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode='HTML')
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# Состояния FSM
class TopicStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_text = State()
    waiting_for_attachments = State()

class TopicManager:
    """Класс для управления темами"""
    
    @staticmethod
    async def create_topic_directory(topic_id: str) -> Optional[Path]:
        """Создает директорию для темы"""
        try:
            topic_dir = UPLOAD_FOLDER / f"topic_{topic_id}"
            topic_dir.mkdir(parents=True, exist_ok=True)
            return topic_dir
        except Exception as e:
            logger.error(f"Ошибка при создании директории темы: {e}")
            return None

    @staticmethod
    async def save_topic_data(topic_dir: Path, data: Dict[str, Any]) -> bool:
        """Сохраняет данные темы в JSON файл"""
        try:
            topic_file = topic_dir / "topic.json"
            topic_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении данных темы: {e}")
            return False

    @staticmethod
    async def save_attachment(bot: Bot, topic_dir: Path, attachment: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
        """Сохраняет вложение темы"""
        try:
            file_info = await bot.get_file(attachment['file_id'])
            if attachment['type'] == 'document':
                file_name = attachment['file_name']
            else:
                file_name = f"photo_{index}.jpg"
            
            file_path = topic_dir / file_name
            await bot.download_file(file_info.file_path, file_path)
            
            return {
                'type': attachment['type'],
                'file_name': file_name,
                'file_size': file_path.stat().st_size
            }
        except Exception as e:
            logger.error(f"Ошибка при сохранении вложения: {e}")
            return None

class MessageManager:
    """Класс для управления сообщениями"""
    
    @staticmethod
    async def send_message(chat_id: int, text: str, **kwargs) -> bool:
        """Безопасная отправка сообщения с повторными попытками"""
        for attempt in range(MAX_RETRIES):
            try:
                await bot.send_message(chat_id=chat_id, text=text, **kwargs)
                return True
            except (TelegramNetworkError, TelegramAPIError) as e:
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"Не удалось отправить сообщение после {MAX_RETRIES} попыток: {e}")
                else:
                    logger.warning(f"Попытка {attempt + 1} не удалась, повтор через {RETRY_DELAY} сек: {e}")
                    await asyncio.sleep(RETRY_DELAY)
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения: {e}")
                break
        return False

class UserManager:
    """Класс для управления пользователями"""
    
    @staticmethod
    def check_user_access(user_id: int) -> tuple[bool, Optional[Dict[str, Any]]]:
        """Проверяет доступ пользователя: только преподаватели с привязанным Telegram"""
        try:
            user = db.get_user_by_telegram_id(user_id)
            if not user or user['role'] != 'teacher':
                return False, None
            return True, user
        except Exception as e:
            logger.error(f"Ошибка при проверке доступа пользователя: {e}")
            return False, None

    @staticmethod
    def get_user_direction(user_id: int) -> Optional[str]:
        """Получает направление пользователя"""
        try:
            directions = db.get_user_directions_by_user_id(user_id)
            return directions[0] if directions else None
        except Exception as e:
            logger.error(f"Ошибка при получении направления пользователя: {e}")
            return None

# Обработчики команд
@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    try:
        has_access, user = UserManager.check_user_access(message.from_user.id)
        if not has_access:
            await message.answer("❌ Упс. Кажется вас нет в списке преподавателей. Обратитесь к администратору.")
            return

        logger.info(f"Пользователь {message.from_user.id} запустил бота")
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Доступные команды:\n"
            "📝 /topic — создать новую тему\n"
            "📁 Отправьте файл для загрузки\n"
            "❓ /help — показать справку"
        )
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = (
        "📚 Справка по командам бота:\n\n"
        "/start — начать работу с ботом\n"
        "/topic — создать новую тему\n"
        "/help — показать эту справку\n\n"
        "При создании темы:\n"
        "1. Введите название (минимум 3 символа)\n"
        "2. Введите текст (минимум 10 символов)\n"
        "3. Прикрепите файлы (необязательно)\n"
        "4. Отправьте /done для завершения\n\n"
        "В любой момент можно отменить создание темы командой /cancel"
    )
    await MessageManager.send_message(message.chat.id, help_text)

@router.message(Command("topic"))
async def cmd_topic(message: Message):
    """Информация о создании тем"""
    await MessageManager.send_message(
        message.chat.id,
        "📝 Создание тем теперь доступно на веб-форуме.\n\n"
        "Перейдите в панель преподавателя на форуме для создания новых тем."
    )

@router.message(Command("cancel"), StateFilter(TopicStates.waiting_for_title, TopicStates.waiting_for_text, TopicStates.waiting_for_attachments))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена создания темы"""
    try:
        logger.info(f"Пользователь {message.from_user.id} отменил создание темы")
        await state.clear()
        await MessageManager.send_message(message.chat.id, "❌ Создание темы отменено.")
    except Exception as e:
        logger.error(f"Ошибка при отмене создания темы: {e}", exc_info=True)
        await MessageManager.send_message(
            message.chat.id,
            "❌ Произошла ошибка при отмене создания темы."
        )

@router.message(F.content_type == 'document')
async def handle_file(message: Message):
    """Обработка загрузки файла"""
    try:
        has_access, user = UserManager.check_user_access(message.from_user.id)
        if not has_access:
            await MessageManager.send_message(
                message.chat.id,
                "❌ Упс. Кажется вас нет в списке преподавателей. Обратитесь к администратору."
            )
            return

        direction = UserManager.get_user_direction(user['id'])
        if not direction:
            await MessageManager.send_message(
                message.chat.id,
                "❌ Ошибка: не указано направление. Обратитесь к администратору."
            )
            return

        # Создаем уникальный ID для файла
        file_id = str(uuid.uuid4())[:8]
        file_dir = UPLOAD_FOLDER / f"file_{file_id}"
        file_dir.mkdir(parents=True, exist_ok=True)

        # Скачиваем файл
        file_info = await bot.get_file(message.document.file_id)
        file_path = file_dir / message.document.file_name
        await bot.download_file(file_info.file_path, file_path)

        # Сохраняем данные файла
        file_data = {
            "user_id": message.from_user.id,
            "username": user['username'],
            "direction": direction,
            "status": "pending",
            "file_name": message.document.file_name,
            "file_size": file_path.stat().st_size,
            "created_at": datetime.now().isoformat()
        }

        (file_dir / "file.json").write_text(
            json.dumps(file_data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        await MessageManager.send_message(
            message.chat.id,
            "✅ Ваш файл отправлен на модерацию.\n\n"
            f"📁 Файл: {message.document.file_name}\n"
            "После одобрения модератором он появится на форуме."
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}", exc_info=True)
        await MessageManager.send_message(
            message.chat.id,
            "❌ Ошибка при загрузке файла. Попробуйте позже."
        )

async def on_startup():
    """Действия при запуске бота"""
    logger.info("Бот запущен")
    # Создаем директорию для загрузок, если её нет
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("Бот остановлен")
    await bot.session.close()

async def main():
    """Основная функция запуска бота"""
    try:
        # Регистрируем обработчики
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        # Запускаем бота
        logger.info("Запуск бота...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)

if __name__ == '__main__':
    asyncio.run(main())