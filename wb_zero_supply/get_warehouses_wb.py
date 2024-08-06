import os
import time
import requests
import logging
from functools import wraps
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def cache_with_fallback(expiration=86400):  # 86400 секунд = 24 часа
    """Декоратор для кэширования результата функции с механизмом обновления в случае ошибки."""
    def decorator(func):
        cache = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            
            # Проверяем, нужно ли обновить кэш
            if not cache or current_time - cache['timestamp'] > expiration:
                try:
                    result = func(*args, **kwargs)
                    if result is not None:
                        cache['result'] = result
                        cache['timestamp'] = current_time
                        cache['error'] = None
                    return result
                except Exception as e:
                    logging.error(f"Ошибка при обновлении кэша: {e}")
                    if 'result' in cache:
                        logging.info("Используем предыдущие кэшированные данные")
                        cache['error'] = str(e)
                        return cache['result']
                    raise  # Если нет кэшированных данных, пробрасываем исключение
            
            # Если кэш актуален, возвращаем кэшированный результат
            return cache['result']

        # Добавляем метод для принудительного обновления кэша
        def force_update(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                if result is not None:
                    cache['result'] = result
                    cache['timestamp'] = time.time()
                    cache['error'] = None
                return result
            except Exception as e:
                logging.error(f"Ошибка при принудительном обновлении кэша: {e}")
                cache['error'] = str(e)
                raise

        wrapper.force_update = force_update
        return wrapper

    return decorator


@cache_with_fallback(expiration=86400)  # Кэш на 24 часа
def get_warehouses_wb(wb_api_token):
    url = 'https://supplies-api.wildberries.ru/api/v1/warehouses'

    headers = {
        'Authorization': f'Bearer {wb_api_token}',
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        error_messages = {
            401: "Ошибка авторизации: Убедитесь, что ваши учетные данные верны.",
            403: "Доступ запрещён: У вас нет прав для доступа к этому ресурсу.",
            404: "Адрес не найден: Проверьте правильность URL.",
            429: "Слишком много запросов: Попробуйте позже.",
            500: "Внутренняя ошибка сервера: Попробуйте позже."
        }
        logging.error(error_messages.get(response.status_code, f"Произошла ошибка: {http_err}"))
        raise
    except requests.exceptions.RequestException as err:
        logging.error(f"Произошла ошибка при выполнении запроса: {err}")
        raise
    else:
        warehouses = response.json()
        return warehouses


def get_id_warehouse_wb_by_name(wb_api_token: str, name='Тула') -> dict[str, int]:
    try:
        warehouses = get_warehouses_wb(wb_api_token)
        name = name.strip()
        for warehouse in warehouses:
            if warehouse['name'] == name:
                return {warehouse['name']: warehouse['ID']}
        logging.warning(f"Склад с именем '{name}' не найден")
        return None
    except Exception as e:
        logging.error(f"Ошибка при получении ID склада: {e}")
        return None


# Пример использования
if __name__ == "__main__":
    load_dotenv()
    wb_api_token = os.getenv('WB_API_SUPPLY')

    try:
        warehouses = get_warehouses_wb(wb_api_token)
        print(f"Получено {len(warehouses)} складов")

        # Пример принудительного обновления кэша
        updated_warehouses = get_warehouses_wb.force_update(wb_api_token)
        print(f"После принудительного обновления получено {len(updated_warehouses)} складов")

        # Пример получения ID склада по имени
        tula_id = get_id_warehouse_wb_by_name(wb_api_token, 'Тула')
        print(f"ID склада 'Тула': {tula_id}")

    except Exception as e:
        print(f"Произошла ошибка: {e}")
