import logging
import os
import time
import json
import subprocess
import threading
import queue
import platform
import psutil
import re
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import openai
import asyncio

# Загрузка переменных окружения
load_dotenv()

# Получение токенов из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Настройка клиента OpenAI
openai.api_key = OPENAI_API_KEY

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Путь к истории
HISTORY_PATH = os.path.join("logs", "history.txt")
os.makedirs("logs", exist_ok=True)

class GeminiCLIManager:
    """Менеджер для работы с Gemini CLI через прямые команды"""
    
    def __init__(self):
        self.is_ready = False
        
    def check_gemini_cli(self):
        """Проверяет, установлен ли и работает ли Gemini CLI"""
        try:
            logger.info("Проверяю доступность Gemini CLI...")
            
            # Проверяем версию
            cmd = ["powershell.exe", "-Command", "gemini", "--version"]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=10)
            
            if result.returncode == 0:
                version_info = result.stdout.strip()
                logger.info(f"✅ Gemini CLI найден: {version_info}")
                
                # Проверяем аутентификацию простым запросом
                test_cmd = ["powershell.exe", "-Command", "gemini", "-p", "test"]
                test_result = subprocess.run(test_cmd, capture_output=True, text=True, encoding='utf-8', timeout=15)
                
                if test_result.returncode == 0:
                    logger.info("✅ Gemini CLI аутентифицирован и готов к работе")
                    return True
                else:
                    logger.error(f"❌ Ошибка аутентификации Gemini CLI: {test_result.stderr}")
                    logger.error("Выполните: gemini auth")
                    return False
            else:
                logger.error(f"❌ Gemini CLI не найден: {result.stderr}")
                logger.error("Установите: npm install -g @google/gemini-cli")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Таймаут при проверке Gemini CLI")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки Gemini CLI: {e}")
            return False
    
    def initialize(self):
        """Инициализирует Gemini CLI"""
        logger.info("🔧 Инициализация Gemini CLI...")
        
        # Проверяем доступность CLI
        if not self.check_gemini_cli():
            return False
        
        self.is_ready = True
        logger.info("✅ Gemini CLI готов к работе!")
        return True
    
    async def send_message(self, message, user_id, timeout=60):
        """Отправляет сообщение в Gemini CLI через прямую команду"""
        if not self.is_ready:
            return "❌ Gemini CLI не готов к работе"
        
        try:
            logger.info(f"📤 Отправляю в Gemini CLI: '{message[:100]}{'...' if len(message) > 100 else ''}'")
            
            # Экранируем кавычки в сообщении
            escaped_message = message.replace('"', '""')
            
            # Формируем команду
            cmd = [
                "powershell.exe", 
                "-Command", 
                f'gemini -p "{escaped_message}"'
            ]
            
            # Выполняем команду
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                timeout=timeout
            )
            
            if result.returncode == 0:
                response = result.stdout.strip()
                
                # Убираем предупреждения Node.js
                lines = response.split('\n')
                clean_lines = []
                for line in lines:
                    if not self._is_system_message(line):
                        clean_lines.append(line)
                
                final_response = '\n'.join(clean_lines).strip()
                
                if final_response:
                    logger.info(f"📥 Получен ответ от Gemini ({len(final_response)} символов)")
                    return final_response
                else:
                    logger.warning("⚠️ Gemini CLI вернул пустой ответ")
                    return "Gemini CLI вернул пустой ответ"
            else:
                error_msg = result.stderr.strip()
                logger.error(f"❌ Ошибка выполнения команды Gemini CLI: {error_msg}")
                return f"Ошибка Gemini CLI: {error_msg}"
                
        except subprocess.TimeoutExpired:
            logger.error(f"⏰ Таймаут выполнения команды Gemini CLI ({timeout}s)")
            return f"Таймаут выполнения команды ({timeout}s)"
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения: {e}")
            return f"Ошибка: {e}"
    
    def _is_system_message(self, line):
        """Проверяет, является ли строка служебным сообщением"""
        if not line or len(line.strip()) == 0:
            return True
            
        system_patterns = [
            "DeprecationWarning",
            "punycode",
            "Use `node --trace-deprecation",
            "(node:",
            "┌", "│", "└", "▲", "◯"
        ]
        return any(pattern in line for pattern in system_patterns)

