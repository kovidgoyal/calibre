##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#!/usr/bin/env python
import sys, re, os, shutil
sys.path.append('src')
from libprs500 import __version__ as VERSION

import ez_setup
ez_setup.use_setuptools()
from setuptools import setup, find_packages


if sys.hexversion < 0x2050000:
    print >> sys.stderr, "You must use python >= 2.5 Try invoking this script as python2.5 setup.py."
    print >> sys.stderr, "If you are using easy_install, try easy_install-2.5"
    sys.exit(1)
    
try:
  from PIL import Image
except ImportError:
  import Image
  print >>sys.stderr, "You do not have the Python Imaging Library correctly installed."
  sys.exit(1)

setup(
      name='libprs500', 
      packages = find_packages('src'), 
      package_dir = { '' : 'src' }, 
      version=VERSION, 
      author='Kovid Goyal', 
      author_email='kovid@kovidgoyal.net', 
      url = 'http://libprs500.kovidgoyal.net', 
      package_data = { 
                        'libprs500.ebooks' : ['*.jpg', '*.pl'], 
                        'libpre500.ebooks.lrf.fonts' : ['*.ttf'],
                     }, 
      include_package_data = True,
      entry_points = {
        'console_scripts': [ \
                             'prs500 = libprs500.devices.prs500.cli.main:main', \
                             'lrf-meta = libprs500.ebooks.lrf.meta:main', \
                             'rtf-meta = libprs500.ebooks.metadata.rtf:main', \
                             'txt2lrf = libprs500.ebooks.lrf.txt.convert_from:main', \
                             'html2lrf = libprs500.ebooks.lrf.html.convert_from:main',\
                           ], 
        'gui_scripts'    : [ 'libprs500 = libprs500.gui.main:main']
      }, 
      zip_safe = True,
      description = 
                  """
                  Ebook management application.
                  """, 
      long_description = 
      """
      libprs500 is a ebook management application. It maintains an ebook library
      and allows for easy transfer of books from the library to an ebook reader.
      At the moment, it supports the `SONY Portable Reader`_.
      
      It can also convert various popular ebook formats into LRF, the native
      ebook format of the SONY Reader.
      
      For screenshots: https://libprs500.kovidgoyal.net/wiki/Screenshots
      
      For installation/usage instructions please see 
      https://libprs500.kovidgoyal.net/wiki/WikiStart#Installation
      
      For SVN access: svn co https://svn.kovidgoyal.net/code/libprs500
      
        .. _SONY Portable Reader: http://Sony.com/reader
        .. _USB: http://www.usb.org  
      """, 
      license = 'GPL', 
      classifiers = [
        'Development Status :: 3 - Alpha', 
        'Environment :: Console', 
        'Environment :: X11 Applications :: Qt', 
        'Intended Audience :: Developers', 
        'Intended Audience :: End Users/Desktop', 
        'License :: OSI Approved :: GNU General Public License (GPL)', 
        'Natural Language :: English', 
        'Operating System :: POSIX :: Linux', 
        'Programming Language :: Python', 
        'Topic :: Software Development :: Libraries :: Python Modules', 
        'Topic :: System :: Hardware :: Hardware Drivers'
        ]
     )

if '--uninstall' in ' '.join(sys.argv[1:]):
    sys.exit(0)

try:
  import PyQt4
except ImportError:
  print "You do not have PyQt4 installed. The GUI will not work.", \
        "You can obtain PyQt4 from http://www.riverbankcomputing.co.uk/pyqt/download.php"
else:
  import PyQt4.QtCore
  if PyQt4.QtCore.PYQT_VERSION < 0x40101:
    print "WARNING: The GUI needs PyQt >= 4.1.1"

import os
def options(parse_options):
    options, args, parser = parse_options(['dummy'], cli=False) 
    options = parser.option_list
    for group in parser.option_groups:
        options += group.option_list
    opts = []
    for opt in options:
        opts.extend(opt._short_opts)
        opts.extend(opt._long_opts)
    return opts

def opts_and_exts(name, op, exts):
    opts = ' '.join(options(op))
    exts.extend([i.upper() for i in exts])
    exts='|'.join(exts)
    return '_'+name+'()'+\
