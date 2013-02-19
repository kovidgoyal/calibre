#include <os2.h>



void ExtractOS2EA(Archive &Arc,char *FileName)
{
  if (_osmode != OS2_MODE)
  {
    mprintf(St(MSkipEA));
    return;
  }

  if (Arc.HeaderCRC!=Arc.EAHead.HeadCRC)
  {
    Log(Arc.FileName,St(MEABroken),FileName);
    ErrHandler.SetErrorCode(RARX_CRC);
    return;
  }

  if (Arc.EAHead.Method<0x31 || Arc.EAHead.Method>0x35 || Arc.EAHead.UnpVer>PACK_VER)
  {
    Log(Arc.FileName,St(MEAUnknHeader),FileName);
    ErrHandler.SetErrorCode(RARX_WARNING);
    return;
  }

  struct StructEAOP2
  {
    char *GEAPtr;
    char *FEAPtr;
    unsigned long Error;
  } EAOP2;

  ComprDataIO DataIO;
  Unpack Unpack(&DataIO);
  Unpack.Init();

  Array<unsigned char> UnpData(Arc.EAHead.UnpSize);
  DataIO.SetUnpackToMemory(&UnpData[0],Arc.EAHead.UnpSize);
  DataIO.SetPackedSizeToRead(Arc.EAHead.DataSize);
  DataIO.EnableShowProgress(false);
  DataIO.SetFiles(&Arc,NULL);
  Unpack.SetDestSize(Arc.EAHead.UnpSize);
  Unpack.DoUnpack(Arc.EAHead.UnpVer,false);

  if (Arc.EAHead.EACRC!=~DataIO.UnpFileCRC)
  {
    Log(Arc.FileName,St(MEABroken),FileName);
    ErrHandler.SetErrorCode(RARX_CRC);
    return;
  }

  EAOP2.FEAPtr=(char *)&UnpData[0];
  EAOP2.GEAPtr=NULL;
  if (DosSetPathInfo((unsigned char *)FileName,2,&EAOP2,sizeof(EAOP2),0x10)!=0)
  {
    Log(Arc.FileName,St(MCannotSetEA),FileName);
    ErrHandler.SetErrorCode(RARX_WARNING);
  }
  File::SetCloseFileTimeByName(FileName,&Arc.NewLhd.mtime,&Arc.NewLhd.atime);
  mprintf(St(MShowEA));
}


void ExtractOS2EANew(Archive &Arc,char *FileName)
{
  if (_osmode != OS2_MODE)
  {
    mprintf(St(MSkipEA));
    return;
  }

  Array<byte> SubData;
  if (!Arc.ReadSubData(&SubData,NULL))
    return;

  struct StructEAOP2
  {
    char *GEAPtr;
    char *FEAPtr;
    unsigned long Error;
  } EAOP2;

  EAOP2.FEAPtr=(char *)&SubData[0];
  EAOP2.GEAPtr=NULL;
  if (DosSetPathInfo((unsigned char *)FileName,2,&EAOP2,sizeof(EAOP2),0x10)!=0)
  {
    Log(Arc.FileName,St(MCannotSetEA),FileName);
    ErrHandler.SetErrorCode(RARX_WARNING);
  }
  File::SetCloseFileTimeByName(FileName,&Arc.NewLhd.mtime,&Arc.NewLhd.atime);
  mprintf(St(MShowEA));
}

