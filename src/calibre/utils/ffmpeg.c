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
#include <stdint.h>
#include <libavutil/version.h>
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
    if (!PyErr_Occurred()) {  // python error happened in a callback function for example
        char avbuf[4096];
        av_strerror(errnum, avbuf, sizeof(avbuf));
        PyErr_Format(PyExc_Exception, "%s:%d:%s", __FILE__, line, avbuf);
    }
    return NULL;
}

typedef struct Transcoder {
    AVCodecContext *dec_ctx, *enc_ctx;
    AVFrame *dec_frame;
    AVFormatContext *ifmt_ctx, *ofmt_ctx;
    AVPacket *pkt;
    PyObject *write_output, *read_input, *seek_in_input, *seek_in_output;
    unsigned int output_bitrate;
    const char *container_format, *output_codec_name;
    AVAudioFifo *fifo;
    SwrContext *resample_ctx;
    int64_t pts;
} Transcoder;

#define check_call(func, ...) if ((ret = func(__VA_ARGS__)) < 0) return averror_as_python(ret, __LINE__);
static const bool debug_io = false;

static int
read_packet(void *opaque, uint8_t *buf, int buf_size) {
    PyObject *psz = PyLong_FromLong((long)buf_size);
    PyObject *ret = PyObject_CallOneArg(((Transcoder*)opaque)->read_input, psz);
    Py_DECREF(psz);
    if (!ret) return AVERROR_EXTERNAL;
    Py_buffer b;
    if (PyObject_GetBuffer(ret, &b, PyBUF_SIMPLE) != 0) { Py_DECREF(ret); return AVERROR_EXTERNAL; }
    memcpy(buf, b.buf, b.len < buf_size ? b.len : buf_size);
    int ans = b.len;
    PyBuffer_Release(&b); Py_DECREF(ret);
    if (debug_io) printf("read: requested_size: %d actual_size: %d\n", buf_size, ans);
    if (ans == 0 && buf_size > 0) ans = AVERROR_EOF;
    return ans;
}

