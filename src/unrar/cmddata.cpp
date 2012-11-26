#include "rar.hpp"


CommandData::CommandData()
{
  FileArgs=ExclArgs=InclArgs=StoreArgs=ArcNames=NULL;
  Init();
}


CommandData::~CommandData()
{
  Close();
}


void CommandData::Init()
{
  RAROptions::Init();
  Close();

  *Command=0;
  *CommandW=0;
  *ArcName=0;
  *ArcNameW=0;
  FileLists=false;
  NoMoreSwitches=false;

  ListMode=RCLM_AUTO;


  FileArgs=new StringList;
  ExclArgs=new StringList;
  InclArgs=new StringList;
  StoreArgs=new StringList;
  ArcNames=new StringList;
}


void CommandData::Close()
{
  delete FileArgs;
  delete ExclArgs;
  delete InclArgs;
  delete StoreArgs;
  delete ArcNames;
  FileArgs=ExclArgs=InclArgs=StoreArgs=ArcNames=NULL;
  NextVolSizes.Reset();
}


#ifdef CUSTOM_CMDLINE_PARSER
// Return the pointer to next position in the string and store dynamically
// allocated command line parameters in Unicode and ASCII in ParW and ParA.
static const wchar *AllocCmdParam(const wchar *CmdLine,wchar **ParW,char **ParA)
{
  const wchar *NextCmd=GetCmdParam(CmdLine,NULL,0);
  if (NextCmd==NULL)
    return NULL;
  size_t ParSize=NextCmd-CmdLine+2; // Parameter size including the trailing zero.
  *ParW=(wchar *)malloc(ParSize*sizeof(wchar));
  if (*ParW==NULL)
    return NULL;
  CmdLine=GetCmdParam(CmdLine,*ParW,ParSize);
  size_t ParSizeA=ParSize*2; // One Unicode char can be converted to several MBCS chars.
  *ParA=(char *)malloc(ParSizeA);
  if (*ParA==NULL)
  {
    free(*ParW);
    return NULL;
  }
  GetAsciiName(*ParW,*ParA,ParSizeA);
  return CmdLine;
}
#endif


#ifndef SFX_MODULE
void CommandData::PreprocessCommandLine(int argc, char *argv[])
{
#ifdef CUSTOM_CMDLINE_PARSER
  // In Windows we may prefer to implement our own command line parser
  // to avoid replacing \" by " in standard parser. Such replacing corrupts
  // destination paths like "dest path\" in extraction commands.
  const wchar *CmdLine=GetCommandLine();

  wchar *ParW;
  char *ParA;
  for (bool FirstParam=true;;FirstParam=false)
  {
    if ((CmdLine=AllocCmdParam(CmdLine,&ParW,&ParA))==NULL)
      break;
    bool Code=FirstParam ? true:PreprocessSwitch(ParA);
    free(ParW);
    free(ParA);
    if (!Code)
      break;
  }
#else
  for (int I=1;I<argc;I++)
    if (!PreprocessSwitch(argv[I]))
      break;
#endif
}
#endif


#ifndef SFX_MODULE
void CommandData::ParseCommandLine(int argc, char *argv[])
{
#ifdef CUSTOM_CMDLINE_PARSER
  // In Windows we may prefer to implement our own command line parser
  // to avoid replacing \" by " in standard parser. Such replacing corrupts
  // destination paths like "dest path\" in extraction commands.
  const wchar *CmdLine=GetCommandLine();

  wchar *ParW;
  char *ParA;
  for (bool FirstParam=true;;FirstParam=false)
  {
    if ((CmdLine=AllocCmdParam(CmdLine,&ParW,&ParA))==NULL)
      break;
    if (!FirstParam) // First parameter is the executable name.
      ParseArg(ParA,ParW);
    free(ParW);
    free(ParA);
  }
#else
  for (int I=1;I<argc;I++)
    ParseArg(argv[I],NULL);
#endif
  ParseDone();
}
#endif


