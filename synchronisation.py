import os, re, subprocess, tempfile, shutil, time, sys, stat, datetime, threading
from concurrent.futures import ThreadPoolExecutor

def is_running_in_docker():
    """Check if running inside a Docker container."""
    try:
        if os.path.exists('/.dockerenv'):
            return True
        with open('/proc/1/cgroup', 'r') as f:
            return 'docker' in f.read()
    except:
        return False

def calculate_subtitle_offset(original_path, synchronized_path):
    """Calculate time offset between original and synchronized subtitle files."""
    try:
        def parse_srt_first_timestamp(file_path):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            for line in lines:
                if '-->' in line:
                    start_time = line.split('-->')[0].strip()
                    time_parts = start_time.split(':')
                    if len(time_parts) == 3:
                        hours = int(time_parts[0])
                        minutes = int(time_parts[1])
                        seconds_ms = time_parts[2].split(',')
                        seconds = int(seconds_ms[0])
                        milliseconds = int(seconds_ms[1]) if len(seconds_ms) > 1 else 0
                        total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
                        return total_seconds
            return 0.0
        if not os.path.exists(original_path) or not os.path.exists(synchronized_path):
            return 0.0
        
        original_time = parse_srt_first_timestamp(original_path)
        synchronized_time = parse_srt_first_timestamp(synchronized_path)
        offset = abs(original_time - synchronized_time)
        return offset
    except Exception as e:
        print_and_log(f"{sync_tag()} {Fore.YELLOW}Warning: Could not calculate subtitle offset: {str(e)}{Style.RESET_ALL}", log_only=True)
        return 0.0

def synchronize_subtitle_with_ffsubsync(video_path, subtitle_path, output_path):
    """Synchronize subtitle file with video using ffsubsync and return success status with offset."""
    try:
        if not os.path.exists(video_path):
            print_and_log(f"{sync_tag()} {Fore.RED}Video file not found: {video_path}{Style.RESET_ALL}")
            return False, 0.0
        if not os.path.exists(subtitle_path):
            print_and_log(f"{sync_tag()} {Fore.RED}Subtitle file not found: {subtitle_path}{Style.RESET_ALL}")
            return False, 0.0
        print_and_log(f"{sync_tag()} {Fore.CYAN}Synchronizing {os.path.basename(subtitle_path)} with video...{Style.RESET_ALL}")
        cmd = [
            'ffsubsync', video_path, 
            '-i', subtitle_path, 
            '-o', output_path,
        ]
        try:
            result = subprocess.run(cmd, timeout=600)
            if result.returncode == 0 and os.path.exists(output_path):
                offset_seconds = calculate_subtitle_offset(subtitle_path, output_path)
                print_and_log(f"{sync_tag()} {Fore.GREEN}Synchronization successful! Offset: {offset_seconds:.3f}s{Style.RESET_ALL}")
                return True, offset_seconds
            else:
                print_and_log(f"{sync_tag()} {Fore.RED}FFSubSync failed with return code {result.returncode}{Style.RESET_ALL}")
                return False, 0.0
        except Exception as proc_error:
            print_and_log(f"{sync_tag()} {Fore.RED}Process error during synchronization: {str(proc_error)}{Style.RESET_ALL}")
            return False, 0.0
    except subprocess.TimeoutExpired:
        print_and_log(f"{sync_tag()} {Fore.RED}FFSubSync timed out after 10 minutes{Style.RESET_ALL}")
        return False, 0.0
    except Exception as e:
        print_and_log(f"{sync_tag()} {Fore.RED}Error during synchronization: {str(e)}{Style.RESET_ALL}")
        return False, 0.0

def check_required_packages():
    """Check if all required packages are installed and show install instructions if missing."""
    required_packages = ["colorama", "platformdirs", "langdetect"]
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    if missing:
        print("\n" + "="*60)
        print("  SUBSERVIENT SYNCHRONISATION - PACKAGE REQUIREMENTS ERROR")
        print("="*60)
        print("\nThe following required packages are missing:")
        for pkg in missing:
            print(f"  - {pkg}")
        print(f"\nTo resolve this issue:")
        print(f"  1. Navigate to your main Subservient folder")
        print(f"  2. Run subordinate.py so that it automatically installs the required packages.")
        print(f"  3. If 2 is not happening, choose option '4' to install & verify requirements")
        print(f"  4. After installation, try running synchronisation.py again")
        print(f"\nIf you don't have subordinate.py, please download the complete")
        print(f"Subservient package from the official source.")
        print("\n" + "="*60)
        input("Press Enter to exit...")
        sys.exit(1)

check_required_packages()

from langdetect import detect
from colorama import init, Fore, Style
from collections import defaultdict
from platformdirs import user_config_dir
from pathlib import Path
from utils import (ASCII_ART, clear_and_print_ascii, map_lang_3to2, 
                   trim_movie_name, scan_subtitle_coverage, display_coverage_results, 
                   get_skip_dirs_from_config)

init(autoreset=True)

BANNER_LINE = f"                   {Style.BRIGHT}{Fore.RED}[Phase 4/4]{Style.RESET_ALL} Subtitle Synchronisation"
script_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(script_dir, '.config')
ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m|\033\[[0-9;]*m')

run_counter = 1
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, encoding='utf-8') as f:
        run_counter = next((int(line.split('=', 1)[1].strip()) for line in f 
                           if line.strip().lower().startswith('run_counter') and '=' in line), 1)

LOGS_DIR = os.path.join(script_dir, 'logs', f'Subservient-run-{run_counter}')
os.makedirs(LOGS_DIR, exist_ok=True)

existing_log = next((os.path.join(LOGS_DIR, f) for f in os.listdir(LOGS_DIR) 
                    if f.startswith('synchronisation_log') and f.endswith('.txt')), None)

if existing_log:
    LOG_FILE = existing_log
    with open(LOG_FILE, 'r+', encoding='utf-8') as f:
        content = f.read()
        part_count = content.count('Synchronisation - part') + 1
        f.seek(0, 2)
        if f.tell() > 0:
            f.write('\n')
        f.write(f'Synchronisation - part {part_count}\n')
else:
    log_time = datetime.datetime.now().strftime('%d-%m-%Y_%H.%M.%S')
    LOG_FILE = os.path.join(LOGS_DIR, f"synchronisation_log_{log_time}.txt")
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write('Synchronisation - part 1\n')

def read_config_as_dict(config_path):
    """Read config file and return key-value pairs as dictionary."""
    if not os.path.exists(config_path):
        return {}
    with open(config_path, encoding='utf-8') as f:
        return {m.group(1).strip().lower(): m.group(2).strip() 
                for line in f if (m := re.match(r'^([a-zA-Z0-9_]+)\s*=\s*(.+)$', line.strip()))}

def strip_ansi(text):
    """Remove ANSI color codes from text."""
    return ANSI_ESCAPE.sub('', text)

def sync_tag():
    """Return formatted synchronisation tag for console output."""
    return f"{Style.BRIGHT}{Fore.BLUE}[Synchronisation]{Style.RESET_ALL}"

def print_and_log(msg, end='\n', log_only=False):
    """Print message to console and write to log file."""
    if not log_only:
        print(msg, end=end)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(strip_ansi(msg) + ('' if end == '' else end))

def input_and_log(prompt):
    """Get user input and log it to file."""
    print_and_log(prompt, end='')
    answer = input('')
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f'[USER INPUT] {strip_ansi(answer)}\n')
    return answer

def ensure_initial_setup():
    """Check if Subservient initial setup is complete."""
    config_dir = Path(user_config_dir()) / "Subservient"
    pathfile = config_dir / "Subservient_pathfiles"
    required_keys = ["subservient_anchor", "subordinate_path", "extraction_path", "acquisition_path", "synchronisation_path", "utils_path"]
    if not pathfile.exists():
        show_setup_error()
    lines = pathfile.read_text(encoding="utf-8").splitlines()
    keys = {l.split('=')[0] for l in lines if '=' in l}
    if not all(k in keys for k in required_keys):
        show_setup_error()

def show_setup_error():
    """Display setup error message and exit."""
    error_msg = (f"{Fore.RED}{Style.BRIGHT}[ERROR]{Style.RESET_ALL} Initial setup not complete.\n\n"
                f"{Fore.YELLOW}To get started with Subservient:{Style.RESET_ALL}\n"
                f"{Fore.CYAN}1.{Style.RESET_ALL} Ensure subordinate.py is in the main folder with other scripts\n"
                f"{Fore.CYAN}2.{Style.RESET_ALL} Run subordinate.py to perform setup and register script paths\n"
                f"{Fore.CYAN}3.{Style.RESET_ALL} After setup, move subordinate.py to process movies\n\n"
                f"{Fore.YELLOW}See README for more details.{Style.RESET_ALL}\n")
    print_and_log(error_msg)
    input("Press Enter to exit...")
    sys.exit(1)

with open(LOG_FILE, 'a+', encoding='utf-8') as f:
    f.write(strip_ansi(ASCII_ART) + '\n')
    f.write(strip_ansi(BANNER_LINE) + '\n\n')
clear_and_print_ascii(BANNER_LINE)
ensure_initial_setup()

pathfile = os.path.join(user_config_dir(), "Subservient", "Subservient_pathfiles")
anchor_path = script_dir

if os.path.exists(pathfile):
    with open(pathfile, "r", encoding="utf-8") as f:
        anchor_path = next((line.strip().split("=", 1)[1] for line in f 
                           if line.startswith("subservient_anchor=")), anchor_path)

