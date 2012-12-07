#include "rar.hpp"

int ToPercent(int64 N1,int64 N2)
{
  if (N2<N1)
    return(100);
  return(ToPercentUnlim(N1,N2));
}


// Allows the percent larger than 100.
int ToPercentUnlim(int64 N1,int64 N2)
{
  if (N2==0)
    return(0);
  return((int)(N1*100/N2));
}


void RARInitData()
{
  InitCRC();
  ErrHandler.Clean();
}


#ifdef _DJGPP
// Disable wildcard expansion in DJGPP DOS SFX module.
extern "C" char **__crt0_glob_function (char *arg) 
{ 
  return 0; 
}
#endif


#ifdef _DJGPP
// Disable environments variable loading in DJGPP DOS SFX module
// to reduce the module size.
extern "C" void __crt0_load_environment_file (char *progname) 
{ 
}
#endif
