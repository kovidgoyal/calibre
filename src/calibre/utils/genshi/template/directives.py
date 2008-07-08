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

"""Implementation of the various template directives."""

import compiler
try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset

from calibre.utils.genshi.core import QName, Stream
from calibre.utils.genshi.path import Path
from calibre.utils.genshi.template.base import TemplateRuntimeError, TemplateSyntaxError, \
                                 EXPR, _apply_directives, _eval_expr, \
                                 _exec_suite
from calibre.utils.genshi.template.eval import Expression, ExpressionASTTransformer, _parse

__all__ = ['AttrsDirective', 'ChooseDirective', 'ContentDirective',
           'DefDirective', 'ForDirective', 'IfDirective', 'MatchDirective',
           'OtherwiseDirective', 'ReplaceDirective', 'StripDirective',
           'WhenDirective', 'WithDirective']
__docformat__ = 'restructuredtext en'


class DirectiveMeta(type):
    """Meta class for template directives."""

    def __new__(cls, name, bases, d):
        d['tagname'] = name.lower().replace('directive', '')
        return type.__new__(cls, name, bases, d)


class Directive(object):
    """Abstract base class for template directives.
    
    A directive is basically a callable that takes three positional arguments:
    ``ctxt`` is the template data context, ``stream`` is an iterable over the
    events that the directive applies to, and ``directives`` is is a list of
    other directives on the same stream that need to be applied.
    
    Directives can be "anonymous" or "registered". Registered directives can be
    applied by the template author using an XML attribute with the
    corresponding name in the template. Such directives should be subclasses of
    this base class that can  be instantiated with the value of the directive
    attribute as parameter.
    
    Anonymous directives are simply functions conforming to the protocol
    described above, and can only be applied programmatically (for example by
    template filters).
    """
    __metaclass__ = DirectiveMeta
    __slots__ = ['expr']

    def __init__(self, value, template=None, namespaces=None, lineno=-1,
                 offset=-1):
        self.expr = self._parse_expr(value, template, lineno, offset)

    def attach(cls, template, stream, value, namespaces, pos):
        """Called after the template stream has been completely parsed.
        
        :param template: the `Template` object
        :param stream: the event stream associated with the directive
        :param value: the argument value for the directive; if the directive was
                      specified as an element, this will be an `Attrs` instance
                      with all specified attributes, otherwise it will be a
                      `unicode` object with just the attribute value
        :param namespaces: a mapping of namespace URIs to prefixes
        :param pos: a ``(filename, lineno, offset)`` tuple describing the
                    location where the directive was found in the source
        
        This class method should return a ``(directive, stream)`` tuple. If
        ``directive`` is not ``None``, it should be an instance of the `Directive`
        class, and gets added to the list of directives applied to the substream
        at runtime. `stream` is an event stream that replaces the original
        stream associated with the directive.
        """
        return cls(value, template, namespaces, *pos[1:]), stream
    attach = classmethod(attach)

    def __call__(self, stream, directives, ctxt, **vars):
        """Apply the directive to the given stream.
        
        :param stream: the event stream
        :param directives: a list of the remaining directives that should
                           process the stream
        :param ctxt: the context data
        :param vars: additional variables that should be made available when
                     Python code is executed
        """
        raise NotImplementedError

    def __repr__(self):
        expr = ''
        if getattr(self, 'expr', None) is not None:
            expr = ' "%s"' % self.expr.source
        return '<%s%s>' % (self.__class__.__name__, expr)

    def _parse_expr(cls, expr, template, lineno=-1, offset=-1):
        """Parses the given expression, raising a useful error message when a
        syntax error is encountered.
        """
        try:
            return expr and Expression(expr, template.filepath, lineno,
                                       lookup=template.lookup) or None
        except SyntaxError, err:
            err.msg += ' in expression "%s" of "%s" directive' % (expr,
                                                                  cls.tagname)
            raise TemplateSyntaxError(err, template.filepath, lineno,
                                      offset + (err.offset or 0))
    _parse_expr = classmethod(_parse_expr)