#ifndef SFX_MODULE
void CommandData::ParseArg(char *Arg,wchar *ArgW)
{
  if (IsSwitch(*Arg) && !NoMoreSwitches)
    if (Arg[1]=='-')
      NoMoreSwitches=true;
    else
      ProcessSwitch(Arg+1,(ArgW!=NULL && *ArgW!=0 ? ArgW+1:NULL));
  else
    if (*Command==0)
    {
      strncpyz(Command,Arg,ASIZE(Command));
      if (ArgW!=NULL)
        wcsncpy(CommandW,ArgW,ASIZE(CommandW));


#ifndef GUI
      *Command=etoupper(*Command);
      // 'I' and 'S' commands can contain case sensitive strings after
      // the first character, so we must not modify their case.
      // 'S' can contain SFX name, which case is important in Unix.
      if (*Command!='I' && *Command!='S')
        strupper(Command);
#endif
    }
    else
      if (*ArcName==0 && *ArcNameW==0)
      {
        strncpyz(ArcName,Arg,ASIZE(ArcName));
        if (ArgW!=NULL)
          wcsncpyz(ArcNameW,ArgW,ASIZE(ArcNameW));
      }
      else
      {
        bool EndSeparator; // If last character is the path separator.
        if (ArgW!=NULL)
        {
          size_t Length=wcslen(ArgW);
          wchar EndChar=Length==0 ? 0:ArgW[Length-1];
          EndSeparator=IsDriveDiv(EndChar) || IsPathDiv(EndChar);
        }
        else
        {
          size_t Length=strlen(Arg);
          char EndChar=Length==0 ? 0:Arg[Length-1];
          EndSeparator=IsDriveDiv(EndChar) || IsPathDiv(EndChar);
        }

        char CmdChar=etoupper(*Command);
        bool Add=strchr("AFUM",CmdChar)!=NULL;
        bool Extract=CmdChar=='X' || CmdChar=='E';
        if (EndSeparator && !Add)
        {
          strncpyz(ExtrPath,Arg,ASIZE(ExtrPath));
          if (ArgW!=NULL)
            wcsncpyz(ExtrPathW,ArgW,ASIZE(ExtrPathW));
        }
        else
          if ((Add || CmdChar=='T') && (*Arg!='@' || ListMode==RCLM_REJECT_LISTS))
            FileArgs->AddString(Arg,ArgW);
          else
          {
            FindData FileData;
            bool Found=FindFile::FastFind(Arg,ArgW,&FileData);
            if ((!Found || ListMode==RCLM_ACCEPT_LISTS) && 
                ListMode!=RCLM_REJECT_LISTS && *Arg=='@' && !IsWildcard(Arg,ArgW))
            {
              FileLists=true;

              RAR_CHARSET Charset=FilelistCharset;

#if defined(_WIN_ALL) && !defined(GUI)
              // for compatibility reasons we use OEM encoding
              // in Win32 console version by default

              if (Charset==RCH_DEFAULT)
                Charset=RCH_OEM;
#endif

              wchar *WideArgName=(ArgW!=NULL && *ArgW!=0 ? ArgW+1:NULL);
              ReadTextFile(Arg+1,WideArgName,FileArgs,false,true,Charset,true,true,true);

            }
            else
              if (Found && FileData.IsDir && Extract && *ExtrPath==0 && *ExtrPathW==0)
              {
                strncpyz(ExtrPath,Arg,ASIZE(ExtrPath)-1);
                AddEndSlash(ExtrPath);
                if (ArgW!=NULL)
                {
                  wcsncpyz(ExtrPathW,ArgW,ASIZE(ExtrPathW)-1);
                  AddEndSlash(ExtrPathW);
                }
              }
              else
                FileArgs->AddString(Arg,ArgW);
          }
      }
}
#endif


void CommandData::ParseDone()
{
  if (FileArgs->ItemsCount()==0 && !FileLists)
    FileArgs->AddString(MASKALL);
  char CmdChar=etoupper(*Command);
  bool Extract=CmdChar=='X' || CmdChar=='E' || CmdChar=='P';
  if (Test && Extract)
    Test=false;        // Switch '-t' is senseless for 'X', 'E', 'P' commands.
  BareOutput=(CmdChar=='L' || CmdChar=='V') && Command[1]=='B';
}


#if !defined(SFX_MODULE) && !defined(_WIN_CE)
void CommandData::ParseEnvVar()
{
  char *EnvStr=getenv("RAR");
  if (EnvStr!=NULL)
  {
    ProcessSwitchesString(EnvStr);
  }
}
#endif



#ifndef SFX_MODULE
// Preprocess those parameters, which must be processed before the rest of
// command line. Return 'false' to stop further processing.
bool CommandData::PreprocessSwitch(const char *Switch)
{
  if (IsSwitch(Switch[0]))
  {
    Switch++;
    if (stricomp(Switch,"-")==0) // Switch "--".
      return false;
    if (stricomp(Switch,"cfg-")==0)
      ConfigDisabled=true;
#ifndef GUI
    if (strnicomp(Switch,"ilog",4)==0)
    {
      // Ensure that correct log file name is already set
      // if we need to report an error when processing the command line.
      ProcessSwitch(Switch);
      InitLogOptions(LogName);
    }
#endif
    if (strnicomp(Switch,"sc",2)==0)
    {
      // Process -sc before reading any file lists.
      ProcessSwitch(Switch);
    }
  }
  return true;
}
#endif


#if !defined(GUI) && !defined(SFX_MODULE)
void CommandData::ReadConfig()
{
  StringList List;
  if (ReadTextFile(DefConfigName,NULL,&List,true))
  {
    char *Str;
    while ((Str=List.GetString())!=NULL)
    {
      while (IsSpace(*Str))
        Str++;
      if (strnicomp(Str,"switches=",9)==0)
        ProcessSwitchesString(Str+9);
    }
  }
}
#endif


#if !defined(SFX_MODULE) && !defined(_WIN_CE)
void CommandData::ProcessSwitchesString(char *Str)
{
  while (*Str)
  {
    while (!IsSwitch(*Str) && *Str!=0)
      Str++;
    if (*Str==0)
      break;
    char *Next=Str;
    while (!(Next[0]==' ' && IsSwitch(Next[1])) && *Next!=0)
      Next++;
    char NextChar=*Next;
    *Next=0;
    ProcessSwitch(Str+1);
    *Next=NextChar;
    Str=Next;
  }
}
#endif


