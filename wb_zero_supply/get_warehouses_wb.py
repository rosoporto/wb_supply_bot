import os
import time
import requests
import logging
from functools import wraps
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def cache_daily(func):
    """Декоратор для кэширования результата функции на 24 часа."""
    cache = {}

    @wraps(func)
    def wrapper(*args, **kwargs):
        current_time = time.time()
        if not cache or current_time - cache['timestamp'] > 86400:  # 86400 секунд = 24 часа
            result = func(*args, **kwargs)
            if result is not None:  # Кэшируем только успешные результаты
                cache['result'] = result
                cache['timestamp'] = current_time
            return result
        return cache['result']
    return wrapper


@cache_daily
def get_warehouses_wb(wb_api_token):
    url = 'https://supplies-api.wildberries.ru/api/v1/warehouses'

    headers = {
        'Authorization': f'Bearer {wb_api_token}',  # Добавляем токен в заголовок Authorization
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Проверка на ошибки HTTP
    except requests.exceptions.HTTPError as http_err:
        error_messages = {
            401: "Ошибка авторизации: Убедитесь, что ваши учетные данные верны.",
            403: "Доступ запрещён: У вас нет прав для доступа к этому ресурсу.",
            404: "Адрес не найден: Проверьте правильность URL.",
            429: "Слишком много запросов: Попробуйте позже.",
            500: "Внутренняя ошибка сервера: Попробуйте позже."
        }
        logging.error(error_messages.get(response.status_code, f"Произошла ошибка: {http_err}"))
        return None
    except requests.exceptions.RequestException as err:
        print(f"Произошла ошибка при выполнении запроса: {err}")
        return None
    else:
        # Если запрос успешен, обрабатываем ответ
        warehouses = response.json()  # Возвращаем данные в формате JSON
        return warehouses


def frequent_caller(wb_api_token):
    """Функция, которая будет часто вызывать get_warehouses_wb"""
    while True:
        data = get_warehouses_wb(wb_api_token)
        if data:
            print(f"Получены данные о складах. Количество складов: {len(data)}")
        else:
            print("Не удалось получить данные о складах.")
        time.sleep(12)  # Пауза на 12 секунд


def get_id_warehouse_wb_by_name(wb_api_token, name='Тула'):
    warehouses = get_warehouses_wb(wb_api_token)
    name = name.strip()
    for warehouse in warehouses:
        if warehouse['name'] == name:
            return f"ID склада {name}: {warehouse['ID']}"
    return None


def main():
    load_dotenv()
    wb_api_token = os.getenv('WB_API_SUPPLY')
    num_func = int(input("Ввидите значение (1-Все склады, 2-Поиск id склада по имени): "))

    match num_func:
        case 1:
            result = get_warehouses_wb(wb_api_token)
            logging.info(result)
        case 2:
            name_warehous = input("Ввидите имя интересующего склада: ")
            result = get_id_warehouse_wb_by_name(wb_api_token, name_warehous)
            if result is None:
                logging.warning(f"ID склада с именем '{name_warehous}' не найден")
            else:
                logging.info(result)
        case 3:
            frequent_caller(wb_api_token)
        case _:
            logging.warning(f"Значение {num_func} не найдено")


if __name__ == '__main__':
    main()
