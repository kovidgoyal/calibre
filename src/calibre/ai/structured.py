#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

# Convert Python classes with type annotations into JSON schemas/TypeScript
# interfaces and use them to get structured (JSON) output from AI models.

import enum
import json
import re
import types
from collections.abc import Callable, Iterable, Iterator
from enum import Enum, auto
from typing import TYPE_CHECKING, Annotated, Any, Literal, NamedTuple, Union, get_args, get_origin, get_type_hints
from urllib.error import HTTPError, URLError

from calibre.ai import ChatMessage, ChatMessageType, ChatResponse, StructuredOutputResult

if TYPE_CHECKING:
    from unittest.suite import TestSuite
else:
    TestSuite = object


class Doc(str):
    # A description string for schema classes and enums that survives
    # optimized Python builds (python -OO strips docstrings). Assign as an
    # unannotated class attribute: doc = Doc("Human-readable description.")
    # Being a descriptor prevents Enum from treating it as a member.
    __slots__ = ()

    def __get__(self, obj: object, objtype: type | None = None) -> Doc:
        return self


class Kind(Enum):
    string = auto()
    integer = auto()
    number = auto()
    boolean = auto()
    enumeration = auto()
    array = auto()
    object = auto()


class TypeSpec(NamedTuple):
    kind: Kind
    nullable: bool = False
    description: str = ''
    items: TypeSpec | None = None  # the item type for arrays
    fields: tuple[FieldSpec, ...] = ()  # the fields for objects
    choices: tuple[str | int, ...] = ()  # allowed values for Enum subclasses and Literal
    cls: type | None = None  # class used to instantiate parsed values
    name: str = ''  # class name, used as the TypeScript interface name


class FieldSpec(NamedTuple):
    name: str
    spec: TypeSpec
    has_default: bool = False
    default: Any = None


def class_doc(cls: type) -> str:
    ans = ''
    for v in cls.__dict__.values():
        if type(v) is Doc:
            ans += str(v) + '\n'
    return ans.rstrip()


def defaults_for_class(cls: type) -> dict[str, Any]:
    import dataclasses

    if dataclasses.is_dataclass(cls):
        ans = {}
        for f in dataclasses.fields(cls):
            if f.default is not dataclasses.MISSING:
                ans[f.name] = f.default
            elif f.default_factory is not dataclasses.MISSING:
                ans[f.name] = f.default_factory()
        return ans
    fd = getattr(cls, '_field_defaults', None)
    if fd is not None:  # NamedTuple
        return dict(fd)
    return {name: getattr(cls, name) for name in getattr(cls, '__annotations__', {}) if hasattr(cls, name)}


def is_schema_class(t: Any) -> bool:  # noqa: ANN401
    return isinstance(t, type) and not issubclass(t, enum.Enum) and bool(getattr(t, '__annotations__', None))


def spec_for_type(t: Any, path: str, seen: frozenset[type]) -> TypeSpec:  # noqa: ANN401
    description = ''
    if get_origin(t) is Annotated:
        args = get_args(t)
        t = args[0]
        description = next((m for m in args[1:] if isinstance(m, str)), '')

    def finish(spec: TypeSpec) -> TypeSpec:
        return spec._replace(description=description) if description else spec

    origin = get_origin(t)
    if origin is Union or origin is types.UnionType:
        args = get_args(t)
        non_none = tuple(a for a in args if a is not type(None))
        if len(non_none) != 1 or len(non_none) == len(args):
            raise ValueError(f'{path}: only unions of a single type with None are supported')
        return finish(spec_for_type(non_none[0], path, seen)._replace(nullable=True))
    if origin is Literal:
        choices = get_args(t)
        if not choices or not (all(isinstance(c, str) for c in choices) or all(isinstance(c, int) and not isinstance(c, bool) for c in choices)):
            raise ValueError(f'{path}: Literal values must be all strings or all integers')
        return finish(TypeSpec(kind=Kind.enumeration, choices=choices))
    if origin is list or origin is tuple:
        args = get_args(t)
        if origin is tuple:
            if len(args) != 2 or args[1] is not Ellipsis:
                raise ValueError(f'{path}: only homogeneous tuples of the form tuple[T, ...] are supported')
        elif len(args) != 1:
            raise ValueError(f'{path}: list must be parameterized with a single item type')
        return finish(TypeSpec(kind=Kind.array, items=spec_for_type(args[0], path + '[]', seen), cls=origin))
    if origin is dict or t is dict:
        raise ValueError(f'{path}: dict is not supported as objects with arbitrary keys cannot be expressed in strict JSON schemas, use a nested class instead')
    if t is list or t is tuple:
        raise ValueError(f'{path}: bare {t.__name__} is not supported, parameterize it with an item type')
    if t is str:
        return finish(TypeSpec(kind=Kind.string))
    if t is bool:
        return finish(TypeSpec(kind=Kind.boolean))
    if t is int:
        return finish(TypeSpec(kind=Kind.integer))
    if t is float:
        return finish(TypeSpec(kind=Kind.number))
    if isinstance(t, type) and issubclass(t, enum.Enum):
        choices = tuple(m.value for m in t)
        if not choices or not (all(isinstance(c, str) for c in choices) or all(isinstance(c, int) and not isinstance(c, bool) for c in choices)):
            raise ValueError(f'{path}: Enum values must be all strings or all integers')
        return finish(TypeSpec(kind=Kind.enumeration, choices=choices, cls=t, name=t.__name__, description=class_doc(t)))
    if is_schema_class(t):
        return finish(spec_for_class(t, seen))
    raise ValueError(f'{path}: unsupported type annotation: {t!r}')


