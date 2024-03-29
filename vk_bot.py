import os
import random
from dotenv import load_dotenv
import redis
import redis_tools
import vk_api
from vk_api.utils import get_random_id
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from questions import get_all_questions


def create_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button('Новый вопрос', color=VkKeyboardColor.POSITIVE)
    keyboard.add_button('Сдаться', color=VkKeyboardColor.NEGATIVE)

    return keyboard.get_keyboard()


def handle_new_question(event, vk_api, redis, questions):
    try:
        rm_question, rm_answer = random.choice(tuple(questions.items()))
    except IndexError:
        rm_question, rm_answer = None, None
    if rm_question is not None:
        redis_tools.save_user(redis, event.user_id, rm_question, rm_answer)

        vk_api.messages.send(
            peer_id=event.user_id,
            random_id=get_random_id(),
            message=rm_question,
            keyboard=create_keyboard()
        )
    else:
        vk_api.messages.send(
            peer_id=event.user_id,
            random_id=get_random_id(),
            message='Вопросы закончились, приходите позже..'
        )


def handle_answer(event, vk_api, redis):
    user = redis_tools.get_user(redis, event.user_id)
    answer = user['last_answer']

    if event.text.lower().strip('.') == answer.lower().strip('.'):
        vk_api.messages.send(
            peer_id=event.user_id,
            random_id=get_random_id(),
            message='Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»',
            keyboard=create_keyboard()
        )
    else:
        vk_api.messages.send(
            peer_id=event.user_id,
            random_id=get_random_id(),
            message='Неправильно... Попробуешь ещё раз?',
            keyboard=create_keyboard()
        )


def handle_give_up(event, vk_api, redis):
    user = redis_tools.get_user(redis, event.user_id)
    if user:
        answer = user.get('last_answer')
    else:
        answer = None
    redis_tools.clear_user(redis, event.user_id)

    vk_api.messages.send(
        peer_id=event.user_id,
        random_id=get_random_id(),
        message=f'Ответ был {answer}\nДля следущего вопроса нажми "Новый вопрос"',
        keyboard=create_keyboard()
    )


def main():
    db_url = os.getenv('REDIS_DATABASE')
    db_port = os.getenv('REDIS_PORT')
    db_password = os.getenv('REDIS_PSWRD')
    token = os.getenv('VK_TOKEN')

    vk_session = vk_api.VkApi(token=token)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    all_questions = get_all_questions()
    redis_db = redis.StrictRedis(
        host=db_url, port=db_port, password=db_password, charset='utf-8', decode_responses=True)

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:

            if event.text.lower() in ['начать', 'start', 'старт']:
                vk.messages.send(
                    peer_id=event.user_id,
                    random_id=get_random_id(),
                    message='Начнем игру..',
                    keyboard=create_keyboard()
                )
            elif event.text.lower() in ['закончить', 'стоп', 'end', 'stop']:
                vk.messages.send(
                    peer_id=event.user_id,
                    random_id=get_random_id(),
                    message='Игра закончилась. Чтобы начать заново, напечатайте начать, старт или start.'
                )
            elif event.text == 'Новый вопрос':
                handle_new_question(event, vk, redis_db, all_questions)
            elif event.text == 'Сдаться':
                handle_give_up(event, vk, redis_db)
            else:
                handle_answer(event, vk, redis_db)


if __name__ == "__main__":
    load_dotenv()
    main()
