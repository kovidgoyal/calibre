
from glob import glob
import os
from os import listdir
import os.path
import re
from tempfile import mktemp

def _escapeRegexChars(txt,
                     escapeRE=re.compile(r'([\$\^\*\+\.\?\{\}\[\]\(\)\|\\])')):
    return escapeRE.sub(r'\\\1', txt)

def findFiles(*args, **kw):
    """Recursively find all the files matching a glob pattern.

    This function is a wrapper around the FileFinder class.  See its docstring
    for details about the accepted arguments, etc."""
    
    return FileFinder(*args, **kw).files()
            
def replaceStrInFiles(files, theStr, repl):

    """Replace all instances of 'theStr' with 'repl' for each file in the 'files'
    list. Returns a dictionary with data about the matches found.

    This is like string.replace() on a multi-file basis.

    This function is a wrapper around the FindAndReplace class. See its
    docstring for more details."""
    
    pattern = _escapeRegexChars(theStr)
    return FindAndReplace(files, pattern, repl).results()

def replaceRegexInFiles(files, pattern, repl):

    """Replace all instances of regex 'pattern' with 'repl' for each file in the
    'files' list. Returns a dictionary with data about the matches found.

    This is like re.sub on a multi-file basis.

    This function is a wrapper around the FindAndReplace class. See its
    docstring for more details."""

    return FindAndReplace(files, pattern, repl).results()


##################################################
## CLASSES

class FileFinder:
    
    """Traverses a directory tree and finds all files in it that match one of
    the specified glob patterns."""
    
    def __init__(self, rootPath,
                 globPatterns=('*',),
                 ignoreBasenames=('CVS', '.svn'),
                 ignoreDirs=(),
                 ):
        
        self._rootPath = rootPath
        self._globPatterns = globPatterns
        self._ignoreBasenames = ignoreBasenames
        self._ignoreDirs = ignoreDirs
        self._files = []
        
        self.walkDirTree(rootPath)
            
    def walkDirTree(self, dir='.',
                    
                    listdir=os.listdir,
                    isdir=os.path.isdir,
                    join=os.path.join,
                    ):

        """Recursively walk through a directory tree and find matching files."""
        processDir = self.processDir
        filterDir = self.filterDir
        
        pendingDirs = [dir]
        addDir = pendingDirs.append
        getDir = pendingDirs.pop
        
        while pendingDirs:
            dir = getDir()
            ##  process this dir
            processDir(dir)
            
            ## and add sub-dirs 
            for baseName in listdir(dir):
                fullPath = join(dir, baseName)
                if isdir(fullPath):
                    if filterDir(baseName, fullPath):
                        addDir( fullPath )

    def filterDir(self, baseName, fullPath):
        
        """A hook for filtering out certain dirs. """
        
        return not (baseName in self._ignoreBasenames or 
                    fullPath in self._ignoreDirs)
    
    def processDir(self, dir, glob=glob):
        extend = self._files.extend
        for pattern in self._globPatterns:
            extend( glob(os.path.join(dir, pattern)) )
    
    def files(self):
        return self._files

class _GenSubberFunc:

    """Converts a 'sub' string in the form that one feeds to re.sub (backrefs,
    groups, etc.) into a function that can be used to do the substitutions in
    the FindAndReplace class."""
    
    backrefRE = re.compile(r'\\([1-9][0-9]*)')
    groupRE = re.compile(r'\\g<([a-zA-Z_][a-zA-Z_]*)>')
    
    def __init__(self, replaceStr):
        self._src = replaceStr
        self._pos = 0
        self._codeChunks = []
        self.parse()

    def src(self):
        return self._src
        
    def pos(self):
        return self._pos
    
    def setPos(self, pos):
        self._pos = pos

    def atEnd(self):
        return self._pos >= len(self._src)

    def advance(self, offset=1):
        self._pos += offset

    def readTo(self, to, start=None):
        if start == None:
            start = self._pos
        self._pos = to
        if self.atEnd():
            return self._src[start:]
        else:
            return self._src[start:to]

    ## match and get methods
        
    def matchBackref(self):
        return self.backrefRE.match(self.src(), self.pos())

    def getBackref(self):
        m = self.matchBackref()
        self.setPos(m.end())
        return m.group(1)
        
    def matchGroup(self):
        return self.groupRE.match(self.src(), self.pos())

    def getGroup(self):
        m = self.matchGroup()
        self.setPos(m.end())
        return m.group(1)

    ## main parse loop and the eat methods
    
    def parse(self):
        while not self.atEnd():
            if self.matchBackref():
                self.eatBackref()
            elif self.matchGroup():
                self.eatGroup()
            else:
                self.eatStrConst()
                
    def eatStrConst(self):
        startPos = self.pos()
        while not self.atEnd():
            if self.matchBackref() or self.matchGroup():
                break
            else:
                self.advance()
        strConst = self.readTo(self.pos(), start=startPos)
        self.addChunk(repr(strConst))
    
    def eatBackref(self):
        self.addChunk( 'm.group(' + self.getBackref() + ')' )

    def eatGroup(self):
        self.addChunk( 'm.group("' + self.getGroup() + '")' )
    
    def addChunk(self, chunk):
        self._codeChunks.append(chunk)

    ## code wrapping methods

    def codeBody(self):
        return ', '.join(self._codeChunks)

    def code(self):
        return "def subber(m):\n\treturn ''.join([%s])\n" % (self.codeBody())
    
    def subberFunc(self):
        exec(self.code())
        return subber


