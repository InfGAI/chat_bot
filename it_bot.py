# Импортируем необходимые классы.
import datetime

import pytz
import requests
from sqlalchemy.exc import SQLAlchemyError
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CommandHandler
from telegram.ext import Updater, MessageHandler, Filters, ConversationHandler

from configure import TOKEN, GEOCODER, APIKEY
from data import db_session
from data.events import Event
from data.registations import Registration
from data.users import User

reply_keyboard = [['/start', '/help']]
db_session.global_init("data/tg_bot.db")
db_sess = db_session.create_session()


def user_keyboard(context):
    '''Кнопки по-умолчанию для админа и пользователя. ВОзвращает ReplyKeyboardMarkup'''
    try:
        markup = ReplyKeyboardMarkup(context.user_data['reply_keyboard'], one_time_keyboard=False)
    except:
        context.user_data['reply_keyboard'] = [['/start', '/stop'], ['Мероприятия']]
        markup = ReplyKeyboardMarkup(context.user_data['reply_keyboard'], one_time_keyboard=False)
    return markup


def message_to_all(context, text=''):
    '''Сообщение всем пользователям чата'''
    all_chat_id = db_sess.query(User.chat_id).all()
    print(all_chat_id)
    for chat_id in all_chat_id:
        print(chat_id)
        try:
            context.bot.send_message(chat_id[0], text=text)
        except:
            print('Пользователь удален из чата', chat_id[0])


def to_all(update, context):
    '''Обработка /to_all'''
    try:
        text = ' '.join(context.args)
        print(text)
    except:
        update.message.reply_text(
            "Чтобы отправить всем сообщение, наберите /to_all ваше сообщение")
        return
    message_to_all(context, text)


def help(update, context):
    '''Обработка /help'''
    update.message.reply_text(
        "Воспользуйся кнопками. Если что-то пошло не так, начни сначала /start")


# Стартовый сценарий
def start(update, context):
    db_sess = db_session.create_session()
    context.user_data['reply_keyboard'] = reply_keyboard
    update.message.reply_text(
        "Привет! Я - бот IT класса школы №444! Я помогу зарегаться на мероприятия и напомню о тех, которые будут тебе интересны. Представься, пожалуйста")
    return 1


def first_response(update, context):
    '''Выбор кнопок в зависимости от прав доступа, регистарция нового пользователя.'''
    name = update.message.text
    context.user_data['name'] = name
    if name.lower() == 'admin':
        update.message.reply_text('Чтобы отправить сообщение всем участникам чата, наберите /start ваше сообщение')
        context.user_data['reply_keyboard'] = [['Разместить информацию', 'Мероприятия'],
                                               ['/events прошедшие', '/events будущие']]
    else:
        context.user_data['reply_keyboard'] = [['Регистрация', 'Мероприятия'], ['Мои мероприятия']]
        try:
            user = db_sess.query(User).filter(User.token == update.message.from_user['id']).one()
            markup = ReplyKeyboardMarkup([['Да', 'Нет']], one_time_keyboard=True)
            update.message.reply_text(
                f'Пользователь с вашим токеном уже зарегистрирован под именем: {user.name}\n Хотите изменить имя?')
            return 2
        except:
            user = User()
            user.name = name
            user.tlg_name = update.message.from_user['first_name']
            user.token = update.message.from_user['id']
            user.chat_id = update.message.chat_id
            db_sess.add(user)
            db_sess.commit()

    welcome(update, context)
    return ConversationHandler.END


def choice(update, context):
    '''Изменение имени пользователя.'''
    if update.message.text.lower() == 'нет':
        user = db_sess.query(User).filter(User.token == update.message.from_user['id']).one()
        context.user_data['name'] = user.name
    welcome(update, context)
    return ConversationHandler.END


def welcome(update, context):
    '''Обновляем имя пользователя'''
    markup = user_keyboard(context)
    update.message.reply_text(
        f"{context.user_data['name'].capitalize()}, добро пожаловать!", reply_markup=markup)
    try:
        query = db_sess.query(User).filter(User.token == update.message.from_user['id']).update(
            {User.name: context.user_data['name']}, synchronize_session=False)
        db_sess.commit()
    except SQLAlchemyError:
        db_sess.rollback()
        print('error')


