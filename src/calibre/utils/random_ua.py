#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import json
import random


def user_agent_data():
    ans = getattr(user_agent_data, 'ans', None)
    if ans is None:
        ans = user_agent_data.ans = json.loads(
            P('user-agent-data.json', data=True, allow_user_override=False))
    return ans


def common_english_words():
    ans = getattr(common_english_words, 'ans', None)
    if ans is None:
        ans = common_english_words.ans = tuple(x.strip() for x in P('common-english-words.txt', data=True).decode('utf-8').splitlines())
    return ans


def common_user_agents():
    return user_agent_data()['common_user_agents']


def common_chrome_user_agents():
    for x in user_agent_data()['common_user_agents']:
        if 'Chrome/' in x:
            yield x


def choose_randomly_by_popularity(ua_list):
    pm = user_agents_popularity_map()
    weights = None
    if pm:
        weights = tuple(map(pm.__getitem__, ua_list))
    return random.choices(ua_list, weights=weights)[0]


def random_common_chrome_user_agent():
    return choose_randomly_by_popularity(tuple(common_chrome_user_agents()))


def user_agents_popularity_map():
    return user_agent_data().get('user_agents_popularity', {})


def all_firefox_versions(limit=10):
    return user_agent_data()['firefox_versions'][:limit]


def random_desktop_platform():
    return random.choice(user_agent_data()['desktop_platforms'])


def all_chrome_versions(limit=10):
    return user_agent_data()['chrome_versions'][:limit]


def accept_header_for_ua(ua):
    # See https://developer.mozilla.org/en-US/docs/Web/HTTP/Content_negotiation/List_of_default_Accept_values
    if 'Firefox/' in ua:
        return 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
    return 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'


def common_english_word_ua():
    words = common_english_words()
    w1 = random.choice(words)
    w2 = w1
    while w2 == w1:
        w2 = random.choice(words)
    return f'{w1}/{w2}'
