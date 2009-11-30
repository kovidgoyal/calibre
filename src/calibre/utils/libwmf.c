#include <libwmf/api.h>
#include <libwmf/svg.h>

#define False 0
#define True 1
typedef int bool;

bool create_api(wmfAPI** API) {
    wmfAPI_Options options;
    wmf_error_t error;
    unsigned long flags;

    flags = WMF_OPT_FUNCTION;
	flags |= WMF_OPT_IGNORE_NONFATAL;

    options.function = wmf_svg_function;
    error = wmf_api_create (API, flags, &options);
    if (error != wmf_E_None) {
        wmf_api_destroy (*API);
        return False;
    }
    return True;
}

bool load_image(wmfAPI *API, const char *path) {
    wmf_error_t error;
    
    error = wmf_file_open(API, path);
    if (error != wmf_E_None) {
        wmf_api_destroy (API);
        return False;
    }
    return True;
}

bool scan_image(wmfAPI *API, wmfD_Rect *bbox) {
    wmf_error_t error;

    error = wmf_scan (API, 0, bbox);
    if (error != wmf_E_None) {
        wmf_api_destroy (API);
        return False;
    }
    return True;
}

void get_image_size(wmfD_Rect *bbox, float *width, float *height) {
    *width = bbox->BR.x - bbox->TL.x;
    *height = bbox->BR.y - bbox->TL.y;
}

int main(int argc, char **argv) {
    wmfAPI *API = NULL;
    wmfD_Rect bbox;
    wmf_svg_t *ddata;
    float width, height;

    if (argc != 2) {
        fprintf(stderr, "Usage: wmf file\n");
        return 1;
    }
    if (!create_api(&API)) {
        fprintf(stderr, "Failed to create WMF API\n");
        return 1;
    }
    ddata = WMF_SVG_GetData(API);

    if (!load_image(API, argv[1])) {
        fprintf(stderr, "Failed to load image: %s\n", argv[1]);
        return 1;
    }
    if (!scan_image(API, &bbox)) {
        fprintf(stderr, "Failed to scan image: %s\n", argv[1]);
        return 1;
    }


    wmf_file_close(API);
    get_image_size(&bbox, &width, &height);
    printf("Image size: %f x %f\n", width, height);

    return 0;
}
