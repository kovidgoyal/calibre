def resample_raw_audio_16bit(
    input_data: bytes,
    input_sample_rate: int,
    output_sample_rate: int,
    input_num_channels: int = 1,
    output_num_channels: int = 1,
) -> bytes:
    "resample_raw_audio(input_data, input_sample_rate, output_sample_rate, input_num_channels=1, output_num_channels=1) -> Return resampled raw audio data."
    pass

def transcode_single_audio_stream(
    input_file_like_object: object,
    output_file_like_object: object,
    output_bitrate: int = 0,
    container_format: str = '',
    output_codec_name: str = '',
) -> None:
    """transcode_single_audio_stream(input_file_like_object, output_file_like_object,
    output_bitrate: int = auto_select, container_format: str = auto_detect,
    output_codec_name: str = auto_detect) -> Transcode an input file containing a single
    audio stream to an output file. The format is autodetected from output file name or can
    be specified using the container_format and output_codec_name parameters. The output
    bitrate is by default automatically chosen based on the output codec.
    """
    pass

def wav_header_for_pcm_data(audio_data_size: int = 0, sample_rate: int = 22050, num_channels: int = 1) -> bytes:
    "wav_header_for_pcm_data(audio_data_size=0, sample_rate=22050, num_channels=1) -> WAV header for specified amount of PCM data as bytestring"
    pass
