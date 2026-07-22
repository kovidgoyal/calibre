# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

"""
Interface defining the necessary public functions for a pdb format writer.
"""


class FormatWriter:
    def __init__(self, opts, log):
        raise NotImplementedError()

    def write_content(self, oeb_book, output_stream, metadata=None):
        raise NotImplementedError()
