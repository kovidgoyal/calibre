#include "rar.hpp"

#ifndef GUI
#include "log.cpp"
#endif

static int KbdAnsi(char *Addr,int Size);

#if !defined(GUI) && !defined(SILENT)
static void RawPrint(char *Msg,MESSAGE_TYPE MessageType);
static byte GetKey();
#endif

static MESSAGE_TYPE MsgStream=MSG_STDOUT;
static bool Sound=false;
const int MaxMsgSize=2*NM+2048;

void InitConsoleOptions(MESSAGE_TYPE MsgStream,bool Sound)
{
  ::MsgStream=MsgStream;
  ::Sound=Sound;
}

#if !defined(GUI) && !defined(SILENT)
void mprintf(const char *fmt,...)
{
  if (MsgStream==MSG_NULL || MsgStream==MSG_ERRONLY)
    return;
  char Msg[MaxMsgSize];
  va_list argptr;
  va_start(argptr,fmt);
  vsnprintf(Msg,ASIZE(Msg),fmt,argptr);

  // Different vsnprintf implementation can return either -1 or >=MaxMsgSize
  // if string is truncated. So we do not check exit code and always zero
  // terminate the string for safety. It is faster than check for error.
  Msg[ASIZE(Msg)-1] = 0;

  RawPrint(Msg,MsgStream);
  va_end(argptr);
}
#endif


#if !defined(GUI) && !defined(SILENT)
void eprintf(const char *fmt,...)
{
  if (MsgStream==MSG_NULL)
    return;
  safebuf char Msg[MaxMsgSize];
  va_list argptr;
  va_start(argptr,fmt);
  vsnprintf(Msg,ASIZE(Msg),fmt,argptr);

  // Different vsnprintf implementation can return either -1 or >=MaxMsgSize
  // if string is truncated. So we do not check exit code and always zero
  // terminate the string for safety. It is faster than check for error.
  Msg[ASIZE(Msg)-1] = 0;

  RawPrint(Msg,MSG_STDERR);
  va_end(argptr);
}
#endif


#if !defined(GUI) && !defined(SILENT)
void RawPrint(char *Msg,MESSAGE_TYPE MessageType)
{
  File OutFile;
  switch(MessageType)
  {
    case MSG_STDOUT:
      OutFile.SetHandleType(FILE_HANDLESTD);
      break;
    case MSG_STDERR:
    case MSG_ERRONLY:
      OutFile.SetHandleType(FILE_HANDLEERR);
      break;
    default:
      return;
  }
#ifdef _WIN_ALL
  CharToOemA(Msg,Msg);

  char OutMsg[MaxMsgSize];
  size_t OutPos=0;
  for (size_t I=0;Msg[I]!=0;I++)
  {
    if (Msg[I]=='\n' && (I==0 || Msg[I-1]!='\r') && OutPos<ASIZE(OutMsg)-1)
      OutMsg[OutPos++]='\r';
    if (OutPos<ASIZE(OutMsg)-1)
      OutMsg[OutPos++]=Msg[I];
  }
  OutMsg[OutPos]=0;
  strcpy(Msg,OutMsg);
#endif
#if defined(_UNIX) || defined(_EMX)
  char OutMsg[MaxMsgSize],*OutPos=OutMsg;
  for (size_t I=0;Msg[I]!=0;I++)
    if (Msg[I]!='\r')
      *(OutPos++)=Msg[I];
  *OutPos=0;
  strcpy(Msg,OutMsg);
#endif

  OutFile.Write(Msg,strlen(Msg));
}
#endif


#ifndef SILENT
void Alarm()
{
#ifndef SFX_MODULE
  if (Sound)
    putchar('\007');
#endif
}
#endif


#ifndef SILENT
#ifndef GUI
void GetPasswordText(wchar *Str,uint MaxLength)
{
  if (MaxLength==0)
    return;
#ifdef _WIN_ALL
  HANDLE hConIn=GetStdHandle(STD_INPUT_HANDLE);
  HANDLE hConOut=GetStdHandle(STD_OUTPUT_HANDLE);
  DWORD ConInMode,ConOutMode;
  DWORD Read=0;
  GetConsoleMode(hConIn,&ConInMode);
  GetConsoleMode(hConOut,&ConOutMode);
  SetConsoleMode(hConIn,ENABLE_LINE_INPUT);
  SetConsoleMode(hConOut,ENABLE_PROCESSED_OUTPUT|ENABLE_WRAP_AT_EOL_OUTPUT);

  ReadConsoleW(hConIn,Str,MaxLength-1,&Read,NULL);
  Str[Read]=0;
  SetConsoleMode(hConIn,ConInMode);
  SetConsoleMode(hConOut,ConOutMode);
#else
  char StrA[MAXPASSWORD];
#if defined(_EMX) || defined(_BEOS) || defined(__sparc) || defined(sparc) || defined (__VMS)
  fgets(StrA,ASIZE(StrA)-1,stdin);
#else
  strncpyz(StrA,getpass(""),ASIZE(StrA));
#endif
  CharToWide(StrA,Str,MaxLength);
  cleandata(StrA,sizeof(StrA));
#endif
  Str[MaxLength-1]=0;
  RemoveLF(Str);
}
#endif
#endif


