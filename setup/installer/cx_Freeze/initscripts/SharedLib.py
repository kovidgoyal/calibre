#------------------------------------------------------------------------------
# SharedLib.py
#   Initialization script for cx_Freeze which behaves similarly to the one for
# console based applications but must handle the case where Python has already
# been initialized and another DLL of this kind has been loaded. As such it
# does not block the path unless sys.frozen is not already set.
#------------------------------------------------------------------------------

import encodings
import os
import sys
import warnings

if not hasattr(sys, "frozen"):
    sys.frozen = True
    sys.path = sys.path[:4]

os.environ["TCL_LIBRARY"] = os.path.join(DIR_NAME, "tcl")
os.environ["TK_LIBRARY"] = os.path.join(DIR_NAME, "tk")