# Глобальный менеджер Gemini CLI
gemini_manager = GeminiCLIManager()

# Ретрай для Whisper API
async def transcribe_with_retry(audio_file, retries=3, delay=2):
    for attempt in range(retries):
        try:
            return openai.Audio.transcribe("whisper-1", audio_file)
        except Exception as e:
            logger.warning(f"Попытка {attempt+1} не удалась: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise

# Функция для записи истории
def log_history(user_id, text, gemini_response):
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(f"USER {user_id}: {text}\nGEMINI: {gemini_response}\n---\n")

# Функция для обработки текстовых сообщений
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.message.from_user.id

    # Игнорируем команды бота
    if text.startswith('/'):
        return

    logger.info(f"📱 Текстовое сообщение от {user_id}: {text}")

    try:
        # Отправляем текст в Gemini CLI
        gemini_response = await gemini_manager.send_message(text, user_id)
        
        logger.debug(f"📥 Ответ Gemini: {gemini_response[:200]}{'...' if len(gemini_response) > 200 else ''}")
        
        # Запись в историю
        log_history(user_id, text, gemini_response)
        
        # Отправка ответа от Gemini пользователю
        await update.message.reply_text(gemini_response)

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке текстового сообщения: {e}")
        await update.message.reply_text("Произошла ошибка при обработке вашего сообщения.")

# Функция для обработки голосовых сообщений
async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    file_id = update.message.voice.file_id
    duration = update.message.voice.duration
    user_id = update.message.from_user.id

    # Проверка лимита 3 минуты
    if duration > 180:
        await update.message.reply_text("Максимальная длина голосового сообщения — 3 минуты.")
        logger.info(f"❌ Отклонено сообщение от {user_id}: превышен лимит {duration} сек.")
        return

    new_file = await context.bot.get_file(file_id)
    file_path = f"{file_id}.ogg"
    await new_file.download_to_drive(file_path)

    try:
        logger.info(f"🎤 Обрабатываю голосовое сообщение от {user_id} ({duration}s)")
        
        with open(file_path, "rb") as audio_file:
            transcript = await transcribe_with_retry(audio_file)
        text = transcript['text']

        logger.info(f"📝 Транскрипция: {text}")

        # Отправляем транскрипт в Gemini CLI
        gemini_response = await gemini_manager.send_message(text, user_id)
        
        logger.debug(f"📥 Ответ Gemini: {gemini_response[:200]}{'...' if len(gemini_response) > 200 else ''}")
        
        # Запись в историю
        log_history(user_id, text, gemini_response)
        
        # Отправка ответа от Gemini пользователю
        await update.message.reply_text(gemini_response)

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке голосового сообщения: {e}")
        await update.message.reply_text("Произошла ошибка при обработке вашего сообщения.")
    finally:
        # Удаление временного аудиофайла
        if os.path.exists(file_path):
            os.remove(file_path)

# Функция для обработки ошибок
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main() -> None:
    """Запуск бота."""
    logger.info("🚀 Запуск Gemini Telegram Bot")
    
    # Инициализируем Gemini CLI
    if not gemini_manager.initialize():
        logger.error("❌ Не удалось инициализировать Gemini CLI. Завершение работы.")
        logger.error("💡 Убедитесь, что:")
        logger.error("   1. Установлен Gemini CLI: npm install -g @google/gemini-cli")
        logger.error("   2. Выполнена аутентификация: gemini auth")
        return
    
    logger.info("✅ Gemini CLI готов к работе")
    logger.info("📱 Запускаю Telegram бота...")
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Добавление обработчика для голосовых сообщений
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
    
    # Добавление обработчика для текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Добавление обработчика ошибок
    application.add_error_handler(error)

    try:
        # Запуск бота
        logger.info("🎯 Бот запущен и готов к работе!")
        logger.info("💬 Отправьте сообщение в Telegram для тестирования")
        application.run_polling()
    finally:
        logger.info("🛑 Завершение работы...")

if __name__ == "__main__":
    main()
