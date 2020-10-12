#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import json
import random


def user_agent_data():
    ans = getattr(user_agent_data, 'ans', None)
    if ans is None:
        ans = user_agent_data.ans = json.loads(
            P('user-agent-data.json', data=True, allow_user_override=False))
    return ans


def common_user_agents():
    return user_agent_data()['common_user_agents']


def all_firefox_versions(limit=10):
    return user_agent_data()['firefox_versions'][:limit]


def random_firefox_version():
    return random.choice(all_firefox_versions())


def random_desktop_platform():
    return random.choice(user_agent_data()['desktop_platforms'])


def render_firefox_ua(platform, version):
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/User-Agent/Firefox
    return 'Mozilla/5.0 ({p}; rv:{ver}) Gecko/20100101 Firefox/{ver}'.format(
        p=platform, ver=version)


def random_firefox_ua():
    render_firefox_ua(random_desktop_platform(), random_firefox_version())


def all_chrome_versions(limit=10):
    return user_agent_data()['chrome_versions'][:limit]


def random_chrome_version():
    return random.choice(all_chrome_versions())


def render_chrome_ua(platform, version):
    return 'Mozilla/5.0 ({p}) AppleWebKit/{wv} (KHTML, like Gecko) Chrome/{cv} Safari/{wv}'.format(
        p=platform, wv=version['webkit_version'], cv=version['chrome_version'])


def random_chrome_ua():
    return render_chrome_ua(random_desktop_platform(), random_chrome_version())


def all_user_agents():
    ans = getattr(all_user_agents, 'ans', None)
    if ans is None:
        uas = []
        g = globals()
        platforms = user_agent_data()['desktop_platforms']
        for b in ('chrome', 'firefox'):
            versions = g['all_%s_versions' % b]()
            func = g['render_%s_ua' % b]
            for v in versions:
                for p in platforms:
                    uas.append(func(p, v))
        random.shuffle(uas)
        ans = all_user_agents.ans = tuple(uas)
    return ans


def random_user_agent():
    return random.choice(all_user_agents())


def accept_header_for_ua(ua):
    if 'Firefox/' in ua:
        return 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    return 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
