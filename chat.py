import asyncio
import os
from datetime import datetime

import aiofiles
import configargparse

import gui
from auth_tools import authorize
from chat_tools import connect_to_chat, read_message, submit_message


MINECHAT_HOST = 'minechat.dvmn.org'
SENDING_PORT = 5050
LISTENING_PORT = 5000
CHAT_LOG_PATH = 'chat_log.txt'


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


async def read_msgs(host, port, msgs_queue, history_queue):
    await restore_chat_history(msgs_queue)
    async with connect_to_chat(host, port) as (reader, writer):
        while True:
            chat_message = await asyncio.wait_for(read_message(reader), 10)
            message_received_time = datetime.now().strftime('%d.%m.%y %H:%M:%S')
            chat_message = f'[{message_received_time}] {chat_message}'
            msgs_queue.put_nowait(chat_message.replace('\n', ''))  # replace for ignore empty strings
            history_queue.put_nowait(chat_message)


async def send_msgs(writer, queue):
    while True:
        msg = await queue.get()
        await submit_message(writer, msg)


async def main(options):
    async with connect_to_chat(options.host, SENDING_PORT) as (reader, writer):
        messages_queue = asyncio.Queue()
        sending_queue = asyncio.Queue()
        status_updates_queue = asyncio.Queue()
        history_queue = asyncio.Queue()

        await authorize(writer, reader, options.minechat_token)

        await asyncio.gather(
            gui.draw(messages_queue, sending_queue, status_updates_queue),
            read_msgs(options.host, options.port, messages_queue, history_queue),
            save_msgs(options.history, history_queue),
            send_msgs(writer, sending_queue)
        )


def check_token_existence():
    if os.path.exists('token.txt'):
        with open('token.txt', 'r') as file:
            return file.read()
    return None


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
    options = get_application_options()
    loop = asyncio.get_event_loop()

    loop.run_until_complete(main(options))
