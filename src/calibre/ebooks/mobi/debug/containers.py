#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from struct import unpack_from

from calibre.ebooks.mobi.debug.headers import EXTHHeader


class ContainerHeader:

    def __init__(self, data):
        self.ident = data[:4]
        self.record_size, self.type, self.count, self.encoding = unpack_from(b'>IHHI', data, 4)
        self.encoding = {
                1252 : 'cp1252',
                65001: 'utf-8',
            }.get(self.encoding, repr(self.encoding))
        rest = list(unpack_from(b'>IIIIIIII', data, 16))
        self.num_of_resource_records = rest[2]
        self.num_of_non_dummy_resource_records = rest[3]
        self.offset_to_href_record = rest[4]
        self.unknowns1 = rest[:2]
        self.unknowns2 = rest[5]
        self.header_length = rest[6]
        self.title_length = rest[7]
        self.resources = []
        self.hrefs = []
        if data[48:52] == b'EXTH':
            self.exth = EXTHHeader(data[48:])
            self.title = data[48 + self.exth.length:][:self.title_length].decode(self.encoding)
            self.is_image_container = self.exth[539] == 'application/image'
        else:
            self.exth = ' No EXTH header present '
            self.title = ''
            self.is_image_container = False
        self.bytes_after_exth = data[self.header_length + self.title_length:]
        self.null_bytes_after_exth = len(self.bytes_after_exth) - len(self.bytes_after_exth.replace(b'\0', b''))

    def add_hrefs(self, data):
        # kindlegen inserts a trailing | after the last href
        self.hrefs = list(filter(None, data.decode('utf-8').split('|')))

    def __str__(self):
        ans = [('*'*10) + ' Container Header ' + ('*'*10)]
        a = ans.append
        a(f'Record size: {self.record_size}')
        a(f'Type: {self.type}')
        a(f'Total number of records in this container: {self.count}')
        a(f'Encoding: {self.encoding}')
        a(f'Unknowns1: {self.unknowns1}')
        a(f'Num of resource records: {self.num_of_resource_records}')
        a(f'Num of non-dummy resource records: {self.num_of_non_dummy_resource_records}')
        a(f'Offset to href record: {self.offset_to_href_record}')
        a(f'Unknowns2: {self.unknowns2}')
        a(f'Header length: {self.header_length}')
        a(f'Title Length: {self.title_length}')
        a(f'hrefs: {self.hrefs}')
        a(f'Null bytes after EXTH: {self.null_bytes_after_exth}')
        if len(self.bytes_after_exth) != self.null_bytes_after_exth:
            a('Non-null bytes present after EXTH header!!!!')
        return '\n'.join(ans) + '\n\n' + str(self.exth) + '\n\n' + (f'Title: {self.title}')
