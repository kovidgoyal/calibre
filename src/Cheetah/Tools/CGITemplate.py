# $Id: CGITemplate.py,v 1.6 2006/01/29 02:09:59 tavis_rudd Exp $
"""A subclass of Cheetah.Template for use in CGI scripts.

Usage in a template:
    #extends Cheetah.Tools.CGITemplate
    #implements respond
    $cgiHeaders#slurp

Usage in a template inheriting a Python class:
1. The template
    #extends MyPythonClass
    #implements respond
    $cgiHeaders#slurp

2. The Python class
    from Cheetah.Tools import CGITemplate
    class MyPythonClass(CGITemplate):
        def cgiHeadersHook(self):
            return "Content-Type: text/html; charset=koi8-r\n\n"

To read GET/POST variables, use the .webInput method defined in
Cheetah.Utils.WebInputMixin (available in all templates without importing
anything), use Python's 'cgi' module, or make your own arrangements.

This class inherits from Cheetah.Template to make it usable in Cheetah's
single-inheritance model.  


Meta-Data
================================================================================
Author: Mike Orr <iron@mso.oz.net>
License: This software is released for unlimited distribution under the
         terms of the MIT license.  See the LICENSE file.
Version: $Revision: 1.6 $
Start Date: 2001/10/03
Last Revision Date: $Date: 2006/01/29 02:09:59 $
""" 
__author__ = "Mike Orr <iron@mso.oz.net>"
__revision__ = "$Revision: 1.6 $"[11:-2]

import os
from Cheetah.Template import Template

class CGITemplate(Template):
    """Methods useful in CGI scripts.

       Any class that inherits this mixin must also inherit Cheetah.Servlet.
    """
    

    def cgiHeaders(self):
        """Outputs the CGI headers if this is a CGI script.

           Usage:  $cgiHeaders#slurp
           Override .cgiHeadersHook() if you want to customize the headers.
        """
        if self.isCgi():
            return self.cgiHeadersHook()



    def cgiHeadersHook(self):
        """Override if you want to customize the CGI headers.
        """
        return "Content-type: text/html\n\n"


    def isCgi(self):
        """Is this a CGI script?
        """
        env = 'REQUEST_METHOD' in os.environ 
        wk = self._CHEETAH__isControlledByWebKit
        return env and not wk


    
# vim: shiftwidth=4 tabstop=4 expandtab
