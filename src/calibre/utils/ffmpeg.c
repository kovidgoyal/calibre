/*
 * ffmpeg.c
 * Copyright (C) 2024 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */


#define UNICODE
#define PY_SSIZE_T_CLEAN

#include <Python.h>

#include <libavutil/audio_fifo.h>
#include <libavcodec/avcodec.h>
#include <libavutil/samplefmt.h>
#include <libavutil/common.h>
#include <libavutil/channel_layout.h>
#include <libavutil/opt.h>
#include <libavutil/mem.h>
#include <libavutil/fifo.h>
#include <libswresample/swresample.h>

static PyObject*
averror_as_python(int errnum) {
    char buf[4096];
    av_strerror(errnum, buf, sizeof(buf));
    PyErr_SetString(PyExc_Exception, buf);
    return NULL;
}

static PyObject*
resample_raw_audio_16bit(PyObject *self, PyObject *args) {
    int input_sample_rate, output_sample_rate, input_num_channels = 1, output_num_channels = 1;
    Py_buffer inb = {0};
    if (!PyArg_ParseTuple(args, "y*ii|ii", &inb, &input_sample_rate, &output_sample_rate, &input_num_channels, &output_num_channels)) return NULL;
    int64_t output_size = av_rescale_rnd(inb.len, output_sample_rate, input_sample_rate, AV_ROUND_UP);
    uint8_t *output = av_malloc(output_size);  // we have to use av_malloc as it aligns to vector boundaries
    if (!output) { PyBuffer_Release(&inb); return PyErr_NoMemory(); }
    AVChannelLayout input_layout = {0}, output_layout = {0};
    av_channel_layout_default(&input_layout, input_num_channels);
    av_channel_layout_default(&output_layout, output_num_channels);
    SwrContext *swr_ctx = NULL;
    static const enum AVSampleFormat fmt = AV_SAMPLE_FMT_S16;
    const int bytes_per_sample = av_get_bytes_per_sample(fmt);
    int ret = swr_alloc_set_opts2(&swr_ctx,
            &output_layout, fmt, output_sample_rate,
            &input_layout, fmt, input_sample_rate,
            0, NULL);
    if (ret != 0) { av_free(output); PyBuffer_Release(&inb); return averror_as_python(ret); }
#define free_resources av_free(output); PyBuffer_Release(&inb); swr_free(&swr_ctx);
    if ((ret = swr_init(swr_ctx)) < 0) { free_resources; return averror_as_python(ret); }
    const uint8_t *input = inb.buf;
    ret = swr_convert(swr_ctx,
            &output, output_size / (output_num_channels * bytes_per_sample),
            &input,  inb.len / (input_num_channels * bytes_per_sample)
            );
    if (ret < 0) { free_resources; return averror_as_python(ret); }
    output_size = ret * output_num_channels * bytes_per_sample;
    PyObject *ans = PyBytes_FromStringAndSize((char*)output, output_size);
    free_resources;
#undef free_resources
    return ans;
}


// Boilerplate {{{
static int
exec_module(PyObject *module) { return 0; }

CALIBRE_MODINIT_FUNC PyInit_ffmpeg(void) {
    static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };
    static PyMethodDef methods[] = {
        {"resample_raw_audio_16bit", (PyCFunction)resample_raw_audio_16bit, METH_VARARGS,
        "resample_raw_audio(input_data, input_sample_rate, output_sample_rate, input_num_channels=1, output_num_channels=1) -> Return resampled raw audio data."
        },
        {0}  /* Sentinel */
    };
    static struct PyModuleDef module_def = {
        .m_base     = PyModuleDef_HEAD_INIT,
        .m_name     = "ffmpeg",
        .m_doc      = "Wrapper for the ffmpeg C libraries",
        .m_methods  = methods,
        .m_slots    = slots,
    };
    return PyModuleDef_Init(&module_def);
}
// }}}
