__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Perform various initialization tasks.
'''

import locale, sys, os

# Default translation is NOOP
import __builtin__
__builtin__.__dict__['_'] = lambda s: s

# For strings which belong in the translation tables, but which shouldn't be
# immediately translated to the environment language
__builtin__.__dict__['__'] = lambda s: s

from calibre.constants import iswindows, preferred_encoding, plugins

_run_once = False
winutil = winutilerror = None

if not _run_once:
    _run_once = True

    ################################################################################
    # Platform specific modules
    if iswindows:
        winutil, winutilerror = plugins['winutil']
        if not winutil:
            raise RuntimeError('Failed to load the winutil plugin: %s'%winutilerror)
        if len(sys.argv) > 1 and not isinstance(sys.argv[1], unicode):
            sys.argv[1:] = winutil.argv()[1-len(sys.argv):]

    ################################################################################
    # Convert command line arguments to unicode
    for i in range(1, len(sys.argv)):
        if not isinstance(sys.argv[i], unicode):
            sys.argv[i] = sys.argv[i].decode(preferred_encoding, 'replace')

    ################################################################################
    # Setup resources
    import calibre.utils.resources as resources
    resources


    ################################################################################
    # Setup translations
    from calibre.utils.localization import set_translators

    set_translators()

    ################################################################################
    # Initialize locale
    try:
        locale.setlocale(locale.LC_ALL, '')
    except:
        dl = locale.getdefaultlocale()
        try:
            if dl:
                locale.setlocale(dl[0])
        except:
            pass

    ################################################################################
    # Improve builtin path functions to handle unicode sensibly

    _abspath = os.path.abspath
    def my_abspath(path, encoding=sys.getfilesystemencoding()):
        '''
        Work around for buggy os.path.abspath. This function accepts either byte strings,
        in which it calls os.path.abspath, or unicode string, in which case it first converts
        to byte strings using `encoding`, calls abspath and then decodes back to unicode.
        '''
        to_unicode = False
        if encoding is None:
            encoding = preferred_encoding
        if isinstance(path, unicode):
            path = path.encode(encoding)
            to_unicode = True
        res = _abspath(path)
        if to_unicode:
            res = res.decode(encoding)
        return res

    os.path.abspath = my_abspath

    _join = os.path.join
    def my_join(a, *p):
        encoding=sys.getfilesystemencoding()
        if not encoding:
            encoding = preferred_encoding
        p = [a] + list(p)
        _unicode = False
        for i in p:
            if isinstance(i, unicode):
                _unicode = True
                break
        p = [i.encode(encoding) if isinstance(i, unicode) else i for i in p]

        res = _join(*p)
        if _unicode:
            res = res.decode(encoding)
        return res

    os.path.join = my_join

    def local_open(name, mode='r', bufsize=-1):
        '''
        Open a file that wont be inherited by child processes

        Only supports the following modes:
            r, w, a, rb, wb, ab, r+, w+, a+, r+b, w+b, a+b
        '''
        if iswindows:
            class fwrapper(object):
                def __init__(self, name, fobject):
                    object.__setattr__(self, 'fobject', fobject)
                    object.__setattr__(self, 'name', name)

                def __getattribute__(self, attr):
                    if attr == 'name':
                        return object.__getattribute__(self, attr)
                    fobject = object.__getattribute__(self, 'fobject')
                    return getattr(fobject, attr)

                def __setattr__(self, attr, val):
                    fobject = object.__getattribute__(self, 'fobject')
                    return setattr(fobject, attr, val)

                def __repr__(self):
                    fobject = object.__getattribute__(self, 'fobject')
                    name = object.__getattribute__(self, 'name')
                    return repr(fobject).replace('>', ' name='+repr(name)+'>')

                def __str__(self):
                    return repr(self)

                def __unicode__(self):
                    return repr(self).decode('utf-8')


            m = mode[0]
            random = len(mode) > 1 and mode[1] == '+'
            binary = mode[-1] == 'b'

            if m == 'a':
                flags = os.O_APPEND| os.O_RDWR
                flags |= os.O_RANDOM if random else os.O_SEQUENTIAL
            elif m == 'r':
                if random:
                    flags = os.O_RDWR | os.O_RANDOM
                else:
                    flags = os.O_RDONLY | os.O_SEQUENTIAL
            elif m == 'w':
                if random:
                    flags = os.O_RDWR | os.O_RANDOM
                else:
                    flags = os.O_WRONLY | os.O_SEQUENTIAL
                flags |= os.O_TRUNC | os.O_CREAT
            if binary:
                flags |= os.O_BINARY
            else:
                flags |= os.O_TEXT
            flags |= os.O_NOINHERIT
            fd = os.open(name, flags)
            ans = os.fdopen(fd, mode, bufsize)
            ans = fwrapper(name, ans)
        else:
            import fcntl
            try:
                cloexec_flag = fcntl.FD_CLOEXEC
            except AttributeError:
                cloexec_flag = 1
            ans = open(name, mode, bufsize)
            old = fcntl.fcntl(ans, fcntl.F_GETFD)
            fcntl.fcntl(ans, fcntl.F_SETFD, old | cloexec_flag)
        return ans

    __builtin__.__dict__['lopen'] = local_open

def test_lopen():
    from calibre.ptempfile import TemporaryDirectory
    from calibre import CurrentDir
    n = u'f\xe4llen'

    with TemporaryDirectory() as tdir:
        with CurrentDir(tdir):
            with lopen(n, 'w') as f:
                f.write('one')
            print 'O_CREAT tested'
            with lopen(n, 'w+b') as f:
                f.write('two')
            with lopen(n, 'r') as f:
                if f.read() == 'two':
                    print 'O_TRUNC tested'
                else:
                    raise Exception('O_TRUNC failed')
            with lopen(n, 'ab') as f:
                f.write('three')
            with lopen(n, 'r+') as f:
                if f.read() == 'twothree':
                    print 'O_APPEND tested'
                else:
                    raise Exception('O_APPEND failed')
            with lopen(n, 'r+') as f:
                f.seek(3)
                f.write('xxxxx')
                f.seek(0)
                if f.read() == 'twoxxxxx':
                    print 'O_RANDOM tested'
                else:
                    raise Exception('O_RANDOM failed')



