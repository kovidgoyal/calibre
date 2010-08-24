# An advanced setup script to create multiple executables and demonstrate a few
# of the features available to setup scripts
#
# hello.py is a very simple "Hello, world" type script which also displays the
# environment in which the script runs
#
# Run the build process by running the command 'python setup.py build'
#
# If everything works well you should find a subdirectory in the build
# subdirectory that contains the files needed to run the script without Python

import sys
from cx_Freeze import setup, Executable

executables = [
        Executable("advanced_1.py"),
        Executable("advanced_2.py")
]

buildOptions = dict(
        compressed = True,
        includes = ["testfreeze_1", "testfreeze_2"],
        path = sys.path + ["modules"])

setup(
        name = "advanced_cx_Freeze_sample",
        version = "0.1",
        description = "Advanced sample cx_Freeze script",
        options = dict(build_exe = buildOptions),
        executables = executables)

