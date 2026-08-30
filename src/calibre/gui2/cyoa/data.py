#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Storage for the "Create Your Own Adventure" game GUI. Preferences,
# including the AI configuration and the list of user created worlds, are
# stored in cyoa/prefs.json in the calibre config directory. Games are
# stored one per sub folder, each as a game.json file containing all game
# data with pictures of each scene stored alongside it as turn1.webp,
# turn2.webp, etc. The game currently being played is auto-saved into a
# folder of the cyoa folder named by a random id, while games explicitly
# saved by the player go into folders of cyoa/saves named after the game
# title. API keys are NOT stored here, they live in the common AI
# preferences; all other AI provider settings used for the game are scoped
# to these preferences via override_prefs_for_providers(). This module must
# not import Qt so that it can be used and tested headless.

import json
import os
import re
import shutil
from collections.abc import Sequence
from contextlib import AbstractContextManager, suppress
from functools import lru_cache
from time import time
from typing import TYPE_CHECKING, Any, Literal, NamedTuple

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
    ans.defaults['game_splitter_state'] = None
    return ans


def save_game_splitter_state(raw: bytes) -> None:
    # The position of the splitter between the story and scene panels of the
    # game widget, remembered across sessions.
    prefs().set('game_splitter_state', bytearray(raw))


def game_splitter_state() -> bytes:
    return bytes(prefs()['game_splitter_state'] or b'')


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


def images_enabled() -> bool:
    # Images are generated only when the user has configured an image AI and
    # not skipped image generation on the welcome screen.
    return not image_skipped() and is_ready('image')


# }}}


# Saved games {{{


class SceneImage(NamedTuple):
    # An AI generated picture of the scene of one turn, with the cost of
    # generating it, stored on disk as turn<N>.webp next to game.json.
    data: bytes  # WebP encoded image data
    cost: float = 0
    currency: str = ''
    provider: str = ''
    model: str = ''


class SavedGame(NamedTuple):
    game_id: str
    title: str
    updated: float = 0
    num_turns: int = 0


def game_dir(game_id: str, base: str = '') -> str:
    return os.path.join(base or cyoa_dir(), game_id)


def game_file(game_id: str, base: str = '') -> str:
    return os.path.join(game_dir(game_id, base), GAME_FILE_NAME)


def new_game_id(base: str = '') -> str:
    while True:
        ans = uuid4()
        if not os.path.exists(game_dir(ans, base)):
            return ans


def saves_dir(base: str = '') -> str:
    # Games explicitly saved by the player go here, in folders named after
    # the game title, see save_name_for_title().
    return os.path.join(base or cyoa_dir(), 'saves')


def save_name_for_title(title: str) -> str:
    from calibre import sanitize_file_name

    return sanitize_file_name(title) or 'Adventure'


def image_file_name(turn_number: int) -> str:
    return f'turn{turn_number}.webp'


