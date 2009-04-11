"""winshell - convenience functions to access Windows shell functionality

Certain aspects of the Windows user interface are grouped by
 Microsoft as Shell functions. These include the Desktop, shortcut
 icons, special folders (such as My Documents) and a few other things.

These are mostly available via the shell module of the win32all
 extensions, but whenever I need to use them, I've forgotten the
 various constants and so on.

Several of the shell items have two variants: personal and common,
 or User and All Users. These refer to systems with profiles in use:
 anything from NT upwards, and 9x with Profiles turned on. Where
 relevant, the Personal/User version refers to that owned by the
 logged-on user and visible only to that user; the Common/All Users
 version refers to that maintained by an Administrator and visible
 to all users of the system.

(c) Tim Golden <winshell@timgolden.me.uk> 25th November 2003
Licensed under the (GPL-compatible) MIT License:
http://www.opensource.org/licenses/mit-license.php

9th Nov 2005  0.2  . License changed to MIT
                   . Added functionality using SHFileOperation
25th Nov 2003 0.1  . Initial release by Tim Golden
"""

__VERSION__ = "0.2"

import os
from win32com import storagecon
from win32com.shell import shell, shellcon
import pythoncom

class x_winshell (Exception):
  pass

#
# Although this can be done in one call, Win9x didn't
#  support it, so I added this workaround.
#
def get_path (folder_id):
  return shell.SHGetPathFromIDList (shell.SHGetSpecialFolderLocation (0, folder_id))

def desktop (common=0):
  "What folder is equivalent to the current desktop?"
  return get_path ((shellcon.CSIDL_DESKTOP, shellcon.CSIDL_COMMON_DESKTOPDIRECTORY)[common])

def common_desktop ():
#
# Only here because already used in code
#
  return desktop (common=1)

def application_data (common=0):
  "What folder holds application configuration files?"
  return get_path ((shellcon.CSIDL_APPDATA, shellcon.CSIDL_COMMON_APPDATA)[common])

def favourites (common=0):
  "What folder holds the Explorer favourites shortcuts?"
  return get_path ((shellcon.CSIDL_FAVORITES, shellcon.CSIDL_COMMON_FAVORITES)[common])
bookmarks = favourites

def start_menu (common=0):
  "What folder holds the Start Menu shortcuts?"
  return get_path ((shellcon.CSIDL_STARTMENU, shellcon.CSIDL_COMMON_STARTMENU)[common])

def programs (common=0):
  "What folder holds the Programs shortcuts (from the Start Menu)?"
  return get_path ((shellcon.CSIDL_PROGRAMS, shellcon.CSIDL_COMMON_PROGRAMS)[common])

def startup (common=0):
  "What folder holds the Startup shortcuts (from the Start Menu)?"
  return get_path ((shellcon.CSIDL_STARTUP, shellcon.CSIDL_COMMON_STARTUP)[common])

def personal_folder ():
  "What folder holds the My Documents files?"
  return get_path (shellcon.CSIDL_PERSONAL)
my_documents = personal_folder

def recent ():
  "What folder holds the Documents shortcuts (from the Start Menu)?"
  return get_path (shellcon.CSIDL_RECENT)

def sendto ():
  "What folder holds the SendTo shortcuts (from the Context Menu)?"
  return get_path (shellcon.CSIDL_SENDTO)

#
# Internally abstracted function to handle one
#  of several shell-based file manipulation
#  routines. Not all the possible parameters
#  are covered which might be passed to the
#  underlying SHFileOperation API call, but
#  only those which seemed useful to me at
#  the time.
#
def _file_operation (
  operation,
  source_path,
  target_path=None,
  allow_undo=True,
  no_confirm=False,
  rename_on_collision=True,
  silent=False,
  hWnd=None
):
  #
  # At present the Python wrapper around SHFileOperation doesn't
  # allow lists of files. Hopefully it will at some point, so
  # take account of it here.
  # If you pass this shell function a "/"-separated path with
  # a wildcard, eg c:/temp/*.tmp, it gets confused. It's ok
  # with a backslash, so convert here.
  #
  source_path = source_path or ""
  if isinstance (source_path, basestring):
    source_path = os.path.abspath (source_path)
  else:
    source_path = [os.path.abspath (i) for i in source_path]

  target_path = target_path or ""
  if isinstance (target_path, basestring):
    target_path = os.path.abspath (target_path)
  else:
    target_path = [os.path.abspath (i) for i in target_path]

  flags = 0
  if allow_undo: flags |= shellcon.FOF_ALLOWUNDO
  if no_confirm: flags |= shellcon.FOF_NOCONFIRMATION
  if rename_on_collision: flags |= shellcon.FOF_RENAMEONCOLLISION
  if silent: flags |= shellcon.FOF_SILENT

  result, n_aborted = shell.SHFileOperation (
    (hWnd or 0, operation, source_path, target_path, flags, None, None)
  )
  if result <> 0:
    raise x_winshell, result
  elif n_aborted:
    raise x_winshell, "%d operations were aborted by the user" % n_aborted

