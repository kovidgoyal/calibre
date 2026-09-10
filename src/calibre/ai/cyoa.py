#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Backend for an AI driven "Create Your Own Adventure" game. The game has two
# phases: world generation, where a brief description from the player is
# expanded by the AI into a full world with playable characters, and the
# turn-by-turn game itself. Every turn the AI narrates what happens, suggests
# three quick actions of deliberately different kinds, see QuickActionKind,
# describes the current scene for an image generation AI,
# reports whether a new chapter starts and sends the changes the passage makes
# to a running summary of the story, which Python, not the AI, maintains. The
# AI is sent the story summary and the transcript of only the current chapter,
# plus the closing passages of the previous one as a bridge while a chapter is
# young, so the context stays bounded no matter how long the game runs. The AI's
# response to every turn is kept, turn by turn, so games can be rewound and
# saved/loaded. What was sent to the AI is not kept, as it is reconstructable
# from the game state, see STORE_PROMPTS_IN_TURN_RECORDS.

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

# Games serialized by older versions are migrated up to this version on load,
# see migrated_game(), so bumping it does not orphan existing saves.
GAME_SERIALIZATION_VERSION = 4

# The id of the CharacterState of the character the player plays. It is fixed
# so that their entry in the story summary and their portrait can be found
# without matching on their name, which both the player and the AI can change.
PROTAGONIST_ID = 'protagonist'


def character_id_for_name(name: str) -> str:
    # A stable id derived from a character's name, for characters that have
    # none, either because the AI failed to invent one or because they come
    # from a game saved before ids existed.
    words = ''.join(c if c.isalnum() else ' ' for c in name.casefold()).split()
    return '-'.join(words)[:32].rstrip('-') or 'character'


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
    # Never generated directly by the AI: every turn it sends a
    # CharacterDelta for each character it changes and updated_characters()
    # merges those into the cast of the previous summary.
    name: str
    description: Annotated[str, 'The durable physical appearance and nature of the character, doubling as the prompt used to draw them']
    backstory: Annotated[str, "The character's brief backstory: who they are and how they came to be part of the story"]
    relationships: Annotated[str, 'Their relationships with the player and the other characters, and how those have changed']
    # Trailing and defaulted so that games serialized before these fields
    # existed still deserialize, see instantiate().
    current_state: Annotated[
        str,
        'Everything that is true of this character only right now: where they are, what they are doing,'
        ' their physical condition and any injuries, their mood, what they are carrying and what they intend to do next',
    ] = ''
    id: Annotated[
        str,
        "A short, permanent, lowercase identifier for this character, such as 'marlo'."
        ' It is the identity of the character, not their name, so it survives them being renamed.',
    ] = ''


# The summary is sent to the AI in full on every turn, so the list of major
# events has to be bounded or it grows without limit as a game goes on. The AI
# is asked to condense the older events into single lines as the list
# approaches this cap, see SummaryUpdate.consolidated_major_events, and the
# oldest are dropped if it does not.
MAX_MAJOR_EVENTS = 30


class StorySummary(NamedTuple):
    doc = Doc('A summary of the story so far, serving as memory for continuing it')
    # Maintained by Python, not by the AI: every turn the AI sends only a
    # SummaryUpdate and updated_summary() merges it into the previous summary.
    world: Annotated[str, 'Description of the world and its current state']
    major_events: Annotated[tuple[str, ...], f'The major events of the story so far, in chronological order, at most {MAX_MAJOR_EVENTS} of them']
    characters: Annotated[
        tuple[CharacterState, ...],
        'All significant named characters in the story, each with a description, brief backstory, their relationships and their current state',
    ]
    current_situation: Annotated[str, 'Where the player currently is and what is happening']
    upcoming_events: Annotated[tuple[str, ...], 'Foreshadowed or planned future events and unresolved plot threads']


class CharacterDelta(NamedTuple):
    doc = Doc(
        'A change to one character of the story summary. Only what changed this turn need be filled in:'
        ' every field left empty keeps the value the character already has in the summary.'
    )
    id: Annotated[
        str,
        "The short, permanent, lowercase identifier of the character this updates, such as 'marlo'."
        ' It is the identity of the character, not their name: reproduce the id from the summary verbatim,'
        ' even when you rename the character or reveal their true identity.'
        ' Invent a new one, based on their name, only for a character you are adding to the summary for the first time.',
    ]
    current_state: Annotated[
        str,
        'Everything that is true of this character only right now: where they are, what they are doing,'
        ' their physical condition and any injuries, their mood, what they are carrying and what they intend to do next.'
        ' Always fill this in: it replaces whatever the summary currently says about them.',
    ]
    name: Annotated[
        str,
        'The name of the character. Fill this in only when you are adding them to the summary or the story renames them;'
        ' leave it empty to keep the name they already have.',
    ] = ''
    description: Annotated[
        str,
        'The physical appearance and nature of the character: their looks, age, distinguishing features,'
        ' the kind of clothes they wear and their temperament. This doubles as the prompt used to draw them.'
        ' Leave it empty unless you are adding them to the summary, or their appearance or nature has permanently'
        ' changed, for example a new scar, the loss of a limb or aging, in which case give the full new description.'
        ' Never record events, mood, injuries, location or plot developments here, they belong in current_state.',
    ] = ''
    backstory: Annotated[
        str,
        "The character's brief backstory: who they are and how they came to be part of the story."
        ' Leave it empty unless you are adding them to the summary, or the story has just revealed something new'
        ' about their past, in which case give the full extended backstory.',
    ] = ''
    relationships: Annotated[
        str,
        'How this character stands with the protagonist and the other characters.'
        ' Leave it empty unless their relationships changed this turn, in which case give them in full.',
    ] = ''


class SummaryUpdate(NamedTuple):
    doc = Doc('The changes a passage of the story makes to the running summary of the story')
    current_situation: Annotated[str, 'Where the protagonist is and what is happening as this passage ends. This replaces the previous situation.']
    character_updates: Annotated[
        tuple[CharacterDelta, ...],
        'One entry for every character this passage changes and every new named character it introduces.'
        ' Leave out the characters it does not touch: they keep the state they already have in the summary.',
    ]
    new_major_events: Annotated[
        tuple[str, ...],
        'The events of this passage that matter to the rest of the story, one short line each, in chronological order.'
        ' They are appended to the major events already in the summary, so never repeat one that is already there.'
        ' Leave this empty when nothing of lasting importance happened.',
    ]
    upcoming_events: Annotated[
        tuple[str, ...],
        'The complete list of foreshadowed or planned future events and unresolved plot threads as it now stands.'
        ' This one field replaces the previous list rather than adding to it, so repeat every thread that is still'
        ' open and leave out only the ones this passage has resolved.',
    ]
    world: Annotated[
        str,
        'The description of the world. Leave it empty unless the state of the world itself has changed, in which case give the full new description.',
    ] = ''
    consolidated_major_events: Annotated[
        tuple[str, ...],
        'A condensed rewrite of the major events that were already in the summary, replacing them.'
        f' Leave this empty except when the summary is nearing its limit of {MAX_MAJOR_EVENTS} major events:'
        ' then merge the older ones into fewer single lines, each covering several events,'
        ' keeping every development the rest of the story still depends on.',
    ] = ()


# Asking the AI for three "short, distinct actions the player could plausibly
# take next" reliably gets three variations on the single obvious move. Asking
# for one action of each kind instead costs nothing and gets three choices that
# actually differ, so every action the AI suggests comes tagged with its kind,
# taken from this fixed vocabulary.
class QuickActionKind(Enum):
    doc = Doc(
        'The kind of approach a suggested action takes. The actions offered to the player must differ in kind,'
        ' so that they are genuinely different choices rather than variations on a single idea.'
    )
    cautious = 'cautious'
    bold = 'bold'
    social = 'social'
    investigate = 'investigate'
    # The catch-all for an action that fits none of the above. Also what an
    # action of a game saved before the kinds existed becomes, see
    # migrated_game_v3_to_v4().
    other = 'other'


