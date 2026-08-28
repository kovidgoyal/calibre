#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Storage for the "Create Your Own Adventure" game GUI. Preferences,
# including the AI configuration and the list of user created worlds, are
# stored in cyoa/prefs.json in the calibre config directory. Games are
# stored one per sub folder of the cyoa folder, each as a single game.json
# file containing all game data including per turn pictures. API keys are
# NOT stored here, they live in the common AI preferences; all other AI
# provider settings used for the game are scoped to these preferences via
# override_prefs_for_providers(). This module must not import Qt so that it
# can be used and tested headless.

import json
import os
import shutil
from contextlib import AbstractContextManager
from functools import lru_cache
from time import time
from typing import TYPE_CHECKING, Any, Literal

from calibre.ai import AICapabilities
from calibre.ai.cyoa import GameState, GeneratedWorld, as_jsonable, deserialize_game, serialize_game
from calibre.ai.prefs import override_prefs_for_providers, plugins_for_purpose, update_prefs_for_provider
from calibre.ai.structured import instantiate, spec_for_class
from calibre.constants import config_dir
from calibre.customize import AIProviderPlugin
from calibre.utils.config import JSONConfig
from calibre.utils.config_base import commit_data
from calibre.utils.short_uuid import uuid4

if TYPE_CHECKING:
    from unittest.suite import TestSuite
else:
    TestSuite = object

GAME_FILE_VERSION = 1
GAME_FILE_NAME = 'game.json'
AIPurpose = Literal['text', 'image']
PURPOSE_CAPABILITIES: dict[str, AICapabilities] = {
    'text': AICapabilities.text_to_text,
    'image': AICapabilities.text_to_image,
}


@lru_cache(2)
def prefs() -> JSONConfig:
    # No secrets are stored here, API keys live in the common AI preferences
    ans = JSONConfig('cyoa/prefs')
    ans.defaults['ai'] = {}
    ans.defaults['image_skipped'] = False
    ans.defaults['worlds'] = []
    ans.defaults['current_game'] = ''
    return ans


def cyoa_dir() -> str:
    return os.path.join(config_dir, 'cyoa')


# AI configuration {{{


def save_ai_settings(kind: AIPurpose, provider_name: str, settings: dict[str, Any]) -> None:
    # Store the API key in the common AI preferences, so it is shared with
    # the rest of calibre, and everything else in the dedicated CYOA
    # preferences.
    settings = dict(settings)
    if api_key := settings.pop('api_key', None):
        update_prefs_for_provider(provider_name, {'api_key': api_key})
    p = prefs()
    ai = p['ai']
    ai[kind] = {'provider': provider_name, 'settings': settings}
    p.set('ai', ai)


def ai_settings(kind: AIPurpose) -> dict[str, Any]:
    return prefs()['ai'].get(kind) or {}


def configured_provider_name(kind: AIPurpose) -> str:
    return ai_settings(kind).get('provider', '')


def mark_image_skipped(skipped: bool = True) -> None:
    prefs().set('image_skipped', skipped)


def image_skipped() -> bool:
    return bool(prefs()['image_skipped'])


def plugin_for(kind: AIPurpose) -> AIProviderPlugin | None:
    name = configured_provider_name(kind)
    if not name:
        return None
    for p in plugins_for_purpose(PURPOSE_CAPABILITIES[kind]):
        if p.name == name:
            return p
    return None


def prefs_overlay() -> dict[str, dict[str, Any]]:
    ans: dict[str, dict[str, Any]] = {}
    for kind in ('text', 'image'):
        e = ai_settings(kind)
        if e.get('provider'):
            ans.setdefault(e['provider'], {}).update(e.get('settings') or {})
    return ans


def cyoa_ai_settings() -> AbstractContextManager[None]:
    # All AI readiness checks, config widget construction and AI calls made
    # by the game must run inside this context manager, in the calling
    # thread, so that model, effort, etc. come from the CYOA preferences
    # while API keys fall through to the common AI preferences. Note that
    # some providers (Ollama, LM Studio, OpenAI compatible) cache values
    # derived from the api_url/headers preferences, so scoping those keys
    # can serve stale values within a process.
    return override_prefs_for_providers(prefs_overlay())