#if !defined(SFX_MODULE)
void CommandData::ProcessSwitch(const char *Switch,const wchar *SwitchW)
{

  bool WidePresent=SwitchW!=NULL && *SwitchW!=0; // If 'true', SwitchW is not empty.

  switch(etoupper(Switch[0]))
  {
    case '@':
      ListMode=Switch[1]=='+' ? RCLM_ACCEPT_LISTS:RCLM_REJECT_LISTS;
      break;
    case 'I':
      if (strnicomp(&Switch[1],"LOG",3)==0)
      {
        strncpyz(LogName,Switch[4] ? Switch+4:DefLogName,ASIZE(LogName));
        break;
      }
      if (stricomp(&Switch[1],"SND")==0)
      {
        Sound=true;
        break;
      }
      if (stricomp(&Switch[1],"ERR")==0)
      {
        MsgStream=MSG_STDERR;
        break;
      }
      if (strnicomp(&Switch[1],"EML",3)==0)
      {
        strncpyz(EmailTo,Switch[4] ? Switch+4:"@",ASIZE(EmailTo));
        EmailTo[sizeof(EmailTo)-1]=0;
        break;
      }
      if (stricomp(&Switch[1],"NUL")==0)
      {
        MsgStream=MSG_NULL;
        break;
      }
      if (etoupper(Switch[1])=='D')
      {
        for (int I=2;Switch[I]!=0;I++)
          switch(etoupper(Switch[I]))
          {
            case 'Q':
              MsgStream=MSG_ERRONLY;
              break;
            case 'C':
              DisableCopyright=true;
              break;
            case 'D':
              DisableDone=true;
              break;
            case 'P':
              DisablePercentage=true;
              break;
          }
        break;
      }
      if (stricomp(&Switch[1],"OFF")==0)
      {
        Shutdown=true;
        break;
      }
      break;
    case 'T':
      switch(etoupper(Switch[1]))
      {
        case 'K':
          ArcTime=ARCTIME_KEEP;
          break;
        case 'L':
          ArcTime=ARCTIME_LATEST;
          break;
        case 'O':
          FileTimeBefore.SetAgeText(Switch+2);
          break;
        case 'N':
          FileTimeAfter.SetAgeText(Switch+2);
          break;
        case 'B':
          FileTimeBefore.SetIsoText(Switch+2);
          break;
        case 'A':
          FileTimeAfter.SetIsoText(Switch+2);
          break;
        case 'S':
          {
            EXTTIME_MODE Mode=EXTTIME_HIGH3;
            bool CommonMode=Switch[2]>='0' && Switch[2]<='4';
            if (CommonMode)
              Mode=(EXTTIME_MODE)(Switch[2]-'0');
            if (Switch[2]=='-')
              Mode=EXTTIME_NONE;
            if (CommonMode || Switch[2]=='-' || Switch[2]=='+' || Switch[2]==0)
              xmtime=xctime=xatime=Mode;
            else
            {
              if (Switch[3]>='0' && Switch[3]<='4')
                Mode=(EXTTIME_MODE)(Switch[3]-'0');
              if (Switch[3]=='-')
                Mode=EXTTIME_NONE;
              switch(etoupper(Switch[2]))
              {
                case 'M':
                  xmtime=Mode;
                  break;
                case 'C':
                  xctime=Mode;
                  break;
                case 'A':
                  xatime=Mode;
                  break;
                case 'R':
                  xarctime=Mode;
                  break;
              }
            }
          }
          break;
        case '-':
          Test=false;
          break;
        case 0:
          Test=true;
          break;
        default:
          BadSwitch(Switch);
          break;
      }
      break;
    case 'A':
      switch(etoupper(Switch[1]))
      {
        case 'C':
          ClearArc=true;
          break;
        case 'D':
          AppendArcNameToPath=true;
          break;
#ifndef SFX_MODULE
        case 'G':
          if (Switch[2]=='-' && Switch[3]==0)
            GenerateArcName=0;
          else
          {
            GenerateArcName=true;
            strncpyz(GenerateMask,Switch+2,ASIZE(GenerateMask));
          }
          break;
#endif
        case 'I':
          IgnoreGeneralAttr=true;
          break;
        case 'N': // Reserved for archive name.
          break;
        case 'O':
          AddArcOnly=true;
          break;
        case 'P':
          strcpy(ArcPath,Switch+2);
          if (WidePresent)
            wcscpy(ArcPathW,SwitchW+2);
          break;
        case 'S':
          SyncFiles=true;
          break;
        default:
          BadSwitch(Switch);
          break;
      }
      break;
    case 'D':
      if (Switch[2]==0)
        switch(etoupper(Switch[1]))
        {
          case 'S':
            DisableSortSolid=true;
            break;
          case 'H':
            OpenShared=true;
            break;
          case 'F':
            DeleteFiles=true;
            break;
        }
      break;
    case 'O':
      switch(etoupper(Switch[1]))
      {
        case '+':
          Overwrite=OVERWRITE_ALL;
          break;
        case '-':
          Overwrite=OVERWRITE_NONE;
          break;
        case 0:
          Overwrite=OVERWRITE_FORCE_ASK;
          break;
        case 'R':
          Overwrite=OVERWRITE_AUTORENAME;
          break;
        case 'W':
          ProcessOwners=true;
          break;
#ifdef SAVE_LINKS
        case 'L':
          SaveLinks=true;
          break;
#endif
#ifdef _WIN_ALL
        case 'S':
          SaveStreams=true;
          break;
        case 'C':
          SetCompressedAttr=true;
          break;
#endif
        default :
          BadSwitch(Switch);
          break;
      }
      break;
    case 'R':
      switch(etoupper(Switch[1]))
      {
        case 0:
          Recurse=RECURSE_ALWAYS;
          break;
        case '-':
          Recurse=RECURSE_DISABLE;
          break;
        case '0':
          Recurse=RECURSE_WILDCARDS;
          break;
#ifndef _WIN_CE
        case 'I':
          {
            Priority=atoi(Switch+2);
            if (Priority<0 || Priority>15)
              BadSwitch(Switch);
            const char *ChPtr=strchr(Switch+2,':');
            if (ChPtr!=NULL)
            {
              SleepTime=atoi(ChPtr+1);
              if (SleepTime>1000)
                BadSwitch(Switch);
              InitSystemOptions(SleepTime);
            }
            SetPriority(Priority);
          }
          break;
#endif
      }
      break;
    case 'Y':
      AllYes=true;
      break;
    case 'N':
    case 'X':
      if (Switch[1]!=0)
      {
        StringList *Args=etoupper(Switch[0])=='N' ? InclArgs:ExclArgs;
        if (Switch[1]=='@' && !IsWildcard(Switch))
        {
          RAR_CHARSET Charset=FilelistCharset;

#if defined(_WIN_ALL) && !defined(GUI)
          // for compatibility reasons we use OEM encoding
          // in Win32 console version by default

          if (Charset==RCH_DEFAULT)
            Charset=RCH_OEM;
#endif

          ReadTextFile(Switch+2,NULL,Args,false,true,Charset,true,true,true);
        }
        else
          Args->AddString(Switch+1);
      }
      break;
    case 'E':
      switch(etoupper(Switch[1]))
      {
        case 'P':
          switch(Switch[2])
          {
            case 0:
              ExclPath=EXCL_SKIPWHOLEPATH;
              break;
            case '1':
              ExclPath=EXCL_BASEPATH;
              break;
            case '2':
              ExclPath=EXCL_SAVEFULLPATH;
              break;
            case '3':
              ExclPath=EXCL_ABSPATH;
              break;
          }
          break;
        case 'E':
          ProcessEA=false;
          break;
        case 'N':
          NoEndBlock=true;
          break;
        default:
          if (Switch[1]=='+')
          {
            InclFileAttr=GetExclAttr(&Switch[2]);
            InclAttrSet=true;
          }
          else
            ExclFileAttr=GetExclAttr(&Switch[1]);
          break;
      }
      break;
    case 'P':
      if (Switch[1]==0)
      {
        GetPassword(PASSWORD_GLOBAL,NULL,NULL,&Password);
        eprintf("\n");
      }
      else
      {
        wchar PlainPsw[MAXPASSWORD];
        CharToWide(Switch+1,PlainPsw,ASIZE(PlainPsw));
        PlainPsw[ASIZE(PlainPsw)-1]=0;
        Password.Set(PlainPsw);
        cleandata(PlainPsw,ASIZE(PlainPsw));
      }
      break;
    case 'H':
      if (etoupper(Switch[1])=='P')
      {
        EncryptHeaders=true;
        if (Switch[2]!=0)
        {
          wchar PlainPsw[MAXPASSWORD];
          CharToWide(Switch+2,PlainPsw,ASIZE(PlainPsw));
          PlainPsw[ASIZE(PlainPsw)-1]=0;
          Password.Set(PlainPsw);
          cleandata(PlainPsw,ASIZE(PlainPsw));
        }
        else
          if (!Password.IsSet())
          {
            GetPassword(PASSWORD_GLOBAL,NULL,NULL,&Password);
            eprintf("\n");
          }
      }
      break;
    case 'Z':
      if (Switch[1]==0 && (!WidePresent || SwitchW[1]==0))
      {
#ifndef GUI // stdin is not supported by WinRAR.
        // If comment file is not specified, we read data from stdin.
        strcpy(CommentFile,"stdin");
#endif
      }
      else
      {
        strncpyz(CommentFile,Switch+1,ASIZE(CommentFile));
        if (WidePresent)
          wcsncpyz(CommentFileW,SwitchW+1,ASIZE(CommentFileW));
      }
      break;
    case 'M':
      switch(etoupper(Switch[1]))
      {
        case 'C':
          {
            const char *Str=Switch+2;
            if (*Str=='-')
              for (uint I=0;I<ASIZE(FilterModes);I++)
                FilterModes[I].State=FILTER_DISABLE;
            else
              while (*Str)
              {
                int Param1=0,Param2=0;
                FilterState State=FILTER_AUTO;
                FilterType Type=FILTER_NONE;
                if (IsDigit(*Str))
                {
                  Param1=atoi(Str);
                  while (IsDigit(*Str))
                    Str++;
                }
                if (*Str==':' && IsDigit(Str[1]))
                {
                  Param2=atoi(++Str);
                  while (IsDigit(*Str))
                    Str++;
                }
                switch(etoupper(*(Str++)))
                {
                  case 'T': Type=FILTER_PPM;         break;
                  case 'E': Type=FILTER_E8;          break;
                  case 'D': Type=FILTER_DELTA;       break;
                  case 'A': Type=FILTER_AUDIO;       break;
                  case 'C': Type=FILTER_RGB;         break;
                  case 'I': Type=FILTER_ITANIUM;     break;
                  case 'L': Type=FILTER_UPCASETOLOW; break;
                }
                if (*Str=='+' || *Str=='-')
                  State=*(Str++)=='+' ? FILTER_FORCE:FILTER_DISABLE;
                FilterModes[Type].State=State;
                FilterModes[Type].Param1=Param1;
                FilterModes[Type].Param2=Param2;
              }
            }
          break;
        case 'M':
          break;
        case 'D':
          {
            if ((WinSize=atoi(&Switch[2]))==0)
              WinSize=0x10000<<(etoupper(Switch[2])-'A');
            else
              WinSize*=1024;
            if (!CheckWinSize())
              BadSwitch(Switch);
          }
          break;
        case 'S':
          {
            char StoreNames[1024];
            strncpyz(StoreNames,(Switch[2]==0 ? DefaultStoreList:Switch+2),ASIZE(StoreNames));
            char *Names=StoreNames;
            while (*Names!=0)
            {
              char *End=strchr(Names,';');
              if (End!=NULL)
                *End=0;
              if (*Names=='.')
                Names++;
              char Mask[NM];
              if (strpbrk(Names,"*?.")==NULL)
                sprintf(Mask,"*.%s",Names);
              else
                strcpy(Mask,Names);
              StoreArgs->AddString(Mask);
              if (End==NULL)
                break;
              Names=End+1;
            }
          }
          break;
#ifdef RAR_SMP
        case 'T':
          Threads=atoi(Switch+2);
          if (Threads>MaxPoolThreads || Threads<1)
            BadSwitch(Switch);
          else
          {
          }
          break;
#endif
        default:
          Method=Switch[1]-'0';
          if (Method>5 || Method<0)
            BadSwitch(Switch);
          break;
      }
      break;
    case 'V':
      switch(etoupper(Switch[1]))
      {
        case 'N':
          OldNumbering=true;
          break;
        case 'P':
          VolumePause=true;
          break;
        case 'E':
          if (etoupper(Switch[2])=='R')
            VersionControl=atoi(Switch+3)+1;
          break;
        case '-':
          VolSize=0;
          break;
        default:
          VolSize=VOLSIZE_AUTO; // UnRAR -v switch for list command.
          break;
      }
      break;
    case 'F':
      if (Switch[1]==0)
        FreshFiles=true;
      else
        BadSwitch(Switch);
      break;
    case 'U':
      if (Switch[1]==0)
        UpdateFiles=true;
      else
        BadSwitch(Switch);
      break;
    case 'W':
      strncpyz(TempPath,&Switch[1],ASIZE(TempPath));
      AddEndSlash(TempPath);
      break;
    case 'S':
      if (IsDigit(Switch[1]))
      {
        Solid|=SOLID_COUNT;
        SolidCount=atoi(&Switch[1]);
      }
      else
        switch(etoupper(Switch[1]))
        {
          case 0:
            Solid|=SOLID_NORMAL;
            break;
          case '-':
            Solid=SOLID_NONE;
            break;
          case 'E':
            Solid|=SOLID_FILEEXT;
            break;
          case 'V':
            Solid|=Switch[2]=='-' ? SOLID_VOLUME_DEPENDENT:SOLID_VOLUME_INDEPENDENT;
            break;
          case 'D':
            Solid|=SOLID_VOLUME_DEPENDENT;
            break;
          case 'L':
            if (IsDigit(Switch[2]))
              FileSizeLess=atoil(Switch+2);
            break;
          case 'M':
            if (IsDigit(Switch[2]))
              FileSizeMore=atoil(Switch+2);
            break;
          case 'C':
            {
              // Switch is already found bad, avoid reporting it several times.
              bool AlreadyBad=false;

              RAR_CHARSET rch=RCH_DEFAULT;
              switch(etoupper(Switch[2]))
              {
                case 'A':
                  rch=RCH_ANSI;
                  break;
                case 'O':
                  rch=RCH_OEM;
                  break;
                case 'U':
                  rch=RCH_UNICODE;
                  break;
                default :
                  BadSwitch(Switch);
                  AlreadyBad=true;
                  break;
              };
              if (!AlreadyBad)
                if (Switch[3]==0)
                  CommentCharset=FilelistCharset=rch;
                else
                  for (int I=3;Switch[I]!=0 && !AlreadyBad;I++)
                    switch(etoupper(Switch[I]))
                    {
                      case 'C':
                        CommentCharset=rch;
                        break;
                      case 'L':
                        FilelistCharset=rch;
                        break;
                      default:
                        BadSwitch(Switch);
                        AlreadyBad=true;
                        break;
                    }
            }
            break;

        }
      break;
    case 'C':
      if (Switch[2]==0)
        switch(etoupper(Switch[1]))
        {
          case '-':
            DisableComment=true;
            break;
          case 'U':
            ConvertNames=NAMES_UPPERCASE;
            break;
          case 'L':
            ConvertNames=NAMES_LOWERCASE;
            break;
        }
      break;
    case 'K':
      switch(etoupper(Switch[1]))
      {
        case 'B':
          KeepBroken=true;
          break;
        case 0:
          Lock=true;
          break;
      }
      break;
#ifndef GUI
    case '?' :
      OutHelp(RARX_SUCCESS);
      break;
#endif
    default :
      BadSwitch(Switch);
      break;
  }
}
#endif