os.chdir(anchor_path)

skip_dirs = get_skip_dirs_from_config()
videos = []
for root, dirs, files in os.walk(anchor_path):
    dirs[:] = [d for d in dirs if d.lower() not in skip_dirs]
    if any(f.endswith((".mkv", ".mp4")) for f in files):
        videos.extend(os.path.join(root, f) for f in files if f.endswith((".mkv", ".mp4")))
        dirs[:] = []

config_values = read_config_as_dict(CONFIG_PATH)
pause_seconds = int(float(config_values.get('pause_seconds', 3)))
ACCEPT_OFFSET_THRESHOLD = float(config_values.get('accept_offset_threshold', 0.05))
REJECT_OFFSET_THRESHOLD = float(config_values.get('reject_offset_threshold', 2.5))
PRESERVE_FORCED_SUBTITLES = config_values.get('preserve_forced_subtitles', 'false').lower() in ('true', '1', 'yes', 'on')
PRESERVE_UNWANTED_SUBTITLES = config_values.get('preserve_unwanted_subtitles', 'false').lower() in ('true', '1', 'yes', 'on')
drift_marked = False

def read_languages_from_config(config_path):
    """Read and validate language settings from config file."""
    if not os.path.exists(config_path):
        print_and_log(f"{sync_tag()} {Fore.RED}Config file not found. Defaulting to English.{Style.RESET_ALL}")
        return handle_language_default_warning()
    
    with open(config_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip().lower().startswith('languages'):
                parts = line.split('=', 1)
                if len(parts) == 2:
                    langs = [l.strip() for l in parts[1].split(',') if l.strip()]
                    if langs:
                        return langs
                break
    
    print_and_log(f"{sync_tag()} {Fore.RED}{Style.BRIGHT}No valid languages found in config!{Style.RESET_ALL}")
    print_and_log(f"{sync_tag()} {Fore.YELLOW}Defaulting to English.{Style.RESET_ALL}")
    return handle_language_default_warning()

def handle_language_default_warning():
    """Handle language config warning with user choice to continue or exit."""
    while True:
        print_and_log(f"\n{Fore.RED}{Style.BRIGHT}WARNING: No valid languages found in config!{Style.RESET_ALL}")
        print_and_log(f"{Fore.YELLOW}Defaulting to English only.{Style.RESET_ALL}")
        print_and_log(f"\n{Fore.CYAN}1{Style.RESET_ALL} = Continue with English only")
        print_and_log(f"{Fore.RED}2{Style.RESET_ALL} = Exit and fix config file")
        
        choice = input(f"Make a choice [{Fore.CYAN}1{Style.RESET_ALL}/{Fore.RED}2{Style.RESET_ALL}]: ").strip()
        if choice == "1":
            print_and_log(f"{Fore.YELLOW}Continuing with English only.{Style.RESET_ALL}\n")
            return ['en']
        elif choice == "2":
            print_and_log(f"{Fore.RED}Exiting. Please fix your config file.{Style.RESET_ALL}")
            sys.exit(1)
        else:
            print_and_log(f"{Fore.RED}Invalid choice. Please enter 1 or 2.{Style.RESET_ALL}")

def read_series_mode_from_config(config_path):
    """Read series mode setting from config file."""
    if not os.path.exists(config_path):
        print_and_log(f"{sync_tag()} {Fore.YELLOW}Config file not found. Defaulting to film mode.{Style.RESET_ALL}")
        return False
    
    with open(config_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip().lower().startswith('series_mode'):
                parts = line.split('=', 1)
                if len(parts) == 2:
                    val = parts[1].strip().lower()
                    return val in ['1', 'true', 'yes', 'on']
    
    print_and_log(f"{sync_tag()} {Fore.YELLOW}series_mode not found in config. Defaulting to film mode.{Style.RESET_ALL}")
    return False

def run_ffmpeg_with_progress(cmd, output_path, orig_size):
    """Run ffmpeg command with progress bar based on output file size."""
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    stop_flag = threading.Event()
    
    def show_progress():
        while not stop_flag.is_set():
            try:
                if os.path.exists(output_path):
                    size = os.path.getsize(output_path)
                    percent = min(100, int(size * 100 / orig_size)) if orig_size else 0
                    bar = ('#' * (percent // 2)).ljust(50)
                    print(f"\r[{bar}] {percent:3d}% ", end='', flush=True)
            except Exception:
                pass
            time.sleep(0.5)
        print('\r' + ' ' * 60 + '\r', end='', flush=True)
    
    t = threading.Thread(target=show_progress)
    t.start()
    stdout, stderr = process.communicate()
    stop_flag.set()
    t.join()
    return stdout, stderr

clear_and_print_ascii(BANNER_LINE)
successful_syncs = 0
successful_syncs_per_lang = {}
LANGUAGES = read_languages_from_config(CONFIG_PATH)
SERIES_MODE = read_series_mode_from_config(CONFIG_PATH)

def extract_sxxexx(filename):
    """Extract season/episode code (SxxExx) from filename."""
    match = re.search(r'(S\d{2}E\d{2})', filename, re.IGNORECASE)
    return match.group(1).upper() if match else None

sxxexx_to_video = {}
if SERIES_MODE:
    for video in videos:
        if code := extract_sxxexx(os.path.basename(video)):
            sxxexx_to_video[code] = video

FAILED_SUBS = set()
FAILED_DETAILS = {}
for f in os.listdir():
    if f.endswith('.FAILED.srt'):
        for pattern in [r"(?P<basename>.+)\.(?P<lang>[a-z]{2})\.number\d+\.FAILED\.srt$",
                       r"(?P<basename>.+)\.(?P<lang>[a-z]{2})\.FAILED\.srt$"]:
            if m := re.match(pattern, f):
                base, lang = m.group('basename'), m.group('lang')
                FAILED_SUBS.add((base, lang))
                FAILED_DETAILS[(base, lang)] = f
                break

if FAILED_SUBS:
    print_and_log(f"{sync_tag()} {Fore.RED}{Style.BRIGHT}Detected subtitles marked as FAILED (will be skipped):{Style.RESET_ALL}")
    for (base, lang) in sorted(FAILED_SUBS):
        print_and_log(f"    {Fore.LIGHTRED_EX}* {base} [{lang.upper()}] ({FAILED_DETAILS[(base, lang)]}){Style.RESET_ALL}")
def print_video_header(video_name, idx, total):
    """Print formatted header for current video being processed."""
    bar = f"{Fore.CYAN}[{idx}/{total}]{Style.RESET_ALL}  {Fore.LIGHTYELLOW_EX}{os.path.basename(video_name).upper()}{Style.RESET_ALL}"
    print(bar.ljust(79), end='\n', flush=True)
def cleanup_duplicates_in_folder(folder: str, languages):
    """Remove redundant numbered subtitle files when correct ones exist."""
    try:
        files = os.listdir(folder)
    except Exception:
        return
    
    for f in files:
        if f.endswith(('.mkv', '.mp4')):
            base_name = os.path.splitext(f)[0]
            for lang in languages:
                correct = f"{base_name}.{lang}.srt"
                if os.path.exists(os.path.join(folder, correct)):
                    for g in files:
                        if (g != correct and 
                            f".{lang}.number" in g and 
                            g.endswith('.srt') and
                            not g.endswith('.FAILED.srt') and
                            not g.endswith('.DRIFT.srt')):
                            try:
                                os.remove(os.path.join(folder, g))
                                print_and_log(f"{sync_tag()} {Fore.YELLOW}Removed redundant numbered subtitle: {g}{Style.RESET_ALL}")
                            except Exception as e:
                                print_and_log(f"{sync_tag()} {Fore.RED}Could not remove {g}: {e}{Style.RESET_ALL}")

def final_cleanup_prompt_and_cleanup():
    """Perform final cleanup of duplicate and redundant subtitle files."""
    print_and_log(f"{sync_tag()} {Fore.LIGHTYELLOW_EX}Final cleanup: removing duplicate/redundant subtitles...{Style.RESET_ALL}")
    
    total_dirs = 1
    all_dirs = []
    all_dirs.append(anchor_path)
    
    for root, dirs, files in os.walk(anchor_path):
        dirs[:] = [d for d in dirs if d.lower() not in skip_dirs]
        for d in dirs:
            dir_path = os.path.join(root, d)
            all_dirs.append(dir_path)
            total_dirs += 1
    
    processed_dirs = 0
    start_time = time.time()
    
    def update_progress():
        elapsed = time.time() - start_time
        progress = processed_dirs / total_dirs if total_dirs > 0 else 0
        bar_length = 40
        filled_length = int(bar_length * progress)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        print(f"\r{sync_tag()} {Fore.CYAN}[{bar}]{Style.RESET_ALL} {progress*100:.1f}% ({processed_dirs}/{total_dirs}) - {elapsed:.1f}s", end='', flush=True)
    
    cleanup_duplicates_in_folder(anchor_path, LANGUAGES)
    processed_dirs += 1
    update_progress()
    
    for root, dirs, files in os.walk(anchor_path):
        dirs[:] = [d for d in dirs if d.lower() not in skip_dirs]
        for d in dirs:
            time.sleep(0.25) 
            cleanup_duplicates_in_folder(os.path.join(root, d), LANGUAGES)
            processed_dirs += 1
            update_progress()
    
    print() 

cleaned_internal_subs = 0
not_cleaned_internal_subs = 0
not_cleaned_videos = []
manual_choices = {}

def has_internal_subs(video_path):
    """Check if video file contains internal subtitle streams."""
    cmd = ["ffprobe", "-v", "error", "-select_streams", "s",
           "-show_entries", "stream=index", "-of", "csv=p=0", video_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return bool(result.stdout.strip())

def remove_internal_subs(video_path):
    """Remove all internal subtitle streams from video file."""
    temp_path = video_path + ".nointernal.mkv"
    cmd = ["ffmpeg", "-hide_banner", "-y", "-i", video_path,
           "-map", "0:v", "-map", "0:a", "-c", "copy", "-sn", temp_path]
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0 and os.path.exists(temp_path):
        os.replace(temp_path, video_path)
        return True
    else:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

def prompt_and_cleanup_internal_subs():
    """Handle internal subtitle cleanup with interactive user prompts for each video.
    
    This complex function processes videos with internal subtitles and prompts users
    to decide whether to keep or remove them. It handles different scenarios based on
    missing external subtitles and duplicate language tracks.
    """
    global cleaned_internal_subs, not_cleaned_internal_subs, not_cleaned_videos, manual_choices
    total = sum(1 for video in videos if has_internal_subs(video) and any(
        not os.path.exists(f"{os.path.splitext(video)[0]}.{lang}.srt") for lang in LANGUAGES)
    )
    idx = 0
    for video in videos:
        video_basename, ext = os.path.splitext(video)
        all_present = True
        missing_langs = []
        for lang in LANGUAGES:
            found = False
            expected = f"{video_basename}.{lang}.srt"
            if os.path.exists(expected):
                found = True
            if not found:
                all_present = False
                missing_langs.append(lang)
        if all_present:
            if has_internal_subs(video):
                print_and_log(f"{sync_tag()} {Fore.LIGHTYELLOW_EX}Removing internal subtitles for compatibility...{Style.RESET_ALL}")
                if remove_internal_subs(video):
                    cleaned_internal_subs += 1
                    print_and_log(f"{sync_tag()} {Fore.GREEN}Internal subtitles removed from {video}.{Style.RESET_ALL}")
                else:
                    not_cleaned_internal_subs += 1
                    not_cleaned_videos.append(video)
                    print_and_log(f"{sync_tag()} {Fore.RED}Failed to remove internal subtitles from {video}.{Style.RESET_ALL}")
            else:
                print_and_log(f"{sync_tag()} {Fore.LIGHTYELLOW_EX}No internal subtitles detected in {video}. Skipping removal step.{Style.RESET_ALL}")
        else:
            if has_internal_subs(video):
                idx += 1
                year_match = re.search(r'(19|20)\d{2}', os.path.basename(video))
                year = year_match.group(0) if year_match else ''
                title = f"[{idx}/{total}]  {os.path.basename(video).upper()}"
                if year:
                    title += f" ({year})"
                clear_and_print_ascii(BANNER_LINE)
                print_and_log(f"{Style.BRIGHT}{Fore.LIGHTYELLOW_EX}{title}{Style.RESET_ALL}\n")
                cmd = [
                    "ffprobe", "-v", "error", "-select_streams", "s", "-show_entries",
                    "stream=index:stream_tags=language:stream_tags=title:stream_tags=handler_name:stream_tags=codec_name",
                    "-of", "csv=p=0", video
                ]
                try:
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
                    lines = [l for l in result.stdout.strip().split('\n') if l.strip()]
                except Exception:
                    lines = []
                if lines:
                    print_and_log(f"{Fore.WHITE}Found internal subtitle tracks:{Style.RESET_ALL}")
                    for l in lines:
                        parts = l.split(',')
                        lang = next((p for p in parts if len(p) == 3 and p.isalpha()), None)
                        codec = next((p for p in parts if p in ('subrip', 'hdmv_pgs_subtitle', 'dvd_subtitle', 'mov_text')), None)
                        desc = []
                        if lang:
                            desc.append(f"{Fore.CYAN}{lang.upper()}{Style.RESET_ALL} (VOBSUB)")
                        if codec:
                            desc.append(f"{Fore.LIGHTBLACK_EX}{codec}{Style.RESET_ALL}")
                        print_and_log(f"  - {' '.join(desc) if desc else l}")
                else:
                    print_and_log(f"{Fore.WHITE}No internal subtitle tracks found (unexpected).{Style.RESET_ALL}")
                if missing_langs:
                    print_and_log(f"\n{Fore.WHITE}Missing external subtitles (SRT) for:{Style.RESET_ALL}")
                    for lang in missing_langs:
                        print_and_log(f"  - {Fore.LIGHTRED_EX}{lang.upper()}{Style.RESET_ALL}")
                present_langs = set()
                internal_langs = set()
                external_langs = set()
                for l in lines:
                    parts = l.split(',')
                    lang = next((p for p in parts if len(p) == 3 and p.isalpha()), None)
                    if lang:
                        lang2 = map_lang_3to2(lang)
                        internal_langs.add(lang2)
                for lang in LANGUAGES:
                    expected = f"{video_basename}.{lang}.srt"
                    if os.path.exists(expected):
                        external_langs.add(lang)
                present_langs = internal_langs.union(external_langs)
                duplicates = internal_langs.intersection(external_langs)
                all_present = all(lang in present_langs for lang in LANGUAGES)
                if all_present and not duplicates:
                    print_and_log(f"\n{Fore.GREEN}✓ All required languages are present (internally and/or externally), no duplicates found.{Style.RESET_ALL}")
                    print_and_log(f"{Fore.GREEN}✓ Recommended: Keep internal subtitles to ensure all subtitle languages remain available.{Style.RESET_ALL}")
                    print_and_log(f"{Fore.YELLOW}⚠ Alternative: Remove internal subtitles if you prefer external SRT files only.{Style.RESET_ALL}\n")
                    print_and_log(f"{Fore.CYAN}1{Style.RESET_ALL} = {Style.BRIGHT}Keep internal subtitles {Fore.LIGHTYELLOW_EX}(recommended, no duplicates){Style.RESET_ALL}")
                    print_and_log(f"{Fore.YELLOW}2{Style.RESET_ALL} = Remove all internal subtitles completely {Fore.LIGHTYELLOW_EX}(will cause missing subtitles for some languages, not recommended){Style.RESET_ALL}\n")
                    valid_choices = ['1', '2', '']
                else:
                    print_and_log(f"\n{Fore.YELLOW}⚠ Some required languages lack external subtitles.{Style.RESET_ALL}")
                    print_and_log(f"{Fore.YELLOW}⚠ Keep internal  when no external SRT is available for that language.{Style.RESET_ALL}")
                    print_and_log(f"{Fore.LIGHTYELLOW_EX}What would you like to do?{Style.RESET_ALL}")
                    print_and_log(f"{Fore.CYAN}1{Style.RESET_ALL} = {Style.BRIGHT}Keep internal subtitles {Fore.LIGHTYELLOW_EX}(duplicate subtitles can occur){Style.RESET_ALL}")
                    print_and_log(f"{Fore.CYAN}2{Style.RESET_ALL} = Remove internal subtitles only for languages with external subtitles present {Fore.LIGHTYELLOW_EX}(recommended){Style.RESET_ALL}")
                    print_and_log(f"{Fore.YELLOW}3{Style.RESET_ALL} = Remove all internal subtitles completely {Fore.LIGHTYELLOW_EX}(Will cause missing subtitles, not recommended){Style.RESET_ALL}\n")
                    valid_choices = ['1', '2', '3', '']
                while True:
                    if all_present and not duplicates:
                        choice = input_and_log(f"Make a choice [{Fore.CYAN}1{Style.RESET_ALL}/{Fore.YELLOW}2{Style.RESET_ALL}]: ").strip()
                        if choice == "1" or choice == "":
                            print_and_log(f"{Fore.GREEN}Internal subtitles kept for this video.{Style.RESET_ALL}\n")
                            not_cleaned_internal_subs += 1
                            not_cleaned_videos.append(video)
                            manual_choices[video] = 'kept'
                            break
                        elif choice == "2":
                            temp_path = video + ".nointernal.mkv"
                            orig_size = os.path.getsize(video)
                            cmd = [
                                "ffmpeg", "-hide_banner", "-y", "-i", video,
                                "-map", "0:v", "-map", "0:a", "-c", "copy", "-sn", temp_path
                            ]
                            print_and_log(f"{Fore.LIGHTYELLOW_EX}Remuxing to remove all internal subtitles...{Style.RESET_ALL}")
                            stdout, stderr = run_ffmpeg_with_progress(cmd, temp_path, orig_size)
                            for line in (stdout + '\n' + stderr).splitlines():
                                if 'muxing overhead' in line or 'frame' in line or 'size' in line:
                                    print_and_log(line)
                            if os.path.exists(temp_path):
                                os.replace(temp_path, video)
                                cleaned_internal_subs += 1
                                print_and_log(f"{Fore.GREEN}Internal subtitles removed from {video}.{Style.RESET_ALL}")
                                manual_choices[video] = 'removed'
                            else:
                                not_cleaned_internal_subs += 1
                                not_cleaned_videos.append(video)
                                print_and_log(f"{Fore.RED}Failed to remove internal subtitles from {video}.{Style.RESET_ALL}")
                                manual_choices[video] = 'failed'
                            break
                        else:
                            print_and_log(f"{Fore.RED}Invalid choice. Please enter 1 or 2.{Style.RESET_ALL}")
                    else:
                        choice = input_and_log(f"Make a choice [{Fore.CYAN}1{Style.RESET_ALL}/{Fore.CYAN}2{Style.RESET_ALL}/{Fore.YELLOW}3{Style.RESET_ALL}]: ").strip()
                        if choice == "1" or choice == "":
                            print_and_log(f"{Fore.GREEN}Internal subtitles kept for this video.{Style.RESET_ALL}\n")
                            not_cleaned_internal_subs += 1
                            not_cleaned_videos.append(video)
                            manual_choices[video] = 'kept'
                            break
                        elif choice == "2":
                            removed_any = False
                            probe_cmd = [
                                "ffprobe", "-v", "error", "-select_streams", "s", "-show_entries",
                                "stream=index:stream_tags=language", "-of", "csv=p=0", video
                            ]
                            result = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
                            probe_lines = [l for l in result.stdout.strip().split('\n') if l.strip()]
                            subtitle_streams = []
                            ffmpeg_sub_idx = 0
                            for l in probe_lines:
                                parts = l.split(',')
                                if len(parts) >= 1:
                                    stream_idx = parts[0]
                                    stream_lang = parts[1].lower() if len(parts) >= 2 and parts[1] else 'und'
                                    subtitle_streams.append((ffmpeg_sub_idx, stream_idx, stream_lang))
                                    ffmpeg_sub_idx += 1
                            for lang in LANGUAGES:
                                has_external = any(os.path.exists(f"{video_basename}.{lang}.srt"))
                                if has_external:
                                    print_and_log(f"{Fore.YELLOW}Removing internal subtitle for {Fore.CYAN}{lang.upper()}{Fore.YELLOW} from the video file. Please wait...{Style.RESET_ALL}")
                                    streams_to_keep = []
                                    lang_removed = False
                                    for ffmpeg_idx, stream_idx, stream_lang in subtitle_streams:
                                        matches_lang = False
                                        if map_lang_3to2(stream_lang) == lang:
                                            matches_lang = True
                                        if not matches_lang:
                                            streams_to_keep.append(ffmpeg_idx)
                                        else:
                                            lang_removed = True
                                    if lang_removed:
                                        temp_path = video + f".nointernal.{lang}.mkv"
                                        orig_size = os.path.getsize(video)
                                        cmd = [
                                            "ffmpeg", "-hide_banner", "-y", "-i", video,
                                            "-map", "0:v", "-map", "0:a", "-c", "copy"
                                        ]
                                        for ffmpeg_idx in streams_to_keep:
                                            cmd += ["-map", f"0:s:{ffmpeg_idx}"]
                                        cmd.append(temp_path)
                                        print_and_log(f"{Fore.LIGHTYELLOW_EX}Remuxing to remove internal subtitle...{Style.RESET_ALL}")
                                        stdout, stderr = run_ffmpeg_with_progress(cmd, temp_path, orig_size)
                                        for line in (stdout + '\n' + stderr).splitlines():
                                            if 'muxing overhead' in line or 'frame' in line or 'size' in line:
                                                print_and_log(line)
                                        if os.path.exists(temp_path):
                                            os.replace(temp_path, video)
                                            removed_any = True
                                            print_and_log(f"{Fore.GREEN}Successfully removed {lang.upper()} internal subtitle.{Style.RESET_ALL}")
                                        else:
                                            print_and_log(f"{Fore.RED}Failed to remove {lang.upper()} internal subtitle.{Style.RESET_ALL}")
                                    else:
                                        print_and_log(f"{Fore.YELLOW}No internal subtitle found for {lang.upper()}.{Style.RESET_ALL}")
                            if removed_any:
                                print_and_log(f"{Fore.GREEN}Selected internal subtitles removed from {os.path.basename(video)}.{Style.RESET_ALL}\n")
                                cleaned_internal_subs +=  1
                                manual_choices[video] = 'partial-removed'
                            else:
                                print_and_log(f"{Fore.YELLOW}No matching internal subtitles found to remove.{Style.RESET_ALL}\n")
                                not_cleaned_internal_subs += 1
                                not_cleaned_videos.append(video)
                                manual_choices[video] = 'none-removed'
                            break
                        elif choice == "3":
                            temp_path = video + ".nointernal.mkv"
                            orig_size = os.path.getsize(video)
                            cmd = [
                                "ffmpeg", "-hide_banner", "-y", "-i", video,
                                "-map", "0:v", "-map", "0:a", "-c", "copy", "-sn", temp_path
                            ]
                            print_and_log(f"{Fore.LIGHTYELLOW_EX}Remuxing to remove all internal subtitles...{Style.RESET_ALL}")
                            stdout, stderr = run_ffmpeg_with_progress(cmd, temp_path, orig_size)
                            for line in (stdout + '\n' + stderr).splitlines():
                                if 'muxing overhead' in line or 'frame' in line or 'size' in line:
                                    print_and_log(line)
                            if os.path.exists(temp_path):
                                os.replace(temp_path, video)
                                cleaned_internal_subs += 1
                                print_and_log(f"{Fore.GREEN}Internal subtitles removed from {video}.{Style.RESET_ALL}")
                                manual_choices[video] = 'removed'
                            else:
                                not_cleaned_internal_subs += 1
                                not_cleaned_videos.append(video)
                                print_and_log(f"{Fore.RED}Failed to remove internal subtitles from {video}.{Style.RESET_ALL}")
                                manual_choices[video] = 'failed'
                            break
                        else:
                            print_and_log(f"{Fore.RED}Invalid choice. Please enter 1, 2, or 3.{Style.RESET_ALL}")
    print_and_log(f"{sync_tag()} {Fore.LIGHTYELLOW_EX}Cleaning up failed subtitles...{Style.RESET_ALL}")
    failed_count = 0
    for f in [f for f in os.listdir() if f.endswith('.FAILED.srt')]:
        try:
            os.remove(f)
            failed_count += 1
        except Exception:
            pass
    video_dirs = set()
    for video in videos:
        video_dirs.add(os.path.dirname(video))
    
    for video_dir in video_dirs:
        try:
            for f in os.listdir(video_dir):
                if f.endswith('.FAILED.srt'):
                    try:
                        full_path = os.path.join(video_dir, f)
                        os.remove(full_path)
                        failed_count += 1
                    except Exception:
                        pass
        except Exception:
            pass
    
    if failed_count > 0:
        print_and_log(f"{sync_tag()} {Fore.LIGHTRED_EX}Failed subtitles have been cleaned.{Style.RESET_ALL} {Fore.CYAN}({failed_count} .FAILED.srt files removed){Style.RESET_ALL}")
MOVIES_WITH_LINEAR_OFFSET_FILE = os.path.join(script_dir, 'movies_with_linear_offset.txt')

def add_offset_entry(video, video_dir, lang, output_sub, diffs, anchor_path, sub_files):
    """Add or update offset entry in tracking file for manual verification."""
    if not os.path.exists(MOVIES_WITH_LINEAR_OFFSET_FILE):
        with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'w', encoding='utf-8') as f:
            f.write("Linear offset tracking file for movies with subtitle sync corrections.\n")
            f.write("Format: movie name, path, offset, timestamp, first line\n--\n")
    
    rel_video_path = os.path.relpath(video, anchor_path)
    trimmed_name = trim_movie_name(os.path.basename(video)) + f" [{lang.upper()}]"
    first_time, first_line = get_first_line_and_time(output_sub)

    orig_numbered = next((s for s in sub_files if '.number' in s), None)
    
    video_filename = os.path.basename(video)
    existing_entries = []
    header_entry = None
    entry_found = False
    
    try:
        with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        entries = content.split('--\n')
        for entry in entries:
            entry = entry.strip()
            if (entry.startswith('Linear offset tracking') or 
                entry.startswith('Format:') or 
                len(entry.splitlines()) < 3):
                if header_entry is None:
                    header_entry = entry
                continue
            if len(entry.splitlines()) >= 3:
                entry_title = entry.splitlines()[0].strip()
                entry_folder = entry.splitlines()[1].strip()
                entry_video = entry.splitlines()[2].strip()
                lang_match = re.search(r'\[([A-Z]{2})\]', entry_title)
                entry_lang = lang_match.group(1) if lang_match else ""
                if (entry_folder == video_dir and 
                    entry_video == video_filename and 
                    entry_lang.upper() == lang.upper()):
                    print_and_log(f"{sync_tag()} {Fore.YELLOW}Updating existing offset entry for {trimmed_name}{Style.RESET_ALL}")
                    entry_found = True
                    continue
            existing_entries.append(entry)
    
    except Exception as e:
        print_and_log(f"{sync_tag()} {Fore.RED}Warning: Could not read existing offset file: {e}{Style.RESET_ALL}")
        existing_entries = []
    new_entry_lines = [
        trimmed_name,
        video_dir,
        os.path.basename(video),
        os.path.basename(output_sub),
        f"{diffs[0]:.3f}",
        f"{first_time}  {first_line}"
    ]
    if orig_numbered:
        new_entry_lines.append(orig_numbered)
    else:
        output_basename = os.path.splitext(os.path.basename(output_sub))[0]
        output_ext = os.path.splitext(output_sub)[1]
        video_name = output_basename.replace(f".{lang}", "")
        orig_name = f"{video_name}.{lang}.number1{output_ext}"
        new_entry_lines.append(orig_name)
    with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'w', encoding='utf-8') as f:
        if header_entry:
            f.write(header_entry)
            if not header_entry.endswith('\n'):
                f.write('\n')
            if not header_entry.endswith('--\n'):
                f.write('--\n')
        for i, entry in enumerate(existing_entries):
            if entry.strip():
                f.write(entry)
                if not entry.endswith('\n'):
                    f.write('\n')
                if i < len(existing_entries) - 1:
                    f.write('--\n')
                else:
                    f.write('--\n')
        f.write('\n'.join(new_entry_lines))
        f.write('\n--\n')
    action_word = "Updated" if entry_found else "Added"
    print_and_log(f"{sync_tag()} {Fore.GREEN}{action_word} offset entry for {trimmed_name}{Style.RESET_ALL}")
def get_first_line_and_time(sub_path):
    """Extract first timestamp and text line from subtitle file."""
    ext = os.path.splitext(sub_path)[1].lower()
    with open(sub_path, encoding="utf-8", errors="ignore") as f:
        if ext == ".srt":
            time_str = next((line.split("-->")[0].strip() for line in f if "-->" in line), "")
            f.seek(0)
            first_line = next((line.strip() for line in f 
                              if line.strip() and not line.strip().isdigit() and "-->" not in line), "")
            return time_str, first_line
    return "", ""
def apply_srt_offset(sub_path, ms_offset):
    """Apply time offset to all timestamps in SRT subtitle file."""
    try:
        with open(sub_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        time_pattern = re.compile(r'^(\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2},\d{3})$')
        
        def shift_timestamp(ts, ms):
            h, m, s_ms = ts.split(':')
            s, ms_part = s_ms.split(',')
            total_ms = max(0, (int(h)*3600 + int(m)*60 + int(s)) * 1000 + int(ms_part) + ms)
            nh, nm, ns, nms = total_ms // 3600000, (total_ms % 3600000) // 60000, (total_ms % 60000) // 1000, total_ms % 1000
            return f"{nh:02}:{nm:02}:{ns:02},{nms:03}"
        
        new_lines = []
        for line in lines:
            if m := time_pattern.match(line.strip()):
                start, end = m.groups()
                new_start = shift_timestamp(start, ms_offset)
                new_end = shift_timestamp(end, ms_offset)
                new_lines.append(f"{new_start} --> {new_end}\n")
            else:
                new_lines.append(line)
        
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False) as tmp:
            tmp.writelines(new_lines)
            tmp_path = tmp.name
        
        for attempt in [
            lambda: os.replace(tmp_path, sub_path),
            lambda: (os.chmod(sub_path, stat.S_IWRITE if os.name == 'nt' else 0o666), 
                    os.remove(sub_path), os.replace(tmp_path, sub_path)),
            lambda: (shutil.copyfile(tmp_path, sub_path), os.remove(tmp_path))
        ]:
            try:
                attempt()
                return True, None
            except Exception as e:
                last_error = e
                continue
        
        return False, str(last_error)
    except Exception as e:
        return False, str(e)
def mark_subtitle_as_drift(subtitle_path, lang, create_copies=False):
    """Mark subtitle file as DRIFT and optionally create copies for lower numbers."""
    try:
        video_dir = os.path.dirname(subtitle_path)
        subtitle_name = os.path.basename(subtitle_path)
        
        m = re.search(r'number(\d+)', subtitle_name)
        if m:
            num = int(m.group(1))
        else:
            num = None
        
        base, ext = os.path.splitext(subtitle_name)
        drift_name = f"{base}.DRIFT{ext}"
        drift_path = os.path.join(video_dir, drift_name)
        
        os.rename(subtitle_path, drift_path)
        print_and_log(f"{sync_tag()} {Fore.LIGHTRED_EX}Subtitle marked as DRIFT: {drift_name}{Style.RESET_ALL}")
        
        if create_copies and num and num > 1:
            for i in range(1, num):
                new_name = re.sub(r'number\d+', f'number{i}', subtitle_name)
                base2, ext2 = os.path.splitext(new_name)
                new_drift_name = f"{base2}.DRIFT{ext2}"
                new_drift_path = os.path.join(video_dir, new_drift_name)
                
                if not os.path.exists(new_drift_path):
                    try:
                        shutil.copyfile(drift_path, new_drift_path)
                        print_and_log(f"{sync_tag()} {Fore.YELLOW}Created drift copy: {new_drift_name}{Style.RESET_ALL}")
                    except Exception as e:
                        print_and_log(f"{sync_tag()} {Fore.RED}Failed to create drift copy {new_drift_name}: {e}{Style.RESET_ALL}")
                else:
                    print_and_log(f"{sync_tag()} {Fore.CYAN}DRIFT copy already exists, skipping: {new_drift_name}{Style.RESET_ALL}", log_only=True)
        
        return drift_path
        
    except Exception as e:
        print_and_log(f"{sync_tag()} {Fore.RED}Error marking subtitle as DRIFT: {str(e)}{Style.RESET_ALL}")
        return None

def cleanup_drift_and_failed(video_dir, lang, keep_file=None, clean_drifts=True):
    """Clean up numbered, failed, and drift subtitle files for a language."""
    for f in os.listdir(video_dir):
        full_path = os.path.abspath(os.path.join(video_dir, f))
        if re.match(rf".*\.{lang}\.number\d+\.srt$", f, re.IGNORECASE):
            if keep_file and full_path == os.path.abspath(keep_file):
                continue
            try:
                os.remove(full_path)
                print_and_log(f"{sync_tag()} {Fore.YELLOW}Cleanup: removed numbered sub: {f}{Style.RESET_ALL}")
            except Exception as e:
                print_and_log(f"{sync_tag()} {Fore.RED}Could not remove {f}: {e}{Style.RESET_ALL}")
        elif re.match(rf".*\.{lang}\.number\d+\.FAILED\.srt$", f, re.IGNORECASE):
            try:
                os.remove(full_path)
                print_and_log(f"{sync_tag()} {Fore.YELLOW}Cleanup: removed FAILED: {f}{Style.RESET_ALL}")
            except Exception as e:
                print_and_log(f"{sync_tag()} {Fore.RED}Could not remove {f}: {e}{Style.RESET_ALL}")
        elif clean_drifts and re.match(rf".*\.{lang}\.number\d+\.DRIFT\.srt$", f, re.IGNORECASE):
            try:
                os.remove(full_path)
                print_and_log(f"{sync_tag()} {Fore.YELLOW}Cleanup: removed DRIFT: {f}{Style.RESET_ALL}")
            except Exception as e:
                print_and_log(f"{sync_tag()} {Fore.RED}Could not remove {f}: {e}{Style.RESET_ALL}")
processed_subs = set()
total_videos = len(videos)
acquisition_needed = False  

for idx, video in enumerate(videos, 1):
    clear_and_print_ascii(BANNER_LINE)
    print_video_header(video, idx, total_videos)
    video_dir = os.path.dirname(video)
    video_basename, _ = os.path.splitext(video)
    
    all_subs_exist = True
    for lang in LANGUAGES:
        expected = f"{video_basename}.{lang}.srt"
        if not os.path.exists(expected):
            all_subs_exist = False
            break
    
    if all_subs_exist:
        print_and_log(f"{sync_tag()} {Fore.GREEN}All required subtitles already exist for this video - skipping{Style.RESET_ALL}")
        continue
    
    candidate_subs = defaultdict(list)
    for f in os.listdir(video_dir):
        f_path = os.path.join(video_dir, f)
        match = re.match(r".*\.(?P<lang>[a-z]{2})\.number\d+\.srt$", f)
        if match:
            lang = match.group("lang")
            if lang in LANGUAGES:
                candidate_subs[lang].append(f_path)
    
    for lang in LANGUAGES:
        subs = candidate_subs.get(lang, [])
        found_good = False
        drift_subs = []  
        
        subs_sorted = sorted(subs, key=lambda x: int(re.search(r"number(\d+)", x).group(1)))
        logged_video_context = False
        
        for sub in subs_sorted:
            if sub.endswith('.DRIFT.srt') or sub.endswith('.FAILED.srt'):
                continue
                
            ext = os.path.splitext(sub)[1].lower()
            output_ext = f".{lang}{ext}"
            output_sub = video_basename + output_ext
            
            if os.path.exists(output_sub):
                found_good = True
                break
            
            if not logged_video_context:
                print_and_log(f"➤ {os.path.basename(video)}", log_only=True)
                logged_video_context = True
            
            print_and_log(f"{Fore.YELLOW}Synchronizing {os.path.basename(sub)} {Fore.LIGHTYELLOW_EX}[{lang.upper()}]{Style.RESET_ALL}")
            
            sync_success, offset_seconds = synchronize_subtitle_with_ffsubsync(video, sub, output_sub)
            
            if sync_success:
                if offset_seconds > REJECT_OFFSET_THRESHOLD:
                    print_and_log(f"{sync_tag()} {Fore.RED}⚠ High offset detected ({offset_seconds:.3f}s > {REJECT_OFFSET_THRESHOLD}s) - marking as DRIFT{Style.RESET_ALL}")
                    
                    try:
                        os.remove(output_sub)
                        mark_subtitle_as_drift(sub, lang, create_copies=False)  
                        drift_subs.append(sub)
                        
                        continue
                    except Exception as e:
                        print_and_log(f"{sync_tag()} {Fore.RED}Error handling high offset: {str(e)}{Style.RESET_ALL}")
                        continue
                        
                elif offset_seconds > ACCEPT_OFFSET_THRESHOLD:
                    print_and_log(f"{sync_tag()} {Fore.YELLOW}✓ Synchronized with moderate offset ({offset_seconds:.3f}s) - added to manual verification{Style.RESET_ALL}")
                    
                    try:
                        add_offset_entry(video, video_dir, lang, output_sub, [offset_seconds], anchor_path, [os.path.basename(sub)])
                    except Exception as e:
                        print_and_log(f"{sync_tag()} {Fore.RED}Error adding offset entry: {str(e)}{Style.RESET_ALL}")
                        
                else:
                    print_and_log(f"{sync_tag()} {Fore.GREEN}✓ Synchronized with excellent precision ({offset_seconds:.3f}s ≤ {ACCEPT_OFFSET_THRESHOLD}s){Style.RESET_ALL}")
                
                found_good = True
                successful_syncs += 1
                successful_syncs_per_lang[lang] = successful_syncs_per_lang.get(lang, 0) + 1
                processed_subs.add(sub)
                
                cleanup_drift_and_failed(video_dir, lang, keep_file=output_sub, clean_drifts=True)
                
                break
            else:
                print_and_log(f"{sync_tag()} {Fore.RED}✗ Synchronization failed for {os.path.basename(sub)}{Style.RESET_ALL}")
                
                base_name = os.path.splitext(sub)[0]
                failed_name = f"{base_name}.FAILED{ext}"
                
                try:
                    os.rename(sub, failed_name)
                    print_and_log(f"{sync_tag()} {Fore.YELLOW}Marked as FAILED: {os.path.basename(failed_name)}{Style.RESET_ALL}")
                except Exception as e:
                    print_and_log(f"{sync_tag()} {Fore.RED}Could not rename to FAILED: {str(e)}{Style.RESET_ALL}")
        
        if not found_good:
            all_current_drifted = all(f.endswith('.DRIFT.srt') or f.endswith('.FAILED.srt') 
                                    for f in [os.path.basename(s) for s in subs_sorted])
            
            existing_drifts = [f for f in os.listdir(video_dir) 
                             if f.endswith('.DRIFT.srt') and f'.{lang}.' in f]
            
            if (all_current_drifted and subs_sorted) or existing_drifts:
                print_and_log(f"{sync_tag()} {Fore.YELLOW}No good sync found for {lang.upper()} - will check for acquisition at end{Style.RESET_ALL}")
                acquisition_needed = True

if acquisition_needed:
    os.system('cls' if os.name == 'nt' else 'clear')
    clear_and_print_ascii(BANNER_LINE)
    print_and_log(f"{sync_tag()} {Style.BRIGHT}{Fore.RED}Some videos/languages only have DRIFTs! Acquisition will be started.{Style.RESET_ALL}\n")
    print_and_log(f"{sync_tag()} {Fore.YELLOW}This window will close automatically in {pause_seconds} seconds...{Style.RESET_ALL}")
    time.sleep(pause_seconds)
    os.system(f'python "{os.path.join(script_dir, "acquisition.py")}"')
    sys.exit(0)
else:
    print_and_log(f"{sync_tag()} {Fore.GREEN}Synchronization completed successfully - cleaning up remaining DRIFT files{Style.RESET_ALL}")
    for video in videos:
        video_dir = os.path.dirname(video)
        for lang in LANGUAGES:
            for f in os.listdir(video_dir):
                if re.match(rf".*\.{lang}\.number\d+\.DRIFT\.srt$", f, re.IGNORECASE):
                    try:
                        drift_path = os.path.join(video_dir, f)
                        os.remove(drift_path)
                        print_and_log(f"{sync_tag()} {Fore.YELLOW}Final cleanup: removed DRIFT: {f}{Style.RESET_ALL}")
                    except Exception as e:
                        print_and_log(f"{sync_tag()} {Fore.RED}Could not remove DRIFT {f}: {e}{Style.RESET_ALL}")
all_subs_present = True
missing_langs = set()
missing_details = {}
missing_per_video = {}
if SERIES_MODE:
    for code, video in sxxexx_to_video.items():
        video_basename, _ = os.path.splitext(video)
        for lang in LANGUAGES:
            expected = f"{video_basename}.{lang}.srt"
            if not os.path.exists(expected):
                all_subs_present = False
                missing_langs.add(lang)
                missing_details.setdefault(lang, []).append(video)
                missing_per_video.setdefault(video, []).append(lang)
else:
    for video in videos:
        video_basename, _ = os.path.splitext(video)
        for lang in LANGUAGES:
            expected = f"{video_basename}.{lang}.srt"
            if not os.path.exists(expected):
                all_subs_present = False
                missing_langs.add(lang)
                missing_details.setdefault(lang, []).append(video)
                missing_per_video.setdefault(video, []).append(lang)

def show_offset_verification_menu():
    """Display menu for manual verification of subtitle offset corrections."""
    MOVIES_WITH_LINEAR_OFFSET_FILE = os.path.join(script_dir, 'movies_with_linear_offset.txt')
    if not os.path.exists(MOVIES_WITH_LINEAR_OFFSET_FILE):
        return
    with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    entries = []
    for entry in content.split('--\n'):
        entry = entry.strip()
        if entry and not entry.startswith('Linear offset tracking') and not entry.startswith('Format:'):
            lines = entry.splitlines()
            if len(lines) >= 3 and any(line.endswith(('.mkv', '.mp4', '.avi')) for line in lines):
                entries.append(entry)
    if not entries:
        return
    clear_and_print_ascii(BANNER_LINE)
    print_and_log(f"{Style.BRIGHT}{Fore.CYAN}Offset Correction Verification Menu{Style.RESET_ALL}\n")
    print_and_log(f"{Fore.YELLOW}Detected {Style.BRIGHT}{len(entries)}{Style.NORMAL} subtitle file(s) that had an offset correction.{Style.RESET_ALL}\n")
    print_and_log(f"These subtitles had offsets above {ACCEPT_OFFSET_THRESHOLD:.3f}s, below {REJECT_OFFSET_THRESHOLD:.3f}s.")
    print_and_log("Subtitles with smaller offsets were automatically accepted, while those with larger offsets were marked as DRIFT.")
    print_and_log("Let's manually verify these intermediate cases to ensure the subtitle text matches the audio well enough.")
    print_and_log("If the result is inadequate, then you can make manual adjustments using Subservient.\n")
    print_and_log(f"Subservient will attempt to automatically open the video for you, using your default media player.")
    print_and_log(f"Don't have a decent media player? You can install {Fore.LIGHTYELLOW_EX}VLC Media Player{Style.RESET_ALL} for free. \n")
    print_and_log(f"{Fore.GREEN}Press any key to start going through the video files...{Style.RESET_ALL}")
    input()
    clear_and_print_ascii(BANNER_LINE)
    show_offset_verification_details()

def open_video_with_default_app(path):
    """Open video file with system default media player."""
    if sys.platform.startswith('win'):
        os.startfile(path)
    elif sys.platform.startswith('darwin'):
        subprocess.call(['open', path])
    else:
        subprocess.call(['xdg-open', path])

def remove_completed_entry_from_offset_file(title, folder, video):
    """Remove verified entry from offset tracking file."""
    offset_file = os.path.join(script_dir, 'movies_with_linear_offset.txt')
    if not os.path.exists(offset_file):
        return
    
    try:
        with open(offset_file, 'r', encoding='utf-8') as f:
            content = f.read()

        entries = content.split('--\n')
        updated_entries = []
        
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
                
            lines = entry.splitlines()
            if (entry.startswith('Linear offset tracking') or 
                entry.startswith('Format:') or 
                len(lines) < 3):
                updated_entries.append(entry)
                continue
            if (len(lines) >= 3 and 
                lines[0].strip() == title.strip() and 
                lines[1].strip() == folder.strip() and 
                lines[2].strip() == video.strip()):
                print_and_log(f"{sync_tag()} {Fore.GREEN}Removed completed entry from offset tracking: {title}{Style.RESET_ALL}")
                continue

            updated_entries.append(entry)
        data_entries = []
        header_entries = []
        
        for entry in updated_entries:
            lines = entry.strip().splitlines()
            if (entry.startswith('Linear offset tracking') or 
                entry.startswith('Format:') or 
                len(lines) < 3):
                header_entries.append(entry)
            else:
                data_entries.append(entry)
        
        if data_entries:
            with open(offset_file, 'w', encoding='utf-8') as f:
                for i, entry in enumerate(updated_entries):
                    f.write(entry)
                    if not entry.endswith('\n'):
                        f.write('\n')
                    if i < len(updated_entries) - 1:
                        f.write('--\n')
                    else:
                        f.write('--\n')
        else:
            os.remove(offset_file)
            print_and_log(f"{sync_tag()} {Fore.LIGHTYELLOW_EX}Offset tracking file deleted - no more entries to track{Style.RESET_ALL}")
            
    except Exception as e:
        print_and_log(f"{sync_tag()} {Fore.RED}Error removing entry from offset file: {str(e)}{Style.RESET_ALL}")

def show_offset_verification_details():
    """Process offset verification entries and prompt user for each video."""
    offset_file = os.path.join(script_dir, 'movies_with_linear_offset.txt')
    if not os.path.exists(offset_file):
        print_and_log(f"{Fore.LIGHTRED_EX}No offset verification file found!{Style.RESET_ALL}")
        return
    with open(offset_file, 'r', encoding='utf-8') as f:
        content = f.read()
    raw_entries = [e.strip() for e in content.split('--') if e.strip()]
    entries = []
    for entry in raw_entries:
        lines = entry.splitlines()
        if len(lines) >= 3 and (lines[2].endswith('.mkv') or lines[2].endswith('.mp4')):
            entries.append(entry)
    if not entries:
        print_and_log(f"{Fore.LIGHTRED_EX}No entries found in offset verification file!{Style.RESET_ALL}")
        return
    for idx, entry in enumerate(entries, 1):
        lines = entry.splitlines()
        if len(lines) < 6:
            continue
        title = lines[0]
        folder = lines[1]
        video = lines[2]
        lang_match = re.search(r'\[([A-Z]{2})\]', title)
        lang = lang_match.group(1) if lang_match else "EN"
        
        subfiles = []
        for l in lines[3:]:
            if l.replace('.', '', 1).replace('-', '', 1).isdigit() or l.startswith('00:') or l.startswith('0:'):
                break
            subfiles.append(l)
        offset_line_idx = 3 + len(subfiles)
        offset = lines[offset_line_idx]
        timestamp = lines[offset_line_idx+1] if len(lines) > offset_line_idx+1 else ''
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"{Fore.LIGHTYELLOW_EX}[{idx}/{len(entries)}] {title}{Style.RESET_ALL}")
        print_and_log(f"{Fore.WHITE}Video folder: {Fore.GREEN}{folder}{Style.RESET_ALL}")
        print_and_log(f"{Fore.WHITE}Video file:   {Fore.GREEN}{video}{Style.RESET_ALL}")
        for sub in subfiles:
            print_and_log(f"{Fore.WHITE}Subtitle:    {Fore.GREEN}{sub}{Style.RESET_ALL}")
        print()
        docker_note = ""
        if is_running_in_docker():
            docker_note = f"Note: Your docker container does not have access to your video player, so you'll need to open the video manually.\n"
        
        vlc_text = (
            f"Choose option 1 to automatically open the video file using your default media player.\n"
            f"{docker_note}"
            f"If you prefer not to, then you can always open the video file manually:"
        )
        print_and_log(f"{Fore.WHITE}{vlc_text}{Style.RESET_ALL}")
        print_and_log(f"{Fore.CYAN}{folder}{os.sep}{video}{Style.RESET_ALL}")
        print()
        while True:
            print_and_log(f"{Fore.LIGHTYELLOW_EX}How would you like to open the video?:{Style.RESET_ALL}")
            print_and_log(f"{Fore.CYAN}1{Style.RESET_ALL} = Automatically open the video using your default media player.")
            print_and_log(f"{Fore.YELLOW}2{Style.RESET_ALL} = I will open the video manually.")
            choice = input(f"\nChoose [{Fore.CYAN}1{Style.RESET_ALL}/{Fore.YELLOW}2{Style.RESET_ALL}]: ").strip()
            vlc_opened = False
            clear_and_print_ascii(BANNER_LINE)
            if choice == "1":
                if subfiles:
                    video_path = os.path.join(folder, video)
                    print_and_log(f"{Fore.CYAN}Opening video with the default player...{Style.RESET_ALL}")
                    try:
                        open_video_with_default_app(video_path)
                        vlc_opened = True
                    except Exception:
                        print_and_log(f"{Fore.LIGHTRED_EX}Could not automatically open the video..{Style.RESET_ALL}")
                        print_and_log(f"{Fore.LIGHTYELLOW_EX}Please open the video file manually, using the path below.{Style.RESET_ALL}")
                        print_and_log(f"{Fore.CYAN}{video_path}{Style.RESET_ALL}")
                else:
                    print_and_log(f"{Fore.LIGHTRED_EX}No subtitle file found for this entry!{Style.RESET_ALL}")
                break
            elif choice == "2":
                break
            else:
                print_and_log(f"{Fore.RED}Invalid choice. Please enter 1 or 2.{Style.RESET_ALL}")
        try:
            offset_val = float(str(offset).replace('s','').replace('seconds','').replace('second','').strip())
            if offset_val > 0:
                offset_color = Fore.GREEN
                offset_sign = "+"
            elif offset_val < 0:
                offset_color = Fore.RED
                offset_sign = ""
            else:
                offset_color = Fore.WHITE
                offset_sign = ""
            offset_display = f" | {Fore.WHITE}corrected offset: {offset_color}{offset_sign}{offset_val:.3f}s{Style.RESET_ALL}"
        except (ValueError, TypeError):
            offset_display = f" | {Fore.WHITE}corrected offset: {Fore.YELLOW}unknown{Style.RESET_ALL}"
        
        print_and_log(f"\n{Fore.LIGHTYELLOW_EX}[{idx}/{len(entries)}] {title}{offset_display}{Style.RESET_ALL}\n")
        if 'vlc_opened' in locals() and vlc_opened:
            print_and_log("The video file should now have started. Please especially check for:")
            print_and_log("1. Sentences that are too early or too late compared to the audio.")
            print_and_log("2. Subtitles appearing correctly when actors are talking in a different language.\n")
            print_and_log("The subtitles we're now manually checking are usually listed at the very bottom.\n")
        else:
            print_and_log("Please open the video file manually at the blue path, then check for the questions below:")
            print_and_log(f"{Fore.CYAN}{folder}{os.sep}{video}{Style.RESET_ALL}")
            print_and_log("1. Check for sentences that are too early or too late compared to the audio.")
            print_and_log("2. Check that subtitles appear correctly when actors are talking in a different language.\n")
            print_and_log("The subtitles we're now manually checking are usually listed at the very bottom.")
        print()
        while True:
            lang_display = f"{Fore.LIGHTGREEN_EX}{lang.upper()}{Style.RESET_ALL}"
            print_and_log(f"{Fore.LIGHTYELLOW_EX}Please check if the [{lang_display}]{Fore.LIGHTYELLOW_EX} subtitle text matches the audio. Does it match well enough?{Style.RESET_ALL}")
            print_and_log(f"{Fore.GREEN}1{Style.RESET_ALL} = Yes, the subtitle is well synced. Go to the next video file.")
            print_and_log(f"{Fore.RED}2{Style.RESET_ALL} = No, let's make some manual corrections using Subservient.")
            sub_choice = input(f"\nChoose [{Fore.GREEN}1{Style.RESET_ALL}/{Fore.RED}2{Style.RESET_ALL}]: ").strip()
            if sub_choice == "1":
                remove_completed_entry_from_offset_file(title, folder, video)
                clear_and_print_ascii(BANNER_LINE)
                break
            elif sub_choice == "2":
                subtitle_name = subfiles[0] if subfiles else "(unknown)"
                try:
                    offset_val = offset
                except Exception:
                    offset_val = "(unknown)"
                try:
                    timestamp_val = timestamp
                except Exception:
                    timestamp_val = "(unknown)"
                show_manual_correction_menu(idx, len(entries), title, subtitle_name, offset_val, timestamp_val, folder, video)
                clear_and_print_ascii(BANNER_LINE)
                break
            else:
                print_and_log(f"{Fore.RED}Invalid choice. Please enter 1 or 2.{Style.RESET_ALL}")

def show_manual_correction_menu(idx, total, title, subtitle_name, offset, timestamp, folder, video):
    """Display interactive menu for manual subtitle timing correction with multiple adjustment options.
    
    This complex function provides a detailed interface for manually adjusting subtitle timing
    with options to apply positive/negative offsets, restore original timing, or mark as drift.
    It tracks all changes and provides video playback integration for verification.
    """
    global drift_marked
    logs = []
    sub_path = os.path.join(folder, subtitle_name)
    net_change = 0
    offset_restored = False
    drift_marked_in_menu = False
    try:
        offset_sec = float(str(offset).replace('s','').replace('seconds','').replace('second','').replace('+','').strip())
        ms_restore = int(round(-offset_sec * 1000))
    except Exception:
        ms_restore = 0
    while True:
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"{Fore.LIGHTYELLOW_EX}[{idx}/{total}] {title}{Style.RESET_ALL}")
        print()
        print_and_log(f"{Fore.WHITE}Editing this subtitle:{Style.RESET_ALL}")
        print_and_log(f"{Fore.CYAN}{subtitle_name}{Style.RESET_ALL}")
        print()
        if net_change > 0:
            net_col = Fore.GREEN
        elif net_change < 0:
            net_col = Fore.LIGHTRED_EX
        else:
            net_col = Fore.WHITE
        net_str = f"{Fore.WHITE}({net_col}{'+' if net_change > 0 else ''}{net_change}ms changed{Fore.WHITE}){Style.RESET_ALL}" if net_change != 0 else ""
        print_and_log(f"{Fore.WHITE}Applied offset: {Fore.LIGHTYELLOW_EX}{offset}{Style.RESET_ALL}  {net_str}")
        print_and_log(f"{Fore.WHITE}Timestamp: {Fore.LIGHTYELLOW_EX}{timestamp}{Style.RESET_ALL}")
        print()
        for log in logs:
            print_and_log(log)
        if logs:
            print()
        print_and_log(f"{Fore.LIGHTYELLOW_EX}Apply as many corrections as you want, until the subtitle text matches the audio.{Style.RESET_ALL}")
        print_and_log(f"{Fore.CYAN}1{Style.RESET_ALL} = Open video file")
        print_and_log(f"{Fore.CYAN}2{Style.RESET_ALL} = Type in a correction..")
        if ms_restore != 0:
            restore_col = Fore.GREEN if ms_restore > 0 else Fore.LIGHTRED_EX
            restore_str = f"{Fore.WHITE}(applies {restore_col}{'+' if ms_restore > 0 else ''}{ms_restore}ms offset{Fore.WHITE}){Style.RESET_ALL}"
        else:
            restore_str = f"{Fore.WHITE}(no offset to restore){Style.RESET_ALL}"
        print_and_log(f"{Fore.CYAN}3{Style.RESET_ALL} = Restore original offset {restore_str}")
        print_and_log(f"{Fore.CYAN}4{Style.RESET_ALL} = Clear logs in terminal (only visual)")
        print_and_log(f"{Fore.CYAN}5{Style.RESET_ALL} = Mark as Drift {Fore.LIGHTBLACK_EX}(will download a new subtitle after all videos are checked){Style.RESET_ALL}")
        print_and_log(f"{Fore.CYAN}6{Style.RESET_ALL} = Done")
        print()
        choice = input(f"Choose [{Fore.CYAN}1-6{Style.RESET_ALL}]: ").strip()
        if choice == "1":
            video_path = os.path.join(folder, video)
            try:
                open_video_with_default_app(video_path)
                logs.append(f"{sync_tag()} {Fore.CYAN}Video file opened..{Style.RESET_ALL}")
            except Exception:
                logs.append(f"{sync_tag()} {Fore.LIGHTRED_EX}Could not automatically open the video. Please open it manually if needed.{Style.RESET_ALL}")
        elif choice == "2":
            corr = input(f"Enter correction in milliseconds (e.g: 100 or -100 to make it negative):").strip()
            try:
                ms = int(corr)
                if ms == 0:
                    logs.append(f"{sync_tag()} {Fore.YELLOW}No correction applied (0 ms).{Style.RESET_ALL}")
                elif not subtitle_name.lower().endswith('.srt'):
                    logs.append(f"{sync_tag()} {Fore.LIGHTRED_EX}Only .srt subtitles are supported for correction.{Style.RESET_ALL}")
                else:
                    success, message = apply_srt_offset(sub_path, ms)
                    if success:
                        net_change += ms
                        if ms > 0:
                            corr_col = Fore.GREEN
                            logs.append(f"{sync_tag()} {corr_col}Applied +{ms} ms, making the subtitles appear later{Style.RESET_ALL}")
                        else:
                            corr_col = Fore.LIGHTRED_EX
                            logs.append(f"{sync_tag()} {corr_col}Applied {ms} ms, making the subtitles appear earlier{Style.RESET_ALL}")
                    else:
                        logs.append(f"{sync_tag()} {Fore.LIGHTRED_EX}Unable to apply correction. {message} {Style.RESET_ALL}")
            except ValueError:
                logs.append(f"{sync_tag()} {Fore.LIGHTRED_EX}Invalid input: please enter a number (ms).{Style.RESET_ALL}")
        elif choice == "3":
            if not subtitle_name.lower().endswith('.srt'):
                logs.append(f"{sync_tag()} {Fore.LIGHTRED_EX}Only .srt subtitles are supported for restore{Style.RESET_ALL}")
            elif offset_restored:
                logs.append(f"{sync_tag()} {Fore.YELLOW}Unable to comply, offset was already restored..{Style.RESET_ALL}")
            else:
                if ms_restore == 0:
                    logs.append(f"{sync_tag()} {Fore.YELLOW}No original offset to restore (0 ms){Style.RESET_ALL}")
                else:
                    success, message = apply_srt_offset(sub_path, ms_restore)
                    
                    if success:
                        net_change += ms_restore
                        offset_restored = True
                        logs.append(f"{sync_tag()} {Fore.YELLOW}Original offset restored..{Style.RESET_ALL}")
                    else:
                        logs.append(f"{sync_tag()} {Fore.LIGHTRED_EX}Failed to restore original offset: {message}{Style.RESET_ALL}")
        elif choice == "4":
            logs.clear()
        elif choice == "5":
            while True:
                confirm = input(f"{Fore.LIGHTYELLOW_EX}Are you sure that you want to mark this file as drift? (y/n): {Style.RESET_ALL}").strip().lower()
                if confirm == "y":
                    orig_name = None
                    if os.path.exists(MOVIES_WITH_LINEAR_OFFSET_FILE):
                        with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'r', encoding='utf-8') as f:
                            entries = f.read().split('--\n')
                        for entry in entries:
                            if subtitle_name in entry:
                                lines = [l for l in entry.strip().splitlines() if l.strip()]
                                if lines:
                                    orig_name = lines[-1]
                                break
                    if orig_name and subtitle_name != orig_name and not orig_name.endswith(('.mkv', '.mp4', '.avi')):
                        orig_path = os.path.join(folder, orig_name)
                        if not os.path.exists(orig_path):
                            os.rename(sub_path, orig_path)
                            sub_path = orig_path
                            subtitle_name = orig_name
                    m = re.search(r'number(\d+)', subtitle_name)
                    if m:
                        num = int(m.group(1))
                    else:
                        num = None
                    mark_subtitle_as_drift(sub_path, lang='', create_copies=True)  
                    
                    remove_completed_entry_from_offset_file(title, folder, video)
                    print_and_log(f"{sync_tag()} {Fore.YELLOW}Removed offset entry from tracking file due to drift marking{Style.RESET_ALL}")
                    
                    drift_marked = True
                    drift_marked_in_menu = True
                    print_and_log(f"{Fore.LIGHTGREEN_EX}Drift marking completed successfully. Moving to next video.{Style.RESET_ALL}")
                    return
                elif confirm == "n":
                    print_and_log(f"{Fore.YELLOW}Cancelled drift marking.{Style.RESET_ALL}")
                    break
                else:
                    print_and_log(f"{Fore.RED}Invalid choice. Please enter y or n.{Style.RESET_ALL}")
        elif choice == "6":
            remove_completed_entry_from_offset_file(title, folder, video)
            break
        else:
            logs.append(f"{sync_tag()} {Fore.RED}Invalid choice. Please enter 1-6.{Style.RESET_ALL}")

