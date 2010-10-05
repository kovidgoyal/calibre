#!/usr/bin/env python
'''
Tests for the 'cheetah' command.

Besides unittest usage, recognizes the following command-line options:
    --list CheetahWrapper.py
        List all scenarios that are tested.  The argument is the path
        of this script.
     --nodelete
        Don't delete scratch directory at end.
     --output
        Show the output of each subcommand.  (Normally suppressed.)
'''
import os
import os.path
import pdb
import re                                     # Used by listTests.
import shutil
import sys
import tempfile
import unittest

from optparse import OptionParser
from Cheetah.CheetahWrapper import CheetahWrapper  # Used by NoBackup.

try:
    from subprocess import Popen, PIPE, STDOUT
    class Popen4(Popen):
        def __init__(self, cmd, bufsize=-1, shell=True, close_fds=True,
                        stdin=PIPE, stdout=PIPE, stderr=STDOUT, **kwargs):

            super(Popen4, self).__init__(cmd, bufsize=bufsize, shell=shell,
                            close_fds=close_fds, stdin=stdin, stdout=stdout,
                            stderr=stderr, **kwargs)

            self.tochild = self.stdin
            self.fromchild = self.stdout
            self.childerr = self.stderr
except ImportError:
    from popen2 import Popen4

DELETE = True # True to clean up after ourselves, False for debugging.
OUTPUT = False # Normally False, True for debugging.

BACKUP_SUFFIX = CheetahWrapper.BACKUP_SUFFIX

def warn(msg):
    sys.stderr.write(msg + '\n')

