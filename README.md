# USPhoneBook Scraper

Docker-скрапер для USPhoneBook.com с автоматическим обходом Cloudflare Turnstile.

## Особенности

- **Автоматический обход Cloudflare Turnstile** через Xvfb + nodriver-cf-verify
- **SOCKS5 прокси** с поддержкой US IP (SOAX)
- **Docker** — работает на любом сервере без GUI
- **Извлечение данных:** ФИО, телефоны, адреса, родственники

## Требования

- Docker + Docker Compose
- US прокси (SOCKS5) — без US IP сервис не работает

## Быстрый старт

```bash
# Сборка образа
docker compose build

# Запуск скрапинга
docker compose run --rm scraper 828-685-1514
```

## Результаты

Результаты сохраняются в `results/`:
- `result_XXXXXXXXXX.json` — данные в JSON
- `result_XXXXXXXXXX.png` — скриншот страницы
- `debug_XXXXXXXXXX.html` — HTML для отладки

### Пример результата

```json
{
  "full_name": "Angela Murray",
  "phones": ["828-685-1514"],
  "addresses": [
    "22 Treemont Ln, Hendersonville, NC 28792",
    "26 Stepp Mill Rd, Hendersonville, NC 28792"
  ],
  "relatives": [
    "Bobby Hylemon",
    "Diane Patterson",
    "Lillian Hawkins"
  ],
  "status": "success"
}
```

## Конфигурация

### Прокси

По умолчанию используется SOAX прокси. Для замены установите переменную окружения:

```bash
# В docker-compose.yml
environment:
  - PROXY_URL=socks5://user:pass@proxy.example.com:1080
```

Формат с сессией (для ротации IP):
```
socks5://user-sessionid-{session}:pass@proxy.example.com:1080
```

## Структура проекта

```
.
├── Dockerfile           # Docker образ с Chrome + Xvfb
├── docker-compose.yml   # Конфигурация Docker Compose
├── scraper.py          # Основной скрипт скрапера
├── nodriver_cf_verify/ # Модуль для обхода Cloudflare
├── requirements.txt    # Python зависимости
└── results/            # Результаты скрапинга
```

## Технологии

- **nodriver** — автоматизация Chrome без детекта
- **nodriver-cf-verify** — автоматический обход Cloudflare Turnstile
- **Xvfb** — виртуальный дисплей (обход headless-детекции)
- **loguru** — логирование

## Лицензия

Private / Internal Use Only