def spec_for_class(cls: type, seen: frozenset[type] = frozenset()) -> TypeSpec:
    if not is_schema_class(cls):
        raise ValueError(f'{cls!r} is not a class with annotated fields')
    if cls in seen:
        raise ValueError(f'Recursive schema classes are not supported: {cls.__name__}')
    seen |= {cls}
    defaults = defaults_for_class(cls)
    # localns allows string self-references like 'MyClass | None' to resolve,
    # so they are reported as recursive rather than as undefined names
    hints = get_type_hints(cls, include_extras=True, localns={cls.__name__: cls})
    fields = tuple(
        FieldSpec(name=name, spec=spec_for_type(t, f'{cls.__name__}.{name}', seen), has_default=name in defaults, default=defaults.get(name))
        for name, t in hints.items()
    )
    if not fields:
        raise ValueError(f'{cls.__name__} has no annotated fields')
    return TypeSpec(kind=Kind.object, description=class_doc(cls), fields=fields, cls=cls, name=cls.__name__)


def enum_json_type(choices: tuple[str | int, ...]) -> str:
    return 'string' if isinstance(choices[0], str) else 'integer'


def spec_as_strict_json_schema(spec: TypeSpec) -> dict[str, Any]:
    ans: dict[str, Any] = {}
    match spec.kind:
        case Kind.string | Kind.integer | Kind.number | Kind.boolean:
            ans['type'] = spec.kind.name
        case Kind.enumeration:
            ans['type'] = enum_json_type(spec.choices)
            ans['enum'] = list(spec.choices)
        case Kind.array:
            assert spec.items is not None
            ans['type'] = 'array'
            ans['items'] = spec_as_strict_json_schema(spec.items)
        case Kind.object:
            ans['type'] = 'object'
            ans['properties'] = {f.name: spec_as_strict_json_schema(f.spec) for f in spec.fields}
            ans['required'] = [f.name for f in spec.fields]
            ans['additionalProperties'] = False
    if spec.description:
        ans['description'] = spec.description
    if spec.nullable:
        if 'enum' in ans:
            ans['enum'] = ans['enum'] + [None]
            ans['type'] = [ans['type'], 'null']
        elif spec.kind in (Kind.array, Kind.object):
            description = ans.pop('description', '')
            ans = {'anyOf': [ans, {'type': 'null'}]}
            if description:
                ans['description'] = description
        else:
            ans['type'] = [ans['type'], 'null']
    return ans


def strict_json_schema(schema: type) -> dict[str, Any]:
    # A JSON schema suitable for strict structured output modes:
    # additionalProperties is false and all properties are required, with
    # optionality expressed as nullability.
    return spec_as_strict_json_schema(spec_for_class(schema))


