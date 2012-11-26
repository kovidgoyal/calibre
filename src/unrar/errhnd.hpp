#ifndef _RAR_ERRHANDLER_
#define _RAR_ERRHANDLER_

#ifndef SFX_MODULE
#define ALLOW_EXCEPTIONS
#endif

enum RAR_EXIT // RAR exit code.
{ 
  RARX_SUCCESS   =   0,
  RARX_WARNING   =   1,
  RARX_FATAL     =   2,
  RARX_CRC       =   3,
  RARX_LOCK      =   4,
  RARX_WRITE     =   5,
  RARX_OPEN      =   6,
  RARX_USERERROR =   7,
  RARX_MEMORY    =   8,
  RARX_CREATE    =   9,
  RARX_NOFILES   =  10,
  RARX_USERBREAK = 255
};

class ErrorHandler
{
  private:
    void ErrMsg(const char *ArcName,const char *fmt,...);

    RAR_EXIT ExitCode;
    int ErrCount;
    bool EnableBreak;
    bool Silent;
    bool DoShutdown;
  public:
    ErrorHandler();
    void Clean();
    void MemoryError();
    void OpenError(const char *FileName,const wchar *FileNameW);
    void CloseError(const char *FileName,const wchar *FileNameW);
    void ReadError(const char *FileName,const wchar *FileNameW);
    bool AskRepeatRead(const char *FileName,const wchar *FileNameW);
    void WriteError(const char *ArcName,const wchar *ArcNameW,const char *FileName,const wchar *FileNameW);
    void WriteErrorFAT(const char *FileName,const wchar *FileNameW);
    bool AskRepeatWrite(const char *FileName,const wchar *FileNameW,bool DiskFull);
    void SeekError(const char *FileName,const wchar *FileNameW);
    void GeneralErrMsg(const char *Msg);
    void MemoryErrorMsg();
    void OpenErrorMsg(const char *FileName,const wchar *FileNameW=NULL);
    void OpenErrorMsg(const char *ArcName,const wchar *ArcNameW,const char *FileName,const wchar *FileNameW);
    void CreateErrorMsg(const char *FileName,const wchar *FileNameW=NULL);
    void CreateErrorMsg(const char *ArcName,const wchar *ArcNameW,const char *FileName,const wchar *FileNameW);
    void CheckLongPathErrMsg(const char *FileName,const wchar *FileNameW);
    void ReadErrorMsg(const char *ArcName,const wchar *ArcNameW,const char *FileName,const wchar *FileNameW);
    void WriteErrorMsg(const char *ArcName,const wchar *ArcNameW,const char *FileName,const wchar *FileNameW);
    void Exit(RAR_EXIT ExitCode);
    void SetErrorCode(RAR_EXIT Code);
    RAR_EXIT GetErrorCode() {return(ExitCode);}
    int GetErrorCount() {return(ErrCount);}
    void SetSignalHandlers(bool Enable);
    void Throw(RAR_EXIT Code);
    void SetSilent(bool Mode) {Silent=Mode;};
    void SetShutdown(bool Mode) {DoShutdown=Mode;};
    void SysErrMsg();
};


#endif
