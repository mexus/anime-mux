# anime-mux

A command-line tool for consolidating anime releases into clean, player-friendly MKV files.

## Features

- **Filter embedded tracks**: Keep only selected audio/subtitle tracks from MKV files
- **Merge external tracks**: Combine video with separate audio (MKA) and subtitle (ASS/SRT) files
- **Hybrid mode**: Add external tracks to files that already have embedded tracks
- **Smart episode detection**: Automatically matches files by episode number
- **Fast processing**: Parallel execution, video stream-copy, audio re-encoded to AAC
- **Interactive selection**: Checkbox UI with arrow keys and spacebar for track selection
- **Preserves attachments**: Keeps fonts and other MKV attachments intact

## Installation

### Prerequisites

- Python 3.10 or higher
- FFmpeg (with ffprobe) installed and in PATH

### Install with uv

```bash
git clone <repository-url>
cd anime-mux
uv sync
```

### Verify installation

```bash
uv run anime-mux --version
```

## Usage

### Basic Command

```bash
anime-mux <directory>
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--output PATH` | `-o` | Output directory (default: `<directory>/output`) |
| `--audio-dir PATH` | `-a` | Directory to search for external audio files |
| `--subs-dir PATH` | `-s` | Directory to search for external subtitle files |
| `--version` | `-v` | Show version and exit |

### Use Cases

#### 1. Filter Embedded Tracks

When your MKV files contain multiple audio/subtitle tracks and you want to keep only specific ones:

```bash
anime-mux /media/Anime/SeriesName/
```

The tool will:
1. Scan for video files
2. Show all audio tracks present in ALL files
3. Let you select which audio track(s) to keep
4. Show all subtitle tracks present in ALL files
5. Let you select which subtitle track(s) to keep
6. Create new files in `output/` with only selected tracks

#### 2. Merge External Tracks

When you have separate video, audio, and subtitle files:

```
/media/Anime/SeriesName/
├── Video/
│   ├── Episode.01.mkv
│   └── Episode.02.mkv
├── Audio/
│   ├── Anilibria/
│   │   ├── Episode.01.mka
│   │   └── Episode.02.mka
│   └── Studio_Band/
│       ├── Episode.01.mka
│       └── Episode.02.mka
└── Subtitles/
    └── English/
        ├── Episode.01.ass
        └── Episode.02.ass
```

```bash
anime-mux /media/Anime/SeriesName/Video/
```

The tool will:
1. Find video files in the specified directory
2. Search nearby directories for audio sources (Anilibria, Studio_Band)
3. Search nearby directories for subtitle sources (English)
4. Let you select which audio/subtitle sources to use
5. Match files by episode number and merge them

#### 3. Hybrid Mode

When your videos have embedded Japanese audio but you want to add an external Russian voiceover:

```bash
anime-mux /media/Anime/SeriesName/ -a /path/to/russian/audio/
```

The tool will show both embedded and external tracks, letting you select multiple audio tracks to include.

#### Handling Existing Files

If output files already exist, you'll be prompted to choose:
- **Overwrite** (`o`) - Re-process and overwrite existing files
- **Skip** (`s`) - Process only new files, skip existing ones
- **Abort** (`a`) - Cancel the operation

### Interactive Session Example

