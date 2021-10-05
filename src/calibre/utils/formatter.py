
'''
Created on 23 Sep 2010

@author: charles
'''

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, string, traceback, numbers
from functools import partial
from math import modf

from calibre import prints
from calibre.constants import DEBUG
from calibre.ebooks.metadata.book.base import field_metadata
from calibre.utils.formatter_functions import formatter_functions
from calibre.utils.icu import strcmp
from polyglot.builtins import unicode_type, error_message


class Node:
    NODE_RVALUE = 1
    NODE_IF = 2
    NODE_ASSIGN = 3
    NODE_FUNC = 4
    NODE_COMPARE_STRING = 5
    NODE_COMPARE_NUMERIC = 6
    NODE_CONSTANT = 7
    NODE_FIELD = 8
    NODE_RAW_FIELD = 9
    NODE_CALL = 10
    NODE_ARGUMENTS = 11
    NODE_FIRST_NON_EMPTY = 12
    NODE_FOR = 13
    NODE_GLOBALS = 14
    NODE_SET_GLOBALS = 15
    NODE_CONTAINS = 16
    NODE_BINARY_LOGOP = 17
    NODE_UNARY_LOGOP = 18
    NODE_BINARY_ARITHOP = 19
    NODE_UNARY_ARITHOP = 20
    NODE_PRINT = 21
    NODE_BREAK = 22
    NODE_CONTINUE = 23
    NODE_RETURN = 24
    NODE_CHARACTER = 25

    def __init__(self, line_number, name):
        self.my_line_number = line_number
        self.my_node_name = name

    @property
    def node_name(self):
        return self.my_node_name

    @property
    def line_number(self):
        return self.my_line_number


class IfNode(Node):
    def __init__(self, line_number, condition, then_part, else_part):
        Node.__init__(self, line_number, 'if ...')
        self.node_type = self.NODE_IF
        self.condition = condition
        self.then_part = then_part
        self.else_part = else_part


class ForNode(Node):
    def __init__(self, line_number, variable, list_field_expr, separator, block):
        Node.__init__(self, line_number, 'for ...:')
        self.node_type = self.NODE_FOR
        self.variable = variable
        self.list_field_expr = list_field_expr
        self.separator = separator
        self.block = block


class BreakNode(Node):
    def __init__(self, line_number):
        Node.__init__(self, line_number, 'break')
        self.node_type = self.NODE_BREAK


class ContinueNode(Node):
    def __init__(self, line_number):
        Node.__init__(self, line_number, 'continue')
        self.node_type = self.NODE_CONTINUE


class ReturnNode(Node):
    def __init__(self, line_number, expr):
        Node.__init__(self, line_number, 'return')
        self.expr = expr
        self.node_type = self.NODE_RETURN


class AssignNode(Node):
    def __init__(self, line_number, left, right):
        Node.__init__(self, line_number, 'assign to ' + left)
        self.node_type = self.NODE_ASSIGN
        self.left = left
        self.right = right


class FunctionNode(Node):
    def __init__(self, line_number, function_name, expression_list):
        Node.__init__(self, line_number, function_name + '()')
        self.node_type = self.NODE_FUNC
        self.name = function_name
        self.expression_list = expression_list


class CallNode(Node):
    def __init__(self, line_number, name, function, expression_list):
        Node.__init__(self, line_number, 'call template: ' + name)
        self.node_type = self.NODE_CALL
        self.function = function
        self.expression_list = expression_list


class ArgumentsNode(Node):
    def __init__(self, line_number, expression_list):
        Node.__init__(self, line_number, 'arguments()')
        self.node_type = self.NODE_ARGUMENTS
        self.expression_list = expression_list


class GlobalsNode(Node):
    def __init__(self, line_number, expression_list):
        Node.__init__(self, line_number, 'globals()')
        self.node_type = self.NODE_GLOBALS
        self.expression_list = expression_list


class SetGlobalsNode(Node):
    def __init__(self, line_number, expression_list):
        Node.__init__(self, line_number, 'set_globals()')
        self.node_type = self.NODE_SET_GLOBALS
        self.expression_list = expression_list


class StringCompareNode(Node):
    def __init__(self, line_number, operator, left, right):
        Node.__init__(self, line_number, 'comparision: ' + operator)
        self.node_type = self.NODE_COMPARE_STRING
        self.operator = operator
        self.left = left
        self.right = right


class NumericCompareNode(Node):
    def __init__(self, line_number, operator, left, right):
        Node.__init__(self, line_number, 'comparison: ' + operator)
        self.node_type = self.NODE_COMPARE_NUMERIC
        self.operator = operator
        self.left = left
        self.right = right


class LogopBinaryNode(Node):
    def __init__(self, line_number, operator, left, right):
        Node.__init__(self, line_number, 'binary operator: ' + operator)
        self.node_type = self.NODE_BINARY_LOGOP
        self.operator = operator
        self.left = left
        self.right = right


class LogopUnaryNode(Node):
    def __init__(self, line_number, operator, expr):
        Node.__init__(self, line_number, 'unary operator: ' + operator)
        self.node_type = self.NODE_UNARY_LOGOP
        self.operator = operator
        self.expr = expr


class NumericBinaryNode(Node):
    def __init__(self, line_number, operator, left, right):
        Node.__init__(self, line_number, 'binary operator: ' + operator)
        self.node_type = self.NODE_BINARY_ARITHOP
        self.operator = operator
        self.left = left
        self.right = right


class NumericUnaryNode(Node):
    def __init__(self, line_number, operator, expr):
        Node.__init__(self, line_number, 'unary operator: '+ operator)
        self.node_type = self.NODE_UNARY_ARITHOP
        self.operator = operator
        self.expr = expr


class ConstantNode(Node):
    def __init__(self, line_number, value):
        Node.__init__(self, line_number, 'constant: ' + value)
        self.node_type = self.NODE_CONSTANT
        self.value = value


