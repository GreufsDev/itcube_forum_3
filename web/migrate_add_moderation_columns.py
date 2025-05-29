import sqlite3
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def migrate():
    """Добавляет колонки для модерации в таблицу topics"""
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect('forum.db')
        cursor = conn.cursor()

        # Проверяем существование колонки status
        cursor.execute("PRAGMA table_info(topics)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'status' not in columns:
            # Добавляем колонку status
            cursor.execute('''
                ALTER TABLE topics
                ADD COLUMN status TEXT DEFAULT 'pending'
            ''')
            logger.info("Добавлена колонка status")

        if 'moderator_id' not in columns:
            # Добавляем колонку moderator_id
            cursor.execute('''
                ALTER TABLE topics
                ADD COLUMN moderator_id INTEGER
            ''')
            logger.info("Добавлена колонка moderator_id")

        if 'moderated_at' not in columns:
            # Добавляем колонку moderated_at
            cursor.execute('''
                ALTER TABLE topics
                ADD COLUMN moderated_at DATETIME
            ''')
            logger.info("Добавлена колонка moderated_at")

        if 'moderation_comment' not in columns:
            # Добавляем колонку moderation_comment
            cursor.execute('''
                ALTER TABLE topics
                ADD COLUMN moderation_comment TEXT
            ''')
            logger.info("Добавлена колонка moderation_comment")

        # Обновляем существующие темы
        cursor.execute('''
            UPDATE topics
            SET status = 'approved'
            WHERE status IS NULL
        ''')
        logger.info("Обновлены существующие темы")

        # Сохраняем изменения
        conn.commit()
        logger.info("Миграция успешно завершена")

    except Exception as e:
        logger.error(f"Ошибка при миграции: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    migrate() 