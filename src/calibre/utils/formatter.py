'''
Created on 23 Sep 2010

@author: charles
'''

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, string, traceback

from calibre.constants import DEBUG
from calibre.utils.formatter_functions import formatter_functions

class _Parser(object):
    LEX_OP  = 1
    LEX_ID  = 2
    LEX_STR = 3
    LEX_NUM = 4
    LEX_EOF = 5

    def __init__(self, val, prog, parent):
        self.lex_pos = 0
        self.prog = prog[0]
        if prog[1] != '':
            self.error(_('failed to scan program. Invalid input {0}').format(prog[1]))
        self.parent = parent
        self.parent.locals = {'$':val}

    def error(self, message):
        m = 'Formatter: ' + message + _(' near ')
        if self.lex_pos > 0:
            m = '{0} {1}'.format(m, self.prog[self.lex_pos-1][1])
        elif self.lex_pos < len(self.prog):
            m = '{0} {1}'.format(m, self.prog[self.lex_pos+1][1])
        else:
            m = '{0} {1}'.format(m, _('end of program'))
        raise ValueError(m)

    def token(self):
        if self.lex_pos >= len(self.prog):
            return None
        token = self.prog[self.lex_pos]
        self.lex_pos += 1
        return token[1]

    def lookahead(self):
        if self.lex_pos >= len(self.prog):
            return (self.LEX_EOF, '')
        return self.prog[self.lex_pos]

    def consume(self):
        self.lex_pos += 1

    def token_op_is_a(self, val):
        token = self.lookahead()
        return token[0] == self.LEX_OP and token[1] == val

    def token_is_id(self):
        token = self.lookahead()
        return token[0] == self.LEX_ID

    def token_is_constant(self):
        token = self.lookahead()
        return token[0] == self.LEX_STR or token[0] == self.LEX_NUM

    def token_is_eof(self):
        token = self.lookahead()
        return token[0] == self.LEX_EOF

    def program(self):
        val = self.statement()
        if not self.token_is_eof():
            self.error(_('syntax error - program ends before EOF'))
        return val

    def statement(self):
        while True:
            val = self.expr()
            if self.token_is_eof():
                return val
            if not self.token_op_is_a(';'):
                return val
            self.consume()
            if self.token_is_eof():
                return val

    def expr(self):
        if self.token_is_id():
            funcs = formatter_functions.get_functions()
            # We have an identifier. Determine if it is a function
            id = self.token()
            if not self.token_op_is_a('('):
                if self.token_op_is_a('='):
                    # classic assignment statement
                    self.consume()
                    cls = funcs['assign']
                    return cls.eval(self.parent, self.parent.kwargs,
                                    self.parent.book, self.parent.locals, id, self.expr())
                return self.parent.locals.get(id, _('unknown id ') + id)
            # We have a function.
            # Check if it is a known one. We do this here so error reporting is
            # better, as it can identify the tokens near the problem.

            if id not in funcs:
                self.error(_('unknown function {0}').format(id))
            # Eat the paren
            self.consume()
            args = list()
            while not self.token_op_is_a(')'):
                if id == 'assign' and len(args) == 0:
                    # Must handle the lvalue semantics of the assign function.
                    # The first argument is the name of the destination, not
                    # the value.
                    if not self.token_is_id():
                        self.error('assign requires the first parameter be an id')
                    args.append(self.token())
                else:
                    # evaluate the argument (recursive call)
                    args.append(self.statement())
                if not self.token_op_is_a(','):
                    break
                self.consume()
            if self.token() != ')':
                self.error(_('missing closing parenthesis'))

            # Evaluate the function
            if id in funcs:
                cls = funcs[id]
                if cls.arg_count != -1 and len(args) != cls.arg_count:
                    self.error('incorrect number of arguments for function {}'.format(id))
                return cls.eval(self.parent, self.parent.kwargs,
                                self.parent.book, self.parent.locals, *args)
            else:
                f = self.parent.functions[id]
                if f[0] != -1 and len(args) != f[0]+1:
                    self.error('incorrect number of arguments for function {}'.format(id))
                return f[1](self.parent, *args)
            # can't get here
        elif self.token_is_constant():
            # String or number
            return self.token()
        else:
            self.error(_('expression is not function or constant'))


