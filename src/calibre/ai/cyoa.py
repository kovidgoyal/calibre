#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Backend for an AI driven "Create Your Own Adventure" game. The game has two
# phases: world generation, where a brief description from the player is
# expanded by the AI into a full world with playable characters, and the
# turn-by-turn game itself. Every turn the AI narrates what happens, suggests
# three quick actions, describes the current scene for an image generation AI,
# updates a running summary of the story and reports whether a new chapter
# starts. The AI is sent the
# story summary and the transcript of only the current chapter, so the context
# stays bounded no matter how long the game runs. A full log of everything
# sent to and received from the AI is kept, turn by turn, so games can be
# rewound and saved/loaded.

import json
import textwrap
from collections.abc import Iterable
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


class CharacterState(NamedTuple):
    doc = Doc('The current state of a significant character in the story')
    name: str
    description: Annotated[str, 'Who this character is and their current status']
    backstory: Annotated[str, "The character's brief backstory: who they are and how they came to be part of the story"]
    relationships: Annotated[str, 'Their relationships with the player and the other characters']


class StorySummary(NamedTuple):
    doc = Doc('A summary of the story so far, serving as memory for continuing it')
    world: Annotated[str, 'Description of the world and its current state']
    major_events: Annotated[tuple[str, ...], 'The major events of the story so far, in chronological order']
    characters: Annotated[
        tuple[CharacterState, ...], 'All significant named characters in the story, each with a description, brief backstory and their relationships'
    ]
    current_situation: Annotated[str, 'Where the player currently is and what is happening']
    upcoming_events: Annotated[tuple[str, ...], 'Foreshadowed or planned future events and unresolved plot threads']


class StoryTurn(NamedTuple):
    doc = Doc('One turn of the adventure')
    narrative: Annotated[
        str,
        'The next passage of the novel, continuing seamlessly from the prose written so far without repeating any of it,'
        ' written as immersive long form prose'
        ' with dialogue from the characters, their expressions and reactions, and scene descriptions where needed',
    ]
    quick_actions: Annotated[tuple[str, ...], 'Exactly three short, distinct actions the player could plausibly take next']
    scene_description: Annotated[
        str,
        'A self-contained visual description of the current scene,'
        ' suitable as a prompt for an image generation AI, that does not rely on knowledge of the story.'
        ' Describe the current physical state of the characters, their clothing and emotional state.',
    ]
    updated_summary: Annotated[StorySummary, 'The story summary updated to include the events of this turn']
    starts_new_chapter: Annotated[bool, 'True only when this turn begins a major new phase of the story, suitable as the start of a new chapter']
    chapter_title: Annotated[str | None, 'A title for the new chapter when starts_new_chapter is true, null otherwise']


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
        characters=(CharacterState(name=character.name, description=character.description, backstory=character.backstory, relationships=''),),
        current_situation='The adventure has not yet begun.',
        upcoming_events=(),
    )


@dataclass
class GameState:
    # The complete state of a game. Everything except the turn log is
    # derived, which keeps rewinding trivial: dropping turn records restores
    # the summary and chapter position automatically.
    brief: str  # the player's original brief description of the world
    world: GeneratedWorld
    character: PlayerCharacter  # the character the player chose
    turns: list[TurnRecord] = field(default_factory=list)
    # The key of the art style from ART_STYLES used for generated scene images.
    art_style: str = ''

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
    def chapter_titles(self) -> tuple[str, ...]:
        titles: list[str] = []
        for t in self.turns:
            if t.chapter >= len(titles):
                titles.append(t.turn.chapter_title or _('Chapter {}').format(len(titles) + 1))
        return tuple(titles)


def start_game(brief: str, world: GeneratedWorld, character: PlayerCharacter, art_style: str = '') -> GameState:
    return GameState(brief=brief, world=world, character=character, art_style=art_style)


def rewind(state: GameState, num_of_turns: int = 1) -> None:
    # Undo the last num_of_turns turns. The summary and current chapter are
    # derived from the remaining turn records.
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


# Art styles for generated images {{{


class ArtStyle(NamedTuple):
    key: str  # stable key used in settings and serialized data
    name: str  # human readable, translated name for display in the UI
    # What to add to image generation prompts for this style, deliberately
    # not translated as AI models work best with English instructions. Empty
    # for the default style, which leaves the choice to the AI.
    prompt: str


