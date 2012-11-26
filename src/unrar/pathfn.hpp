#ifndef _RAR_PATHFN_
#define _RAR_PATHFN_

char* PointToName(const char *Path);
wchar* PointToName(const wchar *Path);
char* PointToLastChar(const char *Path);
wchar* PointToLastChar(const wchar *Path);
char* ConvertPath(const char *SrcPath,char *DestPath);
wchar* ConvertPath(const wchar *SrcPath,wchar *DestPath);
void SetExt(char *Name,const char *NewExt);
void SetExt(wchar *Name,const wchar *NewExt);
void SetSFXExt(char *SFXName);
void SetSFXExt(wchar *SFXName);
char *GetExt(const char *Name);
wchar *GetExt(const wchar *Name);
bool CmpExt(const char *Name,const char *Ext);
bool CmpExt(const wchar *Name,const wchar *Ext);
bool IsWildcard(const char *Str,const wchar *StrW=NULL);
bool IsPathDiv(int Ch);
bool IsDriveDiv(int Ch);
int GetPathDisk(const char *Path);
int GetPathDisk(const wchar *Path);
void AddEndSlash(char *Path);
void AddEndSlash(wchar *Path);
void GetFilePath(const char *FullName,char *Path,int MaxLength);
void GetFilePath(const wchar *FullName,wchar *Path,int MaxLength);
void RemoveNameFromPath(char *Path);
void RemoveNameFromPath(wchar *Path);
void GetAppDataPath(char *Path);
void GetAppDataPath(wchar *Path);
void GetRarDataPath(char *Path);
void GetRarDataPath(wchar *Path);
bool EnumConfigPaths(wchar *Path,int Number);
bool EnumConfigPaths(char *Path,int Number);
void GetConfigName(const char *Name,char *FullName,bool CheckExist);
void GetConfigName(const wchar *Name,wchar *FullName,bool CheckExist);
char* GetVolNumPart(char *ArcName);
wchar* GetVolNumPart(wchar *ArcName);
void NextVolumeName(char *ArcName,wchar *ArcNameW,uint MaxLength,bool OldNumbering);
bool IsNameUsable(const char *Name);
bool IsNameUsable(const wchar *Name);
void MakeNameUsable(char *Name,bool Extended);
void MakeNameUsable(wchar *Name,bool Extended);
char* UnixSlashToDos(char *SrcName,char *DestName=NULL,uint MaxLength=NM);
char* DosSlashToUnix(char *SrcName,char *DestName=NULL,uint MaxLength=NM);
wchar* UnixSlashToDos(wchar *SrcName,wchar *DestName=NULL,uint MaxLength=NM);
wchar* DosSlashToUnix(wchar *SrcName,wchar *DestName=NULL,uint MaxLength=NM);
void ConvertNameToFull(const char *Src,char *Dest);
void ConvertNameToFull(const wchar *Src,wchar *Dest);
bool IsFullPath(const char *Path);
bool IsFullPath(const wchar *Path);
bool IsDiskLetter(const char *Path);
bool IsDiskLetter(const wchar *Path);
void GetPathRoot(const char *Path,char *Root);
void GetPathRoot(const wchar *Path,wchar *Root);
int ParseVersionFileName(char *Name,wchar *NameW,bool Truncate);
char* VolNameToFirstName(const char *VolName,char *FirstName,bool NewNumbering);
wchar* VolNameToFirstName(const wchar *VolName,wchar *FirstName,bool NewNumbering);
wchar* GetWideName(const char *Name,const wchar *NameW,wchar *DestW,size_t DestSize);
char* GetAsciiName(const wchar *NameW,char *Name,size_t DestSize);

#ifndef SFX_MODULE
void GenerateArchiveName(char *ArcName,wchar *ArcNameW,size_t MaxSize,char *GenerateMask,bool Archiving);
#endif

#endif