class TemplateFormatter(string.Formatter):
    '''
    Provides a format function that substitutes '' for any missing value
    '''

    _validation_string = 'This Is Some Text THAT SHOULD be LONG Enough.%^&*'

    # Dict to do recursion detection. It is up the the individual get_value
    # method to use it. It is cleared when starting to format a template
    composite_values = {}

    def __init__(self):
        string.Formatter.__init__(self)
        self.book = None
        self.kwargs = None
        self.program_cache = {}
        self.locals = {}

    def _do_format(self, val, fmt):
        if not fmt or not val:
            return val
        if val == self._validation_string:
            val = '0'
        typ = fmt[-1]
        if typ == 's':
            pass
        elif 'bcdoxXn'.find(typ) >= 0:
            try:
                val = int(val)
            except:
                raise ValueError(
                    _('format: type {0} requires an integer value, got {1}').format(typ, val))
        elif 'eEfFgGn%'.find(typ) >= 0:
            try:
                val = float(val)
            except:
                raise ValueError(
                    _('format: type {0} requires a decimal (float) value, got {1}').format(typ, val))
        return unicode(('{0:'+fmt+'}').format(val))

    def _explode_format_string(self, fmt):
        try:
            matches = self.format_string_re.match(fmt)
            if matches is None or matches.lastindex != 3:
                return fmt, '', ''
            return matches.groups()
        except:
            if DEBUG:
                traceback.print_exc()
            return fmt, '', ''

    format_string_re = re.compile(r'^(.*)\|([^\|]*)\|(.*)$', re.DOTALL)
    compress_spaces = re.compile(r'\s+')
    backslash_comma_to_comma = re.compile(r'\\,')

    arg_parser = re.Scanner([
                (r',', lambda x,t: ''),
                (r'.*?((?<!\\),)', lambda x,t: t[:-1]),
                (r'.*?\)', lambda x,t: t[:-1]),
        ])

    ################## 'Functional' template language ######################

    lex_scanner = re.Scanner([
                (r'[(),=;]',            lambda x,t: (1, t)),
                (r'-?[\d\.]+',          lambda x,t: (3, t)),
                (r'\$',                 lambda x,t: (2, t)),
                (r'\w+',                lambda x,t: (2, t)),
                (r'".*?((?<!\\)")',     lambda x,t: (3, t[1:-1])),
                (r'\'.*?((?<!\\)\')',   lambda x,t: (3, t[1:-1])),
                (r'\n#.*?(?=\n)',       None),
                (r'\s',                 None)
        ], flags=re.DOTALL)

    def _eval_program(self, val, prog):
        # keep a cache of the lex'ed program under the theory that re-lexing
        # is much more expensive than the cache lookup. This is certainly true
        # for more than a few tokens, but it isn't clear for simple programs.
        lprog = self.program_cache.get(prog, None)
        if not lprog:
            lprog = self.lex_scanner.scan(prog)
            self.program_cache[prog] = lprog
        parser = _Parser(val, lprog, self)
        return parser.program()

    ################## Override parent classes methods #####################

    def get_value(self, key, args, kwargs):
        raise Exception('get_value must be implemented in the subclass')

    def format_field(self, val, fmt):
        # ensure we are dealing with a string.
        if isinstance(val, (int, float)):
            if val:
                val = unicode(val)
            else:
                val = ''
        # Handle conditional text
        fmt, prefix, suffix = self._explode_format_string(fmt)

        # Handle functions
        # First see if we have a functional-style expression
        if fmt.startswith('\''):
            p = 0
        else:
            p = fmt.find(':\'')
            if p >= 0:
                p += 1
        if p >= 0 and fmt[-1] == '\'':
            val = self._eval_program(val, fmt[p+1:-1])
            colon = fmt[0:p].find(':')
            if colon < 0:
                dispfmt = ''
            else:
                dispfmt = fmt[0:colon]
        else:
            # check for old-style function references
            p = fmt.find('(')
            dispfmt = fmt
            if p >= 0 and fmt[-1] == ')':
                colon = fmt[0:p].find(':')
                if colon < 0:
                    dispfmt = ''
                    colon = 0
                else:
                    dispfmt = fmt[0:colon]
                    colon += 1

                funcs = formatter_functions.get_functions()
                if fmt[colon:p] in funcs:
                    field = fmt[colon:p]
                    func = funcs[field]
                    if func.arg_count == 2:
                        # only one arg expected. Don't bother to scan. Avoids need
                        # for escaping characters
                        args = [fmt[p+1:-1]]
                    else:
                        args = self.arg_parser.scan(fmt[p+1:])[0]
                        args = [self.backslash_comma_to_comma.sub(',', a) for a in args]
                    if (func.arg_count == 1 and (len(args) != 0)) or \
                            (func.arg_count > 1 and func.arg_count != len(args)+1):
                        print args
                        raise ValueError('Incorrect number of arguments for function '+ fmt[0:p])
                    if func.arg_count == 1:
                        val = func.eval(self, self.kwargs, self.book, self.locals, val).strip()
                    else:
                        val = func.eval(self, self.kwargs, self.book, self.locals,
                                        val, *args).strip()
        if val:
            val = self._do_format(val, dispfmt)
        if not val:
            return ''
        return prefix + val + suffix

    def vformat(self, fmt, args, kwargs):
        if fmt.startswith('program:'):
            ans = self._eval_program(None, fmt[8:])
        else:
            ans = string.Formatter.vformat(self, fmt, args, kwargs)
        return self.compress_spaces.sub(' ', ans).strip()

    ########## a formatter guaranteed not to throw and exception ############

    def safe_format(self, fmt, kwargs, error_value, book):
        self.kwargs = kwargs
        self.book = book
        self.composite_values = {}
        self.locals = {}
        try:
            ans = self.vformat(fmt, [], kwargs).strip()
        except Exception, e:
            if DEBUG:
                traceback.print_exc()
            ans = error_value + ' ' + e.message
        return ans

class ValidateFormatter(TemplateFormatter):
    '''
    Provides a formatter that substitutes the validation string for every value
    '''
    def get_value(self, key, args, kwargs):
        return self._validation_string

    def validate(self, x):
        return self.vformat(x, [], {})

validation_formatter = ValidateFormatter()

class EvalFormatter(TemplateFormatter):
    '''
    A template formatter that uses a simple dict instead of an mi instance
    '''
    def get_value(self, key, args, kwargs):
        key = key.lower()
        return kwargs.get(key, _('No such variable ') + key)

eval_formatter = EvalFormatter()

