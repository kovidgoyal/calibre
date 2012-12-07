static void SetPrivileges();

static bool ReadSacl=false;



#ifndef SFX_MODULE
void ExtractACL(Archive &Arc,char *FileName,wchar *FileNameW)
{
  if (!WinNT())
    return;

  SetPrivileges();

  if (Arc.HeaderCRC!=Arc.EAHead.HeadCRC)
  {
    Log(Arc.FileName,St(MACLBroken),FileName);
    ErrHandler.SetErrorCode(RARX_CRC);
    return;
  }

  if (Arc.EAHead.Method<0x31 || Arc.EAHead.Method>0x35 || Arc.EAHead.UnpVer>PACK_VER)
  {
    Log(Arc.FileName,St(MACLUnknown),FileName);
    ErrHandler.SetErrorCode(RARX_WARNING);
    return;
  }

  ComprDataIO DataIO;
  Unpack Unpack(&DataIO);
  Unpack.Init();

  Array<byte> UnpData(Arc.EAHead.UnpSize);
  DataIO.SetUnpackToMemory(&UnpData[0],Arc.EAHead.UnpSize);
  DataIO.SetPackedSizeToRead(Arc.EAHead.DataSize);
  DataIO.EnableShowProgress(false);
  DataIO.SetFiles(&Arc,NULL);
  Unpack.SetDestSize(Arc.EAHead.UnpSize);
  Unpack.DoUnpack(Arc.EAHead.UnpVer,false);

  if (Arc.EAHead.EACRC!=~DataIO.UnpFileCRC)
  {
    Log(Arc.FileName,St(MACLBroken),FileName);
    ErrHandler.SetErrorCode(RARX_CRC);
    return;
  }

  SECURITY_INFORMATION  si=OWNER_SECURITY_INFORMATION|GROUP_SECURITY_INFORMATION|
                           DACL_SECURITY_INFORMATION;
  if (ReadSacl)
    si|=SACL_SECURITY_INFORMATION;
  SECURITY_DESCRIPTOR *sd=(SECURITY_DESCRIPTOR *)&UnpData[0];

  int SetCode;
  if (FileNameW!=NULL)
    SetCode=SetFileSecurityW(FileNameW,si,sd);
  else
    SetCode=SetFileSecurityA(FileName,si,sd);

  if (!SetCode)
  {
    Log(Arc.FileName,St(MACLSetError),FileName);
    ErrHandler.SysErrMsg();
    ErrHandler.SetErrorCode(RARX_WARNING);
  }
}
#endif


void ExtractACLNew(Archive &Arc,char *FileName,wchar *FileNameW)
{
  if (!WinNT())
    return;

  Array<byte> SubData;
  if (!Arc.ReadSubData(&SubData,NULL))
    return;

  SetPrivileges();

  SECURITY_INFORMATION si=OWNER_SECURITY_INFORMATION|GROUP_SECURITY_INFORMATION|
                          DACL_SECURITY_INFORMATION;
  if (ReadSacl)
    si|=SACL_SECURITY_INFORMATION;
  SECURITY_DESCRIPTOR *sd=(SECURITY_DESCRIPTOR *)&SubData[0];

  int SetCode;
  if (FileNameW!=NULL)
    SetCode=SetFileSecurityW(FileNameW,si,sd);
  else
    SetCode=SetFileSecurityA(FileName,si,sd);

  if (!SetCode)
  {
    Log(Arc.FileName,St(MACLSetError),FileName);
    ErrHandler.SysErrMsg();
    ErrHandler.SetErrorCode(RARX_WARNING);
  }
}


void SetPrivileges()
{
  static bool InitDone=false;
  if (InitDone)
    return;
  InitDone=true;

  HANDLE hToken;

  if(!OpenProcessToken(GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES, &hToken))
    return;

  TOKEN_PRIVILEGES tp;
  tp.PrivilegeCount = 1;
  tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED;

  if (LookupPrivilegeValue(NULL,SE_SECURITY_NAME,&tp.Privileges[0].Luid))
    if (AdjustTokenPrivileges(hToken, FALSE, &tp, 0, NULL, NULL) &&
        GetLastError() == ERROR_SUCCESS)
      ReadSacl=true;

  if (LookupPrivilegeValue(NULL,SE_RESTORE_NAME,&tp.Privileges[0].Luid))
    AdjustTokenPrivileges(hToken, FALSE, &tp, 0, NULL, NULL);

  CloseHandle(hToken);
}
