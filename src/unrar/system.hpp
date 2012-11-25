#ifndef _RAR_SYSTEM_
#define _RAR_SYSTEM_

#ifdef _WIN_ALL
#ifndef BELOW_NORMAL_PRIORITY_CLASS
#define BELOW_NORMAL_PRIORITY_CLASS     0x00004000
#define ABOVE_NORMAL_PRIORITY_CLASS     0x00008000
#endif
#ifndef PROCESS_MODE_BACKGROUND_BEGIN
#define PROCESS_MODE_BACKGROUND_BEGIN   0x00100000
#define PROCESS_MODE_BACKGROUND_END     0x00200000
#endif
#ifndef SHTDN_REASON_MAJOR_APPLICATION
#define SHTDN_REASON_MAJOR_APPLICATION  0x00040000
#define SHTDN_REASON_FLAG_PLANNED       0x80000000
#define SHTDN_REASON_MINOR_MAINTENANCE  0x00000001
#endif
#endif

void InitSystemOptions(int SleepTime);
void SetPriority(int Priority);
void Wait();
bool EmailFile(char *FileName,char *MailTo);
void Shutdown();



#endif
