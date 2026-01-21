"""
USPhoneBook Scraper для Docker с Xvfb.
Использует nodriver-cf-verify для автоматического прохождения Cloudflare.
"""

import asyncio
import json
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import nodriver as uc
from loguru import logger

# Попытка импорта nodriver-cf-verify
try:
    from nodriver_cf_verify import CFVerify
    HAS_CF_VERIFY = True
except ImportError:
    HAS_CF_VERIFY = False
    logger.warning("nodriver-cf-verify не установлен, Turnstile будет ждать вручную")

# Конфигурация через переменные окружения
PROXY_TEMPLATE = os.getenv("PROXY_URL")
if not PROXY_TEMPLATE:
    raise ValueError("PROXY_URL environment variable is required. Example: socks5://user:pass@proxy:port")

OUTPUT_DIR = Path("results")
OUTPUT_DIR.mkdir(exist_ok=True)


def get_proxy() -> str:
    """Генерация прокси с уникальной сессией."""
    session = f"{random.randint(10000000, 99999999):08x}"
    return PROXY_TEMPLATE.format(session=session)


async def handle_cloudflare(tab) -> bool:
    """Обработка Cloudflare Turnstile через nodriver-cf-verify."""
    if not HAS_CF_VERIFY:
        logger.info("Ждём прохождение Cloudflare вручную...")
        await asyncio.sleep(10)
        return True

    try:
        cf_verify = CFVerify(_browser_tab=tab, _debug=True)
        success = await cf_verify.verify(_max_retries=20, _interval_between_retries=1)
        if success:
            logger.success("Cloudflare Turnstile пройден!")
            return True
        else:
            logger.warning("Не удалось пройти Cloudflare")
            return False
    except Exception as e:
        logger.error(f"Ошибка CFVerify: {e}")
        return False


async def wait_for_page_load(tab, timeout: int = 90) -> bool:
    """Ожидание загрузки страницы."""
    for i in range(timeout):
        await asyncio.sleep(1)
        try:
            content = await tab.get_content()

            # Проверка на Cloudflare
            if "challenges.cloudflare" in content or "turnstile" in content.lower():
                if i == 3:
                    logger.info("Обнаружен Cloudflare Turnstile, пробуем пройти...")
                    await handle_cloudflare(tab)
                continue

            # Страница загружена
            if "usphonebook" in content.lower() and len(content) > 10000:
                indicators = ["captcha", "just a moment", "checking your browser"]
                if not any(ind in content.lower() for ind in indicators):
                    logger.success(f"Страница загружена за {i+1} сек")
                    return True
        except Exception:
            pass

    return False


async def close_popups(tab) -> None:
    """Закрытие попапов."""
    try:
        agree = await tab.find("I Agree", timeout=2)
        if agree:
            await agree.click()
            await asyncio.sleep(1)
    except Exception:
        pass

    try:
        await tab.send(uc.cdp.input_.dispatch_key_event(
            type_="keyDown", key="Escape", code="Escape", windows_virtual_key_code=27
        ))
    except Exception:
        pass


