#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


'''
Generate UUID encoded using a user specified alphabet.
'''

import string, math, uuid as _uuid

from polyglot.builtins import unicode_type


def num_to_string(number, alphabet, alphabet_len, pad_to_length=None):
    ans = []
    number = max(0, number)
    while number:
        number, digit = divmod(number, alphabet_len)
        ans.append(alphabet[digit])
    if pad_to_length is not None and pad_to_length > len(ans):
        ans.append(alphabet[0] * (pad_to_length - len(ans)))
    return ''.join(ans)


def string_to_num(string, alphabet_map, alphabet_len):
    ans = 0
    for char in reversed(string):
        ans = ans * alphabet_len + alphabet_map[char]
    return ans


class ShortUUID(object):

    def __init__(self, alphabet=None):
        # We do not include zero and one in the default alphabet as they can be
        # confused with the letters O and I in some fonts. And removing them
        # does not change the uuid_pad_len.
        self.alphabet = tuple(sorted(unicode_type(alphabet or (string.digits + string.ascii_letters)[2:])))
        self.alphabet_len = len(self.alphabet)
        self.alphabet_map = {c:i for i, c in enumerate(self.alphabet)}
        self.uuid_pad_len = int(math.ceil(math.log(1 << 128, self.alphabet_len)))

    def uuid4(self, pad_to_length=None):
        if pad_to_length is None:
            pad_to_length = self.uuid_pad_len
        return num_to_string(_uuid.uuid4().int, self.alphabet, self.alphabet_len, pad_to_length)

    def uuid5(self, namespace, name, pad_to_length=None):
        if pad_to_length is None:
            pad_to_length = self.uuid_pad_len
        return num_to_string(_uuid.uuid5(namespace, name).int, self.alphabet, self.alphabet_len, pad_to_length)

    def decode(self, encoded):
        return _uuid.UUID(int=string_to_num(encoded, self.alphabet_map, self.alphabet_len))


_global_instance = ShortUUID()
uuid4 = _global_instance.uuid4
uuid5 = _global_instance.uuid5
decode = _global_instance.decode