class CFBase(unittest.TestCase):
    """Base class for "cheetah compile" and "cheetah fill" unit tests.
    """
    srcDir = '' # Nonblank to create source directory.
    subdirs = ('child', 'child/grandkid') # Delete in reverse order.
    srcFiles = ('a.tmpl', 'child/a.tmpl', 'child/grandkid/a.tmpl')
    expectError = False # Used by --list option.

    def inform(self, message):
        if self.verbose:
            print(message)

    def setUp(self):
        """Create the top-level directories, subdirectories and .tmpl
           files.
        """
        self.cmd = self.locate_cheetah('cheetah')
        pythonPath = os.getcwd()
        if not os.environ.get('PYTHONPATH'):
            os.environ['PYTHONPATH'] = pythonPath
        else:
            os.environ['PYTHONPATH'] = '%s:%s' % (os.environ['PYTHONPATH'], pythonPath)
        I = self.inform
        # Step 1: Create the scratch directory and chdir into it.
        self.scratchDir = scratchDir = tempfile.mktemp() 
        os.mkdir(scratchDir)
        self.origCwd = os.getcwd()
        os.chdir(scratchDir)
        if self.srcDir:
            os.mkdir(self.srcDir)
        # Step 2: Create source subdirectories.
        for dir in self.subdirs:
            os.mkdir(dir)
        # Step 3: Create the .tmpl files, each in its proper directory.
        for fil in self.srcFiles:
            f = open(fil, 'w')
            f.write("Hello, world!\n")
            f.close()

    def tearDown(self):
        os.chdir(self.origCwd)
        if DELETE:
            shutil.rmtree(self.scratchDir, True) # Ignore errors.
            if os.path.exists(self.scratchDir):
                warn("Warning: unable to delete scratch directory %s")
        else:
            warn("Warning: not deleting scratch directory %s" % self.scratchDir)


    def _checkDestFileHelper(self, path, expected, 
        allowSurroundingText, errmsg):
        """Low-level helper to check a destination file.

           in : path, string, the destination path.
                expected, string, the expected contents.
                allowSurroundingtext, bool, allow the result to contain
                  additional text around the 'expected' substring?
                errmsg, string, the error message.  It may contain the
                  following "%"-operator keys: path, expected, result.
           out: None
        """
        path = os.path.abspath(path)
        exists = os.path.exists(path)
        msg = "destination file missing: %s" % path
        self.failUnless(exists, msg)
        f = open(path, 'r')
        result = f.read()
        f.close()
        if allowSurroundingText:
            success = result.find(expected) != -1
        else:
            success = result == expected
        msg = errmsg % locals()
        self.failUnless(success, msg)


    def checkCompile(self, path):
        # Raw string to prevent "\n" from being converted to a newline.
        #expected = R"write('Hello, world!\n')"
        expected = "Hello, world!" # might output a u'' string
        errmsg = """\
destination file %(path)s doesn't contain expected substring:
%(expected)r"""
        self._checkDestFileHelper(path, expected, True, errmsg)


    def checkFill(self, path):
        expected = "Hello, world!\n"
        errmsg = """\
destination file %(path)s contains wrong result.
Expected %(expected)r
Found %(result)r"""
        self._checkDestFileHelper(path, expected, False, errmsg)


    def checkSubdirPyInit(self, path):
        """Verify a destination subdirectory exists and contains an
           __init__.py file.
        """
        exists = os.path.exists(path)
        msg = "destination subdirectory %s misssing" % path
        self.failUnless(exists, msg)
        initPath = os.path.join(path, "__init__.py")
        exists = os.path.exists(initPath)
        msg = "destination init file missing: %s" % initPath
        self.failUnless(exists, msg)


    def checkNoBackup(self, path):
        """Verify 'path' does not exist.  (To check --nobackup.)
        """
        exists = os.path.exists(path)
        msg = "backup file exists in spite of --nobackup: %s" % path
        self.failIf(exists, msg)

    def locate_cheetah(self, cmd):
        paths = os.getenv('PATH')
        if not paths:
            return cmd
        parts = cmd.split(' ')
        paths = paths.split(':')
        for p in paths:
            p = os.path.join(p, cmd)
            p = os.path.abspath(p)
            if os.path.isfile(p):
                return p
        return cmd

    def assertWin32Subprocess(self, cmd):
        _in, _out = os.popen4(cmd)
        _in.close()
        output = _out.read()
        rc = _out.close()
        if rc is None:
            rc = 0
        return rc, output

    def assertPosixSubprocess(self, cmd):
        cmd = cmd.replace('cheetah', self.cmd)
        process = Popen4(cmd, env=os.environ)
        process.tochild.close()
        output = process.fromchild.read()
        status = process.wait()
        process.fromchild.close()
        return status, output

    def assertSubprocess(self, cmd, nonzero=False):
        status, output = None, None
        if sys.platform == 'win32':
            status, output = self.assertWin32Subprocess(cmd)
        else:
            status, output = self.assertPosixSubprocess(cmd)

        if not nonzero:
            self.failUnlessEqual(status, 0, '''Subprocess exited with a non-zero status (%d)
                            %s''' % (status, output))
        else:
            self.failIfEqual(status, 0, '''Subprocess exited with a zero status (%d)
                            %s''' % (status, output))
        return output 
    
    def go(self, cmd, expectedStatus=0, expectedOutputSubstring=None):
        """Run a "cheetah compile" or "cheetah fill" subcommand.

           in : cmd, string, the command to run.
                expectedStatus, int, subcommand's expected output status.
                  0 if the subcommand is expected to succeed, 1-255 otherwise.
                expectedOutputSubstring, string, substring which much appear
                  in the standard output or standard error.  None to skip this
                  test.
           out: None.
        """
        output = self.assertSubprocess(cmd)
        if expectedOutputSubstring is not None:
            msg = "substring %r not found in subcommand output: %s" % \
                (expectedOutputSubstring, cmd)
            substringTest = output.find(expectedOutputSubstring) != -1
            self.failUnless(substringTest, msg)


class CFIdirBase(CFBase):
    """Subclass for tests with --idir.
    """
    srcDir = 'SRC'
    subdirs = ('SRC/child', 'SRC/child/grandkid') # Delete in reverse order.
    srcFiles = ('SRC/a.tmpl', 'SRC/child/a.tmpl', 'SRC/child/grandkid/a.tmpl')