#ifndef SFX_MODULE
void CommandData::BadSwitch(const char *Switch)
{
  mprintf(St(MUnknownOption),Switch);
  ErrHandler.Exit(RARX_USERERROR);
}
#endif


#ifndef GUI
void CommandData::OutTitle()
{
  if (BareOutput || DisableCopyright)
    return;
#if defined(__GNUC__) && defined(SFX_MODULE)
  mprintf(St(MCopyrightS));
#else
#ifndef SILENT
  static bool TitleShown=false;
  if (TitleShown)
    return;
  TitleShown=true;
  char Version[50];
  int Beta=RARVER_BETA;
  if (Beta!=0)
    sprintf(Version,"%d.%02d %s %d",RARVER_MAJOR,RARVER_MINOR,St(MBeta),RARVER_BETA);
  else
    sprintf(Version,"%d.%02d",RARVER_MAJOR,RARVER_MINOR);
#ifdef UNRAR
  mprintf(St(MUCopyright),Version,RARVER_YEAR);
#else
#endif
#endif
#endif
}
#endif


inline bool CmpMSGID(MSGID i1,MSGID i2)
{
#ifdef MSGID_INT
  return(i1==i2);
#else
  // If MSGID is const char*, we cannot compare pointers only.
  // Pointers to different instances of same strings can differ,
  // so we need to compare complete strings.
  return(strcmp(i1,i2)==0);
#endif
}

