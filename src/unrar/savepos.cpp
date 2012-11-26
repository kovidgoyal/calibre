#include "rar.hpp"

SaveFilePos::SaveFilePos(File &SaveFile)
{
  SaveFilePos::SaveFile=&SaveFile;
  SavePos=SaveFile.Tell();
  CloseCount=SaveFile.CloseCount;
}


SaveFilePos::~SaveFilePos()
{
  if (CloseCount==SaveFile->CloseCount)
    SaveFile->Seek(SavePos,SEEK_SET);
}
