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

"""Support for "safe" evaluation of Python expressions."""

import __builtin__
from compiler import ast, parse
from compiler.pycodegen import ExpressionCodeGenerator, ModuleCodeGenerator
import new
try:
    set
except NameError:
    from sets import ImmutableSet as frozenset
    from sets import Set as set
from textwrap import dedent

from calibre.utils.genshi.core import Markup
from calibre.utils.genshi.template.base import TemplateRuntimeError
from calibre.utils.genshi.util import flatten

__all__ = ['Code', 'Expression', 'Suite', 'LenientLookup', 'StrictLookup',
           'Undefined', 'UndefinedError']
__docformat__ = 'restructuredtext en'

# Check for a Python 2.4 bug in the eval loop
has_star_import_bug = False
try:
    class _FakeMapping(object):
        __getitem__ = __setitem__ = lambda *a: None
    exec 'from sys import *' in {}, _FakeMapping()
except SystemError:
    has_star_import_bug = True
except TypeError:
    pass # Python 2.3
del _FakeMapping

def _star_import_patch(mapping, modname):
    """This function is used as helper if a Python version with a broken
    star-import opcode is in use.
    """
    module = __import__(modname, None, None, ['__all__'])
    if hasattr(module, '__all__'):
        members = module.__all__
    else:
        members = [x for x in module.__dict__ if not x.startswith('_')]
    mapping.update([(name, getattr(module, name)) for name in members])


class Code(object):
    """Abstract base class for the `Expression` and `Suite` classes."""
    __slots__ = ['source', 'code', 'ast', '_globals']

    def __init__(self, source, filename=None, lineno=-1, lookup='strict',
                 xform=None):
        """Create the code object, either from a string, or from an AST node.
        
        :param source: either a string containing the source code, or an AST
                       node
        :param filename: the (preferably absolute) name of the file containing
                         the code
        :param lineno: the number of the line on which the code was found
        :param lookup: the lookup class that defines how variables are looked
                       up in the context; can be either "strict" (the default),
                       "lenient", or a custom lookup class
        :param xform: the AST transformer that should be applied to the code;
                      if `None`, the appropriate transformation is chosen
                      depending on the mode
        """
        if isinstance(source, basestring):
            self.source = source
            node = _parse(source, mode=self.mode)
        else:
            assert isinstance(source, ast.Node), \
                'Expected string or AST node, but got %r' % source
            self.source = '?'
            if self.mode == 'eval':
                node = ast.Expression(source)
            else:
                node = ast.Module(None, source)

        self.ast = node
        self.code = _compile(node, self.source, mode=self.mode,
                             filename=filename, lineno=lineno, xform=xform)
        if lookup is None:
            lookup = LenientLookup
        elif isinstance(lookup, basestring):
            lookup = {'lenient': LenientLookup, 'strict': StrictLookup}[lookup]
        self._globals = lookup.globals

    def __getstate__(self):
        state = {'source': self.source, 'ast': self.ast,
                 'lookup': self._globals.im_self}
        c = self.code
        state['code'] = (c.co_nlocals, c.co_stacksize, c.co_flags, c.co_code,
                         c.co_consts, c.co_names, c.co_varnames, c.co_filename,
                         c.co_name, c.co_firstlineno, c.co_lnotab, (), ())
        return state

    def __setstate__(self, state):
        self.source = state['source']
        self.ast = state['ast']
        self.code = new.code(0, *state['code'])
        self._globals = state['lookup'].globals

    def __eq__(self, other):
        return (type(other) == type(self)) and (self.code == other.code)

    def __hash__(self):
        return hash(self.code)

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.source)


