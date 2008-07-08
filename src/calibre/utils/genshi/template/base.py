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

"""Basic templating functionality."""

try:
    from collections import deque
except ImportError:
    class deque(list):
        def appendleft(self, x): self.insert(0, x)
        def popleft(self): return self.pop(0)
import os
from StringIO import StringIO
import sys

from calibre.utils.genshi.core import Attrs, Stream, StreamEventKind, START, TEXT, _ensure
from calibre.utils.genshi.input import ParseError

__all__ = ['Context', 'Template', 'TemplateError', 'TemplateRuntimeError',
           'TemplateSyntaxError', 'BadDirectiveError']
__docformat__ = 'restructuredtext en'

if sys.version_info < (2, 4):
    _ctxt2dict = lambda ctxt: ctxt.frames[0]
else:
    _ctxt2dict = lambda ctxt: ctxt


class TemplateError(Exception):
    """Base exception class for errors related to template processing."""

    def __init__(self, message, filename=None, lineno=-1, offset=-1):
        """Create the exception.
        
        :param message: the error message
        :param filename: the filename of the template
        :param lineno: the number of line in the template at which the error
                       occurred
        :param offset: the column number at which the error occurred
        """
        if filename is None:
            filename = '<string>'
        self.msg = message #: the error message string
        if filename != '<string>' or lineno >= 0:
            message = '%s (%s, line %d)' % (self.msg, filename, lineno)
        Exception.__init__(self, message)
        self.filename = filename #: the name of the template file
        self.lineno = lineno #: the number of the line containing the error
        self.offset = offset #: the offset on the line


class TemplateSyntaxError(TemplateError):
    """Exception raised when an expression in a template causes a Python syntax
    error, or the template is not well-formed.
    """

    def __init__(self, message, filename=None, lineno=-1, offset=-1):
        """Create the exception
        
        :param message: the error message
        :param filename: the filename of the template
        :param lineno: the number of line in the template at which the error
                       occurred
        :param offset: the column number at which the error occurred
        """
        if isinstance(message, SyntaxError) and message.lineno is not None:
            message = str(message).replace(' (line %d)' % message.lineno, '')
        TemplateError.__init__(self, message, filename, lineno)


class BadDirectiveError(TemplateSyntaxError):
    """Exception raised when an unknown directive is encountered when parsing
    a template.
    
    An unknown directive is any attribute using the namespace for directives,
    with a local name that doesn't match any registered directive.
    """

    def __init__(self, name, filename=None, lineno=-1):
        """Create the exception
        
        :param name: the name of the directive
        :param filename: the filename of the template
        :param lineno: the number of line in the template at which the error
                       occurred
        """
        TemplateSyntaxError.__init__(self, 'bad directive "%s"' % name,
                                     filename, lineno)


class TemplateRuntimeError(TemplateError):
    """Exception raised when an the evaluation of a Python expression in a
    template causes an error.
    """


