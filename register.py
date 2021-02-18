import asyncio
import tkinter as tk
from tkinter.scrolledtext import ScrolledText

from anyio import create_task_group

from auth_tools import register
from chat_tools import connect_to_chat
from gui import TkAppClosed, update_tk, SendingConnectionStateChanged

import constants


def fetch_and_validate_form_values(values, events_queue, info_queue):
    host, port, nickname = [value.get() for value in values]

    if not nickname:
        info_queue.put_nowait('Укажите желаемый никнейм!')
        return

    events_queue.put_nowait((host, port, nickname))


async def listen_register(events_queue, info_queue, token_field):
    while True:
        host, port, nickmane = await events_queue.get()
        try:
            async with connect_to_chat(
                    host, port,
                    info_queue,
                    SendingConnectionStateChanged
            ) as (reader, writer):
                token = await register(writer, reader, nickmane)
                token_field.delete(0, tk.END)
                token_field.insert(0, token)
                info_queue.put_nowait(f'Регистрация прошла успешно! Ваш токен:{token}')
                info_queue.put_nowait('Токен сохранен в файл token.txt')
        except ConnectionError:
            info_queue.put_nowait('Ошибка соединения, проверьте ввод адреса или попробуйте позже.')


async def show_info_log(info_queue, info_text_area):
    while True:
        info_message = await info_queue.get()

        info_text_area.configure(state='normal')
        info_text_area.insert(tk.END, str(info_message) + '\n')
        info_text_area.configure(state='disabled')


async def draw(events_queue, info_queue):
    root = tk.Tk()
    root.title('Регистрация в подпольном чате Майнкрафта')

    root_frame = tk.Frame()
    root_frame.pack(fill='both', expand=True)
    
    host_frame = tk.Frame(root_frame)
    host_label = tk.Label(host_frame, text='Адрес сервера: ', width=15, pady=5)
    host_field = tk.Entry(host_frame, width=40)
    host_field.insert(0, constants.MINECHAT_WRITE_HOST)
    host_frame.pack()
    host_label.pack(side=tk.LEFT)
    host_field.pack(expand=1)

    port_frame = tk.Frame(root_frame)
    port_label = tk.Label(port_frame, text='Порт сервера: ', width=15, pady=5)
    port_field = tk.Entry(port_frame, width=40)
    port_field.insert(0, constants.MINECHAT_WRITE_PORT)
    port_frame.pack()
    port_label.pack(side=tk.LEFT)
    port_field.pack(expand=1)

    nickname_frame = tk.Frame(root_frame)
    nickname_label = tk.Label(nickname_frame, text='Желаемый никнейм: ', width=15, pady=5)
    nickname_field = tk.Entry(nickname_frame, width=40)
    nickname_field.insert(0, '')
    nickname_frame.pack()
    nickname_label.pack(side=tk.LEFT)
    nickname_field.pack(expand=1)

    register_button_frame = tk.Frame(root_frame)
    register_button = tk.Button(register_button_frame, text='Зарегистрироваться')
    register_button_frame.pack()
    register_button.pack()

    token_frame = tk.Frame(root_frame)
    token_label = tk.Label(token_frame, text='Ваш токен: ', width=15, pady=5)
    token_field = tk.Entry(token_frame, width=40)
    token_field.insert(0, '')
    token_frame.pack()
    token_label.pack(side=tk.LEFT)
    token_field.pack(expand=1)

    info_frame = tk.Frame(root_frame)
    info_text_area = ScrolledText(info_frame, state='disabled', height=5)
    info_frame.pack()
    info_text_area.pack(expand=1)

    register_button['command'] = lambda: fetch_and_validate_form_values(
        (host_field, port_field, nickname_field),
        events_queue,
        info_queue
    )

    async with create_task_group() as tg:
        await tg.spawn(update_tk, root)
        await tg.spawn(listen_register, events_queue, info_queue, token_field)
        await tg.spawn(show_info_log, info_queue, info_text_area)


async def main():
    events_queue = asyncio.Queue()
    info_queue = asyncio.Queue()
    try:
        await draw(events_queue, info_queue)
    except (TkAppClosed, KeyboardInterrupt):
        pass


if __name__ == '__main__':
    asyncio.run(main())