def _assignment(ast):
    """Takes the AST representation of an assignment, and returns a function
    that applies the assignment of a given value to a dictionary.
    """
    def _names(node):
        if isinstance(node, (compiler.ast.AssTuple, compiler.ast.Tuple)):
            return tuple([_names(child) for child in node.nodes])
        elif isinstance(node, (compiler.ast.AssName, compiler.ast.Name)):
            return node.name
    def _assign(data, value, names=_names(ast)):
        if type(names) is tuple:
            for idx in range(len(names)):
                _assign(data, value[idx], names[idx])
        else:
            data[names] = value
    return _assign


class AttrsDirective(Directive):
    """Implementation of the ``py:attrs`` template directive.
    
    The value of the ``py:attrs`` attribute should be a dictionary or a sequence
    of ``(name, value)`` tuples. The items in that dictionary or sequence are
    added as attributes to the element:
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<ul xmlns:py="http://genshi.edgewall.org/">
    ...   <li py:attrs="foo">Bar</li>
    ... </ul>''')
    >>> print tmpl.generate(foo={'class': 'collapse'})
    <ul>
      <li class="collapse">Bar</li>
    </ul>
    >>> print tmpl.generate(foo=[('class', 'collapse')])
    <ul>
      <li class="collapse">Bar</li>
    </ul>
    
    If the value evaluates to ``None`` (or any other non-truth value), no
    attributes are added:
    
    >>> print tmpl.generate(foo=None)
    <ul>
      <li>Bar</li>
    </ul>
    """
    __slots__ = []

    def __call__(self, stream, directives, ctxt, **vars):
        def _generate():
            kind, (tag, attrib), pos  = stream.next()
            attrs = _eval_expr(self.expr, ctxt, **vars)
            if attrs:
                if isinstance(attrs, Stream):
                    try:
                        attrs = iter(attrs).next()
                    except StopIteration:
                        attrs = []
                elif not isinstance(attrs, list): # assume it's a dict
                    attrs = attrs.items()
                attrib -= [name for name, val in attrs if val is None]
                attrib |= [(QName(name), unicode(val).strip()) for name, val
                           in attrs if val is not None]
            yield kind, (tag, attrib), pos
            for event in stream:
                yield event

        return _apply_directives(_generate(), directives, ctxt, **vars)


class ContentDirective(Directive):
    """Implementation of the ``py:content`` template directive.
    
    This directive replaces the content of the element with the result of
    evaluating the value of the ``py:content`` attribute:
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<ul xmlns:py="http://genshi.edgewall.org/">
    ...   <li py:content="bar">Hello</li>
    ... </ul>''')
    >>> print tmpl.generate(bar='Bye')
    <ul>
      <li>Bye</li>
    </ul>
    """
    __slots__ = []

    def attach(cls, template, stream, value, namespaces, pos):
        if type(value) is dict:
            raise TemplateSyntaxError('The content directive can not be used '
                                      'as an element', template.filepath,
                                      *pos[1:])
        expr = cls._parse_expr(value, template, *pos[1:])
        return None, [stream[0], (EXPR, expr, pos),  stream[-1]]
    attach = classmethod(attach)