def is_ready(kind: AIPurpose = 'text') -> bool:
    p = plugin_for(kind)
    if p is None:
        return False
    with cyoa_ai_settings():
        return bool(p.is_ready_for_use)


# }}}


# Saved games {{{


def game_dir(game_id: str, base: str = '') -> str:
    return os.path.join(base or cyoa_dir(), game_id)


def game_file(game_id: str, base: str = '') -> str:
    return os.path.join(game_dir(game_id, base), GAME_FILE_NAME)


def new_game_id(base: str = '') -> str:
    while True:
        ans = uuid4()
        if not os.path.exists(game_dir(ans, base)):
            return ans


def save_game(game_id: str, state: GameState, images: dict[int, dict[str, str]] | None = None, base: str = '') -> None:
    # images maps turn number to {'mime': mime type, 'data': base64 encoded image data}
    gf = game_file(game_id, base)
    created = time()
    try:
        with open(gf, 'rb') as f:
            created = json.load(f).get('created') or created
    except Exception:
        pass
    data = {
        'version': GAME_FILE_VERSION,
        'title': state.world.title,
        'created': created,
        'updated': time(),
        'game': json.loads(serialize_game(state)),
        'images': {str(k): v for k, v in (images or {}).items()},
    }
    commit_data(gf, json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))


def load_game(game_id: str, base: str = '') -> tuple[GameState, dict[int, dict[str, str]]]:
    with open(game_file(game_id, base), 'rb') as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get('version') != GAME_FILE_VERSION:
        raise ValueError(f'Not a valid CYOA game file: {game_file(game_id, base)}')
    state = deserialize_game(json.dumps(data['game']))
    images = {int(k): v for k, v in (data.get('images') or {}).items()}
    return state, images


def list_games(base: str = '') -> list[tuple[str, str]]:
    # All saved games as (game_id, title) tuples, most recently played first.
    entries: list[tuple[float, str, str]] = []
    base = base or cyoa_dir()
    try:
        candidates = os.listdir(base)
    except OSError:
        return []
    for x in candidates:
        gf = game_file(x, base)
        if os.path.exists(gf):
            try:
                with open(gf, 'rb') as f:
                    data = json.load(f)
            except Exception:
                continue
            entries.append((data.get('updated') or 0, x, data.get('title') or x))
    entries.sort(reverse=True)
    return [(game_id, title) for _updated, game_id, title in entries]


def delete_game(game_id: str, base: str = '') -> None:
    if current_game_id() == game_id:
        set_current_game('')
    shutil.rmtree(game_dir(game_id, base), ignore_errors=True)


def current_game_id() -> str:
    return prefs()['current_game']


def set_current_game(game_id: str) -> None:
    prefs().set('current_game', game_id)


# }}}


# User created worlds {{{


def saved_worlds() -> list[dict[str, Any]]:
    return prefs()['worlds']


def add_saved_world(brief: str, world: GeneratedWorld) -> None:
    jw = as_jsonable(world, spec_for_class(GeneratedWorld))
    p = prefs()
    worlds = p['worlds']
    if any(e.get('world') == jw for e in worlds):
        return
    worlds.append({'brief': brief, 'created': time(), 'world': jw})
    p.set('worlds', worlds)


def world_from_saved(entry: dict[str, Any]) -> GeneratedWorld:
    ans = instantiate(entry['world'], spec_for_class(GeneratedWorld), GeneratedWorld.__name__)
    assert isinstance(ans, GeneratedWorld)
    return ans


def remove_saved_world(index: int) -> None:
    p = prefs()
    worlds = p['worlds']
    del worlds[index]
    p.set('worlds', worlds)


# }}}


