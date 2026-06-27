import os
import sys
import subprocess

def check_required_packages():
    """Check if all required packages are installed and show install instructions if missing."""
    required_packages = ["colorama", "platformdirs", "langdetect", "pycountry"]
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print("\n" + "="*60)
        print("  SUBSERVIENT EXTRACTION - PACKAGE REQUIREMENTS ERROR")
        print("="*60)
        print("\nThe following required packages are missing:")
        for pkg in missing:
            print(f"  - {pkg}")
        print(f"\nTo resolve this issue:")
        print(f"  1. Navigate to your main Subservient folder")
        print(f"  2. Run subordinate.py so that it automatically installs the required packages.")
        print(f"  3. If 2 is not happening, choose option '4' to install & verify requirements")
        print(f"  4. After installation, try running extraction.py again")
        print(f"\nIf you don't have subordinate.py, please download the complete")
        print(f"Subservient package from the official source.")
        print("\n" + "="*60)
        input("Press Enter to exit...")
        sys.exit(1)

check_required_packages()

from pathlib import Path
from langdetect import detect
import datetime
import shutil
from colorama import init, Fore, Style
import re
from platformdirs import user_config_dir
import json
import pycountry
import threading
import time
from utils import ASCII_ART, clear_and_print_ascii, map_lang_3to2, get_skip_dirs_from_config, LANG_2TO3_PREFERRED, lang_in_list, fix_permissions_proactively, ensure_file_writable, ensure_directory_writable

SNAPSHOT_DIR = Path(__file__).parent.resolve()
BANNER_LINE = f"                   {Style.BRIGHT}{Fore.RED}[Phase 2/4]{Style.RESET_ALL} Subtitle Extraction"
CONFIG_PATH = SNAPSHOT_DIR / '.config'
WANTED_LANGUAGES = None
SERIES_MODE = None
DELETE_EXTRA_VIDEOS = None
EXTRAS_FOLDER_NAME = None
AUDIO_TRACK_LANGUAGES = None
PRESERVE_FORCED_SUBTITLES = None
PRESERVE_UNWANTED_SUBTITLES = None
RESYNC_MODE = None
PAUSE_SECONDS = None
RUN_COUNTER = None
if CONFIG_PATH.exists():
    lines = CONFIG_PATH.read_text(encoding='utf-8').splitlines()
    in_setup = False
    run_counter_line_idx = None
    for idx, line in enumerate(lines):
        if line.strip().lower() == '[setup]':
            in_setup = True
            continue
        if in_setup:
            if line.strip().startswith('[') and line.strip().lower() != '[setup]':
                break
            if line.strip() and not line.strip().startswith('#'):
                l = line.lower()
                if l.startswith('run_counter') and '=' in line:
                    run_counter_line_idx = idx
                    _, value = line.split('=', 1)
                    try:
                        RUN_COUNTER = int(value.strip())
                    except Exception:
                        RUN_COUNTER = 0
                elif l.startswith('languages') and '=' in line:
                    _, value = line.split('=', 1)
                    langs = [lang.strip().lower() for lang in value.strip().strip('"').split(',') if lang.strip()]
                    if langs:
                        WANTED_LANGUAGES = langs
                elif l.startswith('series_mode') and '=' in line:
                    _, value = line.split('=', 1)
                    SERIES_MODE = value.strip().lower() in ('true', '1', 'yes', 'on')
                elif l.startswith('delete_extra_videos') and '=' in line:
                    _, value = line.split('=', 1)
                    DELETE_EXTRA_VIDEOS = value.strip().lower() in ('true', '1', 'yes', 'on')
                elif l.startswith('extras_folder_name') and '=' in line:
                    _, value = line.split('=', 1)
                    if value.strip():
                        EXTRAS_FOLDER_NAME = value.strip()
                elif l.startswith('audio_track_languages') and '=' in line:
                    _, value = line.split('=', 1)
                    value_clean = value.strip().strip('"').lower()
                    if value_clean == 'all':
                        AUDIO_TRACK_LANGUAGES = 'ALL'
                    else:
                        langs = [lang.strip().lower() for lang in value_clean.split(',') if lang.strip()]
                        if langs:
                            AUDIO_TRACK_LANGUAGES = langs
                elif l.startswith('preserve_forced_subtitles') and '=' in line:
                    _, value = line.split('=', 1)
                    PRESERVE_FORCED_SUBTITLES = value.strip().lower() in ('true', '1', 'yes', 'on')
                elif l.startswith('preserve_unwanted_subtitles') and '=' in line:
                    _, value = line.split('=', 1)
                    PRESERVE_UNWANTED_SUBTITLES = value.strip().lower() in ('true', '1', 'yes', 'on')
                elif l.startswith('resync_mode') and '=' in line:
                    _, value = line.split('=', 1)
                    RESYNC_MODE = value.strip().lower() in ('true', '1', 'yes', 'on')
                elif l.startswith('pause_seconds') and '=' in line:
                    _, value = line.split('=', 1)
                    try:
                        PAUSE_SECONDS = float(value.strip())
                    except Exception:
                        pass
    # Read the current run_counter but DON'T increment it (subordinate.py already did)
    # Only subordinate.py should increment the run_counter, all other scripts use current value
    if run_counter_line_idx is not None and RUN_COUNTER is not None:
        # Don't increment - just use the current value set by subordinate.py
        pass
    else:
        # Fallback if run_counter not found
        RUN_COUNTER = 1
LOGS_DIR = SNAPSHOT_DIR / 'logs' / f'Subservient-run-{RUN_COUNTER}'
try:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
except PermissionError:
    fixed_items = fix_permissions_proactively(SNAPSHOT_DIR / 'logs')
    if fixed_items:
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Info: Fixed permissions and created logs directory")
        except Exception:
            print(f"Warning: Could not create logs directory (permission denied). Continuing without logging.")
            LOGS_DIR = None
    else:
        print(f"Warning: Could not create logs directory (permission denied). Continuing without logging.")
        LOGS_DIR = None
except Exception as e:
    print(f"Warning: Could not create logs directory: {str(e)}. Continuing without logging.")
    LOGS_DIR = None

log_time = datetime.datetime.now().strftime('%d-%m-%Y_%H.%M.%S')
LOG_FILE = LOGS_DIR / f"extraction_log_{log_time}.txt" if LOGS_DIR else None

init(autoreset=True)
if LOG_FILE:
    try:
        with LOG_FILE.open('w', encoding='utf-8') as f:
            f.write(ASCII_ART + '\n')
            f.write(BANNER_LINE + '\n\n')
    except PermissionError:
        print(f"Warning: Could not create log file (permission denied). Continuing without logging.")
        LOG_FILE = None
    except Exception as e:
        print(f"Warning: Could not create log file: {str(e)}. Continuing without logging.")
        LOG_FILE = None

clear_and_print_ascii(BANNER_LINE)

def ensure_initial_setup():
    """Check if Subservient initial setup is complete."""
    config_dir = Path(user_config_dir()) / "Subservient"
    pathfile = config_dir / "Subservient_pathfiles"
    required_keys = [
        "subservient_anchor",
        "subordinate_path",
        "extraction_path",
        "acquisition_path",
        "synchronisation_path",
        "utils_path"
    ]
    if not pathfile.exists():
        print_and_log(f"{Fore.RED}{Style.BRIGHT}[ERROR]{Style.RESET_ALL} Initial setup not complete.\n\n"
              f"{Fore.YELLOW}To get started with Subservient, please do the following:{Style.RESET_ALL}\n"
              f"{Fore.CYAN}1.{Style.RESET_ALL} Make sure that subordinate.py is located in the main folder, next to extraction.py, acquisition.py and synchronisation.py\n"
              f"{Fore.CYAN}2.{Style.RESET_ALL} Run subordinate.py. This will perform the internal setup and register all necessary script paths.\n"
              f"{Fore.CYAN}3.{Style.RESET_ALL} After setup, you can move subordinate.py to the movie(s) you want to process and run it again.\n\n"
              f"{Fore.YELLOW}If you need help, see the README file for more details.{Style.RESET_ALL}\n")
        input("Press Enter to exit...")
        sys.exit(1)
    lines = pathfile.read_text(encoding="utf-8").splitlines()
    keys = {l.split('=')[0] for l in lines if '=' in l}
    if not all(k in keys for k in required_keys):
        print_and_log(f"{Fore.RED}{Style.BRIGHT}[ERROR]{Style.RESET_ALL} Initial setup incomplete.\n\n"
              f"{Fore.YELLOW}To get started with Subservient, please do the following:{Style.RESET_ALL}\n"
              f"{Fore.CYAN}1.{Style.RESET_ALL} Make sure that subordinate.py is located in the main folder, next to extraction.py, acquisition.py and synchronisation.py\n"
              f"{Fore.CYAN}2.{Style.RESET_ALL} Run subordinate.py. This will perform the internal setup and register all necessary script paths.\n"
              f"{Fore.CYAN}3.{Style.RESET_ALL} After setup, you can move subordinate.py to the movie(s) you want to process and run it again.\n\n"
              f"{Fore.YELLOW}If you need help, see the README file for more details.{Style.RESET_ALL}\n")
        input("Press Enter to exit...")
        sys.exit(1)

ensure_initial_setup()


progress_last = False

def log(msg, end='\n'):
    """Write message to log file only."""
    if isinstance(msg, str) and msg.strip().startswith('Progress:'):
        return
    if LOG_FILE:
        try:
            with LOG_FILE.open('a', encoding='utf-8') as f:
                ansi_escape = re.compile(r'\x1b\[[0-9;]*m|\033\[[0-9;]*m')
                f.write(ansi_escape.sub('', str(msg)) + ('' if end == '' else end))
        except (PermissionError, OSError):
            pass  # Continue silently if logging fails
def print_and_log(msg, end='\n'):
    """Print message to console and write to log file."""
    if isinstance(msg, str) and msg.strip().startswith('Progress:'):
        return
    if not hasattr(print_and_log, 'progress_last'):
        print_and_log.progress_last = False
    is_progress = False
    if is_progress:
        print(msg.ljust(79), end='\r', flush=True)
        print_and_log.progress_last = True
        return
    if print_and_log.progress_last:
        print(' ' * 80, end='\r', flush=True)
        print_and_log.progress_last = False
    print(msg, end=end)
    log(msg, end=end)
def ext_tag():
    """Return formatted extraction tag for console output."""
    return f"{Style.BRIGHT}{Fore.BLUE}[Extraction]{Style.RESET_ALL}"
UNWANTED_EXTENSIONS = [".sub", ".idx", ".sup", ".vob"]
ALLOWED_CODECS = ["SubRip/SRT", "S_TEXT/UTF8", "SubStationAlpha", "S_TEXT/ASS", "SSA", "ASS", "TIMED_TEXT", "TIMED TEXT"]
def detect_language(sub_path):
    """Detect language of subtitle file using langdetect library."""
    try:
        with open(sub_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().isdigit()]
            text_sample = " ".join(lines[:200])
            if not text_sample.strip():
                raise ValueError("No usable text for detection.")
            return detect(text_sample)
    except Exception as e:
        print_and_log(f"{ext_tag()} {Fore.RED}Error detecting language in {sub_path.name}: {str(e)}{Style.RESET_ALL}")
        return "unknown"
def cleanup_unwanted_files(base_path):
    """Remove unwanted files created during extraction process."""
    for ext in UNWANTED_EXTENSIONS:
        for unwanted in base_path.parent.glob(base_path.stem + f".und*{ext}"):
            try:
                unwanted.unlink()
                print_and_log(f"{ext_tag()} {Fore.YELLOW}Removed leftover unwanted file: {unwanted.name}{Style.RESET_ALL}")
            except PermissionError:
                print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove file {unwanted.name} (permission denied){Style.RESET_ALL}")
            except Exception as e:
                print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove file {unwanted.name}: {str(e)}{Style.RESET_ALL}")
def extract_sxxexx_code(name: str) -> str:
    """Extract season/episode code from filename."""
    match = re.search(r"[sS](\d{1,2})[eE](\d{1,2})", name)
    if match:
        season = int(match.group(1))
        episode = int(match.group(2))
        return f"S{season:02d}E{episode:02d}"
    return "UNKNOWN"
