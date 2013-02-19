#include "rar.hpp"

#if !defined(GUI) && !defined(RARDLL)
int main(int argc, char *argv[])
{

#ifdef _UNIX
  setlocale(LC_ALL,"");
#endif

#if defined(_EMX) && !defined(_DJGPP)
  uni_init(0);
#endif

#if !defined(_SFX_RTL_) && !defined(_WIN_ALL)
  setbuf(stdout,NULL);
#endif

#if !defined(SFX_MODULE) && defined(_EMX)
  EnumConfigPaths(argv[0],-1);
#endif

  ErrHandler.SetSignalHandlers(true);

  RARInitData();

#ifdef SFX_MODULE
  char ModuleNameA[NM];
  wchar ModuleNameW[NM];
#ifdef _WIN_ALL
  GetModuleFileNameW(NULL,ModuleNameW,ASIZE(ModuleNameW));
  WideToChar(ModuleNameW,ModuleNameA);
#else
  strcpy(ModuleNameA,argv[0]);
  *ModuleNameW=0;
#endif
#endif

#ifdef _WIN_ALL
  SetErrorMode(SEM_NOALIGNMENTFAULTEXCEPT|SEM_FAILCRITICALERRORS|SEM_NOOPENFILEERRORBOX);


#endif

#if defined(_WIN_ALL) && !defined(SFX_MODULE) && !defined(SHELL_EXT)
  // Must be initialized, normal initialization can be skipped in case of
  // exception.
  bool ShutdownOnClose=false;
#endif

#ifdef ALLOW_EXCEPTIONS
  try 
#endif
  {
  
    CommandData Cmd;
#ifdef SFX_MODULE
    strcpy(Cmd.Command,"X");
    char *Switch=NULL;
#ifdef _SFX_RTL_
    char *CmdLine=GetCommandLineA();
    if (CmdLine!=NULL && *CmdLine=='\"')
      CmdLine=strchr(CmdLine+1,'\"');
    if (CmdLine!=NULL && (CmdLine=strpbrk(CmdLine," /"))!=NULL)
    {
      while (IsSpace(*CmdLine))
        CmdLine++;
      Switch=CmdLine;
    }
#else
    Switch=argc>1 ? argv[1]:NULL;
#endif
    if (Switch!=NULL && Cmd.IsSwitch(Switch[0]))
    {
      int UpperCmd=etoupper(Switch[1]);
      switch(UpperCmd)
      {
        case 'T':
        case 'V':
          Cmd.Command[0]=UpperCmd;
          break;
        case '?':
          Cmd.OutHelp(RARX_SUCCESS);
          break;
      }
    }
    Cmd.AddArcName(ModuleNameA,ModuleNameW);
    Cmd.ParseDone();
#else // !SFX_MODULE
    Cmd.PreprocessCommandLine(argc,argv);
    if (!Cmd.ConfigDisabled)
    {
      Cmd.ReadConfig();
      Cmd.ParseEnvVar();
    }
    Cmd.ParseCommandLine(argc,argv);
#endif

#if defined(_WIN_ALL) && !defined(SFX_MODULE) && !defined(SHELL_EXT)
    ShutdownOnClose=Cmd.Shutdown;
#endif

    InitConsoleOptions(Cmd.MsgStream,Cmd.Sound);
    InitLogOptions(Cmd.LogName);
    ErrHandler.SetSilent(Cmd.AllYes || Cmd.MsgStream==MSG_NULL);
    ErrHandler.SetShutdown(Cmd.Shutdown);

    Cmd.OutTitle();
    Cmd.ProcessCommand();
  }
#ifdef ALLOW_EXCEPTIONS
  catch (RAR_EXIT ErrCode)
  {
    ErrHandler.SetErrorCode(ErrCode);
  }
#ifdef ENABLE_BAD_ALLOC
  catch (std::bad_alloc)
  {
    ErrHandler.MemoryErrorMsg();
    ErrHandler.SetErrorCode(RARX_MEMORY);
  }
#endif
  catch (...)
  {
    ErrHandler.SetErrorCode(RARX_FATAL);
  }
#endif

  File::RemoveCreated();
#if defined(SFX_MODULE) && defined(_DJGPP)
  _chmod(ModuleNameA,1,0x20);
#endif
#if defined(_EMX) && !defined(_DJGPP)
  uni_done();
#endif
#if defined(_WIN_ALL) && !defined(SFX_MODULE) && !defined(SHELL_EXT)
  if (ShutdownOnClose)
    Shutdown();
#endif
  return(ErrHandler.GetErrorCode());
}
#endif


