# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

"""
Interface defining the necessary public functions for a pdb format reader.
"""


class FormatReader:
    def __init__(self, header, stream, log, options):
        raise NotImplementedError()

    def extract_content(self, output_dir):
        raise NotImplementedError()
