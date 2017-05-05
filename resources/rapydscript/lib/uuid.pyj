# vim:fileencoding=utf-8
# License: BSD Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>
# globals: crypto
from __python__ import hash_literals

from encodings import hexlify, urlsafe_b64decode, urlsafe_b64encode

RFC_4122 = 1

if jstype(crypto) is 'object' and crypto.getRandomValues:
    random_bytes = def (num):
        ans = Uint8Array(num or 16)
        crypto.getRandomValues(ans)
        return ans
else:
    random_bytes = def (num):
        ans = Uint8Array(num or 16)
        for i in range(ans.length):
            ans[i] = Math.floor(Math.random() * 256)
        return ans


def uuid4_bytes():
    data = random_bytes()
    data[6] = 0b01000000 | (data[6] & 0b1111)
    data[8] = (((data[8] >> 4) & 0b11 | 0b1000) << 4) | (data[8] & 0b1111)
    return data


def as_str():
    h = this.hex
    return h[:8] + '-' + h[8:12] + '-' + h[12:16] + '-' + h[16:20] + '-' + h[20:]


def uuid4():
    b = uuid4_bytes()
    return {
        'hex': hexlify(b),
        'bytes': b,
        'variant': RFC_4122,
        'version': 4,
        '__str__': as_str,
        'toString': as_str,
    }


def num_to_string(numbers, alphabet, pad_to_length):
    ans = v'[]'
    alphabet_len = alphabet.length
    numbers = Array.prototype.slice.call(numbers)
    for v'var i = 0; i < numbers.length - 1; i++':
        x = divmod(numbers[i], alphabet_len)
        numbers[i] = x[0]
        numbers[i+1] += x[1]
    for v'var i = 0; i < numbers.length; i++':
        number = numbers[i]
        while number:
            x = divmod(number, alphabet_len)
            number = x[0]
            ans.push(alphabet[x[1]])
    if pad_to_length and pad_to_length > ans.length:
        ans.push(alphabet[0].repeat(pad_to_length - ans.length))
    return ans.join('')


def short_uuid():
    # A totally random uuid encoded using only URL and filename safe characters
    return urlsafe_b64encode(random_bytes(), '')


def short_uuid4():
    # A uuid4 encoded using only URL and filename safe characters
    return urlsafe_b64encode(uuid4_bytes(), '')


def decode_short_uuid(val):
    return urlsafe_b64decode(val + '==')
