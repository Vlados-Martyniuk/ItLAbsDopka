import json
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urljoin, urlparse
import time

# Ключові слова для пошуку в банерах та кнопках
COOKIE_BANNER_KEYWORDS = ['cookie', 'consent', 'privacy', 'gdpr', 'рекомендації', 'файли cookie']
ACCEPT_KEYWORDS = ['accept', 'agree', 'ok', 'allow all', 'прийняти', 'погоджуюсь', 'дозволити всі']
REJECT_KEYWORDS = ['reject', 'decline', 'deny', 'necessary only', 'відхилити', 'відмовитись']
POLICY_KEYWORDS = ['privacy & cookies','privacy policy', 'cookie policy', 'політика приватності','політика конфіденційності', 'умови використання сайту', 'політика cookie', 'угода користувача', 'персональні дані']

#Основна функція для аналізу веб-сайту.
def analyze_website(url):
    results = {
        'url': url,
        'scan_results': {},
        'compliance_score': 0,
        'summary': []
    }

    # Налаштування для Selenium
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080") 
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    options.add_experimental_option('excludeSwitches', ['enable-logging']) 
    driver = None
    try:
        print(f"Запускаємо браузер і відкриваємо {url}...")
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        
        # Встановлюємо тайм-аут, щоб сторінка встигла повністю завантажитись
        driver.set_page_load_timeout(20)
        driver.get(url)
        
        # Даємо трохи часу на появу динамічних елементів (банера)
        time.sleep(3) 

        #1. Перевірка початкових cookies
        print("Перевірка початкових cookies (до взаємодії)")
        initial_cookies = driver.get_cookies()
        non_essential_cookies_found = any(
            'ga' in c['name'] or 'fbp' in c['name'] or 'analytics' in c['name']
            for c in initial_cookies
        )
        results['scan_results']['initial_cookies_check'] = {
            'cookies_found_on_load': len(initial_cookies),
            'non_essential_cookies_likely_present': non_essential_cookies_found,
            'details': [c['name'] for c in initial_cookies]
        }
        if not non_essential_cookies_found and len(initial_cookies) < 5:
            results['compliance_score'] += 40
            results['summary'].append("Добре: Несуттєві cookie, ймовірно, не встановлюються до згоди.")
        else:
            results['summary'].append(f"Проблема: Схоже, що відстежуючі або аналітичні cookie встановлюються до отримання згоди. Знайдено {len(initial_cookies)} cookie.")

        #2. Аналіз HTML-контенту 
        print("Отримання та аналіз HTML-коду сторінки")
        page_source = driver.page_source  
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Перевіряємо, чи є тіло сторінки
        if soup.body is None:
            raise Exception("Не вдалося отримати тіло сторінки (body). Можливо, сторінка завантажилась некоректно.")

        body_text = soup.body.get_text().lower()

        #3. Пошук cookie-банера 
        has_banner = any(keyword in body_text for keyword in COOKIE_BANNER_KEYWORDS)
        results['scan_results']['cookie_banner_found'] = has_banner
        if has_banner:
            results['compliance_score'] += 15
            results['summary'].append("Інформація: Знайдено банер або текст, що згадує cookie.")
        else:
            results['summary'].append("Проблема: Не знайдено явного cookie-банера на сторінці.")

        #4. Аналіз кнопок у банері 
        links_and_buttons = soup.find_all(['a', 'button'])
        found_accept = any(any(kw in str(tag.get_text()).lower() for kw in ACCEPT_KEYWORDS) for tag in links_and_buttons)
        found_reject = any(any(kw in str(tag.get_text()).lower() for kw in REJECT_KEYWORDS) for tag in links_and_buttons)

        results['scan_results']['banner_buttons'] = {
            'accept_button_found': found_accept,
            'reject_button_found': found_reject
        }
        if found_accept: results['compliance_score'] += 10
        if found_reject:
            results['compliance_score'] += 25
            results['summary'].append("Добре: Знайдено кнопку для відмови/відхилення.")
        else:
            results['summary'].append("Проблема: Відсутня чітка кнопка для відмови від несуттєвих cookie.")

        #5. Пошук посилання на політику конфіденційності/cookie 
        policy_link = None
        for a in soup.find_all('a', href=True):
            if any(keyword in a.get_text().lower() for keyword in POLICY_KEYWORDS):
                policy_link = urljoin(url, a['href'])
                break
        
        results['scan_results']['policy_link_found'] = bool(policy_link)
        if policy_link:
            results['scan_results']['policy_link_url'] = policy_link
            results['compliance_score'] += 10
            results['summary'].append(f"Добре: Знайдено посилання на політику: {policy_link}")
        else:
            results['summary'].append("Проблема: Не знайдено посилання на політику конфіденційності або cookie.")

    except Exception as e:
        results['error'] = f"Сталася невідома помилка: {e}"
    finally:
        if driver:
            driver.quit()  
            print("Браузер закрито.")

    return results

if __name__ == "__main__":
    # ВКАЖІТЬ САЙТ ДЛЯ ПЕРЕВІРКИ ТУТ 
    target_url = "https://privatbank.ua/" 
    
    # Запускаємо аналіз
    analysis_results = analyze_website(target_url)

    # Генеруємо ім'я файлу на основі домену сайту
    output_filename = f"report_{urlparse(target_url).netloc.replace('.', '_')}.json"
    
    # Зберігаємо результати у файл JSON
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(analysis_results, f, indent=4, ensure_ascii=False)

    print(f"\nАналіз завершено. Результати збережено у файл {output_filename}")
    print("\nПідсумковий звіт:")
    print(json.dumps(analysis_results, indent=4, ensure_ascii=False))
   