void CommandData::OutHelp(RAR_EXIT ExitCode)
{
#if !defined(GUI) && !defined(SILENT)
  OutTitle();
  static MSGID Help[]={
#ifdef SFX_MODULE
    // Console SFX switches definition.
    MCHelpCmd,MSHelpCmdE,MSHelpCmdT,MSHelpCmdV
#elif defined(UNRAR)
    // UnRAR switches definition.
    MUNRARTitle1,MRARTitle2,MCHelpCmd,MCHelpCmdE,MCHelpCmdL,
    MCHelpCmdP,MCHelpCmdT,MCHelpCmdV,MCHelpCmdX,MCHelpSw,MCHelpSwm,
    MCHelpSwAT,MCHelpSwAC,MCHelpSwAD,MCHelpSwAG,MCHelpSwAI,MCHelpSwAP,
    MCHelpSwCm,MCHelpSwCFGm,MCHelpSwCL,MCHelpSwCU,
    MCHelpSwDH,MCHelpSwEP,MCHelpSwEP3,MCHelpSwF,MCHelpSwIDP,MCHelpSwIERR,
    MCHelpSwINUL,MCHelpSwIOFF,MCHelpSwKB,MCHelpSwN,MCHelpSwNa,MCHelpSwNal,
    MCHelpSwO,MCHelpSwOC,MCHelpSwOR,MCHelpSwOW,MCHelpSwP,
    MCHelpSwPm,MCHelpSwR,MCHelpSwRI,MCHelpSwSL,MCHelpSwSM,MCHelpSwTA,
    MCHelpSwTB,MCHelpSwTN,MCHelpSwTO,MCHelpSwTS,MCHelpSwU,MCHelpSwVUnr,
    MCHelpSwVER,MCHelpSwVP,MCHelpSwX,MCHelpSwXa,MCHelpSwXal,MCHelpSwY
#else
#endif
  };

  for (int I=0;I<sizeof(Help)/sizeof(Help[0]);I++)
  {
#ifndef SFX_MODULE
#ifdef DISABLEAUTODETECT
    if (Help[I]==MCHelpSwV)
      continue;
#endif
#ifndef _WIN_ALL
    static MSGID Win32Only[]={
      MCHelpSwIEML,MCHelpSwVD,MCHelpSwAO,MCHelpSwOS,MCHelpSwIOFF,
      MCHelpSwEP2,MCHelpSwOC,MCHelpSwDR,MCHelpSwRI
    };
    bool Found=false;
    for (int J=0;J<sizeof(Win32Only)/sizeof(Win32Only[0]);J++)
      if (CmpMSGID(Help[I],Win32Only[J]))
      {
        Found=true;
        break;
      }
    if (Found)
      continue;
#endif
#if !defined(_UNIX) && !defined(_WIN_ALL)
    if (CmpMSGID(Help[I],MCHelpSwOW))
      continue;
#endif
#if !defined(_WIN_ALL) && !defined(_EMX)
    if (CmpMSGID(Help[I],MCHelpSwAC))
      continue;
#endif
#ifndef SAVE_LINKS
    if (CmpMSGID(Help[I],MCHelpSwOL))
      continue;
#endif
#ifndef RAR_SMP
    if (CmpMSGID(Help[I],MCHelpSwMT))
      continue;
#endif
#ifndef _BEOS
    if (CmpMSGID(Help[I],MCHelpSwEE))
    {
#if defined(_EMX) && !defined(_DJGPP)
      if (_osmode != OS2_MODE)
        continue;
#else
      continue;
#endif
    }
#endif
#endif
    mprintf(St(Help[I]));
  }
  mprintf("\n");
  ErrHandler.Exit(ExitCode);
#endif
}


