/*
 * ffmpeg.c
 * Copyright (C) 2024 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */


#define UNICODE
#define PY_SSIZE_T_CLEAN

#include <Python.h>
#include <stdbool.h>

#include <libavutil/audio_fifo.h>
#include <libavcodec/avcodec.h>
#include <libavutil/samplefmt.h>
#include <libavutil/common.h>
#include <libavutil/channel_layout.h>
#include <libavutil/opt.h>
#include <libavutil/mem.h>
#include <libavutil/fifo.h>
#include <libavformat/avformat.h>
#include <libavformat/avio.h>
#include <libswresample/swresample.h>

static PyObject*
averror_as_python(int errnum, int line) {
    char avbuf[4096];
    av_strerror(errnum, avbuf, sizeof(avbuf));
    PyErr_Format(PyExc_Exception, "%s:%d:%s", __FILE__, line, avbuf);
    return NULL;
}

// resample_raw_audio_16bit {{{
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
    if (ret != 0) { av_free(output); PyBuffer_Release(&inb); return averror_as_python(ret, __LINE__); }
#define free_resources av_free(output); PyBuffer_Release(&inb); swr_free(&swr_ctx);
    if ((ret = swr_init(swr_ctx)) < 0) { free_resources; return averror_as_python(ret, __LINE__); }
    const uint8_t *input = inb.buf;
    Py_BEGIN_ALLOW_THREADS
    ret = swr_convert(swr_ctx,
        &output, output_size / (output_num_channels * bytes_per_sample),
        &input,  inb.len / (input_num_channels * bytes_per_sample)
    );
    Py_END_ALLOW_THREADS
    if (ret < 0) { free_resources; return averror_as_python(ret, __LINE__); }
    output_size = ret * output_num_channels * bytes_per_sample;
    PyObject *ans = PyBytes_FromStringAndSize((char*)output, output_size);
    free_resources;
#undef free_resources
    return ans;
} // }}}

// wav_header_for_pcm_data {{{
static PyObject*
wav_header_for_pcm_data(PyObject *self, PyObject *args) {
    unsigned int sample_rate = 22050, num_channels=1, audio_data_size=0;
    if (!PyArg_ParseTuple(args, "|III", &audio_data_size, &sample_rate, &num_channels)) return NULL;
    struct {
        char riff[4];
        uint32_t file_size;
        char wave[4];
        char fmt[4];
        uint32_t block_size;
        uint16_t audio_format;
        uint16_t num_channels;
        uint32_t sample_rate;
        uint32_t byte_rate;
        uint16_t bytes_per_block;
        uint16_t bits_per_sample;
        char data[4];
        uint32_t subchunk2_size;
    } wav_header;
    wav_header.riff[0] = 'R';
    wav_header.riff[1] = 'I';
    wav_header.riff[2] = 'F';
    wav_header.riff[3] = 'F';

    wav_header.wave[0] = 'W';
    wav_header.wave[1] = 'A';
    wav_header.wave[2] = 'V';
    wav_header.wave[3] = 'E';

    wav_header.fmt[0] = 'f';
    wav_header.fmt[1] = 'm';
    wav_header.fmt[2] = 't';
    wav_header.fmt[3] = ' ';

    wav_header.data[0] = 'd';
    wav_header.data[1] = 'a';
    wav_header.data[2] = 't';
    wav_header.data[3] = 'a';

    wav_header.file_size = audio_data_size + sizeof(wav_header) - 8;
    wav_header.bits_per_sample = 16; // number of bits per sample per channel
    wav_header.block_size = wav_header.bits_per_sample;
    wav_header.audio_format = 1; // 1 for PCM 3 for float32
    wav_header.num_channels = num_channels; // Mono
    wav_header.sample_rate = sample_rate;
    wav_header.bytes_per_block = num_channels * wav_header.bits_per_sample / 8;
    wav_header.byte_rate = sample_rate * wav_header.bytes_per_block;
    wav_header.subchunk2_size = audio_data_size;
    return PyBytes_FromStringAndSize((void*)&wav_header, sizeof(wav_header));
}
// }}}

// Boilerplate {{{
static int
exec_module(PyObject *module) { return 0; }

CALIBRE_MODINIT_FUNC PyInit_ffmpeg(void) {
    static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };
    static PyMethodDef methods[] = {
        {"resample_raw_audio_16bit", (PyCFunction)resample_raw_audio_16bit, METH_VARARGS,
        "resample_raw_audio(input_data, input_sample_rate, output_sample_rate, input_num_channels=1, output_num_channels=1) -> Return resampled raw audio data."
        },
        {"wav_header_for_pcm_data", (PyCFunction)wav_header_for_pcm_data, METH_VARARGS,
        "wav_header_for_pcm_data(audio_data_size=0, sample_rate=22050, num_channels=1) -> WAV header for specified amount of PCM data as bytestring"
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
