import os
import requests
from dotenv import load_dotenv
from datetime import datetime
import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_stock_wb_from_api(wb_api_token, stores=None):
    url = 'https://supplies-api.wildberries.ru/api/v1/acceptance/coefficients'

    headers = {
        'Authorization': f'Bearer {wb_api_token}',  # Добавляем токен в заголовок Authorization
    }

    params = {}
    if stores:
        # Извлекаем идентификаторы складов из словаря stores
        warehouse_ids = list(stores.values())
        if warehouse_ids:
            params['warehouseIDs'] = ','.join(map(str, warehouse_ids))  # Преобразуем список в строку

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Проверка на ошибки HTTP

        # Успешный ответ
        coefficients = response.json()  # Возвращаем данные в формате JSON
        return coefficients
    except requests.HTTPError as e:
        if response.status_code == 400:
            error_info = response.json()
            logging.error(f"Ошибка 400: {error_info['title']} - {error_info['detail']}")
        else:
            logging.error(f'HTTP error occurred: {e}')  # Обработка других ошибок
    except Exception as e:
        logging.error(f'An error occurred: {e}')  # Обработка других ошибок

    return None  # Возвращаем None в случае ошибки


def check_all_coefficients(coefficients):
    if coefficients:
        for coefficient in coefficients:
            date = datetime.strptime(coefficient['date'], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
            print(f"Дата: {date}, "
                  f"Склад: {coefficient['warehouseName']}, "
                  f"Коэффициент: {coefficient['coefficient']}, "                  
                  f"Тип поставки: {coefficient.get('boxTypeName', 'Не указано')}")
    else:
        print('Не удалось получить коэффициенты приёмки.')


def check_zero_coefficients(coefficients):
    messages = []
    for coefficient in coefficients:
        if coefficient['coefficient'] == 0 and coefficient.get('boxTypeName') == 'Короба':
            date = datetime.strptime(coefficient['date'], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
            message = (f"Склад: {coefficient['warehouseName']}, "
                       f"Дата: {date}, "
                       f"Тип поставки: {coefficient['boxTypeName']}")
            messages.append(message)
    return messages


def main():
    load_dotenv()
    stores = {
        'Тула': 206348,
        'СЦ Пушкино': 207743,
        'Электросталь': 120762
    }
    wb_api_token = os.getenv('WB_API_SUPPLY')

    coefficients = get_stock_wb_from_api(wb_api_token, stores)
    if coefficients:
        messages = check_zero_coefficients(coefficients)
        if messages:
            for message in messages:
                print(message)
        else:
            print('Нет поставок с коэффициентом 0 для типа "Короба".')
    else:
        print('Не удалось получить коэффициенты приёмки.')


if __name__ == '__main__':
    main()