# What each kind of action means, sent to the AI as part of the instructions
# so that the vocabulary is defined in exactly one place. Deliberately not
# translated, as AI models work best with English instructions.
QUICK_ACTION_KIND_DESCRIPTIONS: dict[QuickActionKind, str] = {
    QuickActionKind.cautious: 'hold back, defend, hide, retreat, prepare or take the careful option',
    QuickActionKind.bold: 'act directly and decisively: confront someone, force the issue or take the physical risk',
    QuickActionKind.social: 'engage another character: persuade, deceive, plead, bargain, provoke or simply ask',
    QuickActionKind.investigate: 'find something out: look closer, search, follow, eavesdrop or examine',
    QuickActionKind.other: 'an action that fits none of the other kinds',
}

# The kinds of action the AI is asked for, one per entry, in this order. Each
# entry the AI may satisfy with any one of its kinds, so that a scene with
# nobody to talk to can still offer a third action worth taking.
REQUESTED_QUICK_ACTION_KINDS: tuple[tuple[QuickActionKind, ...], ...] = (
    (QuickActionKind.cautious,),
    (QuickActionKind.bold,),
    (QuickActionKind.social, QuickActionKind.investigate),
)


def quick_action_kind_name(kind: QuickActionKind) -> str:
    # A short, translated name for the kind of an action, shown to the player
    # next to the action. Empty for the catch-all kind, which says nothing
    # worth taking up space in the UI for.
    return {
        QuickActionKind.cautious: _('Cautious'),
        QuickActionKind.bold: _('Bold'),
        QuickActionKind.social: _('Social'),
        QuickActionKind.investigate: _('Investigative'),
    }.get(kind, '')


class QuickAction(NamedTuple):
    doc = Doc('One action suggested to the player, with the kind of approach it takes')
    text: Annotated[str, 'The action itself, as a short imperative phrase, such as "Follow the stranger into the alley"']
    # Trailing and defaulted so that a response that omits it, and a game
    # serialized before the kinds existed, are still usable.
    kind: Annotated[QuickActionKind, 'Which kind of approach this action takes'] = QuickActionKind.other


class StoryTurn(NamedTuple):
    doc = Doc('One turn of the adventure')
    narrative: Annotated[
        str,
        'The next passage of the novel, continuing seamlessly from the prose written so far without repeating any of it,'
        ' written as immersive long form prose'
        ' with dialogue from the characters, their expressions and reactions, and scene descriptions where needed',
    ]
    quick_actions: Annotated[
        tuple[QuickAction, ...],
        'Exactly three actions the player could plausibly take next, one of each kind requested in the instructions:'
        ' a cautious one, a bold one and one that engages another character or investigates something.'
        ' They must be three genuinely different approaches to the situation, not three phrasings of the obvious next step.',
    ]
    scene_description: Annotated[
        str,
        'A self-contained visual description of the current scene,'
        ' suitable as a prompt for an image generation AI, that does not rely on knowledge of the story.'
        ' Describe the current physical state of the characters, their clothing and emotional state.',
    ]
    summary_update: Annotated[SummaryUpdate, 'The changes this passage makes to the running summary of the story']
    starts_new_chapter: Annotated[bool, 'True only when this turn begins a major new phase of the story, suitable as the start of a new chapter']
    chapter_title: Annotated[str | None, 'A title for the new chapter when starts_new_chapter is true, null otherwise']


# }}}


# Game state and log of AI exchanges {{{


# Set this to True to record the exact instructions and prompt sent to the AI
# in every turn record. Both are reconstructable from the game state via
# turn_instructions() and turn_prompt(), and the prompt embeds the transcript
# of the chapter so far, so storing them makes a saved game grow
# quadratically with the length of a chapter. For debugging only.
STORE_PROMPTS_IN_TURN_RECORDS = False


class TurnRecord(NamedTuple):
    # The log of a single exchange with the AI, sufficient to replay or rewind
    # the game and to audit what the AI returned. What was sent to the AI is
    # not recorded, see STORE_PROMPTS_IN_TURN_RECORDS.
    player_input: str  # what the player typed or chose, empty for the opening turn
    raw_response: str  # the raw JSON text returned by the AI
    turn: StoryTurn  # the parsed response
    # The story summary as it stands after this turn: the summary of the
    # previous turn with the turn's SummaryUpdate merged into it. Stored
    # rather than recomputed by replaying the updates so that rewinding a
    # game stays a matter of dropping turn records.
    summary: StorySummary
    chapter: int  # zero based chapter number this turn belongs to
    cost: float = 0
    currency: str = ''
    provider: str = ''
    model: str = ''
    # The system prompt and the user prompt sent to the AI, empty unless
    # STORE_PROMPTS_IN_TURN_RECORDS was on when the turn was played.
    instructions: str = ''
    prompt: str = ''


def initial_summary(world: GeneratedWorld, character: PlayerCharacter) -> StorySummary:
    return StorySummary(
        world=world.world_description,
        major_events=(),
        # current_state is left at its default: nothing has happened yet.
        characters=(
            CharacterState(name=character.name, description=character.description, backstory=character.backstory, relationships='', id=PROTAGONIST_ID),
        ),
        current_situation='The adventure has not yet begun.',
        upcoming_events=(),
    )


# The prose sent to the AI is that of the current chapter, which collapses to
# a single passage the moment the AI starts a new chapter, taking the ground
# out from under the instruction to continue seamlessly from where the
# chapter's prose ends. So the closing passages of the previous chapter are
# sent as well, as a bridge, until the new chapter holds this many turns of
# its own, see GameState.prose_context.
MIN_PROSE_CONTEXT_TURNS = 3


@dataclass
class GameState:
    # The complete state of a game. Everything except the turn log is
    # derived, which keeps rewinding trivial: dropping turn records restores
    # the summary and chapter position automatically.
    brief: str  # the player's original brief description of the world
    world: GeneratedWorld
    # The index in world.characters of the character the player chose. Only
    # the index is stored, so that there is a single copy of the played
    # character to edit, see the character property.
    character_index: int
    turns: list[TurnRecord] = field(default_factory=list)
    # The key of the art style from ART_STYLES used for generated scene images.
    art_style: str = ''

    @property
    def character(self) -> PlayerCharacter:
        # Always in range: deserialize_game() and start_game() reject an
        # out of range index and nothing removes characters from a world.
        return self.world.characters[self.character_index]

    @property
    def current_chapter(self) -> int:
        return self.turns[-1].chapter if self.turns else 0

    @property
    def current_chapter_turns(self) -> tuple[TurnRecord, ...]:
        c = self.current_chapter
        return tuple(t for t in self.turns if t.chapter == c)

    @property
    def prose_context(self) -> tuple[tuple[TurnRecord, ...], tuple[TurnRecord, ...]]:
        # The prose to send to the AI, as (bridge, current chapter): the turns
        # of the current chapter, and the turns of earlier chapters needed to
        # bring the prose in context up to MIN_PROSE_CONTEXT_TURNS turns,
        # which is empty once the current chapter is long enough to stand on
        # its own. Only the summary carries the story before that.
        current = self.current_chapter_turns
        bridge = tuple(t for t in self.turns[-MIN_PROSE_CONTEXT_TURNS:] if t.chapter != self.current_chapter)
        return bridge, current

    @property
    def current_summary(self) -> StorySummary:
        return self.turns[-1].summary if self.turns else initial_summary(self.world, self.character)

    @property
    def chapter_titles(self) -> tuple[str, ...]:
        titles: list[str] = []
        for t in self.turns:
            if t.chapter >= len(titles):
                titles.append(t.turn.chapter_title or _('Chapter {}').format(len(titles) + 1))
        return tuple(titles)


def start_game(brief: str, world: GeneratedWorld, character_index: int = 0, art_style: str = '') -> GameState:
    # character_index is the index in world.characters of the character the
    # player chose to play as.
    if not 0 <= character_index < len(world.characters):
        raise ValueError(f'{character_index} is not the index of a character in a world with {len(world.characters)} characters')
    return GameState(brief=brief, world=world, character_index=character_index, art_style=art_style)


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


