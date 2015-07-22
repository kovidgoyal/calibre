#ifndef _DICTMGR_HXX_
#define _DICTMGR_HXX_

#include "hunvisapi.h"

#define MAXDICTIONARIES 100
#define MAXDICTENTRYLEN 1024

struct dictentry {
  char * filename;
  char * lang;
  char * region;
};


class LIBHUNSPELL_DLL_EXPORTED DictMgr
{
private:
  DictMgr(const DictMgr&);
  DictMgr& operator = (const DictMgr&);
private:
  int                 numdict;
  dictentry *         pdentry;

public:
 
  DictMgr(const char * dictpath, const char * etype);
  ~DictMgr();
  int get_list(dictentry** ppentry);
            
private:
  int  parse_file(const char * dictpath, const char * etype);
  char * mystrsep(char ** stringp, const char delim);
  char * mystrdup(const char * s);
  void mychomp(char * s);

};

#endif
