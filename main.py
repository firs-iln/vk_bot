import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import random
import sqlite3
from os.path import join as path_to
import json
import datetime as dt
import sys
from Menu import Dish, Basket
from api_geocoder import get_address_from_coords

SESSION_TIME = dt.datetime.now()


class WrongID(Exception):  # ошибка 'В БД нет пользователя с таким id'
    pass


def update_last_act(user_id, cur, con, act):  # обновление последнего действия в БД
    cur.execute(f'''UPDATE Users
                    SET last_act = '{act}'
                    WHERE user_id = {user_id}''')
    con.commit()


def update_pay_way(user_id, cur, con, pay_way):  # обновление способа оплаты в БД
    cur.execute(f'''UPDATE Users
                    SET pay_way = '{pay_way}'
                    WHERE user_id = {user_id}''')
    con.commit()


def update_basket(user_id, cur, con, vk, dish=None, new=None):  # обновление содержимого корзины
    if new:
        cur.execute(f'''UPDATE Users
                        SET basket = '{new}'
                        WHERE user_id = {user_id}''')
    else:
        if dish != 0:
            old = cur.execute(f'SELECT basket FROM Users WHERE user_id = {user_id}').fetchall()[0][0]
            if old:
                basket = old + dish[1] + ','
            else:
                basket = dish[1] + ','
            cur.execute(f'''UPDATE Users
                            SET basket = '{basket}'
                            WHERE user_id = {user_id}''')
            con.commit()
            vk.messages.send(user_id=user_id,
                             message='Добавлено!',
                             random_id=random.randint(0, 2 ** 64))
        else:
            cur.execute(f'''UPDATE Users
                            SET basket = ''
                            WHERE user_id = {user_id}''')
            con.commit()


def update_carousel_page(user_id, cur, con, value):  # обновление текущей страницы карусели
    if value != 0:
        current = cur.execute(f'''SELECT menu_page FROM Users WHERE user_id = {user_id}''').fetchall()[0][0]
        cur.execute(f'''UPDATE Users
                        SET menu_page = {current + value}
                        WHERE user_id = {user_id}''')
        con.commit()
    else:
        cur.execute(f'''UPDATE Users
                        SET menu_page = {value}
                        WHERE user_id = {user_id}''')
        con.commit()


def update_current_dish(user_id, cur, con, value):
    if value != 0:
        current = cur.execute(f'''SELECT current_dish FROM Users WHERE user_id = {user_id}''').fetchall()[0][0]
        cur.execute(f'''UPDATE Users
                        SET current_dish = {int(current) + value}
                        WHERE user_id = {user_id}''')
        con.commit()
    else:
        cur.execute(f'''UPDATE Users
                                SET current_dish = {value}
                                WHERE user_id = {user_id}''')
        con.commit()


def update_address(user_id, cur, con, address):  # обновление адреса в БД
    cur.execute(f'''UPDATE Users
                    SET address = '{address}'
                    WHERE user_id = {user_id}''')
    con.commit()


def update_status(user_id, cur, con, status):  # обновление статуса в БД
    cur.execute(f'''UPDATE Users
                    SET status = '{status}'
                    WHERE user_id = {user_id}''')
    con.commit()


def logging(*args, file=None, session_time=None):
    if file:
        with open(path_to('data/logs', file), 'w', encoding='UTF-8') as logfile:
            print(args, file=logfile)
    else:
        with open(path_to('data/logs', f'log_{session_time.strftime("%d.%m.%Y_%H-%M-%S-%f")}.txt'), 'wt',
                  encoding='UTF-8') as logfile:
            print(args, file=logfile)


def upload_image(vk, name):  # загрузка фото
    photo = vk_api.VkUpload(vk).photo_messages(path_to('data/dish_photos', name))
    return f'{photo[0]["owner_id"]}_{photo[0]["id"]}'


def conf_address(vk, coords, user_id, cur, con):  # подтверждение адреса
    address = get_address_from_coords(coords)
    if address.split()[0] != 'Ошибка':
        with open(path_to('data/keyboards', 'confirmation.json'), 'r', encoding='UTF-8') as kb:
            vk.messages.send(user_id=user_id,
                             message=f"Ваш адрес — {address}?",
                             random_id=random.randint(0, 2 ** 64), keyboard=kb.read())
            update_last_act(user_id, cur, con, 'ask_conf_address')
            return address
    else:
        with open(path_to('data/keyboards', 'location.json'), 'r', encoding='UTF-8') as kb:
            vk.messages.send(user_id=user_id,
                             message=f"Введённый адрес недействителен. Попробуйте еще раз!",
                             random_id=random.randint(0, 2 ** 64), keyboard=kb.read())


