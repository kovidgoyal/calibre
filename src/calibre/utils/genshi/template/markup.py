# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2008 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""Markup templating engine."""

from itertools import chain

from calibre.utils.genshi.core import Attrs, Markup, Namespace, Stream, StreamEventKind
from calibre.utils.genshi.core import START, END, START_NS, END_NS, TEXT, PI, COMMENT
from calibre.utils.genshi.input import XMLParser
from calibre.utils.genshi.template.base import BadDirectiveError, Template, \
                                 TemplateSyntaxError, _apply_directives, \
                                 EXEC, INCLUDE, SUB
from calibre.utils.genshi.template.eval import Suite
from calibre.utils.genshi.template.interpolation import interpolate
from calibre.utils.genshi.template.directives import *
from calibre.utils.genshi.template.text import NewTextTemplate

__all__ = ['MarkupTemplate']
__docformat__ = 'restructuredtext en'


class MarkupTemplate(Template):
    """Implementation of the template language for XML-based templates.
    
    >>> tmpl = MarkupTemplate('''<ul xmlns:py="http://genshi.edgewall.org/">
    ...   <li py:for="item in items">${item}</li>
    ... </ul>''')
    >>> print tmpl.generate(items=[1, 2, 3])
    <ul>
      <li>1</li><li>2</li><li>3</li>
    </ul>
    """

    DIRECTIVE_NAMESPACE = Namespace('http://genshi.edgewall.org/')
    XINCLUDE_NAMESPACE = Namespace('http://www.w3.org/2001/XInclude')

    directives = [('def', DefDirective),
                  ('match', MatchDirective),
                  ('when', WhenDirective),
                  ('otherwise', OtherwiseDirective),
                  ('for', ForDirective),
                  ('if', IfDirective),
                  ('choose', ChooseDirective),
                  ('with', WithDirective),
                  ('replace', ReplaceDirective),
                  ('content', ContentDirective),
                  ('attrs', AttrsDirective),
                  ('strip', StripDirective)]
    serializer = 'xml'
    _number_conv = Markup

    def _init_filters(self):
        Template._init_filters(self)
        # Make sure the include filter comes after the match filter
        if self.loader:
            self.filters.remove(self._include)
        self.filters += [self._match]
        if self.loader:
            self.filters.append(self._include)

    def _parse(self, source, encoding):
        streams = [[]] # stacked lists of events of the "compiled" template
        dirmap = {} # temporary mapping of directives to elements
        ns_prefix = {}
        depth = 0
        fallbacks = []
        includes = []

        if not isinstance(source, Stream):
            source = XMLParser(source, filename=self.filename,
                               encoding=encoding)

        for kind, data, pos in source:
            stream = streams[-1]

            if kind is START_NS:
                # Strip out the namespace declaration for template directives
                prefix, uri = data
                ns_prefix[prefix] = uri
                if uri not in (self.DIRECTIVE_NAMESPACE,
                               self.XINCLUDE_NAMESPACE):
                    stream.append((kind, data, pos))

            elif kind is END_NS:
                uri = ns_prefix.pop(data, None)
                if uri and uri not in (self.DIRECTIVE_NAMESPACE,
                                       self.XINCLUDE_NAMESPACE):
                    stream.append((kind, data, pos))

            elif kind is START:
                # Record any directive attributes in start tags
                tag, attrs = data
                directives = []
                strip = False

                if tag in self.DIRECTIVE_NAMESPACE:
                    cls = self._dir_by_name.get(tag.localname)
                    if cls is None:
                        raise BadDirectiveError(tag.localname, self.filepath,
                                                pos[1])
                    args = dict([(name.localname, value) for name, value
                                 in attrs if not name.namespace])
                    directives.append((cls, args, ns_prefix.copy(), pos))
                    strip = True

                new_attrs = []
                for name, value in attrs:
                    if name in self.DIRECTIVE_NAMESPACE:
                        cls = self._dir_by_name.get(name.localname)
                        if cls is None:
                            raise BadDirectiveError(name.localname,
                                                    self.filepath, pos[1])
                        directives.append((cls, value, ns_prefix.copy(), pos))
                    else:
                        if value:
                            value = list(interpolate(value, self.filepath,
                                                     pos[1], pos[2],
                                                     lookup=self.lookup))
                            if len(value) == 1 and value[0][0] is TEXT:
                                value = value[0][1]
                        else:
                            value = [(TEXT, u'', pos)]
                        new_attrs.append((name, value))
                new_attrs = Attrs(new_attrs)

                if directives:
                    index = self._dir_order.index
                    directives.sort(lambda a, b: cmp(index(a[0]), index(b[0])))
                    dirmap[(depth, tag)] = (directives, len(stream), strip)

                if tag in self.XINCLUDE_NAMESPACE:
                    if tag.localname == 'include':
                        include_href = new_attrs.get('href')
                        if not include_href:
                            raise TemplateSyntaxError('Include misses required '
                                                      'attribute "href"',
                                                      self.filepath, *pos[1:])
                        includes.append((include_href, new_attrs.get('parse')))
                        streams.append([])
                    elif tag.localname == 'fallback':
                        streams.append([])
                        fallbacks.append(streams[-1])

                else:
                    stream.append((kind, (tag, new_attrs), pos))

                depth += 1

            elif kind is END:
                depth -= 1

                if fallbacks and data == self.XINCLUDE_NAMESPACE['fallback']:
                    assert streams.pop() is fallbacks[-1]
                elif data == self.XINCLUDE_NAMESPACE['include']:
                    fallback = None
                    if len(fallbacks) == len(includes):
                        fallback = fallbacks.pop()
                    streams.pop() # discard anything between the include tags
                                  # and the fallback element
                    stream = streams[-1]
                    href, parse = includes.pop()
                    try:
                        cls = {
                            'xml': MarkupTemplate,
                            'text': NewTextTemplate
                        }[parse or 'xml']
                    except KeyError:
                        raise TemplateSyntaxError('Invalid value for "parse" '
                                                  'attribute of include',
                                                  self.filepath, *pos[1:])
                    stream.append((INCLUDE, (href, cls, fallback), pos))
                else:
                    stream.append((kind, data, pos))

                # If there have have directive attributes with the corresponding
                # start tag, move the events inbetween into a "subprogram"
                if (depth, data) in dirmap:
                    directives, start_offset, strip = dirmap.pop((depth, data))
                    substream = stream[start_offset:]
                    if strip:
                        substream = substream[1:-1]
                    stream[start_offset:] = [(SUB, (directives, substream),
                                              pos)]

            elif kind is PI and data[0] == 'python':
                if not self.allow_exec:
                    raise TemplateSyntaxError('Python code blocks not allowed',
                                              self.filepath, *pos[1:])
                try:
                    suite = Suite(data[1], self.filepath, pos[1],
                                  lookup=self.lookup)
                except SyntaxError, err:
                    raise TemplateSyntaxError(err, self.filepath,
                                              pos[1] + (err.lineno or 1) - 1,
                                              pos[2] + (err.offset or 0))
                stream.append((EXEC, suite, pos))

            elif kind is TEXT:
                for kind, data, pos in interpolate(data, self.filepath, pos[1],
                                                   pos[2], lookup=self.lookup):
                    stream.append((kind, data, pos))

            elif kind is COMMENT:
                if not data.lstrip().startswith('!'):
                    stream.append((kind, data, pos))

            else:
                stream.append((kind, data, pos))

        assert len(streams) == 1
        return streams[0]

    def _match(self, stream, ctxt, match_templates=None, **vars):
        """Internal stream filter that applies any defined match templates
        to the stream.
        """
        if match_templates is None:
            match_templates = ctxt._match_templates

        tail = []
        def _strip(stream):
            depth = 1
            while 1:
                event = stream.next()
                if event[0] is START:
                    depth += 1
                elif event[0] is END:
                    depth -= 1
                if depth > 0:
                    yield event
                else:
                    tail[:] = [event]
                    break

        for event in stream:

            # We (currently) only care about start and end events for matching
            # We might care about namespace events in the future, though
            if not match_templates or (event[0] is not START and
                                       event[0] is not END):
                yield event
                continue

            for idx, (test, path, template, hints, namespaces, directives) \
                    in enumerate(match_templates):

                if test(event, namespaces, ctxt) is True:
                    if 'match_once' in hints:
                        del match_templates[idx]
                        idx -= 1

                    # Let the remaining match templates know about the event so
                    # they get a chance to update their internal state
                    for test in [mt[0] for mt in match_templates[idx + 1:]]:
                        test(event, namespaces, ctxt, updateonly=True)

                    # Consume and store all events until an end event
                    # corresponding to this start event is encountered
                    pre_match_templates = match_templates[:idx + 1]
                    if 'match_once' not in hints and 'not_recursive' in hints:
                        pre_match_templates.pop()
                    inner = _strip(stream)
                    if pre_match_templates:
                        inner = self._match(inner, ctxt, pre_match_templates)
                    content = self._include(chain([event], inner, tail), ctxt)
                    if 'not_buffered' not in hints:
                        content = list(content)

                    if tail:
                        for test in [mt[0] for mt in match_templates]:
                            test(tail[0], namespaces, ctxt, updateonly=True)

                    # Make the select() function available in the body of the
                    # match template
                    def select(path):
                        return Stream(content).select(path, namespaces, ctxt)
                    vars = dict(select=select)

                    # Recursively process the output
                    template = _apply_directives(template, directives, ctxt,
                                                 **vars)
                    for event in self._match(
                            self._exec(
                                self._eval(
                                    self._flatten(template, ctxt, **vars),
                                    ctxt, **vars),
                                ctxt, **vars),
                            ctxt, match_templates[idx + 1:], **vars):
                        yield event

                    break

            else: # no matches
                yield event