def migrated_game_v1_to_v2(game: dict[str, Any]) -> dict[str, Any]:
    # Version 1 stored a copy of the played character rather than its index in
    # world.characters, had no stable ids for the characters of the story
    # summary, and recorded the instructions and prompt of every turn, which
    # are reconstructable from the state, see STORE_PROMPTS_IN_TURN_RECORDS.
    game = dict(game)
    world = dict(game.get('world') or {})
    characters = list(world.get('characters') or ())
    played = game.pop('character', None)
    protagonist, idx = '', -1
    if isinstance(played, dict):
        protagonist = str(played.get('name') or '')
        try:
            idx = characters.index(played)
        except ValueError:
            idx = next((i for i, c in enumerate(characters) if isinstance(c, dict) and c.get('name') == protagonist), -1)
        if idx < 0 and protagonist:
            # the played character was edited until it no longer matched any
            # character of the world, so add them back rather than lose them
            characters.append(played)
            idx = len(characters) - 1
    world['characters'] = characters
    game['world'] = world
    game['character_index'] = max(0, idx)
    turns: list[Any] = []
    for record in game.get('turns') or ():
        if isinstance(record, dict):
            record = {k: v for k, v in record.items() if k not in ('instructions', 'prompt')}
            turn = dict(record.get('turn') or {})
            summary = dict(turn.get('updated_summary') or {})
            summary['characters'] = [migrated_character_v1_to_v2(c, protagonist) for c in summary.get('characters') or ()]
            turn['updated_summary'] = summary
            record['turn'] = turn
        turns.append(record)
    game['turns'] = turns
    return game


def migrated_character_v1_to_v2(character: Any, protagonist: str) -> Any:  # noqa: ANN401
    if not isinstance(character, dict) or character.get('id'):
        return character
    name = str(character.get('name') or '')
    cid = PROTAGONIST_ID if name.strip() and name.strip().casefold() == protagonist.strip().casefold() else character_id_for_name(name)
    return dict(character, id=cid)


def migrated_game_v2_to_v3(game: dict[str, Any]) -> dict[str, Any]:
    # Version 2 had the AI return the whole story summary every turn, stored
    # as updated_summary inside the turn. It now returns only what changed,
    # which Python merges into the summary of the previous turn, so the
    # summary moves onto the turn record and the turn keeps the update the AI
    # sent. There is no record of what the AI actually changed in an old game,
    # so the update is synthesized as one that replaces everything, which
    # merges to exactly the summary that was stored.
    game = dict(game)
    turns: list[Any] = []
    for record in game.get('turns') or ():
        if isinstance(record, dict):
            record = dict(record)
            turn = dict(record.get('turn') or {})
            summary = dict(turn.pop('updated_summary', None) or {})
            record['summary'] = summary
            turn['summary_update'] = {
                'world': summary.get('world') or '',
                'current_situation': summary.get('current_situation') or '',
                'character_updates': [
                    {
                        'id': c.get('id') or '',
                        'name': c.get('name') or '',
                        'description': c.get('description') or '',
                        'backstory': c.get('backstory') or '',
                        'relationships': c.get('relationships') or '',
                        'current_state': c.get('current_state') or '',
                    }
                    for c in summary.get('characters') or ()
                    if isinstance(c, dict)
                ],
                'new_major_events': [],
                'consolidated_major_events': list(summary.get('major_events') or ()),
                'upcoming_events': list(summary.get('upcoming_events') or ()),
            }
            record['turn'] = turn
        turns.append(record)
    game['turns'] = turns
    return game


def migrated_game_v3_to_v4(game: dict[str, Any]) -> dict[str, Any]:
    # Version 3 had the AI return the quick actions as bare strings. Every
    # action now comes with the kind of approach it takes, chosen from a fixed
    # vocabulary, so that the three actions offered differ in kind instead of
    # being three variations on the obvious. Nothing records what kind the
    # actions of an old game were, so they all become the catch-all kind,
    # which the UI shows no label for.
    game = dict(game)
    turns: list[Any] = []
    for record in game.get('turns') or ():
        if isinstance(record, dict):
            record = dict(record)
            turn = dict(record.get('turn') or {})
            turn['quick_actions'] = [{'text': a, 'kind': QuickActionKind.other.value} if isinstance(a, str) else a for a in turn.get('quick_actions') or ()]
            record['turn'] = turn
        turns.append(record)
    game['turns'] = turns
    return game


def migrated_game(game: dict[str, Any], version: int) -> dict[str, Any]:
    # Bring the JSON of a game serialized by an older version of calibre up to
    # GAME_SERIALIZATION_VERSION, so that changing the format does not orphan
    # existing saves. Keys that no longer exist are ignored by instantiate()
    # and missing keys with a default are filled in by it, so only renamed and
    # newly required fields need handling here.
    if version < 2:
        game = migrated_game_v1_to_v2(game)
    if version < 3:
        game = migrated_game_v2_to_v3(game)
    if version < 4:
        game = migrated_game_v3_to_v4(game)
    return game


def deserialize_game(raw: str) -> GameState:
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get('game'), dict):
        raise ValueError('Not a valid serialized CYOA game')
    version = data.get('version')
    if not isinstance(version, int) or version < 1:
        raise ValueError(f'Not a valid serialized CYOA game: {version!r} is not a serialization version')
    if version > GAME_SERIALIZATION_VERSION:
        raise ValueError(f'This game was saved in the version {version} format, which this version of calibre cannot read')
    ans = instantiate(migrated_game(data['game'], version), spec_for_class(GameState), GameState.__name__)
    assert isinstance(ans, GameState)
    if not 0 <= ans.character_index < len(ans.world.characters):
        raise ValueError(f'{ans.character_index} is not the index of a character in a world with {len(ans.world.characters)} characters')
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


