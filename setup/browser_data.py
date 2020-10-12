#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import os
import json
import gzip
import io
from datetime import datetime

from setup import download_securely

from polyglot.builtins import filter

is_ci = os.environ.get('CI', '').lower() == 'true'


def filter_ans(ans):
    return list(filter(None, (x.strip() for x in ans)))


def common_user_agents():
    if is_ci:
        return [
            # IE 11 - windows 10
            'Mozilla/5.0 (Windows NT 10.0; Trident/7.0; rv:11.0) like Gecko',
            # IE 11 - windows 8.1
            'Mozilla/5.0 (Windows NT 6.3; Trident/7.0; rv:11.0) like Gecko',
            # IE 11 - windows 8
            'Mozilla/5.0 (Windows NT 6.2; Trident/7.0; rv:11.0) like Gecko',
            # IE 11 - windows 7
            'Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko',
            # 32bit IE 11 on 64 bit win 10
            'Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko',
            # 32bit IE 11 on 64 bit win 8.1
            'Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; rv:11.0) like Gecko',
            # 32bit IE 11 on 64 bit win 7
            'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko',
        ]
    print('Getting recent UAs...')
    raw = download_securely(
        'https://raw.githubusercontent.com/intoli/user-agents/master/src/user-agents.json.gz')
    data = json.loads(gzip.GzipFile(fileobj=io.BytesIO(raw)).read())
    uas = []
    for item in data:
        ua = item['userAgent']
        if not ua.startswith('Opera'):
            uas.append(ua)
    ans = filter_ans(uas)[:256]
    if not ans:
        raise ValueError('Failed to download list of common UAs')
    return ans


def firefox_versions():
    if is_ci:
        return '51.0 50.0'.split()
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
    if is_ci:
        return []
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
        if 'Mobile/' not in ua and ('Firefox/' in ua or 'Chrome/' in ua):
            plat = ua.partition('(')[2].partition(')')[0]
            parts = plat.split(';')
            if 'Firefox/' in ua:
                del parts[-1]
            ans.add(';'.join(parts))
    return ans


def get_data():
    ans = {
        'chrome_versions': chrome_versions(),
        'firefox_versions': firefox_versions(),
        'common_user_agents': common_user_agents(),
    }
    ans['desktop_platforms'] = list(all_desktop_platforms(ans['common_user_agents']))
    return ans