class DefDirective(Directive):
    """Implementation of the ``py:def`` template directive.
    
    This directive can be used to create "Named Template Functions", which
    are template snippets that are not actually output during normal
    processing, but rather can be expanded from expressions in other places
    in the template.
    
    A named template function can be used just like a normal Python function
    from template expressions:
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <p py:def="echo(greeting, name='world')" class="message">
    ...     ${greeting}, ${name}!
    ...   </p>
    ...   ${echo('Hi', name='you')}
    ... </div>''')
    >>> print tmpl.generate(bar='Bye')
    <div>
      <p class="message">
        Hi, you!
      </p>
    </div>
    
    If a function does not require parameters, the parenthesis can be omitted
    in the definition:
    
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <p py:def="helloworld" class="message">
    ...     Hello, world!
    ...   </p>
    ...   ${helloworld()}
    ... </div>''')
    >>> print tmpl.generate(bar='Bye')
    <div>
      <p class="message">
        Hello, world!
      </p>
    </div>
    """
    __slots__ = ['name', 'args', 'star_args', 'dstar_args', 'defaults']

    def __init__(self, args, template, namespaces=None, lineno=-1, offset=-1):
        Directive.__init__(self, None, template, namespaces, lineno, offset)
        ast = _parse(args).node
        self.args = []
        self.star_args = None
        self.dstar_args = None
        self.defaults = {}
        if isinstance(ast, compiler.ast.CallFunc):
            self.name = ast.node.name
            for arg in ast.args:
                if isinstance(arg, compiler.ast.Keyword):
                    self.args.append(arg.name)
                    self.defaults[arg.name] = Expression(arg.expr,
                                                         template.filepath,
                                                         lineno,
                                                         lookup=template.lookup)
                else:
                    self.args.append(arg.name)
            if ast.star_args:
                self.star_args = ast.star_args.name
            if ast.dstar_args:
                self.dstar_args = ast.dstar_args.name
        else:
            self.name = ast.name

    def attach(cls, template, stream, value, namespaces, pos):
        if type(value) is dict:
            value = value.get('function')
        return super(DefDirective, cls).attach(template, stream, value,
                                               namespaces, pos)
    attach = classmethod(attach)

    def __call__(self, stream, directives, ctxt, **vars):
        stream = list(stream)

        def function(*args, **kwargs):
            scope = {}
            args = list(args) # make mutable
            for name in self.args:
                if args:
                    scope[name] = args.pop(0)
                else:
                    if name in kwargs:
                        val = kwargs.pop(name)
                    else:
                        val = _eval_expr(self.defaults.get(name), ctxt, **vars)
                    scope[name] = val
            if not self.star_args is None:
                scope[self.star_args] = args
            if not self.dstar_args is None:
                scope[self.dstar_args] = kwargs
            ctxt.push(scope)
            for event in _apply_directives(stream, directives, ctxt, **vars):
                yield event
            ctxt.pop()
        try:
            function.__name__ = self.name
        except TypeError:
            # Function name can't be set in Python 2.3 
            pass

        # Store the function reference in the bottom context frame so that it
        # doesn't get popped off before processing the template has finished
        # FIXME: this makes context data mutable as a side-effect
        ctxt.frames[-1][self.name] = function

        return []

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.name)


class ForDirective(Directive):
    """Implementation of the ``py:for`` template directive for repeating an
    element based on an iterable in the context data.
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<ul xmlns:py="http://genshi.edgewall.org/">
    ...   <li py:for="item in items">${item}</li>
    ... </ul>''')
    >>> print tmpl.generate(items=[1, 2, 3])
    <ul>
      <li>1</li><li>2</li><li>3</li>
    </ul>
    """
    __slots__ = ['assign', 'filename']

    def __init__(self, value, template, namespaces=None, lineno=-1, offset=-1):
        if ' in ' not in value:
            raise TemplateSyntaxError('"in" keyword missing in "for" directive',
                                      template.filepath, lineno, offset)
        assign, value = value.split(' in ', 1)
        ast = _parse(assign, 'exec')
        value = 'iter(%s)' % value.strip()
        self.assign = _assignment(ast.node.nodes[0].expr)
        self.filename = template.filepath
        Directive.__init__(self, value, template, namespaces, lineno, offset)

    def attach(cls, template, stream, value, namespaces, pos):
        if type(value) is dict:
            value = value.get('each')
        return super(ForDirective, cls).attach(template, stream, value,
                                               namespaces, pos)
    attach = classmethod(attach)

    def __call__(self, stream, directives, ctxt, **vars):
        iterable = _eval_expr(self.expr, ctxt, **vars)
        if iterable is None:
            return

        assign = self.assign
        scope = {}
        stream = list(stream)
        for item in iterable:
            assign(scope, item)
            ctxt.push(scope)
            for event in _apply_directives(stream, directives, ctxt, **vars):
                yield event
            ctxt.pop()

    def __repr__(self):
        return '<%s>' % self.__class__.__name__