##################################################
## TEST CASE CLASSES

class OneFile(CFBase):
    def testCompile(self):
        self.go("cheetah compile a.tmpl")
        self.checkCompile("a.py")

    def testFill(self):
        self.go("cheetah fill a.tmpl")
        self.checkFill("a.html")

    def testText(self):
        self.go("cheetah fill --oext txt a.tmpl")
        self.checkFill("a.txt")


class OneFileNoExtension(CFBase):
    def testCompile(self):
        self.go("cheetah compile a")
        self.checkCompile("a.py")

    def testFill(self):
        self.go("cheetah fill a")
        self.checkFill("a.html")

    def testText(self):
        self.go("cheetah fill --oext txt a")
        self.checkFill("a.txt")


class SplatTmpl(CFBase):
    def testCompile(self):
        self.go("cheetah compile *.tmpl")
        self.checkCompile("a.py")

    def testFill(self):
        self.go("cheetah fill *.tmpl")
        self.checkFill("a.html")

    def testText(self):
        self.go("cheetah fill --oext txt *.tmpl")
        self.checkFill("a.txt")

class ThreeFilesWithSubdirectories(CFBase):
    def testCompile(self):
        self.go("cheetah compile a.tmpl child/a.tmpl child/grandkid/a.tmpl")
        self.checkCompile("a.py")
        self.checkCompile("child/a.py")
        self.checkCompile("child/grandkid/a.py")

    def testFill(self):
        self.go("cheetah fill a.tmpl child/a.tmpl child/grandkid/a.tmpl")
        self.checkFill("a.html")
        self.checkFill("child/a.html")
        self.checkFill("child/grandkid/a.html")

    def testText(self):
        self.go("cheetah fill --oext txt a.tmpl child/a.tmpl child/grandkid/a.tmpl")
        self.checkFill("a.txt")
        self.checkFill("child/a.txt")
        self.checkFill("child/grandkid/a.txt")


class ThreeFilesWithSubdirectoriesNoExtension(CFBase):
    def testCompile(self):
        self.go("cheetah compile a child/a child/grandkid/a")
        self.checkCompile("a.py")
        self.checkCompile("child/a.py")
        self.checkCompile("child/grandkid/a.py")

    def testFill(self):
        self.go("cheetah fill a child/a child/grandkid/a")
        self.checkFill("a.html")
        self.checkFill("child/a.html")
        self.checkFill("child/grandkid/a.html")

    def testText(self):
        self.go("cheetah fill --oext txt a child/a child/grandkid/a")
        self.checkFill("a.txt")
        self.checkFill("child/a.txt")
        self.checkFill("child/grandkid/a.txt")


class SplatTmplWithSubdirectories(CFBase):
    def testCompile(self):
        self.go("cheetah compile *.tmpl child/*.tmpl child/grandkid/*.tmpl")
        self.checkCompile("a.py")
        self.checkCompile("child/a.py")
        self.checkCompile("child/grandkid/a.py")

    def testFill(self):
        self.go("cheetah fill *.tmpl child/*.tmpl child/grandkid/*.tmpl")
        self.checkFill("a.html")
        self.checkFill("child/a.html")
        self.checkFill("child/grandkid/a.html")

    def testText(self):
        self.go("cheetah fill --oext txt *.tmpl child/*.tmpl child/grandkid/*.tmpl")
        self.checkFill("a.txt")
        self.checkFill("child/a.txt")
        self.checkFill("child/grandkid/a.txt")


class OneFileWithOdir(CFBase):
    def testCompile(self):
        self.go("cheetah compile --odir DEST a.tmpl")
        self.checkSubdirPyInit("DEST")
        self.checkCompile("DEST/a.py")

    def testFill(self):
        self.go("cheetah fill --odir DEST a.tmpl")
        self.checkFill("DEST/a.html")

    def testText(self):
        self.go("cheetah fill --odir DEST --oext txt a.tmpl")
        self.checkFill("DEST/a.txt")


