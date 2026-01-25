#!/usr/bin/env python3
"""
OpenSubtitles Movie Hash Calculator

Official specification:
https://trac.opensubtitles.org/projects/opensubtitles/wiki/HashSourceCodes

Algorithm:
    hash = filesize + checksum(first_64KB) + checksum(last_64KB)

The hash is a 64-bit unsigned integer formatted as 16-character hex string.
"""

import struct
from pathlib import Path


def calculate_hash(video_path):
    """
    Calculate OpenSubtitles movie hash for a video file.

    Args:
        video_path: Path to video file

    Returns:
        16-character hexadecimal hash string (e.g., "9A7B3E2F1C8D5A4B")

    Raises:
        FileNotFoundError: If video file doesn't exist
        IOError: If file cannot be read
    """
    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Constants from OpenSubtitles specification
    HASH_BLOCK_SIZE = 65536  # 64KB = 65536 bytes

    file_size = video_path.stat().st_size

    # Hash starts with file size
    file_hash = file_size

    # Minimum file size check
    if file_size < HASH_BLOCK_SIZE:
        # For files smaller than 64KB, hash the entire file twice
        # This matches OpenSubtitles behavior
        pass

    with open(video_path, 'rb') as f:
        # Hash first 64KB
        for _ in range(HASH_BLOCK_SIZE // 8):
            buffer = f.read(8)
            if len(buffer) < 8:
                break
            # Unpack as unsigned long long (little endian)
            (chunk,) = struct.unpack('<Q', buffer)
            file_hash = (file_hash + chunk) & 0xFFFFFFFFFFFFFFFF  # Keep 64-bit

        # Hash last 64KB
        if file_size >= HASH_BLOCK_SIZE:
            f.seek(max(0, file_size - HASH_BLOCK_SIZE), 0)
        else:
            f.seek(0, 0)  # For small files, re-read from beginning

        for _ in range(HASH_BLOCK_SIZE // 8):
            buffer = f.read(8)
            if len(buffer) < 8:
                break
            (chunk,) = struct.unpack('<Q', buffer)
            file_hash = (file_hash + chunk) & 0xFFFFFFFFFFFFFFFF  # Keep 64-bit

    # Return as 16-character hexadecimal string (lowercase)
    return f"{file_hash:016x}"


def calculate_hash_verbose(video_path):
    """
    Calculate hash with debug information.

    Returns:
        tuple: (hash_string, file_size, debug_info)
    """
    video_path = Path(video_path)
    file_size = video_path.stat().st_size

    debug_info = {
        'file_path': str(video_path),
        'file_size': file_size,
        'file_size_mb': round(file_size / (1024 * 1024), 2)
    }

    hash_value = calculate_hash(video_path)

    return hash_value, file_size, debug_info


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("OpenSubtitles Movie Hash Calculator")
        print("=" * 50)
        print("\nUsage:")
        print("  python opensubtitles_hash.py <video_file>")
        print("\nExample:")
        print('  python opensubtitles_hash.py "movie.mkv"')
        sys.exit(1)

    video_file = sys.argv[1]

    try:
        hash_value, file_size, debug = calculate_hash_verbose(video_file)

        print("\nOpenSubtitles Hash Result:")
        print("-" * 50)
        print(f"File: {debug['file_path']}")
        print(f"Size: {debug['file_size']:,} bytes ({debug['file_size_mb']} MB)")
        print(f"Hash: {hash_value}")
        print()

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
