#include "rar.hpp"


static char LogName[NM];

void InitLogOptions(char *LogName)
{
  strcpy(::LogName,LogName);
}


#ifndef SILENT
void Log(const char *ArcName,const char *Format,...)
{
  safebuf char Msg[2*NM+1024];
  va_list ArgPtr;
  va_start(ArgPtr,Format);
  vsprintf(Msg,Format,ArgPtr);
  va_end(ArgPtr);
  eprintf("%s",Msg);
}
#endif