class Context(object):
    """Container for template input data.
    
    A context provides a stack of scopes (represented by dictionaries).
    
    Template directives such as loops can push a new scope on the stack with
    data that should only be available inside the loop. When the loop
    terminates, that scope can get popped off the stack again.
    
    >>> ctxt = Context(one='foo', other=1)
    >>> ctxt.get('one')
    'foo'
    >>> ctxt.get('other')
    1
    >>> ctxt.push(dict(one='frost'))
    >>> ctxt.get('one')
    'frost'
    >>> ctxt.get('other')
    1
    >>> ctxt.pop()
    {'one': 'frost'}
    >>> ctxt.get('one')
    'foo'
    """

    def __init__(self, **data):
        """Initialize the template context with the given keyword arguments as
        data.
        """
        self.frames = deque([data])
        self.pop = self.frames.popleft
        self.push = self.frames.appendleft
        self._match_templates = []
        self._choice_stack = []

        # Helper functions for use in expressions
        def defined(name):
            """Return whether a variable with the specified name exists in the
            expression scope."""
            return name in self
        def value_of(name, default=None):
            """If a variable of the specified name is defined, return its value.
            Otherwise, return the provided default value, or ``None``."""
            return self.get(name, default)
        data.setdefault('defined', defined)
        data.setdefault('value_of', value_of)

    def __repr__(self):
        return repr(list(self.frames))

    def __contains__(self, key):
        """Return whether a variable exists in any of the scopes.
        
        :param key: the name of the variable
        """
        return self._find(key)[1] is not None
    has_key = __contains__

    def __delitem__(self, key):
        """Remove a variable from all scopes.
        
        :param key: the name of the variable
        """
        for frame in self.frames:
            if key in frame:
                del frame[key]

    def __getitem__(self, key):
        """Get a variables's value, starting at the current scope and going
        upward.
        
        :param key: the name of the variable
        :return: the variable value
        :raises KeyError: if the requested variable wasn't found in any scope
        """
        value, frame = self._find(key)
        if frame is None:
            raise KeyError(key)
        return value

    def __len__(self):
        """Return the number of distinctly named variables in the context.
        
        :return: the number of variables in the context
        """
        return len(self.items())

    def __setitem__(self, key, value):
        """Set a variable in the current scope.
        
        :param key: the name of the variable
        :param value: the variable value
        """
        self.frames[0][key] = value

    def _find(self, key, default=None):
        """Retrieve a given variable's value and the frame it was found in.

        Intended primarily for internal use by directives.
        
        :param key: the name of the variable
        :param default: the default value to return when the variable is not
                        found
        """
        for frame in self.frames:
            if key in frame:
                return frame[key], frame
        return default, None

    def get(self, key, default=None):
        """Get a variable's value, starting at the current scope and going
        upward.
        
        :param key: the name of the variable
        :param default: the default value to return when the variable is not
                        found
        """
        for frame in self.frames:
            if key in frame:
                return frame[key]
        return default

    def keys(self):
        """Return the name of all variables in the context.
        
        :return: a list of variable names
        """
        keys = []
        for frame in self.frames:
            keys += [key for key in frame if key not in keys]
        return keys

    def items(self):
        """Return a list of ``(name, value)`` tuples for all variables in the
        context.
        
        :return: a list of variables
        """
        return [(key, self.get(key)) for key in self.keys()]

    def update(self, mapping):
        """Update the context from the mapping provided."""
        self.frames[0].update(mapping)

    def push(self, data):
        """Push a new scope on the stack.
        
        :param data: the data dictionary to push on the context stack.
        """

    def pop(self):
        """Pop the top-most scope from the stack."""


def _apply_directives(stream, directives, ctxt, **vars):
    """Apply the given directives to the stream.
    
    :param stream: the stream the directives should be applied to
    :param directives: the list of directives to apply
    :param ctxt: the `Context`
    :param vars: additional variables that should be available when Python
                 code is executed
    :return: the stream with the given directives applied
    """
    if directives:
        stream = directives[0](iter(stream), directives[1:], ctxt, **vars)
    return stream

def _eval_expr(expr, ctxt, **vars):
    """Evaluate the given `Expression` object.
    
    :param expr: the expression to evaluate
    :param ctxt: the `Context`
    :param vars: additional variables that should be available to the
                 expression
    :return: the result of the evaluation
    """
    if vars:
        ctxt.push(vars)
    retval = expr.evaluate(ctxt)
    if vars:
        ctxt.pop()
    return retval

def _exec_suite(suite, ctxt, **vars):
    """Execute the given `Suite` object.
    
    :param suite: the code suite to execute
    :param ctxt: the `Context`
    :param vars: additional variables that should be available to the
                 code
    """
    if vars:
        ctxt.push(vars)
        ctxt.push({})
    suite.execute(_ctxt2dict(ctxt))
    if vars:
        top = ctxt.pop()
        ctxt.pop()
        ctxt.frames[0].update(top)


class TemplateMeta(type):
    """Meta class for templates."""

    def __new__(cls, name, bases, d):
        if 'directives' in d:
            d['_dir_by_name'] = dict(d['directives'])
            d['_dir_order'] = [directive[1] for directive in d['directives']]

        return type.__new__(cls, name, bases, d)