static int
#if LIBAVFORMAT_VERSION_MAJOR >= 61
write_packet(void *opaque, const uint8_t *buf, int buf_size) {
#else
write_packet(void *opaque, uint8_t *buf, int buf_size) {
#endif
    Transcoder *t = opaque;
    PyObject *mv = PyMemoryView_FromMemory((char*)buf, buf_size, PyBUF_READ);
    if (!mv) return AVERROR_EXTERNAL;
    PyObject *ret = PyObject_CallOneArg(t->write_output, mv);
    Py_DECREF(mv);
    if (!ret) return AVERROR_EXTERNAL;
    int ans = PyLong_AsLong(ret);
    Py_DECREF(ret);
    if (debug_io) printf("write: requested_size: %d actual_size: %d\n", buf_size, ans);
    return ans;
}

static int64_t
size_packet(PyObject *seek_func, const char *which) {
    PyObject *pos = NULL, *end_pos = NULL, *ret = NULL, *set = NULL;
    int64_t ans = AVERROR_EXTERNAL;
    if (!(pos = PyObject_CallFunction(seek_func, "ii", 0, SEEK_CUR))) goto cleanup;
    if (!(end_pos = PyObject_CallFunction(seek_func, "ii", 0, SEEK_END))) goto cleanup;
    if (!(set = PyLong_FromLong(SEEK_SET))) goto cleanup;
    if (!(ret = PyObject_CallFunctionObjArgs(seek_func, pos, set, NULL))) goto cleanup;
    ans = PyLong_AsLongLong(end_pos);
    if (debug_io) printf("size %s: %ld\n", which, ans);
cleanup:
    Py_XDECREF(pos); Py_XDECREF(end_pos); Py_XDECREF(ret); Py_XDECREF(set);
    return ans;
}

static int64_t
seek_packet(PyObject *seek_func, int64_t offset, int whence, const char *which) {
    whence &= ~AVSEEK_FORCE;
    PyObject *ret = PyObject_CallFunction(seek_func, "Li", (long long)offset, whence);
    if (!ret) return AVERROR_EXTERNAL;
    long long ans = PyLong_AsLongLong(ret);
    if (debug_io) printf("seek %s offset=%ld whence: %d: %lld\n", which, offset, whence, ans);
    Py_DECREF(ret);
    return ans;
}

static int64_t
seek_packet_input(void *opaque, int64_t offset, int whence) {
    Transcoder *t = opaque;
    return whence & AVSEEK_SIZE ? size_packet(t->seek_in_input, "input") : seek_packet(t->seek_in_input, offset, whence, "input");
}

static int64_t
seek_packet_output(void *opaque, int64_t offset, int whence) {
    Transcoder *t = opaque;
    return whence & AVSEEK_SIZE ? size_packet(t->seek_in_output, "output") : seek_packet(t->seek_in_output, offset, whence, "output");
}

static bool
set_seek_pointers(PyObject *file, PyObject **seek) {
    PyObject *ret = PyObject_CallMethod(file, "seekable", "");
    if (!ret) return false;
    bool seekable = PyObject_IsTrue(ret);
    Py_DECREF(ret);
    if (seekable) {
        if (!(*seek = PyObject_GetAttrString(file, "seek"))) return false;
    } else *seek = NULL;
    return true;
}

static PyObject*
open_input_file(Transcoder *t) {
    if (!(t->ifmt_ctx = avformat_alloc_context())) { PyErr_NoMemory(); return NULL; }
    static const size_t io_bufsize = 8192;
    uint8_t *input_buf;
    if (!(input_buf = av_malloc(io_bufsize))) { PyErr_NoMemory(); return NULL; }
    if (t->seek_in_input) t->ifmt_ctx->pb = avio_alloc_context(input_buf, io_bufsize, 0, t, &read_packet, NULL, &seek_packet_input);
    else t->ifmt_ctx->pb = avio_alloc_context(input_buf, io_bufsize, 0, t, &read_packet, NULL, NULL);
    if (!(t->ifmt_ctx->pb)) { PyErr_NoMemory(); return NULL; }
    int ret;
    check_call(avformat_open_input, &t->ifmt_ctx, NULL, NULL, NULL);
    check_call(avformat_find_stream_info, t->ifmt_ctx, NULL);
    if (t->ifmt_ctx->nb_streams != 1) {
        PyErr_Format(PyExc_ValueError, "input file must have only one stream, it has: %u streams", t->ifmt_ctx->nb_streams); return NULL;
    }
    const AVStream *stream = t->ifmt_ctx->streams[0];
    const AVCodec *input_codec = avcodec_find_decoder(stream->codecpar->codec_id);
    if (!input_codec) {
        PyErr_SetString(PyExc_ValueError, "could not find codec to decode input file"); return NULL;
    }
    if (!(t->dec_ctx = avcodec_alloc_context3(input_codec))) return PyErr_NoMemory();
    check_call(avcodec_parameters_to_context, t->dec_ctx, stream->codecpar);
    check_call(avcodec_open2, t->dec_ctx, input_codec, NULL);
    t->dec_ctx->pkt_timebase = stream->time_base;
    return Py_True;
}

static PyObject*
open_output_file(Transcoder *t) {
    if (!(t->ofmt_ctx = avformat_alloc_context())) { PyErr_NoMemory(); return NULL; }
    static const size_t io_bufsize = 8192;
    uint8_t *input_buf;
    if (!(input_buf = av_malloc(io_bufsize))) { PyErr_NoMemory(); return NULL; }
    if (t->seek_in_output) t->ofmt_ctx->pb = avio_alloc_context(input_buf, io_bufsize, 1, t, NULL, &write_packet, &seek_packet_output);
    else t->ofmt_ctx->pb = avio_alloc_context(input_buf, io_bufsize, 1, t, NULL, &write_packet, NULL);
    if (!t->ofmt_ctx->pb) { PyErr_NoMemory(); return NULL; }

    if (!(t->ofmt_ctx->oformat = av_guess_format(t->container_format, NULL, NULL))) {
        PyErr_Format(PyExc_KeyError, "unknown output container format: %s", t->container_format); return NULL;
    }
    const AVCodec *output_codec = NULL;
    if (!t->output_codec_name[0]) {
        if (!(output_codec = avcodec_find_encoder(t->ofmt_ctx->oformat->audio_codec))) {
            PyErr_Format(PyExc_RuntimeError, "Default audio output codec for %s not available", t->ofmt_ctx->oformat->long_name); return NULL;
        }
    } else {
        if (!(output_codec = avcodec_find_encoder_by_name(t->output_codec_name))) {
            PyErr_Format(PyExc_KeyError, "unknown output codec: %s", t->output_codec_name); return NULL;
        }
    }
    AVStream *stream = NULL;
    if (!(stream = avformat_new_stream(t->ofmt_ctx, NULL))) return PyErr_NoMemory();
    if (!(t->enc_ctx = avcodec_alloc_context3(output_codec))) return PyErr_NoMemory();

    // Setup encoding parameters
    av_channel_layout_default(&t->enc_ctx->ch_layout, t->dec_ctx->ch_layout.nb_channels);
    t->enc_ctx->sample_rate = t->dec_ctx->sample_rate;
    t->enc_ctx->sample_fmt = output_codec->sample_fmts[0];
    t->enc_ctx->bit_rate = t->output_bitrate;
    if (!t->enc_ctx->bit_rate) {
        switch (output_codec->id) {
            case AV_CODEC_ID_AAC: t->enc_ctx->bit_rate = 96; break;
            case AV_CODEC_ID_MP3: t->enc_ctx->bit_rate = 192; break;
            default: t->enc_ctx->bit_rate = 128;
        }
        t->enc_ctx->bit_rate *= 1000 * t->enc_ctx->ch_layout.nb_channels;
    }
    stream->time_base.den = t->dec_ctx->sample_rate;
    stream->time_base.num = 1;
    if (t->ofmt_ctx->oformat->flags & AVFMT_GLOBALHEADER) t->enc_ctx->flags |= AV_CODEC_FLAG_GLOBAL_HEADER;
    int ret;
    check_call(avcodec_open2, t->enc_ctx, output_codec, NULL);
    check_call(avcodec_parameters_from_context, stream->codecpar, t->enc_ctx);
    return Py_True;
}

static PyObject*
add_samples_to_fifo(AVAudioFifo *fifo, uint8_t **converted_input_samples, const int frame_size) {
    int ret;

    /* Make the FIFO as large as it needs to be to hold both,
     * the old and the new samples. */
    check_call(av_audio_fifo_realloc, fifo, av_audio_fifo_size(fifo) + frame_size);
    /* Store the new samples in the FIFO buffer. */
    if (av_audio_fifo_write(fifo, (void **)converted_input_samples, frame_size) < frame_size) {
        PyErr_SetString(PyExc_Exception, "could not write data to FIFO"); return NULL;
    }
    return Py_True;
}

static PyObject*
decode_audio_frame(AVFrame *input_frame, AVFormatContext *input_format_context, AVCodecContext *input_codec_context, bool *data_present, bool *finished) {
    AVPacket *input_packet = av_packet_alloc();
    if (!input_packet) return PyErr_NoMemory();
    *data_present = false;
    *finished = false;
    int ret;
    PyObject *r = NULL;
    if ((ret = av_read_frame(input_format_context, input_packet)) < 0) {
        if (ret == AVERROR_EOF) *finished = 1;
        else { averror_as_python(ret, __LINE__); goto cleanup; }
    }
    Py_BEGIN_ALLOW_THREADS;
    ret = avcodec_send_packet(input_codec_context, input_packet);
    Py_END_ALLOW_THREADS;
    if (ret < 0) { averror_as_python(ret, __LINE__); goto cleanup; }
    Py_BEGIN_ALLOW_THREADS;
    ret = avcodec_receive_frame(input_codec_context, input_frame);
    Py_END_ALLOW_THREADS;
    if (ret == AVERROR(EAGAIN)) { r = Py_True; goto cleanup; }
    if (ret == AVERROR_EOF) { r = Py_True; *finished = true; goto cleanup; }
    if (ret < 0) { averror_as_python(ret, __LINE__); goto cleanup; }
    *data_present = true;
    r = Py_True;

cleanup:
    av_packet_free(&input_packet);
    return r;
}

static PyObject*
read_decode_convert_and_store(Transcoder *t, bool *finished) {
    PyObject *r = NULL;
    int ret;
    AVFrame *input_frame = av_frame_alloc();
    uint8_t **converted_input_samples = NULL;
    if (!input_frame) { PyErr_NoMemory(); goto cleanup; }
    bool data_present = false;
    if (!decode_audio_frame(input_frame, t->ifmt_ctx, t->dec_ctx, &data_present, finished)) goto cleanup;
    if (*finished) { r = Py_True; goto cleanup; }
    if (data_present) {
        // Convert the samples to the format needed by the encoder
        if ((ret = av_samples_alloc_array_and_samples(
                &converted_input_samples, NULL, t->enc_ctx->ch_layout.nb_channels,
                input_frame->nb_samples, t->enc_ctx->sample_fmt, 0)) < 0) { averror_as_python(ret, __LINE__); goto cleanup; }
        Py_BEGIN_ALLOW_THREADS;
        ret = swr_convert(t->resample_ctx, converted_input_samples, input_frame->nb_samples, (const uint8_t**)input_frame->extended_data, input_frame->nb_samples);
        Py_END_ALLOW_THREADS;
        if (ret < 0) { averror_as_python(ret, __LINE__); goto cleanup; }
        // Add the converted input samples to the FIFO buffer for later processing.
        if (!add_samples_to_fifo(t->fifo, converted_input_samples, input_frame->nb_samples)) goto cleanup;
    }

    r = Py_True;
cleanup:
    if (converted_input_samples) av_freep(&converted_input_samples[0]);
    av_freep(&converted_input_samples);
    av_frame_free(&input_frame);
    return r;
}


static PyObject*
encode_audio_frame(AVFrame *frame, AVFormatContext *output_format_context, AVCodecContext *output_codec_context, bool *data_present, int64_t *pts) {
    AVPacket *output_packet = av_packet_alloc();
    if (!output_packet) return PyErr_NoMemory();

    if (frame) {
        frame->pts = *pts;
        *pts += frame->nb_samples;
    }
    *data_present = false;
    int ret;
    PyObject *r = NULL;
    Py_BEGIN_ALLOW_THREADS;
    ret = avcodec_send_frame(output_codec_context, frame);
    Py_END_ALLOW_THREADS;
    if (ret < 0 && ret != AVERROR_EOF) {
        averror_as_python(ret, __LINE__); goto cleanup;
    }
    Py_BEGIN_ALLOW_THREADS;
    ret = avcodec_receive_packet(output_codec_context, output_packet);
    Py_END_ALLOW_THREADS;
    if (ret == AVERROR(EAGAIN)) {
        goto ok;
    } else if (ret == AVERROR_EOF) {
        goto ok;
    } else if (ret < 0) {
        averror_as_python(ret, __LINE__);
        goto cleanup;
        /* Default case: Return encoded data. */
    } else {
        *data_present = true;
    }
    if (*data_present && (ret = av_write_frame(output_format_context, output_packet)) < 0) {
        averror_as_python(ret, __LINE__); goto cleanup;
    }

ok:
    r = Py_True;

cleanup:
    av_packet_free(&output_packet);
    return r;
}


static PyObject*
load_encode_and_write(AVAudioFifo *fifo, AVFormatContext *output_format_context, AVCodecContext *output_codec_context, int64_t *pts) {
    const int frame_size = FFMIN(av_audio_fifo_size(fifo), output_codec_context->frame_size);
    PyObject *r = NULL;
    bool data_written = false;
    AVFrame *output_frame = av_frame_alloc();
    if (!output_frame) return PyErr_NoMemory();
    output_frame->nb_samples     = frame_size;
    av_channel_layout_copy(&output_frame->ch_layout, &output_codec_context->ch_layout);
    output_frame->format         = output_codec_context->sample_fmt;
    output_frame->sample_rate    = output_codec_context->sample_rate;
    int ret = av_frame_get_buffer(output_frame, 0);
    if (ret < 0) { averror_as_python(ret, __LINE__); goto cleanup; }
    if (av_audio_fifo_read(fifo, (void **)output_frame->data, frame_size) < frame_size) {
        PyErr_SetString(PyExc_Exception, "could not read audio data from AVAudioFifo"); goto cleanup;
    }
    if (!encode_audio_frame(output_frame, output_format_context, output_codec_context, &data_written, pts)) goto cleanup;
    r = Py_True;

cleanup:
    if (output_frame) av_frame_free(&output_frame);
    return r;
}


static PyObject*
transcode_loop(Transcoder *t) {
    AVCodecContext *output_codec_context = t->enc_ctx;
    while(true) {
        const int output_frame_size = output_codec_context->frame_size;
        bool finished = false;
        while (!finished && av_audio_fifo_size(t->fifo) < output_frame_size) {
            if (!read_decode_convert_and_store(t, &finished)) return NULL;
        }
        while (av_audio_fifo_size(t->fifo) >= output_frame_size || (finished && av_audio_fifo_size(t->fifo) > 0)) {
            if (!load_encode_and_write(t->fifo, t->ofmt_ctx, t->enc_ctx, &t->pts)) return NULL;
        }
        if (finished) {
             bool data_written = false;
             /* Flush the encoder as it may have delayed frames. */
             do {
                 if (!encode_audio_frame(NULL, t->ofmt_ctx, t->enc_ctx, &data_written, &t->pts)) return NULL;
             } while (data_written);
             break;
         }
    }
    return Py_True;
}

static void
free_transcoder_resources(Transcoder *t) {
    if (t->fifo) { av_audio_fifo_free(t->fifo); t->fifo = NULL; }
    if (t->enc_ctx) avcodec_free_context(&t->enc_ctx);
    if (t->dec_ctx) avcodec_free_context(&t->dec_ctx);
    if (t->ifmt_ctx) { if (t->ifmt_ctx->pb) { avio_context_free(&t->ifmt_ctx->pb); } avformat_close_input(&t->ifmt_ctx); }
    if (t->ofmt_ctx) { if (t->ofmt_ctx->pb) { avio_context_free(&t->ofmt_ctx->pb); } avformat_free_context(t->ofmt_ctx); }
    if (t->resample_ctx) swr_free(&t->resample_ctx);
    Py_CLEAR(t->seek_in_input); Py_CLEAR(t->read_input);
    Py_CLEAR(t->seek_in_output); Py_CLEAR(t->write_output);
}

static PyObject*
transcode_single_audio_stream(PyObject *self, PyObject *args, PyObject *kw) {
    static char *kwds[] = {"input_file", "output_file", "output_bitrate", "container_format", "output_codec_name", NULL};
    Transcoder t = {.container_format = "mp4", .output_codec_name = ""};
    PyObject *input_file, *output_file;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "OO|Iss", kwds, &input_file, &output_file, &t.write_output, &t.seek_in_output, &t.output_bitrate, &t.container_format, &t.output_codec_name)) return NULL;
    if (!set_seek_pointers(input_file, &t.seek_in_input)) return NULL;
    if (!(t.read_input = PyObject_GetAttrString(input_file, "read"))) return NULL;
    if (!set_seek_pointers(output_file, &t.seek_in_output)) return NULL;
    if (!(t.write_output = PyObject_GetAttrString(output_file, "write"))) return NULL;

    if (!open_input_file(&t)) goto cleanup;
    if (!open_output_file(&t)) goto cleanup;
    if (!(t.fifo = av_audio_fifo_alloc(t.enc_ctx->sample_fmt, t.enc_ctx->ch_layout.nb_channels, 1))) {
        PyErr_NoMemory(); goto cleanup;
    }
    int ret;
    if ((ret = swr_alloc_set_opts2(&t.resample_ctx,
        &t.enc_ctx->ch_layout, t.enc_ctx->sample_fmt, t.enc_ctx->sample_rate,
        &t.dec_ctx->ch_layout, t.dec_ctx->sample_fmt, t.dec_ctx->sample_rate,
        0, NULL)) < 0) { averror_as_python(ret, __LINE__); goto cleanup; }
    if ((ret = swr_init(t.resample_ctx)) < 0) { averror_as_python(ret, __LINE__); goto cleanup; }

    if ((ret = avformat_write_header(t.ofmt_ctx, NULL)) < 0) { averror_as_python(ret, __LINE__); goto cleanup; }
    if (!transcode_loop(&t)) goto cleanup;
    if ((ret = av_write_trailer(t.ofmt_ctx)) < 0) { averror_as_python(ret, __LINE__); goto cleanup; }

cleanup:
    free_transcoder_resources(&t);
    if (PyErr_Occurred()) return NULL;
    Py_RETURN_NONE;
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
exec_module(PyObject *module) {
    av_log_set_level(AV_LOG_ERROR);
    return 0;
}

CALIBRE_MODINIT_FUNC PyInit_ffmpeg(void) {
    static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };
    static PyMethodDef methods[] = {
        {"resample_raw_audio_16bit", (PyCFunction)resample_raw_audio_16bit, METH_VARARGS,
        "resample_raw_audio(input_data, input_sample_rate, output_sample_rate, input_num_channels=1, output_num_channels=1) -> Return resampled raw audio data."
        },
        {"transcode_single_audio_stream", (PyCFunction)transcode_single_audio_stream, METH_VARARGS | METH_KEYWORDS,
        "transcode_single_audio_stream() -> Transcode an input file containing a single audio stream to an output file in the specified format."
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