class FindAndReplace:
    
    """Find and replace all instances of 'patternOrRE' with 'replacement' for
    each file in the 'files' list. This is a multi-file version of re.sub().

    'patternOrRE' can be a raw regex pattern or
    a regex object as generated by the re module. 'replacement' can be any
    string that would work with patternOrRE.sub(replacement, fileContents).
    """
    
    def __init__(self, files, patternOrRE, replacement,
                 recordResults=True):

        
        if isinstance(patternOrRE, basestring):
            self._regex = re.compile(patternOrRE)
        else:
            self._regex = patternOrRE
        if isinstance(replacement, basestring):
            self._subber = _GenSubberFunc(replacement).subberFunc()
        else:
            self._subber = replacement

        self._pattern = pattern = self._regex.pattern
        self._files = files
        self._results = {}
        self._recordResults = recordResults

        ## see if we should use pgrep to do the file matching
        self._usePgrep = False
        if (os.popen3('pgrep')[2].read()).startswith('Usage:'):
            ## now check to make sure pgrep understands the pattern
            tmpFile = mktemp()
            open(tmpFile, 'w').write('#')
            if not (os.popen3('pgrep "' + pattern + '" ' + tmpFile)[2].read()):
                # it didn't print an error msg so we're ok
                self._usePgrep = True
            os.remove(tmpFile)

        self._run()

    def results(self):
        return self._results
    
    def _run(self):
        regex = self._regex
        subber = self._subDispatcher
        usePgrep = self._usePgrep
        pattern = self._pattern
        for file in self._files:
            if not os.path.isfile(file):
                continue # skip dirs etc.
            
            self._currFile = file
            found = False
            if 'orig' in locals():
                del orig
            if self._usePgrep:
                if os.popen('pgrep "' + pattern + '" ' + file ).read():
                    found = True
            else:
                orig = open(file).read()
                if regex.search(orig):
                    found = True
            if found:
                if 'orig' not in locals():
                    orig = open(file).read()
                new = regex.sub(subber, orig)
                open(file, 'w').write(new)

    def _subDispatcher(self, match):
        if self._recordResults:
            if self._currFile not in self._results:
                res = self._results[self._currFile] = {}
                res['count'] = 0
                res['matches'] = []
            else:
                res = self._results[self._currFile]
            res['count'] += 1
            res['matches'].append({'contents': match.group(),
                                   'start': match.start(),
                                   'end': match.end(),
                                   }
                                   )
        return self._subber(match)


class SourceFileStats:

    """
    """
    
    _fileStats = None
    
    def __init__(self, files):
        self._fileStats = stats = {}
        for file in files:
            stats[file] = self.getFileStats(file)

    def rawStats(self):
        return self._fileStats

    def summary(self):
        codeLines = 0
        blankLines = 0
        commentLines = 0
        totalLines = 0
        for fileStats in self.rawStats().values():
            codeLines += fileStats['codeLines']
            blankLines += fileStats['blankLines']
            commentLines += fileStats['commentLines']
            totalLines += fileStats['totalLines']
            
        stats = {'codeLines': codeLines,
                 'blankLines': blankLines,
                 'commentLines': commentLines,
                 'totalLines': totalLines,
                 }
        return stats
        
    def printStats(self):
        pass

    def getFileStats(self, fileName):
        codeLines = 0
        blankLines = 0
        commentLines = 0 
        commentLineRe = re.compile(r'\s#.*$')
        blankLineRe = re.compile('\s$')
        lines = open(fileName).read().splitlines()
        totalLines = len(lines)
        
        for line in lines:
            if commentLineRe.match(line):
                commentLines += 1
            elif blankLineRe.match(line):
                blankLines += 1
            else:
                codeLines += 1

        stats = {'codeLines': codeLines,
                 'blankLines': blankLines,
                 'commentLines': commentLines,
                 'totalLines': totalLines,
                 }
        
        return stats