def quick_action_instructions() -> str:
    # The part of the turn instructions that asks for the quick actions, built
    # from the vocabulary of kinds so that the AI is told what each kind it
    # can tag an action with means, see QuickActionKind.
    parts = [
        (
            '- quick_actions: exactly three actions the reader could have the protagonist take next, each a short imperative'
            ' phrase and each tagged with the kind of approach it takes. They must be three genuinely different approaches to'
            ' the situation, not three phrasings of the obvious next step, so give one action of each of these kinds, in this order:'
        )
    ]
    for group in REQUESTED_QUICK_ACTION_KINDS:
        kinds = ' or '.join(f'"{k.value}"' for k in group)
        meanings = '; or '.join(QUICK_ACTION_KIND_DESCRIPTIONS[k] for k in group)
        parts.append(f'  * {kinds}: {meanings}.')
    parts.append(
        f'  Use whichever kind of the last group the scene affords. Use "{QuickActionKind.other.value}" only for an action that'
        ' genuinely fits none of the kinds. Every action must be something the protagonist can actually do from where they are'
        ' right now, and must follow from the passage you have just written rather than from the story in general.'
    )
    return '\n'.join(parts)


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
        quick_action_instructions(),
        (
            '- scene_description: a self-contained visual description of the current scene for an image generation AI.'
            ' It must make sense without any knowledge of the story.'
        ),
        (
            '- summary_update: how this passage changes the story summary, which is your only memory of everything'
            ' that happened before the current chapter. Send only what changed. Every field you leave empty keeps the'
            ' value it already has in the summary, so there is never any need to copy text out of the summary and back.'
        ),
        (
            '- character_updates: one entry for every character this passage changes, and one for every new named character it introduces.'
            ' Leave out the characters the passage does not touch. Fill in current_state, which is everything that is only true of them'
            ' right now: where they are, what they are doing, their physical condition and injuries, their mood, what they carry and what'
            ' they intend next. Leave description, backstory and relationships empty unless this passage changed them: description only when'
            ' their appearance or nature has permanently changed, backstory only when the story reveals something new about their past,'
            ' relationships only when how they stand with someone has shifted. Never put events, mood, injuries or location into description,'
            ' which is also used as the prompt to draw them.'
            ' A character you are introducing needs a name, a short description and a brief backstory as well as their current state.'
        ),
        (
            "- Each entry of character_updates names its character by id, which is that character's permanent identity, not their name."
            ' Reproduce the id from the summary verbatim, even when you rename them:'
            ' when "the stranger" turns out to be Marlo, put the new name in name and leave the id untouched.'
            ' Never change, swap or re-use an id and never send two entries for the same character.'
            ' Invent a new short lowercase id, based on their name, only for a character you are adding to the summary for the first time.'
        ),
        (
            '- new_major_events: the events of this passage that matter to the rest of the story, one short line each.'
            ' They are added to the major events already in the summary, so never repeat one that is already there,'
            ' and leave the field empty when nothing of lasting importance happened.'
            f' The summary holds at most {MAX_MAJOR_EVENTS} major events: as it nears that many, use consolidated_major_events to'
            ' replace the events already in the summary with a shorter list that merges the older ones into single lines.'
        ),
        (
            '- upcoming_events is the one field that replaces rather than adds to what the summary holds:'
            ' give the whole list of unresolved plot threads as it now stands, repeating those still open and dropping those this passage resolved.'
        ),
        '- current_situation: where the protagonist is and what is happening as this passage ends.',
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

    def add_prose(turns: Iterable[TurnRecord]) -> None:
        for t in turns:
            if t.player_input:
                parts.append(f'[The reader directs: {t.player_input}]')
                parts.append('')
            parts.append(t.turn.narrative)
            parts.append('')

    bridge, transcript = state.prose_context
    if bridge:
        # A chapter that has only just started has almost no prose of its own,
        # so the passages leading up to it come along to bridge the gap. They
        # are labelled as belonging to the previous chapter, so that the AI
        # continues from the end of the current chapter, not from these.
        parts.append('The closing prose of the previous chapter, for continuity. The reader has read it and the story has moved past it:')
        parts.append('')
        add_prose(bridge)
    if transcript:
        parts.append('The prose of the current chapter so far, which the reader has already read:')
        parts.append('')
        add_prose(transcript)
    if state.turns:
        if interesting_event:
            parts.append(
                'The reader waits to see what happens next. Have something unexpected and interesting happen, taking the story in a surprising new direction.'
            )
            if threads := state.current_summary.upcoming_events:
                # The summary already lists the threads the AI itself
                # foreshadowed, so a surprise that pays one of them off beats
                # one invented from nothing, which leaves them dangling.
                parts.append(
                    'Do it, if you can, by paying off one of these unresolved threads from upcoming_events,'
                    ' bringing it to the surface now rather than leaving it for later:'
                )
                parts.extend(f'- {t}' for t in threads)
                parts.append('Invent something unrelated only if none of them can plausibly surface in this moment.')
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


# The AI is asked for one quick action of each requested kind, but they are
# only a convenience: the player can always type an action of their own.
# Throwing away a passage of prose the player has already paid for because the
# AI repeated itself and one of the three was deduplicated away would be a far
# worse trade than rendering the two that survived, so any at all are accepted.
NUM_QUICK_ACTIONS = len(REQUESTED_QUICK_ACTION_KINDS)


def selected_quick_actions(actions: Iterable[QuickAction]) -> tuple[QuickAction, ...]:
    # Normalize the actions the AI suggests: strip them, discard the blank and
    # duplicate ones and keep at most NUM_QUICK_ACTIONS. When the AI offers
    # more than that, one action of each kind is preferred over simply taking
    # the first few, as three actions that differ in kind is the whole point
    # of asking for kinds. The order the AI put them in is kept, as it is
    # asked for them in the order the kinds are requested.
    unique: list[QuickAction] = []
    seen: set[str] = set()
    for a in actions:
        text = a.text.strip()
        if text and (key := text.casefold()) not in seen:
            seen.add(key)
            unique.append(a._replace(text=text))
    if len(unique) <= NUM_QUICK_ACTIONS:
        return tuple(unique)
    of_kind: dict[QuickActionKind, QuickAction] = {}
    for a in unique:
        of_kind.setdefault(a.kind, a)
    chosen = list(of_kind.values())[:NUM_QUICK_ACTIONS]
    if len(chosen) < NUM_QUICK_ACTIONS:  # fewer kinds than actions to show, so fill up with the rest
        picked = {a.text for a in chosen}
        chosen += [a for a in unique if a.text not in picked][: NUM_QUICK_ACTIONS - len(chosen)]
    position = {a.text: i for i, a in enumerate(unique)}
    return tuple(sorted(chosen, key=lambda a: position[a.text]))


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


def updated_characters(updates: Iterable[CharacterDelta], previous: StorySummary) -> tuple[CharacterState, ...]:
    # Merge the AI's per character updates into the cast of the previous
    # summary. Every field an update leaves blank keeps the value the
    # character already has, and a character the AI says nothing about this
    # turn is left exactly as they were, so "unchanged" is the default rather
    # than something the AI has to achieve by retyping text it was sent.
    # A character is identified by their id rather than their name, so that
    # renaming one, which fiction does constantly as "the stranger" turns out
    # to be Marlo, updates their entry instead of forking it in two. The AI is
    # told to carry ids forward but cannot be relied on to always do so, hence
    # the fallback to matching by name and the invented ids.
    ans = list(previous.characters)
    by_id = {c.id: i for i, c in enumerate(ans) if c.id}
    by_name = {c.name.strip().casefold(): i for i, c in enumerate(ans) if c.name.strip()}
    updated: set[int] = set()
    for u in updates:
        uid, name = u.id.strip(), u.name.strip()
        idx = by_id.get(uid, -1) if uid else -1
        if idx < 0 and name:
            idx = by_name.get(name.casefold(), -1)
        if idx >= 0:
            if idx in updated:
                continue  # a second update for a character already updated this turn
            updated.add(idx)
            c = ans[idx]
            ans[idx] = c._replace(
                name=name or c.name,
                description=u.description.strip() or c.description,
                backstory=u.backstory.strip() or c.backstory,
                relationships=u.relationships.strip() or c.relationships,
                current_state=u.current_state.strip() or c.current_state,
            )
            if name:
                by_name[name.casefold()] = idx
            continue
        # A character not already in the summary. Without a name they can
        # neither be matched with a later update nor be referred to by the AI
        # or the player, and without a description or a backstory nothing is
        # known about them that outlives this turn, so they are dropped and a
        # later turn can re-introduce them if they matter.
        description, backstory = u.description.strip(), u.backstory.strip()
        if not name or not (description or backstory):
            continue
        cid = uid or character_id_for_name(name)
        if cid in by_id:  # the AI invented an id already in use, keep them apart
            base, n = cid, 2
            while cid in by_id:
                cid, n = f'{base}-{n}', n + 1
        ans.append(
            CharacterState(
                name=name, description=description, backstory=backstory, relationships=u.relationships.strip(), current_state=u.current_state.strip(), id=cid
            )
        )
        by_id[cid] = by_name[name.casefold()] = len(ans) - 1
        updated.add(len(ans) - 1)
    return tuple(ans)


