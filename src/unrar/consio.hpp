#ifndef _RAR_CONSIO_
#define _RAR_CONSIO_

#if !defined(SILENT) && !defined(SFX_MODULE)
  enum {SOUND_OK,SOUND_ALARM,SOUND_ERROR,SOUND_QUESTION};
#endif

enum PASSWORD_TYPE {PASSWORD_GLOBAL,PASSWORD_FILE,PASSWORD_ARCHIVE};

void InitConsoleOptions(MESSAGE_TYPE MsgStream,bool Sound);

#ifndef SILENT
  void mprintf(const char *fmt,...);
  void eprintf(const char *fmt,...);
  void Alarm();
  void GetPasswordText(wchar *Str,uint MaxLength);
  bool GetPassword(PASSWORD_TYPE Type,const char *FileName,const wchar *FileNameW,SecPassword *Password);
  int Ask(const char *AskStr);
#endif

void OutComment(char *Comment,size_t Size);

#ifdef SILENT
  #ifdef __GNUC__
    #define mprintf(args...)
    #define eprintf(args...)
  #else
    inline void mprintf(const char *fmt,...) {}
    inline void eprintf(const char *fmt,...) {}
  #endif
  inline void Alarm() {}
  inline void GetPasswordText(wchar *Str,uint MaxLength) {}
  inline bool GetPassword(PASSWORD_TYPE Type,const char *FileName,const wchar *FileNameW,SecPassword *Password) {return(false);}
  inline int Ask(const char *AskStr) {return(0);}
#endif

#endif