class VarietyWithOdir(CFBase):
    def testCompile(self):
        self.go("cheetah compile --odir DEST a.tmpl child/a child/grandkid/*.tmpl")
        self.checkSubdirPyInit("DEST")
        self.checkSubdirPyInit("DEST/child")
        self.checkSubdirPyInit("DEST/child/grandkid")
        self.checkCompile("DEST/a.py")
        self.checkCompile("DEST/child/a.py")
        self.checkCompile("DEST/child/grandkid/a.py")

    def testFill(self):
        self.go("cheetah fill --odir DEST a.tmpl child/a child/grandkid/*.tmpl")
        self.checkFill("DEST/a.html")
        self.checkFill("DEST/child/a.html")
        self.checkFill("DEST/child/grandkid/a.html")

    def testText(self):
        self.go("cheetah fill --odir DEST --oext txt a.tmpl child/a child/grandkid/*.tmpl")
        self.checkFill("DEST/a.txt")
        self.checkFill("DEST/child/a.txt")
        self.checkFill("DEST/child/grandkid/a.txt")


class RecurseExplicit(CFBase):
    def testCompile(self):
        self.go("cheetah compile -R child")
        self.checkCompile("child/a.py")
        self.checkCompile("child/grandkid/a.py")

    def testFill(self):
        self.go("cheetah fill -R child")
        self.checkFill("child/a.html")
        self.checkFill("child/grandkid/a.html")

    def testText(self):
        self.go("cheetah fill -R --oext txt child")
        self.checkFill("child/a.txt")
        self.checkFill("child/grandkid/a.txt")


class RecurseImplicit(CFBase):
    def testCompile(self):
        self.go("cheetah compile -R")
        self.checkCompile("child/a.py")
        self.checkCompile("child/grandkid/a.py")

    def testFill(self):
        self.go("cheetah fill -R")
        self.checkFill("a.html")
        self.checkFill("child/a.html")
        self.checkFill("child/grandkid/a.html")

    def testText(self):
        self.go("cheetah fill -R --oext txt")
        self.checkFill("a.txt")
        self.checkFill("child/a.txt")
        self.checkFill("child/grandkid/a.txt")


class RecurseExplicitWIthOdir(CFBase):
    def testCompile(self):
        self.go("cheetah compile -R --odir DEST child")
        self.checkSubdirPyInit("DEST/child")
        self.checkSubdirPyInit("DEST/child/grandkid")
        self.checkCompile("DEST/child/a.py")
        self.checkCompile("DEST/child/grandkid/a.py")

    def testFill(self):
        self.go("cheetah fill -R --odir DEST child")
        self.checkFill("DEST/child/a.html")
        self.checkFill("DEST/child/grandkid/a.html")

    def testText(self):
        self.go("cheetah fill -R --odir DEST --oext txt child")
        self.checkFill("DEST/child/a.txt")
        self.checkFill("DEST/child/grandkid/a.txt")


class Flat(CFBase):
    def testCompile(self):
        self.go("cheetah compile --flat child/a.tmpl")
        self.checkCompile("a.py")

    def testFill(self):
        self.go("cheetah fill --flat child/a.tmpl")
        self.checkFill("a.html")

    def testText(self):
        self.go("cheetah fill --flat --oext txt child/a.tmpl")
        self.checkFill("a.txt")


class FlatRecurseCollision(CFBase):
    expectError = True

    def testCompile(self):
        self.assertSubprocess("cheetah compile -R --flat", nonzero=True)

    def testFill(self):
        self.assertSubprocess("cheetah fill -R --flat", nonzero=True)

    def testText(self):
        self.assertSubprocess("cheetah fill -R --flat", nonzero=True)


