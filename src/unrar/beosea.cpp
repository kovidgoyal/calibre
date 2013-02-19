

void ExtractBeEA(Archive &Arc,char *FileName)
{
  if (Arc.HeaderCRC!=Arc.EAHead.HeadCRC)
  {
    Log(Arc.FileName,St(MEABroken),FileName);
    ErrHandler.SetErrorCode(RARX_CRC);
    return;
  }
  if (Arc.EAHead.Method<0x31 || Arc.EAHead.Method>0x35 || Arc.EAHead.UnpVer>PACK_VER)
  {
    Log(Arc.FileName,St(MEAUnknHeader),FileName);
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
    Log(Arc.FileName,St(MEABroken),FileName);
    ErrHandler.SetErrorCode(RARX_CRC);
    return;
  }
  int fd = open(FileName,O_WRONLY);
  if (fd==-1)
  {
    Log(Arc.FileName,St(MCannotSetEA),FileName);
    ErrHandler.SetErrorCode(RARX_WARNING);
    return;
  }

  int AttrPos=0;
  while (AttrPos<Arc.EAHead.UnpSize)
  {
    unsigned char *CurItem=&UnpData[AttrPos];
    int NameSize=CurItem[0]+((int)CurItem[1]<<8);
    int Type=CurItem[2]+((int)CurItem[3]<<8)+((int)CurItem[4]<<16)+((int)CurItem[5]<<24);
    int Size=CurItem[6]+((int)CurItem[7]<<8)+((int)CurItem[8]<<16)+((int)CurItem[9]<<24);
    char Name[1024];
    if (NameSize>=sizeof(Name))
    {
      Log(Arc.FileName,St(MCannotSetEA),FileName);
      ErrHandler.SetErrorCode(RARX_WARNING);
      break;
    }
    memcpy(Name,CurItem+10,NameSize);
    Name[NameSize]=0;
    if (fs_write_attr(fd,Name,Type,0,CurItem+10+NameSize,Size)==-1)
    {
      Log(Arc.FileName,St(MCannotSetEA),FileName);
      ErrHandler.SetErrorCode(RARX_WARNING);
      break;
    }
    AttrPos+=10+NameSize+Size;
  }
  close(fd);
  mprintf(St(MShowEA));
}


void ExtractBeEANew(Archive &Arc,char *FileName)
{
  Array<byte> SubData;
  if (!Arc.ReadSubData(&SubData,NULL))
    return;

  int fd = open(FileName,O_WRONLY);
  if (fd==-1)
  {
    Log(Arc.FileName,St(MCannotSetEA),FileName);
    ErrHandler.SetErrorCode(RARX_WARNING);
    return;
  }

  int AttrPos=0;
  while (AttrPos<Arc.EAHead.UnpSize)
  {
    unsigned char *CurItem=&SubData[AttrPos];
    int NameSize=CurItem[0]+((int)CurItem[1]<<8);
    int Type=CurItem[2]+((int)CurItem[3]<<8)+((int)CurItem[4]<<16)+((int)CurItem[5]<<24);
    int Size=CurItem[6]+((int)CurItem[7]<<8)+((int)CurItem[8]<<16)+((int)CurItem[9]<<24);
    char Name[1024];
    if (NameSize>=sizeof(Name))
    {
      Log(Arc.FileName,St(MCannotSetEA),FileName);
      ErrHandler.SetErrorCode(RARX_WARNING);
      break;
    }
    memcpy(Name,CurItem+10,NameSize);
    Name[NameSize]=0;
    if (fs_write_attr(fd,Name,Type,0,CurItem+10+NameSize,Size)==-1)
    {
      Log(Arc.FileName,St(MCannotSetEA),FileName);
      ErrHandler.SetErrorCode(RARX_WARNING);
      break;
    }
    AttrPos+=10+NameSize+Size;
  }
  close(fd);
  mprintf(St(MShowEA));
}

