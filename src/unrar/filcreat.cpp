#include "rar.hpp"

bool FileCreate(RAROptions *Cmd,File *NewFile,char *Name,wchar *NameW,
                OVERWRITE_MODE Mode,bool *UserReject,int64 FileSize,
                uint FileTime,bool WriteOnly)
{
  if (UserReject!=NULL)
    *UserReject=false;
#if defined(_WIN_ALL) && !defined(_WIN_CE)
  bool ShortNameChanged=false;
#endif
  while (FileExist(Name,NameW))
  {
#if defined(_WIN_ALL) && !defined(_WIN_CE)
    if (!ShortNameChanged)
    {
      // Avoid the infinite loop if UpdateExistingShortName returns
      // the same name.
      ShortNameChanged=true;

      // Maybe our long name matches the short name of existing file.
      // Let's check if we can change the short name.
      wchar WideName[NM];
      GetWideName(Name,NameW,WideName,ASIZE(WideName));
      if (UpdateExistingShortName(WideName))
      {
        if (Name!=NULL && *Name!=0)
          WideToChar(WideName,Name);
        if (NameW!=NULL && *NameW!=0)
          wcscpy(NameW,WideName);
        continue;
      }
    }
    // Allow short name check again. It is necessary, because rename and
    // autorename below can change the name, so we need to check it again.
    ShortNameChanged=false;
#endif
    if (Mode==OVERWRITE_NONE)
    {
      if (UserReject!=NULL)
        *UserReject=true;
      return(false);
    }

    // Must be before Cmd->AllYes check or -y switch would override -or.
    if (Mode==OVERWRITE_AUTORENAME)
    {
      if (!GetAutoRenamedName(Name,NameW))
        Mode=OVERWRITE_DEFAULT;
      continue;
    }

#ifdef SILENT
    Mode=OVERWRITE_ALL;
#endif

    // This check must be after OVERWRITE_AUTORENAME processing or -y switch
    // would override -or.
    if (Cmd->AllYes || Mode==OVERWRITE_ALL)
      break;

    if (Mode==OVERWRITE_DEFAULT || Mode==OVERWRITE_FORCE_ASK)
    {
      char NewName[NM];
      wchar NewNameW[NM];
      *NewNameW=0;
      eprintf(St(MFileExists),Name);
      int Choice=Ask(St(MYesNoAllRenQ));
      if (Choice==1)
        break;
      if (Choice==2)
      {
        if (UserReject!=NULL)
          *UserReject=true;
        return(false);
      }
      if (Choice==3)
      {
        Cmd->Overwrite=OVERWRITE_ALL;
        break;
      }
      if (Choice==4)
      {
        if (UserReject!=NULL)
          *UserReject=true;
        Cmd->Overwrite=OVERWRITE_NONE;
        return(false);
      }
      if (Choice==5)
      {
#ifndef GUI
        mprintf(St(MAskNewName));

#ifdef  _WIN_ALL
        File SrcFile;
        SrcFile.SetHandleType(FILE_HANDLESTD);
        int Size=SrcFile.Read(NewName,sizeof(NewName)-1);
        NewName[Size]=0;
        OemToCharA(NewName,NewName);
#else
        if (fgets(NewName,sizeof(NewName),stdin)==NULL)
        {
          // Process fgets failure as if user answered 'No'.
          if (UserReject!=NULL)
            *UserReject=true;
          return(false);
        }
#endif
        RemoveLF(NewName);
#endif
        if (PointToName(NewName)==NewName)
          strcpy(PointToName(Name),NewName);
        else
          strcpy(Name,NewName);

        if (NameW!=NULL)
          if (PointToName(NewNameW)==NewNameW)
            wcscpy(PointToName(NameW),NewNameW);
          else
            wcscpy(NameW,NewNameW);
        continue;
      }
      if (Choice==6)
        ErrHandler.Exit(RARX_USERBREAK);
    }
  }
  uint FileMode=WriteOnly ? FMF_WRITE|FMF_SHAREREAD:FMF_UPDATE|FMF_SHAREREAD;
  if (NewFile!=NULL && NewFile->Create(Name,NameW,FileMode))
    return(true);
  PrepareToDelete(Name,NameW);
  CreatePath(Name,NameW,true);
  return(NewFile!=NULL ? NewFile->Create(Name,NameW,FileMode):DelFile(Name,NameW));
}


