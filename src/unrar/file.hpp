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
    virtual bool Create(const char *Name,const wchar *NameW=NULL,uint Mode=FMF_UPDATE|FMF_SHAREREAD); // virtual added by Kovid
    virtual void TCreate(const char *Name,const wchar *NameW=NULL,uint Mode=FMF_UPDATE|FMF_SHAREREAD); // virtual added by Kovid
    virtual bool WCreate(const char *Name,const wchar *NameW=NULL,uint Mode=FMF_UPDATE|FMF_SHAREREAD); // virtual added by Kovid
    virtual bool Close(); // virtual added by Kovid
    virtual void Flush(); // virtual added by Kovid
    virtual bool Delete(); // virtual added by Kovid
    virtual bool Rename(const char *NewName,const wchar *NewNameW=NULL); // virtual added by Kovid
    virtual void Write(const void *Data,size_t Size); // virtual added by Kovid
    virtual int Read(void *Data,size_t Size); // virtual added by Kovid
    virtual int DirectRead(void *Data,size_t Size); // virtual added by Kovid
    virtual void Seek(int64 Offset,int Method); // virtual added by Kovid
    virtual bool RawSeek(int64 Offset,int Method); // virtual added by Kovid
    virtual int64 Tell(); // virtual added by Kovid
    virtual void Prealloc(int64 Size); // virtual added by Kovid
    virtual byte GetByte(); // virtual added by Kovid
    virtual void PutByte(byte Byte); // virtual added by Kovid
    virtual bool Truncate(); // virtual added by Kovid
    virtual void SetOpenFileTime(RarTime *ftm,RarTime *ftc=NULL,RarTime *fta=NULL); // virtual added by Kovid
    virtual void SetCloseFileTime(RarTime *ftm,RarTime *fta=NULL); // virtual added by Kovid
    static void SetCloseFileTimeByName(const char *Name,RarTime *ftm,RarTime *fta); 
    virtual void GetOpenFileTime(RarTime *ft); // virtual added by Kovid
    virtual bool IsOpened() {return(hFile!=BAD_HANDLE);}; // virtual added by Kovid
    virtual int64 FileLength(); // virtual added by Kovid
    virtual void SetHandleType(FILE_HANDLETYPE Type); // virtual added by Kovid
    virtual FILE_HANDLETYPE GetHandleType() {return(HandleType);}; // virtual added by Kovid
    virtual bool IsDevice(); // virtual added by Kovid
    virtual void fprintf(const char *fmt,...); // virtual added by Kovid
    static bool RemoveCreated(); 
    virtual FileHandle GetHandle() {return(hFile);}; // virtual added by Kovid
    virtual void SetIgnoreReadErrors(bool Mode) {IgnoreReadErrors=Mode;}; // virtual added by Kovid
    virtual char *GetName() {return(FileName);} // virtual added by Kovid
    virtual int64 Copy(File &Dest,int64 Length=INT64NDF); // virtual added by Kovid
    virtual void SetAllowDelete(bool Allow) {AllowDelete=Allow;} // virtual added by Kovid
    virtual void SetExceptions(bool Allow) {AllowExceptions=Allow;} // virtual added by Kovid
#ifdef _WIN_ALL
    virtual void RemoveSequentialFlag() {NoSequentialRead=true;} // virtual added by Kovid
#endif
};

#endif
