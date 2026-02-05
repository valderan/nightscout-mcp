# Nightscout MCP Server

Доступ к данным CGM из [Nightscout](https://nightscout.github.io/) в ассистентах (Claude, Cursor и др.).

Важно: MCP оптимизирован для Nightscout версии 14+.

## Быстрый старт

```bash
uvx --from git+https://github.com/vgmakeev/nightscout-mcp nightscout-mcp
```

## Настройка

Добавьте в MCP конфиг (например, `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "nightscout": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/vgmakeev/nightscout-mcp", "nightscout-mcp"],
      "env": {
        "NIGHTSCOUT_URL": "https://YOUR_TOKEN@your-site.nightscout.com",
        "LOCALE": "ru"
      }
    }
  }
}
```

## Конфигурация

| Переменная | Описание | По умолчанию |
|----------|-------------|---------|
| `NIGHTSCOUT_URL` | URL Nightscout (можно с токеном: `https://token@site.com`) | Обязательно |
| `NIGHTSCOUT_API_SECRET` | API secret (опционально, если используется токен в URL) | - |
| `GLUCOSE_UNITS` | Единицы отображения: `mmol` или `mgdl` | `mmol` |
| `GLUCOSE_LOW` | Нижняя граница диапазона TIR (авто-определение единиц: <30 = mmol) | `3.9` (70 mg/dL) |
| `GLUCOSE_HIGH` | Верхняя граница диапазона TIR (авто-определение единиц: <30 = mmol) | `7.8` (140 mg/dL) |
| `LOCALE` | Язык вывода: `en` или `ru` | `en` |

### Пример с пользовательским диапазоном TIR

```json
{
  "nightscout": {
    "command": "uvx",
    "args": ["--from", "git+https://github.com/vgmakeev/nightscout-mcp", "nightscout-mcp"],
    "env": {
      "NIGHTSCOUT_URL": "https://TOKEN@your-site.nightscout.com",
      "GLUCOSE_UNITS": "mmol",
      "GLUCOSE_LOW": "4.0",
      "GLUCOSE_HIGH": "10.0",
      "LOCALE": "ru"
    }
  }
}
```

## Локальная разработка (.env)

Создайте `.env` в корне репозитория (он уже в `.gitignore`) или скопируйте `.env.example` и отредактируйте:

```bash
cp .env.example .env
```

Запуск сервера:

```bash
./start-server.sh
```

Запуск клиента:

```bash
./start-client.sh
```

## Клиент для проверки

Локальный клиент запускается в интерактивном режиме и позволяет вызвать любой инструмент или все сразу:

```bash
uv run python scripts/test_client.py
```

## Инструменты

| Инструмент | Описание |
|------|-------------|
| `glucose_current` | Текущее значение глюкозы |
| `glucose_history` | История за последние N часов |
| `analyze` | TIR, CV, HbA1c за любой период |
| `analyze_monthly` | Помесячная аналитика за год |
| `treatments` | Инсулин и углеводы |
| `status` | Статус Nightscout |
| `devices` | Статус помпы, CGM, загрузчика |

## Примеры

Попросите ассистента:
1. "Какая сейчас глюкоза?"
2. "Покажи историю глюкозы за последние 6 часов"
3. "Проанализируй декабрь 2025"
4. "Сделай помесячный разбор за 2025"

## Лицензия

MIT
