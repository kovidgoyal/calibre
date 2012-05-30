" Project wide builtins
let $PYFLAKES_BUILTINS = "_,dynamic_property,__,P,I,lopen,icu_lower,icu_upper,icu_title,ngettext"

" Include directories for C modules
let g:syntastic_c_include_dirs = [ '/usr/include/podofo']

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