def shortname(path, maxlen=40):
    """Truncate path to specified maximum length for display."""
    name = str(path)
    if len(name) <= maxlen:
        return name
    return name[:maxlen//2] + '...' + name[-maxlen//2:]
def print_movie_header(movie_name, idx, total):
    """Print formatted header for current movie being processed."""
    bar = f"{Fore.CYAN}[{idx}/{total}]{Style.RESET_ALL}  {Fore.LIGHTYELLOW_EX}{movie_name.upper()}{Style.RESET_ALL}"
    print(bar.ljust(79), end='\n')
def run_extraction_with_progress(cmd, output_path, total_subtitles, current_sub):
    """Run subtitle extraction command with progress display."""
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    start_time = time.time()
    
    def update_progress():
        elapsed = time.time() - start_time
        bar_length = 40
        progress = current_sub / total_subtitles if total_subtitles > 0 else 0
        filled_length = int(bar_length * progress)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        print(f"\r{ext_tag()} {Fore.CYAN}[{bar}]{Style.RESET_ALL} {progress*100:.1f}% ({current_sub}/{total_subtitles}) - {elapsed:.1f}s", end='', flush=True)
    
    def progress_thread():
        while process.poll() is None:
            update_progress()
            time.sleep(0.25)
        update_progress()
    
    t = threading.Thread(target=progress_thread)
    t.start()
    stdout, stderr = process.communicate()
    t.join()
    print()
    return stdout, stderr

def run_remux_with_progress(cmd, temp_path, orig_size):
    """Run video remux command with file size-based progress bar."""
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    percent = [0]
    stop_flag = [False]
    def progress_thread():
        while process.poll() is None and not stop_flag[0]:
            try:
                if temp_path.exists() and orig_size > 0:
                    done = temp_path.stat().st_size
                    p = min(int((done / orig_size) * 100), 100)
                    if p != percent[0]:
                        percent[0] = p
                        print(f"{Fore.WHITE}Remux progress: {p}%{Style.RESET_ALL}".ljust(79), end='\r', flush=True)
            except Exception:
                pass
            time.sleep(0.25)
        print(' ' * 80, end='\r', flush=True)
    t = threading.Thread(target=progress_thread)
    t.start()
    stdout, stderr = process.communicate()
    stop_flag[0] = True
    t.join()
    return stdout, stderr
def extract_subtitles(file_path, movie_idx=1, total_movies=1):
    """Extract internal subtitles from video file and clean up temporary files."""
    extracted_files = []
    deleted_files = []
    forced_vobsub_to_remove = []  # Initialize early to avoid UnboundLocalError
    
    # Clean up any leftover .temp.mkv files from previous failed operations
    parent_dir = file_path.parent
    base_name = file_path.stem
    temp_path = parent_dir / (base_name + ".temp.mkv")
    if temp_path.exists():
        try:
            temp_path.unlink()
            print_and_log(f"{ext_tag()} {Fore.YELLOW}Cleaned up leftover temp file: {temp_path.name}{Style.RESET_ALL}")
        except Exception as e:
            print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove leftover temp file {temp_path.name}: {str(e)}{Style.RESET_ALL}")
    
    # Verify the file still exists before proceeding (in case of previous processing issues)
    if not file_path.exists():
        print_and_log(f"{ext_tag()} {Fore.RED}Error: File not found: {file_path.name}{Style.RESET_ALL}")
        print_and_log(f"{ext_tag()} {Fore.YELLOW}This may indicate a previous processing error or the file was moved/renamed.{Style.RESET_ALL}")
        return
    
    if file_path.stat().st_size < 50 * 1024 * 1024:
        print_and_log(f"{ext_tag()} {Fore.YELLOW}Skipped (file too small < 50MB): {shortname(file_path)}{Style.RESET_ALL}")
        return
    
    fixed_items = fix_permissions_proactively(file_path)
    
    print_movie_header(file_path.stem, movie_idx, total_movies)
    print_and_log(f"{ext_tag()} {Fore.CYAN}Scanning: {shortname(file_path)}{Style.RESET_ALL}")
    und_index = 0
    original_suffix = file_path.suffix.lower()
    extracted_track_for_lang = {}   # lang -> {'track_id': str, 'srt_path': Path}
    forced_track_ids_by_size = {}   # lang -> track_id of the forced track (detected by file size)
    base_name = file_path.stem
    parent_dir = file_path.parent
    base_path = parent_dir / base_name
    sxxexx_code = extract_sxxexx_code(file_path.name) if SERIES_MODE else None
    
    # Check if subtitles already exist (both standard and series naming)
    has_lang = {}
    for lang in WANTED_LANGUAGES:
        # Check standard naming: filename.lang.srt
        standard_srt = parent_dir / f"{base_name}.{lang}.srt"
        
        # Check series naming if in series mode
        series_srt = None
        if SERIES_MODE and sxxexx_code:
            # Check if video filename already contains the episode code
            if sxxexx_code.lower() in base_name.lower():
                # Video already has SxxExx in name, subtitle should use standard naming
                series_srt = parent_dir / f"{base_name}.{lang}.srt"
            else:
                # Video doesn't have SxxExx, subtitle should have SxxExx before language
                series_srt = parent_dir / f"{base_name}.{sxxexx_code}.{lang}.srt"
        
        # Language exists if either standard or series file exists
        has_lang[lang] = standard_srt.exists() or (series_srt and series_srt.exists())

    try:
        info_cmd_json = ['mkvmerge', '-J', str(file_path)]
        result_json = subprocess.run(info_cmd_json, capture_output=True, text=True)
        if result_json.returncode != 0:
            print_and_log(f"{ext_tag()} {Fore.RED}Error reading file (JSON).{Style.RESET_ALL}")
            return
        try:
            mkv_info = json.loads(result_json.stdout)
            audio_tracks = [t for t in mkv_info.get('tracks', []) if t.get('type') == 'audio']
            if audio_tracks:
                for t in audio_tracks:
                    lang = t.get('properties', {}).get('language', 'und')
                    tid = t.get('id', '?')
                    print_and_log(f"{ext_tag()} {Fore.CYAN}Audio track {tid}: language {lang}{Style.RESET_ALL}")
            external_subs = list(parent_dir.glob(f"{base_name}.*.srt"))
            if external_subs:
                for sub in external_subs:
                    sub_name = sub.stem.lower()
                    if 'forced' in sub_name and '.forced.' not in sub_name:
                        parts = sub.stem.split('.')
                        if len(parts) >= 2:
                            lang_part = parts[1]
                            if lang_part in WANTED_LANGUAGES:
                                if PRESERVE_FORCED_SUBTITLES:
                                    proper_name = f"{base_name}.{lang_part}.forced.srt"
                                    new_path = parent_dir / proper_name
                                    if not new_path.exists():
                                        try:
                                            sub.rename(new_path)
                                            print_and_log(f"{ext_tag()} {Fore.MAGENTA}Renamed external FORCED subtitle: {shortname(new_path)}{Style.RESET_ALL}")
                                            continue
                                        except PermissionError as e:
                                            print_and_log(f"{ext_tag()} {Fore.RED}PERMISSION ERROR: Cannot rename external FORCED subtitle!{Style.RESET_ALL}")
                                            print_and_log(f"{ext_tag()} {Fore.RED}Source: {sub.name} → Target: {proper_name}{Style.RESET_ALL}")
                                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Please check folder permissions and try again.{Style.RESET_ALL}")
                                else:
                                    proper_name = f"{base_name}.{lang_part}.srt"
                                    new_path = parent_dir / proper_name
                                    if not new_path.exists():
                                        try:
                                            sub.rename(new_path)
                                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Renamed external FORCED subtitle to regular: {shortname(new_path)} (preserve_forced_subtitles=false){Style.RESET_ALL}")
                                            continue
                                        except PermissionError as e:
                                            print_and_log(f"{ext_tag()} {Fore.RED}PERMISSION ERROR: Cannot rename external FORCED subtitle!{Style.RESET_ALL}")
                                            print_and_log(f"{ext_tag()} {Fore.RED}Source: {sub.name} → Target: {proper_name}{Style.RESET_ALL}")
                                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Please check folder permissions and try again.{Style.RESET_ALL}")
                    print_and_log(f"{ext_tag()} {Fore.CYAN}External subtitle found: {shortname(sub)}{Style.RESET_ALL}")
            subtitle_tracks = [t for t in mkv_info.get('tracks', []) if t.get('type') == 'subtitles']
            vobsub_per_lang = {lang: [] for lang in WANTED_LANGUAGES}
            vobsub_forced_per_lang = {lang: [] for lang in WANTED_LANGUAGES}
            srt_found_per_lang = {}
            for lang in WANTED_LANGUAGES:
                # Check standard naming: filename.lang.srt
                standard_exists = (parent_dir / f"{base_name}.{lang}.srt").exists()
                forced_exists = PRESERVE_FORCED_SUBTITLES and (parent_dir / f"{base_name}.{lang}.forced.srt").exists()
                
                # Check series naming if in series mode
                series_exists = False
                series_forced_exists = False
                if SERIES_MODE and sxxexx_code:
                    # Check if video filename already contains the episode code
                    if sxxexx_code.lower() in base_name.lower():
                        # Video already has SxxExx in name, subtitle uses standard naming
                        series_exists = (parent_dir / f"{base_name}.{lang}.srt").exists()
                        series_forced_exists = PRESERVE_FORCED_SUBTITLES and (parent_dir / f"{base_name}.{lang}.forced.srt").exists()
                    else:
                        # Video doesn't have SxxExx, subtitle has SxxExx before language
                        series_exists = (parent_dir / f"{base_name}.{sxxexx_code}.{lang}.srt").exists()
                        series_forced_exists = PRESERVE_FORCED_SUBTITLES and (parent_dir / f"{base_name}.{sxxexx_code}.{lang}.forced.srt").exists()
                
                srt_found_per_lang[lang] = standard_exists or forced_exists or series_exists or series_forced_exists
            unwanted_bitmap_count = 0
            forced_vobsub_to_remove = []
            forced_text_subtitles = []
            
            for t in subtitle_tracks:
                codec = t.get('codec', '').upper()
                tid = t.get('id', '?')
                lang_raw = t.get('properties', {}).get('language', 'und').lower()
                lang = map_lang_3to2(lang_raw)
                forced = t.get('properties', {}).get('forced_track', False) or \
                         (t.get('properties', {}).get('flag-forced', False)) or \
                         ('forced' in (t.get('properties', {}).get('track_name', '') or '').lower())
                
                if any(x in codec for x in ['SRT', 'ASS', 'UTF8', 'SSA']):
                    if forced:
                        print_and_log(f"{ext_tag()} {Fore.MAGENTA}Internal FORCED subtitle track {tid}: {codec}, language {lang_raw}{Style.RESET_ALL}")
                        forced_text_subtitles.append({
                            'id': str(tid),
                            'lang': lang,
                            'lang_raw': lang_raw,
                            'codec': codec
                        })
                        if PRESERVE_FORCED_SUBTITLES:
                            print_and_log(f"{ext_tag()} {Fore.CYAN}→ FORCED subtitle will be preserved with .forced. naming (preserve_forced_subtitles=true){Style.RESET_ALL}")
                        else:
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}→ FORCED subtitle detected but will be treated as regular subtitle (preserve_forced_subtitles=false){Style.RESET_ALL}")
                    else:
                        print_and_log(f"{ext_tag()} {Fore.GREEN}Internal subtitle track {tid}: {codec}, language {lang_raw}{Style.RESET_ALL}")
                elif any(x in codec for x in ['VOBSUB', 'VOB', 'SUP', 'PGS', 'HDMV']):
                    if lang in vobsub_per_lang:
                        if forced:
                            print_and_log(f"{ext_tag()} {Fore.MAGENTA}Internal FORCED VobSub track {tid}: {codec}, language {lang_raw}{Style.RESET_ALL}")
                            if PRESERVE_FORCED_SUBTITLES:
                                print_and_log(f"{ext_tag()} {Fore.CYAN}→ FORCED VobSub will be preserved with .forced. naming (preserve_forced_subtitles=true){Style.RESET_ALL}")
                            else:
                                print_and_log(f"{ext_tag()} {Fore.YELLOW}→ FORCED VobSub detected but will be treated as regular subtitle (preserve_forced_subtitles=false){Style.RESET_ALL}")
                        else:
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Internal subtitle track {tid}: {codec}, language {lang_raw}{Style.RESET_ALL}")
                        vobsub_per_lang[lang].append((tid, forced))
                        if forced:
                            vobsub_forced_per_lang[lang].append(tid)
                    else:
                        unwanted_bitmap_count += 1
                else:
                    print_and_log(f"{ext_tag()} Internal subtitle track {tid}: {codec}, language {lang_raw}")
            
            total_forced = len(forced_text_subtitles) + sum(len(tracks) for tracks in vobsub_forced_per_lang.values())
            if total_forced > 0:
                print_and_log(f"{ext_tag()} {Fore.MAGENTA}Found {total_forced} FORCED subtitle track(s) total{Style.RESET_ALL}")
                if PRESERVE_FORCED_SUBTITLES:
                    print_and_log(f"{ext_tag()} {Fore.GREEN}FORCED subtitles will be preserved with .forced. naming (config: preserve_forced_subtitles=true){Style.RESET_ALL}")
                else:
                    print_and_log(f"{ext_tag()} {Fore.YELLOW}FORCED subtitles will be treated as regular subtitles and may be replaced (config: preserve_forced_subtitles=false){Style.RESET_ALL}")
            
            if PRESERVE_UNWANTED_SUBTITLES:
                print_and_log(f"{ext_tag()} {Fore.CYAN}Unwanted subtitle languages will be preserved (config: preserve_unwanted_subtitles=true){Style.RESET_ALL}")
            else:
                print_and_log(f"{ext_tag()} {Fore.YELLOW}Unwanted subtitle languages will be removed (config: preserve_unwanted_subtitles=false){Style.RESET_ALL}")
            
            all_vobsubs_by_lang = {}
            for t in subtitle_tracks:
                codec = t.get('codec', '').upper()
                tid = t.get('id', '?')
                lang_raw = t.get('properties', {}).get('language', 'und').lower()
                lang_norm = map_lang_3to2(lang_raw)
                forced = t.get('properties', {}).get('forced_track', False) or \
                         (t.get('properties', {}).get('flag-forced', False)) or \
                         ('forced' in (t.get('properties', {}).get('track_name', '') or '').lower())
                if any(x in codec for x in ['VOBSUB', 'VOB', 'SUP', 'PGS', 'HDMV']):
                    if lang_norm not in all_vobsubs_by_lang:
                        all_vobsubs_by_lang[lang_norm] = []
                    all_vobsubs_by_lang[lang_norm].append({'id': str(tid), 'forced': forced})
            for lang, vobsubs in all_vobsubs_by_lang.items():
                forced_ids = [v['id'] for v in vobsubs if v['forced']]
                if len(vobsubs) > 1 and forced_ids and not (PRESERVE_FORCED_SUBTITLES and (PRESERVE_UNWANTED_SUBTITLES or lang in WANTED_LANGUAGES)):
                    for tid in forced_ids:
                        if PRESERVE_FORCED_SUBTITLES and PRESERVE_UNWANTED_SUBTITLES:
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Removing FORCED VOBSUB track {tid} for language {lang.upper()} (preserve_forced_subtitles=true but language not in wanted list and preserve_unwanted_subtitles=false){Style.RESET_ALL}")
                        elif PRESERVE_FORCED_SUBTITLES and lang not in WANTED_LANGUAGES:
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Removing FORCED VOBSUB track {tid} for language {lang.upper()} (preserve_forced_subtitles=true but language not in wanted list and preserve_unwanted_subtitles=false){Style.RESET_ALL}")
                        else:
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Removing FORCED VOBSUB track {tid} for language {lang.upper()} (extra {lang.upper()}-sub with 'FORCED=TRUE' flag was found){Style.RESET_ALL}")
                        forced_vobsub_to_remove.append(str(tid))
                elif len(vobsubs) > 1 and forced_ids and PRESERVE_FORCED_SUBTITLES and (PRESERVE_UNWANTED_SUBTITLES or lang in WANTED_LANGUAGES):
                    if PRESERVE_UNWANTED_SUBTITLES:
                        print_and_log(f"{ext_tag()} {Fore.MAGENTA}Keeping FORCED VOBSUB track(s) {forced_ids} for language {lang.upper()} (preserve_forced_subtitles=true and preserve_unwanted_subtitles=true){Style.RESET_ALL}")
                    else:
                        print_and_log(f"{ext_tag()} {Fore.MAGENTA}Keeping FORCED VOBSUB track(s) {forced_ids} for language {lang.upper()} (preserve_forced_subtitles=true and language is wanted){Style.RESET_ALL}")
            if unwanted_bitmap_count > 0:
                if PRESERVE_UNWANTED_SUBTITLES:
                    print_and_log(f"{ext_tag()} {Fore.CYAN}Found {unwanted_bitmap_count} unwanted bitmap subtitle languages - Will be preserved.{Style.RESET_ALL}")
                else:
                    print_and_log(f"{ext_tag()} {Fore.YELLOW}Found {unwanted_bitmap_count} unwanted bitmap subtitle languages - Will be removed.{Style.RESET_ALL}")
            for lang in WANTED_LANGUAGES:
                if not srt_found_per_lang[lang] and vobsub_per_lang[lang]:
                    print_and_log(f"{ext_tag()} {Fore.LIGHTYELLOW_EX}No SRT found for language: {lang.upper()} — VobSub(s) present!{Style.RESET_ALL}")
                    for tid in vobsub_per_lang[lang]:
                        if str(tid[0]) not in forced_vobsub_to_remove:
                            print_and_log(f"{ext_tag()} {Fore.GREEN}VobSub backup kept: track {tid} for language {lang.upper()}{Style.RESET_ALL}")
        except Exception as e:
            print_and_log(f"{ext_tag()} {Fore.RED}Failed to parse mkvmerge JSON output: {e}{Style.RESET_ALL}")
    except Exception as e:
        print_and_log(f"{ext_tag()} {Fore.RED}Error with {shortname(file_path)}: {str(e)}{Style.RESET_ALL}")
    
    # Early exit: Skip extraction completely if all wanted subtitles already exist
    if all(has_lang.values()):
        print_and_log(f"{ext_tag()} {Fore.GREEN}All required subtitles already present. Skipping extraction.{Style.RESET_ALL}")
        # Jump directly to remux section (check if unwanted tracks need removal)
    else:
        # Only run mkvmerge -i if we need to extract subtitles
        lines = subprocess.run(['mkvmerge', '-i', str(file_path)], capture_output=True, text=True).stdout.splitlines()
        subtitle_lines = [line for line in lines if 'subtitles' in line.lower()]
        
        total_subtitles_to_extract = 0
        for line in subtitle_lines:
            if not any(codec in line for codec in ALLOWED_CODECS):
                continue
            track_id = line.split(':')[0].split()[-1]
            suffix = f".und{total_subtitles_to_extract}.srt"
            out_path = parent_dir / f"{base_name}{suffix}"
            if not out_path.exists():
                total_subtitles_to_extract += 1
        
        if total_subtitles_to_extract > 0:
            print_and_log(f"{ext_tag()} {Fore.LIGHTYELLOW_EX}Extracting {total_subtitles_to_extract} internal subtitle track(s)...{Style.RESET_ALL}")
        
        current_subtitle = 0
        for line in subtitle_lines:
            if all(has_lang.values()):
                print_and_log(f"{ext_tag()} {Fore.GREEN}Goal reached. Extraction stopped.{Style.RESET_ALL}")
                break
            if not any(codec in line for codec in ALLOWED_CODECS):
                continue
            track_id = line.split(':')[0].split()[-1]
            lang_code = 'und'
            if '(' in line and 'language' in line:
                lang_code = line.split('language ')[-1].split(')')[0].strip().lower()
            suffix = f".und{und_index}.srt"
            out_path = parent_dir / f"{base_name}{suffix}"
            if not out_path.exists():
                current_subtitle += 1
                extract_cmd = ['mkvextract', 'tracks', str(file_path), f"{track_id}:{str(out_path)}"]
                stdout, stderr = run_extraction_with_progress(extract_cmd, out_path, total_subtitles_to_extract, current_subtitle)
                print_and_log(f"{ext_tag()} {Fore.GREEN}Extracted: {shortname(out_path)}{Style.RESET_ALL}")
                extracted_files.append(str(out_path))
            detected = detect_language(out_path)
            if detected != 'unknown':
                print_and_log(f"{ext_tag()} {Fore.GREEN}Detected and recognized language: {detected.upper()}{Style.RESET_ALL}")
            if detected in WANTED_LANGUAGES and not has_lang[detected]:
                is_forced_extracted = False
                track_id_from_line = line.split(':')[0].split()[-1]
                
                for forced_sub in forced_text_subtitles:
                    if forced_sub['id'] == track_id_from_line:
                        is_forced_extracted = True
                        break
                
                if is_forced_extracted and PRESERVE_FORCED_SUBTITLES:
                    # Forced subtitle: always keep internal, never create external .forced.srt
                    try:
                        out_path.unlink()
                        deleted_files.append(str(out_path))
                    except Exception:
                        pass
                    print_and_log(f"{ext_tag()} {Fore.MAGENTA}Forced subtitle track {track_id_from_line} ({detected.upper()}) kept internal — no external SRT created{Style.RESET_ALL}")
                    subprocess.run(['mkvpropedit', str(file_path), '--edit', f'track:@{int(track_id_from_line) + 1}', '--set', f'name={detected.upper()} (Forced)'], capture_output=True)
                    print_and_log(f"{ext_tag()} {Fore.MAGENTA}Renamed internal track {track_id_from_line} to '{detected.upper()} (Forced)'{Style.RESET_ALL}")
                    # Don't set has_lang = True: acquisition still searches for a full non-forced subtitle
                    continue
                if SERIES_MODE:
                    # Check if video filename already contains the episode code
                    if sxxexx_code and sxxexx_code.lower() in base_name.lower():
                        new_path = parent_dir / f"{base_name}.{detected}.srt"
                    else:
                        # Video doesn't have SxxExx, add it before language
                        new_path = parent_dir / f"{base_name}.{sxxexx_code}.{detected}.srt"
                else:
                    lang_part = detected if detected != 'unknown' else 'UNKNOWN'
                    new_path = parent_dir / f"{base_name}.{lang_part}.srt"
                
                try:
                    out_path.rename(new_path)
                except FileExistsError:
                    print_and_log(f"{ext_tag()} {Fore.RED}ERROR: Cannot rename subtitle file - target already exists!{Style.RESET_ALL}")
                    print_and_log(f"{ext_tag()} {Fore.RED}Source: {out_path.name}{Style.RESET_ALL}")
                    print_and_log(f"{ext_tag()} {Fore.RED}Target: {new_path.name}{Style.RESET_ALL}")
                    print_and_log(f"{ext_tag()} {Fore.YELLOW}This usually happens when Subservient was interrupted previously and left incomplete files.{Style.RESET_ALL}")
                    print_and_log(f"{ext_tag()} {Fore.CYAN}SOLUTION: Please remove all .srt files that are not fully synchronized/complete and try again.{Style.RESET_ALL}")
                    print_and_log(f"{ext_tag()} {Fore.CYAN}Look for files like: *.und0.srt, *.temp.srt, or duplicate .forced.srt files{Style.RESET_ALL}")
                    print(f"\n{Fore.RED}Press Enter to exit...{Style.RESET_ALL}")
                    input()
                    sys.exit(1)
                except PermissionError as e:
                    print_and_log(f"{ext_tag()} {Fore.YELLOW}Permission error for subtitle renaming - attempting automatic fix...{Style.RESET_ALL}")
                    fixed_items = fix_permissions_proactively(out_path)
                    if fixed_items:
                        print_and_log(f"{ext_tag()} {Fore.CYAN}Fixed permissions for: {', '.join(fixed_items)}{Style.RESET_ALL}")
                        try:
                            out_path.rename(new_path)
                            print_and_log(f"{ext_tag()} {Fore.GREEN}Permission fix successful! Subtitle renamed.{Style.RESET_ALL}")
                        except Exception as retry_error:
                            print_and_log(f"{ext_tag()} {Fore.RED}PERMISSION ERROR: Cannot rename subtitle file even after permission fix!{Style.RESET_ALL}")
                            print_and_log(f"{ext_tag()} {Fore.RED}Source: {out_path.name}{Style.RESET_ALL}")
                            print_and_log(f"{ext_tag()} {Fore.RED}Target: {new_path.name}{Style.RESET_ALL}")
                            print_and_log(f"{ext_tag()} {Fore.RED}Error details: {str(retry_error)}{Style.RESET_ALL}")
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}POSSIBLE SOLUTIONS:{Style.RESET_ALL}")
                            print_and_log(f"{ext_tag()} {Fore.CYAN}1. Right-click the Subservient folder → Properties → Uncheck 'Read-only' if checked{Style.RESET_ALL}")
                            print_and_log(f"{ext_tag()} {Fore.CYAN}2. Move the entire Subservient folder to a different location (Desktop, Documents, etc.){Style.RESET_ALL}")
                            print_and_log(f"{ext_tag()} {Fore.CYAN}3. Make sure no other application is accessing the subtitle files{Style.RESET_ALL}")
                            print_and_log(f"{ext_tag()} {Fore.CYAN}4. Try running Subservient as Administrator{Style.RESET_ALL}")
                            print(f"\n{Fore.RED}Press Enter to exit...{Style.RESET_ALL}")
                            input()
                            sys.exit(1)
                    else:
                        print_and_log(f"{ext_tag()} {Fore.RED}PERMISSION ERROR: Cannot rename subtitle file!{Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.RED}Source: {out_path.name}{Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.RED}Target: {new_path.name}{Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.RED}Error details: {str(e)}{Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.YELLOW}POSSIBLE SOLUTIONS:{Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.CYAN}1. Right-click the Subservient folder → Properties → Uncheck 'Read-only' if checked{Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.CYAN}2. Move the entire Subservient folder to a different location (Desktop, Documents, etc.){Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.CYAN}3. Make sure no other application is accessing the subtitle files{Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.CYAN}4. Try running Subservient as Administrator{Style.RESET_ALL}")
                        print(f"\n{Fore.RED}Press Enter to exit...{Style.RESET_ALL}")
                        input()
                        sys.exit(1)
                if is_forced_extracted:
                    print_and_log(f"{ext_tag()} {Fore.YELLOW}Recognized as FORCED language: {detected.upper()} - treated as regular subtitle (preserve_forced_subtitles=false){Style.RESET_ALL}")
                else:
                    print_and_log(f"{ext_tag()} {Fore.GREEN}Recognized as language: {detected.upper()}{Style.RESET_ALL}")
                has_lang[detected] = True
                extracted_files.append(str(new_path))
                extracted_track_for_lang[detected] = {'track_id': track_id_from_line, 'srt_path': new_path}
            elif detected in WANTED_LANGUAGES:
                # Duplicate language — try size-based forced/non-forced detection
                existing_info = extracted_track_for_lang.get(detected)
                size_handled = False
                if existing_info and existing_info['srt_path'].exists() and out_path.exists():
                    size_existing = existing_info['srt_path'].stat().st_size
                    size_new = out_path.stat().st_size
                    if size_existing > 0 and size_new > 0:
                        min_size = min(size_existing, size_new)
                        max_size = max(size_existing, size_new)
                        confident = min_size / max_size < 0.40
                        if size_new <= size_existing:
                            # New is smaller — treat as forced candidate
                            forced_track_id = track_id_from_line
                            try:
                                out_path.unlink()
                                deleted_files.append(str(out_path))
                            except Exception:
                                pass
                        else:
                            # Existing is smaller — treat as forced candidate, new is non-forced
                            forced_track_id = existing_info['track_id']
                            nf_path = existing_info['srt_path']
                            try:
                                existing_info['srt_path'].unlink()
                                out_path.rename(nf_path)
                                extracted_track_for_lang[detected] = {'track_id': track_id_from_line, 'srt_path': nf_path}
                            except Exception as e:
                                print_and_log(f"{ext_tag()} {Fore.YELLOW}Size-based swap failed for {detected.upper()}: {e} — falling back to single-track mode{Style.RESET_ALL}")
                                forced_track_id = None
                        if forced_track_id is not None:
                            forced_track_ids_by_size[detected] = forced_track_id
                            label = "FORCED" if confident else "likely forced (best guess by size)"
                            if PRESERVE_FORCED_SUBTITLES:
                                print_and_log(f"{ext_tag()} {Fore.MAGENTA}Size-based detection: track {forced_track_id} is {label} ({detected.upper()}) — will be kept internal, non-forced extracted externally{Style.RESET_ALL}")
                                subprocess.run(['mkvpropedit', str(file_path), '--edit', f'track:@{int(forced_track_id) + 1}', '--set', f'name={detected.upper()} (Forced)'], capture_output=True)
                                print_and_log(f"{ext_tag()} {Fore.MAGENTA}Renamed internal track {forced_track_id} to '{detected.upper()} (Forced)'{Style.RESET_ALL}")
                            else:
                                print_and_log(f"{ext_tag()} {Fore.YELLOW}Size-based detection: track {forced_track_id} is {label} ({detected.upper()}) — will be removed (preserve_forced_subtitles=false){Style.RESET_ALL}")
                            size_handled = True
                if not size_handled:
                    # Sizes identical or unavailable — discard duplicate
                    try:
                        out_path.unlink()
                        deleted_files.append(str(out_path))
                    except PermissionError:
                        print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove duplicate extracted subtitle {out_path.name} (permission denied){Style.RESET_ALL}")
                    except Exception as e:
                        print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove duplicate extracted subtitle {out_path.name}: {str(e)}{Style.RESET_ALL}")
            elif detected == 'unknown':
                if not SERIES_MODE:
                    new_path = parent_dir / f"{base_name}.UNKNOWN.srt"
                    try:
                        out_path.rename(new_path)
                        print_and_log(f"{ext_tag()} {Fore.YELLOW}Language not recognized, renamed to: {shortname(new_path)}{Style.RESET_ALL}")
                        extracted_files.append(str(new_path))
                    except PermissionError:
                        print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not rename unknown subtitle {out_path.name} (permission denied){Style.RESET_ALL}")
                    except Exception as e:
                        print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not rename unknown subtitle {out_path.name}: {str(e)}{Style.RESET_ALL}")
            else:
                try:
                    out_path.unlink()
                    deleted_files.append(str(out_path))
                except PermissionError:
                    print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove unwanted extracted subtitle {out_path.name} (permission denied){Style.RESET_ALL}")
                except Exception as e:
                    print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove unwanted extracted subtitle {out_path.name}: {str(e)}{Style.RESET_ALL}")
            und_index += 1
    
    # Continue with remux section (this runs regardless of whether extraction was skipped)
    did_remux = False
    info_cmd_json = ['mkvmerge', '-J', str(file_path)]
    result_json = subprocess.run(info_cmd_json, capture_output=True, text=True)
    audio_tracks = []
    unwanted_audio_tracks = []
    subtitle_tracks = []
    unwanted_subtitle_tracks = []
    forced_subtitle_track_ids = set()
    if PRESERVE_FORCED_SUBTITLES:
        for forced_sub in forced_text_subtitles:
            forced_subtitle_track_ids.add(forced_sub['id'])
        for lang, forced_ids in vobsub_forced_per_lang.items():
            forced_subtitle_track_ids.update(str(tid) for tid in forced_ids)
        if forced_subtitle_track_ids:
            print_and_log(f"{ext_tag()} {Fore.CYAN}FORCED subtitle preservation enabled - protecting track IDs: {', '.join(sorted(forced_subtitle_track_ids))}{Style.RESET_ALL}")
    
    for tid in forced_vobsub_to_remove:
        if tid not in unwanted_subtitle_tracks:
            unwanted_subtitle_tracks.append(tid)
    mkv_audio_langs_3 = set()
    mkv_audio_track_langs = {}
    if result_json.returncode == 0:
        try:
            mkv_info = json.loads(result_json.stdout)
            for track in mkv_info.get('tracks', []):
                track_id = str(track.get('id', '?'))
                track_type = track.get('type', '?')
                lang_code = track.get('properties', {}).get('language', 'und').lower()
                lang_code_3 = to_iso639_2(lang_code)
                codec = track.get('codec', '').lower()
                if track_type == 'audio':
                    mkv_audio_langs_3.add(lang_code_3)
                    mkv_audio_track_langs[track_id] = lang_code_3
                    log(f"[DEBUG] Stored MKV audio track: id={track_id}, original='{lang_code}', iso3='{lang_code_3}'")
            log(f"[DEBUG] All MKV audio 3-letter codes: {sorted(mkv_audio_langs_3)}")
        except Exception as e:
            print_and_log(f"{ext_tag()} {Fore.RED}Failed to parse mkvmerge JSON output for audio track storing: {e}{Style.RESET_ALL}")
    
    if AUDIO_TRACK_LANGUAGES == 'ALL':
        print_and_log(f"{ext_tag()} {Fore.YELLOW}Audio track processing disabled - keeping all audio tracks{Style.RESET_ALL}")
        if result_json.returncode == 0:
            try:
                mkv_info = json.loads(result_json.stdout)
                for track in mkv_info.get('tracks', []):
                    if track.get('type') == 'audio':
                        audio_tracks.append(str(track.get('id', '?')))
            except Exception:
                pass
    elif AUDIO_TRACK_LANGUAGES is None:
        print_and_log(f"{ext_tag()} {Fore.YELLOW}Audio track languages not configured - keeping all audio tracks{Style.RESET_ALL}")
        if result_json.returncode == 0:
            try:
                mkv_info = json.loads(result_json.stdout)
                for track in mkv_info.get('tracks', []):
                    if track.get('type') == 'audio':
                        audio_tracks.append(str(track.get('id', '?')))
            except Exception:
                pass
    else:
        config_audio_langs_3 = set()
        for lang in AUDIO_TRACK_LANGUAGES:
            lang3 = to_iso639_2(lang)
            log(f"[DEBUG] Config audio language '{lang}' converted to 3-letter '{lang3}'")
            config_audio_langs_3.add(lang3)
        log(f"[DEBUG] All config audio 3-letter codes: {sorted(config_audio_langs_3)}")
    
        primary_audio_track = None
        if mkv_audio_track_langs:
            primary_audio_track = min(mkv_audio_track_langs.keys(), key=int)
            log(f"[DEBUG] Primary audio track identified: {primary_audio_track}")
    
        filename_upper = file_path.name.upper()
        multi_lang_indicators = [
            'LICDOM', 'ITA', 'ENG', 'FRA', 'GER', 'SPA', 'MULTI', 'DUT', 'NLD', 'NL', 'DUTCH',
            'RUS', 'RUSSIAN', 'POR', 'PT', 'PORTUGUESE', 'CHI', 'CHN', 'CHINESE', 'MANDARIN', 
            'CANTONESE', 'JPN', 'JAP', 'JAPANESE', 'KOR', 'KOREAN', 'POL', 'POLISH', 'CZE', 
            'CZECH', 'HUN', 'HUNGARIAN', 'SWE', 'SWEDISH', 'NOR', 'NORWEGIAN', 'DAN', 'DANISH',
            'TUR', 'TURKISH', 'HEB', 'HEBREW', 'ARA', 'ARABIC', 'HIN', 'HINDI', 'TAM', 'TAMIL',
            'THA', 'THAI', 'VIE', 'VIETNAMESE', 'UKR', 'UKRAINIAN', 'BUL', 'BULGARIAN', 'ROM',
            'ROMANIAN', 'GRE', 'GREEK', 'SER', 'SERBIAN', 'CRO', 'CROATIAN', 'DUAL', 'DUALAUDIO', 'AC3'
        ]
        is_multi_lang_release = any(indicator in filename_upper for indicator in multi_lang_indicators)
        if is_multi_lang_release:
            log(f"[DEBUG] Multi-language release detected in filename: {file_path.name}")
            log(f"[DEBUG] Primary track protection will be DISABLED for unwanted languages")

        # When all audio tracks are 'und', try to infer their languages from the filename.
        # Scene releases often encode audio languages in dot-separated order before 'sub':
        #   e.g. "Movie.ita.eng.sub.ita.Group.avi"  →  track 1 = ita, track 2 = eng
        all_und = mkv_audio_track_langs and all(lang == 'und' for lang in mkv_audio_track_langs.values())
        if all_und:
            _FILENAME_LANG_TOKENS = {
                'ita': 'ita', 'it': 'ita',
                'eng': 'eng', 'en': 'eng',
                'fra': 'fra', 'fre': 'fra', 'fr': 'fra',
                'ger': 'deu', 'deu': 'deu', 'de': 'deu',
                'spa': 'spa', 'es': 'spa',
                'dut': 'nld', 'nld': 'nld', 'nl': 'nld',
                'por': 'por', 'pt': 'por',
                'jpn': 'jpn', 'jap': 'jpn', 'ja': 'jpn',
                'kor': 'kor', 'ko': 'kor',
                'chi': 'zho', 'chn': 'zho', 'zho': 'zho', 'zh': 'zho',
                'rus': 'rus', 'ru': 'rus',
                'pol': 'pol', 'pl': 'pol',
                'tur': 'tur', 'tr': 'tur',
                'swe': 'swe', 'sv': 'swe',
                'nor': 'nor', 'nb': 'nor',
                'dan': 'dan', 'da': 'dan',
                'fin': 'fin', 'fi': 'fin',
                'hun': 'hun', 'hu': 'hun',
                'cze': 'ces', 'ces': 'ces', 'cs': 'ces',
                'rum': 'ron', 'ron': 'ron', 'ro': 'ron',
                'hrv': 'hrv', 'cro': 'hrv', 'hr': 'hrv',
                'srp': 'srp', 'ser': 'srp', 'sr': 'srp',
                'bul': 'bul', 'bg': 'bul',
                'ukr': 'ukr', 'uk': 'ukr',
                'heb': 'heb', 'he': 'heb',
                'ara': 'ara', 'ar': 'ara',
                'hin': 'hin', 'hi': 'hin',
                'tha': 'tha', 'th': 'tha',
                'vie': 'vie', 'vi': 'vie',
                'gre': 'ell', 'ell': 'ell', 'el': 'ell',
            }
            _SUB_MARKERS = {'sub', 'subs', 'dub', 'dubbed'}
            stem_parts = file_path.stem.lower().split('.')
            audio_parts = []
            for _p in stem_parts:
                if _p in _SUB_MARKERS:
                    break
                audio_parts.append(_p)
            inferred_langs = [_FILENAME_LANG_TOKENS[_p] for _p in audio_parts if _p in _FILENAME_LANG_TOKENS]
            track_ids_sorted = sorted(mkv_audio_track_langs.keys(), key=int)
            if inferred_langs and len(inferred_langs) == len(track_ids_sorted):
                log(f"[DEBUG] All audio tracks untagged — inferring languages from filename: {inferred_langs}")
                print_and_log(f"{ext_tag()} {Fore.CYAN}All audio tracks untagged — inferring languages from filename: {', '.join(inferred_langs)}{Style.RESET_ALL}")
                for _tid, _lang in zip(track_ids_sorted, inferred_langs):
                    mkv_audio_track_langs[_tid] = _lang
                mkv_audio_langs_3 = set(mkv_audio_track_langs.values())
            else:
                log(f"[DEBUG] Cannot infer audio languages from filename: {len(inferred_langs)} token(s) found vs {len(track_ids_sorted)} track(s)")

        for track_id, lang_code_3 in mkv_audio_track_langs.items():
            log(f"[DEBUG] Comparing MKV track id={track_id} lang='{lang_code_3}' to config set {config_audio_langs_3}")
            if lang_code_3 == 'und':
                print_and_log(f"{ext_tag()} {Fore.GREEN}Keeping audio track {track_id} (lang: und/undefined){Style.RESET_ALL}")
                audio_tracks.append(track_id)
            elif lang_in_list(lang_code_3, config_audio_langs_3):
                print_and_log(f"{ext_tag()} {Fore.GREEN}Keeping audio track {track_id} (lang: {lang_code_3}){Style.RESET_ALL}")
                audio_tracks.append(track_id)
            elif track_id == primary_audio_track and not is_multi_lang_release:
                print_and_log(f"{ext_tag()} {Fore.YELLOW}Keeping primary audio track {track_id} (lang: {lang_code_3}) - Main track protection{Style.RESET_ALL}")
                audio_tracks.append(track_id)
            else:
                if track_id == primary_audio_track and is_multi_lang_release:
                    print_and_log(f"{ext_tag()} {Fore.RED}Marking primary audio track {track_id} (lang: {lang_code_3}) for removal - Multi-lang release detected{Style.RESET_ALL}")
                else:
                    print_and_log(f"{ext_tag()} {Fore.RED}Marking audio track {track_id} (lang: {lang_code_3}) for removal{Style.RESET_ALL}")
                unwanted_audio_tracks.append(track_id)
    
    missing_langs = config_audio_langs_3 - mkv_audio_langs_3 if AUDIO_TRACK_LANGUAGES not in ('ALL', None) else set()
    if result_json.returncode == 0:
        try:
            mkv_info = json.loads(result_json.stdout)
            vobsub_backup_tracks = set()
            vobsub_per_lang = {lang: [] for lang in WANTED_LANGUAGES}
            lang_fallback_info = {}  # lang -> {'track_id': str, 'is_forced': bool}
            srt_found_per_lang = {lang: (parent_dir / f"{base_name}.{lang}.srt").exists() or 
                                         (parent_dir / f"{base_name}.{lang}.forced.srt").exists() 
                                  for lang in WANTED_LANGUAGES}
            for track in mkv_info.get('tracks', []):
                track_id = str(track.get('id', '?'))
                track_type = track.get('type', '?')
                lang_code = track.get('properties', {}).get('language', 'und').lower()
                lang = map_lang_3to2(lang_code)
                codec = track.get('codec', '').lower()
                if track_type == 'subtitles' and lang in WANTED_LANGUAGES and ('vobsub' in codec or 'sub/vobsub' in codec or 'sup' in codec or 'vob' in codec or 'pgs' in codec or 'hdmv' in codec):
                    vobsub_per_lang[lang].append(track_id)
            for lang in WANTED_LANGUAGES:
                if not srt_found_per_lang[lang] and vobsub_per_lang[lang]:
                    vobsub_backup_tracks.update(vobsub_per_lang[lang])
            for track in mkv_info.get('tracks', []):
                track_id = str(track.get('id', '?'))
                track_type = track.get('type', '?')
                lang_code = track.get('properties', {}).get('language', 'und').lower()
                lang = map_lang_3to2(lang_code)
                codec = track.get('codec', '').lower()
                srt_exists = (parent_dir / f"{base_name}.{lang}.srt").exists()
                
                if track_type == 'subtitles':
                    is_forced_to_preserve = (PRESERVE_FORCED_SUBTITLES and track_id in forced_subtitle_track_ids)
                    
                    if lang in WANTED_LANGUAGES:
                        if 'vobsub' in codec or 'sub/vobsub' in codec or 'sup' in codec or 'vob' in codec or 'pgs' in codec or 'hdmv' in codec:
                            if srt_exists and not is_forced_to_preserve:
                                unwanted_subtitle_tracks.append(track_id)
                            else:
                                subtitle_tracks.append(track_id)
                                if is_forced_to_preserve:
                                    print_and_log(f"{ext_tag()} {Fore.MAGENTA}Preserving FORCED VobSub track {track_id} (lang: {lang}){Style.RESET_ALL}")
                        else:
                            if is_forced_to_preserve:
                                subtitle_tracks.append(track_id)
                                print_and_log(f"{ext_tag()} {Fore.MAGENTA}Preserving FORCED text subtitle track {track_id} (lang: {lang}){Style.RESET_ALL}")
                            elif not srt_exists:
                                track_is_forced = (
                                    track.get('properties', {}).get('forced_track', False) or
                                    track.get('properties', {}).get('flag-forced', False) or
                                    ('forced' in (track.get('properties', {}).get('track_name', '') or '').lower())
                                )
                                if lang not in lang_fallback_info:
                                    subtitle_tracks.append(track_id)
                                    lang_fallback_info[lang] = {'track_id': track_id, 'is_forced': track_is_forced}
                                    print_and_log(f"{ext_tag()} {Fore.GREEN}Keeping internal text subtitle track {track_id} (lang: {lang.upper()}, forced={track_is_forced}) — no external SRT present{Style.RESET_ALL}")
                                else:
                                    existing = lang_fallback_info[lang]
                                    if existing['is_forced'] and not track_is_forced:
                                        # Swap: replace forced with non-forced (prefer full subtitle)
                                        subtitle_tracks.remove(existing['track_id'])
                                        unwanted_subtitle_tracks.append(existing['track_id'])
                                        subtitle_tracks.append(track_id)
                                        lang_fallback_info[lang] = {'track_id': track_id, 'is_forced': False}
                                        print_and_log(f"{ext_tag()} {Fore.GREEN}Replacing forced track {existing['track_id']} with non-forced track {track_id} (lang: {lang.upper()}) — preferring full subtitle{Style.RESET_ALL}")
                                    elif not existing['is_forced'] and track_is_forced:
                                        # Already have a non-forced track, drop the forced duplicate
                                        unwanted_subtitle_tracks.append(track_id)
                                        print_and_log(f"{ext_tag()} {Fore.YELLOW}Removing forced duplicate text subtitle track {track_id} (lang: {lang.upper()}) — non-forced track already kept{Style.RESET_ALL}")
                                    else:
                                        # Both same forced status — try size-based detection
                                        # Extract both temporarily and compare file sizes
                                        tmp_a = existing['track_id']
                                        tmp_b = track_id
                                        out_a = extracted_track_for_lang.get(lang, {}).get('srt_path')
                                        # out_a is already extracted (if MKV extraction pass ran); for non-MKV it won't exist yet
                                        if out_a and out_a.exists():
                                            # Extract the new (second) track temporarily
                                            tmp_out = parent_dir / f"{base_name}.sizecheck_tmp.srt"
                                            try:
                                                tmp_extract_cmd = ['mkvextract', 'tracks', str(file_path), f"{tmp_b}:{str(tmp_out)}"]
                                                subprocess.run(tmp_extract_cmd, capture_output=True)
                                            except Exception:
                                                pass
                                            size_handled_remux = False
                                            if tmp_out.exists():
                                                size_a = out_a.stat().st_size
                                                size_b = tmp_out.stat().st_size
                                                try:
                                                    tmp_out.unlink()
                                                except Exception:
                                                    pass
                                                if size_a > 0 and size_b > 0:
                                                    min_s = min(size_a, size_b)
                                                    max_s = max(size_a, size_b)
                                                    if min_s / max_s < 0.40:
                                                        # Can determine forced
                                                        if size_b <= size_a:
                                                            # track_b (current) is forced
                                                            forced_tid = tmp_b
                                                            nonforcced_tid = tmp_a
                                                        else:
                                                            # track_a (existing) is forced
                                                            forced_tid = tmp_a
                                                            nonforcced_tid = tmp_b
                                                        forced_track_ids_by_size[lang] = forced_tid
                                                        if PRESERVE_FORCED_SUBTITLES:
                                                            # Keep forced internal, exclude non-forced (srt_exists covers it)
                                                            subtitle_tracks.append(forced_tid)
                                                            # Remove non-forced if it was added
                                                            if nonforcced_tid in subtitle_tracks:
                                                                subtitle_tracks.remove(nonforcced_tid)
                                                            unwanted_subtitle_tracks.append(nonforcced_tid)
                                                            print_and_log(f"{ext_tag()} {Fore.MAGENTA}Size-based detection: track {forced_tid} is FORCED ({lang.upper()}) — kept internal, track {nonforcced_tid} removed (external SRT is non-forced){Style.RESET_ALL}")
                                                        else:
                                                            # Both removed; forced doesn't need to stay
                                                            unwanted_subtitle_tracks.append(forced_tid)
                                                            if nonforcced_tid in subtitle_tracks:
                                                                subtitle_tracks.remove(nonforcced_tid)
                                                            unwanted_subtitle_tracks.append(nonforcced_tid)
                                                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Size-based detection: track {forced_tid} identified as FORCED ({lang.upper()}) — both internal tracks removed, external SRT (non-forced) retained{Style.RESET_ALL}")
                                                        size_handled_remux = True
                                            if not size_handled_remux:
                                                subtitle_tracks.append(track_id)
                                                print_and_log(f"{ext_tag()} {Fore.CYAN}Keeping additional text subtitle track {track_id} (lang: {lang.upper()}) — cannot determine which is forced{Style.RESET_ALL}")
                                        else:
                                            # No extracted SRT available for comparison (non-MKV pre-remux)
                                            subtitle_tracks.append(track_id)
                                            print_and_log(f"{ext_tag()} {Fore.CYAN}Keeping additional text subtitle track {track_id} (lang: {lang.upper()}) — cannot determine which is forced{Style.RESET_ALL}")
                            else:
                                # srt_exists=True: track is normally excluded from remux output
                                # Exception: if size-detection identified this as the forced track and we want to preserve it
                                if (PRESERVE_FORCED_SUBTITLES
                                        and lang in forced_track_ids_by_size
                                        and track_id == forced_track_ids_by_size[lang]):
                                    subtitle_tracks.append(track_id)
                                    print_and_log(f"{ext_tag()} {Fore.MAGENTA}Size-detected FORCED track {track_id} (lang: {lang.upper()}) kept internal — external SRT is non-forced{Style.RESET_ALL}")
                    else:
                        if track_id in forced_subtitle_track_ids:
                            if PRESERVE_FORCED_SUBTITLES and (PRESERVE_UNWANTED_SUBTITLES or lang in WANTED_LANGUAGES):
                                subtitle_tracks.append(track_id)
                                if PRESERVE_UNWANTED_SUBTITLES:
                                    print_and_log(f"{ext_tag()} {Fore.MAGENTA}Preserving FORCED subtitle track {track_id} (lang: {lang}) - preserve_forced_subtitles=true and preserve_unwanted_subtitles=true{Style.RESET_ALL}")
                                else:
                                    print_and_log(f"{ext_tag()} {Fore.MAGENTA}Preserving FORCED subtitle track {track_id} (lang: {lang}) - preserve_forced_subtitles=true and language is wanted{Style.RESET_ALL}")
                            else:
                                unwanted_subtitle_tracks.append(track_id)
                                if PRESERVE_FORCED_SUBTITLES and lang not in WANTED_LANGUAGES:
                                    print_and_log(f"{ext_tag()} {Fore.YELLOW}Removing FORCED subtitle track {track_id} (lang: {lang}) - preserve_forced_subtitles=true but language not in wanted list and preserve_unwanted_subtitles=false{Style.RESET_ALL}")
                                else:
                                    print_and_log(f"{ext_tag()} {Fore.YELLOW}Removing FORCED subtitle track {track_id} (unwanted lang: {lang}) - preserve_forced_subtitles=false{Style.RESET_ALL}")
                        else:
                            if PRESERVE_UNWANTED_SUBTITLES:
                                subtitle_tracks.append(track_id)
                                print_and_log(f"{ext_tag()} {Fore.CYAN}Preserving unwanted subtitle track {track_id} (lang: {lang}) - preserve_unwanted_subtitles=true{Style.RESET_ALL}")
                            elif lang == 'und' and original_suffix != '.mkv' and any(c.lower() in codec or codec in c.lower() for c in ALLOWED_CODECS):
                                # Undefined language text track in non-MKV: keep it through remux so the
                                # post-remux pass can extract it and run language detection. It may turn
                                # out to be English or Dutch.
                                subtitle_tracks.append(track_id)
                                print_and_log(f"{ext_tag()} {Fore.CYAN}Keeping undefined-language text subtitle track {track_id} in non-MKV file — will extract and detect language after remux{Style.RESET_ALL}")
                            else:
                                unwanted_subtitle_tracks.append(track_id)
            for tid in vobsub_backup_tracks:
                if tid not in subtitle_tracks:
                    subtitle_tracks.append(tid)
        except Exception as e:
            print_and_log(f"{ext_tag()} {Fore.RED}Failed to parse mkvmerge JSON output for subtitle track storing: {e}{Style.RESET_ALL}")
    subtitle_tracks = [tid for tid in subtitle_tracks if tid not in unwanted_subtitle_tracks]
    log(f"[DEBUG] Subtitle tracks kept (final): {subtitle_tracks}")
    log(f"[DEBUG] Subtitle tracks removed: {unwanted_subtitle_tracks}")
    if result_json.returncode == 0 and not PRESERVE_UNWANTED_SUBTITLES:
        try:
            mkv_info = json.loads(result_json.stdout)
            for lang in WANTED_LANGUAGES:
                srt_path = parent_dir / f"{base_name}.{lang}.srt"
                if srt_path.exists():
                    for track in mkv_info.get('tracks', []):
                        if track.get('type') == 'subtitles':
                            track_lang = map_lang_3to2(track.get('properties', {}).get('language', 'und').lower())
                            if track_lang == lang:
                                tid = str(track.get('id', '?'))
                                is_forced_to_preserve = (PRESERVE_FORCED_SUBTITLES and tid in forced_subtitle_track_ids and lang in WANTED_LANGUAGES)
                                if not is_forced_to_preserve and tid not in unwanted_subtitle_tracks:
                                    unwanted_subtitle_tracks.append(tid)
                                    print_and_log(f"{ext_tag()} {Fore.LIGHTYELLOW_EX}Both an internal and external {lang.upper()} subtitle detected — removing the spare internal ({lang.upper()}) subtitle{Style.RESET_ALL}")
                                    log(f"[DEBUG] Marking internal subtitle track {tid} for language {lang} for removal (external SRT exists)")
                                elif is_forced_to_preserve:
                                    print_and_log(f"{ext_tag()} {Fore.MAGENTA}Keeping FORCED internal subtitle track {tid} despite external {lang.upper()} SRT{Style.RESET_ALL}")
        except Exception as e:
            print_and_log(f"{ext_tag()} {Fore.RED}Failed to check for external SRTs before remux: {e}{Style.RESET_ALL}")
    elif PRESERVE_UNWANTED_SUBTITLES:
        print_and_log(f"{ext_tag()} {Fore.CYAN}Skipping internal/external subtitle duplicate removal - preserve_unwanted_subtitles=true{Style.RESET_ALL}")
    subtitle_tracks = [tid for tid in subtitle_tracks if tid not in unwanted_subtitle_tracks]
    log(f"[DEBUG] Subtitle tracks kept (final): {subtitle_tracks}")
    log(f"[DEBUG] Subtitle tracks removed: {unwanted_subtitle_tracks}")
    # Non-MKV files (MP4/AVI) with subtitle tracks need remux to MKV even if no tracks are
    # unwanted — mkvmerge auto-converts TIMED_TEXT → SubRip/SRT during remux, after which
    # the post-remux extraction pass can extract them with mkvextract.
    needs_conversion_remux = (original_suffix != '.mkv' and not all(has_lang.values()) and bool(subtitle_tracks))
    if needs_conversion_remux and not unwanted_audio_tracks and not unwanted_subtitle_tracks:
        print_and_log(f"{ext_tag()} {Fore.CYAN}Non-MKV file with internal subtitle tracks — remuxing to MKV for subtitle conversion...{Style.RESET_ALL}")
    if unwanted_audio_tracks or unwanted_subtitle_tracks or needs_conversion_remux:
        temp_path = parent_dir / (base_name + ".temp.mkv")
        # mkvmerge always outputs MKV; for non-mkv inputs the final file gets .mkv extension
        final_path = file_path if file_path.suffix.lower() == '.mkv' else file_path.with_suffix('.mkv')
        
        fixed_items = fix_permissions_proactively(file_path)
        if fixed_items:
            print_and_log(f"{ext_tag()} {Fore.CYAN}Fixed permissions for: {', '.join(fixed_items)}{Style.RESET_ALL}")
        
        mkvmerge_cmd = ['mkvmerge', '-o', str(temp_path)]
        if audio_tracks:
            mkvmerge_cmd += ['--audio-tracks', ','.join(audio_tracks)]
        else:
            mkvmerge_cmd += ['--no-audio']
        if subtitle_tracks:
            mkvmerge_cmd += ['--subtitle-tracks', ','.join(subtitle_tracks)]
        else:
            mkvmerge_cmd += ['--no-subtitles']
        mkvmerge_cmd += [str(file_path)]
        log(f"[DEBUG] mkvmerge command: {' '.join(mkvmerge_cmd)}")
        log(f"[DEBUG] Audio tracks kept: {audio_tracks}")
        log(f"[DEBUG] Subtitle tracks kept: {subtitle_tracks}")
        if original_suffix != '.mkv':
            print_and_log(f"{ext_tag()} {Fore.LIGHTYELLOW_EX}{file_path.suffix.upper().lstrip('.')} detected — converting to MKV to enable subtitle extraction.{Style.RESET_ALL}")
        print_and_log(f"{Fore.LIGHTYELLOW_EX}{ext_tag()} Remuxing to remove unwanted audio/subtitle tracks...{Style.RESET_ALL}")
        orig_size = file_path.stat().st_size
        percent = [0]
        stop_flag = [False]
        def progress_thread():
            while temp_path.exists() and temp_path.stat().st_size < orig_size and not stop_flag[0]:
                try:
                    done = temp_path.stat().st_size
                    p = min(int((done / orig_size) * 100), 100)
                    if p != percent[0]:
                        percent[0] = p
                        print(f"{Fore.WHITE}Remux progress: {p}%{Style.RESET_ALL}".ljust(79), end='\r', flush=True)
                except Exception:
                    pass
                time.sleep(0.25)
                print(' ' * 80, end='\r', flush=True)

        t = threading.Thread(target=progress_thread)
        t.start()
        stdout, stderr = run_remux_with_progress(mkvmerge_cmd, temp_path, orig_size)
        stop_flag[0] = True
        t.join()
        for line in (stdout + '\n' + stderr).splitlines():
            if 'Multiplexing took' in line:
                print_and_log(line)
            elif line.strip():
                log(line)
        if temp_path.exists():
            try:
                file_path.unlink()
                temp_path.rename(final_path)
                file_path = final_path
                did_remux = True
                print_and_log(f"{ext_tag()} {Fore.GREEN}Remuxed to remove unwanted internal subtitles and audio tracks: {file_path.name}{Style.RESET_ALL}")
            except PermissionError as e:
                print_and_log(f"{ext_tag()} {Fore.YELLOW}Permission error detected - attempting automatic fix...{Style.RESET_ALL}")
                fixed_items = fix_permissions_proactively(file_path)
                if fixed_items:
                    print_and_log(f"{ext_tag()} {Fore.CYAN}Fixed permissions for: {', '.join(fixed_items)}{Style.RESET_ALL}")
                    try:
                        file_path.unlink()
                        temp_path.rename(final_path)
                        file_path = final_path
                        did_remux = True
                        print_and_log(f"{ext_tag()} {Fore.GREEN}Permission fix successful! Remuxed to remove unwanted internal subtitles and audio tracks: {file_path.name}{Style.RESET_ALL}")
                    except Exception as retry_error:
                        print_and_log(f"{ext_tag()} {Fore.RED}PERMISSION ERROR: Cannot complete remux operation even after permission fix!{Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.RED}Error details: {str(retry_error)}{Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.YELLOW}POSSIBLE SOLUTIONS:{Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.CYAN}1. Make sure the video file is not open in any media player or application{Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.CYAN}2. Right-click the Subservient folder → Properties → Uncheck 'Read-only' if checked{Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.CYAN}3. Move the entire Subservient folder to a different location (Desktop, Documents, etc.){Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.CYAN}4. If moved: Place subordinate.py back in Subservient folder and run initial setup again{Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.CYAN}5. Try restarting your computer and running Subservient again{Style.RESET_ALL}")
                        print_and_log(f"\n{ext_tag()} {Fore.YELLOW}The temp file '{temp_path.name}' contains your processed video.{Style.RESET_ALL}")
                        print_and_log(f"{ext_tag()} {Fore.YELLOW}You can manually rename it to replace the original if needed.{Style.RESET_ALL}")
                        print(f"\n{Fore.RED}Press Enter to exit...{Style.RESET_ALL}")
                        input()
                        sys.exit(1)
                else:
                    print_and_log(f"{ext_tag()} {Fore.RED}PERMISSION ERROR: Cannot complete remux operation!{Style.RESET_ALL}")
                    print_and_log(f"{ext_tag()} {Fore.RED}Error details: {str(e)}{Style.RESET_ALL}")
                    print_and_log(f"{ext_tag()} {Fore.YELLOW}POSSIBLE SOLUTIONS:{Style.RESET_ALL}")
                    print_and_log(f"{ext_tag()} {Fore.CYAN}1. Make sure the video file is not open in any media player or application{Style.RESET_ALL}")
                    print_and_log(f"{ext_tag()} {Fore.CYAN}2. Right-click the Subservient folder → Properties → Uncheck 'Read-only' if checked{Style.RESET_ALL}")
                    print_and_log(f"{ext_tag()} {Fore.CYAN}3. Move the entire Subservient folder to a different location (Desktop, Documents, etc.){Style.RESET_ALL}")
                    print_and_log(f"{ext_tag()} {Fore.CYAN}4. If moved: Place subordinate.py back in Subservient folder and run initial setup again{Style.RESET_ALL}")
                    print_and_log(f"{ext_tag()} {Fore.CYAN}5. Try restarting your computer and running Subservient again{Style.RESET_ALL}")
                    print_and_log(f"\n{ext_tag()} {Fore.YELLOW}The temp file '{temp_path.name}' contains your processed video.{Style.RESET_ALL}")
                    print_and_log(f"{ext_tag()} {Fore.YELLOW}You can manually rename it to replace the original if needed.{Style.RESET_ALL}")
                    print(f"\n{Fore.RED}Press Enter to exit...{Style.RESET_ALL}")
                    input()
                    sys.exit(1)
            except Exception as e:
                print_and_log(f"{ext_tag()} {Fore.RED}Unexpected error during remux: {str(e)}{Style.RESET_ALL}")
                if temp_path.exists():
                    print_and_log(f"{ext_tag()} {Fore.YELLOW}The temp file '{temp_path.name}' contains your processed video.{Style.RESET_ALL}")
                print(f"\n{Fore.RED}Press Enter to exit...{Style.RESET_ALL}")
                input()
                sys.exit(1)
            finally:
                # Always try to clean up temp file if operation completed successfully
                if 'temp_path' in locals() and temp_path.exists():
                    # Check if the original file still exists, indicating remux failed
                    if not file_path.exists():
                        # Original was removed, temp should become the new file - don't clean up
                        pass
                    else:
                        # Original still exists, something went wrong, clean up temp
                        try:
                            temp_path.unlink()
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Cleaned up temporary remux file after error{Style.RESET_ALL}")
                        except Exception as cleanup_error:
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not clean up temp file: {str(cleanup_error)}{Style.RESET_ALL}")
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}You may need to manually remove: {temp_path.name}{Style.RESET_ALL}")
        else:
            print_and_log(f"{ext_tag()} {Fore.RED}Remux failed, temp.mkv not found.{Style.RESET_ALL}")
    else:
        print_and_log(f"{Fore.WHITE}{ext_tag()} No unwanted internal subtitles or audio tracks — {Fore.GREEN}remux skipped{Style.RESET_ALL}")

    # Post-remux extraction pass: non-MKV files (MP4/AVI) could not be extracted by mkvextract
    # on the first pass. After remux to MKV, TIMED_TEXT tracks are auto-converted to SubRip/SRT
    # by mkvmerge and are now extractable.
    post_remux_tracks_to_strip = []  # track IDs that turned out unwanted after language detection
    unwanted_track_for_lang = {}  # lang -> {'track_id': str, 'srt_path': Path} for first-occurrence unwanted tracks (temp, for size comparison)
    if did_remux and not all(has_lang.values()) and original_suffix != '.mkv':
        print_and_log(f"{ext_tag()} {Fore.CYAN}Post-remux: scanning converted MKV for newly extractable subtitle tracks...{Style.RESET_ALL}")
        pr_lines = subprocess.run(['mkvmerge', '-i', str(file_path)], capture_output=True, text=True).stdout.splitlines()
        pr_subtitle_lines = [line for line in pr_lines if 'subtitles' in line.lower()]

        pr_total = sum(
            1 for line in pr_subtitle_lines
            if any(codec in line for codec in ALLOWED_CODECS)
        )
        if pr_total > 0:
            print_and_log(f"{ext_tag()} {Fore.LIGHTYELLOW_EX}Extracting {pr_total} subtitle track(s) from converted MKV...{Style.RESET_ALL}")

        pr_current = 0
        goal_logged = False
        for line in pr_subtitle_lines:
            if all(has_lang.values()) and not goal_logged:
                print_and_log(f"{ext_tag()} {Fore.GREEN}Goal reached — continuing to check remaining tracks for duplicate/forced detection.{Style.RESET_ALL}")
                goal_logged = True
            if not any(codec in line for codec in ALLOWED_CODECS):
                continue
            track_id = line.split(':')[0].split()[-1]
            suffix = f".und{und_index}.srt"
            out_path = parent_dir / f"{base_name}{suffix}"
            if not out_path.exists():
                pr_current += 1
                extract_cmd = ['mkvextract', 'tracks', str(file_path), f"{track_id}:{str(out_path)}"]
                run_extraction_with_progress(extract_cmd, out_path, pr_total, pr_current)
                if out_path.exists():
                    print_and_log(f"{ext_tag()} {Fore.GREEN}Extracted: {shortname(out_path)}{Style.RESET_ALL}")
                else:
                    und_index += 1
                    continue
            detected = detect_language(out_path)
            if detected != 'unknown':
                print_and_log(f"{ext_tag()} {Fore.GREEN}Detected and recognized language: {detected.upper()}{Style.RESET_ALL}")
            if detected in WANTED_LANGUAGES and not has_lang[detected]:
                is_forced_extracted = any(fs['id'] == track_id for fs in forced_text_subtitles)
                if is_forced_extracted and PRESERVE_FORCED_SUBTITLES:
                    # Forced subtitle: always keep internal, never create external .forced.srt
                    try:
                        out_path.unlink()
                        deleted_files.append(str(out_path))
                    except Exception:
                        pass
                    print_and_log(f"{ext_tag()} {Fore.MAGENTA}Forced subtitle track {track_id} ({detected.upper()}) kept internal — no external SRT created{Style.RESET_ALL}")
                    subprocess.run(['mkvpropedit', str(file_path), '--edit', f'track:@{int(track_id) + 1}', '--set', f'name={detected.upper()} (Forced)'], capture_output=True)
                    print_and_log(f"{ext_tag()} {Fore.MAGENTA}Renamed internal track {track_id} to '{detected.upper()} (Forced)'{Style.RESET_ALL}")
                    # Don't set has_lang = True
                    und_index += 1
                    continue
                if SERIES_MODE:
                    if sxxexx_code and sxxexx_code.lower() in base_name.lower():
                        new_path = parent_dir / f"{base_name}.{detected}.srt"
                    else:
                        new_path = parent_dir / f"{base_name}.{sxxexx_code}.{detected}.srt"
                else:
                    new_path = parent_dir / f"{base_name}.{detected}.srt"
                try:
                    out_path.rename(new_path)
                except Exception as e:
                    print_and_log(f"{ext_tag()} {Fore.RED}Could not rename post-remux subtitle {out_path.name} → {new_path.name}: {e}{Style.RESET_ALL}")
                    post_remux_tracks_to_strip.append(track_id)
                    und_index += 1
                    continue
                if is_forced_extracted:
                    print_and_log(f"{ext_tag()} {Fore.YELLOW}Recognized as FORCED language: {detected.upper()} - treated as regular subtitle (preserve_forced_subtitles=false){Style.RESET_ALL}")
                else:
                    print_and_log(f"{ext_tag()} {Fore.GREEN}Recognized as language: {detected.upper()}{Style.RESET_ALL}")
                # External SRT created — strip the internal track
                post_remux_tracks_to_strip.append(track_id)
                has_lang[detected] = True
                extracted_files.append(str(new_path))
                extracted_track_for_lang[detected] = {'track_id': track_id, 'srt_path': new_path}
            elif detected in WANTED_LANGUAGES:
                # Duplicate language — try size-based forced/non-forced detection
                existing_info = extracted_track_for_lang.get(detected)
                size_handled = False
                if existing_info and existing_info['srt_path'].exists() and out_path.exists():
                    size_existing = existing_info['srt_path'].stat().st_size
                    size_new = out_path.stat().st_size
                    if size_existing > 0 and size_new > 0:
                        min_size = min(size_existing, size_new)
                        max_size = max(size_existing, size_new)
                        confident = min_size / max_size < 0.40
                        if size_new <= size_existing:
                            # New (out_path) is smaller — treat as forced candidate
                            forced_track_id = track_id
                            try:
                                out_path.unlink()
                                deleted_files.append(str(out_path))
                            except Exception:
                                pass
                        else:
                            # Existing is smaller — treat as forced candidate, new is non-forced
                            forced_track_id = existing_info['track_id']
                            nf_path = existing_info['srt_path']
                            try:
                                existing_info['srt_path'].unlink()
                                out_path.rename(nf_path)
                                extracted_track_for_lang[detected] = {'track_id': track_id, 'srt_path': nf_path}
                            except Exception as e:
                                print_and_log(f"{ext_tag()} {Fore.YELLOW}Size-based swap failed for {detected.upper()}: {e}{Style.RESET_ALL}")
                                forced_track_id = None
                        if forced_track_id is not None:
                            forced_track_ids_by_size[detected] = forced_track_id
                            label = "FORCED" if confident else "likely forced (best guess by size)"
                            if PRESERVE_FORCED_SUBTITLES:
                                if forced_track_id in post_remux_tracks_to_strip:
                                    post_remux_tracks_to_strip.remove(forced_track_id)
                                print_and_log(f"{ext_tag()} {Fore.MAGENTA}Size-based detection: track {forced_track_id} is {label} ({detected.upper()}) — kept internal, non-forced extracted externally{Style.RESET_ALL}")
                                subprocess.run(['mkvpropedit', str(file_path), '--edit', f'track:@{int(forced_track_id) + 1}', '--set', f'name={detected.upper()} (Forced)'], capture_output=True)
                                print_and_log(f"{ext_tag()} {Fore.MAGENTA}Renamed internal track {forced_track_id} to '{detected.upper()} (Forced)'{Style.RESET_ALL}")
                            else:
                                if forced_track_id not in post_remux_tracks_to_strip:
                                    post_remux_tracks_to_strip.append(forced_track_id)
                                print_and_log(f"{ext_tag()} {Fore.YELLOW}Size-based detection: track {forced_track_id} is {label} ({detected.upper()}) — will be removed (preserve_forced_subtitles=false){Style.RESET_ALL}")
                            size_handled = True
                if not size_handled:
                    # Sizes identical or unavailable — keep internal track, discard duplicate external SRT
                    try:
                        out_path.unlink()
                        deleted_files.append(str(out_path))
                    except Exception:
                        pass
                    print_and_log(f"{ext_tag()} {Fore.CYAN}Internal track {track_id} ({detected.upper()}) kept — external duplicate SRT discarded (sizes identical){Style.RESET_ALL}")
            else:
                # Unwanted or undetectable language
                if PRESERVE_UNWANTED_SUBTITLES and detected != 'unknown':
                    prev_unwanted = unwanted_track_for_lang.get(detected)
                    if prev_unwanted is not None:
                        # Duplicate unwanted language — size-based forced/non-forced detection
                        size_handled = False
                        if prev_unwanted['srt_path'].exists() and out_path.exists():
                            size_prev = prev_unwanted['srt_path'].stat().st_size
                            size_new = out_path.stat().st_size
                            if size_prev > 0 and size_new > 0:
                                min_size = min(size_prev, size_new)
                                max_size = max(size_prev, size_new)
                                confident = min_size / max_size < 0.40
                                forced_track_id = track_id if size_new <= size_prev else prev_unwanted['track_id']
                                label = "FORCED" if confident else "likely forced (best guess by size)"
                                for p in [out_path, prev_unwanted['srt_path']]:
                                    try:
                                        if p.exists():
                                            p.unlink()
                                            deleted_files.append(str(p))
                                    except Exception:
                                        pass
                                if PRESERVE_FORCED_SUBTITLES:
                                    if forced_track_id in post_remux_tracks_to_strip:
                                        post_remux_tracks_to_strip.remove(forced_track_id)
                                    print_and_log(f"{ext_tag()} {Fore.MAGENTA}Size-based detection: track {forced_track_id} is {label} ({detected.upper()}) — kept internal (preserve_unwanted + preserve_forced=true){Style.RESET_ALL}")
                                    subprocess.run(['mkvpropedit', str(file_path), '--edit', f'track:@{int(forced_track_id) + 1}', '--set', f'name={detected.upper()} (Forced)'], capture_output=True)
                                    print_and_log(f"{ext_tag()} {Fore.MAGENTA}Renamed internal track {forced_track_id} to '{detected.upper()} (Forced)'{Style.RESET_ALL}")
                                else:
                                    if forced_track_id not in post_remux_tracks_to_strip:
                                        post_remux_tracks_to_strip.append(forced_track_id)
                                    print_and_log(f"{ext_tag()} {Fore.YELLOW}Size-based detection: track {forced_track_id} is {label} ({detected.upper()}) — forced removed (preserve_forced_subtitles=false){Style.RESET_ALL}")
                                size_handled = True
                        if not size_handled:
                            for p in [out_path, prev_unwanted['srt_path']]:
                                try:
                                    if p.exists():
                                        p.unlink()
                                        deleted_files.append(str(p))
                                except Exception:
                                    pass
                            print_and_log(f"{ext_tag()} {Fore.CYAN}Duplicate unwanted {detected.upper()} tracks — both kept internal (sizes unavailable){Style.RESET_ALL}")
                    else:
                        # First occurrence — keep SRT temporarily for potential duplicate size comparison
                        unwanted_track_for_lang[detected] = {'track_id': track_id, 'srt_path': out_path}
                        print_and_log(f"{ext_tag()} {Fore.CYAN}Keeping internal track {track_id} ({detected.upper()}) — preserve_unwanted_subtitles=true{Style.RESET_ALL}")
                elif PRESERVE_UNWANTED_SUBTITLES:
                    # Unknown language — keep internal, delete temp SRT
                    try:
                        out_path.unlink()
                        deleted_files.append(str(out_path))
                    except Exception:
                        pass
                    print_and_log(f"{ext_tag()} {Fore.CYAN}Keeping internal track {track_id} (unknown) — preserve_unwanted_subtitles=true{Style.RESET_ALL}")
                else:
                    # preserve_unwanted=false — strip internal track from MKV
                    post_remux_tracks_to_strip.append(track_id)
                    try:
                        out_path.unlink()
                        deleted_files.append(str(out_path))
                    except Exception:
                        pass
            und_index += 1

        # Clean up any first-occurrence unwanted SRTs that had no duplicate to compare with
        for lang, info in unwanted_track_for_lang.items():
            try:
                if info['srt_path'].exists():
                    info['srt_path'].unlink()
                    deleted_files.append(str(info['srt_path']))
            except Exception:
                pass

    # Cleanup remux: strip any internal tracks that turned out to be unwanted after detection
    if post_remux_tracks_to_strip:
        print_and_log(f"{ext_tag()} {Fore.LIGHTYELLOW_EX}Cleanup remux: removing {len(post_remux_tracks_to_strip)} unwanted internal subtitle track(s) from MKV...{Style.RESET_ALL}")
        try:
            pr_info = json.loads(subprocess.run(['mkvmerge', '-J', str(file_path)], capture_output=True, text=True).stdout)
            all_track_ids = [str(t.get('id')) for t in pr_info.get('tracks', [])]
            keep_tracks = [tid for tid in all_track_ids if tid not in post_remux_tracks_to_strip]
            sub_keep = [tid for tid in keep_tracks if any(
                t.get('type') == 'subtitles' and str(t.get('id')) == tid
                for t in pr_info.get('tracks', [])
            )]
            audio_keep = [tid for tid in keep_tracks if any(
                t.get('type') == 'audio' and str(t.get('id')) == tid
                for t in pr_info.get('tracks', [])
            )]
            cleanup_temp = parent_dir / (base_name + ".temp.mkv")
            cleanup_cmd = ['mkvmerge', '-o', str(cleanup_temp)]
            if audio_keep:
                cleanup_cmd += ['--audio-tracks', ','.join(audio_keep)]
            else:
                cleanup_cmd += ['--no-audio']
            if sub_keep:
                cleanup_cmd += ['--subtitle-tracks', ','.join(sub_keep)]
            else:
                cleanup_cmd += ['--no-subtitles']
            cleanup_cmd += [str(file_path)]
            orig_size = file_path.stat().st_size
            run_remux_with_progress(cleanup_cmd, cleanup_temp, orig_size)
            if cleanup_temp.exists():
                file_path.unlink()
                cleanup_temp.rename(file_path)
                print_and_log(f"{ext_tag()} {Fore.GREEN}Cleanup remux complete: unwanted tracks removed from MKV{Style.RESET_ALL}")
            else:
                print_and_log(f"{ext_tag()} {Fore.RED}Cleanup remux failed: temp file not found{Style.RESET_ALL}")
        except Exception as e:
            print_and_log(f"{ext_tag()} {Fore.RED}Cleanup remux error: {e}{Style.RESET_ALL}")

    if not all(has_lang.values()):
        status = f"{file_path.name}: "
    for lang in WANTED_LANGUAGES:
        correct_sub = parent_dir / f"{base_name}.{lang}.srt"
        if correct_sub.exists():
            for ext in ('.srt', '.ass', '.ssa'):
                for sub in parent_dir.glob(f"{base_name}.*{ext}"):
                    if sub.resolve() == correct_sub.resolve():
                        continue
                    parts = sub.stem.split('.')
                    sub_lang = None
                    if len(parts) > 1:
                        sub_lang = parts[-1].lower()
                    if sub_lang == lang:
                        try:
                            sub.unlink()
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Cleanup: removed duplicate subtitle for {lang}: {sub.name}{Style.RESET_ALL}")
                            deleted_files.append(str(sub))
                        except PermissionError:
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove duplicate subtitle {sub.name} (permission denied){Style.RESET_ALL}")
                        except Exception as e:
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove duplicate subtitle {sub.name}: {str(e)}{Style.RESET_ALL}")
    protected_subs = set()
    for lang in WANTED_LANGUAGES:
        protected_subs.add(str(parent_dir / f"{base_name}.{lang}.srt"))
        if PRESERVE_FORCED_SUBTITLES:
            protected_subs.add(str(parent_dir / f"{base_name}.{lang}.forced.srt"))
    if SERIES_MODE and sxxexx_code:
        for lang in WANTED_LANGUAGES:
            # Check if video filename already contains the episode code
            if sxxexx_code.lower() in base_name.lower():
                # Video already has SxxExx in name, subtitle uses standard naming
                protected_subs.add(str(parent_dir / f"{base_name}.{lang}.srt"))
                if PRESERVE_FORCED_SUBTITLES:
                    protected_subs.add(str(parent_dir / f"{base_name}.{lang}.forced.srt"))
            else:
                # Video doesn't have SxxExx, subtitle has SxxExx before language
                protected_subs.add(str(parent_dir / f"{base_name}.{sxxexx_code}.{lang}.srt"))
                if PRESERVE_FORCED_SUBTITLES:
                    protected_subs.add(str(parent_dir / f"{base_name}.{sxxexx_code}.{lang}.forced.srt"))

    for lang in WANTED_LANGUAGES:
        correct_sub = parent_dir / f"{base_name}.{lang}.srt"
        if correct_sub.exists():
            for ext in ('.srt', '.ass', '.ssa'):
                for sub in parent_dir.glob(f"{base_name}.*{ext}"):
                    parts = sub.stem.split('.')
                    sub_lang = None
                    if len(parts) > 1:
                        sub_lang = parts[-1].lower()
                    if sub_lang == lang and str(sub.resolve()) != str(correct_sub.resolve()) and str(sub.resolve()) not in protected_subs:
                        try:
                            sub.unlink()
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Cleanup: removed duplicate subtitle for {lang}: {sub.name}{Style.RESET_ALL}")
                            deleted_files.append(str(sub))
                        except PermissionError:
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove duplicate subtitle {sub.name} (permission denied){Style.RESET_ALL}")
                        except Exception as e:
                            print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove duplicate subtitle {sub.name}: {str(e)}{Style.RESET_ALL}")

    if all(has_lang.values()):
        for ext in ('.srt', '.ass', '.ssa'):
            for sub in parent_dir.glob(f"{base_name}.*{ext}"):
                parts = sub.stem.split('.')
                lang = None
                if len(parts) > 1:
                    lang = parts[-1].lower()
                if not (lang in WANTED_LANGUAGES and sub.suffix == '.srt') and str(sub.resolve()) not in protected_subs:
                    try:
                        sub.unlink()
                        print_and_log(f"{ext_tag()} {Fore.YELLOW}Cleanup: removed redundant subtitle: {sub.name}{Style.RESET_ALL}")
                        deleted_files.append(str(sub))
                    except PermissionError:
                        print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove redundant subtitle {sub.name} (permission denied){Style.RESET_ALL}")
                    except Exception as e:
                        print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove redundant subtitle {sub.name}: {str(e)}{Style.RESET_ALL}")

    cleanup_unwanted_files(file_path)

    if not PRESERVE_UNWANTED_SUBTITLES:
        for ext in ('.srt', '.ass', '.ssa'):
            for sub in parent_dir.glob(f"{base_name}.*{ext}"):
                parts = sub.stem.split('.')
                lang = None
                if len(parts) > 1:
                    lang = parts[-1].lower()
                if lang and lang not in WANTED_LANGUAGES and lang != 'unknown' and str(sub.resolve()) not in protected_subs:
                    try:
                        sub.unlink()
                        print_and_log(f"{ext_tag()} {Fore.YELLOW}Removed external subtitle not in wanted languages: {sub.name}{Style.RESET_ALL}")
                        deleted_files.append(str(sub))
                    except PermissionError:
                        print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove unwanted subtitle {sub.name} (permission denied){Style.RESET_ALL}")
                    except Exception as e:
                        print_and_log(f"{ext_tag()} {Fore.YELLOW}Warning: Could not remove unwanted subtitle {sub.name}: {str(e)}{Style.RESET_ALL}")
    else:
        print_and_log(f"{ext_tag()} {Fore.CYAN}Preserving all external subtitles (preserve_unwanted_subtitles=true){Style.RESET_ALL}")
    if extracted_files:
        print_and_log(f"{ext_tag()} {Fore.GREEN}Extracted files:{Style.RESET_ALL}")
        for ef in extracted_files:
            print_and_log(f"  {ef}")
    if deleted_files:
        print_and_log(f"{ext_tag()} {Fore.RED}Deleted files:{Style.RESET_ALL}")
        for df in deleted_files:
            print_and_log(f"  {df}")
    if movie_idx < total_movies:
        clear_and_print_ascii(BANNER_LINE)
    global missing_subs_list
    missing_langs = [lang for lang, present in has_lang.items() if not present]
    if missing_langs:
        entry = f"{file_path.name}: {','.join(missing_langs)}"
        missing_subs_list.append(entry)