def spec_as_gemini_schema(spec: TypeSpec) -> dict[str, Any]:
    # See https://ai.google.dev/api/caching#Schema (OpenAPI 3 subset).
    # additionalProperties is not supported and nullability is expressed
    # via the nullable property.
    ans: dict[str, Any] = {}
    match spec.kind:
        case Kind.string | Kind.integer | Kind.number | Kind.boolean:
            ans['type'] = spec.kind.name
        case Kind.enumeration:
            ans['type'] = enum_json_type(spec.choices)
            if ans['type'] == 'string':
                ans['enum'] = list(spec.choices)
            elif spec.description:  # enum is only supported for strings
                ans['description'] = spec.description + ' Allowed values: ' + ', '.join(map(str, spec.choices))
            else:
                ans['description'] = 'Allowed values: ' + ', '.join(map(str, spec.choices))
        case Kind.array:
            assert spec.items is not None
            ans['type'] = 'array'
            ans['items'] = spec_as_gemini_schema(spec.items)
        case Kind.object:
            ans['type'] = 'object'
            ans['properties'] = {f.name: spec_as_gemini_schema(f.spec) for f in spec.fields}
            ans['required'] = [f.name for f in spec.fields]
            ans['propertyOrdering'] = [f.name for f in spec.fields]
    if spec.description and 'description' not in ans:
        ans['description'] = spec.description
    if spec.nullable:
        ans['nullable'] = True
    return ans


def gemini_response_schema(schema: type) -> dict[str, Any]:
    return spec_as_gemini_schema(spec_for_class(schema))


def typescript_interface(schema: type) -> str:
    # Render the schema class and all classes nested inside it as TypeScript
    # interfaces, with descriptions as comments. Referenced interfaces come
    # first and the schema class itself is last.
    interfaces: dict[str, str] = {}

    def ts_type(spec: TypeSpec) -> str:
        match spec.kind:
            case Kind.string:
                base = 'string'
            case Kind.integer | Kind.number:
                base = 'number'
            case Kind.boolean:
                base = 'boolean'
            case Kind.enumeration:
                base = ' | '.join(json.dumps(c) for c in spec.choices)
            case Kind.array:
                assert spec.items is not None
                it = ts_type(spec.items)
                base = f'Array<{it}>' if ' ' in it else f'{it}[]'
            case Kind.object:
                render_interface(spec)
                base = spec.name
        if spec.nullable:
            base += ' | null'
        return base

    def comment_lines(text: str, indent: str = '') -> Iterator[str]:
        for line in text.splitlines():
            yield f'{indent}// {line}'

    def render_interface(spec: TypeSpec) -> None:
        if spec.name in interfaces:
            return
        lines: list[str] = []
        if spec.description:
            lines.extend(comment_lines(spec.description))
        lines.append(f'interface {spec.name} {{')
        for f in spec.fields:
            ft = ts_type(f.spec)  # render any nested interfaces first
            if f.spec.description:
                lines.extend(comment_lines(f.spec.description, '  '))
            lines.append(f'  {f.name}: {ft};')
        lines.append('}')
        interfaces[spec.name] = '\n'.join(lines)

    render_interface(spec_for_class(schema))
    return '\n\n'.join(interfaces.values())


def strip_code_fences(text: str) -> str:
    # Models using the prompt based fallback sometimes wrap their JSON in
    # markdown code fences despite instructions not to. If a fenced block is
    # present use its contents, otherwise the full text.
    text = text.strip()
    m = re.search(r'```[a-zA-Z0-9_-]*[ \t]*\n(.*?)\n?[ \t]*```', text, re.DOTALL)
    if m is not None:
        return m.group(1).strip()
    return text


def instantiate(value: Any, spec: TypeSpec, path: str) -> Any:  # noqa: ANN401
    def type_error(expected: str) -> ValueError:
        return ValueError(f'{path}: expected {expected}, got {type(value).__name__}')

    if value is None:
        if spec.nullable:
            return None
        raise type_error(spec.kind.name)
    match spec.kind:
        case Kind.string:
            if not isinstance(value, str):
                raise type_error('string')
            return value
        case Kind.integer:
            if isinstance(value, bool) or not isinstance(value, int):
                raise type_error('integer')
            return value
        case Kind.number:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise type_error('number')
            return float(value)
        case Kind.boolean:
            if not isinstance(value, bool):
                raise type_error('boolean')
            return value
        case Kind.enumeration:
            if value not in spec.choices:
                raise ValueError(f'{path}: {value!r} is not one of the allowed values: {", ".join(map(repr, spec.choices))}')
            return value if spec.cls is None else spec.cls(value)
        case Kind.array:
            if not isinstance(value, list):
                raise type_error('array')
            assert spec.items is not None
            items = tuple(instantiate(v, spec.items, f'{path}[{i}]') for i, v in enumerate(value))
            return items if spec.cls is tuple else list(items)
        case Kind.object:
            if not isinstance(value, dict):
                raise type_error('object')
            assert spec.cls is not None
            kwargs = {}
            for f in spec.fields:
                if f.name in value:
                    kwargs[f.name] = instantiate(value[f.name], f.spec, f'{path}.{f.name}')
                elif f.has_default:
                    kwargs[f.name] = f.default
                elif f.spec.nullable:
                    kwargs[f.name] = None
                else:
                    raise ValueError(f'{path}: missing required key: {f.name}')
            return spec.cls(**kwargs)
    raise AssertionError(f'Unknown kind: {spec.kind}')  # pragma: no cover


