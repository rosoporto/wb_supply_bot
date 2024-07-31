import time
import requests
import logging


# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class APICache:
    def __init__(self, token, cache_duration=86400):  # 86400 секунд = 1 день
        """
        Инициализация кэша API.

        :param token: Токен для авторизации API.
        :param cache_duration: Время кэширования в секундах (по умолчанию 1 день).
        """
        self.token = token
        self.cache_duration = cache_duration
        self.last_fetch_time = 0
        self.cached_data = None

    def get_data(self):
        """
        Получение данных из кэша или API.

        :return: Данные из кэша или API.
        """
        current_time = time.time()
        # Проверяем, нужно ли обновить кэш
        if current_time - self.last_fetch_time > self.cache_duration:
            logging.info("Обращение к API для получения новых данных...")
            self.cached_data = self.fetch_data_from_api()
            if self.cached_data is not None:  # Проверяем, что данные получены
                self.last_fetch_time = current_time
        else:
            logging.info("Возвращаем данные из кэша.")
        return self.cached_data

    def fetch_data_from_api(self):
        """
        Запрос данных из API.

        :return: Данные из API в формате JSON или None в случае ошибки.
        """
        url = 'https://supplies-api.wildberries.ru/api/v1/warehouses'
        headers = {
            'Authorization': f'Bearer {self.token}',  # Добавляем токен в заголовок Authorization
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Проверка на ошибки HTTP
        except requests.exceptions.HTTPError:
            self.handle_http_error(response)
            return None  # Возвращаем None в случае ошибки
        except requests.exceptions.RequestException as err:
            logging.error(f"Произошла ошибка при выполнении запроса: {err}")
            return None  # Возвращаем None в случае ошибки
        else:
            # Если запрос успешен, обрабатываем ответ
            warehouses = response.json()  # Возвращаем данные в формате JSON
            return warehouses

    def handle_http_error(self, response):
        """
        Обработка ошибок HTTP.

        :param response: Ответ от API.
        """
        if response.status_code == 401:
            logging.error("Ошибка авторизации: Убедитесь, что ваши учетные данные верны.")
        elif response.status_code == 403:
            logging.error("Доступ запрещён: У вас нет прав для доступа к этому ресурсу.")
        elif response.status_code == 404:
            logging.error("Адрес не найден: Проверьте правильность URL.")
        elif response.status_code == 429:
            logging.error("Слишком много запросов: Попробуйте позже.")
        elif response.status_code == 500:
            logging.error("Внутренняя ошибка сервера: Попробуйте позже.")
        else:
            logging.error(f"Произошла ошибка: {response.status_code}")


def frequently_called_function(api_cache):
    """
    Часто вызываемая функция для получения данных.
    """
    data = api_cache.get_data()
    # Обработка данных
    return data


# Пример использования
if __name__ == "__main__":
    api_cache = APICache(token='your_api_token_here')

    # Пример вызова функции каждые 12 секунд
    for _ in range(10):  # Пример 10 вызовов
        result = frequently_called_function(api_cache)
        print(result)
        time.sleep(12)  # Задержка 12 секунд
