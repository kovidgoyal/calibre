" Include directories for C++ modules
let g:syntastic_cpp_include_dirs = [ 
            \'/usr/include/python2.7',
            \'/usr/include/podofo', 
            \'/usr/include/qt4/QtCore', 
            \'/usr/include/qt4/QtGui', 
            \'/usr/include/qt4',
            \'/usr/include/freetype2',
            \'/usr/include/fontconfig',
            \'src/qtcurve/common', 'src/qtcurve',
            \'src/unrar',
            \'src/qt-harfbuzz/src',
            \'/usr/include/ImageMagick',
            \]
let g:syntastic_c_include_dirs = g:syntastic_cpp_include_dirs

set wildignore+=resources/viewer/mathjax/**
set wildignore+=build/**
set wildignore+=dist/**

fun! CalibreLog()
    " Setup buffers to edit the calibre changelog and version info prior to
    " making a release.
    enew
    read ! git log "--pretty=\%an:::\%n\%s\%n\%b\%n" -500
    setl nomodifiable noswapfile buftype=nofile nohlsearch
    hi def link au Keyword
    syntax match au /^.*:::$/
    nnoremap <silent> <buffer> ]n /:::$/1<CR>
    nnoremap <silent> <buffer> yb vt#t<Space>y
    normal! gg2j
    edit Changelog.yaml
    edit src/calibre/constants.py
endfun

nnoremap \log :call CalibreLog()<CR>

python import init_calibre
python import calibre