// Return 'true' if we need to exclude the file from processing as result
// of -x switch. If CheckInclList is true, we also check the file against
// the include list created with -n switch.
bool CommandData::ExclCheck(char *CheckName,bool Dir,bool CheckFullPath,bool CheckInclList)
{
  if (ExclCheckArgs(ExclArgs,Dir,CheckName,CheckFullPath,MATCH_WILDSUBPATH))
    return(true);
  if (!CheckInclList || InclArgs->ItemsCount()==0)
    return(false);
  if (ExclCheckArgs(InclArgs,Dir,CheckName,false,MATCH_WILDSUBPATH))
    return(false);
  return(true);
}


bool CommandData::ExclCheckArgs(StringList *Args,bool Dir,char *CheckName,bool CheckFullPath,int MatchMode)
{
  char *Name=ConvertPath(CheckName,NULL);
  char FullName[NM];
  char CurMask[NM+1]; // We reserve the space to append "*" to mask.
  *FullName=0;
  Args->Rewind();
  while (Args->GetString(CurMask,ASIZE(CurMask)-1))
  {
    char *LastMaskChar=PointToLastChar(CurMask);
    bool DirMask=IsPathDiv(*LastMaskChar); // Mask for directories only.

    if (Dir)
    {
      // CheckName is a directory.
      if (DirMask)
      {
        // We process the directory and have the directory exclusion mask.
        // So let's convert "mask\" to "mask" and process it normally.
        
        *LastMaskChar=0;
      }
      else
      {
        // If mask has wildcards in name part and does not have the trailing
        // '\' character, we cannot use it for directories.
      
        if (IsWildcard(PointToName(CurMask)))
          continue;
      }
    }
    else
    {
      // If we process a file inside of directory excluded by "dirmask\".
      // we want to exclude such file too. So we convert "dirmask\" to
      // "dirmask\*". It is important for operations other than archiving.
      // When archiving, directory matched by "dirmask\" is excluded
      // from further scanning.

      if (DirMask)
        strcat(CurMask,"*");
    }

#ifndef SFX_MODULE
    if (CheckFullPath && IsFullPath(CurMask))
    {
      // We do not need to do the special "*\" processing here, because
      // unlike the "else" part of this "if", now we convert names to full
      // format, so they all include the path, which is matched by "*\"
      // correctly. Moreover, removing "*\" from mask would break
      // the comparison, because now all names have the path.

      if (*FullName==0)
        ConvertNameToFull(CheckName,FullName);
      if (CmpName(CurMask,FullName,MatchMode))
        return(true);
    }
    else
#endif
    {
      char NewName[NM+2],*CurName=Name;
      if (CurMask[0]=='*' && IsPathDiv(CurMask[1]))
      {
        // We want "*\name" to match 'name' not only in subdirectories,
        // but also in the current directory. We convert the name
        // from 'name' to '.\name' to be matched by "*\" part even if it is
        // in current directory.
        NewName[0]='.';
        NewName[1]=CPATHDIVIDER;
        strncpyz(NewName+2,Name,ASIZE(NewName)-2);
        CurName=NewName;
      }

      if (CmpName(ConvertPath(CurMask,NULL),CurName,MatchMode))
        return(true);
    }
  }
  return(false);
}