def copy_file (
  source_path,
  target_path,
  allow_undo=True,
  no_confirm=False,
  rename_on_collision=True,
  silent=False,
  hWnd=None
):
  """Perform a shell-based file copy. Copying in
   this way allows the possibility of undo, auto-renaming,
   and showing the "flying file" animation during the copy.

  The default options allow for undo, don't automatically
   clobber on a name clash, automatically rename on collision
   and display the animation.
  """
  _file_operation (
    shellcon.FO_COPY,
    source_path,
    target_path,
    allow_undo,
    no_confirm,
    rename_on_collision,
    silent,
    hWnd
  )

def move_file (
  source_path,
  target_path,
  allow_undo=True,
  no_confirm=False,
  rename_on_collision=True,
  silent=False,
  hWnd=None
):
  """Perform a shell-based file move. Moving in
   this way allows the possibility of undo, auto-renaming,
   and showing the "flying file" animation during the copy.

  The default options allow for undo, don't automatically
   clobber on a name clash, automatically rename on collision
   and display the animation.
  """
  _file_operation (
    shellcon.FO_MOVE,
    source_path,
    target_path,
    allow_undo,
    no_confirm,
    rename_on_collision,
    silent,
    hWnd
  )

def rename_file (
  source_path,
  target_path,
  allow_undo=True,
  no_confirm=False,
  rename_on_collision=True,
  silent=False,
  hWnd=None
):
  """Perform a shell-based file rename. Renaming in
   this way allows the possibility of undo, auto-renaming,
   and showing the "flying file" animation during the copy.

  The default options allow for undo, don't automatically
   clobber on a name clash, automatically rename on collision
   and display the animation.
  """
  _file_operation (
    shellcon.FO_RENAME,
    source_path,
    target_path,
    allow_undo,
    no_confirm,
    rename_on_collision,
    silent,
    hWnd
  )

def delete_file (
  source_path,
  allow_undo=True,
  no_confirm=False,
  rename_on_collision=True,
  silent=False,
  hWnd=None
):
  """Perform a shell-based file delete. Deleting in
   this way uses the system recycle bin, allows the
   possibility of undo, and showing the "flying file"
   animation during the delete.

  The default options allow for undo, don't automatically
   clobber on a name clash, automatically rename on collision
   and display the animation.
  """
  _file_operation (
    shellcon.FO_DELETE,
    source_path,
    None,
    allow_undo,
    no_confirm,
    rename_on_collision,
    silent,
    hWnd
  )

def CreateShortcut (Path, Target, Arguments = "", StartIn = "", Icon = ("",0), Description = ""):
  """Create a Windows shortcut:

  Path - As what file should the shortcut be created?
  Target - What command should the desktop use?
  Arguments - What arguments should be supplied to the command?
  StartIn - What folder should the command start in?
  Icon - (filename, index) What icon should be used for the shortcut?
  Description - What description should the shortcut be given?

  eg
  CreateShortcut (
    Path=os.path.join (desktop (), "PythonI.lnk"),
    Target=r"c:\python\python.exe",
    Icon=(r"c:\python\python.exe", 0),
    Description="Python Interpreter"
  )
  """
  sh = pythoncom.CoCreateInstance (
    shell.CLSID_ShellLink,
    None,
    pythoncom.CLSCTX_INPROC_SERVER,
    shell.IID_IShellLink
  )

  sh.SetPath (Target)
  sh.SetDescription (Description)
  sh.SetArguments (Arguments)
  sh.SetWorkingDirectory (StartIn)
  sh.SetIconLocation (Icon[0], Icon[1])

  persist = sh.QueryInterface (pythoncom.IID_IPersistFile)
  persist.Save (Path, 1)

