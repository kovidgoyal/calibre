#!/usr/bin/env python
'''
Provides an abstract Servlet baseclass for Cheetah's Template class
'''

import sys
import os.path

class Servlet(object):
    """
        This class is an abstract baseclass for Cheetah.Template.Template.
    """

    transaction = None
    application = None
    request = None
    session = None

    def respond(self, trans=None):
        raise NotImplementedError("""\
couldn't find the template's main method.  If you are using #extends
without #implements, try adding '#implements respond' to your template
definition.""")

    def sleep(self, transaction):
        super(Servlet, self).sleep(transaction)
        self.session = None
        self.request  = None
        self._request  = None
        self.response = None
        self.transaction = None

    def shutdown(self):
        pass

    def serverSidePath(self, path=None,
                       normpath=os.path.normpath,
                       abspath=os.path.abspath
                       ):

        if path:
            return normpath(abspath(path.replace("\\", '/')))
        elif hasattr(self, '_filePath') and self._filePath:
            return normpath(abspath(self._filePath))
        else:
            return None

# vim: shiftwidth=4 tabstop=4 expandtab