def get_address(vk, event, user_id, cur, con, necessarily=True):  # получение адреса из сообщения пользователя
    address = None
    try:
        lat = event.obj.message['geo']['coordinates']['latitude']
        long = event.obj.message['geo']['coordinates']['longitude']
        address = (lat, long)
    except KeyError:
        pass
    if address:
        return conf_address(vk, address, user_id, cur, con)
    else:
        if necessarily:
            update_last_act(user_id, cur, con, 'ask_address')
            with open(path_to('data/keyboards', 'location.json'), 'r', encoding='UTF-8') as kb:
                vk.messages.send(user_id=user_id,
                                 message=f"Попробуйте еще раз!",
                                 random_id=random.randint(0, 2 ** 64), keyboard=kb.read())
        return None


def show_current_carousel(vk, cur, con, user_id):  # отправка карусели пользователю
    max_num = cur.execute('SELECT num FROM Menu').fetchall()[-1][0]
    page_num = cur.execute(f'SELECT menu_page FROM Users WHERE user_id = {user_id}').fetchall()[0][0]
    if page_num * 10 - 10 < max_num:
        page_content = cur.execute(f'''SELECT * FROM Menu 
                                        WHERE num BETWEEN ({page_num} * 10 + 1) AND ({page_num} * 10 + 10)''').fetchall()
        carousel_dict = {'type': 'carousel', 'elements': []}

        for dish in page_content:  # формирование карусели
            element_dict = {'title': dish[1],
                            'description': dish[3],
                            'photo_id': upload_image(vk, dish[4]),
                            'action': {'type': 'open_photo'},
                            'buttons': [{'action': {'type': 'text', 'label': f'{dish[1]}'}, 'color': 'positive'},
                                        {'action': {'type': 'text', 'label': 'Следующая страница!'},
                                         'color': 'primary'},
                                        {'action': {'type': 'text', 'label': 'Предыдущая страница!'},
                                         'color': 'secondary'}]}
            carousel_dict['elements'].append(element_dict)
        # преобразование словаря в json-файл
        carousel_json = json.dumps(carousel_dict)
        vk.messages.send(user_id=user_id,
                         message=f"Страница {page_num + 1}." +
                                 " Чтобы добавить пиццу в свою корзину, нажми на кнопку с её названием",
                         random_id=random.randint(0, 2 ** 64), template=carousel_json)
        update_last_act(user_id, cur, con, 'show_carousel')
    else:
        with open(path_to('data/keyboards', 'last_page.json'), 'r', encoding='UTF-8') as kb:
            vk.messages.send(user_id=user_id,
                             message=f"Меню кончилось. Посмотрим еще раз или идем в корзину?",
                             random_id=random.randint(0, 2 ** 64), keyboard=kb.read())
        update_last_act(user_id, cur, con, 'show_last_carousel')


def show_basket(vk, cur, con, user_id):  # отправка корзины
    basket_li = cur.execute(f'''SELECT basket FROM Users WHERE user_id = {user_id}''').fetchall()[0][0].split(',')
    basket = Basket()
    basket = None
    basket = Basket()
    for dish in basket_li:
        if dish:
            dish = cur.execute(f"SELECT * FROM Menu WHERE name = '{dish}'").fetchall()[0]
            basket.append(Dish(dish))
    text = str(basket)
    if text:
        with open(path_to('data/keyboards', 'basket.json'), 'r', encoding='UTF-8') as kb:
            vk.messages.send(user_id=user_id,
                             message=text,
                             random_id=random.randint(0, 2 ** 64), keyboard=kb.read())
        update_last_act(user_id, cur, con, 'show_basket')
    else:
        with open(path_to('data/keyboards', 'empty_basket.json'), 'r', encoding='UTF-8') as kb:
            vk.messages.send(user_id=user_id,
                             message='Ваша корзина пуста. Наполните ее и возвращайтесь!',
                             random_id=random.randint(0, 2 ** 64), keyboard=kb.read())
        update_last_act(user_id, cur, con, 'show_empty_basket')


