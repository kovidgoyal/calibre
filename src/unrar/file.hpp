#ifndef _RAR_FILE_
#define _RAR_FILE_

#ifdef _WIN_ALL
typedef HANDLE FileHandle;
#define BAD_HANDLE INVALID_HANDLE_VALUE
#else
typedef FILE* FileHandle;
#define BAD_HANDLE NULL
#endif

class RAROptions;

enum FILE_HANDLETYPE {FILE_HANDLENORMAL,FILE_HANDLESTD,FILE_HANDLEERR};

enum FILE_ERRORTYPE {FILE_SUCCESS,FILE_NOTFOUND,FILE_READERROR};

struct FileStat
{
  uint FileAttr;
  uint FileTime;
  int64 FileSize;
  bool IsDir;
};


enum FILE_MODE_FLAGS {
  // Request read only access to file. Default for Open.
  FMF_READ=0,

  // Request both read and write access to file. Default for Create.
  FMF_UPDATE=1,

  // Request write only access to file.
  FMF_WRITE=2,

  // Open files which are already opened for write by other programs.
  FMF_OPENSHARED=4,

  // Provide read access to created file for other programs.
  FMF_SHAREREAD=8,

  // Mode flags are not defined yet.
  FMF_UNDEFINED=256
};


class File
{
  private:
    void AddFileToList(FileHandle hFile);

    FileHandle hFile;
    bool LastWrite;
    FILE_HANDLETYPE HandleType;
    bool SkipClose;
    bool IgnoreReadErrors;
    bool NewFile;
    bool AllowDelete;
    bool AllowExceptions;
#ifdef _WIN_ALL
    bool NoSequentialRead;
    uint CreateMode;
#endif
  protected:
    bool OpenShared; // Set by 'Archive' class.
  public:
    char FileName[NM];
    wchar FileNameW[NM];

    FILE_ERRORTYPE ErrorType;

    uint CloseCount;
  public:
    File();
    virtual ~File();
    void operator = (File &SrcFile);
    bool Open(const char *Name,const wchar *NameW=NULL,uint Mode=FMF_READ);
    void TOpen(const char *Name,const wchar *NameW=NULL);
    bool WOpen(const char *Name,const wchar *NameW=NULL);
    bool Create(const char *Name,const wchar *NameW=NULL,uint Mode=FMF_UPDATE|FMF_SHAREREAD);
    void TCreate(const char *Name,const wchar *NameW=NULL,uint Mode=FMF_UPDATE|FMF_SHAREREAD);
    bool WCreate(const char *Name,const wchar *NameW=NULL,uint Mode=FMF_UPDATE|FMF_SHAREREAD);
    bool Close();
    void Flush();
    bool Delete();
    bool Rename(const char *NewName,const wchar *NewNameW=NULL);
    void Write(const void *Data,size_t Size);
    int Read(void *Data,size_t Size);
    int DirectRead(void *Data,size_t Size);
    void Seek(int64 Offset,int Method);
    bool RawSeek(int64 Offset,int Method);
    int64 Tell();
    void Prealloc(int64 Size);
    byte GetByte();
    void PutByte(byte Byte);
    bool Truncate();
    void SetOpenFileTime(RarTime *ftm,RarTime *ftc=NULL,RarTime *fta=NULL);
    void SetCloseFileTime(RarTime *ftm,RarTime *fta=NULL);
    static void SetCloseFileTimeByName(const char *Name,RarTime *ftm,RarTime *fta);
    void GetOpenFileTime(RarTime *ft);
    bool IsOpened() {return(hFile!=BAD_HANDLE);};
    int64 FileLength();
    void SetHandleType(FILE_HANDLETYPE Type);
    FILE_HANDLETYPE GetHandleType() {return(HandleType);};
    bool IsDevice();
    void fprintf(const char *fmt,...);
    static bool RemoveCreated();
    FileHandle GetHandle() {return(hFile);};
    void SetIgnoreReadErrors(bool Mode) {IgnoreReadErrors=Mode;};
    char *GetName() {return(FileName);}
    int64 Copy(File &Dest,int64 Length=INT64NDF);
    void SetAllowDelete(bool Allow) {AllowDelete=Allow;}
    void SetExceptions(bool Allow) {AllowExceptions=Allow;}
#ifdef _WIN_ALL
    void RemoveSequentialFlag() {NoSequentialRead=true;}
#endif
};

#endif