def find_tests() -> TestSuite:  # {{{
    import tempfile
    import unittest
    from unittest.mock import patch

    from calibre.ai.cyoa import PlayerCharacter, start_game
    from calibre.ai.prefs import pref_for_provider

    def make_world() -> GeneratedWorld:
        return GeneratedWorld(
            title='Mist City',
            world_description='A city lost in perpetual mist.',
            characters=(PlayerCharacter('Ada', 'a stubborn engineer', 'She built the mist engines.'),),
            win_condition='Escape the city.',
        )

    def temp_prefs(tdir: str) -> JSONConfig:
        ans = JSONConfig('cyoa-test-prefs', base_path=tdir)
        ans.defaults['ai'] = {}
        ans.defaults['image_skipped'] = False
        ans.defaults['worlds'] = []
        ans.defaults['current_game'] = ''
        return ans

    class TestCYOAData(unittest.TestCase):
        ae = unittest.TestCase.assertEqual

        def test_cyoa_ai_settings_split(self) -> None:
            with tempfile.TemporaryDirectory() as tdir:
                p = temp_prefs(tdir)
                saved_keys: dict[str, dict[str, Any]] = {}

                def fake_update(name: str, pref_map: dict[str, Any]) -> None:
                    saved_keys.setdefault(name, {}).update(pref_map)

                with (
                    patch('calibre.gui2.cyoa.data.prefs', return_value=p),
                    patch('calibre.gui2.cyoa.data.update_prefs_for_provider', side_effect=fake_update),
                ):
                    save_ai_settings('text', 'Prov', {'api_key': 'sekrit', 'model': 'm', 'reasoning_strategy': 'high'})
                    self.ae(saved_keys, {'Prov': {'api_key': 'sekrit'}}, 'the API key must go to the common AI prefs')
                    self.ae(ai_settings('text'), {'provider': 'Prov', 'settings': {'model': 'm', 'reasoning_strategy': 'high'}})
                    self.ae(configured_provider_name('text'), 'Prov')
                    save_ai_settings('image', 'Local', {'text_model': 'x'})  # provider without an API key, e.g. Ollama
                    self.ae(saved_keys, {'Prov': {'api_key': 'sekrit'}})
                    self.ae(prefs_overlay(), {'Prov': {'model': 'm', 'reasoning_strategy': 'high'}, 'Local': {'text_model': 'x'}})
                    with cyoa_ai_settings():
                        self.ae(pref_for_provider('Prov', 'model'), 'm')
                        self.ae(pref_for_provider('Prov', 'reasoning_strategy'), 'high')

        def test_cyoa_game_storage(self) -> None:
            with tempfile.TemporaryDirectory() as tdir:
                p = temp_prefs(tdir)
                with patch('calibre.gui2.cyoa.data.prefs', return_value=p):
                    world = make_world()
                    state = start_game('brief', world, world.characters[0])
                    gid = new_game_id(tdir)
                    save_game(gid, state, {0: {'mime': 'image/png', 'data': 'abcd'}}, base=tdir)
                    loaded, images = load_game(gid, base=tdir)
                    self.ae(state, loaded)
                    self.ae(images, {0: {'mime': 'image/png', 'data': 'abcd'}})
                    self.ae(list_games(base=tdir), [(gid, 'Mist City')])
                    self.ae(current_game_id(), '')
                    set_current_game(gid)
                    self.ae(current_game_id(), gid)
                    with open(game_file(gid, tdir), 'rb') as f:
                        raw = json.load(f)
                    raw['version'] += 1
                    with open(game_file(gid, tdir), 'wb') as f:
                        f.write(json.dumps(raw).encode('utf-8'))
                    self.assertRaises(ValueError, load_game, gid, base=tdir)
                    delete_game(gid, base=tdir)
                    self.assertFalse(os.path.exists(game_dir(gid, tdir)))
                    self.ae(current_game_id(), '', 'deleting the current game must clear the current game pointer')
                    self.ae(list_games(base=tdir), [])

        def test_cyoa_saved_worlds(self) -> None:
            with tempfile.TemporaryDirectory() as tdir:
                p = temp_prefs(tdir)
                with patch('calibre.gui2.cyoa.data.prefs', return_value=p):
                    world = make_world()
                    add_saved_world('a brief', world)
                    add_saved_world('another brief', world)
                    entries = saved_worlds()
                    self.ae(len(entries), 1, 'adding an identical world twice must not create a duplicate')
                    self.ae(entries[0]['brief'], 'a brief')
                    self.ae(world_from_saved(entries[0]), world)
                    remove_saved_world(0)
                    self.ae(saved_worlds(), [])

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestCYOAData)


# }}}
