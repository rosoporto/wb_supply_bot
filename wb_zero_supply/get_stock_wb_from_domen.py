import os
import json
import requests
from dotenv import load_dotenv
from datetime import datetime
import logging


# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_stock_wb_from_domen(stores, domain, cookie):
    if not cookie:
        logging.error("Cookie не задано.")
        return None

    data = []
    session = requests.Session()
    for store_name, store_id in stores.items():
        url = f'https://{domain}/wp-admin/admin-ajax.php?action=get_limit_store&id={store_id}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Cookie': cookie
        }

        response = session.get(url, headers=headers)
        try:
            response.raise_for_status()  # Проверка на ошибки HTTP
            stocks = response.json()  # Безопасное получение JSON-данных
        except requests.HTTPError as e:
            logging.error(f'HTTP error occurred: {e}')  # Обработка ошибок
            continue  # Переход к следующему складу
        except json.JSONDecodeError:
            logging.error('Ошибка декодирования JSON. Ответ сервера не является корректным JSON.')
            continue  # Переход к следующему складу
        except Exception as e:
            logging.error(f'An error occurred: {e}')  # Обработка других ошибок
            continue  # Переход к следующему складу

        data.append({store_name: stocks})

    return data


def check_stock(stores, data):
    messages = []
    for stock in data:
        for stock_name, stock_data in stock.items():
            if stock_name in stores:  # Проверяем, что склад есть в списке
                for delivery_type, deliveries in stock_data.items():
                    for item in deliveries:
                        if item.get('coefficient') == 0:  # Используем get для безопасного доступа
                            date = datetime.strptime(item['date'], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
                            message = (f'Бесплатный слот для приемки\n'
                                       f'Склад: {stock_name},\n'
                                       f'Дата: {date},\n'
                                       f'Тип поставки: {delivery_type}')
                            messages.append(message)

    return messages if messages else False


def main():
    load_dotenv()
    stores = {
        'Тула': int(os.getenv('STORES_TULA')),
        'Электросталь': int(os.getenv('STORES_ELECTROSTAL'))
    }
    domain = os.getenv('DOMAIN')
    cookie = os.getenv('COOKIE')

    result = get_stock_wb_from_domen(stores, domain, cookie)
    if result is None:
        logging.error('Не удалось выполнить проверку из-за отсутствия cookie.')
    else:
        messages = check_stock(stores, result)
        if not messages:
            logging.info('Бесплатных слотов для приемки нет.')
        else:
            logging.info('\n'.join(messages))  # Исправлено на messages


if __name__ == '__main__':
    main()
