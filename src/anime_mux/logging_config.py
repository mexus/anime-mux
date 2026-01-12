"""Structured logging configuration for anime-mux."""

import logging
import sys
from pathlib import Path
from typing import Optional


class AnimeMuxLogger:
    """Logger with console (stderr) and optional file output."""

    def __init__(self, log_file: Optional[Path] = None, verbose: bool = False):
        self.logger = logging.getLogger("anime_mux")
        self.logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        self.logger.handlers.clear()

        # Console handler (forward to stderr)
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        self.logger.addHandler(console_handler)

        # File handler (detailed, with timestamps)
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            self.logger.addHandler(file_handler)

    def debug(self, msg: str, **kwargs):
        self.logger.debug(msg, **kwargs)

    def info(self, msg: str, **kwargs):
        self.logger.info(msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self.logger.warning(msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self.logger.error(msg, **kwargs)


# Global instance (initialized in CLI)
_logger: Optional[AnimeMuxLogger] = None


def get_logger() -> Optional[AnimeMuxLogger]:
    """Get the global logger instance."""
    return _logger


def init_logger(log_file: Optional[Path] = None, verbose: bool = False):
    """Initialize the global logger instance."""
    global _logger
    _logger = AnimeMuxLogger(log_file, verbose)
    return _logger