def stop(update, context):
    '''Прерывание регистрации'''
    markup = user_keyboard(context)
    update.message.reply_text(
        "Регистрация завершена", reply_markup=markup)
    return ConversationHandler.END


# Сценарий добавления события

def post(update, context):
    '''Обработка /post'''
    markup = ReplyKeyboardRemove()
    update.message.reply_text(
        "Разместить информацию:")
    update.message.reply_text(
        "Введите название мероприятия")
    context.user_data['new_event'] = {}
    return 1


def add_event_name(update, context):
    '''Ввод названия мероприятия, проверка на существование в БД и переход к вооду времени'''
    try:
        reply_keyboard = [['Мероприятия', '/stop_post']]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False)
        event = db_sess.query(Event).filter(Event.name == update.message.text).one()
        update.message.reply_text(
            f"Данное мероприятие уже добавлено в календарь")
        update.message.reply_text(
            "Введите название мероприятия")
        return 1
    except:
        context.user_data['new_event']['name'] = update.message.text
        update.message.reply_text(
            f"Введите дату мероприятия в формате {datetime.datetime.now()}")
        return 2


def add_event_date(update, context):
    '''Ввод даты мероприятия, проверка на корректность и переход к ввод организации'''
    try:
        date = datetime.datetime.strptime(update.message.text, "%Y-%m-%d %H:%M")
        context.user_data['new_event']['date'] = date
        if date < datetime.datetime.now():
            update.message.reply_text(
                "Нельзя добавить мероприятие в прошлом")
            return 2
        update.message.reply_text(
            "Введите организацию, проводящую мероприятие или online, если мероприятие заочное")
        return 3
    except:
        update.message.reply_text("Соблюдайте,  пожалуйста, формат даты")
        return 2