class IfDirective(Directive):
    """Implementation of the ``py:if`` template directive for conditionally
    excluding elements from being output.
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <b py:if="foo">${bar}</b>
    ... </div>''')
    >>> print tmpl.generate(foo=True, bar='Hello')
    <div>
      <b>Hello</b>
    </div>
    """
    __slots__ = []

    def attach(cls, template, stream, value, namespaces, pos):
        if type(value) is dict:
            value = value.get('test')
        return super(IfDirective, cls).attach(template, stream, value,
                                              namespaces, pos)
    attach = classmethod(attach)

    def __call__(self, stream, directives, ctxt, **vars):
        value = _eval_expr(self.expr, ctxt, **vars)
        if value:
            return _apply_directives(stream, directives, ctxt, **vars)
        return []


class MatchDirective(Directive):
    """Implementation of the ``py:match`` template directive.

    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <span py:match="greeting">
    ...     Hello ${select('@name')}
    ...   </span>
    ...   <greeting name="Dude" />
    ... </div>''')
    >>> print tmpl.generate()
    <div>
      <span>
        Hello Dude
      </span>
    </div>
    """
    __slots__ = ['path', 'namespaces', 'hints']

    def __init__(self, value, template, hints=None, namespaces=None,
                 lineno=-1, offset=-1):
        Directive.__init__(self, None, template, namespaces, lineno, offset)
        self.path = Path(value, template.filepath, lineno)
        self.namespaces = namespaces or {}
        self.hints = hints or ()

    def attach(cls, template, stream, value, namespaces, pos):
        hints = []
        if type(value) is dict:
            if value.get('buffer', '').lower() == 'false':
                hints.append('not_buffered')
            if value.get('once', '').lower() == 'true':
                hints.append('match_once')
            if value.get('recursive', '').lower() == 'false':
                hints.append('not_recursive')
            value = value.get('path')
        return cls(value, template, frozenset(hints), namespaces, *pos[1:]), \
               stream
    attach = classmethod(attach)

    def __call__(self, stream, directives, ctxt, **vars):
        ctxt._match_templates.append((self.path.test(ignore_context=True),
                                      self.path, list(stream), self.hints,
                                      self.namespaces, directives))
        return []

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.path.source)


class ReplaceDirective(Directive):
    """Implementation of the ``py:replace`` template directive.
    
    This directive replaces the element with the result of evaluating the
    value of the ``py:replace`` attribute:
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <span py:replace="bar">Hello</span>
    ... </div>''')
    >>> print tmpl.generate(bar='Bye')
    <div>
      Bye
    </div>
    
    This directive is equivalent to ``py:content`` combined with ``py:strip``,
    providing a less verbose way to achieve the same effect:
    
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <span py:content="bar" py:strip="">Hello</span>
    ... </div>''')
    >>> print tmpl.generate(bar='Bye')
    <div>
      Bye
    </div>
    """
    __slots__ = []

    def attach(cls, template, stream, value, namespaces, pos):
        if type(value) is dict:
            value = value.get('value')
        if not value:
            raise TemplateSyntaxError('missing value for "replace" directive',
                                      template.filepath, *pos[1:])
        expr = cls._parse_expr(value, template, *pos[1:])
        return None, [(EXPR, expr, pos)]
    attach = classmethod(attach)