class Template(object):
    """Abstract template base class.
    
    This class implements most of the template processing model, but does not
    specify the syntax of templates.
    """
    __metaclass__ = TemplateMeta

    EXEC = StreamEventKind('EXEC')
    """Stream event kind representing a Python code suite to execute."""

    EXPR = StreamEventKind('EXPR')
    """Stream event kind representing a Python expression."""

    INCLUDE = StreamEventKind('INCLUDE')
    """Stream event kind representing the inclusion of another template."""

    SUB = StreamEventKind('SUB')
    """Stream event kind representing a nested stream to which one or more
    directives should be applied.
    """

    serializer = None
    _number_conv = unicode # function used to convert numbers to event data

    def __init__(self, source, filepath=None, filename=None, loader=None,
                 encoding=None, lookup='strict', allow_exec=True):
        """Initialize a template from either a string, a file-like object, or
        an already parsed markup stream.
        
        :param source: a string, file-like object, or markup stream to read the
                       template from
        :param filepath: the absolute path to the template file
        :param filename: the path to the template file relative to the search
                         path
        :param loader: the `TemplateLoader` to use for loading included
                       templates
        :param encoding: the encoding of the `source`
        :param lookup: the variable lookup mechanism; either "strict" (the
                       default), "lenient", or a custom lookup class
        :param allow_exec: whether Python code blocks in templates should be
                           allowed
        
        :note: Changed in 0.5: Added the `allow_exec` argument
        """
        self.filepath = filepath or filename
        self.filename = filename
        self.loader = loader
        self.lookup = lookup
        self.allow_exec = allow_exec
        self._init_filters()

        if isinstance(source, basestring):
            source = StringIO(source)
        else:
            source = source
        try:
            self.stream = list(self._prepare(self._parse(source, encoding)))
        except ParseError, e:
            raise TemplateSyntaxError(e.msg, self.filepath, e.lineno, e.offset)

    def __getstate__(self):
        state = self.__dict__.copy()
        state['filters'] = []
        return state

    def __setstate__(self, state):
        self.__dict__ = state
        self._init_filters()

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.filename)

    def _init_filters(self):
        self.filters = [self._flatten, self._eval, self._exec]
        if self.loader:
            self.filters.append(self._include)

    def _parse(self, source, encoding):
        """Parse the template.
        
        The parsing stage parses the template and constructs a list of
        directives that will be executed in the render stage. The input is
        split up into literal output (text that does not depend on the context
        data) and directives or expressions.
        
        :param source: a file-like object containing the XML source of the
                       template, or an XML event stream
        :param encoding: the encoding of the `source`
        """
        raise NotImplementedError

    def _prepare(self, stream):
        """Call the `attach` method of every directive found in the template.
        
        :param stream: the event stream of the template
        """
        from calibre.utils.genshi.template.loader import TemplateNotFound

        for kind, data, pos in stream:
            if kind is SUB:
                directives = []
                substream = data[1]
                for cls, value, namespaces, pos in data[0]:
                    directive, substream = cls.attach(self, substream, value,
                                                      namespaces, pos)
                    if directive:
                        directives.append(directive)
                substream = self._prepare(substream)
                if directives:
                    yield kind, (directives, list(substream)), pos
                else:
                    for event in substream:
                        yield event
            else:
                if kind is INCLUDE:
                    href, cls, fallback = data
                    if isinstance(href, basestring) and \
                            not getattr(self.loader, 'auto_reload', True):
                        # If the path to the included template is static, and
                        # auto-reloading is disabled on the template loader,
                        # the template is inlined into the stream
                        try:
                            tmpl = self.loader.load(href, relative_to=pos[0],
                                                    cls=cls or self.__class__)
                            for event in tmpl.stream:
                                yield event
                        except TemplateNotFound:
                            if fallback is None:
                                raise
                            for event in self._prepare(fallback):
                                yield event
                        continue
                    elif fallback:
                        # Otherwise the include is performed at run time
                        data = href, cls, list(self._prepare(fallback))

                yield kind, data, pos

    def generate(self, *args, **kwargs):
        """Apply the template to the given context data.
        
        Any keyword arguments are made available to the template as context
        data.
        
        Only one positional argument is accepted: if it is provided, it must be
        an instance of the `Context` class, and keyword arguments are ignored.
        This calling style is used for internal processing.
        
        :return: a markup event stream representing the result of applying
                 the template to the context data.
        """
        vars = {}
        if args:
            assert len(args) == 1
            ctxt = args[0]
            if ctxt is None:
                ctxt = Context(**kwargs)
            else:
                vars = kwargs
            assert isinstance(ctxt, Context)
        else:
            ctxt = Context(**kwargs)

        stream = self.stream
        for filter_ in self.filters:
            stream = filter_(iter(stream), ctxt, **vars)
        return Stream(stream, self.serializer)

    def _eval(self, stream, ctxt, **vars):
        """Internal stream filter that evaluates any expressions in `START` and
        `TEXT` events.
        """
        filters = (self._flatten, self._eval)
        number_conv = self._number_conv

        for kind, data, pos in stream:

            if kind is START and data[1]:
                # Attributes may still contain expressions in start tags at
                # this point, so do some evaluation
                tag, attrs = data
                new_attrs = []
                for name, substream in attrs:
                    if isinstance(substream, basestring):
                        value = substream
                    else:
                        values = []
                        for subkind, subdata, subpos in self._eval(substream,
                                                                   ctxt,
                                                                   **vars):
                            if subkind is TEXT:
                                values.append(subdata)
                        value = [x for x in values if x is not None]
                        if not value:
                            continue
                    new_attrs.append((name, u''.join(value)))
                yield kind, (tag, Attrs(new_attrs)), pos

            elif kind is EXPR:
                result = _eval_expr(data, ctxt, **vars)
                if result is not None:
                    # First check for a string, otherwise the iterable test
                    # below succeeds, and the string will be chopped up into
                    # individual characters
                    if isinstance(result, basestring):
                        yield TEXT, result, pos
                    elif isinstance(result, (int, float, long)):
                        yield TEXT, number_conv(result), pos
                    elif hasattr(result, '__iter__'):
                        substream = _ensure(result)
                        for filter_ in filters:
                            substream = filter_(substream, ctxt, **vars)
                        for event in substream:
                            yield event
                    else:
                        yield TEXT, unicode(result), pos

            else:
                yield kind, data, pos

    def _exec(self, stream, ctxt, **vars):
        """Internal stream filter that executes Python code blocks."""
        for event in stream:
            if event[0] is EXEC:
                _exec_suite(event[1], ctxt, **vars)
            else:
                yield event

    def _flatten(self, stream, ctxt, **vars):
        """Internal stream filter that expands `SUB` events in the stream."""
        for event in stream:
            if event[0] is SUB:
                # This event is a list of directives and a list of nested
                # events to which those directives should be applied
                directives, substream = event[1]
                substream = _apply_directives(substream, directives, ctxt,
                                              **vars)
                for event in self._flatten(substream, ctxt, **vars):
                    yield event
            else:
                yield event

    def _include(self, stream, ctxt, **vars):
        """Internal stream filter that performs inclusion of external
        template files.
        """
        from calibre.utils.genshi.template.loader import TemplateNotFound

        for event in stream:
            if event[0] is INCLUDE:
                href, cls, fallback = event[1]
                if not isinstance(href, basestring):
                    parts = []
                    for subkind, subdata, subpos in self._eval(href, ctxt,
                                                               **vars):
                        if subkind is TEXT:
                            parts.append(subdata)
                    href = u''.join([x for x in parts if x is not None])
                try:
                    tmpl = self.loader.load(href, relative_to=event[2][0],
                                            cls=cls or self.__class__)
                    for event in tmpl.generate(ctxt, **vars):
                        yield event
                except TemplateNotFound:
                    if fallback is None:
                        raise
                    for filter_ in self.filters:
                        fallback = filter_(iter(fallback), ctxt, **vars)
                    for event in fallback:
                        yield event
            else:
                yield event


EXEC = Template.EXEC
EXPR = Template.EXPR
INCLUDE = Template.INCLUDE
SUB = Template.SUB