if os.path.exists(MOVIES_WITH_LINEAR_OFFSET_FILE):
    print_and_log(f"\n{Fore.YELLOW}Manual verification file exists - some subtitles may need review{Style.RESET_ALL}")
    show_offset_verification_menu()

if drift_marked:
    os.system('cls' if os.name == 'nt' else 'clear')
    clear_and_print_ascii(BANNER_LINE)
    print_and_log(f"{sync_tag()} {Style.BRIGHT}{Fore.RED}DRIFT subtitles detected during manual verification! Acquisition will be started.{Style.RESET_ALL}\n")
    print_and_log(f"{sync_tag()} {Fore.YELLOW}This window will close automatically in {pause_seconds} seconds...{Style.RESET_ALL}")
    time.sleep(pause_seconds)
    os.system(f'python "{os.path.join(script_dir, "acquisition.py")}"')
    sys.exit(0)

print_and_log(f"\n{sync_tag()} {Fore.CYAN}Checking internal subtitle cleanup requirements...{Style.RESET_ALL}")

if PRESERVE_UNWANTED_SUBTITLES:
    print_and_log(f"{sync_tag()} {Fore.GREEN}Skipping internal subtitle cleanup - preserve_unwanted_subtitles is enabled{Style.RESET_ALL}")
    print_and_log(f"{sync_tag()} {Fore.CYAN}preserve_unwanted_subtitles: {PRESERVE_UNWANTED_SUBTITLES}{Style.RESET_ALL}")