class VariableNode(Node):
    def __init__(self, line_number, name):
        Node.__init__(self, line_number, 'variable: ' + name)
        self.node_type = self.NODE_RVALUE
        self.name = name


class FieldNode(Node):
    def __init__(self, line_number, expression):
        Node.__init__(self, line_number, 'field()')
        self.node_type = self.NODE_FIELD
        self.expression = expression


class RawFieldNode(Node):
    def __init__(self, line_number, expression, default=None):
        Node.__init__(self, line_number, 'raw_field()')
        self.node_type = self.NODE_RAW_FIELD
        self.expression = expression
        self.default = default


class FirstNonEmptyNode(Node):
    def __init__(self, line_number, expression_list):
        Node.__init__(self, line_number, 'first_non_empty()')
        self.node_type = self.NODE_FIRST_NON_EMPTY
        self.expression_list = expression_list


class ContainsNode(Node):
    def __init__(self, line_number, arguments):
        Node.__init__(self, line_number, 'contains()')
        self.node_type = self.NODE_CONTAINS
        self.value_expression = arguments[0]
        self.test_expression = arguments[1]
        self.match_expression = arguments[2]
        self.not_match_expression = arguments[3]


class PrintNode(Node):
    def __init__(self, line_number, arguments):
        Node.__init__(self, line_number, 'print')
        self.node_type = self.NODE_PRINT
        self.arguments = arguments


class CharacterNode(Node):
    def __init__(self, line_number, expression):
        Node.__init__(self, line_number, 'character()')
        self.node_type = self.NODE_CHARACTER
        self.expression = expression