bool GetAutoRenamedName(char *Name,wchar *NameW)
{
  char NewName[NM];
  wchar NewNameW[NM];

  if (Name!=NULL && strlen(Name)>ASIZE(NewName)-10 || 
      NameW!=NULL && wcslen(NameW)>ASIZE(NewNameW)-10)
    return(false);
  char *Ext=NULL;
  if (Name!=NULL && *Name!=0)
  {
    Ext=GetExt(Name);
    if (Ext==NULL)
      Ext=Name+strlen(Name);
  }
  wchar *ExtW=NULL;
  if (NameW!=NULL && *NameW!=0)
  {
    ExtW=GetExt(NameW);
    if (ExtW==NULL)
      ExtW=NameW+wcslen(NameW);
  }
  *NewName=0;
  *NewNameW=0;
  for (int FileVer=1;;FileVer++)
  {
    if (Name!=NULL && *Name!=0)
      sprintf(NewName,"%.*s(%d)%s",int(Ext-Name),Name,FileVer,Ext);
    if (NameW!=NULL && *NameW!=0)
      sprintfw(NewNameW,ASIZE(NewNameW),L"%.*s(%d)%s",int(ExtW-NameW),NameW,FileVer,ExtW);
    if (!FileExist(NewName,NewNameW))
    {
      if (Name!=NULL && *Name!=0)
        strcpy(Name,NewName);
      if (NameW!=NULL && *NameW!=0)
        wcscpy(NameW,NewNameW);
      break;
    }
    if (FileVer>=1000000)
      return(false);
  }
  return(true);
}


#if defined(_WIN_ALL) && !defined(_WIN_CE)
// If we find a file, which short name is equal to 'Name', we try to change
// its short name, while preserving the long name. It helps when unpacking
// an archived file, which long name is equal to short name of already
// existing file. Otherwise we would overwrite the already existing file,
// even though its long name does not match the name of unpacking file.
bool UpdateExistingShortName(wchar *Name)
{
  // 'Name' is the name of file which we want to create. Let's check
  // if file with such name is exist. If it does not, we return.
  FindData fd;
  if (!FindFile::FastFind(NULL,Name,&fd))
    return(false);

  // We continue only if file has a short name, which does not match its
  // long name, and this short name is equal to name of file which we need
  // to create.
  if (*fd.ShortName==0 || wcsicomp(PointToName(fd.NameW),fd.ShortName)==0 ||
      wcsicomp(PointToName(Name),fd.ShortName)!=0)
    return(false);

  // Generate the temporary new name for existing file.
  wchar NewName[NM];
  *NewName=0;
  for (int I=0;I<10000 && *NewName==0;I+=123)
  {
    // Here we copy the path part of file to create. We'll make the temporary
    // file in the same folder.
    wcsncpyz(NewName,Name,ASIZE(NewName));

    // Here we set the random name part.
    sprintfw(PointToName(NewName),ASIZE(NewName),L"rtmp%d",I);
    
    // If such file is already exist, try next random name.
    if (FileExist(NULL,NewName))
      *NewName=0;
  }

  // If we could not generate the name not used by any other file, we return.
  if (*NewName==0)
    return(false);
  
  // FastFind returns the name without path, but we need the fully qualified
  // name for renaming, so we use the path from file to create and long name
  // from existing file.
  wchar FullName[NM];
  wcsncpyz(FullName,Name,ASIZE(FullName));
  wcscpy(PointToName(FullName),PointToName(fd.NameW));
  
  // Rename the existing file to randomly generated name. Normally it changes
  // the short name too.
  if (!MoveFileW(FullName,NewName))
    return(false);

  // Now we need to create the temporary empty file with same name as
  // short name of our already existing file. We do it to occupy its previous
  // short name and not allow to use it again when renaming the file back to
  // its original long name.
  File KeepShortFile;
  bool Created=false;
  if (!FileExist(NULL,Name))
    Created=KeepShortFile.Create(NULL,Name);

  // Now we rename the existing file from temporary name to original long name.
  // Since its previous short name is occupied by another file, it should
  // get another short name.
  MoveFileW(NewName,FullName);

  if (Created)
  {
    // Delete the temporary zero length file occupying the short name,
    KeepShortFile.Close();
    KeepShortFile.Delete();
  }
  // We successfully changed the short name. Maybe sometimes we'll simplify
  // this function by use of SetFileShortName Windows API call.
  // But SetFileShortName is not available in older Windows.
  return(true);
}
#endif