def to_iso639_2(code):
    """Convert language code to ISO 639-2 format, using preferred codes for consistency."""
    code = (code or '').lower()
    
    from utils import LANG_3TO2_MAP, LANG_2TO3_PREFERRED
    if len(code) == 2 and code in LANG_2TO3_PREFERRED:
        return LANG_2TO3_PREFERRED[code]
    
    if code in LANG_3TO2_MAP:
        return code
    
    try:
        lang = pycountry.languages.get(alpha_2=code)
        if lang and hasattr(lang, 'alpha_3'):
            return lang.alpha_3.lower()
    except (KeyError, AttributeError):
        pass
    try:
        lang = pycountry.languages.get(alpha_3=code)
        if lang and hasattr(lang, 'alpha_3'):
            return lang.alpha_3.lower()
    except (KeyError, AttributeError):
        pass
    return code
def get_video_files_for_folder(folder: Path) -> list:
    """Get all video files in folder while respecting skip_dirs configuration."""
    video_files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in ['.mkv', '.mp4', '.avi']]
    if SERIES_MODE:
        return sorted(video_files)
    if not video_files:
        return []
    largest = max(video_files, key=lambda f: f.stat().st_size)
    extras = [f for f in video_files if f != largest]
    if extras:
        if DELETE_EXTRA_VIDEOS:
            for f in extras:
                try:
                    f.unlink()
                    print_and_log(f"{ext_tag()} {Fore.YELLOW}Deleted extra video: {f.name}{Style.RESET_ALL}")
                except Exception as e:
                    print_and_log(f"{ext_tag()} {Fore.RED}Failed to delete {f.name}: {e}{Style.RESET_ALL}")
        else:
            extras_folder = folder / EXTRAS_FOLDER_NAME
            try:
                extras_folder.mkdir(exist_ok=True)
            except Exception as e:
                print_and_log(f"{ext_tag()} {Fore.RED}Failed to create extras folder '{EXTRAS_FOLDER_NAME}': {e}{Style.RESET_ALL}")
                return [largest]
            for f in extras:
                try:
                    dest = extras_folder / f.name
                    f.rename(dest)
                    print_and_log(f"{ext_tag()} {Fore.YELLOW}Moved extra video to '{EXTRAS_FOLDER_NAME}': {f.name}{Style.RESET_ALL}")
                except Exception as e:
                    print_and_log(f"{ext_tag()} {Fore.RED}Failed to move {f.name}: {e}{Style.RESET_ALL}")
    return [largest]
