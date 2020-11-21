import builtins
import os
import sys
import _sitebuiltins


def nuke_stdout():
    # Redirect stdout, stdin and stderr to /dev/null
    from calibre_extensions.speedup import detach
    detach(os.devnull)


def set_helper():
    builtins.help = _sitebuiltins._Helper()


def set_quit():
    eof = 'Ctrl-D (i.e. EOF)'
    builtins.quit = _sitebuiltins.Quitter('quit', eof)
    builtins.exit = _sitebuiltins.Quitter('exit', eof)


def main():
    sys.argv[0] = sys.calibre_basename
    set_helper()
    set_quit()
    mod = __import__(sys.calibre_module, fromlist=[1])
    func = getattr(mod, sys.calibre_function)
    if sys.gui_app and not (
        sys.stdout.isatty() or sys.stderr.isatty() or sys.stdin.isatty()
    ):
        # this has to be done after calibre is imported and therefore
        # calibre_extensions is available.
        nuke_stdout()
    return func()


if __name__ == '__main__':
    main()