def updated_summary(update: SummaryUpdate, previous: StorySummary) -> StorySummary:
    # The summary is the only memory the AI has of the story beyond the
    # current chapter, so it is maintained here rather than by the AI: the AI
    # sends only what this turn changed and everything else is carried over
    # from the previous summary, which cannot silently lose the plot the way
    # asking the AI to re-emit the whole summary every turn does.
    world = update.world.strip() or previous.world
    if not world:
        raise InvalidAIResponse('The AI returned a story summary with no description of the world')
    current_situation = update.current_situation.strip() or previous.current_situation
    if not current_situation:
        raise InvalidAIResponse('The AI returned a story summary with no description of the current situation')
    characters = updated_characters(update.character_updates, previous)
    if not characters:
        raise InvalidAIResponse('The AI returned a story summary with no characters')
    # The AI is asked to condense the older events as the list approaches
    # MAX_MAJOR_EVENTS; dropping the oldest is the backstop for when it does
    # not, which keeps the summary, and so the prompt, bounded.
    events = clean_text_list(update.consolidated_major_events) or previous.major_events
    return StorySummary(
        world=world,
        major_events=clean_text_list(events + tuple(update.new_major_events))[-MAX_MAJOR_EVENTS:],
        characters=characters,
        current_situation=current_situation,
        # Deliberately the one field that is replaced rather than merged: a
        # plot thread the story has resolved has to be able to leave the
        # summary, and there is no way to say "drop this one" in a list of
        # bare strings. The list is short, so having the AI re-send the
        # threads that are still open costs little.
        upcoming_events=clean_text_list(update.upcoming_events),
    )


def validated_turn(turn: StoryTurn) -> StoryTurn:
    # Responses are checked against the schema before they get here, but that
    # only guarantees that the fields are present and of the right type.
    # Normalize what can be normalized and reject turns that are not usable,
    # so that a bad response is reported to the player as a failed turn they
    # can retry rather than being added to the game. The summary update is not
    # touched here, updated_summary() repairs it against the previous summary.
    narrative = turn.narrative.strip()
    if not narrative:
        raise InvalidAIResponse('The AI returned an empty passage of prose')
    quick_actions = selected_quick_actions(turn.quick_actions)
    if not quick_actions:
        raise InvalidAIResponse('The AI returned no usable quick actions')
    return StoryTurn(
        narrative=narrative,
        quick_actions=quick_actions,
        # A missing scene description only means no image can be generated for
        # this turn, which is not worth failing an otherwise good turn for.
        scene_description=turn.scene_description.strip(),
        summary_update=turn.summary_update,
        starts_new_chapter=turn.starts_new_chapter,
        chapter_title=(turn.chapter_title or '').strip() or None,
    )