ART_STYLES: tuple[ArtStyle, ...] = (
    ArtStyle('default', _('Let the AI decide'), ''),
    ArtStyle('anime', _('Anime'), 'Render in a vibrant anime style: clean line art, cel shading, expressive features.'),
    ArtStyle('photorealistic', _('Photo realistic'), 'Render as a photorealistic photograph: natural lighting, shallow depth of field, fine detail.'),
    ArtStyle('digital-painting', _('Fantasy painting'), 'Render as an epic fantasy digital painting: rich colors, dramatic lighting, painterly brushwork.'),
    ArtStyle('comic', _('Comic book'), 'Render in a comic book style: bold ink outlines, flat colors, dynamic halftone shading.'),
    ArtStyle('watercolor', _('Watercolor'), 'Render as a delicate watercolor painting: soft washes of color, visible paper texture, loose expressive strokes.'),
    ArtStyle('pixel-art', _('Pixel art'), 'Render as detailed retro pixel art: limited color palette, crisp pixels, 16-bit video game aesthetic.'),
    ArtStyle('noir', _('Film noir'), 'Render in a film noir style: moody high contrast black and white, deep shadows, dramatic lighting.'),
)


def art_style_for_key(key: str) -> ArtStyle:
    for s in ART_STYLES:
        if s.key == key:
            return s
    return ART_STYLES[0]


def character_portrait_prompt(character: PlayerCharacter, style_key: str = '', world_description: str = '') -> str:
    parts = [f'A portrait of {character.name}, a character in an adventure story.', character.description]
    if world_description:
        parts.append(f'The world they inhabit: {world_description}')
    if style := art_style_for_key(style_key).prompt:
        parts.append(style)
    parts.append('Do not include any text in the image you generate.')
    return '\n'.join(parts)


def scene_image_prompt(scene_description: str, style_key: str = '') -> str:
    parts = [scene_description]
    if style := art_style_for_key(style_key).prompt:
        parts.append(style)
    parts.append('Do not include any text in the image you generate.')
    return '\n'.join(parts)


# }}}


# Prompt construction {{{
# Deliberately not translated as AI models work best with English instructions.

WORLD_GENERATION_INSTRUCTIONS = (
    'You are a creative designer of interactive "choose your own adventure" fiction.'
    ' Given a brief description of a world, flesh it out into a rich, internally consistent game world,'
    ' inventing concrete details: places, factions, conflicts and atmosphere.'
    ' Create between three and five distinct playable characters, each with a different perspective'
    " on the world's central conflict."
    ' Include physical descriptions and a little back story for the characters.'
    ' If the world description mentions a central character, then have the playable characters all be'
    ' variants of that person with different descriptions and back stories.'
    " Make each character's physical description detailed enough to be used, as a prompt for"
    ' an image generation AI: cover their appearance, age and distinguishing features without'
    ' relying on the rest of the world description. Describe the kind of clothes the character'
    ' typically wears but not an individual outfit, let the image generation AI choose that.'
    ' Format all descriptive text fields (world_description, character descriptions, backstories)'
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
            'You are a novelist writing an interactive novel in collaboration with your reader.'
            f" You write the novel's prose; the reader directs the actions of the protagonist, {c.name}, between passages."
            ' Write the next passage based on the story summary, the prose of the current chapter so far'
            " and the reader's latest direction."
            ' Each passage you write must continue seamlessly from exactly where the previous passage ended,'
            ' as if it were the next paragraphs of the same chapter.'
            ' Never repeat, summarize or rephrase prose that has already been written: the reader has just read it.'
            " Have the characters react to the protagonist's actions and the world in realistic and consistent ways."
            ' Write each passage as rich long form fiction of several substantial paragraphs, typically 400-800 words,'
            ' the way a skilled novelist would: let scenes breathe and unfold rather than summarizing events.'
            ' Bring the characters to life with spoken dialogue, quoting their words directly in their own distinct voices,'
            ' and show their expressions, gestures, body language and emotional reactions as they speak and act.'
            ' When the story enters a new location or the mood shifts, ground the scene with vivid sensory detail:'
            ' sights, sounds, smells and atmosphere.'
            ' Format all narrative and descriptive text using Markdown:'
            ' use **bold** for emphasis and important moments, *italics* for atmosphere and inner thoughts,'
            ' and blank lines to separate paragraphs. Do not use headers or bullet lists in narrative text.'
        ),
        'Rules for the fields of your response:',
        (
            '- narrative: the next passage of the novel, in second person present tense, addressing the reader as "you".'
            " It must pick up exactly where the chapter's prose left off, without repeating or recapping anything already written."
            ' Write it as compelling long form prose: multiple paragraphs weaving together action, dialogue from the characters,'
            ' their expressions and reactions, and scene description where needed, never a terse summary of events.'
            ' End at a point where the reader must decide what the protagonist does next.'
            ' Use Markdown formatting as instructed above.'
        ),
        '- quick_actions: exactly three short, distinct actions the reader could plausibly have the protagonist take next.',
        (
            '- scene_description: a self-contained visual description of the current scene for an image generation AI.'
            ' It must make sense without any knowledge of the story.'
        ),
        (
            "- updated_summary: the story summary updated with this passage's events."
            ' Preserve all information that is still relevant, including characters, relationships and unresolved plot threads, and keep it concise.'
            ' Whenever the narrative introduces a new named character, add an entry for them to the characters field of the summary'
            ' with a short description and a brief backstory.'
            " Keep existing characters' descriptions, backstories and relationships up to date as the story evolves."
        ),
        '- starts_new_chapter: true only when this passage begins a major new phase of the story, with chapter_title naming the new chapter.',
        '',
        f'The world, titled {w.title!r}, is described as:',
        w.world_description,
        '',
        f'The protagonist, {c.name}, is {c.description}',
        c.backstory,
    ]
    return '\n'.join(parts)