def parse_structured_response(text: str, schema: type) -> Any:  # noqa: ANN401
    # Parse the text returned by an AI model as JSON and return an instance
    # of the schema class, raising ValueError if the response does not
    # conform to the schema.
    raw = strip_code_fences(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f'The AI model did not return valid JSON, with error: {e}. Returned text: {text[:4096]!r}') from e
    spec = spec_for_class(schema)
    return instantiate(data, spec, schema.__name__)


def structured_output_from_chat(responses: Iterable[ChatResponse], schema: type, plugin_name: str) -> StructuredOutputResult:
    # Accumulate a chat session whose text content is JSON conforming to
    # schema into a StructuredOutputResult.
    content = ''
    metadata = ChatResponse()
    for r in responses:
        if r.exception is not None:
            return StructuredOutputResult(exception=r.exception, error_details=r.error_details, plugin_name=plugin_name)
        if r.has_metadata:
            metadata = r
        content += r.content
    data = parse_structured_response(content, schema)
    return StructuredOutputResult(
        data=data,
        raw=strip_code_fences(content),
        cost=metadata.cost,
        currency=metadata.currency,
        provider=metadata.provider,
        model=metadata.model,
        plugin_name=plugin_name or metadata.plugin_name,
    )


def system_prompt_for_schema(schema: type, instructions: str = '') -> str:
    # Deliberately not translated as it is sent to AI models, which work best
    # with English instructions.
    parts = []
    if instructions:
        parts.append(instructions)
    parts.append(
        'You must respond with only valid JSON that conforms to the TypeScript interface'
        f' named {schema.__name__} defined below. Do not include markdown formatting, code fences,'
        ' explanations or any other text in your response, only the JSON object itself.'
    )
    parts.append(typescript_interface(schema))
    return '\n\n'.join(parts)


def structured_output_via_prompt(
    text_chat: Callable[[Iterable[ChatMessage], str], Iterator[ChatResponse]],
    prompt: str,
    schema: type,
    instructions: str = '',
    use_model: str = '',
    plugin_name: str = '',
) -> StructuredOutputResult:
    # Fallback for AI providers that have no native structured output
    # support: describe the schema as a TypeScript interface in a system
    # prompt and parse the response.
    messages = (
        ChatMessage(type=ChatMessageType.system, query=system_prompt_for_schema(schema, instructions)),
        ChatMessage(prompt),
    )
    return structured_output_from_chat(text_chat(messages, use_model), schema, plugin_name)


def structured_output_with_error_handler(func: Callable[[], StructuredOutputResult]) -> StructuredOutputResult:
    try:
        return func()
    except HTTPError as e:
        try:
            details = e.fp.read().decode('utf-8', 'replace')
        except Exception:
            details = ''
        try:
            error_json = json.loads(details)
            details = error_json.get('error', {}).get('message', details)
        except Exception:
            pass
        return StructuredOutputResult(exception=e, error_details=details)
    except URLError as e:
        return StructuredOutputResult(exception=e, error_details=f'Network error: {e.reason}')
    except Exception as e:
        import traceback

        return StructuredOutputResult(exception=e, error_details=traceback.format_exc())


def messages_for_structured_output(prompt: str, instructions: str = '') -> tuple[ChatMessage, ...]:
    # The messages used by backends with native structured output support.
    ans = (ChatMessage(prompt),)
    if instructions:
        ans = (ChatMessage(type=ChatMessageType.system, query=instructions),) + ans
    return ans


