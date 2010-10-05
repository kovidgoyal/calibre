# $Id: TemplateCmdLineIface.py,v 1.13 2006/01/10 20:34:35 tavis_rudd Exp $

"""Provides a command line interface to compiled Cheetah template modules.

Meta-Data
================================================================================
Author: Tavis Rudd <tavis@damnsimple.com>
Version: $Revision: 1.13 $
Start Date: 2001/12/06
Last Revision Date: $Date: 2006/01/10 20:34:35 $
"""
__author__ = "Tavis Rudd <tavis@damnsimple.com>"
__revision__ = "$Revision: 1.13 $"[11:-2]

import sys
import os
import getopt
import os.path
try:
    from cPickle import load
except ImportError:
    from pickle import load

from Cheetah.Version import Version

class Error(Exception):
    pass

class CmdLineIface:
    """A command line interface to compiled Cheetah template modules."""

    def __init__(self, templateObj,
                 scriptName=os.path.basename(sys.argv[0]),
                 cmdLineArgs=sys.argv[1:]):

        self._template = templateObj
        self._scriptName = scriptName
        self._cmdLineArgs = cmdLineArgs

    def run(self):
        """The main program controller."""
        
        self._processCmdLineArgs()
        print(self._template)
        
    def _processCmdLineArgs(self):
        try:
            self._opts, self._args = getopt.getopt(
                self._cmdLineArgs, 'h', ['help',
                                            'env',
                                            'pickle=',
                                            ])

        except getopt.GetoptError, v:
            # print help information and exit:
            print(v)
            print(self.usage())
            sys.exit(2)
        
        for o, a in self._opts:
            if o in ('-h', '--help'):
                print(self.usage())
                sys.exit()
            if o == '--env':
                self._template.searchList().insert(0, os.environ)
            if o == '--pickle':
                if a == '-':
                    unpickled = load(sys.stdin)
                    self._template.searchList().insert(0, unpickled)
                else:
                    f = open(a)
                    unpickled = load(f)
                    f.close()
                    self._template.searchList().insert(0, unpickled)

    def usage(self):
        return """Cheetah %(Version)s template module command-line interface

Usage
-----
  %(scriptName)s [OPTION]

Options
-------
  -h, --help                 Print this help information
  
  --env                      Use shell ENVIRONMENT variables to fill the
                             $placeholders in the template.
                             
  --pickle <file>            Use a variables from a dictionary stored in Python
                             pickle file to fill $placeholders in the template.
                             If <file> is - stdin is used: 
                             '%(scriptName)s --pickle -'

Description
-----------

This interface allows you to execute a Cheetah template from the command line
and collect the output.  It can prepend the shell ENVIRONMENT or a pickled
Python dictionary to the template's $placeholder searchList, overriding the
defaults for the $placeholders.

""" % {'scriptName': self._scriptName,
       'Version': Version,
       }

# vim: shiftwidth=4 tabstop=4 expandtab
