# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""This package provides various means for generating and processing web markup
(XML or HTML).

The design is centered around the concept of streams of markup events (similar
in concept to SAX parsing events) which can be processed in a uniform manner
independently of where or how they are produced.
"""

__docformat__ = 'restructuredtext en'
__version__   = '0.5.0'

from calibre.utils.genshi.core import *
from calibre.utils.genshi.input import ParseError, XML, HTML
