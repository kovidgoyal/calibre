__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Device drivers.
'''

def devices():
    from calibre.devices.prs500.driver import PRS500
    from calibre.devices.prs505.driver import PRS505
    from calibre.devices.prs700.driver import PRS700
    from calibre.devices.cybookg3.driver import CYBOOKG3
    from calibre.devices.kindle.driver import KINDLE
    from calibre.devices.kindle.driver import KINDLE2
    from calibre.devices.bebook.driver import BEBOOK
    from calibre.devices.bebook.driver import BEBOOKMINI
    from calibre.devices.blackberry.driver import BLACKBERRY
    from calibre.devices.eb600.driver import EB600
    from calibre.devices.jetbook.driver import JETBOOK
    return (PRS500, PRS505, PRS700, CYBOOKG3, KINDLE, KINDLE2,
            BEBOOK, BEBOOKMINI, BLACKBERRY, EB600, JETBOOK)

import time

DAY_MAP   = dict(Sun=0, Mon=1, Tue=2, Wed=3, Thu=4, Fri=5, Sat=6)
MONTH_MAP = dict(Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6, Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12)
INVERSE_DAY_MAP = dict(zip(DAY_MAP.values(), DAY_MAP.keys()))
INVERSE_MONTH_MAP = dict(zip(MONTH_MAP.values(), MONTH_MAP.keys()))

def strptime(src):
    src = src.strip()
    src = src.split()
    src[0] = str(DAY_MAP[src[0][:-1]])+','
    src[2] = str(MONTH_MAP[src[2]])
    return time.strptime(' '.join(src), '%w, %d %m %Y %H:%M:%S %Z')

def strftime(epoch, zone=time.gmtime):
    src = time.strftime("%w, %d %m %Y %H:%M:%S GMT", zone(epoch)).split()
    src[0] = INVERSE_DAY_MAP[int(src[0][:-1])]+','
    src[2] = INVERSE_MONTH_MAP[int(src[2])]
    return ' '.join(src)