#ifndef SILENT
bool GetPassword(PASSWORD_TYPE Type,const char *FileName,const wchar *FileNameW,
                 SecPassword *Password)
{
  Alarm();
  while (true)
  {
    char PromptStr[NM+256];
#if defined(_EMX) || defined(_BEOS)
    strcpy(PromptStr,St(MAskPswEcho));
#else
    strcpy(PromptStr,St(MAskPsw));
#endif
    if (Type!=PASSWORD_GLOBAL)
    {
      strcat(PromptStr,St(MFor));
      char *NameOnly=PointToName(FileName);
      if (strlen(PromptStr)+strlen(NameOnly)<ASIZE(PromptStr))
        strcat(PromptStr,NameOnly);
    }
    eprintf("\n%s: ",PromptStr);

    wchar PlainPsw[MAXPASSWORD];
    GetPasswordText(PlainPsw,ASIZE(PlainPsw));
    if (*PlainPsw==0 && Type==PASSWORD_GLOBAL)
      return(false);
    if (Type==PASSWORD_GLOBAL)
    {
      eprintf(St(MReAskPsw));
      wchar CmpStr[MAXPASSWORD];
      GetPasswordText(CmpStr,ASIZE(CmpStr));
      if (*CmpStr==0 || wcscmp(PlainPsw,CmpStr)!=0)
      {
        eprintf(St(MNotMatchPsw));
        cleandata(PlainPsw,sizeof(PlainPsw));
        cleandata(CmpStr,sizeof(CmpStr));
        continue;
      }
      cleandata(CmpStr,sizeof(CmpStr));
    }
    Password->Set(PlainPsw);
    cleandata(PlainPsw,sizeof(PlainPsw));
    break;
  }
  return(true);
}
#endif


#if !defined(GUI) && !defined(SILENT)
byte GetKey()
{
  char Str[80];
  bool EndOfFile;
#if defined(__GNUC__) || defined(sun)
  EndOfFile=(fgets(Str,sizeof(Str),stdin)==NULL);
#else
  File SrcFile;
  SrcFile.SetHandleType(FILE_HANDLESTD);
  EndOfFile=(SrcFile.Read(Str,sizeof(Str))==0);
#endif
  if (EndOfFile)
  {
    // Looks like stdin is a null device. We can enter to infinite loop
    // calling Ask(), so let's better exit.
    ErrHandler.Exit(RARX_USERBREAK);
  }
  return (byte)Str[0];
}
#endif


#if !defined(GUI) && !defined(SILENT)
int Ask(const char *AskStr)
{
  const int MaxItems=10;
  char Item[MaxItems][40];
  int ItemKeyPos[MaxItems],NumItems=0;

  for (const char *NextItem=AskStr;NextItem!=NULL;NextItem=strchr(NextItem+1,'_'))
  {
    char *CurItem=Item[NumItems];
    strncpyz(CurItem,NextItem+1,ASIZE(Item[0]));
    char *EndItem=strchr(CurItem,'_');
    if (EndItem!=NULL)
      *EndItem=0;
    int KeyPos=0,CurKey;
    while ((CurKey=CurItem[KeyPos])!=0)
    {
      bool Found=false;
      for (int I=0;I<NumItems && !Found;I++)
        if (loctoupper(Item[I][ItemKeyPos[I]])==loctoupper(CurKey))
          Found=true;
      if (!Found && CurKey!=' ')
        break;
      KeyPos++;
    }
    ItemKeyPos[NumItems]=KeyPos;
    NumItems++;
  }

  for (int I=0;I<NumItems;I++)
  {
    eprintf(I==0 ? (NumItems>4 ? "\n":" "):", ");
    int KeyPos=ItemKeyPos[I];
    for (int J=0;J<KeyPos;J++)
      eprintf("%c",Item[I][J]);
    eprintf("[%c]%s",Item[I][KeyPos],&Item[I][KeyPos+1]);
  }
  eprintf(" ");
  byte Ch=GetKey();
#if defined(_WIN_ALL)
  OemToCharBuffA((LPCSTR)&Ch,(LPSTR)&Ch,1);
#endif
  Ch=loctoupper(Ch);
  for (int I=0;I<NumItems;I++)
    if (Ch==(byte)Item[I][ItemKeyPos[I]])
      return(I+1);
  return(0);
}
#endif


int KbdAnsi(char *Addr,size_t Size)
{
  int RetCode=0;
#ifndef GUI
  for (size_t I=0;I<Size;I++)
    if (Addr[I]==27 && Addr[I+1]=='[')
    {
      for (size_t J=I+2;J<Size;J++)
      {
        if (Addr[J]=='\"')
          return(2);
        if (!IsDigit(Addr[J]) && Addr[J]!=';')
          break;
      }
      RetCode=1;
    }
#endif
  return(RetCode);
}


void OutComment(char *Comment,size_t Size)
{
#ifndef GUI
  if (KbdAnsi(Comment,Size)==2)
    return;
  const size_t MaxOutSize=0x400;
  for (size_t I=0;I<Size;I+=MaxOutSize)
  {
    char Msg[MaxOutSize+1];
    size_t CopySize=Min(MaxOutSize,Size-I);
    strncpy(Msg,Comment+I,CopySize);
    Msg[CopySize]=0;
    mprintf("%s",Msg);
  }
  mprintf("\n");
#endif
}
