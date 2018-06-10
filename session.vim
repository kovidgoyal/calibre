" Scan the following dirs (recursively for tags
let g:project_tags_dirs = ['src/calibre']

" Include directories for C++ modules
let g:syntastic_cpp_include_dirs = [ 
            \'/usr/include/python2.7',
            \'/usr/include/podofo', 
            \'/usr/include/qt/QtCore', 
            \'/usr/include/qt/QtGui', 
            \'/usr/include/qt',
            \'/usr/include/freetype2',
            \'/usr/include/fontconfig',
            \'src/unrar',
            \]
let g:syntastic_c_include_dirs = g:syntastic_cpp_include_dirs
let g:syntastic_python_flake8_exec = 'flake8-python2'
let g:syntastic_python_flake8_args = '--filename='. shellescape('*.py,*.recipe')

set wildignore+=resources/viewer/mathjax/*
set wildignore+=resources/rapydscript/lib/*
set wildignore+=build/*
set wildignore+=dist/*
set wildignore+=manual/generated/*
set wildignore+=manual/locale/*

fun! CalibreLog()
    " Setup buffers to edit the calibre changelog and version info prior to
    " making a release.
    enew
    read ! git log  "--pretty=\%an:::\%n\%s\%n\%b\%n" -500
    setl nomodifiable noswapfile buftype=nofile
    hi def link au Keyword
    syntax match au /^.*:::$/
    nnoremap <silent> <buffer> n :call cursor(1+search('\V:::\$', 'n'), 0)<CR>
    nnoremap <silent> <buffer> yb v/#<CR>t<Space>y:nohl<CR>
    normal! gg2j
    edit Changelog.yaml
    edit src/calibre/constants.py
endfun

nnoremap \log :call CalibreLog()<CR>

python import init_calibre
python import calibre