async def extract_data(tab) -> dict[str, Any]:
    """Извлечение данных."""
    data = {"url": tab.target.url, "scraped_at": datetime.now().isoformat()}

    try:
        content = await tab.get_content()

        # Имя
        given = re.search(r'itemprop="givenName"[^>]*>([^<]+)<', content)
        family = re.search(r'itemprop="familyName"[^>]*>([^<]+)<', content)
        if given and family:
            data["full_name"] = f"{given.group(1).strip()} {family.group(1).strip()}"

        # Телефоны
        phones = set()
        for m in re.findall(r'\((\d{3})\)\s*(\d{3})[-.\\s](\d{4})', content):
            phones.add(f"{m[0]}-{m[1]}-{m[2]}")
        for m in re.findall(r'(\d{3})[-.\\s](\d{3})[-.\\s](\d{4})', content):
            phones.add(f"{m[0]}-{m[1]}-{m[2]}")
        if phones:
            data["phones"] = list(phones)

        # Адреса
        addresses = set()
        for m in re.findall(r'(\d+\s+[\w\s]+(?:St|Ave|Rd|Dr|Ln|Blvd|Way|Ct|Pl)[.,]?\s+[\w\s]+,\s*[A-Z]{2}\s+\d{5})', content, re.I):
            if len(m) > 10 and "Search By" not in m:
                addresses.add(m.strip())
        if addresses:
            data["addresses"] = list(addresses)[:5]

        # Родственники
        relatives = []
        for m in re.finditer(r'itemprop="relatedTo"[^>]*>.*?itemprop="name"[^>]*>([^<]+)<', content, re.DOTALL):
            name = m.group(1).strip()
            if name and name not in relatives:
                relatives.append(name)
        if relatives:
            data["relatives"] = relatives[:15]

        data["_content_length"] = len(content)
    except Exception as e:
        data["_error"] = str(e)

    return data


async def scrape_phone(phone: str) -> dict | None:
    """Скрапинг номера телефона."""
    phone_clean = re.sub(r"[^\d]", "", phone)
    phone_fmt = f"{phone_clean[:3]}-{phone_clean[3:6]}-{phone_clean[6:]}" if len(phone_clean) == 10 else phone

    search_url = f"https://www.usphonebook.com/phone-search/{phone_fmt}"
    logger.info(f"Скрапинг: {phone_fmt}")

    browser = None
    try:
        # Запуск браузера (НЕ headless - используем Xvfb)
        browser = await uc.start(headless=False)

        # Создаём контекст с прокси
        proxy = get_proxy()
        proxy_url = proxy.replace("socks5://", "socks://")
        logger.info(f"Прокси: {proxy_url[:50]}...")

        tab = await browser.create_context(
            url="https://www.usphonebook.com/",
            proxy_server=proxy_url,
        )

        # Закрываем лишнюю вкладку
        try:
            if browser.main_tab and browser.main_tab.target_id != tab.target_id:
                await browser.main_tab.close()
        except Exception:
            pass

        logger.info("Ожидаем загрузку...")
        if not await wait_for_page_load(tab, timeout=90):
            logger.warning("Таймаут главной страницы")
            try:
                await tab.save_screenshot(str(OUTPUT_DIR / f"debug_{phone_clean}_main.png"))
            except Exception:
                pass

        await close_popups(tab)
        await asyncio.sleep(random.uniform(2, 4))

        # Переход на страницу поиска
        logger.info(f"Переход: {search_url}")
        await tab.get(search_url)

        if not await wait_for_page_load(tab, timeout=90):
            logger.warning("Таймаут страницы поиска")

        await close_popups(tab)

        # Сохраняем HTML для отладки
        content = await tab.get_content()
        with open(OUTPUT_DIR / f"debug_{phone_clean}.html", "w", encoding="utf-8") as f:
            f.write(content)

        if "no results" in content.lower():
            return {"phone": phone_fmt, "status": "not_found"}

        data = await extract_data(tab)
        data["phone_searched"] = phone_fmt
        data["status"] = "success"

        # Скриншот результата
        try:
            await tab.save_screenshot(str(OUTPUT_DIR / f"result_{phone_clean}.png"))
        except Exception:
            pass

        logger.success(f"Успешно: {data.get('full_name', 'данные получены')}")
        return data

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return {"phone": phone_fmt, "status": "error", "error": str(e)}

    finally:
        if browser:
            try:
                browser.stop()
            except Exception:
                pass


async def main():
    # Получаем номер из аргументов или используем тестовый
    phone = sys.argv[1] if len(sys.argv) > 1 else "828-685-1514"

    result = await scrape_phone(phone)

    if result:
        output_file = OUTPUT_DIR / f"result_{phone.replace('-', '')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"Сохранено: {output_file}")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
