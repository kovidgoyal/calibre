#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

import json
import random

from calibre.utils.resources import get_path as P

_user_agent_data_cache = None
_common_english_words_cache: tuple | None = None


def user_agent_data():
    global _user_agent_data_cache
    if _user_agent_data_cache is None:
        _user_agent_data_cache = json.loads(P('user-agent-data.json', data=True, allow_user_override=False))
    return _user_agent_data_cache


def common_english_words():
    global _common_english_words_cache
    if _common_english_words_cache is None:
        _common_english_words_cache = tuple(x.strip() for x in P('common-english-words.txt', data=True).decode('utf-8').splitlines())
    return _common_english_words_cache


def random_english_text(max_num_sentences=3, min_words_per_sentence=8, max_words_per_sentence=41):
    import random

    num_sentences = random.randrange(1, max_num_sentences + 1)
    words = common_english_words()

    def sentence():
        num_words = random.randrange(min_words_per_sentence, max_words_per_sentence + 1)
        return ' '.join(random.choice(words) for i in range(num_words)).capitalize() + '.'

    return ' '.join(sentence() for i in range(num_sentences))


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


def random_desktop_platform():
    return random.choice(user_agent_data()['desktop_platforms'])


def accept_header_for_ua(ua):
    # See https://developer.mozilla.org/en-US/docs/Web/HTTP/Content_negotiation/List_of_default_Accept_values
    if 'Firefox/' in ua:
        return 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
    return 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'


def common_english_word_ua():
    words = common_english_words()
    w1 = w2 = random.choice(words)
    while w2 == w1:
        w2 = random.choice(words)
    return f'{w1}/{w2}'
