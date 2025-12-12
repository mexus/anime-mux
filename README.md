# anime-mux

A command-line tool for consolidating anime releases into clean, player-friendly MKV files.

## Features

- **Filter embedded tracks**: Keep only selected audio/subtitle tracks from MKV files
- **Merge external tracks**: Combine video with separate audio (MKA) and subtitle (ASS/SRT) files
- **Hybrid mode**: Add external tracks to files that already have embedded tracks
- **Smart episode detection**: Automatically matches files by episode number
- **Fast processing**: Parallel execution, video/audio stream-copy by default
- **Interactive selection**: Checkbox UI for track selection
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
| `--transcode-audio` | `-t` | Re-encode audio to AAC 256k (default: copy as-is) |
| `--verbose` | `-V` | Print ffmpeg commands before executing |
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

## How It Works

### Modules

- **cli.py** — Entry point, orchestrates the workflow
- **probe.py** — FFprobe wrapper for extracting track metadata
- **matcher.py** — Episode number extraction from filenames
- **discovery.py** — Finds external audio/subtitle sources
- **analyzer.py** — Builds unified analysis from probed data
- **selector.py** — Interactive track selection UI
- **planner.py** — Converts selections into merge jobs
- **executor.py** — Builds and runs FFmpeg commands
- **models.py** — Data classes (`Track`, `Episode`, `MergeJob`, etc.)

### Key Algorithms

#### Episode Number Extraction

The `matcher.py` module uses pattern detection to extract episode numbers:

1. Take the first filename as a template
2. Find all numeric sequences in it
3. For each numeric position (checked in reverse order):
   - Create a regex that captures that position
   - Test if ALL files match with unique numbers
4. The first matching pattern is used

Reverse order matters because episode numbers typically appear after static numbers like resolution (1080p) or year (2024).

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

## Technical Notes

See [TECHNICAL.md](TECHNICAL.md) for implementation details, including the FFmpeg interleaving bug workaround.

## License

MIT
