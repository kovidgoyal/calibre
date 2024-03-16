#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import bz2
import os
import sys
import ssl
from datetime import datetime, timezone
from urllib.request import urlopen


def download_from_calibre_server(url):
    ca = os.path.join(sys.resources_location, 'calibre-ebook-root-CA.crt')
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.load_verify_locations(ca)
    return urlopen(url, context=ssl_context).read()


def filter_ans(ans):
    return list(filter(None, (x.strip() for x in ans)))


def common_user_agents():
    print('Getting recent UAs...')
    raw = download_from_calibre_server('https://code.calibre-ebook.com/ua-popularity')
    ans = {}
    for line in bz2.decompress(raw).decode('utf-8').splitlines():
        count, ua = line.partition(':')[::2]
        count = int(count.strip())
        ua = ua.strip()
        if len(ua) > 25 and 'python' not in ua:
            ans[ua] = count
    return ans, list(sorted(ans, reverse=True, key=ans.__getitem__))


def all_desktop_platforms(user_agents):
    ans = set()
    for ua in user_agents:
        if ' Mobile ' not in ua and 'Mobile/' not in ua and ('Firefox/' in ua or 'Chrome/' in ua):
            plat = ua.partition('(')[2].partition(')')[0]
            parts = plat.split(';')
            if 'Firefox/' in ua:
                del parts[-1]
            ans.add(';'.join(parts))
    return ans


def get_data():
    ua_freq_map, common = common_user_agents()
    ans = {
        'common_user_agents': common,
        'user_agents_popularity': ua_freq_map,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    ans['desktop_platforms'] = list(all_desktop_platforms(ans['common_user_agents']))
    return ans
