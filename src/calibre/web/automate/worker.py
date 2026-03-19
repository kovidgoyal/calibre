#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>


import asyncio
import errno
import json
import os
import secrets
import socket
import struct
import sys
from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any, NamedTuple

from calibre.constants import islinux, ismacos, iswindows
from calibre.ptempfile import base_dir
from calibre.utils.serialize import msgpack_dumps, msgpack_loads

if iswindows:
    from asyncio.windows_events import PipeServer

    from calibre_extensions import winutil
else:
    PipeServer = asyncio.Server

Handler = Callable[[Any], Awaitable[Any]]


def get_random_socket_path(name: str, random_suffix: str = '') -> str:
    # Bloody primitive macOS has a 104 character limit on socket paths and uses
    # insanely long paths for user private tmp dirs. Sigh.
    random_suffix = random_suffix or secrets.token_hex(8 if ismacos else 32)
    name = f'{name}-{random_suffix}'

    if iswindows:
        # Named Pipe for Windows
        return rf'\\.\pipe\{name}'
    if islinux:
        # Abstract Unix Socket for Linux (starts with null byte)
        return f'\x00{name}'
    # Standard Unix Domain Socket for macOS/BSD
    return os.path.join(base_dir(), f'{name}.sock')


def debug(*a, **kw):
    kw['file'] = sys.stderr
    kw['flush'] = True
    print(*a, **kw)


class SingleObjectProtocol(asyncio.Protocol):

    def __init__(self, handler_callback: Handler):
        self.handler = handler_callback
        self.transport = None
        self.expected_length = None
        self.task = None
        self._buffer = bytearray()

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        self._buffer.extend(data)
        if self.expected_length is None and len(self._buffer) > 3:
            header = self._buffer[:4]
            del self._buffer[:4]
            self.expected_length = struct.unpack('!I', header)[0]
        if self.expected_length is not None and len(self._buffer) >= self.expected_length:
            complete_data = self._buffer[:self.expected_length]
            del self._buffer[:self.expected_length]
            self.expected_length = None
            self.task = asyncio.create_task(self._process_and_respond(complete_data))

    def eof_received(self):
        if self.task is None:
            payload = {'exception': 'Complete message not received from client'}
            self.transport.write(msgpack_dumps(payload))
        return False  # Returning False closes the transport

    async def _process_and_respond(self, data: bytearray):
        try:
            data = msgpack_loads(data)
            self._buffer.clear()
            response = await self.handler(data)
            payload = {'response': response}
        except Exception as e:
            import traceback
            payload = {'exception': str(e), 'traceback': traceback.format_exc()}
        finally:
            self.transport.write(msgpack_dumps(payload))
            self.transport.close()


async def echo(x):
    return x


class Server:

    def __init__(self, platform_implementation: asyncio.Server | list[asyncio.Transport]):
        self.platform_implementation = platform_implementation

    def close(self) -> None:
        if isinstance(self.platform_implementation, asyncio.Server):
            self.platform_implementation.close()
        else:
            for x in self.platform_implementation:
                x.close()

    async def serve_till_stdin_is_closed(self) -> None:
        if isinstance(self.platform_implementation, asyncio.Server):
            reader = asyncio.StreamReader()
            await asyncio.get_running_loop().connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
            abort_task = asyncio.create_task(reader.read())
            serving = asyncio.create_task(self.platform_implementation.serve_forever())
            await asyncio.wait((serving, abort_task), return_when=asyncio.FIRST_COMPLETED)
        else:
            loop = asyncio.get_running_loop()
            abort_task = loop.run_in_executor(None, sys.stdin.read)
            await abort_task
        self.close()
        await self.wait_closed()

    async def wait_closed(self) -> None:
        if isinstance(self.platform_implementation, asyncio.Server):
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
                server = await loop.start_serving_pipe(protocol_factory, path)
            else:
                sock = None
                if path.startswith('/'):
                    # Python's stdlib deletes the socket file
                    # if it exists with no way to prevent that. Sigh.
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    try:
                        sock.bind(path)
                        server = await loop.create_unix_server(protocol_factory, sock=sock)
                    except Exception:
                        sock.close()
                        raise
                else:
                    server = await loop.create_unix_server(protocol_factory, path=path)
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
            input_data = json.loads(line)
            break
        handler = partial(handler, input_data)
        delayed_setup = partial(delayed_setup, input_data)
        finalizer = partial(finalizer, input_data)
    setup_done = asyncio.Event()
    setup_lock = asyncio.Lock()
    wh = partial(handler_with_setup, handler=handler, setup=delayed_setup, setup_done=setup_done, setup_lock=setup_lock)
    stdout_is_tty = sys.stdout.isatty()
    try:
        path, server = await start_server(wh)
        sys.__stdout__.write(json.dumps(path))
        sys.__stdout__.flush()
        if stdout_is_tty:
            print()
        else:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.__stdout__.fileno())
            os.close(devnull)
        try:
            await server.serve_till_stdin_is_closed()
        except asyncio.exceptions.CancelledError:
            if stdout_is_tty:
                print('Cancelled, closing', file=sys.stderr)
    finally:
        finalizer()