class _Parser:
    LEX_OP = 1
    LEX_ID = 2
    LEX_CONST = 3
    LEX_EOF = 4
    LEX_STRING_INFIX = 5
    LEX_NUMERIC_INFIX = 6
    LEX_KEYWORD = 7
    LEX_NEWLINE = 8

    def error(self, message):
        ln = None
        try:
            tval = "'" + self.prog[self.lex_pos-1][1] + "'"
        except Exception:
            tval = _('Unknown')
        if self.lex_pos > 0 and self.lex_pos < self.prog_len:
            location = tval
            ln = self.line_number
        else:
            location = _('the end of the program')
        if ln:
            raise ValueError(_('{0}: {1} near {2} on line {3}').format(
                                          'Formatter', message, location, ln))
        else:
            raise ValueError(_('{0}: {1} near {2}').format(
                                          'Formatter', message, location))

    def check_eol(self):
        while self.lex_pos < len(self.prog) and self.prog[self.lex_pos] == self.LEX_NEWLINE:
            self.line_number += 1
            self.consume()

    def token(self):
        self.check_eol()
        try:
            token = self.prog[self.lex_pos][1]
            self.lex_pos += 1
            return token
        except:
            return None

    def consume(self):
        self.lex_pos += 1

    def token_op_is(self, op):
        self.check_eol()
        try:
            token = self.prog[self.lex_pos]
            return token[1] == op and token[0] == self.LEX_OP
        except:
            return False

    def token_op_is_string_infix_compare(self):
        self.check_eol()
        try:
            return self.prog[self.lex_pos][0] == self.LEX_STRING_INFIX
        except:
            return False

    def token_op_is_numeric_infix_compare(self):
        self.check_eol()
        try:
            return self.prog[self.lex_pos][0] == self.LEX_NUMERIC_INFIX
        except:
            return False

    def token_is_newline(self):
        return self.lex_pos < len(self.prog) and self.prog[self.lex_pos] == self.LEX_NEWLINE

    def token_is_id(self):
        self.check_eol()
        try:
            return self.prog[self.lex_pos][0] == self.LEX_ID
        except:
            return False

    def token_is(self, candidate):
        self.check_eol()
        try:
            token = self.prog[self.lex_pos]
            return token[1] == candidate and token[0] == self.LEX_KEYWORD
        except:
            return False

    def token_is_keyword(self):
        self.check_eol()
        try:
            return self.prog[self.lex_pos][0] == self.LEX_KEYWORD
        except:
            return False

    def token_is_constant(self):
        self.check_eol()
        try:
            return self.prog[self.lex_pos][0] == self.LEX_CONST
        except:
            return False

    def token_is_eof(self):
        self.check_eol()
        try:
            return self.prog[self.lex_pos][0] == self.LEX_EOF
        except:
            return True

    def token_text(self):
        self.check_eol()
        try:
            return self.prog[self.lex_pos][1]
        except:
            return _("'End of program'")

    def program(self, parent, funcs, prog):
        self.line_number = 1
        self.lex_pos = 0
        self.parent = parent
        self.funcs = funcs
        self.func_names = frozenset(set(self.funcs.keys()))
        self.prog = prog[0]
        self.prog_len = len(self.prog)
        if prog[1] != '':
            self.error(_("Failed to scan program. Invalid input '{0}'").format(prog[1]))
        tree = self.expression_list()
        if not self.token_is_eof():
            self.error(_("Expected end of program, found '{0}'").format(self.token_text()))
        return tree

    def expression_list(self):
        expr_list = []
        while True:
            while self.token_is_newline():
                self.line_number += 1
                self.consume()
            if self.token_is_eof():
                break
            expr_list.append(self.top_expr())
            if self.token_op_is(';'):
                self.consume()
            else:
                break
        return expr_list

    def if_expression(self):
        self.consume()
        line_number = self.line_number
        condition = self.top_expr()
        if not self.token_is('then'):
            self.error(_("{0} statement: expected '{1}', "
                         "found '{2}'").format('if', 'then', self.token_text()))
        self.consume()
        then_part = self.expression_list()
        if self.token_is('elif'):
            return IfNode(line_number, condition, then_part, [self.if_expression(),])
        if self.token_is('else'):
            self.consume()
            else_part = self.expression_list()
        else:
            else_part = None
        if not self.token_is('fi'):
            self.error(_("{0} statement: expected '{1}', "
                         "found '{2}'").format('if', 'fi', self.token_text()))
        self.consume()
        return IfNode(line_number, condition, then_part, else_part)

    def for_expression(self):
        line_number = self.line_number
        self.consume()
        if not self.token_is_id():
            self.error(_("'{0}' statement: expected an identifier").format('for'))
        variable = self.token()
        if not self.token_is('in'):
            self.error(_("{0} statement: expected '{1}', "
                         "found '{2}'").format('for', 'in', self.token_text()))
        self.consume()
        list_expr = self.top_expr()
        if self.token_is('separator'):
            self.consume()
            separator = self.expr()
        else:
            separator = None
        if not self.token_op_is(':'):
            self.error(_("{0} statement: expected '{1}', "
                         "found '{2}'").format('for', ':', self.token_text()))
        self.consume()
        block = self.expression_list()
        if not self.token_is('rof'):
            self.error(_("{0} statement: expected '{1}', "
                         "found '{2}'").format('for', 'rof', self.token_text()))
        self.consume()
        return ForNode(line_number, variable, list_expr, separator, block)

    def top_expr(self):
        return self.or_expr()

    def or_expr(self):
        left = self.and_expr()
        while self.token_op_is('||'):
            self.consume()
            right = self.and_expr()
            left = LogopBinaryNode(self.line_number, 'or', left, right)
        return left

    def and_expr(self):
        left = self.not_expr()
        while self.token_op_is('&&'):
            self.consume()
            right = self.not_expr()
            left = LogopBinaryNode(self.line_number, 'and', left, right)
        return left

    def not_expr(self):
        if self.token_op_is('!'):
            self.consume()
            return LogopUnaryNode(self.line_number, 'not', self.not_expr())
        return self.compare_expr()

    def compare_expr(self):
        left = self.add_subtract_expr()
        if (self.token_op_is_string_infix_compare() or
                self.token_is('in') or self.token_is('inlist')):
            operator = self.token()
            return StringCompareNode(self.line_number, operator, left, self.add_subtract_expr())
        if self.token_op_is_numeric_infix_compare():
            operator = self.token()
            return NumericCompareNode(self.line_number, operator, left, self.add_subtract_expr())
        return left

    def add_subtract_expr(self):
        left = self.times_divide_expr()
        while self.token_op_is('+') or self.token_op_is('-'):
            operator = self.token()
            right = self.times_divide_expr()
            left = NumericBinaryNode(self.line_number, operator, left, right)
        return left

    def times_divide_expr(self):
        left = self.unary_plus_minus_expr()
        while self.token_op_is('*') or self.token_op_is('/'):
            operator = self.token()
            right = self.unary_plus_minus_expr()
            left = NumericBinaryNode(self.line_number, operator, left, right)
        return left

    def unary_plus_minus_expr(self):
        if self.token_op_is('+'):
            self.consume()
            return NumericUnaryNode(self.line_number, '+', self.unary_plus_minus_expr())
        if self.token_op_is('-'):
            self.consume()
            return NumericUnaryNode(self.line_number, '-', self.unary_plus_minus_expr())
        return self.expr()

    def call_expression(self, name, arguments):
        subprog = self.funcs[name].cached_parse_tree
        if subprog is None:
            text = self.funcs[name].program_text
            if not text.startswith('program:'):
                self.error(_("A stored template must begin with '{0}'").format('program:'))
            text = text[len('program:'):]
            subprog = _Parser().program(self, self.funcs,
                                        self.parent.lex_scanner.scan(text))
            self.funcs[name].cached_parse_tree = subprog
        return CallNode(self.line_number, name, subprog, arguments)

    # {keyword: tuple(preprocessor, node builder) }
    keyword_nodes = {
            'if':       (lambda self:None, if_expression),
            'for':      (lambda self:None, for_expression),
            'break':    (lambda self: self.consume(), lambda self: BreakNode(self.line_number)),
            'continue': (lambda self: self.consume(), lambda self: ContinueNode(self.line_number)),
            'return':   (lambda self: self.consume(), lambda self: ReturnNode(self.line_number, self.expr())),
    }

    # {inlined_function_name: tuple(constraint on number of length, node builder) }
    inlined_function_nodes = {
        'field':            (lambda args: len(args) == 1,
                             lambda ln, args: FieldNode(ln, args[0])),
        'raw_field':        (lambda args: len(args) == 1,
                             lambda ln, args: RawFieldNode(ln, *args)),
        'test':             (lambda args: len(args) == 1,
                             lambda ln, args: IfNode(ln, args[0], (args[1],), (args[2],))),
        'first_non_empty':  (lambda args: len(args) == 1,
                             lambda ln, args: FirstNonEmptyNode(ln, args)),
        'assign':           (lambda args: len(args) == 2 and args[0].node_type == Node.NODE_RVALUE,
                             lambda ln, args: AssignNode(ln, args[0].name, args[1])),
        'contains':         (lambda args: len(args) == 4,
                             lambda ln, args: ContainsNode(ln, args)),
        'character':        (lambda args: len(args) == 1,
                             lambda ln, args: CharacterNode(ln, args[0])),
        'print':            (lambda _: True,
                             lambda ln, args: PrintNode(ln, args)),
    }

    def expr(self):
        if self.token_op_is('('):
            self.consume()
            rv = self.expression_list()
            if not self.token_op_is(')'):
                self.error(_("Expected '{0}', found '{1}'").format(')', self.token_text()))
            self.consume()
            return rv

        # Check if we have a keyword-type expression
        if self.token_is_keyword():
            t = self.token_text()
            kw_tuple = self.keyword_nodes.get(t, None)
            if kw_tuple:
                # These are keywords, so there can't be ambiguity between these,
                # ids, and functions.
                kw_tuple[0](self)
                return kw_tuple[1](self)

        # Not a keyword. Check if we have an id reference or a function call
        if self.token_is_id():
            # We have an identifier. Check if it is a shorthand field reference
            line_number = self.line_number
            id_ = self.token()
            if len(id_) > 1 and id_[0] == '$':
                if id_[1] == '$':
                    return RawFieldNode(line_number, ConstantNode(self.line_number, id_[2:]))
                return FieldNode(line_number, ConstantNode(self.line_number, id_[1:]))

            # Do we have a function call?
            if not self.token_op_is('('):
                # Nope. We must have an lvalue (identifier) or an assignment
                if self.token_op_is('='):
                    # classic assignment statement
                    self.consume()
                    return AssignNode(line_number, id_, self.top_expr())
                return VariableNode(line_number, id_)

            # We have a function.
            # Check if it is a known one. We do this here so error reporting is
            # better, as it can identify the tokens near the problem.
            id_ = id_.strip()
            if id_ not in self.func_names:
                self.error(_('Unknown function {0}').format(id_))

            # Eat the opening paren, parse the argument list, then eat the closing paren
            self.consume()
            arguments = list()
            while not self.token_op_is(')'):
                # parse an argument expression (recursive call)
                arguments.append(self.expression_list())
                if not self.token_op_is(','):
                    break
                self.consume()
            t = self.token()
            if t != ')':
                self.error(_("Expected a '{0}' for function call, "
                             "found '{1}'").format(')', t))

            # Check for an inlined function
            function_tuple = self.inlined_function_nodes.get(id_, None)
            if function_tuple and function_tuple[0](arguments):
                return function_tuple[1](line_number, arguments)
            # More complicated special cases
            if id_ == 'arguments' or id_ == 'globals' or id_ == 'set_globals':
                new_args = []
                for arg_list in arguments:
                    arg = arg_list[0]
                    if arg.node_type not in (Node.NODE_ASSIGN, Node.NODE_RVALUE):
                        self.error(_("Parameters to '{0}' must be "
                                     "variables or assignments").format(id_))
                    if arg.node_type == Node.NODE_RVALUE:
                        arg = AssignNode(line_number, arg.name, ConstantNode(self.line_number, ''))
                    new_args.append(arg)
                if id_ == 'arguments':
                    return ArgumentsNode(line_number, new_args)
                if id_ == 'set_globals':
                    return SetGlobalsNode(line_number, new_args)
                return GlobalsNode(line_number, new_args)
            # Check for calling a stored template
            if id_ in self.func_names and not self.funcs[id_].is_python:
                return self.call_expression(id_, arguments)
            # We must have a reference to a formatter function. Check if
            # the right number of arguments were supplied
            cls = self.funcs[id_]
            if cls.arg_count != -1 and len(arguments) != cls.arg_count:
                self.error(_('Incorrect number of arguments for function {0}').format(id_))
            return FunctionNode(line_number, id_, arguments)
        elif self.token_is_constant():
            # String or number
            return ConstantNode(self.line_number, self.token())
        else:
            # Who knows what?
            self.error(_("Expected an expression, found '{0}'").format(self.token_text()))