else:
    print_and_log(f"{sync_tag()} {Fore.YELLOW}Internal subtitle cleanup enabled - preserve_unwanted_subtitles is false{Style.RESET_ALL}")
    print_and_log(f"{sync_tag()} {Fore.CYAN}Going through internal subtitle cleanup. This can take a while with many videos..{Style.RESET_ALL}")
    prompt_and_cleanup_internal_subs()

print_and_log(f"\n{sync_tag()} {Fore.CYAN}Performing final cleanup...{Style.RESET_ALL}")
final_cleanup_prompt_and_cleanup()

print_and_log(f"\n{sync_tag()} {Fore.CYAN}Performing final subtitle coverage scan...{Style.RESET_ALL}")
coverage_results = scan_subtitle_coverage(videos, LANGUAGES, show_progress=True, logger_func=print_and_log, sync_tag_func=sync_tag)
display_coverage_results(coverage_results, LANGUAGES, banner_line=BANNER_LINE, return_to_menu=True, logger_func=print_and_log, sync_tag_func=sync_tag)

clear_and_print_ascii(BANNER_LINE)
print_and_log(f"\n{Style.BRIGHT}{Fore.GREEN}✓ Subservient run COMPLETE!{Style.RESET_ALL}\n")

print_and_log(f"{Fore.LIGHTYELLOW_EX}Finishing touch:{Style.RESET_ALL}\nWant to rename internal subtitles, clean ads, promotional text, and unwanted content from your subtitles?")
print_and_log(f"Check out the main menu → option {Fore.GREEN}5{Style.RESET_ALL} '{Fore.CYAN}Extra tools{Style.RESET_ALL}' for a final polish!\n")

print_and_log(f"{Style.BRIGHT}Thank you so much for using Subservient!{Style.RESET_ALL}")
print_and_log(f"I hope this tool has made managing your subtitle collection a bit easier.")
print_and_log(f"If Subservient has been helpful to you, I'd be incredibly grateful for any support:")
print_and_log(f"{Fore.CYAN}https://buymeacoffee.com/nexigen{Style.RESET_ALL}")
print_and_log(f"\nEven the smallest contribution helps me keep improving this tool and provide")
print_and_log(f"better support for the community. But please, only if you can spare it!")
print_and_log(f"\n{Fore.GREEN}Thank you for being part of the Subservient community!{Style.RESET_ALL}")

print_and_log(f"\n{Fore.YELLOW}Press any key to exit...{Style.RESET_ALL}")
input()