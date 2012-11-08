#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import unpack

t1_operand_encoding = [None] * 256
t1_operand_encoding[0:32] = (32) * ["do_operator"]
t1_operand_encoding[32:247] = (247 - 32) * ["read_byte"]
t1_operand_encoding[247:251] = (251 - 247) * ["read_small_int1"]
t1_operand_encoding[251:255] = (255 - 251) * ["read_small_int2"]
t1_operand_encoding[255] = "read_long_int"

t2_operand_encoding = t1_operand_encoding[:]
t2_operand_encoding[28] = "read_short_int"
t2_operand_encoding[255] = "read_fixed_1616"

cff_dict_operand_encoding = t2_operand_encoding[:]
cff_dict_operand_encoding[29] = "read_long_int"
cff_dict_operand_encoding[30] = "read_real_number"
cff_dict_operand_encoding[255] = "reserved"

real_nibbles = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
        '.', 'E', 'E-', None, '-']

class Reader(dict):

    def read_byte(self, b0, data, index):
        return b0 - 139, index

    def read_small_int1(self, b0, data, index):
        b1 = ord(data[index])
        return (b0-247)*256 + b1 + 108, index+1

    def read_small_int2(self, b0, data, index):
        b1 = ord(data[index])
        return -(b0-251)*256 - b1 - 108, index+1

    def read_short_int(self, b0, data, index):
        bin = data[index] + data[index+1]
        value, = unpack(b">h", bin)
        return value, index+2

    def read_long_int(self, b0, data, index):
        bin = data[index] + data[index+1] + data[index+2] + data[index+3]
        value, = unpack(b">l", bin)
        return value, index+4

    def read_fixed_1616(self, b0, data, index):
        bin = data[index] + data[index+1] + data[index+2] + data[index+3]
        value, = unpack(b">l", bin)
        return value / 65536.0, index+4

    def read_real_number(self, b0, data, index):
        number = ''
        while True:
            b = ord(data[index])
            index = index + 1
            nibble0 = (b & 0xf0) >> 4
            nibble1 = b & 0x0f
            if nibble0 == 0xf:
                break
            number = number + real_nibbles[nibble0]
            if nibble1 == 0xf:
                break
            number = number + real_nibbles[nibble1]
        return float(number), index

class Dict(Reader):

    operand_encoding = cff_dict_operand_encoding
    TABLE = []

    def __init__(self):
        Reader.__init__(self)

        self.operators = {op:(name, arg) for op, name, arg, default in
                self.TABLE}
        self.defaults = {name:default for op, name, arg, default in self.TABLE}

    def safe_get(self, name):
        return self.get(name, self.defaults[name])

    def decompile(self, strings, global_subrs, data):
        self.strings = strings
        self.global_subrs = global_subrs
        self.stack = []
        index = 0
        while index < len(data):
            b0 = ord(data[index])
            index += 1
            handler = getattr(self, self.operand_encoding[b0])
            value, index = handler(b0, data, index)
            if value is not None:
                self.stack.append(value)

	def do_operator(self, b0, data, index):
		if b0 == 12:
			op = (b0, ord(data[index]))
			index += 1
		else:
			op = b0
		operator, arg_type = self.operators[op]
		self.handle_operator(operator, arg_type)
		return None, index

	def handle_operator(self, operator, arg_type):
        if isinstance(arg_type, tuple):
			value = ()
			for i in xrange(len(arg_type)-1, -1, -1):
				arg = arg_type[i]
				arghandler = getattr(self, 'arg_' + arg)
				value = (arghandler(operator),) + value
		else:
			arghandler = getattr(self, 'arg_' + arg_type)
			value = arghandler(operator)
		self[operator] = value

	def arg_number(self, name):
		return self.stack.pop()

	def arg_SID(self, name):
		return self.strings[self.stack.pop()]

	def arg_array(self, name):
        ans = self.stack[:]
        del self.stack[:]
        return ans

	def arg_delta(self, name):
		out = []
		current = 0
		for v in self.stack:
			current = current + v
			out.append(current)
        del self.stack[:]
		return out