class Expression(Code):
    """Evaluates Python expressions used in templates.

    >>> data = dict(test='Foo', items=[1, 2, 3], dict={'some': 'thing'})
    >>> Expression('test').evaluate(data)
    'Foo'

    >>> Expression('items[0]').evaluate(data)
    1
    >>> Expression('items[-1]').evaluate(data)
    3
    >>> Expression('dict["some"]').evaluate(data)
    'thing'
    
    Similar to e.g. Javascript, expressions in templates can use the dot
    notation for attribute access to access items in mappings:
    
    >>> Expression('dict.some').evaluate(data)
    'thing'
    
    This also works the other way around: item access can be used to access
    any object attribute:
    
    >>> class MyClass(object):
    ...     myattr = 'Bar'
    >>> data = dict(mine=MyClass(), key='myattr')
    >>> Expression('mine.myattr').evaluate(data)
    'Bar'
    >>> Expression('mine["myattr"]').evaluate(data)
    'Bar'
    >>> Expression('mine[key]').evaluate(data)
    'Bar'
    
    All of the standard Python operators are available to template expressions.
    Built-in functions such as ``len()`` are also available in template
    expressions:
    
    >>> data = dict(items=[1, 2, 3])
    >>> Expression('len(items)').evaluate(data)
    3
    """
    __slots__ = []
    mode = 'eval'

    def evaluate(self, data):
        """Evaluate the expression against the given data dictionary.
        
        :param data: a mapping containing the data to evaluate against
        :return: the result of the evaluation
        """
        __traceback_hide__ = 'before_and_this'
        _globals = self._globals(data)
        code = self.code
        if not isinstance(code, unicode) and isinstance(code, basestring):
            code = code.decode('utf-8', 'replace')
        return eval(code, _globals, {'__data__': data})


class Suite(Code):
    """Executes Python statements used in templates.

    >>> data = dict(test='Foo', items=[1, 2, 3], dict={'some': 'thing'})
    >>> Suite("foo = dict['some']").execute(data)
    >>> data['foo']
    'thing'
    """
    __slots__ = []
    mode = 'exec'

    def execute(self, data):
        """Execute the suite in the given data dictionary.
        
        :param data: a mapping containing the data to execute in
        """
        __traceback_hide__ = 'before_and_this'
        _globals = self._globals(data)
        exec self.code in _globals, data


UNDEFINED = object()


class UndefinedError(TemplateRuntimeError):
    """Exception thrown when a template expression attempts to access a variable
    not defined in the context.
    
    :see: `LenientLookup`, `StrictLookup`
    """
    def __init__(self, name, owner=UNDEFINED):
        if owner is not UNDEFINED:
            message = '%s has no member named "%s"' % (repr(owner), name)
        else:
            message = '"%s" not defined' % name
        TemplateRuntimeError.__init__(self, message)


class Undefined(object):
    """Represents a reference to an undefined variable.
    
    Unlike the Python runtime, template expressions can refer to an undefined
    variable without causing a `NameError` to be raised. The result will be an
    instance of the `Undefined` class, which is treated the same as ``False`` in
    conditions, but raise an exception on any other operation:
    
    >>> foo = Undefined('foo')
    >>> bool(foo)
    False
    >>> list(foo)
    []
    >>> print foo
    undefined
    
    However, calling an undefined variable, or trying to access an attribute
    of that variable, will raise an exception that includes the name used to
    reference that undefined variable.
    
    >>> foo('bar')
    Traceback (most recent call last):
        ...
    UndefinedError: "foo" not defined

    >>> foo.bar
    Traceback (most recent call last):
        ...
    UndefinedError: "foo" not defined
    
    :see: `LenientLookup`
    """
    __slots__ = ['_name', '_owner']

    def __init__(self, name, owner=UNDEFINED):
        """Initialize the object.
        
        :param name: the name of the reference
        :param owner: the owning object, if the variable is accessed as a member
        """
        self._name = name
        self._owner = owner

    def __iter__(self):
        return iter([])

    def __nonzero__(self):
        return False

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self._name)

    def __str__(self):
        return 'undefined'

    def _die(self, *args, **kwargs):
        """Raise an `UndefinedError`."""
        __traceback_hide__ = True
        raise UndefinedError(self._name, self._owner)
    __call__ = __getattr__ = __getitem__ = _die


