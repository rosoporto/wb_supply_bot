import os
import logging
from dotenv import load_dotenv
from wb_zero_supply.RedisManager import RedisManagerData, RedisManagerUser
from wb_zero_supply.get_stock_wb_from_api import (
    get_stock_wb_from_api,
    check_coefficients_in_range
)
from wb_zero_supply.get_warehouses_wb import get_id_warehouse_wb_by_name
from telegram import Update
from telegram.ext import Updater, ConversationHandler, CommandHandler
from telegram.ext import MessageHandler, Filters, CallbackContext


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
redis_manager_user = RedisManagerUser()
CHOOSING_WAREHOUSE, CHOOSING_MAX_DEGREE = range(2)


def send_data(context: CallbackContext):
    job = context.job
    token_api_wb = job.data['token_api_wb']    
    pass_redis = job.data['pass_redis']
    user_id = job.context

    user_data = redis_manager_user.get_user_data(str(user_id))
    store = user_data['warehouse_id']

    try:
        coefficients = get_stock_wb_from_api(token_api_wb, store)
        if coefficients:
            max_degree = int(user_data['max_degree'])
            locations = check_coefficients_in_range(coefficients, max_degree=max_degree)
            if locations:
                redis_manager_data = RedisManagerData(password=pass_redis)
                ttl = 1209600  # 14 дней в секундах
                messages = redis_manager_data.process_locations(locations, ttl)
                for message in messages:
                    context.bot.send_message(user_id, text=message)
            else:
                logging.info("Нет уникальных данных для отправки.")
        else:
            logging.error("Не удалось получить коэффициенты из API.")
            context.bot.send_message(user_id, text="Ошибка: Не удалось получить данные о коэффициентах.")
    except Exception as e:
        logging.error(f"Произошла ошибка: {e}")
        context.bot.send_message(user_id, text="Ошибка: Произошла ошибка при обработке данных.")


def start(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    redis_manager_user.set_user_data(user_id, {'warehouse_wb': {}, 'max_degree': 0})
    update.message.reply_text(
        'Бот запущен! Я буду присылать вам данные коэффициенты приёмки на складах WB.'
    )
    update.message.reply_text(
        'Пожалуйста, введите название склада, который вы хотите отслеживать.',
        timeout=3
    )


def handle_warehouse(update: Update, context: CallbackContext) -> int:
    user_id = str(update.effective_user.id)
    warehouse_by_user = update.message.text

    token_api_wb = context.bot_data['token_api_wb']
    warehouse_wb = get_id_warehouse_wb_by_name(token_api_wb, warehouse_by_user)
    if warehouse_wb is None:
        update.message.reply_text('Склада с такими именем нет. Попробуйте снова.')
        return CHOOSING_WAREHOUSE

    # Получаем текущие данные пользователя
    user_data = redis_manager_user.get_user_data(user_id)

    # Обновляем значение 'warehouse_wb'
    user_data['warehouse_wb'] = warehouse_wb

    # Сохраняем склад в Redis
    redis_manager_user.set_user_data(user_id, user_data)

    update.message.reply_text(f"Вы выбрали склад: {warehouse_wb['name']}. Теперь введите максимальный коэффициент для отслеживания.")
    return CHOOSING_MAX_DEGREE


def handle_max_degree(update: Update, context: CallbackContext) -> int:
    user_id = str(update.effective_user.id)

    try:
        max_degree = int(update.message.text)
        user_data = redis_manager_user.get_user_data(user_id)
        user_data['max_degree'] = max_degree
        redis_manager_user.set_user_data(user_id, user_data)
        update.message.reply_text(f'Вы установили максимальный коэффициент: {max_degree}. Бот начнет отслеживать данные.')
    
        # Добавляем задачу в JobQueue с передачей токена API и списка магазинов
        context.job_queue.run_repeating(
            send_data,
            interval=30,
            first=0,
            context=update.message.chat_id,
            name=f'data_fetcher_{user_id}',
            data={
                'token_api_wb': context.bot_data['token_api_wb'],
                'pass_redis': context.bot_data['pass_redis']
            }
        )
        return ConversationHandler.END
    except ValueError:
        update.message.reply_text('Пожалуйста, введите корректное число для максимального коэффициента.')
        return CHOOSING_MAX_DEGREE


def cancel(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)

    # Удаляем данные пользователя из Redis
    redis_manager_user.delete_user_data(user_id)

    # Останавливаем все активные задачи для этого пользователя
    current_jobs = context.job_queue.get_jobs_by_name(f'data_fetcher_{user_id}')
    for job in current_jobs:
        job.schedule_removal()

    update.message.reply_text(
        'Операция отменена. Ваши данные удалены, и отслеживание остановлено. '
        'Используйте /start, чтобы начать заново.'
    )

    return ConversationHandler.END


def main():
    load_dotenv()
    token_telegram = os.getenv('TELEGRAM_TOKEN')
    token_api_wb = os.getenv('WB_API_SUPPLY')
    pass_redis = os.getenv('PASS_REDIS')
    stores = {
        'Тула': 206348,
        'СЦ Пушкино': 207743,
        'Электросталь': 120762
    }

    updater = Updater(token_telegram, use_context=True)
    dp = updater.dispatcher
    # хранения конфигурационных данных и общих значений,
    # которые будут использоваться в различных частях вашего бота
    dp.bot_data['token_api_wb'] = token_api_wb
    dp.bot_data['stores'] = stores
    dp.bot_data['pass_redis'] = pass_redis

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING_WAREHOUSE: [MessageHandler(Filters.text & ~Filters.command, handle_warehouse)],
            CHOOSING_MAX_DEGREE: [MessageHandler(Filters.text & ~Filters.command, handle_max_degree)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    dp.add_handler(conv_handler)
    
    dp.add_handler(CommandHandler('cancel', cancel))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
