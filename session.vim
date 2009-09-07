" Project wide builtins
let g:pyflakes_builtins += ["dynamic_property", "__", "P"]

python << EOFPY
import os

import vipy

source_file = vipy.vipy.eval('expand("<sfile>")')
project_dir = os.path.dirname(source_file)
src_dir = os.path.abspath(os.path.join(project_dir, 'src'))
base_dir = os.path.join(src_dir, 'calibre')

vipy.session.initialize(project_name='calibre', src_dir=src_dir,
            project_dir=project_dir, base_dir=base_dir)
EOFPY