class LookupBase(object):
    """Abstract base class for variable lookup implementations."""

    def globals(cls, data):
        """Construct the globals dictionary to use as the execution context for
        the expression or suite.
        """
        return {
            '__data__': data,
            '_lookup_name': cls.lookup_name,
            '_lookup_attr': cls.lookup_attr,
            '_lookup_item': cls.lookup_item,
            '_star_import_patch': _star_import_patch,
            'UndefinedError': UndefinedError,
        }
    globals = classmethod(globals)

    def lookup_name(cls, data, name):
        __traceback_hide__ = True
        val = data.get(name, UNDEFINED)
        if val is UNDEFINED:
            val = BUILTINS.get(name, val)
            if val is UNDEFINED:
                val = cls.undefined(name)
        return val
    lookup_name = classmethod(lookup_name)

    def lookup_attr(cls, obj, key):
        __traceback_hide__ = True
        try:
            val = getattr(obj, key)
        except AttributeError:
            if hasattr(obj.__class__, key):
                raise
            else:
                try:
                    val = obj[key]
                except (KeyError, TypeError):
                    val = cls.undefined(key, owner=obj)
        return val
    lookup_attr = classmethod(lookup_attr)

    def lookup_item(cls, obj, key):
        __traceback_hide__ = True
        if len(key) == 1:
            key = key[0]
        try:
            return obj[key]
        except (AttributeError, KeyError, IndexError, TypeError), e:
            if isinstance(key, basestring):
                val = getattr(obj, key, UNDEFINED)
                if val is UNDEFINED:
                    val = cls.undefined(key, owner=obj)
                return val
            raise
    lookup_item = classmethod(lookup_item)

    def undefined(cls, key, owner=UNDEFINED):
        """Can be overridden by subclasses to specify behavior when undefined
        variables are accessed.
        
        :param key: the name of the variable
        :param owner: the owning object, if the variable is accessed as a member
        """
        raise NotImplementedError
    undefined = classmethod(undefined)


class LenientLookup(LookupBase):
    """Default variable lookup mechanism for expressions.
    
    When an undefined variable is referenced using this lookup style, the
    reference evaluates to an instance of the `Undefined` class:
    
    >>> expr = Expression('nothing', lookup='lenient')
    >>> undef = expr.evaluate({})
    >>> undef
    <Undefined 'nothing'>
    
    The same will happen when a non-existing attribute or item is accessed on
    an existing object:
    
    >>> expr = Expression('something.nil', lookup='lenient')
    >>> expr.evaluate({'something': dict()})
    <Undefined 'nil'>
    
    See the documentation of the `Undefined` class for details on the behavior
    of such objects.
    
    :see: `StrictLookup`
    """
    def undefined(cls, key, owner=UNDEFINED):
        """Return an ``Undefined`` object."""
        __traceback_hide__ = True
        return Undefined(key, owner=owner)
    undefined = classmethod(undefined)


class StrictLookup(LookupBase):
    """Strict variable lookup mechanism for expressions.
    
    Referencing an undefined variable using this lookup style will immediately
    raise an ``UndefinedError``:
    
    >>> expr = Expression('nothing', lookup='strict')
    >>> expr.evaluate({})
    Traceback (most recent call last):
        ...
    UndefinedError: "nothing" not defined
    
    The same happens when a non-existing attribute or item is accessed on an
    existing object:
    
    >>> expr = Expression('something.nil', lookup='strict')
    >>> expr.evaluate({'something': dict()})
    Traceback (most recent call last):
        ...
    UndefinedError: {} has no member named "nil"
    """
    def undefined(cls, key, owner=UNDEFINED):
        """Raise an ``UndefinedError`` immediately."""
        __traceback_hide__ = True
        raise UndefinedError(key, owner=owner)
    undefined = classmethod(undefined)


def _parse(source, mode='eval'):
    source = source.strip()
    if mode == 'exec':
        lines = [line.expandtabs() for line in source.splitlines()]
        if lines:
            first = lines[0]
            rest = dedent('\n'.join(lines[1:])).rstrip()
            if first.rstrip().endswith(':') and not rest[0].isspace():
                rest = '\n'.join(['    %s' % line for line in rest.splitlines()])
            source = '\n'.join([first, rest])
    if isinstance(source, unicode):
        source = '\xef\xbb\xbf' + source.encode('utf-8')
    return parse(source, mode)

