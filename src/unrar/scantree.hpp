#ifndef _RAR_SCANTREE_
#define _RAR_SCANTREE_

enum SCAN_DIRS 
{ 
  SCAN_SKIPDIRS,     // Skip directories, but recurse for files if recursion mode is enabled.
  SCAN_GETDIRS,      // Get subdirectories in recurse mode.
  SCAN_GETDIRSTWICE, // Get the directory name both before and after the list of files it contains.
  SCAN_GETCURDIRS    // Get subdirectories in current directory even in RECURSE_NONE mode.
};

enum SCAN_CODE { SCAN_SUCCESS,SCAN_DONE,SCAN_ERROR,SCAN_NEXT };

#define MAXSCANDEPTH    (NM/2)

class CommandData;

class ScanTree
{
  private:
    bool GetNextMask();
    SCAN_CODE FindProc(FindData *FD);

    FindFile *FindStack[MAXSCANDEPTH];
    int Depth;

    int SetAllMaskDepth;

    StringList *FileMasks;
    RECURSE_MODE Recurse;
    bool GetLinks;
    SCAN_DIRS GetDirs;
    int Errors;

    // set when processing paths like c:\ (root directory without wildcards)
    bool ScanEntireDisk;

    char CurMask[NM];
    wchar CurMaskW[NM];
    char OrigCurMask[NM];
    wchar OrigCurMaskW[NM];
    bool SearchAllInRoot;
    size_t SpecPathLength;
    size_t SpecPathLengthW;

    char ErrArcName[NM];

    CommandData *Cmd;
  public:
    ScanTree(StringList *FileMasks,RECURSE_MODE Recurse,bool GetLinks,SCAN_DIRS GetDirs);
    ~ScanTree();
    SCAN_CODE GetNext(FindData *FindData);
    size_t GetSpecPathLength() {return(SpecPathLength);};
    size_t GetSpecPathLengthW() {return(SpecPathLengthW);};
    int GetErrors() {return(Errors);};
    void SetErrArcName(const char *Name) {strcpy(ErrArcName,Name);}
    void SetCommandData(CommandData *Cmd) {ScanTree::Cmd=Cmd;}
};

#endif