#ifndef SFX_MODULE
// Now this function performs only one task and only in Windows version:
// it skips symlinks to directories if -e1024 switch is specified.
// Symlinks are skipped in ScanTree class, so their entire contents
// is skipped too. Without this function we would check the attribute
// only directly before archiving, so we would skip the symlink record,
// but not the contents of symlinked directory.
bool CommandData::ExclDirByAttr(uint FileAttr)
{
#ifdef _WIN_ALL
  if ((FileAttr & FILE_ATTRIBUTE_REPARSE_POINT)!=0 &&
      (ExclFileAttr & FILE_ATTRIBUTE_REPARSE_POINT)!=0)
    return true;
#endif
  return false;
}
#endif




#ifndef SFX_MODULE
// Return 'true' if we need to exclude the file from processing.
bool CommandData::TimeCheck(RarTime &ft)
{
  if (FileTimeBefore.IsSet() && ft>=FileTimeBefore)
    return(true);
  if (FileTimeAfter.IsSet() && ft<=FileTimeAfter)
    return(true);
  return(false);
}
#endif


#ifndef SFX_MODULE
// Return 'true' if we need to exclude the file from processing.
bool CommandData::SizeCheck(int64 Size)
{
  if (FileSizeLess!=INT64NDF && Size>=FileSizeLess)
    return(true);
  if (FileSizeMore!=INT64NDF && Size<=FileSizeMore)
    return(true);
  return(false);
}
#endif