class IdirRecurse(CFIdirBase):
    def testCompile(self):
        self.go("cheetah compile -R --idir SRC child")
        self.checkSubdirPyInit("child")
        self.checkSubdirPyInit("child/grandkid")
        self.checkCompile("child/a.py")
        self.checkCompile("child/grandkid/a.py")

    def testFill(self):
        self.go("cheetah fill -R --idir SRC child")
        self.checkFill("child/a.html")
        self.checkFill("child/grandkid/a.html")

    def testText(self):
        self.go("cheetah fill -R --idir SRC --oext txt child")
        self.checkFill("child/a.txt")
        self.checkFill("child/grandkid/a.txt")


class IdirOdirRecurse(CFIdirBase):
    def testCompile(self):
        self.go("cheetah compile -R --idir SRC --odir DEST child")
        self.checkSubdirPyInit("DEST/child")
        self.checkSubdirPyInit("DEST/child/grandkid")
        self.checkCompile("DEST/child/a.py")
        self.checkCompile("DEST/child/grandkid/a.py")

    def testFill(self):
        self.go("cheetah fill -R --idir SRC --odir DEST child")
        self.checkFill("DEST/child/a.html")
        self.checkFill("DEST/child/grandkid/a.html")

    def testText(self):
        self.go("cheetah fill -R --idir SRC --odir DEST --oext txt child")
        self.checkFill("DEST/child/a.txt")
        self.checkFill("DEST/child/grandkid/a.txt")


class IdirFlatRecurseCollision(CFIdirBase):
    expectError = True

    def testCompile(self):
        self.assertSubprocess("cheetah compile -R --flat --idir SRC", nonzero=True)

    def testFill(self):
        self.assertSubprocess("cheetah fill -R --flat --idir SRC", nonzero=True)

    def testText(self):
        self.assertSubprocess("cheetah fill -R --flat --idir SRC --oext txt", nonzero=True)


class NoBackup(CFBase):
    """Run the command twice each time and verify a backup file is 
       *not* created.
    """
    def testCompile(self):
        self.go("cheetah compile --nobackup a.tmpl")
        self.go("cheetah compile --nobackup a.tmpl")
        self.checkNoBackup("a.py" + BACKUP_SUFFIX)

    def testFill(self):
        self.go("cheetah fill --nobackup a.tmpl")
        self.go("cheetah fill --nobackup a.tmpl")
        self.checkNoBackup("a.html" + BACKUP_SUFFIX)

    def testText(self):
        self.go("cheetah fill --nobackup --oext txt a.tmpl")
        self.go("cheetah fill --nobackup --oext txt a.tmpl")
        self.checkNoBackup("a.txt" + BACKUP_SUFFIX)

def listTests(cheetahWrapperFile):
    """cheetahWrapperFile, string, path of this script.

       XXX TODO: don't print test where expectError is true.
    """
    rx = re.compile( R'self\.go\("(.*?)"\)' )
    f = open(cheetahWrapperFile)
    while True:
        lin = f.readline()
        if not lin:
            break
        m = rx.search(lin)
        if m:
            print(m.group(1))
    f.close()

def main():
    global DELETE, OUTPUT
    parser = OptionParser()
    parser.add_option("--list", action="store", dest="listTests")
    parser.add_option("--nodelete", action="store_true")
    parser.add_option("--output", action="store_true")
    # The following options are passed to unittest.
    parser.add_option("-e", "--explain", action="store_true")
    parser.add_option("-v", "--verbose", action="store_true")
    parser.add_option("-q", "--quiet", action="store_true")
    opts, files = parser.parse_args()
    if opts.nodelete:
        DELETE = False
    if opts.output:
        OUTPUT = True
    if opts.listTests:
        listTests(opts.listTests)
    else:
        # Eliminate script-specific command-line arguments to prevent
        # errors in unittest.
        del sys.argv[1:]
        for opt in ("explain", "verbose", "quiet"):
            if getattr(opts, opt):
                sys.argv.append("--" + opt)
        sys.argv.extend(files)
        unittest.main()
        
if __name__ == '__main__':
    main()

# vim: sw=4 ts=4 expandtab
