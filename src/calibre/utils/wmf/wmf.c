#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <libwmf/api.h>
#include <libwmf/svg.h>

typedef struct {
    char *data;
    size_t len;
    size_t pos;
} buf;

//This code is taken mostly from the Abiword wmf plugin


// returns unsigned char cast to int, or EOF
static int wmf_WMF_read(void * context) {
    char c;
	buf *info = (buf*)context;

	if (info->pos == info->len)
		return EOF;

	c = info->data[pos];

	info->pos++;

	return (int)c;
}

// returns (-1) on error, else 0
static int wmf_WMF_seek(void * context, long pos) {
	buf* info = (buf*) context;

    if (pos < 0 || (size_t)pos > info->len) return -1;
	info->pos = (size_t)pos;
	return 0;
}

// returns (-1) on error, else pos
static long wmf_WMF_tell(void * context) {
	buf* info = (buf*) context;

	return (long) info->pos;
}


#define CLEANUP if(API) { if (stream) wmf_free(API, stream); wmf_api_destroy(API); };

static PyObject *
wmf_render(PyObject *self, PyObject *args) {
    char *data;
    Py_ssize_t sz;
    PyObject *ans;

	unsigned int disp_width  = 0;
	unsigned int disp_height = 0;

	float wmf_width;
	float wmf_height;
	float ratio_wmf;
	float ratio_bounds;

	unsigned long flags;

	unsigned int max_width  = 1600;
	unsigned int max_height = 1200;
	unsigned long max_flags = 0;

	static const char* Default_Description = "wmf2svg";

	wmf_error_t err;

	wmf_svg_t* ddata = 0;

	wmfAPI* API = 0;
	wmfD_Rect bbox;

	wmfAPI_Options api_options;

    buf read_info;

	char *stream = NULL;
	unsigned long stream_len = 0;

    if (!PyArg_ParseTuple(args, "s#", &data, &sz))
        return NULL;

	flags = WMF_OPT_IGNORE_NONFATAL | WMF_OPT_FUNCTION;
	api_options.function = wmf_svg_function;

	err = wmf_api_create(&API, flags, &api_options);

	if (err != wmf_E_None) {
        CLEANUP;
        return PyErr_NoMemory();
	}

	read_info.data = data;
	read_info.len = sz;
	read_info.pos = 0;

	err = wmf_bbuf_input(API, wmf_WMF_read, wmf_WMF_seek, wmf_WMF_tell, (void *) &read_info);
	if (err != wmf_E_None) {
        CLEANUP;
        PyErr_SetString(PyExc_Exception, "Failed to initialize WMF input");
        return NULL;
	}

	err = wmf_scan(API, 0, &(bbox));
	if (err != wmf_E_None)
	{	
        CLEANUP;
        PyErr_SetString(PyExc_ValueError, "Failed to scan the WMF");
        return NULL;
	}

/* Okay, got this far, everything seems cool.
 */
	ddata = WMF_SVG_GetData (API);

	ddata->out = wmf_stream_create(API, NULL);

	ddata->Description = (char *)Default_Description;

	ddata->bbox = bbox;

	wmf_display_size(API, &disp_width, &disp_height, 96, 96);

	wmf_width  = (float) disp_width;
	wmf_height = (float) disp_height;

	if ((wmf_width <= 0) || (wmf_height <= 0)) {
        CLEANUP;
        PyErr_SetString(PyExc_ValueError, "Bad WMF image size");
        return NULL;
	}

	if ((wmf_width  > (float) max_width )
	 || (wmf_height > (float) max_height)) {
		ratio_wmf = wmf_height / wmf_width;
		ratio_bounds = (float) max_height / (float) max_width;

		if (ratio_wmf > ratio_bounds) {
			ddata->height = max_height;
			ddata->width  = (unsigned int) ((float) ddata->height / ratio_wmf);
		}
		else {
			ddata->width  = max_width;
			ddata->height = (unsigned int) ((float) ddata->width  * ratio_wmf);
		}
	}
	else {
		ddata->width  = (unsigned int) ceil ((double) wmf_width );
		ddata->height = (unsigned int) ceil ((double) wmf_height);
	}

	ddata->flags |= WMF_SVG_INLINE_IMAGES;

	ddata->flags |= WMF_GD_OUTPUT_MEMORY | WMF_GD_OWN_BUFFER;

    err = wmf_play(API, 0, &(bbox));

    if (err != wmf_E_None) {
        CLEANUP;
        PyErr_SetString(PyExc_ValueError, "Playing of the WMF file failed");
        return NULL;
    }

	wmf_stream_destroy(API, ddata->out, &stream, &stream_len);

    ans = Py_BuildValue("s#", stream, stream_len);
    
    wmf_free(API, stream);
    wmf_api_destroy (API);

    return ans;
}


static PyMethodDef wmf_methods[] = {
    {"render", wmf_render, METH_VARARGS,
        "render(path) -> Render wmf as svg."
    },

    {NULL}  /* Sentinel */
};


PyMODINIT_FUNC
initwmf(void) 
{
    PyObject* m;
    m = Py_InitModule3("wmf", wmf_methods,
                       "Wrapper for the libwmf library");


}

