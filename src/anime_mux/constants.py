"""Constants for anime-mux."""

# Resolution-based CRF values (H.264)
BASE_CRF_4K = 18
BASE_CRF_1080P = 20
BASE_CRF_720P = 22
BASE_CRF_480P = 24
BASE_CRF_LOWER = 26

# Typical bitrates by resolution (bits per second)
TYPICAL_BITRATE_4K = 20_000_000  # 20 Mbps
TYPICAL_BITRATE_1080P = 8_000_000  # 8 Mbps
TYPICAL_BITRATE_720P = 4_000_000  # 4 Mbps
TYPICAL_BITRATE_480P = 2_000_000  # 2 Mbps
TYPICAL_BITRATE_LOWER = 1_000_000  # 1 Mbps

# Bitrate adjustment thresholds (ratio of source to typical bitrate)
HIGH_BITRATE_THRESHOLD = 2.0
MEDIUM_BITRATE_THRESHOLD = 1.5
LOW_BITRATE_THRESHOLD = 0.5

# VA-API base quality values (for -rc_mode CQP)
BASE_QUALITY_4K = 20
BASE_QUALITY_1080P = 22
BASE_QUALITY_720P = 24
BASE_QUALITY_480P = 26
BASE_QUALITY_LOWER = 28

# Quality/CRF value range
MIN_QUALITY_VALUE = 0
MAX_QUALITY_VALUE = 51

# Codec offsets
HEVC_CODEC_OFFSET = 5

# FFmpeg parameters
VAAPI_DEVICE_PATH = "/dev/dri/renderD128"
ENCODING_PRESET_MEDIUM = "medium"
PIXEL_FORMAT_YUV420P = "yuv420p"
BF_FRAMES_ZERO = "0"
AUDIO_BITRATE_256K = "256k"
DISPOSITION_DEFAULT = "default"
DISPOSITION_NONE = "0"
MAX_INTERLEAVE_DELTA_ZERO = "0"

# FFprobe parameters
FFPROBE_VERBOSE_LEVEL = "quiet"
FFPROBE_OUTPUT_FORMAT = "json"

# Episode matching patterns
SPECIAL_EPISODE_PREFIXES = ["OVA", "OAD", "SP", "Special", "Extra", "Bonus", "Movie"]

# Video codec validation
VALID_VIDEO_CODECS = ("copy", "h264", "h264-vaapi", "hevc", "hevc-vaapi")

# Disk space
DISK_SPACE_WARNING_THRESHOLD = 5 * 1024**3  # 5 GB

# Timeout settings
PROGRESS_TIMEOUT_SECONDS = 300  # 5 minutes without progress = hung
MIN_PROGRESS_TIMEOUT = 60  # Minimum timeout for short videos
MAX_RUNTIME_MULTIPLIER = 3  # Max runtime = duration * 3