def show_current_dish(vk, cur, con, user_id):  # отправка текущего блюда
    max_num = cur.execute('SELECT num FROM Menu').fetchall()[-1][0]
    current = cur.execute(f'SELECT current_dish FROM Users WHERE user_id = {user_id}').fetchall()[0][0]
    dish_li = cur.execute(f'SELECT * FROM Menu WHERE num = {int(current) + 1}').fetchall()[0]
    dish = Dish(dish_li)
    last_act = cur.execute(f'SELECT last_act FROM Users WHERE user_id = {user_id}').fetchall()[0][0]
    if last_act != 'show_last_dish':
        kb = {"inline": True, "buttons": [
            [{"action": {"type": "text", "payload": "{\"button\": \"1\"}", "label": f"{dish.name}"},
              "color": "positive"},
             {"action": {"type": "text", "payload": "{\"button\": \"2\"}", "label": "Следующее блюдо!"},
              "color": "primary"},
             {"action": {"type": "text", "payload": "{\"button\": \"2\"}", "label": "Предыдущее блюдо!"},
              "color": "secondary"}]]}
        kb_json = json.dumps(kb)
        vk.messages.send(user_id=user_id,
                         message=str(dish), random_id=random.randint(0, 2 ** 64),
                         keyboard=kb_json, attachment=f'photo{upload_image(vk, dish.url_pic)}')
        if dish.num == max_num:
            update_last_act(user_id, cur, con, 'show_last_dish')
        else:
            update_last_act(user_id, cur, con, 'show_dish')
    else:
        with open(path_to('data/keyboards', 'last_page.json'), 'r', encoding='UTF-8') as kb:
            vk.messages.send(user_id=user_id,
                             message="Меню кончилось. Посмотрим еще раз или идем в корзину?",
                             random_id=random.randint(0, 2 ** 64), keyboard=kb.read())


def registration(vk, cur, con, user_id):
    with open(path_to('data/keyboards', 'registration.json'), 'r', encoding='UTF-8') as kb:
        vk.messages.send(user_id=user_id,
                         message="Выберите способ оплаты:",
                         random_id=random.randint(0, 2 ** 64), keyboard=kb.read())
        update_last_act(user_id, cur, con, 'registration')


def edit_basket(vk, cur, con, user_id, action='ask', elem=None):
    basket_li = cur.execute(f'''SELECT basket FROM Users WHERE user_id = {user_id}''').fetchall()[0][0].split(',')
    basket = Basket()
    update_basket(user_id, cur, con, vk, dish=0)
    if action == 'ask':
        with open(path_to('data/keyboards', 'edit_basket.json'), 'r', encoding='UTF-8') as kb:
            vk.messages.send(user_id=user_id,
                             message='Какую пиццу удалим? Ответь цифрой!',
                             random_id=random.randint(0, 2 ** 64), keyboard=kb.read())
        update_last_act(user_id, cur, con, 'ask_for_del')
    else:
        try:
            if int(elem) in range(len(basket)):
                basket.delete(int(elem) + 1)
                update_basket(user_id, cur, con, vk, new=basket.names())
                basket = None
                basket = Basket()
                with open(path_to('data/keyboards', 'edit_basket.json'), 'r', encoding='UTF-8') as kb:
                    vk.messages.send(user_id=user_id,
                                     message='Выполнено! Если хочешь удалить ещё, пиши цифру!\n\n' + str(
                                         basket),
                                     random_id=random.randint(0, 2 ** 64), keyboard=kb.read())
                update_last_act(user_id, cur, con, 'edit_basket')
            else:
                with open(path_to('data/keyboards', 'edit_basket.json'), 'r', encoding='UTF-8') as kb:
                    vk.messages.send(user_id=user_id,
                                     message='Такой пиццы в корзине нет! Ответь цифрой!',
                                     random_id=random.randint(0, 2 ** 64), keyboard=kb.read())
        except ValueError:
            with open(path_to('data/keyboards', 'edit_basket.json'), 'r', encoding='UTF-8') as kb:
                vk.messages.send(user_id=user_id,
                                 message='Такой пиццы в корзине нет! Ответь цифрой!',
                                 random_id=random.randint(0, 2 ** 64), keyboard=kb.read())


def finish(vk, cur, con, user_id):
    vk.messages.send(user_id=user_id,
                     message="Спасибо за Ваш заказ! Курьер прибудет по указанному вами адресу через час.",
                     random_id=random.randint(0, 2 ** 64))
    update_carousel_page(user_id, cur, con, 0)
    update_current_dish(user_id, cur, con, 0)
    update_basket(user_id, cur, con, vk, dish=0)
    update_last_act(user_id, cur, con, 'new_user')