def _compile(node, source=None, mode='eval', filename=None, lineno=-1,
             xform=None):
    if xform is None:
        xform = {'eval': ExpressionASTTransformer}.get(mode,
                                                       TemplateASTTransformer)
    tree = xform().visit(node)
    if isinstance(filename, unicode):
        # unicode file names not allowed for code objects
        filename = filename.encode('utf-8', 'replace')
    elif not filename:
        filename = '<string>'
    tree.filename = filename
    if lineno <= 0:
        lineno = 1

    if mode == 'eval':
        gen = ExpressionCodeGenerator(tree)
        name = '<Expression %r>' % (source or '?')
    else:
        gen = ModuleCodeGenerator(tree)
        lines = source.splitlines()
        if not lines:
            extract = ''
        else:
            extract = lines[0]
        if len(lines) > 1:
            extract += ' ...'
        name = '<Suite %r>' % (extract)
    gen.optimized = True
    code = gen.getCode()

    # We'd like to just set co_firstlineno, but it's readonly. So we need to
    # clone the code object while adjusting the line number
    return new.code(0, code.co_nlocals, code.co_stacksize,
                    code.co_flags | 0x0040, code.co_code, code.co_consts,
                    code.co_names, code.co_varnames, filename, name, lineno,
                    code.co_lnotab, (), ())

BUILTINS = __builtin__.__dict__.copy()
BUILTINS.update({'Markup': Markup, 'Undefined': Undefined})
CONSTANTS = frozenset(['False', 'True', 'None', 'NotImplemented', 'Ellipsis'])