def turn_prompt(state: GameState, player_input: str = '', interesting_event: bool = False) -> str:
    parts = ['The summary of the story so far, as JSON:', summary_as_json(state.current_summary), '']
    if transcript := state.current_chapter_turns:
        parts.append('The prose of the current chapter so far, which the reader has already read:')
        parts.append('')
        for t in transcript:
            if t.player_input:
                parts.append(f'[The reader directs: {t.player_input}]')
                parts.append('')
            parts.append(t.turn.narrative)
            parts.append('')
    if state.turns:
        if interesting_event:
            parts.append(
                'The reader waits to see what happens next. Have something unexpected and interesting happen, taking the story in a surprising new direction.'
            )
        else:
            parts.append(f'The reader directs: {player_input}' if player_input else 'The reader offers no direction.')
        parts.append("Write the next passage of the novel, continuing seamlessly from where the chapter's prose ends.")
    else:
        if player_input:
            parts.append(f'The reader asks for the novel to begin as follows: {player_input}')
        parts.append('Begin the novel with an opening scene that introduces the protagonist and their situation.')
    return '\n'.join(parts)


# }}}


# The AI driven game phases {{{


def default_provider() -> AIProvider | None:
    from calibre.ai.prefs import plugin_for_purpose

    return plugin_for_purpose(AICapabilities.text_to_text)


def no_provider_error() -> StructuredOutputResult:
    msg = 'No AI provider plugin is configured for text generation'
    return StructuredOutputResult(exception=ValueError(msg), error_details=msg)


class InvalidAIResponse(ValueError):
    # Raised when the AI returns a response that matches the schema, so the
    # provider plugin reports no error, but that is not actually usable, for
    # example an empty passage of prose or too few quick actions.
    pass


def validation_error(res: StructuredOutputResult, e: InvalidAIResponse) -> StructuredOutputResult:
    # Report an unusable response the same way as an error from the provider,
    # keeping the raw response so the player can see what the AI actually said.
    return res._replace(data=None, exception=e, error_details=res.error_details or res.raw)


# The player chooses who to play as, so a world with only one character defeats
# the point of the phase. The AI is asked for three to five, but rejecting an
# otherwise usable world costs the player a full regeneration, so fewer are
# accepted as long as there is a choice.
MIN_PLAYER_CHARACTERS = 2


def validated_player_characters(characters: Iterable[PlayerCharacter]) -> tuple[PlayerCharacter, ...]:
    # Unlike the characters of a story summary there is no previous state to
    # repair these from, and every field is either shown to the player or used
    # to generate their portrait, so incomplete characters are discarded.
    ans: list[PlayerCharacter] = []
    seen: set[str] = set()
    for c in characters:
        name, description, backstory = c.name.strip(), c.description.strip(), c.backstory.strip()
        key = name.casefold()
        if not name or not description or not backstory or key in seen:
            continue
        seen.add(key)
        ans.append(PlayerCharacter(name=name, description=description, backstory=backstory))
    return tuple(ans)


