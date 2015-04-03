#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import curses, os, select, fcntl, errno, re
from io import BlockingIOError
from future_builtins import map
from threading import Thread

clean_pat = re.compile(b'[\n\r\f\v]')

def debug(*args):
    print (*args, file=open('/tmp/log', 'a'))

def show_buf(window, fname, buf, keep_trailing=True):
    while buf:
        n = buf.find(b'\n')
        if n == -1:
            if not keep_trailing:
                show_line(window, bytes(buf), fname)
                del buf[:]
            break
        show_line(window, bytes(buf[:n]), fname)
        del buf[:n + 1]

def nonblocking_readlines(window, fileobj, buf, name, copy_to=None):
    while True:
        try:
            byts = fileobj.read()
        except BlockingIOError:
            break
        except EnvironmentError as err:
            if err.errno == errno.EAGAIN:
                break
            raise

        if not byts:
            break
        if copy_to is not None:
            copy_to.write(byts)

        buf.extend(byts)
        show_buf(window, name, buf)

def show_line(window, line, fname):
    line = clean_pat.sub(b'', line)
    max_lines, max_chars = window.getmaxyx()
    title = str(b" %s " % fname)
    if line:
        continue_prompt = b'> '
        max_line_len = max_chars - 2
        if len(line) > max_line_len:
            first_portion = line[0:max_line_len - 1]
            trailing_len = max_line_len - (len(continue_prompt) + 1)
            remaining = [line[i:i + trailing_len]
                            for i in range(max_line_len - 1, len(line), trailing_len)]
            line_portions = [first_portion] + remaining
        else:
            line_portions = [line]

        def addstr(i, text):
            try:
                if i > 0:
                    window.addstr(continue_prompt, curses.color_pair(1))
                window.addstr(text + b'\n')
            except curses.error:
                pass

        for i, line_portion in enumerate(line_portions):
            y, x = window.getyx()
            y = max(1, y)
            if y >= max_lines - 1:
                window.move(1, 1)
                window.deleteln()
                window.move(y - 1, 1)
                window.deleteln()
                addstr(i, line_portion)
            else:
                window.move(y, x + 1)
                addstr(i, line_portion)

    window.border()
    y, x = window.getyx()
    window.addstr(0, max_chars // 2 - len(title) // 2, title, curses.A_BOLD)
    window.move(y, x)
    window.refresh()

def mainloop(scr, files, control_file, copy_to, name_map):
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    rows, columns = scr.getmaxyx()
    half_columns = columns // 2
    windows = []
    if len(files) == 1:
        windows.append(curses.newwin(rows, columns, 0, 0))
    elif len(files) == 2:
        windows.append(curses.newwin(rows, half_columns, 0, 0))
        windows.append(curses.newwin(rows, half_columns, 0, half_columns))
    elif len(files) == 3:
        windows.append(curses.newwin(rows // 2, half_columns, 0, 0))
        windows.append(curses.newwin(rows // 2, half_columns, 0, half_columns))
        windows.append(curses.newwin(rows // 2, half_columns, rows // 2, 0))
    elif len(files) == 4:
        windows.append(curses.newwin(rows // 2, half_columns, 0, 0))
        windows.append(curses.newwin(rows // 2, half_columns, 0, half_columns))
        windows.append(curses.newwin(rows // 2, half_columns, rows // 2, 0))
        windows.append(curses.newwin(rows // 2, half_columns, rows // 2, half_columns))
    window_map = dict(zip(files, windows))
    buffer_map = {f:bytearray() for f in files}
    handles = set([control_file] + list(files))
    if copy_to is not None:
        copy_to = {h:dest for h, dest in zip(files, copy_to)}
    else:
        copy_to = {}
    name_map = {h:name_map.get(h, h.name) for h in files}

    def flush_buffer(h):
        show_buf(window_map[h], name_map[h], buffer_map[h], keep_trailing=False)

    run = True
    while run:
        readable, writable, error = select.select(list(handles), [], list(handles))
        for h in error:
            if h is control_file:
                run = False
                break
            else:
                flush_buffer(h)
            handles.discard(h)
        for h in readable:
            if h is control_file:
                run = False
                break
            nonblocking_readlines(window_map[h], h, buffer_map[h], name_map[h], copy_to.get(h))

    tuple(map(flush_buffer, files))

def watch(pipes, control_file, copy_to, name_map):
    try:
        curses.wrapper(mainloop, pipes, control_file, copy_to, name_map)
    except KeyboardInterrupt:
        pass

def multitail(pipes, name_map=None, copy_to=None):
    if not 1 <= len(pipes) <= 4:
        raise ValueError('Can only watch 1-4 files at a time')
    r, w = pipe()
    t = Thread(target=watch, args=(pipes, r, copy_to, name_map or {}))
    t.daemon = True
    t.start()
    def stop():
        try:
            w.write(b'0'), w.flush(), w.close()
        except IOError:
            pass
        t.join()
    return stop, t.is_alive

def pipe():
    r, w = os.pipe()
    r, w = os.fdopen(r, 'r'), os.fdopen(w, 'w')
    fl = fcntl.fcntl(r, fcntl.F_GETFL)
    fcntl.fcntl(r, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    return r, w

def test():
    import random, time
    r1, w1 = pipe()
    r2, w2 = pipe()
    r3, w3 = pipe()
    with w1, w2, w3:
        files = (w1, w2, w3)
        stop, is_alive = multitail((r1, r2, r3))
        try:
            num = 0
            while is_alive():
                num += 1
                print (((' %dabc\r' % num) * random.randint(9, 100)), file=random.choice(files))
                [f.flush() for f in files]
                time.sleep(1)
        except KeyboardInterrupt:
            stop()

if __name__ == '__main__':
    test()