class ExecutionBase(Exception):
    def __init__(self, name):
        super().__init__(_('{0} outside of for loop').format(name) if name else '')
        self.value = ''

    def set_value(self, v):
        self.value = v

    def get_value(self):
        return self.value


class ContinueExecuted(ExecutionBase):
    def __init__(self):
        super().__init__('continue')


class BreakExecuted(ExecutionBase):
    def __init__(self):
        super().__init__('break')


class ReturnExecuted(ExecutionBase):
    def __init__(self):
        super().__init__('return')


class StopException(Exception):
    def __init__(self):
        super().__init__('Template evaluation stopped')


class _Interpreter:
    def error(self, message, line_number):
        m = _('Interpreter: {0} - line number {1}').format(message, line_number)
        raise ValueError(m)

    def program(self, funcs, parent, prog, val, is_call=False, args=None,
                global_vars=None, break_reporter=None):
        self.parent = parent
        self.parent_kwargs = parent.kwargs
        self.parent_book = parent.book
        self.funcs = funcs
        self.locals = {'$':val}
        self.override_line_number = None
        self.global_vars = global_vars if isinstance(global_vars, dict) else {}
        if break_reporter:
            self.break_reporter = self.call_break_reporter
            self.real_break_reporter = break_reporter
        else:
            self.break_reporter = None

        try:
            if is_call:
                ret =  self.do_node_call(CallNode(1, prog, None), args=args)
            else:
                ret = self.expression_list(prog)
        except ReturnExecuted as e:
            ret = e.get_value()
        return ret

    def call_break_reporter(self, txt, val, line_number):
        self.real_break_reporter(txt, val, self.locals,
                                 self.override_line_number if self.override_line_number
                                     else line_number)

    def expression_list(self, prog):
        val = ''
        try:
            for p in prog:
                val = self.expr(p)
        except (BreakExecuted, ContinueExecuted) as e:
            e.set_value(val)
            raise e
        return val

    INFIX_STRING_COMPARE_OPS = {
        "==": lambda x, y: strcmp(x, y) == 0,
        "!=": lambda x, y: strcmp(x, y) != 0,
        "<": lambda x, y: strcmp(x, y) < 0,
        "<=": lambda x, y: strcmp(x, y) <= 0,
        ">": lambda x, y: strcmp(x, y) > 0,
        ">=": lambda x, y: strcmp(x, y) >= 0,
        "in": lambda x, y: re.search(x, y, flags=re.I),
        "inlist": lambda x, y: list(filter(partial(re.search, x, flags=re.I),
                                           [v.strip() for v in y.split(',') if v.strip()]))
        }

    def do_node_string_infix(self, prog):
        try:
            left = self.expr(prog.left)
            right = self.expr(prog.right)
            res = '1' if self.INFIX_STRING_COMPARE_OPS[prog.operator](left, right) else ''
            if (self.break_reporter):
                self.break_reporter(prog.node_name, res, prog.line_number)
            return res
        except (StopException, ValueError) as e:
            raise e
        except:
            self.error(_("Error during string comparison: "
                         "operator '{0}'").format(prog.operator), prog.line_number)

    INFIX_NUMERIC_COMPARE_OPS = {
        "==#": lambda x, y: x == y,
        "!=#": lambda x, y: x != y,
        "<#": lambda x, y: x < y,
        "<=#": lambda x, y: x <= y,
        ">#": lambda x, y: x > y,
        ">=#": lambda x, y: x >= y,
        }

    def float_deal_with_none(self, v):
        # Undefined values and the string 'None' are assumed to be zero.
        # The reason for string 'None': raw_field returns it for undefined values
        return float(v if v and v != 'None' else 0)

    def do_node_numeric_infix(self, prog):
        try:
            left = self.float_deal_with_none(self.expr(prog.left))
            right = self.float_deal_with_none(self.expr(prog.right))
            res = '1' if self.INFIX_NUMERIC_COMPARE_OPS[prog.operator](left, right) else ''
            if (self.break_reporter):
                self.break_reporter(prog.node_name, res, prog.line_number)
            return res
        except (StopException, ValueError) as e:
            raise e
        except:
            self.error(_("Value used in comparison is not a number: "
                         "operator '{0}'").format(prog.operator), prog.line_number)

    def do_node_if(self, prog):
        line_number = prog.line_number
        test_part = self.expr(prog.condition)
        if self.break_reporter:
            self.break_reporter("'if': condition value", test_part, line_number)
        if test_part:
            v = self.expression_list(prog.then_part)
            if self.break_reporter:
                self.break_reporter("'if': then-block value", v, line_number)
            return v
        elif prog.else_part:
            v = self.expression_list(prog.else_part)
            if self.break_reporter:
                self.break_reporter("'if': else-block value", v, line_number)
            return v
        return ''

    def do_node_rvalue(self, prog):
        try:
            if (self.break_reporter):
                self.break_reporter(prog.node_name, self.locals[prog.name], prog.line_number)
            return self.locals[prog.name]
        except:
            self.error(_("Unknown identifier '{0}'").format(prog.name), prog.line_number)

    def do_node_func(self, prog):
        args = list()
        for arg in prog.expression_list:
            # evaluate the expression (recursive call)
            args.append(self.expr(arg))
        # Evaluate the function.
        id_ = prog.name.strip()
        cls = self.funcs[id_]
        res = cls.eval_(self.parent, self.parent_kwargs,
                        self.parent_book, self.locals, *args)
        if (self.break_reporter):
            self.break_reporter(prog.node_name, res, prog.line_number)
        return res

    def do_node_call(self, prog, args=None):
        if (self.break_reporter):
            self.break_reporter(prog.node_name, _('before evaluating arguments'), prog.line_number)
        if args is None:
            args = []
            for arg in prog.expression_list:
                # evaluate the expression (recursive call)
                args.append(self.expr(arg))
        saved_locals = self.locals
        self.locals = {}
        for dex, v in enumerate(args):
            self.locals['*arg_'+ str(dex)] = v
        if (self.break_reporter):
            self.break_reporter(prog.node_name, _('after evaluating arguments'), prog.line_number)
            saved_line_number = self.override_line_number
            self.override_line_number = (self.override_line_number if self.override_line_number
                                         else prog.line_number)
        else:
            saved_line_number = None
        try:
            val = self.expression_list(prog.function)
        except ReturnExecuted as e:
            val = e.get_value()
        self.override_line_number = saved_line_number
        self.locals = saved_locals
        if (self.break_reporter):
            self.break_reporter(prog.node_name + _(' returned value'), val, prog.line_number)
        return val

    def do_node_arguments(self, prog):
        for dex, arg in enumerate(prog.expression_list):
            self.locals[arg.left] = self.locals.get('*arg_'+ str(dex), self.expr(arg.right))
        if (self.break_reporter):
            self.break_reporter(prog.node_name, '', prog.line_number)
        return ''

    def do_node_globals(self, prog):
        res = ''
        for arg in prog.expression_list:
            res = self.locals[arg.left] = self.global_vars.get(arg.left, self.expr(arg.right))
        if (self.break_reporter):
            self.break_reporter(prog.node_name, res, prog.line_number)
        return res

    def do_node_set_globals(self, prog):
        res = ''
        for arg in prog.expression_list:
            res = self.global_vars[arg.left] = self.locals.get(arg.left, self.expr(arg.right))
        if (self.break_reporter):
            self.break_reporter(prog.node_name, res, prog.line_number)
        return res

    def do_node_constant(self, prog):
        if (self.break_reporter):
            self.break_reporter(prog.node_name, prog.value, prog.line_number)
        return prog.value

    def do_node_field(self, prog):
        try:
            name = self.expr(prog.expression)
            try:
                res = self.parent.get_value(name, [], self.parent_kwargs)
                if (self.break_reporter):
                    self.break_reporter(prog.node_name, res, prog.line_number)
                return res
            except:
                self.error(_("Unknown field '{0}'").format(name), prog.line_number)
        except (StopException, ValueError) as e:
            raise e
        except:
            self.error(_("Unknown field '{0}'").format('internal parse error'),
                       prog.line_number)

    def do_node_raw_field(self, prog):
        try:
            name = self.expr(prog.expression)
            name = field_metadata.search_term_to_field_key(name)
            res = getattr(self.parent_book, name, None)
            if res is None and prog.default is not None:
                res = self.expr(prog.default)
                if (self.break_reporter):
                    self.break_reporter(prog.node_name, res, prog.line_number)
                return res
            if res is not None:
                if isinstance(res, list):
                    fm = self.parent_book.metadata_for_field(name)
                    if fm is None:
                        res = ', '.join(res)
                    else:
                        res = fm['is_multiple']['list_to_ui'].join(res)
                else:
                    res = unicode_type(res)
            else:
                res = unicode_type(res)  # Should be the string "None"
            if (self.break_reporter):
                self.break_reporter(prog.node_name, res, prog.line_number)
            return res
        except (StopException, ValueError) as e:
            raise e
        except:
            self.error(_("Unknown field '{0}'").format('internal parse error'),
                       prog.line_number)

    def do_node_assign(self, prog):
        t = self.expr(prog.right)
        self.locals[prog.left] = t
        if (self.break_reporter):
            self.break_reporter(prog.node_name, t, prog.line_number)
        return t

    def do_node_first_non_empty(self, prog):
        for expr in prog.expression_list:
            v = self.expr(expr)
            if v:
                if self.break_reporter:
                    self.break_reporter(prog.node_name, v, prog.line_number)
                return v
        if (self.break_reporter):
            self.break_reporter(prog.node_name, '', prog.line_number)
        return ''

    def do_node_for(self, prog):
        line_number = prog.line_number
        try:
            separator = ',' if prog.separator is None else self.expr(prog.separator)
            v = prog.variable
            f = self.expr(prog.list_field_expr)
            res = getattr(self.parent_book, f, f)
            if res is not None:
                if not isinstance(res, list):
                    res = [r.strip() for r in res.split(separator) if r.strip()]
                ret = ''
                if self.break_reporter:
                    self.break_reporter("'for' list value", separator.join(res), line_number)
                try:
                    for x in res:
                        try:
                            self.locals[v] = x
                            ret = self.expression_list(prog.block)
                        except ContinueExecuted as e:
                            ret = e.get_value()
                except BreakExecuted as e:
                    ret = e.get_value()
                if (self.break_reporter):
                    self.break_reporter("'for' block value", ret, line_number)
            elif self.break_reporter:
                # Shouldn't get here
                self.break_reporter("'for' list value", '', line_number)
                ret = ''
            return ret
        except (StopException, ValueError) as e:
            raise e
        except Exception as e:
            self.error(_("Unhandled exception '{0}'").format(e), line_number)

    def do_node_break(self, prog):
        if (self.break_reporter):
            self.break_reporter(prog.node_name, '', prog.line_number)
        raise BreakExecuted()

    def do_node_continue(self, prog):
        if (self.break_reporter):
            self.break_reporter(prog.node_name, '', prog.line_number)
        raise ContinueExecuted()

    def do_node_return(self, prog):
        v = self.expr(prog.expr)
        if (self.break_reporter):
            self.break_reporter(prog.node_name, v, prog.line_number)
        e = ReturnExecuted()
        e.set_value(v)
        raise e

    def do_node_contains(self, prog):
        v = self.expr(prog.value_expression)
        t = self.expr(prog.test_expression)
        if re.search(t, v, flags=re.I):
            res = self.expr(prog.match_expression)
        else:
            res = self.expr(prog.not_match_expression)
        if (self.break_reporter):
            self.break_reporter(prog.node_name, res, prog.line_number)
        return res

    LOGICAL_BINARY_OPS = {
        'and': lambda self, x, y: self.expr(x) and self.expr(y),
        'or': lambda self, x, y: self.expr(x) or self.expr(y),
    }

    def do_node_logop(self, prog):
        try:
            res = ('1' if self.LOGICAL_BINARY_OPS[prog.operator](self, prog.left, prog.right) else '')
            if (self.break_reporter):
                self.break_reporter(prog.node_name, res, prog.line_number)
            return res
        except (StopException, ValueError) as e:
            raise e
        except:
            self.error(_("Error during operator evaluation: "
                         "operator '{0}'").format(prog.operator), prog.line_number)

    LOGICAL_UNARY_OPS = {
        'not': lambda x: not x,
    }

    def do_node_logop_unary(self, prog):
        try:
            expr = self.expr(prog.expr)
            res = ('1' if self.LOGICAL_UNARY_OPS[prog.operator](expr) else '')
            if (self.break_reporter):
                self.break_reporter(prog.node_name, res, prog.line_number)
            return res
        except (StopException, ValueError) as e:
            raise e
        except:
            self.error(_("Error during operator evaluation: "
                         "operator '{0}'").format(prog.operator), prog.line_number)

    ARITHMETIC_BINARY_OPS = {
        '+': lambda x, y: x + y,
        '-': lambda x, y: x - y,
        '*': lambda x, y: x * y,
        '/': lambda x, y: x / y,
    }

    def do_node_binary_arithop(self, prog):
        try:
            answer = self.ARITHMETIC_BINARY_OPS[prog.operator](float(self.expr(prog.left)),
                                                               float(self.expr(prog.right)))
            res = unicode_type(answer if modf(answer)[0] != 0 else int(answer))
            if (self.break_reporter):
                self.break_reporter(prog.node_name, res, prog.line_number)
            return res
        except (StopException, ValueError) as e:
            raise e
        except:
            self.error(_("Error during operator evaluation: "
                         "operator '{0}'").format(prog.operator), prog.line_number)

    ARITHMETIC_UNARY_OPS = {
        '+': lambda x: x,
        '-': lambda x: -x,
    }

    def do_node_unary_arithop(self, prog):
        try:
            expr = self.ARITHMETIC_UNARY_OPS[prog.operator](float(self.expr(prog.expr)))
            res = unicode_type(expr if modf(expr)[0] != 0 else int(expr))
            if (self.break_reporter):
                self.break_reporter(prog.node_name, res, prog.line_number)
            return res
        except (StopException, ValueError) as e:
            raise e
        except:
            self.error(_("Error during operator evaluation: "
                         "operator '{0}'").format(prog.operator), prog.line_number)

    characters = {
        'return':    '\r',
        'newline':   '\n',
        'tab':       '\t',
        'backslash': '\\',
    }

    def do_node_character(self, prog):
        try:
            key = self.expr(prog.expression)
            ret = self.characters.get(key, None)
            if ret is None:
                self.error(_("Function {0}: invalid character name '{1}")
                           .format('character', key), prog.line_number)
            if (self.break_reporter):
                self.break_reporter(prog.node_name, ret, prog.line_number)
        except (StopException, ValueError) as e:
            raise e
        return ret

    def do_node_print(self, prog):
        res = []
        for arg in prog.arguments:
            res.append(self.expr(arg))
        print(res)
        return res[0] if res else ''

    NODE_OPS = {
        Node.NODE_IF:             do_node_if,
        Node.NODE_ASSIGN:         do_node_assign,
        Node.NODE_CONSTANT:       do_node_constant,
        Node.NODE_RVALUE:         do_node_rvalue,
        Node.NODE_FUNC:           do_node_func,
        Node.NODE_FIELD:          do_node_field,
        Node.NODE_RAW_FIELD:      do_node_raw_field,
        Node.NODE_COMPARE_STRING: do_node_string_infix,
        Node.NODE_COMPARE_NUMERIC:do_node_numeric_infix,
        Node.NODE_ARGUMENTS:      do_node_arguments,
        Node.NODE_CALL:           do_node_call,
        Node.NODE_FIRST_NON_EMPTY:do_node_first_non_empty,
        Node.NODE_FOR:            do_node_for,
        Node.NODE_GLOBALS:        do_node_globals,
        Node.NODE_SET_GLOBALS:    do_node_set_globals,
        Node.NODE_CONTAINS:       do_node_contains,
        Node.NODE_BINARY_LOGOP:   do_node_logop,
        Node.NODE_UNARY_LOGOP:    do_node_logop_unary,
        Node.NODE_BINARY_ARITHOP: do_node_binary_arithop,
        Node.NODE_UNARY_ARITHOP:  do_node_unary_arithop,
        Node.NODE_PRINT:          do_node_print,
        Node.NODE_BREAK:          do_node_break,
        Node.NODE_CONTINUE:       do_node_continue,
        Node.NODE_RETURN:         do_node_return,
        Node.NODE_CHARACTER:      do_node_character,
        }

    def expr(self, prog):
        try:
            if isinstance(prog, list):
                return self.expression_list(prog)
            return self.NODE_OPS[prog.node_type](self, prog)
        except (ValueError, ExecutionBase, StopException) as e:
            raise e
        except Exception as e:
            if (DEBUG):
                traceback.print_exc()
            self.error(_("Internal error evaluating an expression: '{0}'").format(str(e)),
                       prog.line_number)


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
        self.column_name = None
        self.template_cache = None
        self.global_vars = {}
        self.locals = {}
        self.funcs = formatter_functions().get_functions()
        self._interpreters = []
        self._template_parser = None
        self.recursion_stack = []
        self.recursion_level = -1

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
            except Exception:
                raise ValueError(
                    _('format: type {0} requires an integer value, got {1}').format(typ, val))
        elif 'eEfFgGn%'.find(typ) >= 0:
            try:
                val = float(val)
            except:
                raise ValueError(
                    _('format: type {0} requires a decimal (float) value, got {1}').format(typ, val))
        return unicode_type(('{0:'+fmt+'}').format(val))

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

    # ################# Template language lexical analyzer ######################

    lex_scanner = re.Scanner([
            (r'(==#|!=#|<=#|<#|>=#|>#)', lambda x,t: (_Parser.LEX_NUMERIC_INFIX, t)),  # noqa
            (r'(==|!=|<=|<|>=|>)',       lambda x,t: (_Parser.LEX_STRING_INFIX, t)),  # noqa
            (r'(if|then|else|elif|fi)\b',lambda x,t: (_Parser.LEX_KEYWORD, t)),  # noqa
            (r'(for|in|rof|separator)\b',lambda x,t: (_Parser.LEX_KEYWORD, t)),  # noqa
            (r'(break|continue)\b',      lambda x,t: (_Parser.LEX_KEYWORD, t)),  # noqa
            (r'(return|inlist)\b',       lambda x,t: (_Parser.LEX_KEYWORD, t)),  # noqa
            (r'(\|\||&&|!)',             lambda x,t: (_Parser.LEX_OP, t)),  # noqa
            (r'[(),=;:\+\-*/]',          lambda x,t: (_Parser.LEX_OP, t)),  # noqa
            (r'-?[\d\.]+',               lambda x,t: (_Parser.LEX_CONST, t)),  # noqa
            (r'\$\$?#?\w+',              lambda x,t: (_Parser.LEX_ID, t)),  # noqa
            (r'\$',                      lambda x,t: (_Parser.LEX_ID, t)),  # noqa
            (r'\w+',                     lambda x,t: (_Parser.LEX_ID, t)),  # noqa
            (r'".*?((?<!\\)")',          lambda x,t: (_Parser.LEX_CONST, t[1:-1])),  # noqa
            (r'\'.*?((?<!\\)\')',        lambda x,t: (_Parser.LEX_CONST, t[1:-1])),  # noqa
            (r'\n#.*?(?:(?=\n)|$)',      lambda x,t: _Parser.LEX_NEWLINE),  # noqa
            (r'\s',                      lambda x,t: _Parser.LEX_NEWLINE if t == '\n' else None),  # noqa
        ], flags=re.DOTALL)

    def _eval_program(self, val, prog, column_name, global_vars, break_reporter):
        if column_name is not None and self.template_cache is not None:
            tree = self.template_cache.get(column_name, None)
            if not tree:
                tree = self.gpm_parser.program(self, self.funcs, self.lex_scanner.scan(prog))
                self.template_cache[column_name] = tree
        else:
            tree = self.gpm_parser.program(self, self.funcs, self.lex_scanner.scan(prog))
        return self.gpm_interpreter.program(self.funcs, self, tree, val,
                                global_vars=global_vars, break_reporter=break_reporter)

    def _eval_sfm_call(self, template_name, args, global_vars):
        func = self.funcs[template_name]
        tree = func.cached_parse_tree
        if tree is None:
            tree = self.gpm_parser.program(self, self.funcs,
                           self.lex_scanner.scan(func.program_text[len('program:'):]))
            func.cached_parse_tree = tree
        return self.gpm_interpreter.program(self.funcs, self, tree, None,
                                            is_call=True, args=args,
                                            global_vars=global_vars)
    # ################# Override parent classes methods #####################

    def get_value(self, key, args, kwargs):
        raise Exception('get_value must be implemented in the subclass')

    def format_field(self, val, fmt):
        # ensure we are dealing with a string.
        if isinstance(val, numbers.Number):
            if val:
                val = unicode_type(val)
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
            val = self._eval_program(val, fmt[p+1:-1], None, self.global_vars, None)
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
                    if not func.is_python:
                        args.insert(0, val)
                        val = self._eval_sfm_call(fname, args, self.global_vars)
                    else:
                        if (func.arg_count == 1 and (len(args) != 1 or args[0])) or \
                                (func.arg_count > 1 and func.arg_count != len(args)+1):
                            raise ValueError(
                                _('Incorrect number of arguments for function {0}').format(fname))
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

    def evaluate(self, fmt, args, kwargs, global_vars, break_reporter=None):
        if fmt.startswith('program:'):
            ans = self._eval_program(kwargs.get('$', None), fmt[8:],
                                     self.column_name, global_vars, break_reporter)
        else:
            ans = self.vformat(fmt, args, kwargs)
            if self.strip_results:
                ans = self.compress_spaces.sub(' ', ans)
        if self.strip_results:
            ans = ans.strip(' ')
        return ans

    # It is possible for a template to indirectly invoke other templates by
    # doing field references of composite columns. If this happens then the
    # reference can use different parameters when calling safe_format(). Because
    # the parameters are saved as instance variables they can possibly affect
    # the 'calling' template. To avoid this problem, save the current formatter
    # state when recursion is detected. There is no point in saving the level
    # 0 state.

    def save_state(self):
        self.recursion_level += 1
        if self.recursion_level > 0:
            return (
                (self.strip_results,
                 self.column_name,
                 self.template_cache,
                 self.kwargs,
                 self.book,
                 self.global_vars,
                 self.funcs,
                 self.locals))
        else:
            return None

    def restore_state(self, state):
        self.recursion_level -= 1
        if state is not None:
            (self.strip_results,
             self.column_name,
             self.template_cache,
             self.kwargs,
             self.book,
             self.global_vars,
             self.funcs,
             self.locals) = state

    # Allocate an interpreter if the formatter encounters a GPM or TPM template.
    # We need to allocate additional interpreters if there is composite recursion
    # so that the templates are evaluated by separate instances. It is OK to
    # reuse already-allocated interpreters because their state is initialized on
    # call. As a side effect, no interpreter is instantiated if no TPM/GPM
    # template is encountered.

    @property
    def gpm_interpreter(self):
        if len(self._interpreters) <= self.recursion_level:
            self._interpreters.append(_Interpreter())
        return self._interpreters[self.recursion_level]

    # Allocate a parser if needed. Parsers cannot recurse so one is sufficient.

    @property
    def gpm_parser(self):
        if self._template_parser is None:
            self._template_parser = _Parser()
        return self._template_parser

    # ######### a formatter that throws exceptions ############

    def unsafe_format(self, fmt, kwargs, book, strip_results=True, global_vars=None):
        state = self.save_state()
        try:
            self.strip_results = strip_results
            self.column_name = self.template_cache = None
            self.kwargs = kwargs
            self.book = book
            self.composite_values = {}
            self.locals = {}
            self.global_vars = global_vars if isinstance(global_vars, dict) else {}
            return self.evaluate(fmt, [], kwargs, self.global_vars)
        finally:
            self.restore_state(state)

    # ######### a formatter guaranteed not to throw an exception ############

    def safe_format(self, fmt, kwargs, error_value, book,
                    column_name=None, template_cache=None,
                    strip_results=True, template_functions=None,
                    global_vars=None, break_reporter=None):
        state = self.save_state()
        if self.recursion_level == 0:
            # Initialize the composite values dict if this is the base-level
            # call. Recursive calls will use the same dict.
            self.composite_values = {}
        try:
            self.strip_results = strip_results
            self.column_name = column_name
            self.template_cache = template_cache
            self.kwargs = kwargs
            self.book = book
            self.global_vars = global_vars if isinstance(global_vars, dict) else {}
            if template_functions:
                self.funcs = template_functions
            else:
                self.funcs = formatter_functions().get_functions()
            self.locals = {}
            try:
                ans = self.evaluate(fmt, [], kwargs, self.global_vars, break_reporter=break_reporter)
            except StopException as e:
                ans = error_message(e)
            except Exception as e:
                if DEBUG:  # and getattr(e, 'is_locking_error', False):
                    traceback.print_exc()
                    if column_name:
                        prints('Error evaluating column named:', column_name)
                ans = error_value + ' ' + error_message(e)
            return ans
        finally:
            self.restore_state(state)


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
        return kwargs.get(key, _('No such variable {0}').format(key))


# DEPRECATED. This is not thread safe. Do not use.
eval_formatter = EvalFormatter()