def next_turn(
    state: GameState, player_input: str = '', plugin: AIProvider | None = None, use_model: str = '', interesting_event: bool = False
) -> StructuredOutputResult:
    # Play one turn: send the AI the story summary, the transcript of the
    # current chapter and the player's input, returning a result whose data
    # field is a StoryTurn. The response is validated and normalized by
    # validated_turn() and its summary update merged into the story summary by
    # updated_summary() before being used. On success the turn is appended to
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
        turn = validated_turn(turn)
        summary = updated_summary(turn.summary_update, state.current_summary)
    except InvalidAIResponse as e:
        return validation_error(res, e)
    chapter = state.current_chapter
    if state.turns and turn.starts_new_chapter:
        chapter += 1
    state.turns.append(
        TurnRecord(
            player_input=player_input,
            raw_response=res.raw,
            turn=turn,
            summary=summary,
            chapter=chapter,
            cost=res.cost,
            currency=res.currency,
            provider=res.provider,
            model=res.model,
            instructions=instructions if STORE_PROMPTS_IN_TURN_RECORDS else '',
            prompt=prompt if STORE_PROMPTS_IN_TURN_RECORDS else '',
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
    state = start_game(brief, world, int(num) - 1)
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
            print(f'{i + 1}) [{action.kind.value}] {action.text}')
        player_input = input('\nWhat do you do? (number for a quick action, empty to quit): ').strip()
        if not player_input:
            break
        if player_input.isdigit() and 1 <= int(player_input) <= len(turn.quick_actions):
            player_input = turn.quick_actions[int(player_input) - 1].text


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

    def make_update(*new_events: str, **kw: Any) -> SummaryUpdate:  # noqa: ANN401
        # An update of the kind the AI sends every turn: what just happened
        # and the protagonist's new state, with everything else left unchanged.
        ans = SummaryUpdate(
            current_situation='In the mist.',
            character_updates=(CharacterDelta(id=PROTAGONIST_ID, current_state='lost in the mist'),),
            new_major_events=new_events,
            upcoming_events=('The mist thickens.',),
        )
        return ans._replace(**kw)

    def make_actions(*actions: str | QuickAction) -> tuple[QuickAction, ...]:
        # Bare strings are convenient for the tests that do not care about the
        # kinds, they get the catch-all kind.
        return tuple(a if isinstance(a, QuickAction) else QuickAction(a) for a in actions)

    def make_turn(
        narrative: str,
        *new_events: str,
        starts_new_chapter: bool = False,
        chapter_title: str | None = None,
    ) -> StoryTurn:
        return StoryTurn(
            narrative=narrative,
            quick_actions=(
                QuickAction('Hide in the doorway', QuickActionKind.cautious),
                QuickAction('Charge into the mist', QuickActionKind.bold),
                QuickAction('Call out to whoever is there', QuickActionKind.social),
            ),
            scene_description=f'A picture of: {narrative}',
            summary_update=make_update(*new_events),
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
            state = start_game('a foggy city', make_world())
            self.ae(state.current_summary.world, state.world.world_description)
            self.ae(state.current_chapter, 0)
            fake = FakePlugin([
                ok(make_turn('You awaken in the mist.', 'awoke')),
                ok(make_turn('Shapes loom around you.', 'saw shapes')),
                ok(make_turn('You descend into the tunnels.', 'descended', starts_new_chapter=True, chapter_title='The Descent')),
                ok(make_turn('The tunnels narrow.', 'tunnels narrowed')),
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
            self.assertIn('current_state', instructions, 'the AI must be told to record what is only true right now in current_state')
            self.assertIn(
                'Send only what changed',
                instructions,
                'the AI must be told to send only what this turn changed, not the whole summary',
            )
            self.assertIn(
                'leave empty keeps the value it already has',
                instructions,
                'the AI must be told that a field it leaves empty keeps the value the summary already has',
            )
            self.assertIn(str(MAX_MAJOR_EVENTS), instructions, 'the AI must be told the limit it has to consolidate major events to stay under')
            self.assertIn('Never repeat', instructions, 'the AI must be forbidden from repeating prose it has already written')
            self.assertIn('400', instructions, 'the AI must be given a concrete length target for passages')
            self.assertIn('permanent identity', instructions, 'the AI must be told to carry the id of every character in the summary forward unchanged')
            self.ae(len(state.turns), 1)
            self.ae(state.turns[0].chapter, 0)
            self.ae(state.turns[0].raw_response, '{"raw": "json"}')
            self.ae((state.turns[0].instructions, state.turns[0].prompt), ('', ''), 'what was sent to the AI must not be recorded by default')
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
            self.assertIn('closing prose of the previous chapter', prompt, 'a chapter that has only just started must be given a bridge')
            self.assertIn('Shapes loom around you.', prompt, 'the bridge must contain the passages leading up to the new chapter')
            self.assertLess(
                prompt.index('Shapes loom around you.'),
                prompt.index('You descend into the tunnels.'),
                'the bridge must come before the prose of the current chapter',
            )
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

        def test_ai_cyoa_prose_context(self) -> None:
            # The prose of the current chapter is sent to the AI, with the
            # passages before it bridging the gap when a chapter has only just
            # started, as the AI is told to continue from where the prose ends.
            state = start_game('a foggy city', make_world())

            def play(narrative: str, new_chapter: bool = False) -> tuple[tuple[str, ...], tuple[str, ...]]:
                turn = make_turn(narrative, starts_new_chapter=new_chapter, chapter_title='Next' if new_chapter else None)
                res = next_turn(state, 'go', FakePlugin([ok(turn)]))
                self.assertIsNone(res.exception, f'turn unexpectedly rejected: {res.exception}')
                bridge, current = state.prose_context
                return tuple(t.turn.narrative for t in bridge), tuple(t.turn.narrative for t in current)

            self.ae(state.prose_context, ((), ()), 'a game that has not started has no prose')
            self.ae(play('one'), ((), ('one',)), 'the first chapter needs no bridge')
            self.ae(play('two'), ((), ('one', 'two')))
            self.ae(play('three'), ((), ('one', 'two', 'three')))
            self.ae(play('four'), ((), ('one', 'two', 'three', 'four')), 'the bridge must not reach back within a chapter')
            self.ae(play('five', new_chapter=True), (('three', 'four'), ('five',)), 'a chapter that has just started must be bridged')
            self.ae(play('six'), (('four',), ('five', 'six')), 'the bridge must shrink as the new chapter grows')
            self.ae(play('seven'), ((), ('five', 'six', 'seven')), 'the bridge must go away once the chapter can stand on its own')
            self.ae(play('eight', new_chapter=True), (('six', 'seven'), ('eight',)))

        def test_ai_cyoa_interesting_event_pays_off_threads(self) -> None:
            # The AI is told to spring a surprise, but the summary already
            # holds the threads it foreshadowed itself, so it is pointed at
            # them rather than left to invent something unrelated.
            state = start_game('a foggy city', make_world())
            fake = FakePlugin([ok(make_turn('You awaken in the mist.', 'awoke')), ok(make_turn('A door opens.'))])
            next_turn(state, '', fake)
            self.ae(state.current_summary.upcoming_events, ('The mist thickens.',))
            next_turn(state, '', fake, interesting_event=True)
            prompt = fake.calls[1][0]
            self.assertIn('something unexpected', prompt)
            self.assertIn('paying off one of these unresolved threads', prompt)
            self.assertIn('- The mist thickens.', prompt, 'the unresolved threads must be listed for the AI to choose from')

            # With no threads open there is nothing to pay off and the AI must
            # not be sent an empty list to work from
            state = start_game('a foggy city', make_world())
            fake = FakePlugin([ok(make_turn('You awaken.')._replace(summary_update=make_update(upcoming_events=()))), ok(make_turn('A door opens.'))])
            next_turn(state, '', fake)
            self.ae(state.current_summary.upcoming_events, ())
            next_turn(state, '', fake, interesting_event=True)
            prompt = fake.calls[1][0]
            self.assertIn('something unexpected', prompt)
            self.assertNotIn('unresolved threads', prompt)

        def test_ai_cyoa_quick_actions(self) -> None:
            # The AI is asked for one action of each requested kind, rather
            # than for three "distinct" actions, which gets three variations
            # on the single obvious move.
            state = start_game('a foggy city', make_world())
            res = next_turn(state, '', FakePlugin([ok(make_turn('You awaken.'))]))
            self.assertIsNone(res.exception)
            instructions = turn_instructions(state)
            for group in REQUESTED_QUICK_ACTION_KINDS:
                for kind in group:
                    self.assertIn(f'"{kind.value}"', instructions, 'every requested kind of action must be named in the instructions')
                    self.assertIn(QUICK_ACTION_KIND_DESCRIPTIONS[kind], instructions, 'the AI must be told what each kind of action means')
            self.ae(state.turns[-1].turn.quick_actions[0].kind, QuickActionKind.cautious)
            self.ae(quick_action_kind_name(QuickActionKind.other), '', 'the catch-all kind must have no name to show the player')
            self.assertTrue(all(quick_action_kind_name(k) for k in QuickActionKind if k is not QuickActionKind.other))

            def selected(*actions: str | QuickAction) -> tuple[tuple[str, str], ...]:
                return tuple((a.text, a.kind.value) for a in selected_quick_actions(make_actions(*actions)))

            # Blanks and duplicates are discarded and the text is stripped
            self.ae(selected(' Run ', 'Run', '', '\n', 'RUN'), (('Run', 'other'),))
            # An action of every kind offered is preferred over the first few
            cautious = QuickAction('Wait for them to pass', QuickActionKind.cautious)
            bold = QuickAction('Kick the door in', QuickActionKind.bold)
            bold2 = QuickAction('Kick the window in', QuickActionKind.bold)
            social = QuickAction('Ask them who they are', QuickActionKind.social)
            self.ae(
                selected(bold, bold2, cautious, social),
                (('Kick the door in', 'bold'), ('Wait for them to pass', 'cautious'), ('Ask them who they are', 'social')),
                'when the AI offers more actions than are shown, one of each kind must be preferred',
            )
            self.ae(
                selected(cautious, bold, social, QuickAction('Search the desk', QuickActionKind.investigate)),
                (('Wait for them to pass', 'cautious'), ('Kick the door in', 'bold'), ('Ask them who they are', 'social')),
                'the order the AI put the actions in must be kept',
            )
            self.ae(
                selected(bold, bold2, QuickAction('Kick the wall in', QuickActionKind.bold), 'Something else'),
                (('Kick the door in', 'bold'), ('Kick the window in', 'bold'), ('Something else', 'other')),
                'with fewer kinds than actions to show, the leftover slots must be filled in the order the AI gave',
            )

        def test_ai_cyoa_turn_validation(self) -> None:
            def played(turn: StoryTurn, state: GameState | None = None) -> tuple[GameState, StructuredOutputResult]:
                state = state or start_game('a foggy city', make_world())
                return state, next_turn(state, 'go', FakePlugin([ok(turn)]))

            def rejected(turn: StoryTurn) -> str:
                state, res = played(turn)
                self.assertIsInstance(res.exception, InvalidAIResponse)
                self.assertIsNone(res.data)
                self.ae(res.error_details, '{"raw": "json"}', 'the raw response must be reported for an unusable turn')
                self.ae(state.turns, [], 'an unusable turn must not modify the game state')
                return str(res.exception)

            def accepted(turn: StoryTurn, state: GameState | None = None) -> TurnRecord:
                state, res = played(turn, state)
                self.assertIsNone(res.exception, f'turn unexpectedly rejected: {res.exception}')
                ans = state.turns[-1]
                self.assertIs(res.data, ans.turn, 'the validated turn must be returned as well as stored')
                return ans

            # A schema conforming but unusable response must be reported as an error
            self.assertIn('empty passage', rejected(make_turn('   \n  ')))
            self.assertIn('quick actions', rejected(make_turn('x')._replace(quick_actions=())))
            self.assertIn('quick actions', rejected(make_turn('x')._replace(quick_actions=make_actions(' ', '\n'))))
            state = start_game('a foggy city', make_world())
            res = next_turn(state, 'go', FakePlugin([StructuredOutputResult(data=None, raw='{}')]))
            self.assertIsInstance(res.exception, InvalidAIResponse, 'a result with neither data nor an exception must be an error')
            self.ae(state.turns, [])

            # Text fields are stripped and quick actions are deduplicated and truncated to three
            turn = accepted(
                make_turn(' You awaken. ')._replace(
                    quick_actions=make_actions(' Run ', 'Run', 'Hide', '', 'Shout', 'Wait'),
                    scene_description='  A misty street.  ',
                    chapter_title='   ',
                )
            ).turn
            self.ae(turn.narrative, 'You awaken.')
            self.ae(turn.quick_actions, make_actions('Run', 'Hide', 'Shout'))
            self.ae(turn.scene_description, 'A misty street.')
            self.assertIsNone(turn.chapter_title, 'a blank chapter title must be normalized to null')
            # A missing scene description must not fail an otherwise good turn
            self.ae(accepted(make_turn('x')._replace(scene_description=' ')).turn.scene_description, '')
            # Nor must too few quick actions: they are a convenience, the passage of prose is what the player paid for
            self.ae(
                accepted(make_turn('x')._replace(quick_actions=make_actions('Look', '  ', 'look'))).turn.quick_actions,
                make_actions('Look'),
                'a turn with a single usable quick action must be kept',
            )

            # An unrepairable summary must fail the turn
            def with_summary(summary: StorySummary) -> GameState:
                state = start_game('a foggy city', make_world())
                state.turns.append(TurnRecord(player_input='', raw_response='', turn=make_turn('x'), summary=summary, chapter=0))
                return state

            empty = StorySummary(world='', major_events=(), characters=(), current_situation='', upcoming_events=())
            state = with_summary(empty)
            res = next_turn(state, 'go', FakePlugin([ok(make_turn('y')._replace(summary_update=make_update()._replace(current_situation='')))]))
            self.assertIsInstance(res.exception, InvalidAIResponse)
            self.assertIn('world', str(res.exception))
            self.ae(len(state.turns), 1, 'an unusable turn must not modify the game state')
            state = with_summary(empty._replace(world='A city lost in mist.'))
            res = next_turn(state, 'go', FakePlugin([ok(make_turn('y')._replace(summary_update=make_update()._replace(current_situation='')))]))
            self.assertIsInstance(res.exception, InvalidAIResponse)
            self.assertIn('current situation', str(res.exception))
            state = with_summary(empty._replace(world='A city lost in mist.', current_situation='In the mist.'))
            res = next_turn(state, 'go', FakePlugin([ok(make_turn('y'))]))
            self.assertIsInstance(res.exception, InvalidAIResponse)
            self.assertIn('no characters', str(res.exception), 'an update that leaves the story with no cast at all must fail the turn')

        def test_ai_cyoa_summary_updates(self) -> None:
            state = start_game('a foggy city', make_world())
            initial = state.current_summary
            ada = initial.characters[0]

            def play(update: SummaryUpdate) -> StorySummary:
                res = next_turn(state, 'go', FakePlugin([ok(make_turn('x')._replace(summary_update=update))]))
                self.assertIsNone(res.exception, f'turn unexpectedly rejected: {res.exception}')
                return state.current_summary

            # Everything the update does not mention is carried over from the previous summary
            s = play(make_update('awoke'))
            self.ae(s.world, initial.world, 'an empty world must leave the description of the world unchanged')
            self.ae(s.current_situation, 'In the mist.')
            self.ae(s.major_events, ('awoke',))
            self.ae(s.upcoming_events, ('The mist thickens.',))
            self.ae(
                s.characters,
                (ada._replace(current_state='lost in the mist'),),
                'the fields an update leaves empty must keep the values the character already has',
            )

            # Major events accumulate rather than being re-sent, and are not duplicated
            self.ae(play(make_update('saw shapes')).major_events, ('awoke', 'saw shapes'))
            self.ae(play(make_update('saw shapes')).major_events, ('awoke', 'saw shapes'), 'an event already in the summary must not be added twice')
            self.ae(play(make_update()).major_events, ('awoke', 'saw shapes'), 'a turn in which nothing important happens must not erase the story memory')

            # A character the update says nothing about is left exactly as they were
            s = play(make_update(character_updates=()))
            self.ae(s.characters, (ada._replace(current_state='lost in the mist'),), 'a character the AI does not mention must keep their state')

            # The world and a character's durable fields change only when the update says so
            s = play(
                make_update(
                    world='The mist has lifted.',
                    character_updates=(CharacterDelta(id=PROTAGONIST_ID, current_state='blinking in the sun', description='a stubborn engineer, now scarred'),),
                )
            )
            self.ae(s.world, 'The mist has lifted.')
            self.ae(s.characters[0].description, 'a stubborn engineer, now scarred')
            self.ae(s.characters[0].backstory, ada.backstory, 'a description that changed must not drag the rest of the character with it')
            self.ae(s.characters[0].current_state, 'blinking in the sun')

            # A new character is added at the end of the cast, one with nothing durable known about them is dropped
            s = play(
                make_update(
                    character_updates=(
                        CharacterDelta(id='marlo', current_state='waiting at the tunnel mouth', name='Marlo', description='a mist-runner', backstory='a local'),
                        CharacterDelta(id='ghost', current_state='watching from the roof'),
                        CharacterDelta(id='', current_state='hiding', name='Nameless friend'),
                    )
                )
            )
            self.ae(tuple(c.name for c in s.characters), ('Ada', 'Marlo'))
            self.ae(s.characters[1].relationships, '', 'a new character who has not met anyone yet must be kept')

            # The list of upcoming events replaces the previous one, so that resolved threads can leave the summary
            self.ae(play(make_update(upcoming_events=('Marlo returns', ' Marlo returns '))).upcoming_events, ('Marlo returns',))
            self.ae(play(make_update(upcoming_events=())).upcoming_events, (), 'the last unresolved plot thread must be able to leave the summary')

            # The major events are capped, with the AI asked to consolidate the older ones before the cap drops them
            s = play(make_update(*(f'event {i}' for i in range(MAX_MAJOR_EVENTS + 5))))
            self.ae(len(s.major_events), MAX_MAJOR_EVENTS, 'the list of major events must be bounded')
            self.ae(s.major_events[-1], f'event {MAX_MAJOR_EVENTS + 4}')
            self.assertNotIn('awoke', s.major_events, 'the oldest events must be the ones dropped when the cap is exceeded')
            s = play(make_update('and then this happened', consolidated_major_events=('everything up to now',)))
            self.ae(
                s.major_events,
                ('everything up to now', 'and then this happened'),
                'a consolidated list must replace the events already in the summary, with this turn appended to it',
            )

        def test_ai_cyoa_rewind(self) -> None:
            state = start_game('brief', make_world())
            fake = FakePlugin([
                ok(make_turn('One.', 'one')),
                ok(make_turn('Two.', 'two')),
                ok(make_turn('Three.', 'three', starts_new_chapter=True, chapter_title='Part II')),
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
            state = start_game('a foggy city', make_world(), art_style='anime')
            fake = FakePlugin([
                ok(make_turn('You awaken.', 'awoke')),
                ok(make_turn('You escape.', 'escaped', starts_new_chapter=True, chapter_title='Freedom')),
            ])
            next_turn(state, '', fake)
            next_turn(state, 'run', fake)
            restored = deserialize_game(serialize_game(state))
            self.ae(state, restored)
            self.ae(restored.current_chapter, 1)
            self.ae(restored.art_style, 'anime')
            self.assertRaises(ValueError, deserialize_game, json.dumps({'version': GAME_SERIALIZATION_VERSION + 1, 'game': {}}))
            self.assertRaises(ValueError, deserialize_game, json.dumps({'version': 0, 'game': {}}))
            self.assertRaises(ValueError, deserialize_game, json.dumps({'game': {}}))
            self.assertRaises(ValueError, deserialize_game, json.dumps(['not', 'a', 'game']))
            bad = json.loads(serialize_game(state))
            bad['game']['character_index'] = len(state.world.characters)
            with self.assertRaises(ValueError, msg='an out of range played character index must be rejected'):
                deserialize_game(json.dumps(bad))
            self.assertRaises(ValueError, start_game, 'brief', make_world(), len(make_world().characters))

            # Games saved before characters had a current_state must still load
            data = json.loads(serialize_game(state))
            for record in data['game']['turns']:
                for c in record['summary']['characters']:
                    del c['current_state']
            restored = deserialize_game(json.dumps(data))
            self.ae(
                tuple(c.current_state for c in restored.current_summary.characters),
                ('',) * len(restored.current_summary.characters),
                'a character saved without a current_state must load with an empty one',
            )

        def test_ai_cyoa_serialization_migration(self) -> None:
            state = start_game('a foggy city', make_world(), art_style='anime')
            fake = FakePlugin([
                ok(make_turn('You awaken.', 'awoke')),
                ok(make_turn('You escape.', 'escaped', starts_new_chapter=True, chapter_title='Freedom')),
            ])
            next_turn(state, '', fake)
            next_turn(state, 'run', fake)

            def as_v3() -> str:
                # A game as version 3 serialized it: the quick actions as bare
                # strings, without the kind of approach each of them takes.
                data = json.loads(serialize_game(state))
                data['version'] = 3
                for record in data['game']['turns']:
                    record['turn']['quick_actions'] = [a['text'] for a in record['turn']['quick_actions']]
                return json.dumps(data)

            restored = deserialize_game(as_v3())
            self.ae(
                [tuple(a.text for a in t.turn.quick_actions) for t in restored.turns],
                [tuple(a.text for a in t.turn.quick_actions) for t in state.turns],
                'migration must keep the text of every quick action of every turn',
            )
            self.ae(
                {a.kind for t in restored.turns for a in t.turn.quick_actions},
                {QuickActionKind.other},
                'a quick action saved without a kind must get the catch-all kind',
            )

            def as_v2() -> str:
                # A game as version 2 serialized it: the whole story summary,
                # returned by the AI on every turn, stored inside the turn.
                data = json.loads(serialize_game(state))
                data['version'] = 2
                for record in data['game']['turns']:
                    record['turn']['updated_summary'] = record.pop('summary')
                    del record['turn']['summary_update']
                return json.dumps(data)

            restored = deserialize_game(as_v2())
            self.ae([t.summary for t in restored.turns], [t.summary for t in state.turns], 'migration must move the stored summary onto the turn record')
            self.ae(restored.current_summary, state.current_summary)
            self.ae(
                updated_summary(restored.turns[0].turn.summary_update, initial_summary(restored.world, restored.character)),
                restored.turns[0].summary,
                'the update synthesized for a migrated turn must merge to exactly the summary that was stored',
            )

            def as_v1(played: PlayerCharacter) -> str:
                # A game as version 1 serialized it: a copy of the played
                # character instead of its index, characters without ids and
                # the instructions and prompt of every turn.
                data = json.loads(serialize_game(state))
                data['version'] = 1
                game = data['game']
                del game['character_index']
                game['character'] = as_jsonable(played, spec_for_class(PlayerCharacter))
                for record in game['turns']:
                    record['instructions'] = 'the system prompt of this turn'
                    record['prompt'] = 'the prompt of this turn, with the whole transcript embedded in it'
                    record['turn']['updated_summary'] = record.pop('summary')
                    del record['turn']['summary_update']
                    for c in record['turn']['updated_summary']['characters']:
                        del c['id']
                return json.dumps(data)

            restored = deserialize_game(as_v1(state.character))
            self.ae(restored.character_index, 0)
            self.ae(restored.character, state.character)
            self.ae(restored.world, state.world)
            self.ae(restored.art_style, 'anime')
            self.ae(restored.current_chapter, 1)
            self.ae(len(restored.turns), len(state.turns))
            self.ae([(t.instructions, t.prompt) for t in restored.turns], [('', '')] * len(state.turns), 'migration must drop the recorded prompts')
            self.ae(
                tuple(c.id for c in restored.current_summary.characters),
                (PROTAGONIST_ID,),
                'migration must give the played character a stable id in the summary',
            )
            self.ae(
                tuple(c.id for c in restored.turns[0].summary.characters),
                (PROTAGONIST_ID,),
                'every stored summary must be migrated, not just the last one',
            )

            # An edited played character must still be linked to its world entry by name
            restored = deserialize_game(as_v1(state.character._replace(description='an edited engineer')))
            self.ae(restored.character_index, 0)
            self.ae(restored.character, state.world.characters[0], 'the world entry must win over the stale copy of the played character')

            # A played character that is no longer part of the world must not be lost
            restored = deserialize_game(as_v1(state.character._replace(name='Zed')))
            self.ae(restored.character_index, len(state.world.characters))
            self.ae(restored.character.name, 'Zed')
            self.ae(len(restored.world.characters), len(state.world.characters) + 1)

        def test_ai_cyoa_character_ids(self) -> None:
            self.ae(character_id_for_name('  The Stranger '), 'the-stranger')
            self.ae(character_id_for_name('Ada Lovelace-Smith'), 'ada-lovelace-smith')
            self.ae(character_id_for_name(' ?! '), 'character')
            self.ae(character_id_for_name('x' * 40), 'x' * 32)
            state = start_game('a foggy city', make_world())
            self.ae(tuple(c.id for c in state.current_summary.characters), (PROTAGONIST_ID,))

            def play(*updates: CharacterDelta) -> tuple[tuple[str, str], ...]:
                turn = make_turn('x')._replace(summary_update=make_update('awoke', character_updates=updates))
                res = next_turn(state, 'go', FakePlugin([ok(turn)]))
                self.assertIsNone(res.exception, f'turn unexpectedly rejected: {res.exception}')
                return tuple((c.id, c.name) for c in state.current_summary.characters)

            # A character the AI introduces without an id gets one derived from their name
            self.ae(
                play(
                    CharacterDelta(id=PROTAGONIST_ID, current_state='alone'),
                    CharacterDelta(id='', current_state='watching Ada', name='the stranger', description='a hooded figure', backstory='unknown'),
                ),
                ((PROTAGONIST_ID, 'Ada'), ('the-stranger', 'the stranger')),
            )

            # Renaming a character while carrying their id forward must update their entry, not fork it
            self.ae(
                play(CharacterDelta(id='the-stranger', current_state='guiding Ada', name='Marlo')),
                ((PROTAGONIST_ID, 'Ada'), ('the-stranger', 'Marlo')),
                'a renamed character must keep their id and their entry',
            )
            self.ae(state.current_summary.characters[1].description, 'a hooded figure', 'renaming a character must not disturb the rest of their entry')

            # An id the AI invents for a character that already has one must not fork them either
            self.ae(
                play(CharacterDelta(id='marlo', current_state='still guiding Ada', name='Marlo')),
                ((PROTAGONIST_ID, 'Ada'), ('the-stranger', 'Marlo')),
                'a character matched by name must keep the id they already have',
            )

            # A second update for a character already updated this turn must be ignored
            self.ae(
                play(
                    CharacterDelta(id='the-stranger', current_state='at the gate'),
                    CharacterDelta(id='the-stranger', current_state='somewhere else entirely', name='Not Marlo'),
                ),
                ((PROTAGONIST_ID, 'Ada'), ('the-stranger', 'Marlo')),
            )
            self.ae(state.current_summary.characters[1].current_state, 'at the gate', 'the first update for a character must win')

            # A new character whose invented id is already taken must not be merged into the character that has it
            self.ae(
                play(CharacterDelta(id='', current_state='still hooded', name='The Stranger', description='a different hooded figure', backstory='unknown')),
                ((PROTAGONIST_ID, 'Ada'), ('the-stranger', 'Marlo'), ('the-stranger-2', 'The Stranger')),
            )

        def test_ai_cyoa_prompts_are_not_stored(self) -> None:
            from unittest.mock import patch

            def play_two_turns() -> GameState:
                state = start_game('a foggy city', make_world())
                fake = FakePlugin([ok(make_turn('You awaken in the mist.', 'awoke')), ok(make_turn('Shapes loom.', 'awoke', 'loomed'))])
                next_turn(state, '', fake)
                next_turn(state, 'look around', fake)
                return state

            state = play_two_turns()
            raw = serialize_game(state)
            records = json.loads(raw)['game']['turns']
            self.assertNotIn('You awaken in the mist.', json.dumps(records[1]), 'the prose of a turn must not be repeated in the record of every later turn')
            self.assertNotIn('The prose of the current chapter so far', raw, 'the prompt sent to the AI must not be stored')
            self.ae([(t.instructions, t.prompt) for t in state.turns], [('', '')] * 2)
            self.ae(deserialize_game(raw), state)

            # The debug flag records exactly what was sent, at the cost of size
            with patch('calibre.ai.cyoa.STORE_PROMPTS_IN_TURN_RECORDS', True):
                recorded = play_two_turns()
            self.assertIn('novelist', recorded.turns[0].instructions)
            self.assertIn('You awaken in the mist.', recorded.turns[1].prompt)
            self.assertGreater(len(serialize_game(recorded)), len(raw))
            self.ae(deserialize_game(serialize_game(recorded)), recorded, 'a game with the prompts recorded must still round trip')

            # Both are reconstructable from the state, which is why they need not be stored
            rewind(state)  # back to the state the second turn was played from
            self.ae(turn_instructions(state), recorded.turns[1].instructions)
            self.ae(turn_prompt(state, 'look around'), recorded.turns[1].prompt)

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestCYOA)


# }}}


if __name__ == '__main__':
    develop()
