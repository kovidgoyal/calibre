" Project wide builtins
let $PYFLAKES_BUILTINS = "_,dynamic_property,__,P,I,lopen,icu_lower,icu_upper,icu_title,ngettext"

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
            \'/usr/include/ImageMagick',
            \]
let g:syntastic_c_include_dirs = g:syntastic_cpp_include_dirs

set wildignore+=resources/viewer/mathjax/**
set wildignore+=build/**

fun! CalibreLog()
    " Setup buffers to edit the calibre changelog and version info prior to
    " making a release.
    enew
    read ! bzr log -l 500
    setl nomodifiable noswapfile buftype=nofile
    edit Changelog.yaml
    edit src/calibre/constants.py
endfun

nnoremap \log :call CalibreLog()<CR>

python import init_calibre
python import calibre
