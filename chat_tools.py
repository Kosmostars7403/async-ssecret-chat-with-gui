import asyncio
import logging
from contextlib import asynccontextmanager


RECONNECT_DELAY = 5

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
    while True:
        queue.put_nowait(state_indicator.INITIATED)
        try:
            reader, writer = await asyncio.open_connection(host, port)
            await read_message(reader)  # server start message

            queue.put_nowait(state_indicator.ESTABLISHED)
            yield reader, writer
            break
        except asyncio.TimeoutError:
            logger.error('Timeout error with server connection!')
            raise
        except ConnectionResetError:
            logger.error(f'Connection failed, start new attempt in {RECONNECT_DELAY}')
            await asyncio.sleep(RECONNECT_DELAY)
            continue
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()
            queue.put_nowait(state_indicator.CLOSED)
            logger.debug('Connection closed.')
