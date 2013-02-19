#include "rar.hpp"



bool ExtractLink(ComprDataIO &DataIO,Archive &Arc,const char *LinkName,uint &LinkCRC,bool Create)
{
#if defined(SAVE_LINKS) && defined(_UNIX)
  char LinkTarget[NM];
  if (IsLink(Arc.NewLhd.FileAttr))
  {
    int DataSize=Min(Arc.NewLhd.PackSize,sizeof(LinkTarget)-1);
    DataIO.UnpRead((byte *)LinkTarget,DataSize);
    LinkTarget[DataSize]=0;
    if (Create)
    {
      CreatePath(LinkName,NULL,true);
      if (symlink(LinkTarget,LinkName)==-1) // Error.
        if (errno==EEXIST)
          Log(Arc.FileName,St(MSymLinkExists),LinkName);
        else
        {
          Log(Arc.FileName,St(MErrCreateLnk),LinkName);
          ErrHandler.SetErrorCode(RARX_WARNING);
        }
      // We do not set time of created symlink, because utime changes
      // time of link target and lutimes is not available on all Linux
      // systems at the moment of writing this code.
    }
    int NameSize=Min(DataSize,strlen(LinkTarget));
    LinkCRC=CRC(0xffffffff,LinkTarget,NameSize);
    return(true);
  }
#endif
  return(false);
}
