#*************************************************************************
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
#*************************************************************************

PRJ = ../../../../../..

PRJNAME	= hunspell
TARGET	= hunspell
LIBTARGET=YES
EXTERNAL_WARNINGS_NOT_ERRORS := TRUE
UWINAPILIB=

#----- Settings ---------------------------------------------------------

.INCLUDE : settings.mk

# --- Files --------------------------------------------------------

CFLAGS+=-I..$/..$/
CDEFS+=-DOPENOFFICEORG

SLOFILES=	\
		$(SLO)$/affentry.obj \
		$(SLO)$/affixmgr.obj \
		$(SLO)$/dictmgr.obj \
		$(SLO)$/csutil.obj \
		$(SLO)$/hashmgr.obj \
		$(SLO)$/suggestmgr.obj \
		$(SLO)$/phonet.obj \
		$(SLO)$/hunzip.obj \
		$(SLO)$/filemgr.obj \
		$(SLO)$/replist.obj \
		$(SLO)$/hunspell.obj

LIB1TARGET= $(SLB)$/lib$(TARGET).lib
LIB1ARCHIV= $(LB)/lib$(TARGET).a
LIB1OBJFILES= $(SLOFILES)

# --- Targets ------------------------------------------------------

.INCLUDE : target.mk