class TopDict(Dict):

    TABLE = [
	#opcode     name                  argument type   default
	((12, 30), 'ROS',        ('SID','SID','number'), None,      ),
	((12, 20), 'SyntheticBase',      'number',       None,      ),
	(0,        'version',            'SID',          None,      ),
	(1,        'Notice',             'SID',          None,      ),
	((12, 0),  'Copyright',          'SID',          None,      ),
	(2,        'FullName',           'SID',          None,      ),
	((12, 38), 'FontName',           'SID',          None,      ),
	(3,        'FamilyName',         'SID',          None,      ),
	(4,        'Weight',             'SID',          None,      ),
	((12, 1),  'isFixedPitch',       'number',       0,         ),
	((12, 2),  'ItalicAngle',        'number',       0,         ),
	((12, 3),  'UnderlinePosition',  'number',       None,      ),
	((12, 4),  'UnderlineThickness', 'number',       50,        ),
	((12, 5),  'PaintType',          'number',       0,         ),
	((12, 6),  'CharstringType',     'number',       2,         ),
	((12, 7),  'FontMatrix',         'array',  [0.001,0,0,0.001,0,0],  ),
	(13,       'UniqueID',           'number',       None,      ),
	(5,        'FontBBox',           'array',  [0,0,0,0],       ),
	((12, 8),  'StrokeWidth',        'number',       0,         ),
	(14,       'XUID',               'array',        None,      ),
	((12, 21), 'PostScript',         'SID',          None,      ),
	((12, 22), 'BaseFontName',       'SID',          None,      ),
	((12, 23), 'BaseFontBlend',      'delta',        None,      ),
	((12, 31), 'CIDFontVersion',     'number',       0,         ),
	((12, 32), 'CIDFontRevision',    'number',       0,         ),
	((12, 33), 'CIDFontType',        'number',       0,         ),
	((12, 34), 'CIDCount',           'number',       8720,      ),
	(15,       'charset',            'number',       0,         ),
	((12, 35), 'UIDBase',            'number',       None,      ),
	(16,       'Encoding',           'number',       0,         ),
	(18,       'Private',       ('number','number'), None,      ),
	((12, 37), 'FDSelect',           'number',       None,      ),
	((12, 36), 'FDArray',            'number',       None,      ),
	(17,       'CharStrings',        'number',       None,      ),
    ]

class PrivateDict(Dict):

    TABLE = [
#	opcode     name                  argument type   default
	(6,        'BlueValues',         'delta',        None,      ),
	(7,        'OtherBlues',         'delta',        None,      ),
	(8,        'FamilyBlues',        'delta',        None,      ),
	(9,        'FamilyOtherBlues',   'delta',        None,      ),
	((12, 9),  'BlueScale',          'number',       0.039625,  ),
	((12, 10), 'BlueShift',          'number',       7,         ),
	((12, 11), 'BlueFuzz',           'number',       1,         ),
	(10,       'StdHW',              'number',       None,      ),
	(11,       'StdVW',              'number',       None,      ),
	((12, 12), 'StemSnapH',          'delta',        None,      ),
	((12, 13), 'StemSnapV',          'delta',        None,      ),
	((12, 14), 'ForceBold',          'number',       0,         ),
	((12, 15), 'ForceBoldThreshold', 'number',       None,      ),  # deprecated
	((12, 16), 'lenIV',              'number',       None,      ),  # deprecated
	((12, 17), 'LanguageGroup',      'number',       0,         ),
	((12, 18), 'ExpansionFactor',    'number',       0.06,      ),
	((12, 19), 'initialRandomSeed',  'number',       0,         ),
	(20,       'defaultWidthX',      'number',       0,         ),
	(21,       'nominalWidthX',      'number',       0,         ),
	(19,       'Subrs',              'number',       None,      ),
    ]