def get_subservient_anchor():
    """Get the Subservient anchor directory from pathfiles config."""
    config_dir = Path(user_config_dir()) / "Subservient"
    pathfile = config_dir / "Subservient_pathfiles"
    if not pathfile.exists():
        print_and_log(f"\033[1;31m[ERROR]\033[0m Subservient_pathfiles not found in your user config directory. Please run subordinate.py first.")
        try:
            input("\nPress any key to exit...")
        except EOFError:
            os.system("pause")
        sys.exit(1)
    with open(pathfile, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("subservient_anchor="):
                return Path(line.split("=", 1)[1].strip())
    print_and_log(f"\033[1;31m[ERROR]\033[0m subservient_anchor not found in Subservient_pathfiles. Please run subordinate.py again.")
    try:
        input("\nPress any key to exit...")
    except EOFError:
        os.system("pause")
    sys.exit(1)
anchor_dir = get_subservient_anchor()
os.chdir(anchor_dir)
__file__ = str((anchor_dir / Path(__file__).name).resolve())

def process_directory(root_path):
    """Process all video files in directory and extract their internal subtitles."""
    anchor_videos = get_video_files_for_folder(root_path)
    if anchor_videos:
        total_movies = len(anchor_videos)
        idx = 1
        for video_file in anchor_videos:
            extract_subtitles(video_file, idx, total_movies)
            idx += 1
    else:
        all_folders = []
        skip_dirs = get_skip_dirs_from_config()
        
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d.lower() not in skip_dirs]
            folder = Path(dirpath)
            video_files = get_video_files_for_folder(folder)
            if video_files:
                all_folders.append((folder, video_files))
        total_movies = sum(len(v) for _, v in all_folders) or 1
        idx = 1
        for folder, video_files in all_folders:
            for video_file in video_files:
                extract_subtitles(video_file, idx, total_movies)
                idx += 1
    if missing_subs_list:
        print_and_log(f"\n{ext_tag()} {Fore.YELLOW}Summary: The following files are missing required subtitles:{Style.RESET_ALL}")
        for entry in missing_subs_list:
            if ':' in entry:
                filename, langs = entry.rsplit(':', 1)
            else:
                filename, langs = entry, ''
            match = re.search(r"^(.*?\(\d{4}\))", filename)
            if match:
                trimmed_name = match.group(1)
            else:
                trimmed_name = filename.strip()
            lang_codes = [l.strip().upper() for l in re.split(r'[ ,]+', langs) if l.strip()]
            if lang_codes:
                langs_formatted = ''.join([f"[{Fore.LIGHTYELLOW_EX}{code}{Style.RESET_ALL}]" for code in lang_codes])
                print_and_log(f"  {trimmed_name} {langs_formatted}")
            else:
                print_and_log(f"  {trimmed_name}")
        print_and_log(f"\n{ext_tag()} {Fore.GREEN}*{Style.RESET_ALL} Opening acquisition.py in {int(PAUSE_SECONDS)} seconds...")
        time.sleep(PAUSE_SECONDS)
        acq_script_path = SNAPSHOT_DIR / "acquisition.py"
        if acq_script_path.exists():
            os.system(f'python "{acq_script_path}"')
            print_and_log(f"{ext_tag()} {Fore.GREEN}*{Style.RESET_ALL} extraction.py will now close.")
        else:
            print_and_log(f"{ext_tag()} {Fore.RED}acquisition.py not found in {SNAPSHOT_DIR}{Style.RESET_ALL}")
        exit(0)
    else:
        print_and_log(f"{ext_tag()} {Fore.GREEN}All files have all required subtitles (SRT).{Style.RESET_ALL}")
        print_and_log(f"\n{ext_tag()} {Fore.GREEN}*{Style.RESET_ALL} Opening acquisition.py in {int(PAUSE_SECONDS)} seconds...")
        time.sleep(PAUSE_SECONDS)
        acq_script_path = SNAPSHOT_DIR / "acquisition.py"
        if acq_script_path.exists():
            os.system(f'python "{acq_script_path}"')
            print_and_log(f"{ext_tag()} {Fore.GREEN}*{Style.RESET_ALL} extraction.py will now close.")
        else:
            print_and_log(f"{ext_tag()} {Fore.RED}acquisition.py not found in {SNAPSHOT_DIR}{Style.RESET_ALL}")
        exit(0)
