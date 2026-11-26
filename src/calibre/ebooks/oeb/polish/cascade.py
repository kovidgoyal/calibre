#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from collections import defaultdict
from functools import partial
from itertools import count
from operator import itemgetter
from typing import TYPE_CHECKING, Literal, NamedTuple, Protocol, Self, cast, overload

from kgcss import (
    CSS_WIDE_KEYWORDS,
    GroupingRule,
    ImportRule,
    MediaRule,
    Property,
    RuleType,
    Select,
    SelectorError,
    StyleRule,
    Stylesheet,
    parse_font_family,
    parse_value,
    serialize_font_family,
)
from lxml import etree

from calibre import as_unicode
from calibre.ebooks.oeb.base import OEB_STYLES, SVG, XHTML
from calibre.ebooks.oeb.normalize_css import DEFAULTS, normalize_shorthand
from calibre.ebooks.oeb.stylizer import INHERITED, inappropriate_pseudo, media_ok
from calibre.utils.resources import get_path as P

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Sequence

    from kgcss import Component, DeclarationBlock, MediaList, Rule, RuleList, Selector
    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.container import Container, ContainerBase

#: Maps elements to their resolved CSS properties
type StyleMap = dict[_Element, dict[str, Values | None]]
#: Maps elements to pseudo-element name to resolved CSS properties
type PseudoStyleMap = dict[_Element, dict[str | None, dict[str, Values | None]]]


class ResolveProperty(Protocol):
    "The type of the ``resolve_property`` function returned by :func:`resolve_styles`"

    def __call__(self, elem: _Element, name: str, /) -> Values | None: ...


class ResolvePseudoProperty(Protocol):
    "The type of the ``resolve_pseudo_property`` function returned by :func:`resolve_styles`"

    @overload
    def __call__(
        self,
        elem: _Element,
        prop: str | None,
        name: str,
        abort_on_missing: bool = False,
        check_if_pseudo_applies: Literal[False] = False,
        check_ancestors: bool = False,
    ) -> Values | None: ...
    @overload
    def __call__(
        self,
        elem: _Element,
        prop: str | None,
        name: str,
        abort_on_missing: bool = False,
        *,
        check_if_pseudo_applies: Literal[True],
        check_ancestors: bool = False,
    ) -> bool: ...


_html_css_stylesheet: Stylesheet | None = None


def html_css_stylesheet(container: ContainerBase) -> Stylesheet:
    global _html_css_stylesheet
    if _html_css_stylesheet is None:
        data = P('templates/html.css', data=True).decode('utf-8')
        _html_css_stylesheet = container.parse_stylesheet(data, 'user-agent.css')
    return _html_css_stylesheet


def media_allowed(media: MediaList | None) -> bool:
    if not media:
        return True
    return media_ok(media.media_text)


def iterrules(
    container: Container,
    sheet_name: str,
    rules: Stylesheet | RuleList | None = None,
    media_rule_ok: Callable[[MediaList | None], bool] = media_allowed,
    rule_index_counter: Iterator[int] | None = None,
    rule_type: RuleType | None = None,
    importing: set[str] | None = None,
) -> Iterator[tuple[Rule, str, int]]:
    """Iterate over all style rules in the specified sheet. Import and Media rules are
    automatically resolved, other grouping rules such as @supports are
    always followed. Yields (rule, sheet_name, rule_number).

    :param rules: A list of rules or a Stylesheet or None in which case it is read from container using sheet_name
    :param sheet_name: The name of the sheet in the container (in case of inline style sheets, the name of the html file)
    :param media_rule_ok: A function to test if a @media rule is allowed
    :param rule_index_counter: A counter object, rule numbers will be calculated by incrementing the counter.
    :param rule_type: Only yield rules of this type (by default all rules are yielded)
    :return: (Rule object, the name of the sheet from which it comes, rule index - a monotonically increasing number)
    """

    rule_index_counter = rule_index_counter or count()
    if importing is None:
        importing = set()
    importing.add(sheet_name)
    riter = partial(
        iterrules,
        container,
        rule_index_counter=rule_index_counter,
        media_rule_ok=media_rule_ok,
        rule_type=rule_type,
        importing=importing,
    )
    if rules is None:
        rules = container.parsed_stylesheet(sheet_name)

    for rule in rules:
        if isinstance(rule, ImportRule):
            if media_rule_ok(rule.media):
                name = container.href_to_name(rule.href, sheet_name)
                if container.has_name(name):
                    if name in importing:
                        container.log.error(f'Recursive import of {name} from {sheet_name}, ignoring')
                    else:
                        csheet = container.parsed_object(name)
                        if isinstance(csheet, Stylesheet):
                            yield from riter(name, rules=csheet)
        elif isinstance(rule, MediaRule):
            if media_rule_ok(rule.media):
                yield from riter(sheet_name, rules=rule.rules)
        elif isinstance(rule, GroupingRule):
            # @supports, @layer, @container and the like: their rules are
            # used, so that what they use, such as fonts, is not considered
            # to be unused
            yield from riter(sheet_name, rules=rule.rules)

        elif rule_type is None or rule.type == rule_type:
            num = next(rule_index_counter)
            yield rule, sheet_name, num

    importing.discard(sheet_name)


