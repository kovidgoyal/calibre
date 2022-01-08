#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import importlib
import os
import sys
from threading import Thread
from zipimport import ZipImportError

from calibre import prints
from calibre.constants import ismacos, iswindows
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.serialize import pickle_dumps
from polyglot.binary import from_hex_unicode
from polyglot.queue import Queue

if iswindows:
    from multiprocessing.connection import PipeConnection as Connection
else:
    from multiprocessing.connection import Connection

PARALLEL_FUNCS = {
    'lrfviewer'    :
    ('calibre.gui2.lrf_renderer.main', 'main', None),

    'ebook-viewer'    :
    ('calibre.gui_launch', 'ebook_viewer', None),

    'ebook-edit' :
    ('calibre.gui_launch', 'gui_ebook_edit', None),

    'store-dialog' :
    ('calibre.gui_launch', 'store_dialog', None),

    'toc-dialog' :
    ('calibre.gui_launch', 'toc_dialog', None),

    'webengine-dialog' :
    ('calibre.gui_launch', 'webengine_dialog', None),

    'render_pages' :
    ('calibre.ebooks.comic.input', 'render_pages', 'notification'),

    'gui_convert'     :
    ('calibre.gui2.convert.gui_conversion', 'gui_convert', 'notification'),

    'gui_convert_recipe'     :
    ('calibre.gui2.convert.gui_conversion', 'gui_convert_recipe', 'notification'),

    'gui_polish'     :
    ('calibre.ebooks.oeb.polish.main', 'gui_polish', None),

    'gui_convert_override'     :
    ('calibre.gui2.convert.gui_conversion', 'gui_convert_override', 'notification'),

    'gui_catalog'     :
    ('calibre.gui2.convert.gui_conversion', 'gui_catalog', 'notification'),

    'arbitrary' :
    ('calibre.utils.ipc.worker', 'arbitrary', None),

    'arbitrary_n' :
    ('calibre.utils.ipc.worker', 'arbitrary_n', 'notification'),
}


class Progress(Thread):

    def __init__(self, conn):
        Thread.__init__(self)
        self.daemon = True
        self.conn = conn
        self.queue = Queue()

    def __call__(self, percent, msg=''):
        self.queue.put((percent, msg))

    def run(self):
        while True:
            x = self.queue.get()
            if x is None:
                break
            try:
                eintr_retry_call(self.conn.send, x)
            except:
                break


def arbitrary(module_name, func_name, args, kwargs={}):
    '''
    An entry point that allows arbitrary functions to be run in a parallel
    process. useful for plugin developers that want to run jobs in a parallel
    process.

    To use this entry point, simply create a ParallelJob with the module and
    function names for the real entry point.

    Remember that args and kwargs must be serialized so only use basic types
    for them.

    To use this, you will do something like

    from calibre.gui2 import Dispatcher
    gui.job_manager.run_job(Dispatcher(job_done), 'arbitrary',
        args=('calibre_plugins.myplugin.worker', 'do_work',
                ('arg1' 'arg2', 'arg3')),
                description='Change the world')

    The function job_done will be called on completion, see the code in
    gui2.actions.catalog for an example of using run_job and Dispatcher.

    :param module_name: The fully qualified name of the module that contains
    the actual function to be run. For example:
    calibre_plugins.myplugin.worker
    :param func_name: The name of the function to be run.
    :param name: A list (or tuple) of arguments that will be passed to the
    function ``func_name``
    :param kwargs: A dictionary of keyword arguments to pass to func_name
    '''
    if module_name.startswith('calibre_plugins'):
        # Initialize the plugin loader by doing this dummy import
        from calibre.customize.ui import find_plugin
        find_plugin
    module = importlib.import_module(module_name)
    func = getattr(module, func_name)
    return func(*args, **kwargs)


def arbitrary_n(module_name, func_name, args, kwargs={},
        notification=lambda x, y: y):
    '''
    Same as :func:`arbitrary` above, except that func_name must support a
    keyword argument "notification". This will be a function that accepts two
    arguments. func_name should call it periodically with progress information.
    The first argument is a float between 0 and 1 that represent percent
    completed and the second is a string with a message (it can be an empty
    string).
    '''
    if module_name.startswith('calibre_plugins'):
        # Initialize the plugin loader by doing this dummy import
        from calibre.customize.ui import find_plugin
        find_plugin
    module = importlib.import_module(module_name)
    func = getattr(module, func_name)
    kwargs['notification'] = notification
    return func(*args, **kwargs)


def get_func(name):
    module, func, notification = PARALLEL_FUNCS[name]
    try:
        module = importlib.import_module(module)
    except ZipImportError:
        # Something windows weird happened, try clearing the zip import cache
        # in case the zipfile was changed from under us
        from zipimport import _zip_directory_cache as zdc
        zdc.clear()
        module = importlib.import_module(module)
    func = getattr(module, func)
    return func, notification


def main():
    if iswindows:
        if '--multiprocessing-fork' in sys.argv:
            # We are using the multiprocessing module on windows to launch a
            # worker process
            from multiprocessing import freeze_support
            freeze_support()
            return 0
    if ismacos and 'CALIBRE_WORKER_FD' not in os.environ and 'CALIBRE_SIMPLE_WORKER' not in os.environ and '--pipe-worker' not in sys.argv:
        # On some OS X computers launchd apparently tries to
        # launch the last run process from the bundle
        # so launch the gui as usual
        from calibre.gui2.main import main as gui_main
        return gui_main(['calibre'])
    niceness = os.environ.pop('CALIBRE_WORKER_NICENESS', None)
    if niceness:
        try:
            os.nice(int(niceness))
        except Exception:
            pass
    csw = os.environ.pop('CALIBRE_SIMPLE_WORKER', None)
    if csw:
        mod, _, func = csw.partition(':')
        mod = importlib.import_module(mod)
        func = getattr(mod, func)
        func()
        return
    if '--pipe-worker' in sys.argv:
        try:
            exec(sys.argv[-1])
        except Exception:
            print('Failed to run pipe worker with command:', sys.argv[-1])
            sys.stdout.flush()
            raise
        return
    fd = int(os.environ['CALIBRE_WORKER_FD'])
    resultf = from_hex_unicode(os.environ['CALIBRE_WORKER_RESULT'])
    with Connection(fd) as conn:
        name, args, kwargs, desc = eintr_retry_call(conn.recv)
        if desc:
            prints(desc)
            sys.stdout.flush()
        func, notification = get_func(name)
        notifier = Progress(conn)
        if notification:
            kwargs[notification] = notifier
            notifier.start()

        result = func(*args, **kwargs)
        if result is not None:
            os.makedirs(os.path.dirname(resultf), exist_ok=True)
            with lopen(resultf, 'wb') as f:
                f.write(pickle_dumps(result))

        notifier.queue.put(None)

    try:
        sys.stdout.flush()
    except OSError:
        pass  # Happens sometimes on OS X for GUI processes (EPIPE)
    try:
        sys.stderr.flush()
    except OSError:
        pass  # Happens sometimes on OS X for GUI processes (EPIPE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