def save_game(game_id: str, state: GameState, images: dict[int, SceneImage] | None = None, base: str = '') -> None:
    # images maps one based turn number to the picture of that turn's scene.
    # Pictures of turns not in images are deleted, so always pass all of them.
    gf = game_file(game_id, base)
    created = time()
    try:
        with open(gf, 'rb') as f:
            created = json.load(f).get('created') or created
    except Exception:
        pass
    images = images or {}
    data = {
        'version': GAME_FILE_VERSION,
        'title': state.world.title,
        'created': created,
        'updated': time(),
        'game': json.loads(serialize_game(state)),
        'images': {
            str(k): {'file': image_file_name(k), 'cost': v.cost, 'currency': v.currency, 'provider': v.provider, 'model': v.model} for k, v in images.items()
        },
    }
    commit_data(gf, json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
    gdir = game_dir(game_id, base)
    for k, v in images.items():
        commit_data(os.path.join(gdir, image_file_name(k)), v.data)
    current_files = {image_file_name(k) for k in images}
    for x in os.listdir(gdir):
        if re.fullmatch(r'turn\d+\.webp', x) and x not in current_files:
            with suppress(OSError):
                os.remove(os.path.join(gdir, x))


def load_game(game_id: str, base: str = '') -> tuple[GameState, dict[int, SceneImage]]:
    with open(game_file(game_id, base), 'rb') as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get('version') != GAME_FILE_VERSION:
        raise ValueError(f'Not a valid CYOA game file: {game_file(game_id, base)}')
    state = deserialize_game(json.dumps(data['game']))
    images: dict[int, SceneImage] = {}
    gdir = game_dir(game_id, base)
    for k, v in (data.get('images') or {}).items():
        try:
            with open(os.path.join(gdir, v['file']), 'rb') as f:
                raw = f.read()
        except OSError:
            continue
        images[int(k)] = SceneImage(
            data=raw, cost=v.get('cost') or 0, currency=v.get('currency') or '', provider=v.get('provider') or '', model=v.get('model') or ''
        )
    return state, images


def list_games(base: str = '') -> list[SavedGame]:
    # All saved games, most recently played first.
    entries: list[SavedGame] = []
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
            entries.append(
                SavedGame(
                    game_id=x,
                    title=data.get('title') or x,
                    updated=data.get('updated') or 0,
                    num_turns=len((data.get('game') or {}).get('turns') or ()),
                )
            )
    entries.sort(key=lambda e: e.updated, reverse=True)
    return entries


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


def saved_world_index_with_title(title: str) -> int:
    # The index of the saved world with the specified title (case insensitive), or -1
    q = title.strip().casefold()
    for i, e in enumerate(saved_worlds()):
        t = str((e.get('world') or {}).get('title') or '')
        if t.strip().casefold() == q:
            return i
    return -1


def add_saved_world(brief: str, world: GeneratedWorld, art_style: str = '', portraits: Sequence[dict[str, str] | None] = ()) -> None:
    # Save the world, replacing any previously saved world with the same
    # title. portraits is a list of character portraits, aligned with
    # world.characters, each either None or {'mime': mime type, 'data':
    # base64 encoded image data}.
    jw = as_jsonable(world, spec_for_class(GeneratedWorld))
    pl = list(portraits)
    p = prefs()
    worlds = p['worlds']
    if any(e.get('world') == jw and (e.get('art_style') or '') == art_style and (e.get('portraits') or []) == pl for e in worlds):
        return
    entry: dict[str, Any] = {'brief': brief, 'created': time(), 'world': jw, 'art_style': art_style, 'portraits': pl}
    idx = saved_world_index_with_title(world.title)
    if idx > -1:
        entry['created'] = worlds[idx].get('created') or entry['created']
        worlds[idx] = entry
    else:
        worlds.append(entry)
    p.set('worlds', worlds)


def world_from_saved(entry: dict[str, Any]) -> GeneratedWorld:
    ans = instantiate(entry['world'], spec_for_class(GeneratedWorld), GeneratedWorld.__name__)
    assert isinstance(ans, GeneratedWorld)
    return ans


def art_style_from_saved(entry: dict[str, Any]) -> str:
    return str(entry.get('art_style') or '')


def portraits_from_saved(entry: dict[str, Any], num_characters: int) -> list[dict[str, str] | None]:
    # The saved character portraits, validated and clamped/padded to one
    # entry per character.
    ans: list[dict[str, str] | None] = []
    for x in entry.get('portraits') or ():
        ans.append(x if isinstance(x, dict) and x.get('mime') and x.get('data') else None)
    del ans[num_characters:]
    ans.extend([None] * (num_characters - len(ans)))
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
                    img1, img2 = SceneImage(data=b'webp1', cost=0.5, currency='USD', provider='prov', model='mod'), SceneImage(data=b'webp2')
                    save_game(gid, state, {1: img1, 2: img2}, base=tdir)
                    self.assertTrue(os.path.exists(os.path.join(game_dir(gid, tdir), 'turn1.webp')))
                    loaded, images = load_game(gid, base=tdir)
                    self.ae(state, loaded)
                    self.ae(images, {1: img1, 2: img2})
                    self.ae(list_games(base=tdir), [SavedGame(gid, 'Mist City', list_games(base=tdir)[0].updated, 0)])
                    save_game(gid, state, {1: img1}, base=tdir)
                    self.assertFalse(os.path.exists(os.path.join(game_dir(gid, tdir), 'turn2.webp')), 'images of turns not passed to save_game must be deleted')
                    self.ae(load_game(gid, base=tdir)[1], {1: img1})
                    self.ae(current_game_id(), '')
                    set_current_game(gid)
                    self.ae(current_game_id(), gid)
                    with open(game_file(gid, tdir), 'rb') as f:
                        raw = json.load(f)
                    raw['version'] = GAME_FILE_VERSION + 1
                    with open(game_file(gid, tdir), 'wb') as f:
                        f.write(json.dumps(raw).encode('utf-8'))
                    self.assertRaises(ValueError, load_game, gid, base=tdir)
                    delete_game(gid, base=tdir)
                    self.assertFalse(os.path.exists(game_dir(gid, tdir)))
                    self.ae(current_game_id(), '', 'deleting the current game must clear the current game pointer')
                    self.ae(list_games(base=tdir), [])
                    self.ae(save_name_for_title(' Mist / City? '), 'Mist _ City_')
                    self.ae(save_name_for_title('  '), 'Adventure')
                    self.ae(saves_dir(tdir), os.path.join(tdir, 'saves'))

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
                    self.ae(saved_world_index_with_title(' MIST city '), 0)
                    self.ae(saved_world_index_with_title('no such world'), -1)
                    created = entries[0]['created']
                    world2 = world._replace(win_condition='Rule the city.')
                    add_saved_world('changed brief', world2)
                    entries = saved_worlds()
                    self.ae(len(entries), 1, 'a world with the same title must replace the existing saved world')
                    self.ae(entries[0]['brief'], 'changed brief')
                    self.ae(entries[0]['created'], created, 'replacing a world must preserve its creation time')
                    self.ae(world_from_saved(entries[0]), world2)
                    other = world._replace(title='Sun City')
                    add_saved_world('sunny brief', other)
                    self.ae(len(saved_worlds()), 2, 'a world with a different title must not replace existing worlds')
                    entry = saved_worlds()[saved_world_index_with_title('Sun City')]
                    self.ae(art_style_from_saved(entry), '')
                    self.ae(portraits_from_saved(entry, 1), [None])
                    portrait = {'mime': 'image/webp', 'data': 'abcd'}
                    add_saved_world('sunny brief', other, 'anime', [portrait])
                    self.ae(len(saved_worlds()), 2, 'adding portraits must update the existing saved world, not create a new one')
                    entry = saved_worlds()[saved_world_index_with_title('Sun City')]
                    self.ae(art_style_from_saved(entry), 'anime')
                    self.ae(portraits_from_saved(entry, 1), [portrait])
                    self.ae(portraits_from_saved(entry, 2), [portrait, None], 'missing portraits must be padded with None')
                    self.ae(portraits_from_saved(entry, 0), [], 'extra portraits must be discarded')
                    created = entry['created']
                    add_saved_world('sunny brief', other, 'anime', [portrait])
                    entry = saved_worlds()[saved_world_index_with_title('Sun City')]
                    self.ae(entry['created'], created, 'saving an identical world must not change it')
                    remove_saved_world(1)
                    remove_saved_world(0)
                    self.ae(saved_worlds(), [])

        def test_cyoa_premade_world_art_styles(self) -> None:
            from calibre.ai.cyoa import art_style_for_key
            from calibre.gui2.cyoa.world import PREMADE_WORLDS, recommended_art_style

            for pw in PREMADE_WORLDS:
                self.ae(art_style_for_key(pw.art_style).key, pw.art_style, f'the recommended art style for {pw.title!r} must be a valid art style key')
                self.ae(recommended_art_style(pw.brief), pw.art_style)
            self.ae(recommended_art_style('not a pre-made brief'), '', 'a custom brief must not have a recommended art style')

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestCYOAData)


# }}}