class ASTTransformer(object):
    """General purpose base class for AST transformations.
    
    Every visitor method can be overridden to return an AST node that has been
    altered or replaced in some way.
    """

    def visit(self, node):
        if node is None:
            return None
        if type(node) is tuple:
            return tuple([self.visit(n) for n in node])
        visitor = getattr(self, 'visit%s' % node.__class__.__name__,
                          self._visitDefault)
        return visitor(node)

    def _clone(self, node, *args):
        lineno = getattr(node, 'lineno', None)
        node = node.__class__(*args)
        if lineno is not None:
            node.lineno = lineno
        if isinstance(node, (ast.Class, ast.Function, ast.Lambda)) or \
                hasattr(ast, 'GenExpr') and isinstance(node, ast.GenExpr):
            node.filename = '<string>' # workaround for bug in pycodegen
        return node

    def _visitDefault(self, node):
        return node

    def visitExpression(self, node):
        return self._clone(node, self.visit(node.node))

    def visitModule(self, node):
        return self._clone(node, node.doc, self.visit(node.node))

    def visitStmt(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes])

    # Classes, Functions & Accessors

    def visitCallFunc(self, node):
        return self._clone(node, self.visit(node.node),
            [self.visit(x) for x in node.args],
            node.star_args and self.visit(node.star_args) or None,
            node.dstar_args and self.visit(node.dstar_args) or None
        )

    def visitClass(self, node):
        return self._clone(node, node.name, [self.visit(x) for x in node.bases],
            node.doc, self.visit(node.code)
        )

    def visitFrom(self, node):
        if not has_star_import_bug or node.names != [('*', None)]:
            # This is a Python 2.4 bug. Only if we have a broken Python
            # version we have to apply the hack
            return node
        new_node = ast.Discard(ast.CallFunc(
            ast.Name('_star_import_patch'),
            [ast.Name('__data__'), ast.Const(node.modname)], None, None
        ))
        if hasattr(node, 'lineno'): # No lineno in Python 2.3
            new_node.lineno = node.lineno
        return new_node

    def visitFunction(self, node):
        args = []
        if hasattr(node, 'decorators'):
            args.append(self.visit(node.decorators))
        return self._clone(node, *args + [
            node.name,
            node.argnames,
            [self.visit(x) for x in node.defaults],
            node.flags,
            node.doc,
            self.visit(node.code)
        ])

    def visitGetattr(self, node):
        return self._clone(node, self.visit(node.expr), node.attrname)

    def visitLambda(self, node):
        node = self._clone(node, node.argnames,
            [self.visit(x) for x in node.defaults], node.flags,
            self.visit(node.code)
        )
        return node

    def visitSubscript(self, node):
        return self._clone(node, self.visit(node.expr), node.flags,
            [self.visit(x) for x in node.subs]
        )

    # Statements

    def visitAssert(self, node):
        return self._clone(node, self.visit(node.test), self.visit(node.fail))

    def visitAssign(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes],
            self.visit(node.expr)
        )

    def visitAssAttr(self, node):
        return self._clone(node, self.visit(node.expr), node.attrname,
            node.flags
        )

    def visitAugAssign(self, node):
        return self._clone(node, self.visit(node.node), node.op,
            self.visit(node.expr)
        )

    def visitDecorators(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes])

    def visitExec(self, node):
        return self._clone(node, self.visit(node.expr), self.visit(node.locals),
            self.visit(node.globals)
        )

    def visitFor(self, node):
        return self._clone(node, self.visit(node.assign), self.visit(node.list),
            self.visit(node.body), self.visit(node.else_)
        )

    def visitIf(self, node):
        return self._clone(node, [self.visit(x) for x in node.tests],
            self.visit(node.else_)
        )

    def _visitPrint(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes],
            self.visit(node.dest)
        )
    visitPrint = visitPrintnl = _visitPrint

    def visitRaise(self, node):
        return self._clone(node, self.visit(node.expr1), self.visit(node.expr2),
            self.visit(node.expr3)
        )

    def visitReturn(self, node):
        return self._clone(node, self.visit(node.value))

    def visitTryExcept(self, node):
        return self._clone(node, self.visit(node.body), self.visit(node.handlers),
            self.visit(node.else_)
        )

    def visitTryFinally(self, node):
        return self._clone(node, self.visit(node.body), self.visit(node.final))

    def visitWhile(self, node):
        return self._clone(node, self.visit(node.test), self.visit(node.body),
            self.visit(node.else_)
        )

    def visitWith(self, node):
        return self._clone(node, self.visit(node.expr),
            [self.visit(x) for x in node.vars], self.visit(node.body)
        )

    def visitYield(self, node):
        return self._clone(node, self.visit(node.value))

    # Operators

    def _visitBoolOp(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes])
    visitAnd = visitOr = visitBitand = visitBitor = visitBitxor = _visitBoolOp
    visitAssTuple = visitAssList = _visitBoolOp

    def _visitBinOp(self, node):
        return self._clone(node,
            (self.visit(node.left), self.visit(node.right))
        )
    visitAdd = visitSub = _visitBinOp
    visitDiv = visitFloorDiv = visitMod = visitMul = visitPower = _visitBinOp
    visitLeftShift = visitRightShift = _visitBinOp

    def visitCompare(self, node):
        return self._clone(node, self.visit(node.expr),
            [(op, self.visit(n)) for op, n in  node.ops]
        )

    def _visitUnaryOp(self, node):
        return self._clone(node, self.visit(node.expr))
    visitUnaryAdd = visitUnarySub = visitNot = visitInvert = _visitUnaryOp
    visitBackquote = visitDiscard = _visitUnaryOp

    def visitIfExp(self, node):
        return self._clone(node, self.visit(node.test), self.visit(node.then),
            self.visit(node.else_)
        )

    # Identifiers, Literals and Comprehensions

    def visitDict(self, node):
        return self._clone(node, 
            [(self.visit(k), self.visit(v)) for k, v in node.items]
        )

    def visitGenExpr(self, node):
        return self._clone(node, self.visit(node.code))

    def visitGenExprFor(self, node):
        return self._clone(node, self.visit(node.assign), self.visit(node.iter),
            [self.visit(x) for x in node.ifs]
        )

    def visitGenExprIf(self, node):
        return self._clone(node, self.visit(node.test))

    def visitGenExprInner(self, node):
        quals = [self.visit(x) for x in node.quals]
        return self._clone(node, self.visit(node.expr), quals)

    def visitKeyword(self, node):
        return self._clone(node, node.name, self.visit(node.expr))

    def visitList(self, node):
        return self._clone(node, [self.visit(n) for n in node.nodes])

    def visitListComp(self, node):
        quals = [self.visit(x) for x in node.quals]
        return self._clone(node, self.visit(node.expr), quals)

    def visitListCompFor(self, node):
        return self._clone(node, self.visit(node.assign), self.visit(node.list),
            [self.visit(x) for x in node.ifs]
        )

    def visitListCompIf(self, node):
        return self._clone(node, self.visit(node.test))

    def visitSlice(self, node):
        return self._clone(node, self.visit(node.expr), node.flags,
            node.lower and self.visit(node.lower) or None,
            node.upper and self.visit(node.upper) or None
        )

    def visitSliceobj(self, node):
        return self._clone(node, [self.visit(x) for x in node.nodes])

    def visitTuple(self, node):
        return self._clone(node, [self.visit(n) for n in node.nodes])


