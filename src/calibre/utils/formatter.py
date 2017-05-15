'''
Created on 23 Sep 2010

@author: charles
'''

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, string, traceback

from calibre import prints
from calibre.constants import DEBUG
from calibre.utils.formatter_functions import formatter_functions, compile_user_function
from calibre.utils.config import tweaks


class _Parser(object):
    LEX_OP  = 1
    LEX_ID  = 2
    LEX_STR = 3
    LEX_NUM = 4
    LEX_EOF = 5

    LEX_CONSTANTS = frozenset([LEX_STR, LEX_NUM])

    def __init__(self, val, prog, funcs, parent):
        self.lex_pos = 0
        self.prog = prog[0]
        self.prog_len = len(self.prog)
        if prog[1] != '':
            self.error(_('failed to scan program. Invalid input {0}').format(prog[1]))
        self.parent = parent
        self.parent_kwargs = parent.kwargs
        self.parent_book = parent.book
        self.locals = {'$':val}
        self.funcs = funcs

    def error(self, message):
        m = 'Formatter: ' + message + _(' near ')
        if self.lex_pos > 0:
            m = '{0} {1}'.format(m, self.prog[self.lex_pos-1][1])
        elif self.lex_pos < self.prog_len:
            m = '{0} {1}'.format(m, self.prog[self.lex_pos+1][1])
        else:
            m = '{0} {1}'.format(m, _('end of program'))
        raise ValueError(m)

    def token(self):
        if self.lex_pos >= self.prog_len:
            return None
        token = self.prog[self.lex_pos][1]
        self.lex_pos += 1
        return token

    def consume(self):
        self.lex_pos += 1

    def token_op_is_a_equals(self):
        if self.lex_pos >= self.prog_len:
            return False
        token = self.prog[self.lex_pos]
        return token[0] == self.LEX_OP and token[1] == '='

    def token_op_is_a_lparen(self):
        if self.lex_pos >= self.prog_len:
            return False
        token = self.prog[self.lex_pos]
        return token[0] == self.LEX_OP and token[1] == '('

    def token_op_is_a_rparen(self):
        if self.lex_pos >= self.prog_len:
            return False
        token = self.prog[self.lex_pos]
        return token[0] == self.LEX_OP and token[1] == ')'

    def token_op_is_a_comma(self):
        if self.lex_pos >= self.prog_len:
            return False
        token = self.prog[self.lex_pos]
        return token[0] == self.LEX_OP and token[1] == ','

    def token_op_is_a_semicolon(self):
        if self.lex_pos >= self.prog_len:
            return False
        token = self.prog[self.lex_pos]
        return token[0] == self.LEX_OP and token[1] == ';'

    def token_is_id(self):
        if self.lex_pos >= self.prog_len:
            return False
        return self.prog[self.lex_pos][0] == self.LEX_ID

    def token_is_constant(self):
        if self.lex_pos >= self.prog_len:
            return False
        return self.prog[self.lex_pos][0] in self.LEX_CONSTANTS

    def token_is_eof(self):
        if self.lex_pos >= self.prog_len:
            return True
        token = self.prog[self.lex_pos]
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
            if not self.token_op_is_a_semicolon():
                return val
            self.consume()
            if self.token_is_eof():
                return val

    def expr(self):
        if self.token_is_id():
            # We have an identifier. Determine if it is a function
            id = self.token()
            if not self.token_op_is_a_lparen():
                if self.token_op_is_a_equals():
                    # classic assignment statement
                    self.consume()
                    cls = self.funcs['assign']
                    return cls.eval_(self.parent, self.parent_kwargs,
                                    self.parent_book, self.locals, id, self.expr())
                val = self.locals.get(id, None)
                if val is None:
                    self.error(_('Unknown identifier ') + id)
                return val
            # We have a function.
            # Check if it is a known one. We do this here so error reporting is
            # better, as it can identify the tokens near the problem.
            id = id.strip()
            if id not in self.funcs:
                self.error(_('unknown function {0}').format(id))

            # Eat the paren
            self.consume()
            args = list()
            while not self.token_op_is_a_rparen():
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
                if not self.token_op_is_a_comma():
                    break
                self.consume()
            if self.token() != ')':
                self.error(_('missing closing parenthesis'))

            # Evaluate the function
            cls = self.funcs[id]
            if cls.arg_count != -1 and len(args) != cls.arg_count:
                self.error('incorrect number of arguments for function {}'.format(id))
            return cls.eval_(self.parent, self.parent_kwargs,
                            self.parent_book, self.locals, *args)
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

    # Dict to do recursion detection. It is up to the individual get_value
    # method to use it. It is cleared when starting to format a template
    composite_values = {}

    def __init__(self):
        string.Formatter.__init__(self)
        self.book = None
        self.kwargs = None
        self.strip_results = True
        self.locals = {}
        self.funcs = formatter_functions().get_functions()

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

    # ################# 'Functional' template language ######################

    lex_scanner = re.Scanner([
                (r'[(),=;]', lambda x,t: (1, t)),
                (r'-?[\d\.]+', lambda x,t: (3, t)),
                (r'\$', lambda x,t: (2, t)),
                (r'\w+', lambda x,t: (2, t)),
                (r'".*?((?<!\\)")', lambda x,t: (3, t[1:-1])),
                (r'\'.*?((?<!\\)\')', lambda x,t: (3, t[1:-1])),
                (r'\n#.*?(?:(?=\n)|$)', None),
                (r'\s',                 None)
        ], flags=re.DOTALL)

    def _eval_program(self, val, prog, column_name):
        # keep a cache of the lex'ed program under the theory that re-lexing
        # is much more expensive than the cache lookup. This is certainly true
        # for more than a few tokens, but it isn't clear for simple programs.
        if column_name is not None and self.template_cache is not None:
            lprog = self.template_cache.get(column_name, None)
            if not lprog:
                lprog = self.lex_scanner.scan(prog)
                self.template_cache[column_name] = lprog
        else:
            lprog = self.lex_scanner.scan(prog)
        parser = _Parser(val, lprog, self.funcs, self)
        return parser.program()

    # ################# Override parent classes methods #####################

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
            val = self._eval_program(val, fmt[p+1:-1], None)
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

                fname = fmt[colon:p].strip()
                if fname in self.funcs:
                    func = self.funcs[fname]
                    if func.arg_count == 2:
                        # only one arg expected. Don't bother to scan. Avoids need
                        # for escaping characters
                        args = [fmt[p+1:-1]]
                    else:
                        args = self.arg_parser.scan(fmt[p+1:])[0]
                        args = [self.backslash_comma_to_comma.sub(',', a) for a in args]
                    if (func.arg_count == 1 and (len(args) != 1 or args[0])) or \
                            (func.arg_count > 1 and func.arg_count != len(args)+1):
                        raise ValueError('Incorrect number of arguments for function '+ fmt[0:p])
                    if func.arg_count == 1:
                        val = func.eval_(self, self.kwargs, self.book, self.locals, val)
                        if self.strip_results:
                            val = val.strip()
                    else:
                        val = func.eval_(self, self.kwargs, self.book, self.locals, val, *args)
                        if self.strip_results:
                            val = val.strip()
                else:
                    return _('%s: unknown function')%fname
        if val:
            val = self._do_format(val, dispfmt)
        if not val:
            return ''
        return prefix + val + suffix

    def evaluate(self, fmt, args, kwargs):
        if fmt.startswith('program:'):
            ans = self._eval_program(kwargs.get('$', None), fmt[8:], self.column_name)
        else:
            ans = self.vformat(fmt, args, kwargs)
        if self.strip_results:
            return self.compress_spaces.sub(' ', ans).strip()
        return ans

    # ######### a formatter that throws exceptions ############

    def unsafe_format(self, fmt, kwargs, book, strip_results=True):
        self.strip_results = strip_results
        self.column_name = self.template_cache = None
        self.kwargs = kwargs
        self.book = book
        self.composite_values = {}
        self.locals = {}
        return self.evaluate(fmt, [], kwargs)

    # ######### a formatter guaranteed not to throw an exception ############

    def safe_format(self, fmt, kwargs, error_value, book,
                    column_name=None, template_cache=None,
                    strip_results=True, user_functions=None):
        self.strip_results = strip_results
        self.column_name = column_name
        self.template_cache = template_cache
        self.kwargs = kwargs
        self.book = book
        if user_functions:
            self.funcs = formatter_functions().get_builtins().copy()
            self.funcs.update(user_functions)
        self.composite_values = {}
        self.locals = {}
        try:
            ans = self.evaluate(fmt, [], kwargs)
        except Exception as e:
            if DEBUG:  # and getattr(e, 'is_locking_error', False):
                traceback.print_exc()
                if column_name:
                    prints('Error evaluating column named:', column_name)
            ans = error_value + ' ' + e.message
        return ans


class ValidateFormatter(TemplateFormatter):
    '''
    Provides a formatter that substitutes the validation string for every value
    '''

    def get_value(self, key, args, kwargs):
        return self._validation_string

    def validate(self, x):
        from calibre.ebooks.metadata.book.base import Metadata
        return self.safe_format(x, {}, 'VALIDATE ERROR', Metadata(''))


validation_formatter = ValidateFormatter()


class EvalFormatter(TemplateFormatter):
    '''
    A template formatter that uses a simple dict instead of an mi instance
    '''

    def get_value(self, key, args, kwargs):
        if key == '':
            return ''
        key = key.lower()
        return kwargs.get(key, _('No such variable ') + key)


# DEPRECATED. This is not thread safe. Do not use.
eval_formatter = EvalFormatter()
