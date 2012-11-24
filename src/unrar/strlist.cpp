#include "rar.hpp"

StringList::StringList()
{
  Reset();
}


void StringList::Reset()
{
  Rewind();
  StringData.Reset();
  StringDataW.Reset();
  StringsCount=0;
  SavePosNumber=0;
}


void StringList::AddString(const char *Str)
{
  AddString(Str,NULL);
}


void StringList::AddString(const wchar *Str)
{
  AddString(NULL,Str);
}




void StringList::AddString(const char *Str,const wchar *StrW)
{
  if (Str==NULL)
    Str="";
  if (StrW==NULL)
    StrW=L"";

  size_t PrevSize=StringData.Size();
  StringData.Add(strlen(Str)+1);
  strcpy(&StringData[PrevSize],Str);

  size_t PrevSizeW=StringDataW.Size();
  StringDataW.Add(wcslen(StrW)+1);
  wcscpy(&StringDataW[PrevSizeW],StrW);

  StringsCount++;
}


bool StringList::GetString(char *Str,size_t MaxLength)
{
  return(GetString(Str,NULL,MaxLength));
}


bool StringList::GetString(wchar *Str,size_t MaxLength)
{
  return(GetString(NULL,Str,MaxLength));
}


bool StringList::GetString(char *Str,wchar *StrW,size_t MaxLength)
{
  char *StrPtr;
  wchar *StrPtrW;
  if (!GetString(&StrPtr,&StrPtrW))
    return(false);
  if (Str!=NULL)
    strncpy(Str,StrPtr,MaxLength);
  if (StrW!=NULL)
    wcsncpy(StrW,StrPtrW,MaxLength);
  return(true);
}


#ifndef SFX_MODULE
bool StringList::GetString(char *Str,wchar *StrW,size_t MaxLength,int StringNum)
{
  SavePosition();
  Rewind();
  bool RetCode=true;
  while (StringNum-- >=0)
    if (!GetString(Str,StrW,MaxLength))
    {
      RetCode=false;
      break;
    }
  RestorePosition();
  return(RetCode);
}
#endif


char* StringList::GetString()
{
  char *Str;
  GetString(&Str,NULL);
  return(Str);
}


wchar* StringList::GetStringW()
{
  wchar *StrW;
  GetString(NULL,&StrW);
  return(StrW);
}


bool StringList::GetString(char **Str,wchar **StrW)
{
  // First check would be enough, because both buffers grow synchronously,
  // but we check both for extra fail proof.
  if (CurPos>=StringData.Size() || CurPosW>=StringDataW.Size())
  {
    // No more strings left unprocessed.
    if (Str!=NULL)
      *Str=NULL;
    if (StrW!=NULL)
      *StrW=NULL;
    return(false);
  }

  // We move ASCII and Unicode buffer pointers synchronously.
  
  char *CurStr=&StringData[CurPos];
  CurPos+=strlen(CurStr)+1;
  if (Str!=NULL)
    *Str=CurStr;

  wchar *CurStrW=&StringDataW[CurPosW];
  CurPosW+=wcslen(CurStrW)+1;
  if (StrW!=NULL)
    *StrW=CurStrW;

  return(true);
}


void StringList::Rewind()
{
  CurPos=0;
  CurPosW=0;
}


// Return the total size of usual and Unicode characters stored in the list.
size_t StringList::GetCharCount()
{
  return(StringData.Size()+StringDataW.Size());
}


#ifndef SFX_MODULE
bool StringList::Search(char *Str,wchar *StrW,bool CaseSensitive)
{
  SavePosition();
  Rewind();
  bool Found=false;
  char *CurStr;
  wchar *CurStrW;
  while (GetString(&CurStr,&CurStrW))
  {
    if (Str!=NULL && CurStr!=NULL)
      if ((CaseSensitive ? strcmp(Str,CurStr):stricomp(Str,CurStr))!=0)
        continue;
    if (StrW!=NULL && CurStrW!=NULL)
      if ((CaseSensitive ? wcscmp(StrW,CurStrW):wcsicomp(StrW,CurStrW))!=0)
        continue;
    Found=true;
    break;
  }
  RestorePosition();
  return(Found);
}
#endif


#ifndef SFX_MODULE
void StringList::SavePosition()
{
  if (SavePosNumber<ASIZE(SaveCurPos))
  {
    SaveCurPos[SavePosNumber]=CurPos;
    SaveCurPosW[SavePosNumber]=CurPosW;
    SavePosNumber++;
  }
}
#endif


#ifndef SFX_MODULE
void StringList::RestorePosition()
{
  if (SavePosNumber>0)
  {
    SavePosNumber--;
    CurPos=SaveCurPos[SavePosNumber];
    CurPosW=SaveCurPosW[SavePosNumber];
  }
}
#endif