#
# Constants for structured storage
#
# These come from ObjIdl.h
FMTID_USER_DEFINED_PROPERTIES = "{F29F85E0-4FF9-1068-AB91-08002B27B3D9}"
FMTID_CUSTOM_DEFINED_PROPERTIES = "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}"

PIDSI_TITLE               = 0x00000002
PIDSI_SUBJECT             = 0x00000003
PIDSI_AUTHOR              = 0x00000004
PIDSI_CREATE_DTM          = 0x0000000c
PIDSI_KEYWORDS            = 0x00000005
PIDSI_COMMENTS            = 0x00000006
PIDSI_TEMPLATE            = 0x00000007
PIDSI_LASTAUTHOR          = 0x00000008
PIDSI_REVNUMBER           = 0x00000009
PIDSI_EDITTIME            = 0x0000000a
PIDSI_LASTPRINTED         = 0x0000000b
PIDSI_LASTSAVE_DTM        = 0x0000000d
PIDSI_PAGECOUNT           = 0x0000000e
PIDSI_WORDCOUNT           = 0x0000000f
PIDSI_CHARCOUNT           = 0x00000010
PIDSI_THUMBNAIL           = 0x00000011
PIDSI_APPNAME             = 0x00000012
PROPERTIES = (
  PIDSI_TITLE,
  PIDSI_SUBJECT,
  PIDSI_AUTHOR,
  PIDSI_CREATE_DTM,
  PIDSI_KEYWORDS,
  PIDSI_COMMENTS,
  PIDSI_TEMPLATE,
  PIDSI_LASTAUTHOR,
  PIDSI_EDITTIME,
  PIDSI_LASTPRINTED,
  PIDSI_LASTSAVE_DTM,
  PIDSI_PAGECOUNT,
  PIDSI_WORDCOUNT,
  PIDSI_CHARCOUNT,
  PIDSI_APPNAME
)

#
# This was taken from someone else's example,
#  but I can't find where. If you know, please
#  tell me so I can give due credit.
#
def structured_storage (filename):
  """Pick out info from MS documents with embedded
   structured storage (typically MS Word docs etc.)

  Returns a dictionary of information found
  """

  if not pythoncom.StgIsStorageFile (filename):
    return {}

  flags = storagecon.STGM_READ | storagecon.STGM_SHARE_EXCLUSIVE
  storage = pythoncom.StgOpenStorage (filename, None, flags)
  try:
    properties_storage = storage.QueryInterface (pythoncom.IID_IPropertySetStorage)
  except pythoncom.com_error:
    return {}

  property_sheet = properties_storage.Open (FMTID_USER_DEFINED_PROPERTIES)
  try:
    data = property_sheet.ReadMultiple (PROPERTIES)
  finally:
    property_sheet = None

  title, subject, author, created_on, keywords, comments, template_used, \
   updated_by, edited_on, printed_on, saved_on, \
   n_pages, n_words, n_characters, \
   application = data

  result = {}
  if title: result['title'] = title
  if subject: result['subject'] = subject
  if author: result['author'] = author
  if created_on: result['created_on'] = created_on
  if keywords: result['keywords'] = keywords
  if comments: result['comments'] = comments
  if template_used: result['template_used'] = template_used
  if updated_by: result['updated_by'] = updated_by
  if edited_on: result['edited_on'] = edited_on
  if printed_on: result['printed_on'] = printed_on
  if saved_on: result['saved_on'] = saved_on
  if n_pages: result['n_pages'] = n_pages
  if n_words: result['n_words'] = n_words
  if n_characters: result['n_characters'] = n_characters
  if application: result['application'] = application
  return result

if __name__ == '__main__':
  try:
    print 'Desktop =>', desktop ()
    print 'Common Desktop =>', desktop (1)
    print 'Application Data =>', application_data ()
    print 'Common Application Data =>', application_data (1)
    print 'Bookmarks =>', bookmarks ()
    print 'Common Bookmarks =>', bookmarks (1)
    print 'Start Menu =>', start_menu ()
    print 'Common Start Menu =>', start_menu (1)
    print 'Programs =>', programs ()
    print 'Common Programs =>', programs (1)
    print 'Startup =>', startup ()
    print 'Common Startup =>', startup (1)
    print 'My Documents =>', my_documents ()
    print 'Recent =>', recent ()
    print 'SendTo =>', sendto ()
  finally:
    raw_input ("Press enter...")