```
$ anime-mux /media/Anime/SeriesName/

anime-mux v0.1.0
==================================================

Scanning for video files...
Found 12 video file(s)
Detected episodes: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

Probing video files...
Probing [████████████████████████████████████████] 12/12

Searching for external audio sources...
  -> Found: Anilibria (12 files)

Searching for external subtitle sources...
  -> Found: English (12 files)

======================================================================
                         TRACK ANALYSIS
======================================================================
┏━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ # ┃ Source     ┃ Track                     ┃ Coverage ┃
┡━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ 1 │ [embedded] │ jpn - Japanese (2ch)      │ all      │
│ 2 │ Anilibria  │ [external]                │ all      │
└───┴────────────┴───────────────────────────┴──────────┘

======================================================================
                         TRACK SELECTION
======================================================================

? Select audio track(s) to include: (↑/↓ navigate, Space select, Enter confirm)
  ❯ ◉ [external] Anilibria
    ◉ [embedded] jpn - Japanese (2ch)

Audio selected:
  • [external] Anilibria
  • [embedded] jpn - Japanese (2ch)

? Select subtitle track(s) to include: (↑/↓ navigate, Space select, Enter confirm)
  ❯ ◉ [embedded] eng - English Subtitles

Subtitles selected:
  • [embedded] eng - English Subtitles

Proceed with merge? [Y/n]: y

Processing 12 files...
Merging [████████████████████████████████████████] 12/12

==================================================
Complete! 12 file(s) written to /media/Anime/SeriesName/output
```

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INPUT                               │
│                    anime-mux /path/to/series                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       DISCOVERY PHASE                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ Find Video  │    │ Find Audio  │    │ Find Sub    │         │
│  │ Files       │    │ Directories │    │ Directories │         │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘         │
│         └──────────────────┼──────────────────┘                 │
│                            ▼                                     │
│              ┌─────────────────────────┐                        │
│              │  Extract Episode        │                        │
│              │  Numbers (Matcher)      │                        │
│              └─────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        PROBE PHASE                               │
│              ┌─────────────────────────┐                        │
│              │  FFprobe each video     │                        │
│              │  Extract embedded       │                        │
│              │  track metadata         │                        │
│              └─────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ANALYSIS PHASE                              │
│              ┌─────────────────────────┐                        │
│              │  Build AnalysisResult   │                        │
│              │  - Find common tracks   │                        │
│              │  - Identify gaps        │                        │
│              └─────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SELECTION PHASE                              │
│              ┌─────────────────────────┐                        │
│              │  Interactive prompts    │                        │
│              │  - User picks audio     │                        │
│              │  - User picks subs      │                        │
│              │  - Handle gaps          │                        │
│              └─────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PLANNING PHASE                              │
│              ┌─────────────────────────┐                        │
│              │  Build MergePlan        │                        │
│              │  - Create MergeJob      │                        │
│              │    per episode          │                        │
│              └─────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EXECUTION PHASE                              │
│              ┌─────────────────────────┐                        │
│              │  For each MergeJob:     │                        │
│              │  - Build FFmpeg command │                        │
│              │  - Execute              │                        │
│              └─────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                          OUTPUT                                  │
│                 /path/to/series/output/                         │
│                 ├── Episode.01.mkv                              │
│                 ├── Episode.02.mkv                              │
│                 └── ...                                         │
└─────────────────────────────────────────────────────────────────┘
```

### Module Overview

| Module | Purpose |
|--------|---------|
| `cli.py` | Typer CLI definition, orchestrates the full workflow |
| `probe.py` | FFprobe wrapper, parses track metadata from media files |
| `matcher.py` | Extracts episode numbers from filenames using pattern detection |
| `discovery.py` | Finds video files and discovers external audio/subtitle sources |
| `analyzer.py` | Combines probe results and discovery into `AnalysisResult` |
| `selector.py` | Interactive menus for track selection, handles gaps |
| `planner.py` | Converts user selections into `MergePlan` |
| `executor.py` | Builds and runs FFmpeg commands |
| `models.py` | Data classes: `Track`, `Episode`, `MergeJob`, `MergePlan`, etc. |
| `utils.py` | Constants (file extensions, keywords) and Rich console |

### Key Algorithms

#### Episode Number Extraction

The `matcher.py` module uses a pattern-detection algorithm to extract episode numbers from filenames:

1. Take the first filename as a template
2. Find all numeric sequences in it
3. For each numeric position (checked in reverse order):
   - Create a regex that captures that position
   - Test if ALL files match the pattern with unique numbers
4. The first pattern that matches all files is used

Reverse order is important because episode numbers typically appear after static numbers like resolution (1080p) or year (2024).

**Supported patterns:**
- `[SubGroup] Series - 01 [1080p].mkv`
- `Series.S01E05.mkv`
- `series_ep_12.mkv`
- `01.ass`

#### Track Identity Matching

To find tracks that are "the same" across all episodes, each track has an `identity_key`:

- **Audio**: `audio|{language}|{title}|{channels}`
- **Subtitle**: `sub|{language}|{title}|{is_forced}`

Common tracks are found by intersecting identity keys across all episodes.

#### External Source Discovery

The `discovery.py` module searches for audio/subtitle directories:

1. Search in: video directory, parent directory
2. Look for directories matching keywords:
   - Audio: "Sound", "Audio", "Voiceover", etc.
   - Subtitles: "Subtitles", "Subs", "Sub", etc.
3. For each found directory:
   - If it contains media files directly → it's a source
   - If it has subdirectories with media files → each subdirectory is a source

### FFmpeg Command

The generated FFmpeg command uses stream mapping with video/subtitle copy and audio re-encoding:

```bash
ffmpeg -y \
  -i video.mkv \
  -i audio.mka \
  -i subs.ass \
  -map 0:v \           # video from input 0
  -map 1:a \           # audio from input 1
  -map 2:s \           # subtitles from input 2
  -map 0:t? \          # attachments from input 0 (optional)
  -c:v copy \          # video: no transcoding
  -c:a aac -b:a 256k \ # audio: re-encode to AAC 256kbps
  -c:s copy \          # subtitles: no transcoding
  -disposition:a:0 default \
  -disposition:s:0 default \
  output.mkv
```

### FFmpeg Interleaving Bug Workaround

When mapping attachments (fonts) from one input file while taking audio from a different input file, FFmpeg exhibits a bug where audio/video packets are not properly interleaved in the output Matroska container.

#### The Problem

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

#### Symptoms

- **Video players show no audio** when video is playing (mpv, mplayer, VLC, ffplay all affected)
- **Audio plays correctly** when video is disabled (`mpv --no-video`)
- **ffprobe shows identical audio metadata** in both broken and working files
- **Extracted audio is byte-for-byte identical** — the audio data is present, just not interleaved

#### Root Cause

The bug occurs specifically when:
1. Attachments are mapped from input 0 (`-map '0:t?'`)
2. Audio comes from a different input (`-map 1:a`)
3. The Matroska muxer is used

FFmpeg's default interleaving logic fails to properly schedule audio packets from the second input when attachment streams are present from the first input.

#### The Fix

Adding `-max_interleave_delta 0` forces FFmpeg to strictly interleave packets by timestamp:

```bash
ffmpeg -i video.mkv -i audio.mka \
  -map 0:v -map 1:a -map '0:t?' \
  -max_interleave_delta 0 \
  -c copy output.mkv
```

This option sets the maximum time difference between packets in the interleaving queue to zero, ensuring packets are written in strict timestamp order regardless of which input they come from.

#### Verification

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

## Development

### Project Structure

```
anime-mux/
├── pyproject.toml
├── src/
│   └── anime_mux/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── models.py
│       ├── probe.py
│       ├── discovery.py
│       ├── matcher.py
│       ├── analyzer.py
│       ├── selector.py
│       ├── planner.py
│       ├── executor.py
│       └── utils.py
└── tests/
    ├── test_matcher.py
    ├── test_probe.py
    └── test_analyzer.py
```

### Running Tests

```bash
uv run pytest
```

### Dependencies

- **typer** - CLI framework
- **rich** - Terminal formatting, tables, progress bars
- **InquirerPy** - Interactive checkbox selection
- **pytest** (dev) - Testing

## License

MIT
