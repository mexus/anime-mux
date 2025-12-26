# Technical Notes

## H.264 Re-encoding with Auto CRF

When using `--video-codec h264`, CRF is automatically calculated based on source resolution and bitrate.

### Base CRF by Resolution

| Resolution | Base CRF | Typical Bitrate |
|------------|----------|-----------------|
| 4K (2160p+)| 17       | 20 Mbps         |
| 1080p      | 19       | 8 Mbps          |
| 720p       | 21       | 4 Mbps          |
| 480p       | 23       | 2 Mbps          |
| Lower      | 25       | 1 Mbps          |

### Bitrate Adjustment

The base CRF is adjusted based on source bitrate relative to typical values:

- Source > 2× typical: CRF -= 2 (preserve quality of high-bitrate source)
- Source > 1.5× typical: CRF -= 1
- Source < 0.5× typical: CRF += 1 (source already low quality)

### Implementation

See `VideoEncodingConfig.calculate_crf()` in `models.py`. The algorithm extracts resolution and bitrate from ffprobe during analysis (`probe.py`), then calculates CRF at encoding time.

## FFmpeg Interleaving Bug Workaround

When mapping attachments (fonts) from one input file while taking audio from a different input file, FFmpeg exhibits a bug where audio/video packets are not properly interleaved in the output Matroska container.

### The Problem

With a command like:

```bash
ffmpeg -i video.mkv -i audio.mka -map 0:v -map 1:a -map '0:t?' -c copy output.mkv
```

FFmpeg writes packets in the wrong order. Instead of interleaving audio and video packets throughout the file:

```
video(0.000s) → audio(0.000s) → audio(0.021s) → video(0.042s) → audio(0.043s) → ...
```

It writes only one audio packet at the start, followed by all video packets:

```
video(0.000s) → audio(0.000s) → video(0.042s) → video(0.083s) → video(0.125s) → ...
```

### Symptoms

- **Video players show no audio** when video is playing (mpv, mplayer, VLC, ffplay all affected)
- **Audio plays correctly** when video is disabled (`mpv --no-video`)
- **ffprobe shows identical audio metadata** in both broken and working files
- **Extracted audio is byte-for-byte identical** — the audio data is present, just not interleaved

### Root Cause

The bug occurs specifically when:
1. Attachments are mapped from input 0 (`-map '0:t?'`)
2. Audio comes from a different input (`-map 1:a`)
3. The Matroska muxer is used

FFmpeg's default interleaving logic fails to properly schedule audio packets from the second input when attachment streams are present from the first input.

### The Fix

Adding `-max_interleave_delta 0` forces FFmpeg to strictly interleave packets by timestamp:

```bash
ffmpeg -i video.mkv -i audio.mka \
  -map 0:v -map 1:a -map '0:t?' \
  -max_interleave_delta 0 \
  -c copy output.mkv
```

This option sets the maximum time difference between packets in the interleaving queue to zero, ensuring packets are written in strict timestamp order regardless of which input they come from.

### Verification

You can verify proper interleaving with:

```bash
# Show first 40 packets with stream index and timestamp
ffprobe -v quiet -show_packets output.mkv | grep -E "stream_index|pts_time" | head -40
```

Correct output alternates between stream indices (0=video, 1=audio):
```
stream_index=0
pts_time=0.000000
stream_index=1
pts_time=0.000000
stream_index=1
pts_time=0.021000
stream_index=0
pts_time=0.042000
...
```

### Implementation

This fix is applied in `executor.py` when building the FFmpeg command:

```python
if job.preserve_attachments:
    primary_input = input_map[job.episode.video_file]
    cmd.extend(["-map", f"{primary_input}:t?"])
    cmd.extend(["-max_interleave_delta", "0"])
```
