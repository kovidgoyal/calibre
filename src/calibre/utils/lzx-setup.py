from distutils.core import setup, Extension

setup(name="lzx", version="1.0",
      ext_modules=[Extension('lzx', sources=['lzx/lzxmodule.c', 'lzx/lzxd.c'],
                             include_dirs=['lzx'])])
