import asyncio
import logging
from contextlib import asynccontextmanager
import socket

from async_timeout import timeout


logger = logging.getLogger('chat_tools')


async def submit_message(writer, message):
    message = message.replace('\n', '')
    writer.write(message.encode(encoding='utf-8') + b'\n\n')
    await writer.drain()


async def read_message(reader):
    message = await reader.readline()
    return message.decode()


@asynccontextmanager
async def connect_to_chat(host, port, queue, state_indicator):
    reader = writer = None
    queue.put_nowait(state_indicator.INITIATED)
    try:
        try:
            async with timeout(1):
                reader, writer = await asyncio.open_connection(host, port)
                queue.put_nowait(state_indicator.ESTABLISHED)
        except (asyncio.TimeoutError, socket.gaierror, ConnectionRefusedError):
            logger.error('Error with server connection!')
            raise ConnectionError

        try:
            await read_message(reader)  # server start message
            yield reader, writer
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()
    finally:
        queue.put_nowait(state_indicator.CLOSED)
        logger.debug('Connection closed.')
