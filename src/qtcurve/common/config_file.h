#ifndef QTC_CONFIG_FILE_H
#define QTC_CONFIG_FILE_H

#include "common.h"

#define MAX_CONFIG_FILENAME_LEN   1024
#define MAX_CONFIG_INPUT_LINE_LEN 256

#if !defined QT_VERSION || QT_VERSION >= 0x040000

#define QTC_MENU_FILE_PREFIX   "menubar-"
#define QTC_STATUS_FILE_PREFIX "statusbar-"

#define qtcMenuBarHidden(A)         qtcBarHidden((A), QTC_MENU_FILE_PREFIX)
#define qtcSetMenuBarHidden(A, H)   qtcSetBarHidden((A), (H), QTC_MENU_FILE_PREFIX)
#define qtcStatusBarHidden(A)       qtcBarHidden((A), QTC_STATUS_FILE_PREFIX)
#define qtcSetStatusBarHidden(A, H) qtcSetBarHidden((A), (H), QTC_STATUS_FILE_PREFIX)

#ifdef __cplusplus
extern bool qtcBarHidden(const QString &app, const char *prefix);
extern void qtcSetBarHidden(const QString &app, bool hidden, const char *prefix);
#else // __cplusplus
extern gboolean qtcBarHidden(const char *app, const char *prefix);
extern void qtcSetBarHidden(const char *app, bool hidden, const char *prefix);
#endif // __cplusplus

extern void qtcLoadBgndImage(QtCImage *img);

#endif // !defined QT_VERSION || QT_VERSION >= 0x040000)

extern const char * qtcGetHome();
extern const char *qtcConfDir();
extern void qtcSetRgb(color *col, const char *str);
extern void qtcDefaultSettings(Options *opts);
extern void qtcCheckConfig(Options *opts);
#ifdef __cplusplus
extern bool qtcReadConfig(const QString &file, Options *opts, Options *defOpts=0L, bool checkImages=true);
extern WindowBorders qtcGetWindowBorderSize(bool force=false);
#else
extern bool qtcReadConfig(const char *file, Options *opts, Options *defOpts);
extern WindowBorders qtcGetWindowBorderSize(gboolean force);
#endif

#ifdef CONFIG_WRITE
class KConfig;
extern bool qtcWriteConfig(KConfig *cfg, const Options &opts, const Options &def, bool exportingStyle=false);
#endif

#endif
