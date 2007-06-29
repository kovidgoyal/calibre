##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
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
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.Warning
''' Post installation script for linux '''
import sys, os
from subprocess import check_call

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

def setup_completion():
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
        f.write(opts_and_exts('lit2lrf', txtop, ['lit']))
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
        import traceback
        traceback.print_exc()
        
def setup_udev_rules():
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

def post_install():
    if os.geteuid() != 0:
        print >> sys.stderr, 'You must be root to run this command.'
        sys.exit(1)
        
    setup_udev_rules()
    setup_completion()
         
if __name__ == '__main__':
    post_install()           
    
    
      