def main():
    global SESSION_TIME
    #  подключение к ВКонтакте
    try:
        vk_session = vk_api.VkApi(
            token='41e1b47bb6d5d9b90ba89da796c0a85c33ebe0c6b75219b2d3f7e2c8492293f9d54a641647d56388c0f7a')
        longpoll = VkBotLongPoll(vk_session, '195073403')
    except BaseException as e:
        return e
    #  подключение к БД
    try:
        con = sqlite3.connect(path_to('data/databases', 'data.db'))
        cur = con.cursor()
    except BaseException as e:
        return e
    for event in longpoll.listen():
        if event.type == VkBotEventType.GROUP_JOIN:
            vk = vk_session.get_api()
            #  логирование
            logging(f'{event.obj.user_id} вступил в группу!', session_time=SESSION_TIME)
            with open(path_to('data/keyboards', 'follow.json'), 'r', encoding='UTF-8') as kb:
                vk.messages.send(user_id=event.obj.user_id,
                                 message="Привет, хочешь заказать вкуснейшую пиццу к себе домой?",
                                 random_id=random.randint(0, 2 ** 64), keyboard=kb.read())
            #  добавление пользователя в БД
            cur.execute(f'''INSERT INTO Users(user_id, status, address, last_act, menu_page) 
                            VALUES({event.obj.user_id}, 'user', 'not_stated', 'new_user', 0)''')
        if event.type == VkBotEventType.MESSAGE_NEW:
            user_id = event.obj.message['from_id']
            text = event.obj.message['text']
            #  логирование
            try:
                logging('Уведомление от', dt.datetime.now(), session_time=SESSION_TIME)
                logging('Новое сообщение от', user_id, 'с текстом', text, session_time=SESSION_TIME)
            except BaseException as e:
                print(e)
            try:
                result = cur.execute(f'''SELECT user_id, status, address, last_act FROM Users
                                         WHERE user_id = {user_id}''').fetchall()
                if not result:
                    raise WrongID
            except WrongID:
                cur.execute(f'''INSERT INTO Users(user_id, status, address, last_act, menu_page, current_dish, pay_way) 
                                VALUES({user_id}, 'user', 'not_stated', 'new_user', 0, 0, 'not_stated')''')
                con.commit()
                result = cur.execute(f'''SELECT user_id, status, address, last_act FROM Users
                                                        WHERE user_id = {user_id}''').fetchall()
            user_id, status, address, last_act = result[0]
            vk = vk_session.get_api()
            if text == '/stop':  # сброс пользователя в БД
                update_carousel_page(user_id, cur, con, 0)
                update_current_dish(user_id, cur, con, 0)
                update_basket(user_id, cur, con, vk, dish=0)
                update_last_act(user_id, cur, con, 'new_user')
                vk.messages.send(user_id=user_id,
                                 message="Ваш заказ сброшен",
                                 random_id=random.randint(0, 2 ** 64))
            else:
                if status == 'user':
                    if address == 'not_stated':
                        if last_act == 'new_user':
                            with open(path_to('data/keyboards', 'location.json'), 'r', encoding='UTF-8') as kb:
                                vk.messages.send(user_id=user_id,
                                                 message="На какой адрес нужно заказать пиццу?\n" +
                                                         "В любой момент напиши /stop, чтобы сбросить свой заказ",
                                                 random_id=random.randint(0, 2 ** 64), keyboard=kb.read())
                            update_last_act(user_id, cur, con, 'ask_address')
                    if last_act == 'ask_address':
                        update_address(user_id, cur, con, get_address(vk, event, user_id, cur, con))
                    if address != 'not_stated' and last_act == 'new_user':
                        conf_address(vk, address, user_id, cur, con)
                    if last_act == 'ask_conf_address':
                        if 'не' in text.lower():
                            update_last_act(user_id, cur, con, 'new_user')
                            get_address(vk, event, user_id, cur, con)
                        else:
                            if address != 'not_stated':
                                with open(path_to('data/keyboards', 'confirmation.json'), 'r', encoding='UTF-8') as kb:
                                    vk.messages.send(user_id=user_id,
                                                     message=f"Отлично, переходим к меню?",
                                                     random_id=random.randint(0, 2 ** 64), keyboard=kb.read())
                                    update_last_act(user_id, cur, con, 'ask_choosing')
                            else:
                                update_last_act(user_id, cur, con, 'new_user')
                    if last_act == 'ask_choosing':
                        if 'не' in text.lower():
                            with open(path_to('data/keyboards', 'confirmation.json'), 'r', encoding='UTF-8') as kb:
                                vk.messages.send(user_id=user_id,
                                                 message=f"Подумай ещё раз!",
                                                 random_id=random.randint(0, 2 ** 64), keyboard=kb.read())
                        else:
                            if 'carousel' in event.client_info.keys():  # проверяет, поддерживает ли устройство пользователя карусели
                                show_current_carousel(vk, cur, con, user_id)
                            else:
                                show_current_dish(vk, cur, con, user_id)
                    if last_act == 'show_carousel':
                        if text == 'Следующая страница!':
                            update_carousel_page(user_id, cur, con, 1)
                        elif text == 'Предыдущая страница!':
                            update_carousel_page(user_id, cur, con, -1)
                        else:
                            result = cur.execute(f"SELECT * FROM Menu WHERE name = '{text.rstrip()}'").fetchall()
                            if result:
                                update_basket(user_id, cur, con, vk, result[0], )
                            else:
                                vk.messages.send(user_id=user_id,
                                                 message="Такого блюда в меню нет, попробуй ещё раз!",
                                                 random_id=random.randint(0, 2 ** 64))
                        show_current_carousel(vk, cur, con, user_id)
                    if last_act == 'show_last_carousel':
                        if text == 'Назад к меню':
                            update_carousel_page(user_id, cur, con, 0)
                            show_current_carousel(vk, cur, con, user_id)
                        elif text == 'Идём в корзину!':
                            update_last_act(user_id, cur, con, 'go_to_basket')
                            show_basket(vk, cur, con, user_id)
                        else:
                            vk.messages.send(user_id=user_id,
                                             message="Я тебя не понял, попробуй ещё раз!",
                                             random_id=random.randint(0, 2 ** 64))
                            show_current_carousel(vk, cur, con, user_id)
                    if last_act == 'show_dish':
                        if text == 'Следующее блюдо!':
                            update_current_dish(user_id, cur, con, 1)
                            show_current_dish(vk, cur, con, user_id)
                        elif text == 'Предыдущее блюдо!':
                            update_current_dish(user_id, cur, con, -1)
                            show_current_dish(vk, cur, con, user_id)
                        else:
                            result = cur.execute(f"SELECT * FROM Menu WHERE name = '{text}'").fetchall()
                            if result:
                                update_basket(user_id, cur, con, vk, result[0], )
                            else:
                                vk.messages.send(user_id=user_id,
                                                 message="Такого блюда в меню нет, попробуй ещё раз!",
                                                 random_id=random.randint(0, 2 ** 64))
                            show_current_dish(vk, cur, con, user_id)
                    if last_act == 'show_last_dish':
                        if text == 'Назад к меню':
                            update_current_dish(user_id, cur, con, 0)
                            show_current_dish(vk, cur, con, user_id)
                        elif text == 'Идём в корзину!':
                            update_last_act(user_id, cur, con, 'go_to_basket')
                            show_basket(vk, cur, con, user_id)
                        else:
                            vk.messages.send(user_id=user_id,
                                             message="Я тебя не понял, попробуй ещё раз!",
                                             random_id=random.randint(0, 2 ** 64))
                            show_current_dish(vk, cur, con, user_id)
                    if last_act == 'show_basket':
                        if text == 'Оформляем!':
                            registration(vk, cur, con, user_id)
                        elif text == 'Давай кое-что удалим':
                            update_last_act(user_id, cur, con, 'edit_basket')
                            edit_basket(vk, cur, con, user_id)
                    if last_act == 'registration':
                        if text == 'Наличными курьеру' or text == 'Картой курьеру':
                            update_pay_way(user_id, cur, con, text)
                            finish(vk, cur, con, user_id)
                        else:
                            vk.messages.send(user_id=user_id,
                                             message="Что-то ты намудрил, отвечай лучше кнопками!",
                                             random_id=random.randint(0, 2 ** 64))
                            registration(vk, cur, con, user_id)
                    if last_act == 'edit_basket':
                        if text == 'Назад к оформлению':
                            registration(vk, cur, con, user_id)
                        else:
                            edit_basket(vk, cur, con, user_id, action='del', elem=text)
                    if last_act == 'ask_for_del':
                        edit_basket(vk, cur, con, user_id, action='del', elem=text)
                    if text == 'Назад к оформлению':
                        registration(vk, cur, con, user_id)
                    if last_act == 'show_empty_basket':
                        if text == 'К меню!':
                            if 'carousel' in event.client_info.keys():
                                show_current_carousel(vk, cur, con, user_id)
                            else:
                                show_current_dish(vk, cur, con, user_id)


if __name__ == '__main__':
    try:
        reason = main()
    except Exception as e:
        reason = e
    if reason:
        logging(dt.datetime.now().strftime("%d.%m.%Y_%H:%M:%S.%f"), ' — ', reason,
                file='main_log.txt', session_time=SESSION_TIME)
        sys.exit(
            f'Произошла ошибка в подключении к ВК или БД. Причина: {reason}. Исправьте ошибку и повторите попытку.')
