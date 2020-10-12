# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from polyglot.builtins import native_string_type


class ConversionUserFeedBack(Exception):

    def __init__(self, title, msg, level='info', det_msg=''):
        ''' Show a simple message to the user

        :param title: The title (very short description)
        :param msg: The message to show the user
        :param level: Must be one of 'info', 'warn' or 'error'
        :param det_msg: Optional detailed message to show the user
        '''
        import json
        Exception.__init__(self, json.dumps({'msg':msg, 'level':level,
            'det_msg':det_msg, 'title':title}))
        self.title, self.msg, self.det_msg = title, msg, det_msg
        self.level = level


# Ensure exception uses fully qualified name as this is used to detect it in
# the GUI.
ConversionUserFeedBack.__name__ = native_string_type('calibre.ebooks.conversion.ConversionUserFeedBack')
