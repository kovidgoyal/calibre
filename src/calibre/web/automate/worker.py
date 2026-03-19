#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>


import asyncio
import errno
import json
import os
import secrets
import sys
from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any

from calibre.constants import islinux, iswindows
from calibre.ptempfile import base_dir

if iswindows:
    from asyncio.windows_events import PipeServer

    import winutil
else:
    PipeServer = asyncio.Server

Handler = Callable[[Any], Awaitable[Any]]


def get_random_socket_path(name: str, random_suffix: str = '') -> str:
    random_suffix = random_suffix or secrets.token_hex(32)
    name = f'{name}-{random_suffix}'

    if iswindows:
        # Named Pipe for Windows
        return rf'\\.\pipe\{name}'
    if islinux:
        # Abstract Unix Socket for Linux (starts with null byte)
        return f'\x00{name}'
    # Standard Unix Domain Socket for macOS/BSD
    return os.path.join(base_dir(), f'{name}.sock')


class SingleObjectProtocol(asyncio.Protocol):

    def __init__(self, handler_callback: Handler):
        self.handler = handler_callback
        self.transport = None
        self._buffer = bytearray()

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        self._buffer.extend(data)

    def eof_received(self):
        # Client finished writing. Process what we have.
        self.task = asyncio.create_task(self._process_and_respond())
        return False  # Returning False closes the transport

    async def _process_and_respond(self):
        try:
            data = json.loads(self._buffer)
            self._buffer.clear()
            response = await self.handler(data)
            payload = {'response': response}
        except Exception as e:
            import traceback
            payload = {'exception': str(e), 'traceback': traceback.format_exc()}
        finally:
            self.transport.write(json.dumps(payload))
            self.transport.close()


async def echo(x):
    return x


class Server:

    def __init__(self, platform_implementation: asyncio.Server | PipeServer):
        self.platform_implementation = platform_implementation

    def close(self):
        self.platform_implementation.close()

    async def wait_closed(self):
        if hasattr(self.platform_implementation, 'wait_closed'):
            await self.platform_implementation.wait_closed()


async def start_server(
    handle_client: Handler = echo,
    name: str = 'calibre-aweb',
    random_suffix: str = '',
    num_attempts: int = 10,
) -> tuple[str, Server]:
    '''Tries to start the server, retrying on name collisions.'''
    loop = asyncio.get_running_loop()
    protocol_factory = partial(SingleObjectProtocol, handle_client)
    for attempt in range(num_attempts):
        path = get_random_socket_path(name, random_suffix)
        try:
            if iswindows:
                servers = await loop.start_serving_pipe(protocol_factory, path)
                assert len(servers) == 1
                server = servers[0]
            else:
                server = await asyncio.start_unix_server(protocol_factory, path=path)
            return path, Server(server)
        except OSError as e:
            if iswindows:
                exists = e.winerror in (winutil.ERROR_ACCESS_DENIED, winutil.ERROR_ALREADY_EXISTS, winutil.ERROR_PIPE_BUSY)
            else:
                exists = e.errno in (errno.EADDRINUSE, errno.EEXIST)
            if not exists:
                raise
            random_suffix = ''


async def no_setup() -> None:
    pass


async def handler_with_setup(
    x: Any, handler: Handler, setup: Callable[[], Awaitable[None]], setup_done: asyncio.Event, setup_lock: asyncio.Lock
) -> Any:
    if not setup_done.is_set():
        async with setup_lock:
            if not setup_done.is_set():
                await setup()
                setup_done.set()
    await setup_done.wait()
    return await handler(x)


async def watch_stdin():
    '''Abort mechanism: waits for stdin to close (EOF).'''
    reader = asyncio.StreamReader()
    await asyncio.get_running_loop().connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
    await reader.read()


async def async_main(
    # async handler that is called to handle each connection
    handler: Handler = echo,
    # global setup called exactly once when first connection arrives
    delayed_setup: Callable[[], Awaitable[None]] = no_setup,
    # called after server is shutdown
    finalizer: Callable[[], None] = lambda: None,
    read_input_data: bool = False,
) -> None:
    input_data = None
    if read_input_data:
        for line in sys.stdin:
            input_data = json.decode(line)
            break
        handler = partial(handler, input_data)
        delayed_setup = partial(delayed_setup, input_data)
        finalizer = partial(finalizer, input_data)
    setup_done = asyncio.Event()
    setup_lock = asyncio.Lock()
    wh = partial(handler_with_setup, handler=handler, setup=delayed_setup, setup_done=setup_done, setup_lock=setup_lock)
    abort_task = asyncio.create_task(watch_stdin())
    try:
        path, server = await start_server(wh)
        print(json.dumps(path), end='')
        sys.stdout.flush()
        if sys.stdout.isatty():
            print()
        else:
            sys.stdout.close()
        serving = asyncio.create_task(server.serve_forever())
        try:
            await asyncio.wait((serving, abort_task), return_when=asyncio.FIRST_COMPLETED)
        except asyncio.exceptions.CancelledError:
            if sys.stdout.isatty():
                print('Cancelled, closing', file=sys.stderr)
        finally:
            server.close()
            await server.wait_closed()
    finally:
        finalizer()


def main(*a, **kw) -> None:
    asyncio.run(async_main(*a, **kw))


def start_worker(handler: str, delayed_setup: str = '', finalize: str = '', input_data: Any = None) -> str:
    from calibre.utils.ipc.simple_worker import start_pipe_worker

    def parse(x: str) -> tuple[str, str, str]:
        module, func = x.partition(':')
        return module, func

    def imp(x: str) -> str:
        m, f = parse(x)
        return f'from {m} import {f}'

    command = [
        'from calibre.web.automate import main',
        imp(handler),
    ]
    if delayed_setup:
        command.append(imp(delayed_setup))
    if finalize:
        command.append(imp(finalize))
    invoke = f'main(handler={parse(handler)[1]}'
    if delayed_setup:
        invoke += f', delayed_setup={parse(delayed_setup)[1]}'
    if finalize:
        invoke += f', finalize={parse(finalize)[1]}'
    if input_data is not None:
        invoke += ', read_input_data=True'
    invoke += ')'
    command.append(invoke)
    p = start_pipe_worker(';'.join(command))
    if input_data is not None:
        stdin = json.dumps(input_data).encode()
        p.stdin.write(stdin)
        p.stdin.write(os.linesep.encode())
        p.stdin.flush()
    socket_path: str = json.decode(p.stdout.read())
    return socket_path


if __name__ == '__main__':
    main(echo)