class StyleDeclaration(NamedTuple):
    index: Specificity
    declaration: dict[str, Values]
    pseudo_element: str | None


class Specificity(NamedTuple):
    is_style: int
    num_id: int
    num_class: int
    num_elem: int
    rule_index: int


def specificity(rule_index: int, selector: Selector, is_style: int = 0) -> Specificity:
    s = selector.specificity
    return Specificity(is_style, s[0], s[1], s[2], rule_index)


def iterdeclaration(decl: DeclarationBlock) -> Iterator[Property]:
    "The properties of a declaration block, with shorthands expanded"
    for p in decl.items:
        if isinstance(p, Property):
            expanded = normalize_shorthand(p.name, p.value_to_css())
            if expanded is None:
                yield p
            else:
                for k, v in expanded.items():
                    yield Property(k, v, p.priority)


def component_text(c: Component) -> str:
    "The text of an identifier or string, unquoted, the CSS of other components, such as 700 or 1.5em"
    return c.css_text if c.string_value is None else c.string_value


class Values(tuple['Component', ...]):
    """A tuple of the components of a property value. Also has a
    `sheet_name` attribute that is the canonical name relative to which URLs
    for this property should be resolved."""

    sheet_name: str | None
    is_important: bool

    def __new__(typ, pv: Iterable[Component], sheet_name: str | None = None, priority: str = '') -> Self:
        ans = tuple.__new__(typ, pv)
        ans.sheet_name = sheet_name
        ans.is_important = priority == 'important'
        return ans

    @property
    def css_text(self) -> str | tuple[str, ...]:
        "This will return either a string or a tuple of strings"
        if len(self) == 1:
            return self[0].css_text
        return tuple(x.css_text for x in self)


def normalize_style_declaration(decl: DeclarationBlock, sheet_name: str) -> dict[str, Values]:
    ans: dict[str, Values] = {}
    for prop in iterdeclaration(decl):
        if 'var(' in prop.value.lower():
            # The value is not known before it is computed, css_parser dropped
            # such declarations
            continue
        # The components of the normalized value, as css_parser gave them
        value = parse_value(prop.value_to_css(), property_name=prop.name)
        if prop.name == 'font-family':
            val = prop.value
            # Font family names as quoted strings, one for each family.
            # serialize_font_family() quotes the CSS-wide keywords, which
            # would turn them into family names
            if val.strip().lower() not in CSS_WIDE_KEYWORDS:
                value = parse_value(serialize_font_family(parse_font_family(val)), property_name='font-family')
        ans[prop.name] = Values(value, sheet_name, prop.priority)
    return ans


def resolve_declarations(decls: Sequence[StyleDeclaration]) -> dict[str, Values | None]:
    property_names: set[str] = set()
    for d in decls:
        property_names |= set(d.declaration)
    ans: dict[str, Values | None] = {}
    for name in property_names:
        first_val: Values | None = None
        for decl in decls:
            x = decl.declaration.get(name)
            if x is not None:
                if x.is_important:
                    first_val = x
                    break
                if first_val is None:
                    first_val = x
        ans[name] = first_val
    return ans


def resolve_pseudo_declarations(decls: Iterable[StyleDeclaration]) -> dict[str | None, dict[str, Values | None]]:
    groups: defaultdict[str | None, list[StyleDeclaration]] = defaultdict(list)
    for d in decls:
        groups[d.pseudo_element].append(d)
    return {k: resolve_declarations(v) for k, v in groups.items()}


