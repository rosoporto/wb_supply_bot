import os
import json
import requests
from dotenv import load_dotenv
from datetime import datetime
import logging


# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def check_stock_wb(stores, domain, cookie):
    messages = []
    session = requests.Session()

    if not cookie:
        logging.error("Cookie не задано.")
        return None

    for store_name, store_id in stores.items():
        url = f'https://{domain}/wp-admin/admin-ajax.php?action=get_limit_store&id={store_id}'
        logging.info(f'Запрос к URL: {url}')

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Cookie': cookie
        }

        response = session.get(url, headers=headers)
        try:
            response.raise_for_status()  # Проверка на ошибки HTTP
            data = response.json()  # Безопасное получение JSON-данных
        except requests.HTTPError as e:
            logging.error(f'HTTP error occurred: {e}')  # Обработка ошибок
            continue  # Переход к следующему складу
        except json.JSONDecodeError:
            logging.error('Ошибка декодирования JSON. Ответ сервера не является корректным JSON.')
            continue  # Переход к следующему складу
        except Exception as e:
            logging.error(f'An error occurred: {e}')  # Обработка других ошибок
            continue  # Переход к следующему складу

        if 'koroba' in data:
            for item in data['koroba']:
                if item['coefficient'] == 0:
                    date = datetime.strptime(item['date'], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
                    message = f'Склад: {store_name}\nДата: {date}\nКоэффициент для "koroba" равен 0'
                    messages.append(message)
        else:
            logging.warning(f'Нет данных для склада: {store_name}')

    return False if not messages else messages


def main():
    load_dotenv()
    stores = {
        'Тула': int(os.getenv('STORES_TULA')),
        'Электросталь': int(os.getenv('STORES_ELECTROSTAL'))
    }
    domain = os.getenv('DOMAIN')
    cookie = os.getenv('COOKIE')

    result = check_stock_wb(stores, domain, cookie)
    if result is None:
        logging.error('Не удалось выполнить проверку из-за отсутствия cookie.')
    elif not result:
        logging.info('Бесплатных слотов для приемки нет.')
    else:
        print('\n'.join(result))


if __name__ == '__main__':
    main()
