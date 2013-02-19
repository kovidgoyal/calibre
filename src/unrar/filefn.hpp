#ifndef _RAR_FILEFN_
#define _RAR_FILEFN_

enum MKDIR_CODE {MKDIR_SUCCESS,MKDIR_ERROR,MKDIR_BADPATH};

MKDIR_CODE MakeDir(const char *Name,const wchar *NameW,bool SetAttr,uint Attr);
bool CreatePath(const char *Path,bool SkipLastName);
bool CreatePath(const wchar *Path,bool SkipLastName);
bool CreatePath(const char *Path,const wchar *PathW,bool SkipLastName);
void SetDirTime(const char *Name,const wchar *NameW,RarTime *ftm,RarTime *ftc,RarTime *fta);
bool IsRemovable(const char *Name);

#ifndef SFX_MODULE
int64 GetFreeDisk(const char *Name);
#endif


bool FileExist(const char *Name,const wchar *NameW=NULL);
bool FileExist(const wchar *Name);
bool WildFileExist(const char *Name,const wchar *NameW=NULL);
bool IsDir(uint Attr);
bool IsUnreadable(uint Attr);
bool IsLabel(uint Attr);
bool IsLink(uint Attr);
void SetSFXMode(const char *FileName);
void EraseDiskContents(const char *FileName);
bool IsDeleteAllowed(uint FileAttr);
void PrepareToDelete(const char *Name,const wchar *NameW=NULL);
uint GetFileAttr(const char *Name,const wchar *NameW=NULL);
bool SetFileAttr(const char *Name,const wchar *NameW,uint Attr);

enum CALCCRC_SHOWMODE {CALCCRC_SHOWNONE,CALCCRC_SHOWTEXT,CALCCRC_SHOWALL};
uint CalcFileCRC(File *SrcFile,int64 Size=INT64NDF,CALCCRC_SHOWMODE ShowMode=CALCCRC_SHOWNONE);

bool RenameFile(const char *SrcName,const wchar *SrcNameW,const char *DestName,const wchar *DestNameW);
bool DelFile(const char *Name);
bool DelFile(const char *Name,const wchar *NameW);
bool DelDir(const char *Name);
bool DelDir(const char *Name,const wchar *NameW);

#if defined(_WIN_ALL) && !defined(_WIN_CE)
bool SetFileCompression(char *Name,wchar *NameW,bool State);
#endif




#endif