class TemplateASTTransformer(ASTTransformer):
    """Concrete AST transformer that implements the AST transformations needed
    for code embedded in templates.
    """

    def __init__(self):
        self.locals = [CONSTANTS]

    def visitConst(self, node):
        if isinstance(node.value, str):
            try: # If the string is ASCII, return a `str` object
                node.value.decode('ascii')
            except ValueError: # Otherwise return a `unicode` object
                return ast.Const(node.value.decode('utf-8'))
        return node

    def visitAssName(self, node):
        if len(self.locals) > 1:
            self.locals[-1].add(node.name)
        return node

    def visitAugAssign(self, node):
        if isinstance(node.node, ast.Name) \
                and node.node.name not in flatten(self.locals):
            name = node.node.name
            node.node = ast.Subscript(ast.Name('__data__'), 'OP_APPLY',
                                      [ast.Const(name)])
            node.expr = self.visit(node.expr)
            return ast.If([
                (ast.Compare(ast.Const(name), [('in', ast.Name('__data__'))]),
                 ast.Stmt([node]))],
                ast.Stmt([ast.Raise(ast.CallFunc(ast.Name('UndefinedError'),
                                                 [ast.Const(name)]),
                                    None, None)]))
        else:
            return ASTTransformer.visitAugAssign(self, node)

    def visitClass(self, node):
        if len(self.locals) > 1:
            self.locals[-1].add(node.name)
        self.locals.append(set())
        try:
            return ASTTransformer.visitClass(self, node)
        finally:
            self.locals.pop()

    def visitFor(self, node):
        self.locals.append(set())
        try:
            return ASTTransformer.visitFor(self, node)
        finally:
            self.locals.pop()

    def visitFunction(self, node):
        if len(self.locals) > 1:
            self.locals[-1].add(node.name)
        self.locals.append(set(node.argnames))
        try:
            return ASTTransformer.visitFunction(self, node)
        finally:
            self.locals.pop()

    def visitGenExpr(self, node):
        self.locals.append(set())
        try:
            return ASTTransformer.visitGenExpr(self, node)
        finally:
            self.locals.pop()

    def visitLambda(self, node):
        self.locals.append(set(flatten(node.argnames)))
        try:
            return ASTTransformer.visitLambda(self, node)
        finally:
            self.locals.pop()

    def visitListComp(self, node):
        self.locals.append(set())
        try:
            return ASTTransformer.visitListComp(self, node)
        finally:
            self.locals.pop()

    def visitName(self, node):
        # If the name refers to a local inside a lambda, list comprehension, or
        # generator expression, leave it alone
        if node.name not in flatten(self.locals):
            # Otherwise, translate the name ref into a context lookup
            func_args = [ast.Name('__data__'), ast.Const(node.name)]
            node = ast.CallFunc(ast.Name('_lookup_name'), func_args)
        return node


class ExpressionASTTransformer(TemplateASTTransformer):
    """Concrete AST transformer that implements the AST transformations needed
    for code embedded in templates.
    """

    def visitGetattr(self, node):
        return ast.CallFunc(ast.Name('_lookup_attr'), [
            self.visit(node.expr),
            ast.Const(node.attrname)
        ])

    def visitSubscript(self, node):
        return ast.CallFunc(ast.Name('_lookup_item'), [
            self.visit(node.expr),
            ast.Tuple([self.visit(sub) for sub in node.subs])
        ])
