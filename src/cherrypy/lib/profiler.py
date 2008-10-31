"""Profiler tools for CherryPy.

CherryPy users
==============

You can profile any of your pages as follows:

    from cherrypy.lib import profiler
    
    class Root:
        p = profile.Profiler("/path/to/profile/dir")
        
        def index(self):
            self.p.run(self._index)
        index.exposed = True
        
        def _index(self):
            return "Hello, world!"
    
    cherrypy.tree.mount(Root())


You can also turn on profiling for all requests
using the make_app function as WSGI middleware.


CherryPy developers
===================

This module can be used whenever you make changes to CherryPy,
to get a quick sanity-check on overall CP performance. Use the
"--profile" flag when running the test suite. Then, use the serve()
function to browse the results in a web browser. If you run this
module from the command line, it will call serve() for you.

"""


# Make profiler output more readable by adding __init__ modules' parents.
def new_func_strip_path(func_name):
    filename, line, name = func_name
    if filename.endswith("__init__.py"):
        return os.path.basename(filename[:-12]) + filename[-12:], line, name
    return os.path.basename(filename), line, name

try:
    import profile
    import pstats
    pstats.func_strip_path = new_func_strip_path
except ImportError:
    profile = None
    pstats = None
    import warnings
    msg = ("Your installation of Python does not have a profile module. "
           "If you're on Debian, you can apt-get python2.4-profiler from "
           "non-free in a separate step. See http://www.cherrypy.org/wiki/"
           "ProfilingOnDebian for details.")
    warnings.warn(msg)

import os, os.path
import sys

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO


_count = 0

class Profiler(object):
    
    def __init__(self, path=None):
        if not path:
            path = os.path.join(os.path.dirname(__file__), "profile")
        self.path = path
        if not os.path.exists(path):
            os.makedirs(path)
    
    def run(self, func, *args, **params):
        """Dump profile data into self.path."""
        global _count
        c = _count = _count + 1
        path = os.path.join(self.path, "cp_%04d.prof" % c)
        prof = profile.Profile()
        result = prof.runcall(func, *args, **params)
        prof.dump_stats(path)
        return result
    
    def statfiles(self):
        """statfiles() -> list of available profiles."""
        return [f for f in os.listdir(self.path)
                if f.startswith("cp_") and f.endswith(".prof")]
    
    def stats(self, filename, sortby='cumulative'):
        """stats(index) -> output of print_stats() for the given profile."""
        sio = StringIO.StringIO()
        if sys.version_info >= (2, 5):
            s = pstats.Stats(os.path.join(self.path, filename), stream=sio)
            s.strip_dirs()
            s.sort_stats(sortby)
            s.print_stats()
        else:
            # pstats.Stats before Python 2.5 didn't take a 'stream' arg,
            # but just printed to stdout. So re-route stdout.
            s = pstats.Stats(os.path.join(self.path, filename))
            s.strip_dirs()
            s.sort_stats(sortby)
            oldout = sys.stdout
            try:
                sys.stdout = sio
                s.print_stats()
            finally:
                sys.stdout = oldout
        response = sio.getvalue()
        sio.close()
        return response
    
    def index(self):
        return """<html>
        <head><title>CherryPy profile data</title></head>
        <frameset cols='200, 1*'>
            <frame src='menu' />
            <frame name='main' src='' />
        </frameset>
        </html>
        """
    index.exposed = True
    
    def menu(self):
        yield "<h2>Profiling runs</h2>"
        yield "<p>Click on one of the runs below to see profiling data.</p>"
        runs = self.statfiles()
        runs.sort()
        for i in runs:
            yield "<a href='report?filename=%s' target='main'>%s</a><br />" % (i, i)
    menu.exposed = True
    
    def report(self, filename):
        import cherrypy
        cherrypy.response.headers['Content-Type'] = 'text/plain'
        return self.stats(filename)
    report.exposed = True


class ProfileAggregator(Profiler):
    
    def __init__(self, path=None):
        Profiler.__init__(self, path)
        global _count
        self.count = _count = _count + 1
        self.profiler = profile.Profile()
    
    def run(self, func, *args):
        path = os.path.join(self.path, "cp_%04d.prof" % self.count)
        result = self.profiler.runcall(func, *args)
        self.profiler.dump_stats(path)
        return result


class make_app:
    def __init__(self, nextapp, path=None, aggregate=False):
        """Make a WSGI middleware app which wraps 'nextapp' with profiling."""
        self.nextapp = nextapp
        self.aggregate = aggregate
        if aggregate:
            self.profiler = ProfileAggregator(path)
        else:
            self.profiler = Profiler(path)
    
    def __call__(self, environ, start_response):
        def gather():
            result = []
            for line in self.nextapp(environ, start_response):
                result.append(line)
            return result
        return self.profiler.run(gather)


def serve(path=None, port=8080):
    import cherrypy
    cherrypy.config.update({'server.socket_port': int(port),
                            'server.thread_pool': 10,
                            'environment': "production",
                            })
    cherrypy.quickstart(Profiler(path))


if __name__ == "__main__":
    serve(*tuple(sys.argv[1:]))

