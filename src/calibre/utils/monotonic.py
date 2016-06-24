# vim:fileencoding=utf-8

from calibre.constants import plugins

monotonicp, err = plugins['monotonic']
if err:
    # This happens on systems with very old glibc that does not
    # have clock_gettime() (glibc < 2.17 http://stackoverflow.com/a/32649327)
    if 'undefined symbol: clock_gettime' in err:
        raise RuntimeError('Your glibc version is too old, glibc >= 2.17 is required')
    raise RuntimeError('Failed to load the monotonic module with error: ' + err)
monotonic = monotonicp.monotonic
del monotonicp, err
