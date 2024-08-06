import json
import redis
import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


class RedisManager:
    def __init__(self, db_number=1, password=None):
        """Инициализация подключения к Redis."""
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            db=db_number,
            password=password,
            decode_responses=True
        )
        if not self.check_connection():
            logging.error("Не удалось подключиться к Redis.")
            raise ConnectionError("Не удалось подключиться к Redis.")

    def check_connection(self):
        """Проверяет, доступен ли Redis."""
        try:
            return self.redis_client.ping()
        except redis.ConnectionError:
            return False

    def check_database_empty(self):
        """Проверяет, пуста ли база данных."""
        return self.redis_client.dbsize() == 0


class RedisManagerData(RedisManager):
    """
        Сохраняет данные о коэффициентах приемки в Redis с установленным временем жизни.

        :param data: Словарь, содержащий 'warehouse', 'date' и 'type'.
        :param ttl: Время жизни в секундах.
        :return: Кортеж (успех: bool, локация: str)
        """
    def save_data(self, location, ttl):
        """Сохраняет данные о коэффициентах приёмки в Redis с установленным временем жизни."""
        warehouse = location.get('Склад')
        date = location.get('Дата')
        type_ = location.get('Тип')
        coefficient = location.get('Коэффициент')

        # Создание уникального ключа
        key = f"warehouse:{warehouse}:{date}:{coefficient}"

        # Проверка, существует ли запись
        if not self.redis_client.exists(key):
            # Сохранение данных в хэш
            self.redis_client.hset(key, mapping={'type': type_, 'coefficient': coefficient})
            # Установка времени жизни для ключа
            self.redis_client.expire(key, ttl)  # Устанавливаем TTL в секундах
            message = f"Склад: {warehouse}, Дата: {date}, Тип: {type_}, Коэффициент {coefficient}"
            return True, message
        else:
            return False, ""  # Данные уже существуют

    def update_data(self, location, ttl):
        """Обновляет существующие данные о коэффициентах приёмки в Redis."""
        warehouse = location.get('Склад')
        date = location.get('Дата')
        type_ = location.get('Тип')
        coefficient = location.get('Коэффициент')

        # Создание уникального ключа
        key = f"warehouse:{warehouse}:{date}:{coefficient}"

        # Проверка, существует ли запись
        if self.redis_client.exists(key):
            # Обновление данных в хэш
            self.redis_client.hset(key, mapping={'type': type_, 'coefficient': coefficient})
            # Обновление времени жизни для ключа
            self.redis_client.expire(key, ttl)
            message = f"Обновлено: Склад: {warehouse}, Дата: {date}, Тип: {type_}, Коэффициент {coefficient}"
            return True, message
        else:
            return False, "Данные для обновления не найдены"

    def get_data(self, warehouse, date, coefficient):
        """Получает данные о коэффициентах приёмки из Redis."""
        key = f"warehouse:{warehouse}:{date}:{coefficient}"
        data = self.redis_client.hgetall(key)
        if data:
            return {k: v for k, v in data.items()}
        else:
            return None

    def process_locations(self, locations, ttl):
        """Обрабатывает список локаций и сохраняет или обновляет данные с установленным временем жизни."""
        messages = []
        for location in locations:
            save_result, save_message = self.save_data(location, ttl)
            if not save_result:
                update_result, update_message = self.update_data(location, ttl)
                if update_result:
                    messages.append(update_message)
            else:
                messages.append(save_message)
        return messages


class RedisManagerUser(RedisManager):
    def set_user_data(self, user_id, data):
        """Сохраняет данные пользователя в Redis."""
        serialized_data = {key: json.dumps(value) for key, value in data.items()}
        self.redis_client.hmset(f"user:{user_id}", serialized_data)

    def get_user_data(self, user_id):
        """Получает данные пользователя из Redis."""
        data = self.redis_client.hgetall(f"user:{user_id}")
        return {key: json.loads(value) for key, value in data.items()}

    def delete_user_data(self, user_id):
        """Удаляет данные пользователя из Redis."""
        self.redis_client.delete(f"user:{user_id}")


if __name__ == '__main__':
    pass
