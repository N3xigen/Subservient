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
                elif l.startswith('pause_seconds') and '=' in line:
                    _, value = line.split('=', 1)
                    try:
                        PAUSE_SECONDS = float(value.strip())
                    except Exception:
                        pass
    if run_counter_line_idx is not None and RUN_COUNTER is not None:
        RUN_COUNTER += 1
        lines[run_counter_line_idx] = f"run_counter= {RUN_COUNTER}"
        try:
            CONFIG_PATH.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        except PermissionError:
            fixed_items = fix_permissions_proactively(CONFIG_PATH)
            if fixed_items:
                try:
                    CONFIG_PATH.write_text('\n'.join(lines) + '\n', encoding='utf-8')
                    print(f"Info: Fixed permissions and updated run counter in config file")
                except Exception:
                    print(f"Warning: Could not update run counter in config file (permission denied)")
            else:
                print(f"Warning: Could not update run counter in config file (permission denied)")
        except Exception as e:
            print(f"Warning: Could not update run counter in config file: {str(e)}")
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
ALLOWED_CODECS = ["SubRip/SRT", "S_TEXT/UTF8", "SubStationAlpha", "S_TEXT/ASS", "SSA", "ASS"]
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
    if file_path.stat().st_size < 50 * 1024 * 1024:
        print_and_log(f"{ext_tag()} {Fore.YELLOW}Skipped (file too small < 50MB): {shortname(file_path)}{Style.RESET_ALL}")
        return
    
    fixed_items = fix_permissions_proactively(file_path)
    
    print_movie_header(file_path.stem, movie_idx, total_movies)
    print_and_log(f"{ext_tag()} {Fore.CYAN}Scanning: {shortname(file_path)}{Style.RESET_ALL}")
    und_index = 0
    base_name = file_path.stem
    parent_dir = file_path.parent
    base_path = parent_dir / base_name
    has_lang = {lang: (parent_dir / f"{base_name}.{lang}.srt").exists() for lang in WANTED_LANGUAGES}
    sxxexx_code = extract_sxxexx_code(file_path.name) if SERIES_MODE else None

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
            srt_found_per_lang = {lang: (parent_dir / f"{base_name}.{lang}.srt").exists() or 
                                         (PRESERVE_FORCED_SUBTITLES and (parent_dir / f"{base_name}.{lang}.forced.srt").exists()) 
                                  for lang in WANTED_LANGUAGES}
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
                elif any(x in codec for x in ['VOBSUB', 'VOB', 'SUP']):
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
                if any(x in codec for x in ['VOBSUB', 'VOB', 'SUP']):
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
            
            if SERIES_MODE:
                if is_forced_extracted and PRESERVE_FORCED_SUBTITLES:
                    new_path = parent_dir / f"{base_name}.{detected}.forced.{sxxexx_code}.srt"
                else:
                    new_path = parent_dir / f"{base_name}.{detected}.{sxxexx_code}.srt"
            else:
                if is_forced_extracted and PRESERVE_FORCED_SUBTITLES:
                    new_path = parent_dir / f"{base_name}.{detected}.forced.srt"
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
                if PRESERVE_FORCED_SUBTITLES:
                    print_and_log(f"{ext_tag()} {Fore.MAGENTA}Recognized as FORCED language: {detected.upper()} - preserved with .forced. naming{Style.RESET_ALL}")
                else:
                    print_and_log(f"{ext_tag()} {Fore.YELLOW}Recognized as FORCED language: {detected.upper()} - treated as regular subtitle (preserve_forced_subtitles=false){Style.RESET_ALL}")
            else:
                print_and_log(f"{ext_tag()} {Fore.GREEN}Recognized as language: {detected.upper()}{Style.RESET_ALL}")
            has_lang[detected] = True
            extracted_files.append(str(new_path))
        elif detected in WANTED_LANGUAGES:
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
            srt_found_per_lang = {lang: (parent_dir / f"{base_name}.{lang}.srt").exists() or 
                                         (parent_dir / f"{base_name}.{lang}.forced.srt").exists() 
                                  for lang in WANTED_LANGUAGES}
            for track in mkv_info.get('tracks', []):
                track_id = str(track.get('id', '?'))
                track_type = track.get('type', '?')
                lang_code = track.get('properties', {}).get('language', 'und').lower()
                lang = map_lang_3to2(lang_code)
                codec = track.get('codec', '').lower()
                if track_type == 'subtitles' and lang in WANTED_LANGUAGES and ('vobsub' in codec or 'sub/vobsub' in codec or 'sup' in codec or 'vob' in codec):
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
                        if 'vobsub' in codec or 'sub/vobsub' in codec or 'sup' in codec or 'vob' in codec:
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
    if unwanted_audio_tracks or unwanted_subtitle_tracks:
        temp_path = parent_dir / (base_name + ".temp.mkv")
        
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
                temp_path.rename(file_path)
                print_and_log(f"{ext_tag()} {Fore.GREEN}Remuxed to remove unwanted internal subtitles and audio tracks: {file_path.name}{Style.RESET_ALL}")
            except PermissionError as e:
                print_and_log(f"{ext_tag()} {Fore.YELLOW}Permission error detected - attempting automatic fix...{Style.RESET_ALL}")
                fixed_items = fix_permissions_proactively(file_path)
                if fixed_items:
                    print_and_log(f"{ext_tag()} {Fore.CYAN}Fixed permissions for: {', '.join(fixed_items)}{Style.RESET_ALL}")
                    try:
                        file_path.unlink()
                        temp_path.rename(file_path)
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
                print_and_log(f"{ext_tag()} {Fore.YELLOW}The temp file '{temp_path.name}' contains your processed video.{Style.RESET_ALL}")
                print(f"\n{Fore.RED}Press Enter to exit...{Style.RESET_ALL}")
                input()
                sys.exit(1)
        else:
            print_and_log(f"{ext_tag()} {Fore.RED}Remux failed, temp.mkv not found.{Style.RESET_ALL}")
    else:
        print_and_log(f"{Fore.WHITE}{ext_tag()} No unwanted internal subtitles or audio tracks — {Fore.GREEN}remux skipped{Style.RESET_ALL}")
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
            protected_subs.add(str(parent_dir / f"{base_name}.{lang}.{sxxexx_code}.srt"))
            if PRESERVE_FORCED_SUBTITLES:
                protected_subs.add(str(parent_dir / f"{base_name}.{lang}.forced.{sxxexx_code}.srt"))

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
    video_files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in ['.mkv', '.mp4']]
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
missing_subs_list = []
missing_file_log = LOGS_DIR / "subtitle_missing_tracks.txt"
MOVIES_WITH_LINEAR_OFFSET_FILE = SNAPSHOT_DIR / 'movies_with_linear_offset.txt'

process_directory(current_folder)