def main(*a, **kw) -> None:
    asyncio.run(async_main(*a, **kw))


def start_worker(
    handler: str = '', delayed_setup: str = '', finalizer: str = '', input_data: Any = None
) -> tuple[str, Callable[[], None]]:
    '''
    Run the specified handler, delayed_setup and finalizer functions in a worker process, passing input_data (if not None)
    to each function as its first parameter.

    Returns: path the worker is listening on for connections and a function to gracefully kill the worker. The worker
    will anyway gracefully close when its parent process closes. The function is mainly useful for testing.
    '''
    from calibre.utils.ipc.simple_worker import start_pipe_worker

    def parse(x: str) -> tuple[str, str, str]:
        module, _, func = x.partition(':')
        return module, func

    def imp(x: str) -> str:
        m, f = parse(x)
        return f'from {m} import {f}'

    command = [
        'import os, sys',
        'os.set_inheritable(sys.stdout.fileno(), False)',
        'os.set_inheritable(sys.stdin.fileno(), False)',
        'from calibre.web.automate.worker import main',
    ]
    args = []
    if handler:
        command.append(imp(handler))
        args.append(f'handler={parse(handler)[1]}')
    if delayed_setup:
        command.append(imp(delayed_setup))
        args.append(f'delayed_setup={parse(delayed_setup)[1]}')
    if finalizer:
        command.append(imp(finalizer))
        args.append(f'finalizer={parse(finalizer)[1]}')
    if input_data is not None:
        args.append('read_input_data=True')
    invoke = f'main({", ".join(args)})'
    command.append(invoke)
    p = start_pipe_worker('\n'.join(command))
    if input_data is not None:
        stdin = json.dumps(input_data).encode()
        p.stdin.write(stdin)
        p.stdin.write(os.linesep.encode())
        p.stdin.flush()
    path_data = p.stdout.read()
    try:
        socket_path: str = json.loads(path_data)
    except Exception:
        raise ValueError(f'Got invalid response from worker process: {path_data}')
    def close_and_reap():
        p.stdin.close()
        return p.wait()
    return socket_path, close_and_reap


class Response(NamedTuple):
    response: Any = None
    exception: str = ''
    traceback: str = ''


def make_request(worker_path: str, data: Any = None) -> Response:
    ' Make a request and get a response from the worker '
    data = msgpack_dumps(data)
    datalen = struct.pack('!I', len(data))
    if iswindows:
        with open(worker_path, 'r+b', buffering=0) as w:
            w.write(datalen)
            w.write(data)
            w.flush()
            resdata = w.read()
    else:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(worker_path)
            with s.makefile('wb', buffering=0) as f_write:
                f_write.write(datalen)
                f_write.write(data)
                f_write.flush()
            s.shutdown(socket.SHUT_WR)
            with s.makefile('rb') as f_read:
                resdata = f_read.read()
    r = msgpack_loads(resdata)
    return Response(r.get('response'), r.get('exception', ''), r.get('traceback'))


if __name__ == '__main__':
    main(echo)