class StripDirective(Directive):
    """Implementation of the ``py:strip`` template directive.
    
    When the value of the ``py:strip`` attribute evaluates to ``True``, the
    element is stripped from the output
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <div py:strip="True"><b>foo</b></div>
    ... </div>''')
    >>> print tmpl.generate()
    <div>
      <b>foo</b>
    </div>
    
    Leaving the attribute value empty is equivalent to a truth value.
    
    This directive is particulary interesting for named template functions or
    match templates that do not generate a top-level element:
    
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <div py:def="echo(what)" py:strip="">
    ...     <b>${what}</b>
    ...   </div>
    ...   ${echo('foo')}
    ... </div>''')
    >>> print tmpl.generate()
    <div>
        <b>foo</b>
    </div>
    """
    __slots__ = []

    def __call__(self, stream, directives, ctxt, **vars):
        def _generate():
            if _eval_expr(self.expr, ctxt, **vars):
                stream.next() # skip start tag
                previous = stream.next()
                for event in stream:
                    yield previous
                    previous = event
            else:
                for event in stream:
                    yield event
        return _apply_directives(_generate(), directives, ctxt, **vars)

    def attach(cls, template, stream, value, namespaces, pos):
        if not value:
            return None, stream[1:-1]
        return super(StripDirective, cls).attach(template, stream, value,
                                                 namespaces, pos)
    attach = classmethod(attach)


class ChooseDirective(Directive):
    """Implementation of the ``py:choose`` directive for conditionally selecting
    one of several body elements to display.
    
    If the ``py:choose`` expression is empty the expressions of nested
    ``py:when`` directives are tested for truth.  The first true ``py:when``
    body is output. If no ``py:when`` directive is matched then the fallback
    directive ``py:otherwise`` will be used.
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/"
    ...   py:choose="">
    ...   <span py:when="0 == 1">0</span>
    ...   <span py:when="1 == 1">1</span>
    ...   <span py:otherwise="">2</span>
    ... </div>''')
    >>> print tmpl.generate()
    <div>
      <span>1</span>
    </div>
    
    If the ``py:choose`` directive contains an expression, the nested
    ``py:when`` directives are tested for equality to the ``py:choose``
    expression:
    
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/"
    ...   py:choose="2">
    ...   <span py:when="1">1</span>
    ...   <span py:when="2">2</span>
    ... </div>''')
    >>> print tmpl.generate()
    <div>
      <span>2</span>
    </div>
    
    Behavior is undefined if a ``py:choose`` block contains content outside a
    ``py:when`` or ``py:otherwise`` block.  Behavior is also undefined if a
    ``py:otherwise`` occurs before ``py:when`` blocks.
    """
    __slots__ = ['matched', 'value']

    def attach(cls, template, stream, value, namespaces, pos):
        if type(value) is dict:
            value = value.get('test')
        return super(ChooseDirective, cls).attach(template, stream, value,
                                                  namespaces, pos)
    attach = classmethod(attach)

    def __call__(self, stream, directives, ctxt, **vars):
        info = [False, bool(self.expr), None]
        if self.expr:
            info[2] = _eval_expr(self.expr, ctxt, **vars)
        ctxt._choice_stack.append(info)
        for event in _apply_directives(stream, directives, ctxt, **vars):
            yield event
        ctxt._choice_stack.pop()