def validated_world(world: GeneratedWorld) -> GeneratedWorld:
    # Nothing here can be repaired from previous state, as the world is the
    # start of the game, but generating it again loses the player nothing that
    # has been written, so an incomplete world is rejected rather than patched
    # up: the title and description are used for the rest of the game.
    title = world.title.strip()
    if not title:
        raise InvalidAIResponse('The AI returned a world with no title')
    description = world.world_description.strip()
    if not description:
        raise InvalidAIResponse('The AI returned a world with no description')
    characters = validated_player_characters(world.characters)
    if len(characters) < MIN_PLAYER_CHARACTERS:
        raise InvalidAIResponse(f'The AI returned {len(characters)} usable playable characters, at least {MIN_PLAYER_CHARACTERS} are needed')
    return GeneratedWorld(title=title, world_description=description, characters=characters)


def generate_world(brief: str, plugin: AIProvider | None = None, use_model: str = '') -> StructuredOutputResult:
    # The world generation phase: expand the player's brief description into
    # a GeneratedWorld, available as the data field of the returned result. The
    # response is validated and normalized by validated_world() before being
    # returned. Errors, including an unusable response, are reported via the
    # exception field, not raised.
    plugin = plugin or default_provider()
    if plugin is None:
        return no_provider_error()
    res = plugin.generate_structured_output(world_generation_prompt(brief), GeneratedWorld, WORLD_GENERATION_INSTRUCTIONS, use_model)
    if res.exception is not None:
        return res
    world = res.data
    try:
        if not isinstance(world, GeneratedWorld):
            raise InvalidAIResponse(f'The AI returned {type(world).__name__} instead of a world')
        world = validated_world(world)
    except InvalidAIResponse as e:
        return validation_error(res, e)
    return res._replace(data=world)


NUM_QUICK_ACTIONS = 3


def clean_text_list(items: Iterable[str]) -> tuple[str, ...]:
    # Strip whitespace and discard blank and duplicate entries, preserving order.
    ans: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = item.strip()
        if text and (key := text.casefold()) not in seen:
            seen.add(key)
            ans.append(text)
    return tuple(ans)


def validated_characters(characters: Iterable[CharacterState], previous: StorySummary) -> tuple[CharacterState, ...]:
    # Fill in fields the AI left blank from the entry for the same character in
    # the previous summary and discard entries that say nothing at all.
    known = {c.name.strip().casefold(): c for c in previous.characters if c.name.strip()}
    ans: list[CharacterState] = []
    seen: set[str] = set()
    for c in characters:
        name = c.name.strip()
        # A character without a name can neither be matched with a previous
        # entry nor be referred to by the AI or the player on later turns.
        if not name or (key := name.casefold()) in seen:
            continue
        seen.add(key)
        prev = known.get(key)
        description = c.description.strip() or (prev.description if prev else '')
        backstory = c.backstory.strip() or (prev.backstory if prev else '')
        if not description and not backstory:
            continue  # nothing is known about this character, a later turn will re-introduce them if they matter
        # An empty relationships field is legitimate for a character who has not yet met anyone.
        relationships = c.relationships.strip() or (prev.relationships if prev else '')
        ans.append(CharacterState(name=name, description=description, backstory=backstory, relationships=relationships))
    # Losing every character means losing the cast of the story, so keep the previous one rather than an empty summary.
    return tuple(ans) or previous.characters


def validated_summary(summary: StorySummary, previous: StorySummary) -> StorySummary:
    # The summary is the only memory the AI has of the story beyond the current
    # chapter, so blank fields are carried over from the previous summary
    # instead of being stored as is, which would silently lose the plot.
    world = summary.world.strip() or previous.world
    if not world:
        raise InvalidAIResponse('The AI returned a story summary with no description of the world')
    current_situation = summary.current_situation.strip() or previous.current_situation
    if not current_situation:
        raise InvalidAIResponse('The AI returned a story summary with no description of the current situation')
    characters = validated_characters(summary.characters, previous)
    if not characters:
        raise InvalidAIResponse('The AI returned a story summary with no characters')
    return StorySummary(
        world=world,
        major_events=clean_text_list(summary.major_events) or previous.major_events,
        characters=characters,
        current_situation=current_situation,
        upcoming_events=clean_text_list(summary.upcoming_events),
    )


