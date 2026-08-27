#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Backend for an AI driven "Create Your Own Adventure" game. The game has two
# phases: world generation, where a brief description from the player is
# expanded by the AI into a full world with playable characters and a win
# condition, and the turn-by-turn game itself. Every turn the AI narrates what
# happens, suggests three quick actions, describes the current scene for an
# image generation AI, updates a running summary of the story and reports
# whether a new chapter starts or the win condition is met. The AI is sent the
# story summary and the transcript of only the current chapter, so the context
# stays bounded no matter how long the game runs. A full log of everything
# sent to and received from the AI is kept, turn by turn, so games can be
# rewound and saved/loaded.

import json
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple, Protocol

from calibre.ai import AICapabilities, StructuredOutputResult
from calibre.ai.structured import Doc, Kind, TypeSpec, instantiate, spec_for_class
from calibre.utils.localization import _

if TYPE_CHECKING:
    from unittest.suite import TestSuite
else:
    TestSuite = object

GAME_SERIALIZATION_VERSION = 1


class AIProvider(Protocol):
    # The subset of calibre.customize.AIProviderPlugin used by this module,
    # expressed as a Protocol so that tests and alternative implementations
    # can be substituted for actual plugins.
    def generate_structured_output(self, prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult: ...


# Schema classes describing what the AI must generate {{{


class PlayerCharacter(NamedTuple):
    doc = Doc('A character the player can choose to play as')
    name: str
    description: Annotated[str, 'Short third person description of the character']
    backstory: Annotated[str, "The character's backstory and motivations"]


class GeneratedWorld(NamedTuple):
    doc = Doc('A detailed game world generated from a brief description')
    title: Annotated[str, 'A short, evocative title for this adventure']
    world_description: Annotated[str, 'Detailed description of the world: its geography, factions, atmosphere, central conflict and stakes']
    characters: Annotated[
        tuple[PlayerCharacter, ...],
        'Between three and five distinct characters or character variants the player can choose to play as, with physical descriptions and brief back stories',
    ]
    win_condition: Annotated[str, 'The single concrete goal the player must achieve to win the adventure']


class CharacterState(NamedTuple):
    doc = Doc('The current state of a significant character in the story')
    name: str
    description: Annotated[str, 'Who this character is and their current status']
    relationships: Annotated[str, 'Their relationships with the player and the other characters']


class StorySummary(NamedTuple):
    doc = Doc('A summary of the story so far, serving as memory for continuing it')
    world: Annotated[str, 'Description of the world and its current state']
    major_events: Annotated[tuple[str, ...], 'The major events of the story so far, in chronological order']
    characters: Annotated[tuple[CharacterState, ...], 'All significant characters in the story and their relationships']
    current_situation: Annotated[str, 'Where the player currently is and what is happening']
    upcoming_events: Annotated[tuple[str, ...], 'Foreshadowed or planned future events and unresolved plot threads']


class StoryTurn(NamedTuple):
    doc = Doc('One turn of the adventure')
    narrative: Annotated[str, 'The narrative text describing what happens in this turn']
    quick_actions: Annotated[tuple[str, ...], 'Exactly three short, distinct actions the player could plausibly take next']
    scene_description: Annotated[
        str,
        'A self-contained visual description of the current scene,'
        ' suitable as a prompt for an image generation AI, that does not rely on knowledge of the story',
    ]
    updated_summary: Annotated[StorySummary, 'The story summary updated to include the events of this turn']
    starts_new_chapter: Annotated[bool, 'True only when this turn begins a major new phase of the story, suitable as the start of a new chapter']
    chapter_title: Annotated[str | None, 'A title for the new chapter when starts_new_chapter is true, null otherwise']
    win_condition_met: Annotated[bool, 'True once the player has achieved the win condition']


# }}}


# Game state and log of AI exchanges {{{


class TurnRecord(NamedTuple):
    # The full log of a single exchange with the AI, sufficient to replay or
    # rewind the game and to audit exactly what was sent and received.
    player_input: str  # what the player typed or chose, empty for the opening turn
    instructions: str  # the system prompt sent to the AI
    prompt: str  # the full user prompt sent to the AI
    raw_response: str  # the raw JSON text returned by the AI
    turn: StoryTurn  # the parsed response
    chapter: int  # zero based chapter number this turn belongs to
    cost: float = 0
    currency: str = ''
    provider: str = ''
    model: str = ''


def initial_summary(world: GeneratedWorld, character: PlayerCharacter) -> StorySummary:
    return StorySummary(
        world=world.world_description,
        major_events=(),
        characters=(CharacterState(name=character.name, description=character.description, relationships=''),),
        current_situation='The adventure has not yet begun.',
        upcoming_events=(),
    )


@dataclass
class GameState:
    # The complete state of a game. Everything except the turn log is
    # derived, which keeps rewinding trivial: dropping turn records restores
    # the summary, chapter position and victory status automatically.
    brief: str  # the player's original brief description of the world
    world: GeneratedWorld
    character: PlayerCharacter  # the character the player chose
    turns: list[TurnRecord] = field(default_factory=list)

    @property
    def current_chapter(self) -> int:
        return self.turns[-1].chapter if self.turns else 0

    @property
    def current_chapter_turns(self) -> tuple[TurnRecord, ...]:
        c = self.current_chapter
        return tuple(t for t in self.turns if t.chapter == c)

    @property
    def current_summary(self) -> StorySummary:
        return self.turns[-1].turn.updated_summary if self.turns else initial_summary(self.world, self.character)

    @property
    def victory_achieved(self) -> bool:
        # Latched: once the win condition is met it stays met, even if the
        # player keeps playing and the AI stops reporting it.
        return any(t.turn.win_condition_met for t in self.turns)

    @property
    def chapter_titles(self) -> tuple[str, ...]:
        titles: list[str] = []
        for t in self.turns:
            if t.chapter >= len(titles):
                titles.append(t.turn.chapter_title or _('Chapter {}').format(len(titles) + 1))
        return tuple(titles)


def start_game(brief: str, world: GeneratedWorld, character: PlayerCharacter) -> GameState:
    return GameState(brief=brief, world=world, character=character)


def rewind(state: GameState, num_of_turns: int = 1) -> None:
    # Undo the last num_of_turns turns. The summary, current chapter and
    # victory status are all derived from the remaining turn records.
    if not 0 < num_of_turns <= len(state.turns):
        raise ValueError(f'Cannot rewind {num_of_turns} turns in a game with {len(state.turns)} turns')
    del state.turns[-num_of_turns:]


# }}}


# Serialization for saving/loading games {{{


def as_jsonable(value: Any, spec: TypeSpec) -> Any:  # noqa: ANN401
    # Convert an instance of a class with annotated fields into JSON
    # serializable form, the inverse of calibre.ai.structured.instantiate().
    if value is None:
        return None
    match spec.kind:
        case Kind.object:
            return {f.name: as_jsonable(getattr(value, f.name), f.spec) for f in spec.fields}
        case Kind.array:
            assert spec.items is not None
            return [as_jsonable(v, spec.items) for v in value]
        case Kind.enumeration:
            return value.value if isinstance(value, Enum) else value
    return value


def serialize_game(state: GameState) -> str:
    return json.dumps({'version': GAME_SERIALIZATION_VERSION, 'game': as_jsonable(state, spec_for_class(GameState))}, ensure_ascii=False)


def deserialize_game(raw: str) -> GameState:
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get('version') != GAME_SERIALIZATION_VERSION:
        raise ValueError('Not a valid serialized CYOA game')
    ans = instantiate(data['game'], spec_for_class(GameState), GameState.__name__)
    assert isinstance(ans, GameState)
    return ans


# }}}


# Prompt construction {{{
# Deliberately not translated as AI models work best with English instructions.

WORLD_GENERATION_INSTRUCTIONS = (
    'You are a creative designer of interactive "choose your own adventure" fiction.'
    ' Given a brief description of a world, flesh it out into a rich, internally consistent game world,'
    ' inventing concrete details: places, factions, conflicts and atmosphere.'
    ' Create between three and five distinct playable characters, each with a different perspective'
    " on the world's central conflict, and a single concrete, achievable win condition for the adventure."
    ' Include physical descriptions and a little back story for the characters.'
    ' If the world description mentions a central character, then have the playable characters all be'
    ' variants of that person with different descriptions and back stories.'
    ' Format all descriptive text fields (world_description, character descriptions, backstories, win_condition)'
    ' using Markdown: use **bold** for emphasis, *italics* for atmosphere, and newlines to separate paragraphs.'
    ' Do not use headers or bullet lists in these fields.'
)


def world_generation_prompt(brief: str) -> str:
    return f'Create the world for an adventure game based on this description:\n\n{brief}'


def summary_as_json(summary: StorySummary) -> str:
    return json.dumps(as_jsonable(summary, spec_for_class(StorySummary)), ensure_ascii=False, indent=2)


def turn_instructions(state: GameState) -> str:
    w, c = state.world, state.character
    parts = [
        (
            'You are the game master of an interactive "choose your own adventure" game.'
            " Continue the story based on the story summary, the transcript of the current chapter and the player's latest action."
            ' Format all narrative and descriptive text using Markdown:'
            ' use **bold** for emphasis and important moments, *italics* for atmosphere and inner thoughts,'
            ' and blank lines to separate paragraphs. Do not use headers or bullet lists in narrative text.'
        ),
        'Rules for the fields of your response:',
        (
            '- narrative: describe what happens next in second person present tense, addressing the player as "you".'
            ' Stop at a point where the player must decide what to do next.'
            ' Use Markdown formatting as instructed above.'
        ),
        '- quick_actions: exactly three short, distinct actions the player could plausibly take next.',
        (
            '- scene_description: a self-contained visual description of the current scene for an image generation AI.'
            ' It must make sense without any knowledge of the story.'
        ),
        (
            "- updated_summary: the story summary updated with this turn's events."
            ' Preserve all information that is still relevant, including characters, relationships and unresolved plot threads, and keep it concise.'
        ),
        '- starts_new_chapter: true only when this turn begins a major new phase of the story, with chapter_title naming the new chapter.',
        '- win_condition_met: true once the player has achieved the win condition.',
        '',
        f'The world, titled {w.title!r}, is described as:',
        w.world_description,
        '',
        f'The player plays {c.name}: {c.description}',
        c.backstory,
        '',
        f'The win condition for the player is: {w.win_condition}',
    ]
    if state.victory_achieved:
        parts.append(
            'The player has already achieved the win condition and has chosen to keep playing.'
            ' Ignore the win condition from now on and continue the story wherever the player takes it.'
        )
    return '\n'.join(parts)


def turn_prompt(state: GameState, player_input: str = '') -> str:
    parts = ['The summary of the story so far, as JSON:', summary_as_json(state.current_summary), '']
    if transcript := state.current_chapter_turns:
        parts.append('The transcript of the current chapter:')
        for t in transcript:
            if t.player_input:
                parts.append(f'Player: {t.player_input}')
            parts.append(f'Narrator: {t.turn.narrative}')
        parts.append('')
    if state.turns:
        parts.append(f'The player responds: {player_input}' if player_input else 'The player says nothing.')
        parts.append('Generate the next turn of the story.')
    else:
        if player_input:
            parts.append(f'The player asks for the story to begin as follows: {player_input}')
        parts.append('Begin the adventure with an opening scene that introduces the player character and their situation.')
    return '\n'.join(parts)


# }}}


# The AI driven game phases {{{


def default_provider() -> AIProvider | None:
    from calibre.ai.prefs import plugin_for_purpose

    return plugin_for_purpose(AICapabilities.text_to_text)


def no_provider_error() -> StructuredOutputResult:
    msg = 'No AI provider plugin is configured for text generation'
    return StructuredOutputResult(exception=ValueError(msg), error_details=msg)


def generate_world(brief: str, plugin: AIProvider | None = None, use_model: str = '') -> StructuredOutputResult:
    # The world generation phase: expand the player's brief description into
    # a GeneratedWorld, available as the data field of the returned result.
    # Errors are reported via the exception field, not raised.
    plugin = plugin or default_provider()
    if plugin is None:
        return no_provider_error()
    return plugin.generate_structured_output(world_generation_prompt(brief), GeneratedWorld, WORLD_GENERATION_INSTRUCTIONS, use_model)


def next_turn(state: GameState, player_input: str = '', plugin: AIProvider | None = None, use_model: str = '') -> StructuredOutputResult:
    # Play one turn: send the AI the story summary, the transcript of the
    # current chapter and the player's input, returning a result whose data
    # field is a StoryTurn. On success the turn is appended to the game log,
    # starting a new chapter when the AI indicates one. On error the state is
    # left unmodified and the error is reported via the exception field of
    # the result, not raised. For the opening turn of the game player_input
    # may be empty.
    plugin = plugin or default_provider()
    if plugin is None:
        return no_provider_error()
    instructions = turn_instructions(state)
    prompt = turn_prompt(state, player_input)
    res = plugin.generate_structured_output(prompt, StoryTurn, instructions, use_model)
    turn = res.data
    if res.exception is None and isinstance(turn, StoryTurn):
        chapter = state.current_chapter
        if state.turns and turn.starts_new_chapter:
            chapter += 1
        state.turns.append(
            TurnRecord(
                player_input=player_input,
                instructions=instructions,
                prompt=prompt,
                raw_response=res.raw,
                turn=turn,
                chapter=chapter,
                cost=res.cost,
                currency=res.currency,
                provider=res.provider,
                model=res.model,
            )
        )
    return res


# }}}


def develop(use_model: str = '') -> None:  # {{{
    # A minimal terminal driver to play the game against a real AI provider,
    # for development and debugging.
    # calibre-debug -c 'from calibre.ai.cyoa import *; develop()'
    def unwrap(res: StructuredOutputResult) -> Any:  # noqa: ANN401
        if res.exception is not None:
            raise SystemExit(str(res.exception) + (': ' + res.error_details if res.error_details else ''))
        return res.data

    plugin = default_provider()
    if plugin is None:
        raise SystemExit('No AI provider plugin is configured for text generation')
    brief = input('Describe the world for your adventure: ')
    world = unwrap(generate_world(brief, plugin, use_model))
    assert isinstance(world, GeneratedWorld)
    print(f'\n=== {world.title} ===\n\n{world.world_description}\n\nWin condition: {world.win_condition}\n')
    for i, c in enumerate(world.characters):
        print(f'{i + 1}) {c.name}: {c.description}')
        bs = textwrap.indent(textwrap.fill(c.backstory), '\t')
        print(bs)
        print()
    num = input(f'\nChoose your character [1-{len(world.characters)}]: ')
    state = start_game(brief, world, world.characters[int(num) - 1])
    player_input, victory_reported = '', False
    while True:
        chapter_before = state.current_chapter if state.turns else -1
        turn = unwrap(next_turn(state, player_input, plugin, use_model))
        assert isinstance(turn, StoryTurn)
        if state.current_chapter != chapter_before:
            print(f'\n--- {state.chapter_titles[-1]} ---')
        print(f'\n{turn.narrative}\n')
        print(f'[Scene: {turn.scene_description}]\n')
        if state.victory_achieved and not victory_reported:
            victory_reported = True
            print('*** You have achieved the win condition! Keep playing if you like. ***\n')
        for i, action in enumerate(turn.quick_actions):
            print(f'{i + 1}) {action}')
        player_input = input('\nWhat do you do? (number for a quick action, empty to quit): ').strip()
        if not player_input:
            break
        if player_input.isdigit() and 1 <= int(player_input) <= len(turn.quick_actions):
            player_input = turn.quick_actions[int(player_input) - 1]


# }}}


def find_tests() -> TestSuite:  # {{{
    import unittest

    class FakePlugin:
        def __init__(self, results: list[StructuredOutputResult]) -> None:
            self.results = list(results)
            self.calls: list[tuple[str, type, str, str]] = []

        def generate_structured_output(self, prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
            self.calls.append((prompt, schema, instructions, use_model))
            return self.results.pop(0)

    def make_world() -> GeneratedWorld:
        return GeneratedWorld(
            title='Mist City',
            world_description='A city lost in perpetual mist.',
            characters=(
                PlayerCharacter('Ada', 'a stubborn engineer', 'She built the mist engines.'),
                PlayerCharacter('Brin', 'a nimble thief', 'He stole the last map.'),
            ),
            win_condition='Escape the city before the mist swallows it.',
        )

    def make_summary(*events: str) -> StorySummary:
        return StorySummary(
            world='A city lost in mist.',
            major_events=events,
            characters=(CharacterState('Ada', 'the player', 'alone so far'),),
            current_situation='In the mist.',
            upcoming_events=('The mist thickens.',),
        )

    def make_turn(
        narrative: str,
        *events: str,
        starts_new_chapter: bool = False,
        chapter_title: str | None = None,
        win: bool = False,
    ) -> StoryTurn:
        return StoryTurn(
            narrative=narrative,
            quick_actions=('Look around', 'Call out', 'Run'),
            scene_description=f'A picture of: {narrative}',
            updated_summary=make_summary(*events),
            starts_new_chapter=starts_new_chapter,
            chapter_title=chapter_title,
            win_condition_met=win,
        )

    def ok(data: GeneratedWorld | StoryTurn) -> StructuredOutputResult:
        return StructuredOutputResult(data=data, raw='{"raw": "json"}', cost=0.25, currency='USD', provider='prov', model='mod')

    class TestCYOA(unittest.TestCase):
        ae = unittest.TestCase.assertEqual

        def test_ai_cyoa_world_generation(self) -> None:
            world = make_world()
            fake = FakePlugin([ok(world)])
            res = generate_world('a foggy city', fake)
            self.assertIs(res.data, world)
            prompt, schema, instructions, use_model = fake.calls[0]
            self.assertIn('a foggy city', prompt)
            self.assertIs(schema, GeneratedWorld)
            self.assertIn('win condition', instructions)
            res = generate_world('anything', FakePlugin([StructuredOutputResult(exception=ValueError('boom'))]))
            self.assertIsInstance(res.exception, ValueError)

        def test_ai_cyoa_turn_flow_and_chapters(self) -> None:
            state = start_game('a foggy city', make_world(), make_world().characters[0])
            self.ae(state.current_summary.world, state.world.world_description)
            self.ae(state.current_chapter, 0)
            fake = FakePlugin([
                ok(make_turn('You awaken in the mist.', 'awoke')),
                ok(make_turn('Shapes loom around you.', 'awoke', 'saw shapes')),
                ok(make_turn('You descend into the tunnels.', 'awoke', 'saw shapes', 'descended', starts_new_chapter=True, chapter_title='The Descent')),
                ok(make_turn('The tunnels narrow.', 'awoke', 'saw shapes', 'descended', 'tunnels narrowed')),
            ])
            res = next_turn(state, '', fake)
            self.assertIsNone(res.exception)
            prompt, schema, instructions, _um = fake.calls[0]
            self.assertIs(schema, StoryTurn)
            self.assertIn('Begin the adventure', prompt)
            self.assertIn(state.world.world_description, instructions)
            self.assertIn(state.character.backstory, instructions)
            self.assertIn(state.world.win_condition, instructions)
            self.ae(len(state.turns), 1)
            self.ae(state.turns[0].chapter, 0)
            self.ae(state.turns[0].raw_response, '{"raw": "json"}')
            self.ae((state.turns[0].cost, state.turns[0].provider, state.turns[0].model), (0.25, 'prov', 'mod'))

            next_turn(state, 'look around', fake)
            prompt = fake.calls[1][0]
            self.assertIn('Narrator: You awaken in the mist.', prompt)
            self.assertIn('The player responds: look around', prompt)
            self.assertIn('awoke', prompt, 'the summary from the previous turn must be sent')
            self.assertNotIn('has not yet begun', prompt, 'the initial summary must have been replaced')

            next_turn(state, 'descend', fake)
            self.ae(state.current_chapter, 1)
            self.ae(state.chapter_titles, ('Chapter 1', 'The Descent'))

            next_turn(state, 'go deeper', fake)
            prompt = fake.calls[3][0]
            self.assertIn('You descend into the tunnels.', prompt, 'the transcript must contain the current chapter')
            self.assertNotIn('You awaken in the mist.', prompt, 'the transcript must not contain previous chapters')
            self.assertNotIn('Shapes loom around you.', prompt, 'the transcript must not contain previous chapters')
            self.ae(state.turns[3].chapter, 1)

            failing = FakePlugin([StructuredOutputResult(exception=ValueError('boom'), error_details='details')])
            res = next_turn(state, 'anything', failing)
            self.assertIsNotNone(res.exception)
            self.ae(len(state.turns), 4, 'a failed turn must not modify the game state')

        def test_ai_cyoa_win_condition(self) -> None:
            state = start_game('brief', make_world(), make_world().characters[1])
            fake = FakePlugin([
                ok(make_turn('You escape.', 'escaped', win=True)),
                ok(make_turn('You wander on.', 'escaped', 'wandered')),
            ])
            next_turn(state, '', fake)
            self.assertTrue(state.victory_achieved)
            next_turn(state, 'keep going', fake)
            self.assertIn('already achieved the win condition', fake.calls[1][2])
            self.assertTrue(state.victory_achieved, 'victory must stay latched even when later turns do not report it')
            self.assertNotIn('already achieved', fake.calls[0][2])

        def test_ai_cyoa_rewind(self) -> None:
            state = start_game('brief', make_world(), make_world().characters[0])
            fake = FakePlugin([
                ok(make_turn('One.', 'one')),
                ok(make_turn('Two.', 'one', 'two', win=True)),
                ok(make_turn('Three.', 'one', 'two', 'three', starts_new_chapter=True, chapter_title='Part II')),
            ])
            for x in ('', 'a', 'b'):
                next_turn(state, x, fake)
            self.ae(state.current_chapter, 1)
            rewind(state)
            self.ae(state.current_chapter, 0)
            self.ae(state.current_summary.major_events, ('one', 'two'))
            self.assertTrue(state.victory_achieved)
            rewind(state)
            self.assertFalse(state.victory_achieved)
            self.assertRaises(ValueError, rewind, state, 2)
            self.assertRaises(ValueError, rewind, state, 0)
            rewind(state)
            self.ae(state.current_summary, initial_summary(state.world, state.character))

        def test_ai_cyoa_serialization(self) -> None:
            state = start_game('a foggy city', make_world(), make_world().characters[0])
            fake = FakePlugin([
                ok(make_turn('You awaken.', 'awoke')),
                ok(make_turn('You escape.', 'awoke', 'escaped', starts_new_chapter=True, chapter_title='Freedom', win=True)),
            ])
            next_turn(state, '', fake)
            next_turn(state, 'run', fake)
            restored = deserialize_game(serialize_game(state))
            self.ae(state, restored)
            self.assertTrue(restored.victory_achieved)
            self.ae(restored.current_chapter, 1)
            self.assertRaises(ValueError, deserialize_game, json.dumps({'version': GAME_SERIALIZATION_VERSION + 1, 'game': {}}))
            self.assertRaises(ValueError, deserialize_game, json.dumps(['not', 'a', 'game']))

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestCYOA)


# }}}


if __name__ == '__main__':
    develop()
