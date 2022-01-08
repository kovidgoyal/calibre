'''
Interface defining the necessary public functions for a pdb format reader.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


class FormatReader:

    def __init__(self, header, stream, log, options):
        raise NotImplementedError()

    def extract_content(self, output_dir):
        raise NotImplementedError()