int CommandData::IsProcessFile(FileHeader &NewLhd,bool *ExactMatch,int MatchType)
{
  if (strlen(NewLhd.FileName)>=NM || wcslen(NewLhd.FileNameW)>=NM)
    return(0);
  bool Dir=(NewLhd.Flags & LHD_WINDOWMASK)==LHD_DIRECTORY;
  if (ExclCheck(NewLhd.FileName,Dir,false,true))
    return(0);
#ifndef SFX_MODULE
  if (TimeCheck(NewLhd.mtime))
    return(0);
  if ((NewLhd.FileAttr & ExclFileAttr)!=0 || InclAttrSet && (NewLhd.FileAttr & InclFileAttr)==0)
    return(0);
  if (!Dir && SizeCheck(NewLhd.FullUnpSize))
    return(0);
#endif
  char *ArgName;
  wchar *ArgNameW;
  FileArgs->Rewind();
  for (int StringCount=1;FileArgs->GetString(&ArgName,&ArgNameW);StringCount++)
  {
#ifndef SFX_MODULE
    bool Unicode=(NewLhd.Flags & LHD_UNICODE) || ArgNameW!=NULL && *ArgNameW!=0;
    if (Unicode)
    {
      wchar NameW[NM],ArgW[NM],*NamePtr=NewLhd.FileNameW;
      bool CorrectUnicode=true;
      if (ArgNameW==NULL || *ArgNameW==0)
      {
        if (!CharToWide(ArgName,ArgW) || *ArgW==0)
          CorrectUnicode=false;
        ArgNameW=ArgW;
      }
      if ((NewLhd.Flags & LHD_UNICODE)==0)
      {
        if (!CharToWide(NewLhd.FileName,NameW) || *NameW==0)
          CorrectUnicode=false;
        NamePtr=NameW;
      }
      if (CmpName(ArgNameW,NamePtr,MatchType))
      {
        if (ExactMatch!=NULL)
          *ExactMatch=wcsicompc(ArgNameW,NamePtr)==0;
        return(StringCount);
      }
      if (CorrectUnicode)
        continue;
    }
#endif
    if (CmpName(ArgName,NewLhd.FileName,MatchType))
    {
      if (ExactMatch!=NULL)
        *ExactMatch=stricompc(ArgName,NewLhd.FileName)==0;
      return(StringCount);
    }
  }
  return(0);
}


#ifndef GUI
void CommandData::ProcessCommand()
{
#ifndef SFX_MODULE

  const char *SingleCharCommands="FUADPXETK";
  if (Command[0]!=0 && Command[1]!=0 && strchr(SingleCharCommands,*Command)!=NULL || *ArcName==0)
    OutHelp(*Command==0 ? RARX_SUCCESS:RARX_USERERROR); // Return 'success' for 'rar' without parameters.

#ifdef _UNIX
  if (GetExt(ArcName)==NULL && (!FileExist(ArcName) || IsDir(GetFileAttr(ArcName))))
    strncatz(ArcName,".rar",ASIZE(ArcName));
#else
  if (GetExt(ArcName)==NULL)
    strncatz(ArcName,".rar",ASIZE(ArcName));
#endif

  if (strchr("AFUMD",*Command)==NULL)
  {
    if (GenerateArcName)
      GenerateArchiveName(ArcName,ArcNameW,ASIZE(ArcName),GenerateMask,false);

    StringList ArcMasks;
    ArcMasks.AddString(ArcName);
    ScanTree Scan(&ArcMasks,Recurse,SaveLinks,SCAN_SKIPDIRS);
    FindData FindData;
    while (Scan.GetNext(&FindData)==SCAN_SUCCESS)
      AddArcName(FindData.Name,FindData.NameW);
  }
  else
    AddArcName(ArcName,NULL);
#endif

  switch(Command[0])
  {
    case 'P':
    case 'X':
    case 'E':
    case 'T':
    case 'I':
      {
        CmdExtract Extract;
        Extract.DoExtract(this);
      }
      break;
#ifndef SILENT
    case 'V':
    case 'L':
      ListArchive(this);
      break;
    default:
      OutHelp(RARX_USERERROR);
#endif
  }
  if (!BareOutput)
    mprintf("\n");
}
#endif


void CommandData::AddArcName(const char *Name,const wchar *NameW)
{
  ArcNames->AddString(Name,NameW);
}


bool CommandData::GetArcName(char *Name,wchar *NameW,int MaxSize)
{
  if (!ArcNames->GetString(Name,NameW,NM))
    return(false);
  return(true);
}


bool CommandData::IsSwitch(int Ch)
{
#if defined(_WIN_ALL) || defined(_EMX)
  return(Ch=='-' || Ch=='/');
#else
  return(Ch=='-');
#endif
}


#ifndef SFX_MODULE
uint CommandData::GetExclAttr(const char *Str)
{
  if (IsDigit(*Str))
    return(strtol(Str,NULL,0));
  else
  {
    uint Attr;
    for (Attr=0;*Str;Str++)
      switch(etoupper(*Str))
      {
#ifdef _UNIX
        case 'D':
          Attr|=S_IFDIR;
          break;
        case 'V':
          Attr|=S_IFCHR;
          break;
#elif defined(_WIN_ALL) || defined(_EMX)
        case 'R':
          Attr|=0x1;
          break;
        case 'H':
          Attr|=0x2;
          break;
        case 'S':
          Attr|=0x4;
          break;
        case 'D':
          Attr|=0x10;
          break;
        case 'A':
          Attr|=0x20;
          break;
#endif
      }
    return(Attr);
  }
}
#endif




#ifndef SFX_MODULE
bool CommandData::CheckWinSize()
{
  static int ValidSize[]={
    0x10000,0x20000,0x40000,0x80000,0x100000,0x200000,0x400000
  };
  for (int I=0;I<sizeof(ValidSize)/sizeof(ValidSize[0]);I++)
    if (WinSize==ValidSize[I])
      return(true);
  WinSize=0x400000;
  return(false);
}
#endif
