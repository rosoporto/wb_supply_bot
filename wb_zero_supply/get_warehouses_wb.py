import os
import requests
import logging
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_warehouses_wb(wb_api_token):
    url = 'https://supplies-api.wildberries.ru/api/v1/warehouses'

    headers = {
        'Authorization': f'Bearer {wb_api_token}',  # Добавляем токен в заголовок Authorization
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Проверка на ошибки HTTP
    except requests.exceptions.HTTPError as http_err:
        if response.status_code == 401:
            print("Ошибка авторизации: Убедитесь, что ваши учетные данные верны.")
        elif response.status_code == 403:
            print("Доступ запрещён: У вас нет прав для доступа к этому ресурсу.")
        elif response.status_code == 404:
            print("Адрес не найден: Проверьте правильность URL.")
        elif response.status_code == 429:
            print("Слишком много запросов: Попробуйте позже.")
        elif response.status_code == 500:
            print("Внутренняя ошибка сервера: Попробуйте позже.")
        else:
            print(f"Произошла ошибка: {http_err}")

    except requests.exceptions.RequestException as err:
        print(f"Произошла ошибка при выполнении запроса: {err}")
    else:
        # Если запрос успешен, обрабатываем ответ
        warehouses = response.json()  # Возвращаем данные в формате JSON
        return warehouses


def main():
    load_dotenv()
    wb_api_token = os.getenv('WB_API_SUPPLY')

    warehouses = get_warehouses_wb(wb_api_token)
    if warehouses:
        logging.info(warehouses)


if __name__ == '__main__':
    main()
