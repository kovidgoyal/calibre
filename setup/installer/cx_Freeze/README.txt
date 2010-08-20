Please see cx_Freeze.html for documentation on how to use cx_Freeze.

To build:

python setup.py build
python setup.py install

On Windows I have used the MinGW compiler (http://www.mingw.org)

python setup.py build --compiler=mingw32
python setup.py build --compiler=mingw32 install

