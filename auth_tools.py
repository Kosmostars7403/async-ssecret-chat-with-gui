import asyncio
import json
import logging
import os

import aiofiles

from chat_tools import read_message, submit_message

logger = logging.getLogger('sender')


class InvalidToken(Exception):
    pass


def check_token_existence():
    if os.path.exists('token.txt'):
        with open('token.txt', 'r') as file:
            return file.read()
    return None


async def register(writer, reader, username):
    writer.write(b'\n')  # Empty line for create new account
    await writer.drain()

    server_message = await read_message(reader)  # Server ask for preferred nickname
    logger.debug(server_message)

    await submit_message(writer, username)
    auth_response = await reader.readline()
    account_hash = json.loads(auth_response.decode())['account_hash']

    async with aiofiles.open('token.txt', mode='w', encoding='utf-8') as file:
        await file.write(account_hash)

    logger.debug(f'Your token is {account_hash}. Save it, please!')

    return account_hash


async def authorize(writer, reader, token):
    if not token:
        logger.error('You are not logged in. Log in or register.')
        raise InvalidToken
    await asyncio.wait_for(submit_message(writer, token), 10)
    auth_response = await read_message(reader)

    auth_response = json.loads(auth_response)
    if not auth_response:
        logger.error('Wrong token. Try again or register a new username.')
        raise InvalidToken
    logger.error(f'Successfully authorized with nickname {auth_response["nickname"]}')
    return auth_response['nickname']
