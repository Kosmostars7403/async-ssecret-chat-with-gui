import asyncio


async def ping(writer):
    while True:
        writer.write( b'\n')
        await writer.drain()
        await asyncio.sleep(1)


async def pong(reader, queue):
    while True:
        msg = await reader.readline()
        if msg == b'':
            await asyncio.sleep(1)
        await queue.put('')