current_folder = Path(".").resolve()
log(f"{ext_tag()} {Fore.CYAN}Start scanning: {current_folder}{Style.RESET_ALL}")

# Resync mode: move existing subtitles to backup folder
if RESYNC_MODE:
    log(f"\n{ext_tag()} {Fore.YELLOW}{Style.BRIGHT}╔═══════════════════════════════════════════════════════════════╗{Style.RESET_ALL}")
    log(f"{ext_tag()} {Fore.YELLOW}{Style.BRIGHT}║  RESYNC MODE ACTIVE - Moving existing subtitles to backup   ║{Style.RESET_ALL}")
    log(f"{ext_tag()} {Fore.YELLOW}{Style.BRIGHT}╚═══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}\n")
    
    moved_count = 0
    for root, dirs, files in os.walk(current_folder):
        # Skip moved_subtitles folders and other skip_dirs
        dirs[:] = [d for d in dirs if d.lower() not in ['moved_subtitles'] + [s.strip().lower() for s in get_skip_dirs_from_config()]]
        
        # Check if this directory contains video files
        video_files = [f for f in files if f.lower().endswith(('.mkv', '.mp4', '.avi', '.m4v'))]
        if not video_files:
            continue
        
        # Move all subtitle files to moved_subtitles folder
        subtitle_files = [f for f in files if f.lower().endswith(('.srt', '.ass'))]
        if subtitle_files:
            moved_folder = Path(root) / "moved_subtitles"
            moved_folder.mkdir(exist_ok=True)
            
            for sub_file in subtitle_files:
                try:
                    src = Path(root) / sub_file
                    dst = moved_folder / sub_file
                    # If file exists in destination, add timestamp
                    if dst.exists():
                        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                        name, ext = os.path.splitext(sub_file)
                        dst = moved_folder / f"{name}.backup_{timestamp}{ext}"
                    
                    shutil.move(str(src), str(dst))
                    moved_count += 1
                    log(f"{ext_tag()} {Fore.YELLOW}→ Moved: {sub_file} → moved_subtitles/{dst.name}{Style.RESET_ALL}")
                except Exception as e:
                    log(f"{ext_tag()} {Fore.RED}Failed to move {sub_file}: {str(e)}{Style.RESET_ALL}")
    
    if moved_count > 0:
        log(f"\n{ext_tag()} {Fore.GREEN}Resync mode: {moved_count} subtitle file(s) backed up to 'moved_subtitles' folders{Style.RESET_ALL}")
        log(f"{ext_tag()} {Fore.CYAN}Proceeding with fresh subtitle extraction and synchronization...{Style.RESET_ALL}\n")
    else:
        log(f"\n{ext_tag()} {Fore.YELLOW}Resync mode: No existing subtitle files found to move{Style.RESET_ALL}\n")

missing_subs_list = []
missing_file_log = LOGS_DIR / "subtitle_missing_tracks.txt"
MOVIES_WITH_LINEAR_OFFSET_FILE = SNAPSHOT_DIR / 'movies_with_linear_offset.txt'

process_directory(current_folder)
