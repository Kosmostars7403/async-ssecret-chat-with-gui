import asyncio
import logging
import os
from datetime import datetime
from tkinter import messagebox
import time

import aiofiles
import configargparse
from async_timeout import timeout
from anyio import create_task_group

import gui
from auth_tools import authorize, InvalidToken, check_token_existence
from chat_tools import connect_to_chat, read_message, submit_message
from constants import *
from ping_connection import ping, pong

logger = logging.getLogger('watchdog_logger')


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
            chat_message = await read_message(reader)
            message_received_time = datetime.now().strftime('%d.%m.%y %H:%M:%S')
            chat_message = f'[{message_received_time}] {chat_message}'

            queues[WATCHDOG_QUEUE].put_nowait('New message in chat')
            queues[MESSAGES_QUEUE].put_nowait(chat_message.replace('\n', ''))  # replace for ignore empty strings
            queues[HISTORY_QUEUE].put_nowait(chat_message)


async def send_user_message(writer, queues):
    while True:
        msg = await queues[SENDING_QUEUE].get()
        await submit_message(writer, msg)
        queues[WATCHDOG_QUEUE].put_nowait('Message sent')


async def send_msgs(host, port, queues):
    async with connect_to_chat(
            host, port,
            queues[STATUS_UPDATE_QUEUE],
            gui.SendingConnectionStateChanged
    ) as (reader, writer):

        queues[WATCHDOG_QUEUE].put_nowait('Prompt before auth')

        try:
            nickname = await authorize(writer, reader, options.minechat_token)
            queues[WATCHDOG_QUEUE].put_nowait('Authorization done')
            event = gui.NicknameReceived(nickname)
            queues[STATUS_UPDATE_QUEUE].put_nowait(event)
        except InvalidToken:
            messagebox.showinfo(
                "Неверный токен",
                "Проверьте токен, сервер его не узнал. Доступно только чтение чата."
            )
            return

        async with create_task_group() as tg:
            await tg.spawn(send_user_message, writer, queues)
            await tg.spawn(ping, writer)
            await tg.spawn(pong, reader, queues[WATCHDOG_QUEUE])


async def watch_for_connection(queue):
    while True:
        try:
            async with timeout(2) as cm:
                log_message = await queue.get()
                timestamp = int(time.time())
                logger.debug(f'[{timestamp}] Connection is alive. {log_message}')
        except asyncio.TimeoutError:
            if cm.expired:
                logger.debug(f'[{timestamp}] 1s timeout is elapsed')
            raise ConnectionError


async def handle_connection(options, queues):
    while True:
        try:
            async with create_task_group() as tg:
                await tg.spawn(send_msgs, options.write_host, options.write_port, queues)
                await tg.spawn(read_msgs, options.read_host, options.read_port, queues)
                await tg.spawn(watch_for_connection, queues[WATCHDOG_QUEUE])
        except ConnectionError:
            logger.error(f'Connection failed, start new attempt in {RECONNECT_DELAY} seconds.')
            await asyncio.sleep(RECONNECT_DELAY)


async def main(options, queues):
    async with create_task_group() as tg:
        await tg.spawn(gui.draw, queues[MESSAGES_QUEUE], queues[SENDING_QUEUE], queues[STATUS_UPDATE_QUEUE])
        await tg.spawn(handle_connection, options, queues)
        await tg.spawn(save_msgs, options.history, queues[HISTORY_QUEUE])


def get_application_options():
    parser = configargparse.ArgParser('Minecraft chat sender.')

    parser.add('--read_host', help='Host for connection.', default=MINECHAT_READ_HOST, env_var='MINECHAT_WRITE_HOST')
    parser.add('--write_host', help='Host for connection.', default=MINECHAT_WRITE_HOST, env_var='MINECHAT_READ_HOST')
    parser.add('--read_port', help='Port for connection.', default=MINECHAT_READ_PORT, env_var='MINECHAT_WRITE_PORT')
    parser.add('--write_port', help='Port for connection.', default=MINECHAT_WRITE_PORT, env_var='MINECHAT_READ_PORT')
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
        HISTORY_QUEUE: asyncio.Queue(),
        WATCHDOG_QUEUE: asyncio.Queue()
    }

    logging.basicConfig(level=logging.DEBUG)
    options = get_application_options()
    loop = asyncio.get_event_loop()

    loop.run_until_complete(main(options, queues))
