## Получение информации для формирования поставок на склады Wildberries
Мониторинг коэффициента приёмки по выбранному складу с информированием в Telegram-боту. Приложение написано с использованием  менеджера проектов Poetry.

### Установка
```bash
git clone https://github.com/rosoporto/dialogflow_bots.git
```

### Настройка
Создайте в корне проекта файл `.env` и наполните его следующим содержимым:

```bash
TELEGRAM_TOKEN=" ... " - токен бота в Telegram
WB_API_SUPPLY= " ... " - api Wildberries
ADMIN_CHANNEL_ID= ...  - ID канала админа (для мониторинга ошибок бота)
```

### Запуск
```python
poetry run bot
```
Далее в Telegram-боте следуете его указанию