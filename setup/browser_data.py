#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import bz2
import os
import sys
from datetime import datetime
from urllib.request import urlopen

from setup import download_securely


def download_from_calibre_server(url):
    ca = os.path.join(sys.resources_location, 'calibre-ebook-root-CA.crt')
    with urlopen(url, cafile=ca) as f:
        return f.read()


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


def firefox_versions():
    print('Getting firefox versions...')
    import html5lib
    raw = download_securely(
        'https://www.mozilla.org/en-US/firefox/releases/').decode('utf-8')
    root = html5lib.parse(raw, treebuilder='lxml', namespaceHTMLElements=False)
    ol = root.xpath('//main[@id="main-content"]/ol')[0]
    ol.xpath('descendant::li/strong/a[@href]')
    ans = filter_ans(ol.xpath('descendant::li/strong/a[@href]/text()'))
    if not ans:
        raise ValueError('Failed to download list of firefox versions')
    return ans


def chrome_versions():
    print('Getting chrome versions...')
    import html5lib
    raw = download_securely(
        'https://en.wikipedia.org/wiki/Google_Chrome_version_history').decode('utf-8')
    root = html5lib.parse(raw, treebuilder='lxml', namespaceHTMLElements=False)
    table = root.xpath('//*[@id="mw-content-text"]//tbody')[-1]
    ans = []
    for tr in table.iterchildren('tr'):
        cells = tuple(tr.iterchildren('td'))
        if not cells:
            continue
        if not cells[2].text or not cells[2].text.strip():
            continue
        s = cells[0].get('style')
        if '#a0e75a' not in s and 'salmon' not in s:
            break
        chrome_version = cells[0].text.strip()
        ts = datetime.strptime(cells[1].text.strip().split()[
                               0], '%Y-%m-%d').date().strftime('%Y-%m-%d')
        try:
            webkit_version = cells[2].text.strip().split()[1]
        except IndexError:
            continue
        ans.append({'date': ts, 'chrome_version': chrome_version,
                    'webkit_version': webkit_version})
    return list(reversed(ans))


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
        'chrome_versions': chrome_versions(),
        'firefox_versions': firefox_versions(),
        'common_user_agents': common,
        'user_agents_popularity': ua_freq_map,
        'timestamp': datetime.utcnow().isoformat() + '+00:00',
    }
    ans['desktop_platforms'] = list(all_desktop_platforms(ans['common_user_agents']))
    return ans