def validated_turn(turn: StoryTurn, previous: StorySummary) -> StoryTurn:
    # Responses are checked against the schema before they get here, but that
    # only guarantees that the fields are present and of the right type. Repair
    # what can be repaired from the previous summary and reject turns that are
    # not usable, so that a bad response is reported to the player as a failed
    # turn they can retry rather than being added to the game.
    narrative = turn.narrative.strip()
    if not narrative:
        raise InvalidAIResponse('The AI returned an empty passage of prose')
    quick_actions = clean_text_list(turn.quick_actions)[:NUM_QUICK_ACTIONS]
    if len(quick_actions) < NUM_QUICK_ACTIONS:
        raise InvalidAIResponse(f'The AI returned {len(quick_actions)} usable quick actions, {NUM_QUICK_ACTIONS} are needed')
    return StoryTurn(
        narrative=narrative,
        quick_actions=quick_actions,
        # A missing scene description only means no image can be generated for
        # this turn, which is not worth failing an otherwise good turn for.
        scene_description=turn.scene_description.strip(),
        updated_summary=validated_summary(turn.updated_summary, previous),
        starts_new_chapter=turn.starts_new_chapter,
        chapter_title=(turn.chapter_title or '').strip() or None,
    )


def next_turn(
    state: GameState, player_input: str = '', plugin: AIProvider | None = None, use_model: str = '', interesting_event: bool = False
) -> StructuredOutputResult:
    # Play one turn: send the AI the story summary, the transcript of the
    # current chapter and the player's input, returning a result whose data
    # field is a StoryTurn. The response is validated and normalized by
    # validated_turn() before being used. On success the turn is appended to
    # the game log, starting a new chapter when the AI indicates one. On error,
    # including an unusable response, the state is left unmodified and the
    # error is reported via the exception field of the result, not raised.
    # For the opening turn of the game player_input may be empty. When
    # interesting_event is true the player's input is ignored and the AI is
    # asked to have something unexpected happen instead.
    plugin = plugin or default_provider()
    if plugin is None:
        return no_provider_error()
    if interesting_event:
        player_input = ''
    instructions = turn_instructions(state)
    prompt = turn_prompt(state, player_input, interesting_event)
    res = plugin.generate_structured_output(prompt, StoryTurn, instructions, use_model)
    if res.exception is not None:
        return res
    turn = res.data
    try:
        if not isinstance(turn, StoryTurn):
            raise InvalidAIResponse(f'The AI returned {type(turn).__name__} instead of a story turn')
        turn = validated_turn(turn, state.current_summary)
    except InvalidAIResponse as e:
        return validation_error(res, e)
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
    return res._replace(data=turn)


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
    print(f'\n=== {world.title} ===\n\n{world.world_description}\n')
    for i, c in enumerate(world.characters):
        print(f'{i + 1}) {c.name}: {c.description}')
        bs = textwrap.indent(textwrap.fill(c.backstory), '\t')
        print(bs)
        print()
    num = input(f'\nChoose your character [1-{len(world.characters)}]: ')
    state = start_game(brief, world, world.characters[int(num) - 1])
    player_input = ''
    while True:
        chapter_before = state.current_chapter if state.turns else -1
        turn = unwrap(next_turn(state, player_input, plugin, use_model))
        assert isinstance(turn, StoryTurn)
        if state.current_chapter != chapter_before:
            print(f'\n--- {state.chapter_titles[-1]} ---')
        print(f'\n{turn.narrative}\n')
        print(f'[Scene: {turn.scene_description}]\n')
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
        )

    def make_summary(*events: str) -> StorySummary:
        return StorySummary(
            world='A city lost in mist.',
            major_events=events,
            characters=(CharacterState('Ada', 'the player', 'built the mist engines', 'alone so far'),),
            current_situation='In the mist.',
            upcoming_events=('The mist thickens.',),
        )

    def make_turn(
        narrative: str,
        *events: str,
        starts_new_chapter: bool = False,
        chapter_title: str | None = None,
    ) -> StoryTurn:
        return StoryTurn(
            narrative=narrative,
            quick_actions=('Look around', 'Call out', 'Run'),
            scene_description=f'A picture of: {narrative}',
            updated_summary=make_summary(*events),
            starts_new_chapter=starts_new_chapter,
            chapter_title=chapter_title,
        )

    def ok(data: GeneratedWorld | StoryTurn) -> StructuredOutputResult:
        return StructuredOutputResult(data=data, raw='{"raw": "json"}', cost=0.25, currency='USD', provider='prov', model='mod')

    class TestCYOA(unittest.TestCase):
        ae = unittest.TestCase.assertEqual

        def test_ai_cyoa_world_generation(self) -> None:
            world = make_world()
            fake = FakePlugin([ok(world)])
            res = generate_world('a foggy city', fake)
            self.ae(res.data, world)
            prompt, schema, instructions, use_model = fake.calls[0]
            self.assertIn('a foggy city', prompt)
            self.assertIs(schema, GeneratedWorld)
            res = generate_world('anything', FakePlugin([StructuredOutputResult(exception=ValueError('boom'))]))
            self.assertIsInstance(res.exception, ValueError)

        def test_ai_cyoa_world_validation(self) -> None:
            def generated(world: GeneratedWorld) -> StructuredOutputResult:
                return generate_world('a foggy city', FakePlugin([ok(world)]))

            def rejected(world: GeneratedWorld) -> str:
                res = generated(world)
                self.assertIsInstance(res.exception, InvalidAIResponse)
                self.assertIsNone(res.data)
                self.ae(res.error_details, '{"raw": "json"}', 'the raw response must be reported for an unusable world')
                return str(res.exception)

            def accepted(world: GeneratedWorld) -> GeneratedWorld:
                res = generated(world)
                self.assertIsNone(res.exception, f'world unexpectedly rejected: {res.exception}')
                assert isinstance(res.data, GeneratedWorld)
                return res.data

            # A schema conforming but unusable response must be reported as an error
            self.assertIn('title', rejected(make_world()._replace(title='  ')))
            self.assertIn('description', rejected(make_world()._replace(world_description='\n')))
            chars = make_world().characters
            self.assertIn('playable characters', rejected(make_world()._replace(characters=())))
            self.assertIn('playable characters', rejected(make_world()._replace(characters=chars[:1])))
            self.assertIn(
                'playable characters',
                rejected(make_world()._replace(characters=(chars[0], chars[1]._replace(backstory='  ')))),
                'characters with an empty field must not count towards the minimum',
            )
            res = generate_world('a foggy city', FakePlugin([StructuredOutputResult(data=None, raw='{}')]))
            self.assertIsInstance(res.exception, InvalidAIResponse, 'a result with neither data nor an exception must be an error')

            # Text fields are stripped and unusable characters are discarded
            padded = make_world()._replace(
                title='  Mist City \n',
                world_description=' A city lost in perpetual mist. ',
                characters=(
                    PlayerCharacter('  Ada  ', ' a stubborn engineer ', ' She built the mist engines. '),
                    PlayerCharacter('ada', 'a duplicate', 'dropped as a duplicate name'),
                    PlayerCharacter(' ', 'nameless', 'dropped for having no name'),
                    PlayerCharacter('Brin', 'a nimble thief', 'He stole the last map.'),
                    PlayerCharacter('Cass', '', 'dropped for having no description'),
                ),
            )
            w = accepted(padded)
            self.ae(w.title, 'Mist City')
            self.ae(w.world_description, 'A city lost in perpetual mist.')
            self.ae(w.characters, make_world().characters)

        def test_ai_cyoa_art_styles(self) -> None:
            keys = [s.key for s in ART_STYLES]
            self.ae(len(keys), len(set(keys)), 'art style keys must be unique')
            self.assertTrue(all(s.key and s.name for s in ART_STYLES), 'art styles must have a key and a human readable name')
            self.assertFalse(ART_STYLES[0].prompt, 'the default art style must not add anything to image prompts')
            self.assertIs(art_style_for_key(''), ART_STYLES[0])
            self.assertIs(art_style_for_key('no-such-style'), ART_STYLES[0])
            self.ae(art_style_for_key('anime').key, 'anime')
            w = make_world()
            c = w.characters[0]
            prompt = character_portrait_prompt(c, 'anime', w.world_description)
            self.assertIn(c.name, prompt)
            self.assertIn(c.description, prompt)
            self.assertIn(w.world_description, prompt)
            self.assertIn(art_style_for_key('anime').prompt, prompt)
            self.ae(character_portrait_prompt(c), character_portrait_prompt(c, 'no-such-style'))
            self.assertNotIn(w.world_description, character_portrait_prompt(c))
            self.assertIn('image generation', WORLD_GENERATION_INSTRUCTIONS, 'character descriptions must be requested to be usable as image prompts')
            prompt = scene_image_prompt('A misty street.', 'anime')
            self.assertIn('A misty street.', prompt)
            self.assertIn(art_style_for_key('anime').prompt, prompt)
            self.assertNotIn(art_style_for_key('anime').prompt, scene_image_prompt('A misty street.'))

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
            self.assertIn('Begin the novel', prompt)
            self.assertIn(state.world.world_description, instructions)
            self.assertIn(state.character.backstory, instructions)
            self.assertIn('new named character', instructions, 'the AI must be told to add a bio for every newly introduced named character')
            self.assertIn('brief backstory', instructions, "new characters' bios must include a brief backstory")
            self.assertIn('Never repeat', instructions, 'the AI must be forbidden from repeating prose it has already written')
            self.assertIn('400', instructions, 'the AI must be given a concrete length target for passages')
            self.ae(len(state.turns), 1)
            self.ae(state.turns[0].chapter, 0)
            self.ae(state.turns[0].raw_response, '{"raw": "json"}')
            self.ae((state.turns[0].cost, state.turns[0].provider, state.turns[0].model), (0.25, 'prov', 'mod'))

            next_turn(state, 'look around', fake)
            prompt = fake.calls[1][0]
            self.assertIn('You awaken in the mist.', prompt)
            self.assertNotIn('Narrator:', prompt, 'the chapter prose must be presented as plain prose, not a dialogue transcript')
            self.assertIn('The reader directs: look around', prompt)
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

            fake = FakePlugin([ok(make_turn('A dragon lands before you.', 'dragon'))])
            res = next_turn(state, 'ignored', fake, interesting_event=True)
            self.assertIsNone(res.exception)
            prompt = fake.calls[0][0]
            self.assertIn('something unexpected', prompt)
            self.assertNotIn('ignored', prompt, "an interesting event must not send the player's input to the AI")
            self.ae(state.turns[-1].player_input, '', 'an interesting event must not record any player input')

        def test_ai_cyoa_turn_validation(self) -> None:
            def played(turn: StoryTurn, state: GameState | None = None) -> tuple[GameState, StructuredOutputResult]:
                state = state or start_game('a foggy city', make_world(), make_world().characters[0])
                return state, next_turn(state, 'go', FakePlugin([ok(turn)]))

            def rejected(turn: StoryTurn) -> str:
                state, res = played(turn)
                self.assertIsInstance(res.exception, InvalidAIResponse)
                self.assertIsNone(res.data)
                self.ae(res.error_details, '{"raw": "json"}', 'the raw response must be reported for an unusable turn')
                self.ae(state.turns, [], 'an unusable turn must not modify the game state')
                return str(res.exception)

            def accepted(turn: StoryTurn, state: GameState | None = None) -> StoryTurn:
                state, res = played(turn, state)
                self.assertIsNone(res.exception, f'turn unexpectedly rejected: {res.exception}')
                ans = state.turns[-1].turn
                self.assertIs(res.data, ans, 'the validated turn must be returned as well as stored')
                return ans

            # A schema conforming but unusable response must be reported as an error
            self.assertIn('empty passage', rejected(make_turn('   \n  ')))
            self.assertIn('quick actions', rejected(make_turn('x')._replace(quick_actions=('Look', '  ', 'look'))))
            self.assertIn('quick actions', rejected(make_turn('x')._replace(quick_actions=())))
            state = start_game('a foggy city', make_world(), make_world().characters[0])
            res = next_turn(state, 'go', FakePlugin([StructuredOutputResult(data=None, raw='{}')]))
            self.assertIsInstance(res.exception, InvalidAIResponse, 'a result with neither data nor an exception must be an error')
            self.ae(state.turns, [])

            # Text fields are stripped and quick actions are deduplicated and truncated to three
            turn = accepted(
                make_turn(' You awaken. ')._replace(
                    quick_actions=(' Run ', 'Run', 'Hide', '', 'Shout', 'Wait'),
                    scene_description='  A misty street.  ',
                    chapter_title='   ',
                )
            )
            self.ae(turn.narrative, 'You awaken.')
            self.ae(turn.quick_actions, ('Run', 'Hide', 'Shout'))
            self.ae(turn.scene_description, 'A misty street.')
            self.assertIsNone(turn.chapter_title, 'a blank chapter title must be normalized to null')
            # A missing scene description must not fail an otherwise good turn
            self.ae(accepted(make_turn('x')._replace(scene_description=' ')).scene_description, '')

            # Blank summary fields must be repaired from the previous summary
            state = start_game('a foggy city', make_world(), make_world().characters[0])
            previous = state.current_summary
            blank_summary = make_summary('awoke')._replace(
                world='  ',
                current_situation='',
                major_events=(' ', ''),
                upcoming_events=('The mist thickens.', '  ', 'The mist thickens.'),
                characters=(CharacterState('  ', 'nameless', 'nobody', ''), CharacterState('Ada', '', '  ', '')),
            )
            summary = accepted(make_turn('x')._replace(updated_summary=blank_summary), state).updated_summary
            self.ae(summary.world, previous.world)
            self.ae(summary.current_situation, previous.current_situation)
            self.ae(summary.major_events, previous.major_events, 'an empty list of major events must not erase the story memory')
            self.ae(summary.upcoming_events, ('The mist thickens.',))
            self.ae(summary.characters, previous.characters, "a character's blank fields must be filled in from the previous summary")

            # Characters that carry no information at all are dropped, an empty cast falls back to the previous one
            summary = accepted(
                make_turn('x')._replace(updated_summary=make_summary('awoke')._replace(characters=(CharacterState('Ghost', ' ', '', ''),)))
            ).updated_summary
            self.ae(summary.characters, previous.characters)
            summary = accepted(
                make_turn('x')._replace(
                    updated_summary=make_summary('awoke')._replace(
                        characters=(CharacterState('Ada', 'the player', 'engineer', ''), CharacterState('Brin', 'a thief', '', ''))
                    )
                )
            ).updated_summary
            self.ae(tuple(c.name for c in summary.characters), ('Ada', 'Brin'))
            self.ae(summary.characters[1].backstory, '', 'a new character with a description but no backstory must be kept')

            # An unrepairable summary must fail the turn
            empty = StorySummary(world='', major_events=(), characters=(), current_situation='', upcoming_events=())
            state = start_game('a foggy city', make_world(), make_world().characters[0])
            state.turns.append(
                TurnRecord(player_input='', instructions='', prompt='', raw_response='', turn=make_turn('x')._replace(updated_summary=empty), chapter=0)
            )
            res = next_turn(state, 'go', FakePlugin([ok(make_turn('y')._replace(updated_summary=empty))]))
            self.assertIsInstance(res.exception, InvalidAIResponse)
            self.assertIn('world', str(res.exception))
            self.ae(len(state.turns), 1, 'an unusable turn must not modify the game state')

        def test_ai_cyoa_rewind(self) -> None:
            state = start_game('brief', make_world(), make_world().characters[0])
            fake = FakePlugin([
                ok(make_turn('One.', 'one')),
                ok(make_turn('Two.', 'one', 'two')),
                ok(make_turn('Three.', 'one', 'two', 'three', starts_new_chapter=True, chapter_title='Part II')),
            ])
            for x in ('', 'a', 'b'):
                next_turn(state, x, fake)
            self.ae(state.current_chapter, 1)
            rewind(state)
            self.ae(state.current_chapter, 0)
            self.ae(state.current_summary.major_events, ('one', 'two'))
            rewind(state)
            self.assertRaises(ValueError, rewind, state, 2)
            self.assertRaises(ValueError, rewind, state, 0)
            rewind(state)
            self.ae(state.current_summary, initial_summary(state.world, state.character))

        def test_ai_cyoa_serialization(self) -> None:
            state = start_game('a foggy city', make_world(), make_world().characters[0], art_style='anime')
            fake = FakePlugin([
                ok(make_turn('You awaken.', 'awoke')),
                ok(make_turn('You escape.', 'awoke', 'escaped', starts_new_chapter=True, chapter_title='Freedom')),
            ])
            next_turn(state, '', fake)
            next_turn(state, 'run', fake)
            restored = deserialize_game(serialize_game(state))
            self.ae(state, restored)
            self.ae(restored.current_chapter, 1)
            self.ae(restored.art_style, 'anime')
            self.assertRaises(ValueError, deserialize_game, json.dumps({'version': GAME_SERIALIZATION_VERSION + 1, 'game': {}}))
            self.assertRaises(ValueError, deserialize_game, json.dumps(['not', 'a', 'game']))

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestCYOA)


# }}}


if __name__ == '__main__':
    develop()