class WhenDirective(Directive):
    """Implementation of the ``py:when`` directive for nesting in a parent with
    the ``py:choose`` directive.
    
    See the documentation of the `ChooseDirective` for usage.
    """
    __slots__ = ['filename']

    def __init__(self, value, template, namespaces=None, lineno=-1, offset=-1):
        Directive.__init__(self, value, template, namespaces, lineno, offset)
        self.filename = template.filepath

    def attach(cls, template, stream, value, namespaces, pos):
        if type(value) is dict:
            value = value.get('test')
        return super(WhenDirective, cls).attach(template, stream, value,
                                                namespaces, pos)
    attach = classmethod(attach)

    def __call__(self, stream, directives, ctxt, **vars):
        info = ctxt._choice_stack and ctxt._choice_stack[-1]
        if not info:
            raise TemplateRuntimeError('"when" directives can only be used '
                                       'inside a "choose" directive',
                                       self.filename, *stream.next()[2][1:])
        if info[0]:
            return []
        if not self.expr and not info[1]:
            raise TemplateRuntimeError('either "choose" or "when" directive '
                                       'must have a test expression',
                                       self.filename, *stream.next()[2][1:])
        if info[1]:
            value = info[2]
            if self.expr:
                matched = value == _eval_expr(self.expr, ctxt, **vars)
            else:
                matched = bool(value)
        else:
            matched = bool(_eval_expr(self.expr, ctxt, **vars))
        info[0] = matched
        if not matched:
            return []

        return _apply_directives(stream, directives, ctxt, **vars)


class OtherwiseDirective(Directive):
    """Implementation of the ``py:otherwise`` directive for nesting in a parent
    with the ``py:choose`` directive.
    
    See the documentation of `ChooseDirective` for usage.
    """
    __slots__ = ['filename']

    def __init__(self, value, template, namespaces=None, lineno=-1, offset=-1):
        Directive.__init__(self, None, template, namespaces, lineno, offset)
        self.filename = template.filepath

    def __call__(self, stream, directives, ctxt, **vars):
        info = ctxt._choice_stack and ctxt._choice_stack[-1]
        if not info:
            raise TemplateRuntimeError('an "otherwise" directive can only be '
                                       'used inside a "choose" directive',
                                       self.filename, *stream.next()[2][1:])
        if info[0]:
            return []
        info[0] = True

        return _apply_directives(stream, directives, ctxt, **vars)


class WithDirective(Directive):
    """Implementation of the ``py:with`` template directive, which allows
    shorthand access to variables and expressions.
    
    >>> from genshi.template import MarkupTemplate
    >>> tmpl = MarkupTemplate('''<div xmlns:py="http://genshi.edgewall.org/">
    ...   <span py:with="y=7; z=x+10">$x $y $z</span>
    ... </div>''')
    >>> print tmpl.generate(x=42)
    <div>
      <span>42 7 52</span>
    </div>
    """
    __slots__ = ['vars']

    def __init__(self, value, template, namespaces=None, lineno=-1, offset=-1):
        Directive.__init__(self, None, template, namespaces, lineno, offset)
        self.vars = [] 
        value = value.strip() 
        try:
            ast = _parse(value, 'exec').node 
            for node in ast.nodes: 
                if isinstance(node, compiler.ast.Discard): 
                    continue 
                elif not isinstance(node, compiler.ast.Assign): 
                    raise TemplateSyntaxError('only assignment allowed in ' 
                                              'value of the "with" directive', 
                                              template.filepath, lineno, offset) 
                self.vars.append(([_assignment(n) for n in node.nodes], 
                                  Expression(node.expr, template.filepath, 
                                             lineno, lookup=template.lookup))) 
        except SyntaxError, err:
            err.msg += ' in expression "%s" of "%s" directive' % (value,
                                                                  self.tagname)
            raise TemplateSyntaxError(err, template.filepath, lineno,
                                      offset + (err.offset or 0))

    def attach(cls, template, stream, value, namespaces, pos):
        if type(value) is dict:
            value = value.get('vars')
        return super(WithDirective, cls).attach(template, stream, value,
                                                namespaces, pos)
    attach = classmethod(attach)

    def __call__(self, stream, directives, ctxt, **vars):
        frame = {}
        ctxt.push(frame)
        for targets, expr in self.vars: 
            value = _eval_expr(expr, ctxt, **vars)
            for assign in targets:
                assign(frame, value)
        for event in _apply_directives(stream, directives, ctxt, **vars):
            yield event
        ctxt.pop()

    def __repr__(self):
        return '<%s>' % (self.__class__.__name__)
