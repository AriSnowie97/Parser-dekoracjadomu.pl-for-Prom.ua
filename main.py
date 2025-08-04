from playwright.sync_api import sync_playwright, TimeoutError
import pandas as pd
import time

def parse_products_to_excel():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("⏳ Загружаем страницу...")
        page.goto("https://dekoracjadomu.pl/marka/atmosphera?page=2", wait_until="networkidle", timeout=60000)

        time.sleep(5)  # Дополнительная пауза на загрузку JS

        try:
            page.wait_for_selector("article.product-miniature.js-product-miniature", timeout=30000)
        except TimeoutError:
            print("❌ Не удалось загрузить товары.")
            browser.close()
            return

        products = page.query_selector_all("article.product-miniature.js-product-miniature")
        print(f"Найдено товаров: {len(products)}")

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
            except Exception as e:
                print(f"Ошибка при обработке товара: {e}")

        browser.close()

        if data:
            df = pd.DataFrame(data)
            df.to_excel("products_with_images.xlsx", index=False)
            print("✅ Данные с фото сохранены в файл products_with_images.xlsx")
        else:
            print("⚠️ Нет данных для сохранения.")

if __name__ == "__main__":
    parse_products_to_excel()
