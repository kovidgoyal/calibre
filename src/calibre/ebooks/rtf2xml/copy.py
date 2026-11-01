#########################################################################
#                                                                       #
#                                                                       #
#   copyright 2002 Paul Henry Tremblay                                  #
#                                                                       #
#   This program is distributed in the hope that it will be useful,     #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of      #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU    #
#   General Public License for more details.                            #
#                                                                       #
#                                                                       #
#########################################################################
import os
import shutil


class Copy:
    """Copy each changed file to a directory for debugging purposes"""

    __dir = ''

    def __init__(
        self,
        bug_handler: type[Exception] = RuntimeError,
        file: str | None = None,
        deb_dir: str | None = None,
    ) -> None:
        self.__file = file
        self.__bug_handler = bug_handler

    def set_dir(self, deb_dir: str | None) -> None:
        """Set the temporary directory to write files to"""
        if deb_dir is None:
            message = 'No directory has been provided to write to in the copy.py'
            raise self.__bug_handler(message)
        check = os.path.isdir(deb_dir)
        if not check:
            message = '{deb_dir} is not a directory'.format(**vars())
            raise self.__bug_handler(message)
        Copy.__dir = deb_dir

    def remove_files(self) -> None:
        """Remove files from directory"""
        self.__remove_the_files(Copy.__dir)

    def __remove_the_files(self, the_dir: str) -> None:
        """Remove files from directory"""
        list_of_files = os.listdir(the_dir)
        for file in list_of_files:
            rem_file = os.path.join(Copy.__dir, file)
            if os.path.isdir(rem_file):
                self.__remove_the_files(rem_file)
            else:
                try:
                    os.remove(rem_file)
                except OSError:
                    pass

    def copy_file(self, file: str, new_file: str) -> None:
        """
        Copy the file to a new name
        If the platform is linux, use the faster linux command
        of cp. Otherwise, use a safe python method.
        """
        write_file = os.path.join(Copy.__dir, new_file)
        shutil.copyfile(file, write_file)

    def rename(self, source: str, dest: str) -> None:
        shutil.copyfile(source, dest)