def add_event_org(update, context):
    '''Ввод организации мероприятия и переход к вводу описания'''
    context.user_data['new_event']['org'] = update.message.text.lower()
    reply_keyboard = [['Нет', '/stop_post'], ['Мероприятия']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    update.message.reply_text("Задайте описание мероприятия или 'НЕТ', если описание отсутствует", reply_markup=markup)
    return 4


def add_event(update, context):
    '''Ввод описания мероприятия, созадние записи в БД'''
    if update.message.text.lower() != 'нет':
        context.user_data['new_event']['about'] = update.message.text
    else:
        context.user_data['new_event']['about'] = ''
    reply_keyboard = [['Да', 'Нет'], ['Мероприятия', '/stop_post']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    try:
        event = Event()
        event.name = context.user_data['new_event']['name']
        print(event.name)
        event.date = context.user_data['new_event']['date']
        print(event.date)
        event.organization = context.user_data['new_event']['org']
        print(event.organization)
        event.about = context.user_data['new_event']['about']

        db_sess.add(event)
        db_sess.commit()
        message_to_all(context, f'''Анонс мероприятия:\n
                        {event.organization}\n
                        {event.name}\n
                        {event.date}\n
                        {event.about}''')
        update.message.reply_text("Добавлено! Хотите добавить еще мероприятие?", reply_markup=markup)
    except:
        markup = user_keyboard(context)
        update.message.reply_text("Не удалось добавить мероприятие", reply_markup=markup)
    return 5


def stop_post(update, context):
    '''Прерывание создания мероприятия'''
    if update.message.text == '/stop_post' or update.message.text.lower() == "нет":
        markup = user_keyboard(context)
        update.message.reply_text(
            "Завершено", reply_markup=markup)
        return ConversationHandler.END
    else:
        update.message.reply_text(
            "Введите название мероприятия")
        return 1


# Сценарий регистрации
def reg(update, context):
    '''Запуск регистрации на мероприятие'''
    view(update, context)
    update.message.reply_text("Чтобы увидеть расположение на карте, ответьте 'ГДЕ' на сообщение с мероприятием.\n" +
                              "Чтобы зарегистрироваться на мероприятие, ответьте 'Я' на сообщение с мероприятием.\n" +
                              "Чтобы завершить регистрацию на мероприятия, наберите команду /stop")
    return 1


def add_my_event(update, context):
    '''Обработка ответа на сообщение для регистрации'''
    try:
        name, date, org, adress = update.message.reply_to_message['text'].split('\n')
        markup = ReplyKeyboardMarkup([['/stop', 'Мероприятия']])
        if update.message.text.lower() == 'где':
            img = show_map(adress)
            context.bot.send_photo(update.message.chat_id, img, caption=org)
        else:
            event = db_sess.query(Event).filter(Event.name == name).one()
            user = db_sess.query(User).filter(User.token == update.message.from_user['id']).one()
            try:
                reg = db_sess.query(Registration).filter(
                    (Registration.user_id == user.id) & (Registration.event_id == event.id)).one()
                update.message.reply_text('Вы уже зарегистрированы на данное мероприятие', reply_markup=markup)
            except:
                reg_event = Registration()
                reg_event.user_id = user.id
                reg_event.event_id = event.id
                db_sess.add(reg_event)
                db_sess.commit()
                set_timer(update, context, name, date)
                update.message.reply_text(f"Добавлена регистрация на\n{update.message.reply_to_message['text']}",
                                          reply_markup=markup)
    except:
        update.message.reply_text(
            'Если хочешь зарегистрироваться на мероприятие, ответь на сообщение с интересным для тебя мероприятием.')
    return 1


def check_time(str_date):
    ''' Проверка текстовой даты относительно текущего момента. Возвращает True, если дата в будущем и False, если дата в прошлом'''
    date = datetime.datetime.strptime(str_date, "%Y-%m-%d %H:%M:%S")
    return date >= datetime.datetime.now()


def my_events(update, context):
    '''Просмотр мероприятий на которые зарегистрирован в будущем'''
    update.message.reply_text("Мои регистрации на мероприятия:")
    events = db_sess.query(Event).filter(
        (User.chat_id == update.message.from_user['id']) & (User.id == Registration.user_id) &
        (Registration.event_id == Event.id)).all()
    if events:
        rez = ''
        pass_rez = ''
        for event in events:
            if event.date > datetime.datetime.now():
                rez += f'{event.name}\n{event.date}\n{event.about}\n\n'
        update.message.reply_text('Будущие мероприятия:\n' + rez)
    else:
        update.message.reply_text('Не найдено регистраций на мероприятия')


def find_adress(org):
    '''Поиск корректного названия организации и адреса, если отстутвует описание'''
    URL = "https://search-maps.yandex.ru/v1/"
    params = {
        'apikey': APIKEY,
        'text': org,
        'lang': 'ru_RU',
        'type': 'biz',

        'format': 'json'
    }
    response = requests.get(URL, params=params)
    if not response:
        print("Ошибка поиска организации:")
        print("Http статус:", response.status_code, "(", response.reason, ")")
        return (None, None)
    json_response = response.json()
    result_name = json_response["features"][0]["properties"]["CompanyMetaData"]["name"]
    result_coords = json_response["features"][0]["geometry"]["coordinates"]
    URL = "https://geocode-maps.yandex.ru/1.x"
    params = {
        'geocode': ','.join(map(str, result_coords)),
        'apikey': GEOCODER,
        'format': 'json'
    }
    response = requests.get(URL, params=params)
    if not response:
        print("Ошибка поиска адреса:")
        print("Http статус:", response.status_code, "(", response.reason, ")")
        return (None, None)
    json_response = response.json()
    result_adress = json_response["response"]["GeoObjectCollection"] \
        ["featureMember"][0]["GeoObject"]["metaDataProperty"]["GeocoderMetaData"]["Address"]["formatted"]
    return result_name, result_adress


def show_map(adress):
    ''' Построенеи карты с меткой организации Возвращает картинку.'''
    URL = "https://search-maps.yandex.ru/v1/"
    params = {
        'apikey': APIKEY,
        'text': adress,
        'lang': 'ru_RU',
        'll': '37.618879, 55.751426',
        'format': 'json'
    }
    response = requests.get(URL, params=params)
    if not response:
        print("Ошибка поиска организации:")
        print("Http статус:", response.status_code, "(", response.reason, ")")
        return None
    json_response = response.json()
    result_coords = json_response["features"][0]["geometry"]["coordinates"]
    URL = "http://static-maps.yandex.ru/1.x/"
    params = {
        'll': ','.join(map(str, result_coords)),
        'spn': "0.02,0.02",
        'l': 'map',
        'pt': ','.join(map(str, result_coords)) + ',org',
    }
    response = requests.get(URL, params=params)
    if not response:
        print("Ошибка выполнения запроса:")
        print("Http статус:", response.status_code, "(", response.reason, ")")
    return response.content


def view(update, context):
    '''Просмотр будущих мероприятий'''
    update.message.reply_text("Доступные мероприятия:")
    events = db_sess.query(Event).filter(datetime.datetime.now() < Event.date)
    rez = ''
    for event in events:
        rez = f'{event.name}\n{event.date}\n'
        if event.organization != 'online' and not event.about:
            org, adress = find_adress(event.organization)
            rez += f'{org}.\n{adress}.'
        else:
            rez += f'ONLINE\n{event.about}.'
        update.message.reply_text(rez)


def view_students(update, context):
    '''Просмотр зарегистрированных учеников на поршедшие и будущие мероприятия'''
    if context.args[0] == 'прошедшие':
        events = db_sess.query(Event).filter(Event.date < datetime.datetime.now()).all()
    else:
        events = db_sess.query(Event).filter(Event.date > datetime.datetime.now()).all()
    if events:
        for event in events:
            text = event.name + '\n\n'
            rez = db_sess.query(User).filter((User.id == Registration.user_id) &
                                             (Registration.event_id == event.id)).all()
            if rez:
                text += '\n'.join([student.name for student in rez])
            else:
                text += '\nНет зарегистрированных участников'
            update.message.reply_text(text)
    else:
        update.message.reply_text('Нет прошедших мероприятий')


# Таймер
def set_timer(update, context, name, date):
    """Добавляет ежедневное напоминание"""
    chat_id = update.message.chat_id
    text = f'Готово!'
    time = datetime.time(hour=8, minute=0, second=0,
                         tzinfo=pytz.timezone('Europe/Moscow'))
    context.job_queue.run_daily(task, time,
                                days=(0, 1, 2, 3, 4, 5, 6), context=chat_id, name=f'{name}|{date}')
    update.message.reply_text(text)


def remove_job_if_exists(name, context):
    """Удаляет задачу по имени.
    Возвращает True если задача была успешно удалена."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


def task(context):
    """Выводит сообщение о мероприятиях и удаляет из очереди пошедшие мероприятия"""
    job = context.job
    for task_ in context.job_queue.jobs():
        task_date = task_.name.split('|')[1]
        if not (check_time(task_date)):
            job_removed = remove_job_if_exists(task_.name, context)
    context.bot.send_message(job.context, text='Скоро состоится\n' + job.name)


def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("set", set_timer,
                                  pass_job_queue=True,
                                  pass_chat_data=True))

    # кнопки
    dp.add_handler(MessageHandler(Filters.regex('Мероприятия'), view, pass_user_data=True))
    dp.add_handler(CommandHandler('events', view_students, pass_user_data=True))
    dp.add_handler(MessageHandler(Filters.regex('Мои мероприятия'), my_events, pass_user_data=True))
    dp.add_handler(CommandHandler('to_all', to_all, pass_user_data=True))

    # Сценарий старта
    start_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start,
                                     pass_chat_data=True)],
        states={
            1: [MessageHandler(Filters.text, first_response, pass_user_data=True)],
            2: [MessageHandler(Filters.text, choice, pass_user_data=True)],

        },

        fallbacks=[CommandHandler('stop', stop)]
    )
    dp.add_handler(start_handler)
    # Сценарий регистрации на мероприятия
    reg_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('Регистрация'), reg)],
        states={
            1: [MessageHandler(Filters.reply, add_my_event)]
        },

        fallbacks=[CommandHandler('stop', stop)]
    )
    dp.add_handler(reg_handler)
    # Сценарий добавления
    # Сценарий
    post_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('Разместить информацию'), post)],
        states={
            1: [MessageHandler(Filters.text, add_event_name)],
            2: [MessageHandler(Filters.text, add_event_date)],
            3: [MessageHandler(Filters.text, add_event_org)],
            4: [MessageHandler(Filters.text, add_event)],
            5: [MessageHandler(Filters.text, stop_post)],
        },

        fallbacks=[CommandHandler('stop_post', stop_post)]
    )
    dp.add_handler(post_handler)
    # Запускаем цикл приема и обработки сообщений.
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
