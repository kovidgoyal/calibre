"""SourceReader class for Cheetah's Parser and CodeGenerator
"""
import re
import sys

EOLre = re.compile(r'[ \f\t]*(?:\r\n|\r|\n)')
EOLZre = re.compile(r'(?:\r\n|\r|\n|\Z)')
ENCODINGsearch = re.compile("coding[=:]\s*([-\w.]+)").search

class Error(Exception):
    pass
                                
class SourceReader(object):
    def __init__(self, src, filename=None, breakPoint=None, encoding=None):
        self._src = src
        self._filename = filename
        self._srcLen = len(src)
        if breakPoint == None:
            self._breakPoint = self._srcLen
        else:
            self.setBreakPoint(breakPoint)
        self._pos = 0
        self._bookmarks = {}
        self._posTobookmarkMap = {}

        ## collect some meta-information
        self._EOLs = []
        pos = 0
        while pos < len(self):
            EOLmatch = EOLZre.search(src, pos)
            self._EOLs.append(EOLmatch.start())
            pos = EOLmatch.end()
            
        self._BOLs = []
        for pos in self._EOLs:
            BOLpos = self.findBOL(pos)
            self._BOLs.append(BOLpos)
        
    def src(self):
        return self._src

    def filename(self):
        return self._filename

    def __len__(self):
        return self._breakPoint
    
    def __getitem__(self, i):
        if not isinstance(i, int):
            self.checkPos(i.stop)
        else:
            self.checkPos(i)
        return self._src[i]
    
    def __getslice__(self, i, j):
        i = max(i, 0); j = max(j, 0)
        return self._src[i:j]

    def splitlines(self):
        if not hasattr(self, '_srcLines'):
            self._srcLines = self._src.splitlines()
        return self._srcLines

    def lineNum(self, pos=None):
        if pos == None:
            pos = self._pos
            
        for i in range(len(self._BOLs)):
            if pos >= self._BOLs[i] and pos <= self._EOLs[i]:
                return i
            
    def getRowCol(self, pos=None):
        if pos == None:
            pos = self._pos
        lineNum = self.lineNum(pos)
        BOL, EOL = self._BOLs[lineNum], self._EOLs[lineNum]
        return lineNum+1, pos-BOL+1
            
    def getRowColLine(self, pos=None):
        if pos == None:
            pos = self._pos
        row, col = self.getRowCol(pos)    
        return row, col, self.splitlines()[row-1]

    def getLine(self, pos):
        if pos == None:
            pos = self._pos
        lineNum = self.lineNum(pos)
        return self.splitlines()[lineNum]
        
    def pos(self):
        return self._pos
    
    def setPos(self, pos):
        self.checkPos(pos)
        self._pos = pos


    def validPos(self, pos):
        return pos <= self._breakPoint and pos >=0 
                    
    def checkPos(self, pos):
        if not pos <= self._breakPoint:
            raise Error("pos (" + str(pos) + ") is invalid: beyond the stream's end (" +
                        str(self._breakPoint-1) + ")" )
        elif not pos >=0:
            raise Error("pos (" + str(pos) + ") is invalid: less than 0" )

    def breakPoint(self):
        return self._breakPoint
    
    def setBreakPoint(self, pos):
        if pos > self._srcLen:
            raise Error("New breakpoint (" + str(pos) +
                        ") is invalid: beyond the end of stream's source string (" +
                        str(self._srcLen) + ")" )
        elif not pos >= 0:
            raise Error("New breakpoint (" + str(pos) + ") is invalid: less than 0" )        
        
        self._breakPoint = pos

    def setBookmark(self, name):
        self._bookmarks[name] = self._pos
        self._posTobookmarkMap[self._pos] = name

    def hasBookmark(self, name):
        return name in self._bookmarks
    
    def gotoBookmark(self, name):
        if not self.hasBookmark(name):
            raise Error("Invalid bookmark (" + name + ") is invalid: does not exist")
        pos = self._bookmarks[name]
        if not self.validPos(pos):
            raise Error("Invalid bookmark (" + name + ', '+
                        str(pos) + ") is invalid: pos is out of range" )        
        self._pos = pos

    def atEnd(self):
        return self._pos >= self._breakPoint

    def atStart(self):
        return self._pos == 0
                          
    def peek(self, offset=0):
        self.checkPos(self._pos+offset)
        pos = self._pos + offset
        return self._src[pos]

    def getc(self):
        pos = self._pos
        if self.validPos(pos+1):
            self._pos += 1
        return self._src[pos]

    def ungetc(self, c=None):
        if not self.atStart():
            raise Error('Already at beginning of stream')

        self._pos -= 1
        if not c==None:
            self._src[self._pos] = c

    def advance(self, offset=1):
        self.checkPos(self._pos + offset)
        self._pos += offset

    def rev(self, offset=1):
        self.checkPos(self._pos - offset)
        self._pos -= offset
               
    def read(self, offset):
        self.checkPos(self._pos + offset)
        start = self._pos
        self._pos += offset
        return self._src[start:self._pos]

    def readTo(self, to, start=None):
        self.checkPos(to)
        if start == None:
            start = self._pos
        self._pos = to
        return self._src[start:to]

        
    def readToEOL(self, start=None, gobble=True):
        EOLmatch = EOLZre.search(self.src(), self.pos())
        if gobble:
            pos = EOLmatch.end()
        else:
            pos = EOLmatch.start()
        return self.readTo(to=pos, start=start)
    

    def find(self, it, pos=None):
        if pos == None:
            pos = self._pos
        return self._src.find(it, pos )

    def startswith(self, it, pos=None):
        if self.find(it, pos) == self.pos():
            return True
        else:
            return False
                    
    def rfind(self, it, pos):
        if pos == None:
            pos = self._pos
        return self._src.rfind(it, pos)
        
    def findBOL(self, pos=None):
        if pos == None:
            pos = self._pos
        src = self.src()
        return max(src.rfind('\n', 0, pos)+1, src.rfind('\r', 0, pos)+1, 0)
        
    def findEOL(self, pos=None, gobble=False):
        if pos == None:
            pos = self._pos

        match = EOLZre.search(self.src(), pos)
        if gobble:
            return match.end()
        else:
            return match.start()
    
    def isLineClearToPos(self, pos=None):
        if pos == None:
            pos = self.pos()
        self.checkPos(pos)            
        src = self.src()
        BOL = self.findBOL()
        return BOL == pos or src[BOL:pos].isspace()

    def matches(self, strOrRE):
        if isinstance(strOrRE, (str, unicode)):
            return self.startswith(strOrRE, pos=self.pos())
        else: # assume an re object
            return strOrRE.match(self.src(), self.pos())

    def matchWhiteSpace(self, WSchars=' \f\t'):
        return (not self.atEnd()) and  self.peek() in WSchars

    def getWhiteSpace(self, max=None, WSchars=' \f\t'):
        if not self.matchWhiteSpace(WSchars):
            return ''
        start = self.pos()
        breakPoint = self.breakPoint()
        if max is not None:
            breakPoint = min(breakPoint, self.pos()+max)
        while self.pos() < breakPoint:
            self.advance()
            if not self.matchWhiteSpace(WSchars):
                break
        return self.src()[start:self.pos()]

    def matchNonWhiteSpace(self, WSchars=' \f\t\n\r'):
        return self.atEnd() or not self.peek() in WSchars

    def getNonWhiteSpace(self, WSchars=' \f\t\n\r'):
        if not self.matchNonWhiteSpace(WSchars):
            return ''
        start = self.pos()
        while self.pos() < self.breakPoint():
            self.advance()
            if not self.matchNonWhiteSpace(WSchars):
                break
        return self.src()[start:self.pos()]
