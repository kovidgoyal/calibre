#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

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


def random_firefox_version():
    versions = user_agent_data()['firefox_versions'][:7]
    return random.choice(versions)


def random_desktop_platform():
    return random.choice(user_agent_data()['desktop_platforms'])


def random_firefox_ua():
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/User-Agent/Firefox
    return 'Mozilla/5.0 ({p}; rv:{ver}) Gecko/20100101 Firefox/{ver}'.format(
        p=random_desktop_platform(), ver=random_firefox_version())


def random_chrome_version():
    versions = user_agent_data()['chrome_versions'][:7]
    return random.choice(versions)


def random_chrome_ua():
    v = random_chrome_version()
    return 'Mozilla/5.0 ({p}) AppleWebKit/{wv} (KHTML, like Gecko) Chrome/{cv} Safari/{wv}'.format(
        p=random_desktop_platform(), wv=v['webkit_version'], cv=v['chrome_version'])


def random_user_agent():
    return random.choice((random_chrome_ua, random_firefox_ua))()