class ExampleBookInfo(NamedTuple):
    doc = Doc('Information about a printed book')
    title: Annotated[str, 'The title of the book without any subtitle']
    authors: Annotated[list[str], 'All the authors of the book']
    publication_year: Annotated[int | None, 'The year of first publication or null if unknown'] = None


def develop_structured_output(
    generate_structured_output: Callable[..., StructuredOutputResult],
    prompt: str = '',
    schema: type | None = None,
    use_model: str = '',
) -> None:
    schema = schema or ExampleBookInfo
    prompt = prompt or 'Give me the details of the novel Pride and Prejudice by Jane Austen.'
    res = generate_structured_output(prompt, schema, use_model=use_model)
    if res.exception is not None:
        raise SystemExit(str(res.exception) + (': ' + res.error_details if res.error_details else ''))
    print('Raw JSON:')
    print(res.raw)
    print()
    from pprint import pprint

    pprint(res.data)
    print(f'\nCost: {res.cost} {res.currency} Provider: {res.provider!r} Model: {res.model!r}')


def find_tests() -> TestSuite:
    import unittest

    class Mood(Enum):
        doc = Doc('The dominant emotional tone.')
        dark = 'dark'
        neutral = 'neutral'
        uplifting = 'uplifting'

    class Chapter(NamedTuple):
        doc = Doc('A single chapter of the book')
        title: Annotated[str, 'The chapter title']
        number: int

    class Book(NamedTuple):
        doc = Doc('Structured analysis of a single book.')
        title: Annotated[str, 'The full title of the book']
        subtitle: Annotated[str | None, 'The subtitle or null if the book has none']
        rating: Annotated[float, 'Overall quality from 0 (worst) to 5 (best)']
        genres: Annotated[list[str], 'Up to three genres, most specific first']
        chapters: tuple[Chapter, ...]
        mood: Annotated[Mood, 'The dominant emotional tone of the text'] = Mood.neutral
        media: Literal['ebook', 'paper', 'audio'] = 'ebook'
        is_fiction: bool = True

    class TestStructuredOutput(unittest.TestCase):
        maxDiff = None
        ae = unittest.TestCase.assertEqual

        def test_ai_structured_json_schema(self) -> None:
            s = strict_json_schema(Book)
            self.ae(s['type'], 'object')
            self.ae(s['description'], 'Structured analysis of a single book.')
            self.ae(s['required'], ['title', 'subtitle', 'rating', 'genres', 'chapters', 'mood', 'media', 'is_fiction'])
            self.assertFalse(s['additionalProperties'])
            p = s['properties']
            self.ae(p['title'], {'type': 'string', 'description': 'The full title of the book'})
            self.ae(p['subtitle']['type'], ['string', 'null'])
            self.ae(p['rating']['type'], 'number')
            self.ae(p['genres'], {'type': 'array', 'items': {'type': 'string'}, 'description': 'Up to three genres, most specific first'})
            c = p['chapters']
            self.ae(c['type'], 'array')
            self.ae(c['items']['type'], 'object')
            self.assertFalse(c['items']['additionalProperties'])
            self.ae(c['items']['required'], ['title', 'number'])
            self.ae(c['items']['properties']['number'], {'type': 'integer'})
            self.ae(p['mood']['enum'], ['dark', 'neutral', 'uplifting'])
            self.ae(p['mood']['description'], 'The dominant emotional tone of the text')
            self.ae(p['media'], {'type': 'string', 'enum': ['ebook', 'paper', 'audio']})
            self.ae(p['is_fiction'], {'type': 'boolean'})

            class N(NamedTuple):
                x: Chapter | None
                y: Mood | None

            p = strict_json_schema(N)['properties']
            self.ae(p['x']['anyOf'][1], {'type': 'null'})
            self.ae(p['x']['anyOf'][0]['type'], 'object')
            self.ae(p['y']['type'], ['string', 'null'])
            self.ae(p['y']['enum'], ['dark', 'neutral', 'uplifting', None])

        def test_ai_structured_gemini_schema(self) -> None:
            s = gemini_response_schema(Book)
            self.assertNotIn('additionalProperties', json.dumps(s))
            self.ae(s['propertyOrdering'], ['title', 'subtitle', 'rating', 'genres', 'chapters', 'mood', 'media', 'is_fiction'])
            p = s['properties']
            self.assertTrue(p['subtitle']['nullable'])
            self.ae(p['mood']['enum'], ['dark', 'neutral', 'uplifting'])
            self.ae(p['chapters']['items']['propertyOrdering'], ['title', 'number'])

            class N(NamedTuple):
                x: Literal[1, 2, 3]

            p = gemini_response_schema(N)['properties']
            self.ae(p['x']['type'], 'integer')
            self.assertNotIn('enum', p['x'])
            self.assertIn('1, 2, 3', p['x']['description'])

        def test_ai_structured_typescript(self) -> None:
            ts = typescript_interface(Book)
            self.assertLess(ts.index('interface Chapter {'), ts.index('interface Book {'), 'referenced interfaces must come before the root interface')
            self.assertIn('// Structured analysis of a single book.', ts)
            self.assertIn('  // The full title of the book\n  title: string;', ts)
            self.assertIn('  subtitle: string | null;', ts)
            self.assertIn('  rating: number;', ts)
            self.assertIn('  genres: string[];', ts)
            self.assertIn('  chapters: Chapter[];', ts)
            self.assertIn('  mood: "dark" | "neutral" | "uplifting";', ts)
            self.assertIn('  media: "ebook" | "paper" | "audio";', ts)
            self.assertIn('  is_fiction: boolean;', ts)

            class N(NamedTuple):
                x: list[str | None]

            self.assertIn('x: Array<string | null>;', typescript_interface(N))

        def test_ai_structured_unsupported_annotations(self) -> None:
            def check(t: Any, msg: str) -> None:  # noqa: ANN401
                class N(NamedTuple):
                    x: t

                with self.assertRaisesRegex(ValueError, msg):
                    strict_json_schema(N)

            check(dict[str, int], 'dict is not supported')
            check(Any, 'unsupported type annotation')
            check(list, 'parameterize it with an item type')
            check(tuple[str, int], 'homogeneous tuples')
            check(str | int, 'unions of a single type with None')

            class Empty:
                pass

            self.assertRaisesRegex(ValueError, 'not a class with annotated fields', strict_json_schema, Empty)

            class R(NamedTuple):
                x: R | None

            self.assertRaisesRegex(ValueError, 'Recursive schema classes', strict_json_schema, R)

        def test_ai_structured_parse_and_instantiate(self) -> None:
            raw = {
                'title': 'Dune',
                'subtitle': None,
                'rating': 4,
                'genres': ['scifi'],
                'chapters': [{'title': 'One', 'number': 1}],
                'mood': 'dark',
                'media': 'paper',
                'is_fiction': True,
            }
            b = parse_structured_response(json.dumps(raw), Book)
            self.ae(b.title, 'Dune')
            self.assertIsNone(b.subtitle)
            self.ae(b.rating, 4.0)
            self.assertIsInstance(b.rating, float)
            self.ae(b.chapters, (Chapter('One', 1),))
            self.assertIs(b.mood, Mood.dark)
            self.ae(b.media, 'paper')

            # missing keys allowed only for fields with defaults or nullable fields, unknown keys ignored
            del raw['mood'], raw['media'], raw['is_fiction'], raw['subtitle']
            raw['unknown_key'] = 'ignored'
            b = parse_structured_response(json.dumps(raw), Book)
            self.assertIs(b.mood, Mood.neutral)
            self.ae(b.media, 'ebook')
            self.assertIsNone(b.subtitle)
            del raw['title']
            with self.assertRaisesRegex(ValueError, 'missing required key: title'):
                parse_structured_response(json.dumps(raw), Book)

            # code fences and surrounding prose
            fenced = 'Here you go:\n```json\n' + json.dumps(raw | {'title': 'Dune'}) + '\n```\nEnjoy!'
            self.ae(parse_structured_response(fenced, Book).title, 'Dune')
            self.ae(strip_code_fences('```\n{"a": 1}\n```'), '{"a": 1}')
            self.ae(strip_code_fences('{"a": 1}'), '{"a": 1}')

            # error paths carry the path to the offending value
            raw['title'] = 'Dune'
            with self.assertRaisesRegex(ValueError, re.escape('Book.chapters[0].number: expected integer, got str')):
                parse_structured_response(json.dumps(raw | {'chapters': [{'title': 'One', 'number': 'x'}]}), Book)
            with self.assertRaisesRegex(ValueError, 'not one of the allowed values'):
                parse_structured_response(json.dumps(raw | {'mood': 'sad'}), Book)
            with self.assertRaisesRegex(ValueError, 'did not return valid JSON'):
                parse_structured_response('this is not JSON', Book)
            with self.assertRaisesRegex(ValueError, 'Book.is_fiction: expected boolean'):
                parse_structured_response(json.dumps(raw | {'is_fiction': 'yes'}), Book)

        def test_ai_structured_prompt_driver(self) -> None:
            payload = json.dumps({'title': 'Emma', 'authors': ['Jane Austen'], 'publication_year': 1815})

            def chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
                messages = tuple(messages)
                self.ae(messages[0].type, ChatMessageType.system)
                self.assertIn('interface ExampleBookInfo', messages[0].query)
                self.ae(messages[1].query, 'Tell me about Emma')
                yield ChatResponse(content='```json\n' + payload[:10])
                yield ChatResponse(content=payload[10:] + '\n```')
                yield ChatResponse(has_metadata=True, cost=0.25, currency='USD', provider='p', model='m')

            res = structured_output_via_prompt(chat, 'Tell me about Emma', ExampleBookInfo, plugin_name='TestPlugin')
            self.assertIsNone(res.exception)
            self.ae(res.data, ExampleBookInfo(title='Emma', authors=['Jane Austen'], publication_year=1815))
            self.ae(res.raw, payload)
            self.ae((res.cost, res.currency, res.provider, res.model, res.plugin_name), (0.25, 'USD', 'p', 'm', 'TestPlugin'))

            def failing_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
                yield ChatResponse(exception=Exception('boom'), error_details='details')

            res = structured_output_with_error_handler(lambda: structured_output_via_prompt(failing_chat, 'q', ExampleBookInfo))
            self.assertIsNotNone(res.exception)
            self.ae(res.error_details, 'details')
            self.assertIsNone(res.data)

            def bad_json_chat(messages: Iterable[ChatMessage], use_model: str = '') -> Iterator[ChatResponse]:
                yield ChatResponse(content='not json')

            res = structured_output_with_error_handler(lambda: structured_output_via_prompt(bad_json_chat, 'q', ExampleBookInfo))
            self.assertIsInstance(res.exception, ValueError)

        def test_ai_structured_openai_request(self) -> None:
            from calibre.ai.openai.backend import structured_output_data

            d = structured_output_data(messages_for_structured_output('extract', 'sys'), ExampleBookInfo)
            self.ae(d['input'][0], {'role': 'system', 'content': 'sys'})
            self.ae(d['input'][1], {'role': 'user', 'content': 'extract'})
            fmt = d['text']['format']
            self.ae(fmt['type'], 'json_schema')
            self.ae(fmt['name'], 'ExampleBookInfo')
            self.assertTrue(fmt['strict'])
            self.assertFalse(fmt['schema']['additionalProperties'])
            self.assertNotIn('tools', d)

        def test_ai_structured_google_request(self) -> None:
            from calibre.ai import AICapabilities
            from calibre.ai.google.backend import Model, structured_output_data

            model = Model(
                name='gemini-2.5-flash',
                id='models/gemini-2.5-flash',
                slug='models/gemini-2.5-flash',
                description='',
                version='1',
                context_length=1000,
                output_token_limit=1000,
                capabilities=AICapabilities.text_to_text,
                family='gemini',
                family_version=2.5,
                name_parts=('gemini', '2.5', 'flash'),
                thinking=False,
                pricing=None,
            )
            d = structured_output_data(messages_for_structured_output('extract'), model, ExampleBookInfo)
            gc = d['generationConfig']
            self.ae(gc['responseMimeType'], 'application/json')
            self.ae(gc['responseSchema']['propertyOrdering'], ['title', 'authors', 'publication_year'])
            self.assertNotIn('additionalProperties', json.dumps(gc['responseSchema']))
            self.assertNotIn('tools', d)
            self.ae(d['contents'], [{'parts': [{'text': 'extract'}]}])

        def test_ai_structured_anthropic(self) -> None:
            import calibre.ai.anthropic.backend as ab

            for model_id, expected in {
                'claude-fable-5': True,
                'claude-mythos-5': True,
                'claude-opus-4-1-20250805': True,
                'claude-haiku-4-5': True,
                'claude-sonnet-5': True,
                'claude-3-5-haiku-20241022': False,
                'claude-3-7-sonnet-20250219': False,
                'claude-future-model': True,
            }.items():
                m = ab.Model.create(model_id, model_id)
                self.ae(m.supports_native_structured_output, expected, model_id)
            model = ab.Model.create('claude-sonnet-5', 'Claude Sonnet 5')
            orig_pref = ab.pref

            def fake_pref(key: str, defval: Any = None) -> Any:  # noqa: ANN401
                return 'low' if key == 'reasoning_strategy' else orig_pref(key, defval)

            from unittest.mock import patch

            # reasoning effort settings and the structured output format must
            # both survive in output_config
            with patch.object(ab, 'pref', fake_pref):
                d = ab.structured_output_data(messages_for_structured_output('extract', 'sys'), model, ExampleBookInfo)
            oc = d['output_config']
            self.ae(oc['effort'], 'low')
            self.ae(oc['format']['type'], 'json_schema')
            self.assertFalse(oc['format']['schema']['additionalProperties'])
            self.ae(d['system'], 'sys')
            self.ae(d['messages'], [{'role': 'user', 'content': 'extract'}])
            self.assertNotIn('tools', d)

        def test_ai_structured_open_router(self) -> None:
            import datetime

            from calibre.ai import AICapabilities
            from calibre.ai.open_router.backend import Model, Pricing, structured_output_data, supports_structured_output

            def m(mid: str, parameters: tuple[str, ...]) -> Model:
                return Model(
                    name=mid,
                    id=mid,
                    slug=mid,
                    created=datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC),
                    description='',
                    context_length=1000,
                    pricing=Pricing(),
                    parameters=parameters,
                    is_moderated=False,
                    capabilities=AICapabilities.text_to_text,
                    tokenizer='',
                )

            with_so, without_so = m('a/with', ('response_format', 'structured_outputs')), m('b/without', ('temperature',))
            self.assertTrue(supports_structured_output(with_so))
            self.assertFalse(supports_structured_output(without_so))
            models = (with_so, without_so, m('c/with', ('structured_outputs',)))
            d = structured_output_data(messages_for_structured_output('extract'), models, with_so.id, ExampleBookInfo)
            rf = d['response_format']
            self.ae(rf['type'], 'json_schema')
            self.ae(rf['json_schema']['name'], 'ExampleBookInfo')
            self.assertTrue(rf['json_schema']['strict'])
            self.ae(d['models'], ['c/with'], 'fallback models must be filtered to those supporting structured output')
            d = structured_output_data(messages_for_structured_output('extract'), (with_so, without_so), with_so.id, ExampleBookInfo)
            self.assertNotIn('models', d)
            self.ae(d['plugins'], [])

        def test_ai_structured_ollama_lm_studio(self) -> None:
            import datetime

            from calibre.ai.lm_studio.backend import structured_output_data as lm_studio_data
            from calibre.ai.ollama.backend import Model
            from calibre.ai.ollama.backend import structured_output_data as ollama_data

            model = Model(name='llama3', id='llama3:latest', family='llama', families=(), modified_at=datetime.datetime(2025, 1, 1), can_think=False)
            d = ollama_data(messages_for_structured_output('extract'), model, ExampleBookInfo)
            self.ae(d['format'], strict_json_schema(ExampleBookInfo))
            self.ae(d['messages'], [{'role': 'user', 'content': 'extract'}])

            d = lm_studio_data(messages_for_structured_output('extract'), 'some-model', ExampleBookInfo)
            rf = d['response_format']
            self.ae(rf['type'], 'json_schema')
            self.ae(rf['json_schema']['schema'], strict_json_schema(ExampleBookInfo))
            self.ae(d['model'], 'some-model')

        def test_ai_structured_system_prompt(self) -> None:
            p = system_prompt_for_schema(ExampleBookInfo, instructions='You are a librarian.')
            self.assertTrue(p.startswith('You are a librarian.'))
            self.assertIn('only valid JSON', p)
            self.assertIn('interface ExampleBookInfo', p)
            m = messages_for_structured_output('the prompt', 'sys')
            self.ae(len(m), 2)
            self.ae(m[0].type, ChatMessageType.system)
            self.ae(m[1].query, 'the prompt')
            self.ae(len(messages_for_structured_output('the prompt')), 1)

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestStructuredOutput)


if __name__ == '__main__':
    import unittest

    unittest.TextTestRunner(verbosity=2).run(find_tests())
