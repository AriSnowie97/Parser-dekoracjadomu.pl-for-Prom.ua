import telebot
import os
import pandas as pd
import time
import threading
import sys
from uuid import uuid4
from playwright.sync_api import sync_playwright, TimeoutError

BOT_TOKEN = "BOT_TOKEN"
bot = telebot.TeleBot(BOT_TOKEN)

user_state = {}

@bot.message_handler(commands=["start"])
def start_cmd(message):
    user_state[message.chat.id] = None  # сброс
    bot.send_message(message.chat.id, (
        "👋 Привет! Я бот-парсер товаров с сайта dekoracjadomu.pl\n\n"
        "🔧 Команды:\n"
        "/parsing_catalogs – парсинг всех товаров из каталога\n"
        "/parsing_product – парсинг одной карточки товара\n"
        "/stop – выключение бота (остановка процесса)\n\n"
        "После выбора команды отправь ссылку 🔗"
    ))

@bot.message_handler(commands=["parsing_catalogs"])
def parse_catalog_cmd(message):
    user_state[message.chat.id] = "catalog"
    bot.send_message(message.chat.id, "📥 Жду ссылку на каталог товаров.")

@bot.message_handler(commands=["parsing_product"])
def parse_product_cmd(message):
    user_state[message.chat.id] = "product"
    bot.send_message(message.chat.id, "📥 Жду ссылку на карточку товара.")

@bot.message_handler(commands=["stop"])
def shutdown_cmd(message):
    bot.send_message(message.chat.id, "🛑 Бот выключается...")
    user_state[message.chat.id] = None

    def shutdown():
        time.sleep(1)
        print("❌ Бот выключен")
        os._exit(0)  # жёсткое завершение процесса

    threading.Thread(target=shutdown).start()

@bot.message_handler(func=lambda m: True)
def handle_link(message):
    text = message.text.strip()
    state = user_state.get(message.chat.id)

    if text.startswith("http"):
        if state == "catalog":
            bot.send_message(message.chat.id, "⏳ Парсю каталог...")
            try:
                file_path = parse_catalog_to_excel(text)
                send_excel_or_path(bot, message, file_path)
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Ошибка при парсинге каталога: {e}")
            user_state[message.chat.id] = None  # сброс

        elif state == "product":
            bot.send_message(message.chat.id, "⏳ Парсю карточку товара...")
            try:
                file_path = parse_single_product_to_excel(text)
                send_excel_or_path(bot, message, file_path)
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Ошибка при парсинге товара: {e}")
            user_state[message.chat.id] = None  # сброс

        else:
            bot.send_message(message.chat.id, "❗ Сначала выбери команду:\n/парсить_каталоги или /парсить_карточку")
    else:
        bot.send_message(message.chat.id, "⚠️ Это не ссылка. Пожалуйста, отправь корректную ссылку, начиная с http.")

def send_excel_or_path(bot, message, filepath):
    try:
        with open(filepath, 'rb') as f:
            bot.send_document(message.chat.id, f)
        os.remove(filepath)
    except:
        bot.send_message(message.chat.id, f"✅ Файл сохранён локально: {filepath}")

def parse_catalog_to_excel(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(5)

        page.wait_for_selector("article.product-miniature.js-product-miniature", timeout=30000)
        products = page.query_selector_all("article.product-miniature.js-product-miniature")

        data = []
        for product in products:
            try:
                name_el = product.query_selector("h2.product-title a")
                price_el = product.query_selector("span.price")
                img_el = product.query_selector("a.thumbnail.product-thumbnail img")

                if not name_el or not price_el:
                    continue

                name = name_el.inner_text().strip()
                link = name_el.get_attribute("href")
                price = price_el.inner_text().strip()
                img_url = img_el.get_attribute("data-src") or img_el.get_attribute("src") if img_el else None

                data.append({
                    "Название": name,
                    "Ссылка": link,
                    "Цена": price,
                    "Фото": img_url
                })
            except:
                continue

        browser.close()
        filename = f"catalog_{uuid4().hex}.xlsx"
        pd.DataFrame(data).to_excel(filename, index=False)
        return filename

def parse_single_product_to_excel(url: str) -> str:
    from uuid import uuid4
    import pandas as pd
    import time
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(5)

        def safe_text(sel):
            el = page.query_selector(sel)
            return el.inner_text().strip() if el else "—"

        name = safe_text("h1")  # Заголовок скорее всего в h1
        sku = safe_text("text=Numer katalogowy ~ span")  # Точный путь может отличаться
        price = safe_text("text= zł")  # можно уточнить через unique selector
        description = safe_text("section:has-text(\"Opis\")")
        specs = safe_text("section:has-text(\"Specyfikacja\")")
        
        images = page.query_selector_all("img")
        image_urls = [img.get_attribute("src") or img.get_attribute("data-src") for img in images][:3]

        data = {
            "Название": name,
            "Артикул": sku,
            "Цена": price,
            "Описание": description,
            "Спецификация": specs,
            "Фото 1": image_urls[0] if len(image_urls) > 0 else "",
            "Фото 2": image_urls[1] if len(image_urls) > 1 else "",
            "Фото 3": image_urls[2] if len(image_urls) > 2 else "",
            "Ссылка": url
        }
        df = pd.DataFrame([data])
        filename = f"product_{uuid4().hex}.xlsx"
        df.to_excel(filename, index=False)
        browser.close()
        return filename

print("✅ Бот запущен")
bot.polling(none_stop=True)
