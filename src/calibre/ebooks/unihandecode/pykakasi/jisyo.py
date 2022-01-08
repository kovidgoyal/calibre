#  jisyo.py
#
# Copyright 2011 Hiroshi Miura <miurahr@linux.com>


from zlib import decompress


class jisyo :
    kanwadict = None
    itaijidict = None
    kanadict = None
    jisyo_table = {}

# this class is Borg
    _shared_state = {}

    def __new__(cls, *p, **k):
        self = object.__new__(cls, *p, **k)
        self.__dict__ = cls._shared_state
        return self

    def __init__(self):
        from calibre.utils.serialize import msgpack_loads
        if self.kanwadict is None:
            self.kanwadict = msgpack_loads(
                P('localization/pykakasi/kanwadict2.calibre_msgpack', data=True))
        if self.itaijidict is None:
            self.itaijidict = msgpack_loads(
                P('localization/pykakasi/itaijidict2.calibre_msgpack', data=True))
        if self.kanadict is None:
            self.kanadict = msgpack_loads(
                P('localization/pykakasi/kanadict2.calibre_msgpack', data=True))

    def load_jisyo(self, char):
        if not isinstance(char, str):
            char = str(char, 'utf-8')
        key = "%04x"%ord(char)

        try:  # already exist?
            table = self.jisyo_table[key]
        except:
            from calibre.utils.serialize import msgpack_loads
            try:
                table = self.jisyo_table[key]  = msgpack_loads(decompress(self.kanwadict[key]))
            except:
                return None
        return table