'''
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="%s"
    pics="@(jpg|jpeg|png|gif|bmp|JPG|JPEG|PNG|GIF|BMP)"

    case "${prev}" in
      --cover )
           _filedir "${pics}"
           return 0
           ;;
    esac

    case "${cur}" in
      --cover )
         _filedir "${pics}"
         return 0
         ;;
      -* )
         COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
         return 0
         ;;
      *  )
        _filedir '@(%s)'
        return 0
        ;;
    esac

}
complete -o filenames -F _'''%(opts,exts) + name + ' ' + name +"\n\n"



if os.access('/etc/bash_completion.d', os.W_OK):
    try:
        print 'Setting up bash completion...',
        sys.stdout.flush()
        from libprs500.ebooks.lrf.html.convert_from import parse_options as htmlop
        from libprs500.ebooks.lrf.txt.convert_from import parse_options as txtop
        from libprs500.ebooks.lrf.meta import parse_options as metaop
        f = open('/etc/bash_completion.d/libprs500', 'wb')
        f.write('# libprs500 Bash Shell Completion\n')
        f.write(opts_and_exts('html2lrf', htmlop, 
                              ['htm', 'html', 'xhtml', 'xhtm', 'rar', 'zip']))
        f.write(opts_and_exts('txt2lrf', txtop, ['txt']))
        f.write(opts_and_exts('lrf-meta', metaop, ['lrf']))
        f.write('''
_prs500_ls()
{
  local pattern search listing prefix
  pattern="$1"
  search="$1"
  if [[ -n "{$pattern}" ]]; then
    if [[ "${pattern:(-1)}" == "/" ]]; then
      pattern=""
    else
      pattern="$(basename ${pattern} 2> /dev/null)"
      search="$(dirname ${search} 2> /dev/null)"
    fi
  fi

  if [[  "x${search}" == "x" || "x${search}" == "x." ]]; then
    search="/"
  fi

  listing="$(prs500 ls ${search} 2>/dev/null)"

  prefix="${search}"
  if [[ "x${prefix:(-1)}" != "x/" ]]; then
    prefix="${prefix}/"
  fi

  echo $(compgen -P "${prefix}" -W "${listing}" "${pattern}") 
}

_prs500()
{
  local cur prev 
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"
  COMPREPLY=()
  case "${prev}" in
    ls|rm|mkdir|touch|cat )        
        COMPREPLY=( $(_prs500_ls "${cur}") )
        return 0
        ;;
    cp )
        if [[ ${cur} == prs500:* ]]; then
          COMPREPLY=( $(_prs500_ls "${cur:7}") )
          return 0
        else
          _filedir
          return 0
        fi
        ;;
    prs500 )
        COMPREPLY=( $(compgen -W "cp ls rm mkdir touch cat info books df" "${cur}") )
        return 0
        ;;
    * )
        if [[ ${cur} == prs500:* ]]; then
          COMPREPLY=( $(_prs500_ls "${cur:7}") )
          return 0
        else
          if [[ ${prev} == prs500:* ]]; then
            _filedir
            return 0
          else
            COMPREPLY=( $(compgen -W "prs500:" "${cur}") )
            return 0
          fi
          return 0
        fi
       ;;
  esac
}
complete -o nospace  -F _prs500 prs500

''')
        f.close()
        print 'done'
    except:
        print 'failed'
                

if os.access('/etc/udev/rules.d', os.W_OK):
  from subprocess import check_call
  print 'Trying to setup udev rules...',
  sys.stdout.flush()
  udev = open('/etc/udev/rules.d/95-libprs500.rules', 'w')
  udev.write('''# Sony Reader PRS-500\n'''
             '''BUS=="usb", SYSFS{idProduct}=="029b", SYSFS{idVendor}=="054c", MODE="660", GROUP="plugdev"\n'''
             )
  udev.close()
  try:
      check_call('udevstart', shell=True)
      print 'success'
  except:
      try:
          check_call('/etc/init.d/udev reload', shell=True)
          print 'success'
      except:
          print >>sys.stderr, "Couldn't reload udev, you may have to reboot"
  
