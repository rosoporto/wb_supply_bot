
import time
import logging
from functools import wraps


# Декоратор для замера времени выполнения функции
def timing_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logging.info(f"{func.__name__} выполнена за {end_time - start_time:.4f} секунд")
        return result
    return wrapper


@timing_decorator
def test_function(duration):
    """Функция, которая просто задерживается на некоторое время"""
    time.sleep(duration)


# Пример использования функции
if __name__ == "__main__":
    test_function(2)  # Задержка на 2 секунды
