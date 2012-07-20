#ifndef QTC_COLOR_UTILS_H
#define QTC_COLOR_UTILS_H

extern color ColorUtils_lighten(const color *color, double ky, double kc);
extern color ColorUtils_darken(const color *color, double ky, double kc);
extern color ColorUtils_shade(const color *color, double ky, double kc);
extern color ColorUtils_tint(const color *base, const color *col, double amount);
extern color ColorUtils_mix(const color *c1, const color *c2, double bias);
extern double ColorUtils_luma(const color *color);

#endif
