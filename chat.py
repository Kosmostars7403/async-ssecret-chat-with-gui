import asyncio
import os
from datetime import datetime
from tkinter import messagebox

import aiofiles
import configargparse

import gui
from auth_tools import authorize, InvalidToken, check_token_existence
from chat_tools import connect_to_chat, read_message, submit_message
from constants import *


async def restore_chat_history(queue):
    if os.path.exists(CHAT_LOG_PATH):
        async with aiofiles.open(CHAT_LOG_PATH, mode='r', encoding='utf-8') as file:
            chat_history = await file.read()
            queue.put_nowait(chat_history[:-1])  # slice for ignore last empty string


async def save_msgs(filepath, queue):
    while True:
        async with aiofiles.open(filepath, mode='a', encoding='utf-8') as file:
            message = await queue.get()
            await file.write(message)


async def read_msgs(host, port, queues):
    await restore_chat_history(queues[MESSAGES_QUEUE])

    async with connect_to_chat(
            host, port,
            queues[STATUS_UPDATE_QUEUE],
            gui.ReadConnectionStateChanged
    ) as (reader, writer):

        while True:
            chat_message = await asyncio.wait_for(read_message(reader), 10)
            message_received_time = datetime.now().strftime('%d.%m.%y %H:%M:%S')
            chat_message = f'[{message_received_time}] {chat_message}'

            queues[MESSAGES_QUEUE].put_nowait(chat_message.replace('\n', ''))  # replace for ignore empty strings
            queues[HISTORY_QUEUE].put_nowait(chat_message)


async def send_msgs(host, port, queues):
    async with connect_to_chat(
            host, port,
            queues[STATUS_UPDATE_QUEUE],
            gui.SendingConnectionStateChanged
    ) as (reader, writer):

        try:
            nickname = await authorize(writer, reader, options.minechat_token)
            event = gui.NicknameReceived(nickname)
            queues[STATUS_UPDATE_QUEUE].put_nowait(event)
        except InvalidToken:
            messagebox.showinfo(
                "Неверный токен",
                "Проверьте токен, сервер его не узнал. Доступно только чтение чата."
            )
            return
        while True:
            msg = await queues[SENDING_QUEUE].get()
            await submit_message(writer, msg)


async def main(options, queues):

    await asyncio.gather(
        gui.draw(queues[MESSAGES_QUEUE], queues[SENDING_QUEUE], queues[STATUS_UPDATE_QUEUE]),
        read_msgs(options.host, options.port, queues),
        save_msgs(options.history, queues[HISTORY_QUEUE]),
        send_msgs(options.host, SENDING_PORT, queues)
    )


def get_application_options():
    parser = configargparse.ArgParser('Minecraft chat sender.')

    parser.add('--host', help='Host for connection.', default=MINECHAT_HOST, env_var='MINECHAT_HOST')
    parser.add('--port', help='Port for connection.', default=LISTENING_PORT, env_var='LISTENING_PORT')
    parser.add('--history', help='Path for history file.', default=CHAT_LOG_PATH, env_var='CHAT_LOG_PATH')
    auth_args = parser.add_mutually_exclusive_group()
    auth_args.add('--minechat_token', help='Authorization token.', default=check_token_existence(), env_var='MINECHAT_TOKEN')
    auth_args.add('--username', help='Choose username for registration.')

    return parser.parse_args()


if __name__ == '__main__':
    queues = {
        STATUS_UPDATE_QUEUE: asyncio.Queue(),
        MESSAGES_QUEUE: asyncio.Queue(),
        SENDING_QUEUE: asyncio.Queue(),
        HISTORY_QUEUE: asyncio.Queue()
    }

    options = get_application_options()
    loop = asyncio.get_event_loop()

    loop.run_until_complete(main(options, queues))