def resolve_styles(
    container: Container,
    name: str,
    select: Select[_Element] | None = None,
    sheet_callback: Callable[[Stylesheet, str], object] | None = None,
) -> tuple[ResolveProperty, ResolvePseudoProperty, Select[_Element]]:
    root = container.parsed(name)
    assert isinstance(root, etree._Element)
    # quirks_mode matches ids and classes case-insensitively, as the selector
    # engine used before kgcss did
    select = select or Select(root, ignore_inappropriate_pseudo_classes=True, quirks_mode=True)
    style_map: defaultdict[_Element, list[StyleDeclaration]] = defaultdict(list)
    pseudo_style_map: defaultdict[_Element, list[StyleDeclaration]] = defaultdict(list)
    rule_index_counter = count()

    def process_sheet(sheet: Stylesheet, sheet_name: str) -> None:
        if sheet_callback is not None:
            sheet_callback(sheet, sheet_name)
        for rule, name_sheet, rule_index in iterrules(container, sheet_name, rules=sheet, rule_index_counter=rule_index_counter, rule_type=RuleType.STYLE):
            assert isinstance(rule, StyleRule)  # only style rules are iterated over
            for selector in rule.selectors:
                try:
                    matches = tuple(select(selector))
                    selector_specificity = specificity(rule_index, selector)
                except SelectorError as err:
                    container.log.error(f'Ignoring CSS rule with invalid selector: {selector.text!r} ({as_unicode(err)})')
                    continue
                pseudo = inappropriate_pseudo(selector)
                style = normalize_style_declaration(rule.style, name_sheet)
                if pseudo is None:
                    for elem in matches:
                        style_map[elem].append(StyleDeclaration(selector_specificity, style, None))
                else:
                    for elem in matches:
                        pseudo_style_map[elem].append(StyleDeclaration(selector_specificity, style, pseudo))

    process_sheet(html_css_stylesheet(container), 'user-agent.css')

    for elem in root.iterdescendants(XHTML('style'), SVG('style'), XHTML('link')):
        tag = elem.tag
        assert isinstance(tag, str)  # only elements with the above string tags are iterated over
        if tag.lower().endswith('style'):
            if not elem.text:
                continue
            sheet = container.parse_stylesheet(elem.text)
            sheet_name = name
        else:
            if (
                (elem.get('type') or 'text/css').lower() not in OEB_STYLES
                or (elem.get('rel') or 'stylesheet').lower() != 'stylesheet'
                or not media_ok(elem.get('media'))
            ):
                continue
            href = elem.get('href')
            if not href:
                continue
            sheet_name = container.href_to_name(href, name)
            if not container.has_name(sheet_name):
                continue
            sheet = container.parsed_object(sheet_name)
            if not isinstance(sheet, Stylesheet):
                continue
        process_sheet(sheet, sheet_name)

    for elem in root.xpath('//*[@style]'):
        text = elem.get('style')
        if text:
            style = container.parse_style(text)
            style_map[elem].append(StyleDeclaration(Specificity(1, 0, 0, 0, 0), normalize_style_declaration(style, name), None))

    for l in (style_map, pseudo_style_map):
        for x in l.values():
            x.sort(key=itemgetter(0), reverse=True)

    resolved_style_map: StyleMap = {elem: resolve_declarations(x) for elem, x in style_map.items()}
    resolved_pseudo_style_map: PseudoStyleMap = {elem: resolve_pseudo_declarations(x) for elem, x in pseudo_style_map.items()}

    return (
        partial(resolve_property, resolved_style_map),
        cast('ResolvePseudoProperty', partial(resolve_pseudo_property, resolved_style_map, resolved_pseudo_style_map)),  # partial() loses the overloads
        select,
    )


_defvals: dict[str, Values] | None = None


def defvals() -> dict[str, Values]:
    global _defvals
    if _defvals is None:
        _defvals = {k: Values(parse_value(str(val), property_name=k)) for k, val in DEFAULTS.items()}
    return _defvals


def resolve_property(style_map: StyleMap, elem: _Element, name: str) -> Values | None:
    """Given a `style_map` previously generated by :func:`resolve_styles()` and
    a property `name`, returns the effective value of that property for the
    specified element. Handles inheritance and CSS cascading rules. Returns
    an instance of :class:`Values`. If the property was never set and
    is not a known property, then it will return None."""

    inheritable = name in INHERITED
    q = elem
    while q is not None:
        s = style_map.get(q)
        if s is not None:
            val = s.get(name)
            if val is not None:
                return val
        q = q.getparent() if inheritable else None
    return defvals().get(name)


@overload
def resolve_pseudo_property(
    style_map: StyleMap,
    pseudo_style_map: PseudoStyleMap,
    elem: _Element,
    prop: str | None,
    name: str,
    abort_on_missing: bool = False,
    check_if_pseudo_applies: Literal[False] = False,
    check_ancestors: bool = False,
) -> Values | None: ...
@overload
def resolve_pseudo_property(
    style_map: StyleMap,
    pseudo_style_map: PseudoStyleMap,
    elem: _Element,
    prop: str | None,
    name: str,
    abort_on_missing: bool = False,
    *,
    check_if_pseudo_applies: Literal[True],
    check_ancestors: bool = False,
) -> bool: ...
def resolve_pseudo_property(
    style_map: StyleMap,
    pseudo_style_map: PseudoStyleMap,
    elem: _Element,
    prop: str | None,
    name: str,
    abort_on_missing: bool = False,
    check_if_pseudo_applies: bool = False,
    check_ancestors: bool = False,
) -> Values | bool | None:
    if check_if_pseudo_applies:
        q = elem
        while q is not None:
            val = pseudo_style_map.get(q, {}).get(prop, {}).get(name)
            if val is not None:
                return True
            if not check_ancestors:
                break
            q = q.getparent()
        return False
    sub_map = pseudo_style_map.get(elem)
    if abort_on_missing and sub_map is None:
        return None
    if sub_map is not None:
        prop_map = sub_map.get(prop)
        if abort_on_missing and prop_map is None:
            return None
        if prop_map is not None:
            val = prop_map.get(name)
            if val is not None:
                return val
    if name in INHERITED:
        if check_ancestors:
            q = elem.getparent()
            while q is not None:
                val = pseudo_style_map.get(q, {}).get(prop, {}).get(name)
                if val is not None:
                    return val
                if not check_ancestors:
                    break
                q = q.getparent()
        return resolve_property(style_map, elem, name)
    return defvals().get(name)
