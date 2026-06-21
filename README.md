# Gemini Telegram Bot

Telegram-бот, который принимает голосовые и текстовые сообщения, транскрибирует голос через OpenAI Whisper и автоматически отправляет команды в Gemini CLI от Google.

## 🚀 Единая точка входа

Весь проект запускается **одним файлом**:
```bash
python telegram_bot.py
```

## 🔧 Новая архитектура (v2.0)

**Прямые команды вместо интерактивной сессии:**
- Каждое сообщение отправляется как отдельная команда: `gemini -p "текст сообщения"`
- Никаких сложных subprocess с потоками
- Максимальная надежность и простота отладки

## 🔍 Автоматическая инициализация

Бот автоматически:
1. **Проверяет установку** Gemini CLI (`gemini --version`)
2. **Тестирует аутентификацию** простым запросом
3. **Ищет активные процессы** Gemini CLI (опционально)
4. **Готов к работе** через прямые команды

## Архитектура

```
Telegram → Bot → Проверка CLI → gemini -p "сообщение" → Ответ
                      ↓
               Если не готов → Ошибка с инструкциями
```

## Установка

### 1. Установка зависимостей

```bash
# Python зависимости
pip install python-telegram-bot openai python-dotenv psutil

# Node.js и Gemini CLI
npm install -g @google/gemini-cli
```

### 2. Настройка переменных окружения

Создайте файл `.env`:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Аутентификация в Gemini CLI

```bash
gemini auth
```

Следуйте инструкциям для входа в ваш Google аккаунт.

## Запуск

### Простой запуск
```bash
python telegram_bot.py
```

Бот автоматически:
- Проверит установку и аутентификацию Gemini CLI
- Покажет подробные инструкции при ошибках
- Будет готов к работе через прямые команды

### Проверка готовности
Бот выполнит автоматические проверки:
1. `gemini --version` - проверка установки
2. `gemini -p "test"` - проверка аутентификации
3. Поиск активных процессов (информативно)

## Как это работает

1. **Пользователь отправляет сообщение** в Telegram (голосовое или текстовое)
2. **Бот транскрибирует голос** (если нужно) через Whisper API
3. **Выполняет команду** `powershell.exe -Command 'gemini -p "сообщение"'`
4. **Получает ответ** из stdout команды
5. **Фильтрует системные сообщения** Node.js
6. **Отправляет ответ** пользователю в Telegram

## Особенности

- ✅ **Прямые команды**: Каждое сообщение = отдельная команда `gemini -p`
- ✅ **Максимальная надежность**: Никаких сложных subprocess
- ✅ **Простая отладка**: Легко воспроизвести команды вручную
- ✅ **Автоматические проверки**: Установка и аутентификация
- ✅ **Голосовые сообщения**: Автоматическая транскрипция через Whisper API
- ✅ **Текстовые сообщения**: Прямая отправка в Gemini CLI
- ✅ **Лимит 3 минуты**: Для голосовых сообщений
- ✅ **Логирование**: Вся история сохраняется в `logs/history.txt`
- ✅ **Фильтрация**: Убирает системные сообщения Node.js

## Файловая структура

```
gemini_telegram_bot/
├── telegram_bot.py          # Единый файл запуска (основной)
├── logs/
│   └── history.txt          # История всех сообщений
├── docs/                    # Документация проекта
├── .env                     # Переменные окружения
└── README.md               # Этот файл
```

## Требования

- **Python 3.10+**
- **Node.js 18+**
- **Токен Telegram бота** (получить у @BotFather)
- **OpenAI API ключ** (для Whisper)
- **Google аккаунт** (для Gemini CLI)

## Устранение неполадок

### Бот не запускается
- Проверьте токены в файле `.env`
- Убедитесь, что установлен Gemini CLI: `gemini --version`
- Проверьте авторизацию: `gemini auth`

### Ошибка "Gemini CLI не найден"
```bash
npm install -g @google/gemini-cli
```

### Ошибка "Ошибка аутентификации"
```bash
gemini auth
```

### Ошибки транскрипции
- Проверьте OPENAI_API_KEY в `.env`
- Убедитесь, что у вас есть средства на OpenAI аккаунте

### Тестирование вручную
Вы можете протестировать команды вручную:
```bash
# Проверка установки
gemini --version

# Проверка аутентификации
gemini -p "test"

# Тест с сообщением
gemini -p "Привет! Как дела?"
```

## Логи

Все сообщения сохраняются в `logs/history.txt` в формате:
```
USER 123456789: Привет, как дела?
GEMINI: Привет! У меня все хорошо, спасибо за вопрос...
---
```

## Технические детали

### Команды Gemini CLI
Каждое сообщение выполняется как:
```powershell
powershell.exe -Command 'gemini -p "экранированное_сообщение"'
```

### Экранирование
Кавычки в сообщениях экранируются: `"` → `""`

### Фильтрация ответов
Убираются системные сообщения:
- `DeprecationWarning`
- `punycode`
- `(node:`
- Символы рамок: `┌`, `│`, `└`

### Таймауты
- Проверка установки: 10 секунд
- Проверка аутентификации: 15 секунд  
- Отправка сообщения: 60 секунд

## Преимущества новой архитектуры

✅ **Простота**: Один вызов subprocess.run() вместо сложных потоков  
✅ **Надежность**: Каждая команда изолирована  
✅ **Отладка**: Легко воспроизвести любую команду вручную  
✅ **Производительность**: Нет постоянных процессов в фоне  
✅ **Стабильность**: Нет проблем с зависшими потоками

---

## Telecodex (Telegram → Codex bridge)

A pinned submodule at `vendor/telecodex` provides a Telegram bot that forwards
messages to the OpenAI Codex CLI SDK with a workspace-write sandbox.

### Recommended runtime

| Component | Requirement |
|-----------|-------------|
| Node.js   | **22 LTS** (minimum) |
| codex CLI | `npm install -g @openai/codex` |
| TELEGRAM_BOT_TOKEN | From @BotFather |
| OPENAI_API_KEY | For Whisper voice transcription on Windows |

### Quick start

```powershell
# 1. Build submodule (first time only)
.\scripts\setup-telecodex.ps1

# 2. Fill in secrets
notepad .env

# 3. Launch
.\scripts\start-telecodex.ps1
```

See [docs/telecodex-integration.md](docs/telecodex-integration.md) for full
setup, BotFather configuration, Codex login, Windows voice setup, security
defaults, and upgrade instructions.
