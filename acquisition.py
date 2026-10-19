import os
import sys
import subprocess
import shutil

def check_required_packages():
    """Check if all required packages are installed and show install instructions if missing."""
    required_packages = ["colorama", "platformdirs", "requests"]
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    if missing:
        print("\n" + "="*60)
        print("  SUBSERVIENT ACQUISITION - PACKAGE REQUIREMENTS ERROR")
        print("="*60)
        print("\nThe following required packages are missing:")
        for pkg in missing:
            print(f"  - {pkg}")
        print(f"\nTo resolve this issue:")
        print(f"  1. Navigate to your main Subservient folder")
        print(f"  2. Run subordinate.py so that it automatically installs the required packages.")
        print(f"  3. If 2 is not happening, choose option '4' to install & verify requirements")
        print(f"  4. After installation, try running acquisition.py again")
        print(f"\nIf you don't have subordinate.py, please download the complete")
        print(f"Subservient package from the official source.")
        print("\n" + "="*60)
        input("Press Enter to exit...")
        sys.exit(1)
check_required_packages()
from pathlib import Path
import requests
import re
import json
import time
from colorama import Fore, Style
import datetime
from platformdirs import user_config_dir
from utils import ASCII_ART, clear_and_print_ascii, get_skip_dirs_from_config, has_strict_series_naming_pattern, extract_sxxexx_code, make_drift_metadata_key, load_drift_subtitle_metadata, detect_language_from_filename
from opensubtitles_hash import calculate_hash
SNAPSHOT_DIR = Path(__file__).parent.resolve()
DRIFT_METADATA_FILE = str(SNAPSHOT_DIR / '.drifted_and_failed_subtitles.txt')
BANNER_LINE = f"                   {Style.BRIGHT}{Fore.RED}[Phase 3/4]{Style.RESET_ALL} Subtitle Acquisition"
CONFIG_PATH = SNAPSHOT_DIR / '.config'
run_counter = 1
if CONFIG_PATH.exists():
    with CONFIG_PATH.open(encoding='utf-8') as f:
        for line in f:
            if line.strip().lower().startswith('run_counter') and '=' in line:
                try:
                    run_counter = int(line.split('=', 1)[1].strip())
                except Exception:
                    run_counter = 1
                break
LOGS_DIR = SNAPSHOT_DIR / 'logs' / f'Subservient-run-{run_counter}'
LOGS_DIR.mkdir(exist_ok=True)
existing_log = None
for fname in LOGS_DIR.iterdir():
    if fname.name.startswith('acquisition_log') and fname.name.endswith('.txt'):
        existing_log = fname
        break
if existing_log:
    LOG_FILE = existing_log
    with LOG_FILE.open('r+', encoding='utf-8') as f:
        content = f.read()
        part_count = content.count('Acquisition - part') + 1
        if f.tell() > 0:
            f.write('\n')
        f.write(f'Acquisition - part {part_count}\n')
else:
    log_time = datetime.datetime.now().strftime('%d-%m-%Y_%H.%M.%S')
    LOG_FILE = LOGS_DIR / f"acquisition_log_{log_time}.txt"
    with LOG_FILE.open('a', encoding='utf-8') as f:
        f.write(f'Acquisition - part 1\n')
ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m|\033\[[0-9;]*m')
def strip_ansi(text):
    """Remove ANSI color codes from text."""
    return ANSI_ESCAPE.sub('', text)

def acq_tag():
    """Return formatted acquisition tag for console output."""
    return f"{Style.BRIGHT}{Fore.BLUE}[Acquisition]{Style.RESET_ALL}"

def exit_with_prompt(message="Press any key to exit..."):
    """Display message and wait for user input before exiting."""
    try:
        input(f"{acq_tag()} {message}")
    except EOFError:
        os.system("pause")
    sys.exit(1)

with LOG_FILE.open('a+', encoding='utf-8') as f:
    f.write(strip_ansi(ASCII_ART) + '\n')
    banner = BANNER_LINE.replace('[Phase 3/4]', f'{Style.BRIGHT}{Fore.RED}[Phase 3/4]{Style.RESET_ALL}{Style.BRIGHT}')
    f.write(strip_ansi(banner) + '\n\n')

def print_and_log(msg, end='\n'):
    """Print message to console and write to log file."""
    print(msg, end=end)
    with LOG_FILE.open('a', encoding='utf-8') as f:
        f.write(strip_ansi(msg) + ('' if end == '' else end))

def print_and_log_colored(msg, color=Fore.WHITE, end='\n'):
    """Print colored message to console and log plain text to file."""
    print(f"{color}{msg}{Style.RESET_ALL}", end=end)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(strip_ansi(msg) + ('' if end == '' else end))
clear_and_print_ascii(BANNER_LINE)
def get_subservient_anchor():
    """Get the Subservient anchor directory from pathfiles config."""
    config_dir = Path(user_config_dir()) / "Subservient"
    pathfile = config_dir / "Subservient_pathfiles"
    if not pathfile.exists():
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"\033[1;31m[ERROR]\033[0m Subservient_pathfiles not found in your user config directory. Please run subordinate.py first.")
        exit_with_prompt()
    with open(pathfile, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("subservient_anchor="):
                return Path(line.split("=", 1)[1].strip())
    clear_and_print_ascii(BANNER_LINE)
    print_and_log(f"\033[1;31m[ERROR]\033[0m subservient_anchor not found in Subservient_pathfiles. Please run subordinate.py again.")
    exit_with_prompt()
clear_and_print_ascii(BANNER_LINE)
anchor_dir = get_subservient_anchor()
os.chdir(anchor_dir)
__file__ = str((anchor_dir / Path(__file__).name).resolve())
CONFIG_PATH = SNAPSHOT_DIR / '.config'
missing_queries = []
REQUIRED_SETUP_KEYS = [
    'api_url',
    'api_key',
    'username',
    'password',
    'languages',
    'subtitle_batch_size',
    'series_mode',
]
def parse_bool(val):
    """Convert string value to boolean."""
    return str(val).strip().lower() in ("true", "1", "yes", "on")

def read_setup_from_config():
    """Read configuration settings from .config file and validate required keys."""
    if not CONFIG_PATH.exists():
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"\033[1;31m[ERROR]\033[0m .config not found!\n\nCreate a valid config or reset it via subordinate.py.")
        exit_with_prompt()
    lines = CONFIG_PATH.read_text(encoding='utf-8').splitlines()
    setup = {}
    in_setup = False
    for line in lines:
        if line.strip().lower() == '[setup]':
            in_setup = True
            continue
        if in_setup:
            if line.strip().startswith('[') and line.strip().lower() != '[setup]':
                break
            if line.strip() and not line.strip().startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    setup[key.strip()] = value.strip().strip('"')
    missing = [k for k in REQUIRED_SETUP_KEYS if k not in setup or not setup[k]]
    if missing:
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"\033[1;31m[ERROR]\033[0m The following variables are missing or have no value in the [SETUP] section of .config:\n")
        for k in missing:
            print_and_log(f"  - {k}")
        print_and_log("\nPlease fix the config file or reconstruct the whole config using subordinate.py.")
        exit_with_prompt()
    setup['series_mode'] = parse_bool(setup['series_mode'])
    return setup
setup = read_setup_from_config()
PAUSE_SECONDS = float(setup.get("pause_seconds", 3))
API_URL = setup['api_url']
API_KEY = setup['api_key']
USERNAME = setup['username']
PASSWORD = setup['password']
LANGUAGES = [lang.strip() for lang in setup['languages'].split(',') if lang.strip()]
MAX_SEARCH_RESULTS = int(setup.get('max_search_results', 50))
SUBTITLE_BATCH_SIZE = int(setup['subtitle_batch_size'])
DOWNLOAD_RETRY_503 = int(setup.get('download_retry_503', 6))
SERIES_MODE = setup['series_mode']
USE_MOVIE_HASH = setup.get('use_movie_hash', 'true').lower() in ('true', '1', 'yes', 'on')
LAST_RESORT_SEARCH = setup.get('last_resort_search', 'false').lower() in ('true', '1', 'yes', 'on')
OMDB_API_KEY = setup.get('omdb_api_key', '').strip()

# Official IMDb title of the most recent successful OMDb lookup (None when there was no match)
_LAST_OMDB_TITLE = None

def get_imdb_id_from_omdb(title, year=None, max_retries=3, media_type='movie'):
    """
    Lookup IMDb ID using OMDb API with retry mechanism.
    
    Args:
        title: Movie/series title (e.g., "Eternals")
        year: Release year (e.g., "2021")
        max_retries: Number of retry attempts for errors (default: 3)
        media_type: 'movie' or 'series' (default: 'movie')
    
    Returns:
        IMDb ID (e.g., "tt9032400") or None if not found
    """
    global _LAST_OMDB_TITLE
    _LAST_OMDB_TITLE = None
    if not OMDB_API_KEY:
        return None
    
    for attempt in range(1, max_retries + 1):
        try:
            params = {
                't': title,
                'apikey': OMDB_API_KEY,
                'type': media_type
            }
            if year:
                params['y'] = year
            
            response = requests.get('http://www.omdbapi.com/', params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('Response') == 'True' and 'imdbID' in data:
                    imdb_id = data['imdbID']
                    _LAST_OMDB_TITLE = data.get('Title')
                    print_and_log(f"{acq_tag()} {Fore.GREEN}[OK] [OMDb]{Style.RESET_ALL} Found IMDb ID: {Fore.CYAN}{imdb_id}{Style.RESET_ALL} for '{title}' ({year})")
                    return imdb_id
                else:
                    error_msg = data.get('Error', 'Unknown error')
                    if media_type == 'series':
                        # Fallback 1: try without type restriction
                        params2 = {'t': title, 'apikey': OMDB_API_KEY}
                        if year:
                            params2['y'] = year
                        r2 = requests.get('http://www.omdbapi.com/', params=params2, timeout=5)
                        if r2.status_code == 200:
                            d2 = r2.json()
                            if d2.get('Response') == 'True' and 'imdbID' in d2:
                                imdb_id = d2['imdbID']
                                _LAST_OMDB_TITLE = d2.get('Title')
                                print_and_log(f"{acq_tag()} {Fore.GREEN}[OK] [OMDb fallback]{Style.RESET_ALL} Found IMDb ID: {Fore.CYAN}{imdb_id}{Style.RESET_ALL} for '{title}' ({year})")
                                return imdb_id
                        # Fallback 2: try possessive variants (e.g. "Handmaids" -> "Handmaid's", "Schitts" -> "Schitt's")
                        _SKIP_WORDS = {'is', 'was', 'has', 'its', 'this', 'as', 'us', 'yes', 'plus', 'times', 'series', 'across', 'always', 'perhaps', 'unless', 'whereas'}
                        _words = title.split()
                        for _i, _word in enumerate(_words):
                            if len(_word) > 3 and _word.lower().endswith('s') and _word.lower() not in _SKIP_WORDS:
                                _variant_words = _words.copy()
                                _variant_words[_i] = _word[:-1] + "'s"
                                _variant_title = ' '.join(_variant_words)
                                _pv = {'t': _variant_title, 'apikey': OMDB_API_KEY, 'type': media_type}
                                if year:
                                    _pv['y'] = year
                                _rv = requests.get('http://www.omdbapi.com/', params=_pv, timeout=5)
                                if _rv.status_code == 200:
                                    _dv = _rv.json()
                                    if _dv.get('Response') == 'True' and 'imdbID' in _dv:
                                        imdb_id = _dv['imdbID']
                                        _LAST_OMDB_TITLE = _dv.get('Title')
                                        print_and_log(f"{acq_tag()} {Fore.GREEN}[OK] [OMDb possessive fallback]{Style.RESET_ALL} Found IMDb ID: {Fore.CYAN}{imdb_id}{Style.RESET_ALL} for '{_variant_title}' ({year})")
                                        return imdb_id
                        # Fallback 3: use OMDb s= search as last resort
                        params3 = {'s': title, 'apikey': OMDB_API_KEY}
                        r3 = requests.get('http://www.omdbapi.com/', params=params3, timeout=5)
                        if r3.status_code == 200:
                            d3 = r3.json()
                            if d3.get('Response') == 'True' and d3.get('Search'):
                                for hit in d3['Search']:
                                    if hit.get('Type') in ('series', 'movie') and 'imdbID' in hit:
                                        imdb_id = hit['imdbID']
                                        _LAST_OMDB_TITLE = hit.get('Title')
                                        print_and_log(f"{acq_tag()} {Fore.GREEN}[OK] [OMDb search fallback]{Style.RESET_ALL} Found IMDb ID: {Fore.CYAN}{imdb_id}{Style.RESET_ALL} for '{hit.get('Title')}' ({hit.get('Year')})")
                                        return imdb_id
                    print_and_log(f"{acq_tag()} {Fore.YELLOW}[OMDb] No IMDb ID found: {error_msg}{Style.RESET_ALL}")
                    return None
            else:
                # HTTP error - retry
                if attempt < max_retries:
                    print_and_log(f"{acq_tag()} {Fore.YELLOW}[OMDb] API returned status {response.status_code}. Retrying... (attempt {attempt}/{max_retries}){Style.RESET_ALL}")
                    time.sleep(2)  # Wait before retry
                    continue
                else:
                    print_and_log(f"{acq_tag()} {Fore.YELLOW}[OMDb] API returned status {response.status_code} after {max_retries} attempts{Style.RESET_ALL}")
                    return None
        except Exception as e:
            # Exception - retry
            if attempt < max_retries:
                print_and_log(f"{acq_tag()} {Fore.YELLOW}[OMDb] Lookup failed: {str(e)}. Retrying... (attempt {attempt}/{max_retries}){Style.RESET_ALL}")
                time.sleep(2)  # Wait before retry
                continue
            else:
                print_and_log(f"{acq_tag()} {Fore.YELLOW}[OMDb] Lookup failed after {max_retries} attempts: {str(e)}{Style.RESET_ALL}")
                return None
    
    return None

def get_episode_imdb_id_from_omdb(show_title, season, episode):
    """
    Lookup the episode-specific IMDb ID using OMDb API (Season/Episode params).
    Returns IMDb ID string (e.g. "tt7435248") or None.
    """
    if not OMDB_API_KEY:
        return None
    # Try with possessive variants if needed (same logic as show lookup)
    titles_to_try = [show_title]
    _SKIP_WORDS = {'is', 'was', 'has', 'its', 'this', 'as', 'us', 'yes', 'plus', 'times', 'series', 'across', 'always', 'perhaps', 'unless', 'whereas'}
    _words = show_title.split()
    for _i, _word in enumerate(_words):
        if len(_word) > 3 and _word.lower().endswith('s') and _word.lower() not in _SKIP_WORDS:
            _variant_words = _words.copy()
            _variant_words[_i] = _word[:-1] + "'s"
            titles_to_try.append(' '.join(_variant_words))
    for title in titles_to_try:
        try:
            params = {
                't': title,
                'Season': season,
                'Episode': episode,
                'apikey': OMDB_API_KEY,
            }
            r = requests.get('http://www.omdbapi.com/', params=params, timeout=5)
            if r.status_code == 200:
                d = r.json()
                if d.get('Response') == 'True' and 'imdbID' in d:
                    ep_id = d['imdbID']
                    print_and_log(f"{acq_tag()} {Fore.GREEN}[OK] [OMDb episode]{Style.RESET_ALL} Found episode IMDb ID: {Fore.CYAN}{ep_id}{Style.RESET_ALL} for '{title}' S{season:02d}E{episode:02d}")
                    return ep_id
        except Exception:
            pass
    return None

_KEEP_BEFORE_YEAR_TERMS = {'extended', 'remastered'}

def lookup_imdb_id_leading(title, year=None, media_type='movie'):
    """OMDb lookup with the lenient title first; if that finds nothing, retry once with all unwanted terms removed."""
    imdb_id = get_imdb_id_from_omdb(title, year, media_type=media_type)
    if imdb_id:
        return imdb_id
    strict_terms = {t.lower() for t in get_unwanted_terms_from_config()} - _KEEP_BEFORE_YEAR_TERMS
    strict_words = [w for w in title.split() if re.sub(r"[^a-z0-9]", "", w.lower()) not in strict_terms]
    strict_title = ' '.join(strict_words).strip()
    if strict_title and strict_title.lower() != title.strip().lower():
        print_and_log(f"{acq_tag()} {Fore.LIGHTBLACK_EX}[OMDb] Retrying with stricter title '{strict_title}'{Style.RESET_ALL}")
        return get_imdb_id_from_omdb(strict_title, year, media_type=media_type)
    return None

def refine_query_with_imdb_title(raw_title, query):
    """Movies only: after an IMDb match, rebuild the text query so that unwanted-term words are kept only
    when they are part of the official IMDb title. Without a match the query is returned unchanged."""
    if SERIES_MODE or not _LAST_OMDB_TITLE:
        return query
    try:
        official = {re.sub(r"[^a-z0-9]", "", w.lower()) for w in _LAST_OMDB_TITLE.split()}
        official.discard('')
        refined = remove_all_short_numbers(build_search_query(raw_title, official_words=official))
        return refined if refined.strip() else query
    except Exception:
        return query

def detect_subtitle_folder(video_folder: Path, season_code: str, language: str):
    """
    Detect subtitle folder for specific season and language (SUBTITLES.Sxx.LANG format).
    Returns folder path or None.
    """
    if not video_folder.exists():
        return None
        
    # Look for SUBTITLES.Sxx.LANG folders or ZIP files (case insensitive)
    target_folder_name = f"subtitles.{season_code}.{language}".lower()
    target_zip_name = f"subtitles.{season_code}.{language}.zip".lower()
    
    for item in video_folder.iterdir():
        if item.is_dir() and item.name.lower() == target_folder_name:
            return item
        elif item.is_file() and item.name.lower() == target_zip_name:
            return item
                    
    return None

def validate_season_episodes_match(video_folder: Path, season_code: str):
    """
    Validate that video files match the detected season code.
    Returns True if valid, False if mismatch found.
    """
    
    # Get all video files in the folder
    video_extensions = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv'}
    video_files = [f for f in video_folder.iterdir() 
                   if f.is_file() and f.suffix.lower() in video_extensions]
    
    if not video_files:
        return True  # No videos to validate
        
    mismatched_files = []
    
    for video_file in video_files:
        # Check if file has series naming pattern
        if has_strict_series_naming_pattern(video_file.name):
            # Extract season code from video filename (returns SxxExx format)
            video_sxxexx_code = extract_sxxexx_code(video_file.name)
            if video_sxxexx_code:
                # Extract just the season part (first 3 characters: "S01" from "S01E01")
                video_season_part = video_sxxexx_code[:3]  # "S01E01" -> "S01"
                
                # Compare season parts only (case insensitive)
                if video_season_part.upper() != season_code.upper():
                    mismatched_files.append((video_file.name, video_season_part, season_code))
                    
    if mismatched_files:
        # Display detailed error message
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"{Fore.RED}{Style.BRIGHT}[ERROR] Season Code Mismatch Detected!{Style.RESET_ALL}\n")
        print_and_log(f"A subtitle download folder was found, but the video files don't match the season code:\n")
        print_and_log(f"  {Fore.YELLOW}Season folder detected:{Style.RESET_ALL} SUBTITLES.{season_code}")
        print_and_log(f"  {Fore.YELLOW}Expected video pattern:{Style.RESET_ALL} *{season_code}E*\n")
        print_and_log(f"{Fore.RED}Mismatched files found:{Style.RESET_ALL}")
        for filename, video_season, expected_season in mismatched_files:
            print_and_log(f"  - {filename}")
            print_and_log(f"    {Fore.RED}Found season:{Style.RESET_ALL} {video_season} {Fore.RED}Expected:{Style.RESET_ALL} {expected_season}")
            
        print_and_log(f"\n{Fore.YELLOW}Possible solutions:{Style.RESET_ALL}")
        print_and_log(f"  1. Rename the SUBTITLES folder to match your video files")
        print_and_log(f"  2. Move video files to the correct season folder") 
        print_and_log(f"  3. Remove the SUBTITLES folder if not needed\n")
        print_and_log(f"{Fore.RED}Subservient in TV-Series mode cannot proceed with mismatched season codes.{Style.RESET_ALL}")
        
        exit_with_prompt("Press Enter to exit...")
        return False
        
    return True

def check_for_language_mismatch_error(video_folder: Path, season_code: str, requested_language: str):
    """
    Check if there are SUBTITLES folders that are improperly configured.
    If found, show error and exit.
    """
    # Look for ANY SUBTITLES folders or ZIP files
    subtitle_pattern = f"subtitles.{season_code}.".lower()
    old_pattern_exact = f"subtitles.{season_code}".lower()  # Exact match for season without language
    found_folders = []
    incomplete_folders = []
    wrong_season_folders = []
    
    for item in video_folder.iterdir():
        item_name_lower = item.name.lower()
        if (item.is_dir() or item.name.lower().endswith('.zip')):
            # Check if this is any SUBTITLES folder
            if item_name_lower.startswith('subtitles.s') and ('s01' in item_name_lower or 's02' in item_name_lower or 's03' in item_name_lower or 's04' in item_name_lower or 's05' in item_name_lower):
                # Extract season from folder name
                season_match = re.search(r'subtitles\\.(s\\d{2})', item_name_lower)
                if season_match:
                    folder_season = season_match.group(1).upper()
                    
                    if folder_season != season_code.upper():
                        # Wrong season detected
                        wrong_season_folders.append((item.name, folder_season))
                    else:
                        # Correct season, check language
                        if item.is_dir() and item_name_lower == old_pattern_exact:
                            incomplete_folders.append(item.name)
                        elif item.is_file() and item_name_lower == f"{old_pattern_exact}.zip":
                            incomplete_folders.append(item.name)
                        elif item_name_lower.startswith(subtitle_pattern):
                            # Extract language part
                            if item.is_dir():
                                lang_part = item.name[len(f"SUBTITLES.{season_code}."):]
                            else:  # ZIP file
                                lang_part = item.name[len(f"SUBTITLES.{season_code}."):-4]  # Remove .zip
                                
                            if lang_part and lang_part.upper() != requested_language.upper():
                                found_folders.append((item.name, lang_part.upper()))
    
    if wrong_season_folders or incomplete_folders or found_folders:
        # Display error message
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"{Fore.RED}{Style.BRIGHT}[ERROR] Subtitle Folder Configuration Error!{Style.RESET_ALL}\\n")
        
        if wrong_season_folders:
            print_and_log(f"Subtitle folder(s) found with wrong season code:\\n")
            print_and_log(f"{Fore.RED}Wrong season folders:{Style.RESET_ALL}")
            for folder_name, folder_season in wrong_season_folders:
                print_and_log(f"  - {folder_name} (Found: {folder_season}, Expected: {season_code})")
            print_and_log(f"\\n{Fore.YELLOW}Expected season:{Style.RESET_ALL} {season_code}")
            print_and_log(f"{Fore.YELLOW}Video files contain:{Style.RESET_ALL} {season_code}E01, {season_code}E02, etc.\\n")
        
        if incomplete_folders:
            print_and_log(f"Subtitle folder(s) found without language specification:\\n")
            print_and_log(f"{Fore.YELLOW}Incomplete folders:{Style.RESET_ALL}")
            for folder_name in incomplete_folders:
                print_and_log(f"  - {folder_name} (Missing language specification)")
            print_and_log(f"\\n{Fore.YELLOW}Required format:{Style.RESET_ALL} SUBTITLES.{season_code}.LANGUAGE")
            print_and_log(f"{Fore.YELLOW}Example:{Style.RESET_ALL} SUBTITLES.{season_code}.{requested_language.upper()}\\n")
        
        if found_folders:
            print_and_log(f"Subtitle folder(s) found for season {season_code}, but not for language '{requested_language.upper()}':\\n")
            print_and_log(f"{Fore.YELLOW}Found folders:{Style.RESET_ALL}")
            for folder_name, lang in found_folders:
                print_and_log(f"  - {folder_name} (Language: {lang})")
            print_and_log(f"\\n{Fore.YELLOW}Requested language:{Style.RESET_ALL} {requested_language.upper()}")
            print_and_log(f"{Fore.YELLOW}Expected folder name:{Style.RESET_ALL} SUBTITLES.{season_code}.{requested_language.upper()}\\n")
        
        print_and_log(f"{Fore.YELLOW}Possible solutions:{Style.RESET_ALL}")
        print_and_log(f"  1. Rename subtitle folder(s) to match the correct season and language")
        print_and_log(f"  2. Create a subtitle folder for season {season_code} and language '{requested_language.upper()}'") 
        print_and_log(f"  3. Remove the subtitle folders if not needed\\n")
        print_and_log(f"{Fore.RED}Subservient in TV-Series mode cannot proceed with improper folder configuration.{Style.RESET_ALL}")
        
        exit_with_prompt("Press Enter to exit...")

def check_subtitle_folder_coverage(video_file: Path, language: str):
    """
    Check if video is covered by pre-downloaded subtitle folder for specific language.
    Returns True if covered (skip download), False if not covered (proceed with download).
    """
    video_folder = video_file.parent
    
    # Extract season code from video filename
    sxxexx_code = extract_sxxexx_code(video_file.name)
    if not sxxexx_code:
        return False  # Not a series file
        
    season_code = sxxexx_code[:3]  # "S01E01" -> "S01"
    episode_code = sxxexx_code[3:]  # "S01E01" -> "E01"
    
    print_and_log(f"{acq_tag()} {Fore.CYAN}Searching for pre-downloaded subtitle folder...{Style.RESET_ALL}")
    
    # Look for subtitle folder for this season and language
    subtitle_folder = detect_subtitle_folder(video_folder, season_code, language)
    
    if not subtitle_folder:
        print_and_log(f"{acq_tag()} {Fore.YELLOW}No subtitle folder found for '{video_file.stem}' [{season_code}] [{language.upper()}]{Style.RESET_ALL}")
        return False  # No folder found, proceed with normal download
        
    print_and_log(f"{acq_tag()} {Fore.GREEN}Subtitle folder found for '{video_file.stem}' [{season_code}] [{language.upper()}]{Style.RESET_ALL}")
    
    # Validate season consistency first
    if not validate_season_episodes_match(video_folder, season_code):
        return False  # Validation failed, function exits the program
        
    print_and_log(f"{acq_tag()} {Fore.CYAN}Checking if all episodes are covered...{Style.RESET_ALL}")
    
    # Get all episodes in this season from video files
    all_episodes = get_all_season_episodes(video_folder, season_code)
    
    # Check coverage for all episodes
    covered_episodes = []
    missing_episodes = []
    
    for ep_code in all_episodes:
        if check_episode_coverage_in_folder(subtitle_folder, ep_code, language):
            covered_episodes.append(ep_code)
        else:
            missing_episodes.append(ep_code)
    
    # Log results
    if missing_episodes:
        print_and_log(f"{acq_tag()} {Fore.YELLOW}Episodes found for [{season_code}] [{language.upper()}], but some are still missing:{Style.RESET_ALL}")
        for missing in missing_episodes:
            print_and_log(f"{acq_tag()} {Fore.YELLOW}  - {missing}{Style.RESET_ALL}")
        print_and_log(f"{acq_tag()} {Fore.YELLOW}These episodes will still be manually downloaded.{Style.RESET_ALL}")
        
        # Return True only if THIS episode is covered
        return sxxexx_code in covered_episodes
    else:
        print_and_log(f"{acq_tag()} {Fore.GREEN}All episodes covered for [{season_code}] [{language.upper()}]{Style.RESET_ALL}")
        return True

def get_all_season_episodes(video_folder: Path, season_code: str) -> list:
    """
    Get all episode codes (S01E01, S01E02, etc.) for a given season from video files.
    """
    video_extensions = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv'}
    episodes = []
    
    for video_file in video_folder.iterdir():
        if video_file.is_file() and video_file.suffix.lower() in video_extensions:
            if has_strict_series_naming_pattern(video_file.name):
                sxxexx_code = extract_sxxexx_code(video_file.name)
                if sxxexx_code and sxxexx_code.startswith(season_code):
                    episodes.append(sxxexx_code)
                    
    return sorted(list(set(episodes)))  # Remove duplicates and sort

def check_episode_coverage_in_folder(subtitle_folder: Path, sxxexx_code: str, language: str) -> bool:
    """
    Check if a specific episode has subtitle coverage.
    After extraction process, we check for extracted subtitles in the video folder instead.
    """
    # If it's a ZIP file, we can't check inside it easily, so skip the check
    # Our extraction process will have already handled ZIP files
    if subtitle_folder.is_file() and subtitle_folder.name.lower().endswith('.zip'):
        # For ZIP files, check if extracted subtitles exist in parent directory
        parent_dir = subtitle_folder.parent
        extracted_pattern = f"*.{language.lower()}.number*.{sxxexx_code}.srt"
        extracted_files = list(parent_dir.glob(extracted_pattern))
        return len(extracted_files) > 0
    
    # If it's not a directory, skip
    if not subtitle_folder.is_dir():
        # Check for extracted subtitles in the same directory as the folder
        parent_dir = subtitle_folder.parent
        extracted_pattern = f"*.{language.lower()}.number*.{sxxexx_code}.srt"
        extracted_files = list(parent_dir.glob(extracted_pattern))
        return len(extracted_files) > 0
        
    # For directory subtitle folders, first check for extracted subtitles in parent
    parent_dir = subtitle_folder.parent
    extracted_pattern = f"*.{language.lower()}.number*.{sxxexx_code}.srt"
    extracted_files = list(parent_dir.glob(extracted_pattern))
    if extracted_files:
        return True
        
    # Fallback to checking inside the subtitle folder (original logic)
    subtitle_extensions = {'.srt', '.sub', '.vtt', '.ass', '.ssa'}
    
    # Look for subtitle files matching this episode
    for item in subtitle_folder.iterdir():
        if item.is_file() and item.suffix.lower() in subtitle_extensions:
            # Check if filename contains the episode code and language
            if (sxxexx_code.lower() in item.name.lower() and 
                language.lower() in item.name.lower()):
                return True
                
    return False

def write_runtime_blocks_to_config(token=None, skipped_entries=None):
    """Write runtime configuration blocks to config file."""
    SEP = '--'
    TOKEN_COMMENT = 'JWT token for OpenSubtitles API. Acquisition.py will update this automatically.'
    TOKEN_TAG = '[token]'
    SKIPPED_COMMENT = 'List of movies that were skipped manually. Remove an entry below in order to make it appear again.'
    SKIPPED_TAG = '[skipped_movies]'
    RUNTIME_TAG = '[RUNTIME]'
    if not CONFIG_PATH.exists():
        lines = []
    else:
        lines = CONFIG_PATH.read_text(encoding='utf-8').splitlines()
    out = []
    for line in lines:
        if line.strip().lower() == RUNTIME_TAG.lower():
            out.append(line)
            break
        out.append(line)
    if out and out[-1].strip():
        out.append('')
    runtime_blocks = []
    if token is None:
        token = get_token_from_config()
    runtime_blocks.append(SEP)
    runtime_blocks.append(TOKEN_COMMENT)
    runtime_blocks.append(TOKEN_TAG)
    if token:
        runtime_blocks.append(token)
    else:
        runtime_blocks.append("")
    if skipped_entries is None:
        skipped_movies_dict = get_skipped_movies_from_config()
        skipped_entries_set = set()
        for path, languages in skipped_movies_dict.items():
            if languages:
                lang_str = ','.join(sorted(languages)).upper()
                skipped_entries_set.add(f"{path} [{lang_str}]")
        skipped_entries = skipped_entries_set
    runtime_blocks.append(SEP)
    runtime_blocks.append(SKIPPED_COMMENT)
    runtime_blocks.append(SKIPPED_TAG)
    for entry in sorted(skipped_entries):
        runtime_blocks.append(entry)
    out = [line.rstrip() for line in out]
    while out and not out[-1].strip():
        out.pop()
    if out and out[-1].strip():
        out.append('')
    out.extend(runtime_blocks)
    out.append('')
    CONFIG_PATH.write_text('\n'.join(out), encoding='utf-8')
def set_token_in_config(token):
    """Store JWT token in config file."""
    write_runtime_blocks_to_config(token=token)

def get_token_from_config():
    """Retrieve JWT token from config file."""
    if not CONFIG_PATH.exists():
        return None
    lines = CONFIG_PATH.read_text(encoding='utf-8').splitlines()
    for i, line in enumerate(lines):
        if line.strip() == '[token]':
            j = i + 1
            while j < len(lines):
                value = lines[j].strip()
                if value and not value.startswith('[') and not value.startswith('--') and not value.startswith('#'):
                    return value
                elif value.startswith('[') or value.startswith('--'):
                    break
                j += 1
        elif line.strip().startswith('token ='):
            parts = line.split('=', 1)
            if len(parts) == 2:
                return parts[1].strip()
    return None

_jwt_token_cache = None

def get_jwt_token():
    """Obtain JWT token through API authentication."""
    global _jwt_token_cache
    if _jwt_token_cache:
        return _jwt_token_cache
    print_and_log(f"{acq_tag()} * Logging in to OpenSubtitles to get a fresh JWT token...")
    login_url = f"{API_URL}/login"
    login_headers = {
        "Api-Key": API_KEY,
        "Content-Type": "application/json",
        "User-Agent": "Subservient v0.85"
    }
    login_payload = {
        "username": USERNAME,
        "password": PASSWORD
    }
    response = requests.post(
        login_url,
        headers=login_headers,
        json=login_payload
    )
    time.sleep(0.5)
    if response.status_code == 200:
        json_data = response.json()
        token = json_data.get("token")
        if token:
            _jwt_token_cache = token
            set_token_in_config(token)
            print_and_log(f"{acq_tag()} * New JWT token saved to .config.")
            return token
    elif response.status_code == 429:
        print_and_log(f"{acq_tag()} 429: Too many requests. Waiting 10 seconds...")
        time.sleep(10)
        return get_jwt_token()
    elif response.status_code == 403:
        handle_api_error(response, {
            "URL": login_url,
            "Headers": login_headers,
            "Payload": login_payload
        })
        return None
    else:
        print_and_log(f"{acq_tag()} OpenSubtitles login error: {response.status_code}")
        print_and_log(f"{acq_tag()} Response:")
        print_and_log(response.text)
        return None

def get_unwanted_terms_from_config():
    """Read unwanted_terms setting from config file."""
    if not CONFIG_PATH.exists():
        return []
    lines = CONFIG_PATH.read_text(encoding='utf-8').splitlines()
    for line in lines:
        if line.strip().lower().startswith('unwanted_terms') and '=' in line:
            _, value = line.split('=', 1)
            return [term.strip().strip('"') for term in value.split(',') if term.strip()]
    return []
UNWANTED_TERMS = get_unwanted_terms_from_config()

# Purely technical terms that are always removed. Other unwanted terms (e.g. release group names such as "kingdom")
# are kept when they appear before the year / SxxExx, because there they are almost certainly part of the title.
ALWAYS_REMOVE_TERMS = {
    '720p', '1080p', '2160p', '480p', '576p', '4k', '5k', '8k', 'uhd',
    'web', 'webrip', 'web-dl', 'bluray', 'brrip', 'bdrip', 'dvdrip', 'hdrip', 'hdtv', 'remux',
    'x264', 'x265', 'h.264', 'h.265', 'h264', 'h265', 'hevc', 'avc', 'xvid', 'divx',
    'hdr', 'hdr10', 'hdr10+', 'dv', 'sdr', '10bit', '8bit',
    'ddp', 'dd+', 'dts', 'aac', 'ac3', 'eac3', 'truehd', 'atmos', 'flac', 'opus', 'mp3', '5.1', '7.1', '2.0',
    'mkv', 'mp4', 'avi', 'wmv', 'm4v', 'mov', 'flv', 'webm',
    'unrated', 'uncut', 'repack', 'proper', 'internal', 'limited', 'dubbed', 'subbed', 'multi', 'dual.audio',
    'eng', 'ita', 'jap', 'hindi', 'nl', 'en', 'sub', 'subs', 'rip', 'ac',
    'amzn', 'nf', 'nflx', 'dsnp',
}
_TITLE_ANCHOR = re.compile(r'(?<![0-9])(?:19|20)\d{2}(?![0-9])|[sS]\d{1,2}[eE]\d{1,3}')

def clean_title(raw_title: str, all_before_anchor: bool = False, official_words=None) -> str:
    """Clean and normalize video title for subtitle searching.

    Unwanted terms that are not purely technical are kept when they occur before the year / SxxExx
    (title part). all_before_anchor=True means raw_title already is only that title part.
    official_words (IMDb title words, lowercase) makes the title part strict: unwanted terms are removed
    unless they are in the official title (extended/remastered are always kept)."""
    UNWANTED_TERMS = get_unwanted_terms_from_config()
    UNWANTED_CHARS = r"[\[\]\(\)\{\}_\+\.-]"
    WHITELIST = {"a", "i", "z", "o", "u"}
    cleaned = raw_title.replace('.', ' ')
    def _unwanted_pattern(terms):
        if not terms:
            return None
        # Longest first so 'web-dl' is matched before 'web' (which would leave 'DL' behind)
        return r"\b(" + "|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True)) + r")\b"
    if all_before_anchor:
        anchor_pos = len(cleaned)
    else:
        anchor = _TITLE_ANCHOR.search(cleaned)
        anchor_pos = anchor.start() if anchor and anchor.start() > 0 else 0
    head, tail = cleaned[:anchor_pos], cleaned[anchor_pos:]
    if official_words is not None:
        head_terms = [t for t in UNWANTED_TERMS
                      if t.lower() not in _KEEP_BEFORE_YEAR_TERMS
                      and re.sub(r"[^a-z0-9]", "", t.lower()) not in official_words]
        head_terms += [t for t in ALWAYS_REMOVE_TERMS
                       if t not in UNWANTED_TERMS and t not in head_terms
                       and re.sub(r"[^a-z0-9]", "", t) not in official_words]
    else:
        head_terms = [t for t in UNWANTED_TERMS if t.lower() in ALWAYS_REMOVE_TERMS]
    for part_terms, is_head in ((head_terms, True), (UNWANTED_TERMS, False)):
        pattern = _unwanted_pattern(part_terms)
        if not pattern:
            continue
        if is_head:
            head = re.sub(pattern, "", head, flags=re.IGNORECASE)
        else:
            tail = re.sub(pattern, "", tail, flags=re.IGNORECASE)
    cleaned = head + tail
    cleaned = re.sub(r"[\[\(\{][^\]\)\}]*[\]\)\}]", "", cleaned)
    # Remove large numbers (≥100) except years (19xx/20xx)
    # This keeps sequel numbers (1-99) and years, removes resolution/bitrate
    cleaned = re.sub(r"\b(?!(?:19|20)\d{2}\b)(?:[1-9]\d{2,})\b", "", cleaned)
    cleaned = re.sub(UNWANTED_CHARS, " ", cleaned)
    # Keep letters, digits (0-9), special fraction characters, and spaces
    cleaned = re.sub(r"[^a-zA-Z0-9\u00BC-\u00BE\u2150-\u215E ]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    words = cleaned.split()
    result = []
    for i, word in enumerate(words):
        if len(word) == 1 and word.lower() not in WHITELIST:
            left = words[i-1] if i > 0 else ''
            right = words[i+1] if i < len(words)-1 else ''
            if (len(left) > 1 or len(right) > 1):
                result.append(word)
        else:
            result.append(word)
    cleaned = ' '.join(result)
    cleaned = re.sub(r"([a-zA-Z])\1{2,}", r"\1", cleaned)
    cleaned = re.sub(r"\\s+", " ", cleaned)
    return cleaned.strip()


def check_existing_subtitles_silent(mkv_path: Path) -> dict:
    """Check which subtitle languages already exist for video file (no logging)."""
    base = mkv_path.with_suffix('')
    result = {}
    
    for lang in LANGUAGES:
        # Check standard naming: filename.lang.srt
        standard_srt = base.with_name(f"{base.name}.{lang}.srt")
        
        # Check series naming if in series mode
        series_srt = None
        if SERIES_MODE:
            sxxexx_code = extract_sxxexx_code(mkv_path.name)
            if sxxexx_code:
                # Check if video filename already contains the episode code
                if sxxexx_code.lower() in base.name.lower():
                    # Video already has SxxExx in name, subtitle should use standard naming
                    series_srt = base.with_name(f"{base.name}.{lang}.srt")
                else:
                    # Video doesn't have SxxExx, subtitle should have SxxExx before language
                    series_srt = base.with_name(f"{base.name}.{sxxexx_code}.{lang}.srt")
        
        # Check if we have any good subtitles (not DRIFT/FAILED)
        has_standard = standard_srt.exists()
        has_series = series_srt.exists() if series_srt else False
        
        result[lang] = has_standard or has_series
    
    return result

def check_existing_subtitles(mkv_path: Path) -> dict:
    """Check which subtitle languages already exist for video file."""
    base = mkv_path.with_suffix('')
    result = {}
    
    print_and_log(f"{acq_tag()} {Fore.CYAN}  - Checking existing subtitles for:{Style.RESET_ALL} {mkv_path.name}")
    
    for lang in LANGUAGES:
        # Check standard naming: filename.lang.srt
        standard_srt = base.with_name(f"{base.name}.{lang}.srt")
        
        # Check series naming if in series mode
        series_srt = None
        if SERIES_MODE:
            sxxexx_code = extract_sxxexx_code(mkv_path.name)
            if sxxexx_code:
                # Check if video filename already contains the episode code
                if sxxexx_code.lower() in base.name.lower():
                    # Video already has SxxExx in name, subtitle should use standard naming
                    series_srt = base.with_name(f"{base.name}.{lang}.srt")
                else:
                    # Video doesn't have SxxExx, subtitle should have SxxExx before language
                    series_srt = base.with_name(f"{base.name}.{sxxexx_code}.{lang}.srt")
        
        # Check if we have any good subtitles (not DRIFT/FAILED)
        has_standard = standard_srt.exists()
        has_series = series_srt.exists() if series_srt else False
        
        # CRITICAL FIX: Only count as "complete" if we have a FINAL subtitle
        # Having only DRIFT files means we need MORE downloads, not skip!
        result[lang] = has_standard or has_series
        
        if has_standard or has_series:
            print_and_log(f"{acq_tag()} {Fore.GREEN}    [OK] {lang.upper()}:{Style.RESET_ALL} subtitle found")
        else:
            print_and_log(f"{acq_tag()} {Fore.YELLOW}    - {lang.upper()}:{Style.RESET_ALL} no subtitle found")
    return result

def extract_sxxexx_code(name: str) -> str | None:
    """Extract season/episode code from filename."""
    # Episode allows up to 3 digits (e.g. "S06E001") so it isn't truncated to just the first 2 digits
    match = re.search(r"[sS](\d{1,2})[eE](\d{1,3})", name)
    return f"S{int(match.group(1)):02d}E{int(match.group(2)):02d}" if match else None

def _find_episode_number_loosely(name: str) -> int | None:
    """Try common episode-number notations other than 'SxxExx' and 'episode N'
    (e.g. '1x01', 'Ep.01', 'Ep 1', 'Aflevering 1'). Returns the episode number, or None."""
    for pattern in (
        r'\d{1,2}x(\d{1,2})',           # 1x01
        r'ep\.?\s*(\d{1,2})\b',         # Ep.01 / Ep 1 / Ep01
        r'aflevering\s*(\d{1,2})',      # Dutch: Aflevering 1
    ):
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None

unknown_sxxexx_files = []
quota_exceeded = False

def show_quota_exceeded_screen():
    """Show a friendly screen when the OpenSubtitles daily download quota is reached.
    Loops until the user chooses to retry (which lets the caller re-attempt) or exit.
    Returns True if the user wants to retry, False if they want to exit.
    """
    while True:
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"\n{Style.BRIGHT}{Fore.CYAN}Daily Download Quota Reached{Style.RESET_ALL}\n")
        print_and_log(f"OpenSubtitles allows a limited number of subtitle downloads per 24 hours.")
        print_and_log(f"It looks like that limit has been reached for today.\n")
        print_and_log(f"{Fore.LIGHTYELLOW_EX}The quota resets 24 hours after your first download of the day.{Style.RESET_ALL}")
        print_and_log(f"{Fore.LIGHTYELLOW_EX}You can come back later and press Retry to continue where you left off.{Style.RESET_ALL}\n")
        print_and_log(f"{Fore.CYAN}1{Style.RESET_ALL} = {Style.BRIGHT}Retry {Fore.LIGHTBLACK_EX}(try again now or after the quota has reset){Style.RESET_ALL}")
        print_and_log(f"{Fore.CYAN}2{Style.RESET_ALL} = Exit Subservient\n")
        choice = input_and_log(f"Make a choice [{Fore.CYAN}1{Style.RESET_ALL}/{Fore.CYAN}2{Style.RESET_ALL}]: ").strip()
        if choice in ('1', ''):
            return True
        elif choice == '2':
            print_and_log(f"\n{acq_tag()} {Fore.CYAN}Closing Subservient. Run again when the quota has reset.{Style.RESET_ALL}")
            sys.exit(0)
        else:
            print_and_log(f"{Fore.RED}Invalid choice. Please enter 1 or 2.{Style.RESET_ALL}")

def download_top_subtitles(subs, lang, dest_folder, jwt_token, mkv_path=None, candidate_index=None, force_download=False, results=None):
    """Download the top-rated subtitles for specified language and video.
    When a results list is given, stored files are appended as (index, file_name, downloads) instead of printed."""
    global unknown_sxxexx_files, quota_exceeded
    headers = {
        "Api-Key": API_KEY,
        "User-Agent": "NexigenSubtitleBot v1.0",
        "Authorization": f"Bearer {jwt_token}"
    }
    sxxexx_from_mkv = None
    if SERIES_MODE and mkv_path is not None:
        sxxexx_from_mkv = extract_sxxexx_code(mkv_path.name)
    for i, sub in enumerate(subs[:SUBTITLE_BATCH_SIZE], 1):
        idx = candidate_index if candidate_index is not None else i
        drift_exists = any(f"number{idx}.DRIFT" in f.name for f in get_subtitle_files_by_pattern(dest_folder, lang, ".DRIFT"))
        failed_exists = any(f"number{idx}.FAILED" in f.name for f in get_subtitle_files_by_pattern(dest_folder, lang, ".FAILED"))
        if not force_download and (drift_exists or failed_exists):
            print_and_log(f"{acq_tag()} Skipping candidate index {idx}: already marked as DRIFT or FAILED.")
            continue
        try:
            files = sub.get('attributes', {}).get('files', [])
            if not files:
                print_and_log(f"{acq_tag()} {Fore.RED}No files for sub {idx}. Skipping.{Style.RESET_ALL}")
                continue
            file_id = files[0].get('file_id')
            if not file_id:
                print_and_log(f"{acq_tag()} {Fore.RED}No file_id for sub {idx}. Skipping.{Style.RESET_ALL}")
                continue
            downloads = sub['attributes'].get('download_count', 0)
            orig_sub_name = files[0].get('file_name', '')
            base_name = f"{downloads}.{lang}.number{idx}"
            if SERIES_MODE:
                sxxexx = sxxexx_from_mkv or extract_sxxexx_code(orig_sub_name)
                if sxxexx:
                    file_name = f"{base_name}.{sxxexx}.srt"
                else:
                    file_name = f"{base_name}.UNKNOWN.srt"
                    print_and_log(f"{acq_tag()} {Fore.YELLOW}Warning: Could not determine SxxExx code for subtitle '{orig_sub_name}'. Naming as '{file_name}'.{Style.RESET_ALL}")
                    unknown_sxxexx_files.append(str(dest_folder / file_name))
            else:
                file_name = f"{base_name}.srt"
            url = f"{API_URL}/download"
            max_retries_503 = DOWNLOAD_RETRY_503
            
            
            for attempt in range(1, max_retries_503 + 1):
                try:
                    resp = requests.post(url, headers=headers, json={"file_id": file_id})
                except Exception as e:
                    print_and_log_colored(f"{acq_tag()} {Fore.RED}HTTP POST error: {e}{Style.RESET_ALL}", Fore.RED)
                    resp = None
                time.sleep(0.1)
                
                if resp is None or resp.status_code >= 400:
                    if resp is not None and resp.status_code == 406:
                        print_and_log_colored(f"{acq_tag()} {Fore.YELLOW}406: Daily download quota reached. Pausing downloads.{Style.RESET_ALL}", Fore.YELLOW)
                        quota_exceeded = True
                        return  # Stop all downloads immediately after finishing this attempt
                    elif resp is not None and resp.status_code == 503:
                        if attempt < max_retries_503:
                            delay = min(5 * attempt, 30)
                            print_and_log_colored(f"{acq_tag()} {Fore.YELLOW}503 Service Unavailable (server overloaded). Retrying in {delay}s... (attempt {attempt}/{max_retries_503}){Style.RESET_ALL}", Fore.YELLOW)
                            time.sleep(delay)
                            continue
                        else:
                            print_and_log_colored(f"{acq_tag()} {Fore.RED}Failed to download after {max_retries_503} attempts (503 Service Unavailable). OpenSubtitles servers are overloaded. Skipping.{Style.RESET_ALL}", Fore.RED)
                            break
                    elif attempt < max_retries_503:
                        http_retry_delay = 5
                        print_and_log_colored(f"{acq_tag()} {Fore.YELLOW}HTTP error (status {getattr(resp, 'status_code', 'N/A')}). Retrying in {http_retry_delay}s... (attempt {attempt}/{max_retries_503}){Style.RESET_ALL}", Fore.YELLOW)
                        time.sleep(http_retry_delay)
                        continue
                    else:
                        print_and_log_colored(f"{acq_tag()} {Fore.RED}Failed to download after {max_retries_503} attempts (HTTP error). Skipping.{Style.RESET_ALL}", Fore.RED)
                        break
                elif resp.status_code == 200:
                    download_link = resp.json().get("link")
                    if download_link:
                        for srt_attempt in range(1, max_retries_503 + 1):
                            try:
                                srt_resp = requests.get(download_link)
                            except Exception as e:
                                print_and_log_colored(f"{acq_tag()} {Fore.RED}HTTP GET error: {e}{Style.RESET_ALL}", Fore.RED)
                                srt_resp = None
                            time.sleep(0.2)
                            
                            if srt_resp is None or srt_resp.status_code >= 400:
                                if srt_resp and srt_resp.status_code == 503:
                                    if srt_attempt < max_retries_503:
                                        delay = min(5 * srt_attempt, 30)
                                        print_and_log_colored(f"{acq_tag()} {Fore.YELLOW}SRT 503 Service Unavailable. Retrying in {delay}s... (attempt {srt_attempt}/{max_retries_503}){Style.RESET_ALL}", Fore.YELLOW)
                                        time.sleep(delay)
                                        continue
                                    else:
                                        print_and_log_colored(f"{acq_tag()} {Fore.RED}Failed to download SRT after {max_retries_503} attempts (503 Service Unavailable). Skipping.{Style.RESET_ALL}", Fore.RED)
                                        break
                                elif srt_attempt < max_retries_503:
                                    http_retry_delay = 5
                                    print_and_log_colored(f"{acq_tag()} {Fore.YELLOW}SRT HTTP error (status {getattr(srt_resp, 'status_code', 'N/A')}). Retrying in {http_retry_delay}s... (attempt {srt_attempt}/{max_retries_503}){Style.RESET_ALL}", Fore.YELLOW)
                                    time.sleep(http_retry_delay)
                                    continue
                                else:
                                    print_and_log_colored(f"{acq_tag()} {Fore.RED}Failed to download SRT after {max_retries_503} attempts (HTTP error). Skipping.{Style.RESET_ALL}", Fore.RED)
                                    break
                            elif srt_resp.status_code == 200:
                                srt_data = srt_resp.content
                                dest_path = dest_folder / file_name
                                with open(dest_path, 'wb') as f:
                                    f.write(srt_data)
                                if results is not None:
                                    results.append((idx, os.path.basename(dest_path), downloads))
                                else:
                                    print_and_log_colored(f"Stored as: {os.path.basename(dest_path)}", Fore.GREEN)
                                for failed_file in get_subtitle_files_by_pattern(dest_folder, lang, ".FAILED"):
                                    drift_file = failed_file.with_name(failed_file.name.replace(".FAILED.srt", ".DRIFT.srt"))
                                    failed_file.rename(drift_file)
                                    print_and_log_colored(
                                        f"{acq_tag()} {Fore.CYAN}Restored to DRIFT: {drift_file.name}{Style.RESET_ALL}",
                                        Fore.CYAN
                                    )
                                break
                        else:
                            print_and_log_colored(f"{acq_tag()} {Fore.RED}No valid SRT download after retries.{Style.RESET_ALL}", Fore.RED)
                    else:
                        print_and_log_colored(f"{acq_tag()} {Fore.RED}No download link in response.{Style.RESET_ALL}", Fore.RED)
                    break
                elif resp.status_code == 403:
                    print_and_log_colored(f"{acq_tag()} {Fore.RED}403 Forbidden: Download denied by OpenSubtitles API.{Style.RESET_ALL}", Fore.RED)
                    break
                else:
                    print_and_log_colored(f"{acq_tag()} {Fore.RED}Download endpoint error: HTTP {resp.status_code}{Style.RESET_ALL}", Fore.RED)
                    break
        except Exception as e:
            print_and_log_colored(f"{acq_tag()} {Fore.RED}Download error: {e}{Style.RESET_ALL}", Fore.RED)
def download_candidate_batch(candidates, lang, dest_folder, jwt_token, mkv_path, start_index):
    """Download candidates back to back and print one overview of what was stored."""
    results = []
    if candidates:
        print_and_log(f"{acq_tag()} Downloading {len(candidates)} subtitle(s) ({lang.upper()}):")
    for i, candidate in enumerate(candidates, start=start_index):
        shown = len(results)
        download_top_subtitles([candidate], lang, dest_folder, jwt_token, mkv_path=mkv_path, candidate_index=i, results=results)
        for idx, name, downloads in results[shown:]:
            print_and_log_colored(f"  {Fore.GREEN}[OK]{Style.RESET_ALL} {idx}. {name} ({downloads} downloads)", Fore.GREEN)
        if quota_exceeded:
            break
    if candidates:
        print_and_log(f"{acq_tag()} Downloaded {len(results)}/{len(candidates)} subtitle(s) ({lang.upper()})")

def print_subtitle_list(subs, lang, color=Fore.LIGHTBLUE_EX):
    """Display formatted list of available subtitles."""
    for i, item in enumerate(subs, 1):
        file_name = item['attributes']['files'][0]['file_name']
        downloads = item['attributes']['download_count']
        line = f"  {color}{i}.{Style.RESET_ALL} {file_name} (" \
               f"{Fore.CYAN}{downloads}{Style.RESET_ALL} downloads) " \
               f"[{Fore.LIGHTYELLOW_EX}{lang.upper()}{Style.RESET_ALL}]"
        print_and_log(line)
    print_and_log("")
def filter_subtitles_by_query(subs, query, debug=False):
    """Filter subtitle results by search query terms using word boundaries to avoid partial matches."""
    match = re.search(r'(.*?)([\s._-]?)(19|20)\d{2}', query)
    if match:
        left = match.group(1).strip().split()
        year = match.group(3) + match.group(0)[-2:]
        filter_words = [w.lower() for w in left if w] + [year]
    else:
        filter_words = [w.lower() for w in query.strip().split() if w]
    
    if debug:
        print_and_log(f"{acq_tag()} {Fore.LIGHTBLACK_EX}[Filter] Words: {filter_words}{Style.RESET_ALL}")

    filtered = []
    rejected_sample = []
    for sub in subs:
        # Skip subtitles without file information
        if not sub.get('attributes', {}).get('files') or len(sub['attributes']['files']) == 0:
            continue
        file_name = sub['attributes']['files'][0]['file_name'].lower().replace("'", "")
        
        # Use word boundaries to match whole words only (avoid "eternal" matching "eternally")
        # Word boundaries include: spaces, dots, underscores, hyphens, start/end of string
        all_matched = True
        failed_word = None
        for word in filter_words:
            # Create pattern that matches the word with word boundaries (non-alphanumeric chars)
            # \b doesn't work well with dots/underscores, so use explicit boundaries
            pattern = r'(?:^|[.\s_-])' + re.escape(word) + r'(?:[.\s_-]|$)'
            if not re.search(pattern, file_name):
                all_matched = False
                failed_word = word
                break
        
        if all_matched:
            filtered.append(sub)
        elif debug and len(rejected_sample) < 5:
            rejected_sample.append(f"'{file_name}' (missing: '{failed_word}')")
    
    if debug and rejected_sample:
        for r in rejected_sample:
            print_and_log(f"{acq_tag()} {Fore.LIGHTBLACK_EX}[Filter] Rejected: {r}{Style.RESET_ALL}")
    
    return filtered
_RELEASE_RESOLUTIONS = ('2160p', '1080p', '720p', '576p', '480p')
_RELEASE_SOURCES = (
    ('remux', r'remux'),
    ('bluray', r'blu-?ray|bdrip|brrip|bd'),
    ('webdl', r'web-?dl|webdl'),
    ('webrip', r'webrip'),
    ('web', r'web'),
    ('hdtv', r'hdtv'),
    ('dvd', r'dvd(?:rip)?'),
)
_RELEASE_CODECS = (('x265', r'x265|h\.?265|hevc'), ('x264', r'x264|h\.?264|avc'))
def _release_tokens(name):
    """Extract resolution/source/codec/group traits from a release-style name."""
    n = (name or '').lower()
    n = re.sub(r'\.(mkv|mp4|avi|srt|m4v)$', '', n)
    traits = {'res': None, 'src': None, 'codec': None, 'group': None}
    for res in _RELEASE_RESOLUTIONS:
        if re.search(r'(?:^|[.\s_\-\[\(])' + res + r'(?:[.\s_\-\]\)]|$)', n):
            traits['res'] = res
            break
    for label, pat in _RELEASE_SOURCES:
        if re.search(r'(?:^|[.\s_\-\[\(])(?:' + pat + r')(?:[.\s_\-\]\)]|$)', n):
            traits['src'] = label
            break
    for label, pat in _RELEASE_CODECS:
        if re.search(r'(?:^|[.\s_\-\[\(])(?:' + pat + r')(?:[.\s_\-\]\)]|$)', n):
            traits['codec'] = label
            break
    group = re.search(r'-([a-z0-9]{2,15})$', n)
    if group and (traits['res'] or traits['src'] or traits['codec']):
        traits['group'] = group.group(1)
    return traits, n
_RELEASE_STOP_WORDS = {'2160p', '1080p', '720p', '576p', '480p', 'bluray', 'blu', 'ray', 'bdrip', 'brrip', 'webdl', 'web', 'webrip', 'hdtv', 'dvdrip', 'dvd', 'remux', 'x264', 'x265', 'h264', 'h265', 'hevc', 'avc'}
def _title_and_episode(name):
    """Return (title words, (season, episode) or None) from a video or subtitle name."""
    n = re.sub(r'\.(mkv|mp4|avi|srt|m4v)$', '', (name or '').lower())
    episode = None
    m = re.search(r'(?:^|[^a-z0-9])s(\d{1,2})[ ._-]?e(\d{1,3})(?![0-9])', n)
    if m:
        episode = (int(m.group(1)), int(m.group(2)))
    words = []
    for tok in re.split(r'[^a-z0-9]+', n):
        if not tok:
            continue
        if re.fullmatch(r's\d{1,2}e\d{1,3}', tok) or re.fullmatch(r'(19|20)\d{2}', tok) or tok in _RELEASE_STOP_WORDS:
            break
        words.append(tok)
    return words, episode
def prioritize_release_matches(candidates, video_path):
    """Stable reorder only: candidates whose names resemble the video's title/episode/release go first.
    The set of candidates is never changed; ties keep their existing (download_count) order."""
    try:
        if not candidates or len(candidates) < 2:
            return candidates
        video_stem = Path(video_path).stem
        video_traits, _ = _release_tokens(video_stem)
        video_words, video_episode = _title_and_episode(video_stem)
        if not any(video_traits.values()) and not video_words and not video_episode:
            return candidates
        group = video_traits['group']

        def score(sub):
            attrs = sub.get('attributes', {})
            if attrs.get('moviehash_match'):
                return 100
            files = attrs.get('files') or [{}]
            text = f"{files[0].get('file_name', '')} {attrs.get('release', '')}"
            sub_traits, sub_text = _release_tokens(text)
            s = 0
            if video_episode:
                _, sub_episode = _title_and_episode(text)
                if sub_episode == video_episode:
                    s += 10
            if video_words:
                sub_tokens = set(re.split(r'[^a-z0-9]+', sub_text))
                found = sum(1 for w in video_words if w in sub_tokens)
                s += 12 * found / len(video_words)
            if group and re.search(r'(?:^|[.\s_\-\[\(])' + re.escape(group) + r'(?:[.\s_\-\]\)]|$)', sub_text):
                s += 4
            if video_traits['src'] and sub_traits['src'] == video_traits['src']:
                s += 2
            if video_traits['res'] and sub_traits['res'] == video_traits['res']:
                s += 2
            if video_traits['codec'] and sub_traits['codec'] == video_traits['codec']:
                s += 1
            return s

        scores = [score(c) for c in candidates]
        if not any(scores):
            return candidates
        order = sorted(range(len(candidates)), key=lambda i: -scores[i])
        if order != list(range(len(candidates))):
            print_and_log(f"{acq_tag()} {Fore.CYAN}Prioritizing subtitles that match the video's release name.{Style.RESET_ALL}")
        return [candidates[i] for i in order]
    except Exception:
        return candidates
def handle_api_error(response, request_details=None):
    """Handle and display API error responses with detailed information."""
    if response.status_code == 403:
        print_and_log(f"{acq_tag()} {Fore.RED}403 Forbidden: Access denied by OpenSubtitles API.{Style.RESET_ALL}")
        print_and_log(f"{acq_tag()} This is usually due to account, content, or region restrictions.")
        print_and_log(f"{acq_tag()} Please check your OpenSubtitles account status, try a different account, or contact OpenSubtitles support.")
        if request_details:
            print_and_log(f"{acq_tag()} --- REQUEST DETAILS ---")
            for key, value in request_details.items():
                print_and_log(f"{key}: {value}")
        print_and_log(f"{acq_tag()} --- RESPONSE DETAILS ---")
        print_and_log(f"Status: {response.status_code}")
        print_and_log(f"Headers: {dict(response.headers)}")
        print_and_log(f"Body: {response.text}")
        return True
    elif response.status_code == 401:
        print_and_log(f"{acq_tag()} JWT token invalid or expired. Fetching new token...")
        return False
    return False

def get_subtitle_files_by_pattern(folder: Path, lang: str, pattern_suffix: str = "") -> list[Path]:
    pattern = f"*.{lang}.number*{pattern_suffix}.srt"
    return list(folder.glob(pattern))

def count_existing_subtitles(movie_path: Path, lang: str) -> tuple[set, int]:
    existing_counts = set()
    
    # For series mode, only count episode-specific subtitles
    if SERIES_MODE:
        sxxexx_code = extract_sxxexx_code(movie_path.name)
        if sxxexx_code:
            # Count episode-specific candidates
            episode_pattern = f"*.{lang}.number*.{sxxexx_code}.srt"
            episode_drift_pattern = f"*.{lang}.number*.{sxxexx_code}.DRIFT.srt"
            episode_failed_pattern = f"*.{lang}.number*.{sxxexx_code}.FAILED.srt"
            
            episode_files = list(movie_path.parent.glob(episode_pattern))
            episode_drift_files = list(movie_path.parent.glob(episode_drift_pattern))
            episode_failed_files = list(movie_path.parent.glob(episode_failed_pattern))
            
            # Extract existing download counts for this episode
            for f in episode_files:
                if f.name.endswith('.DRIFT.srt') or f.name.endswith('.FAILED.srt'):
                    continue
                m = re.match(rf"^(P?\d+)\.{re.escape(lang)}\.number\d+\.{re.escape(sxxexx_code)}\.srt$", f.name)
                if m:
                    number_str = m.group(1)
                    # Skip P-prefixed files in normal counting (they're pre-downloaded)
                    if not number_str.startswith('P'):
                        existing_counts.add(int(number_str))
            
            for f in episode_drift_files:
                m = re.match(rf"^(P?\d+)\.{re.escape(lang)}\.number\d+\.{re.escape(sxxexx_code)}\.DRIFT\.srt$", f.name)
                if m:
                    number_str = m.group(1)
                    # Handle P-prefix: if highest number is P-prefixed, start downloads at 1
                    if number_str.startswith('P'):
                        # P-prefixed DRIFT found - this triggers the special logic later
                        existing_counts.add(-1)  # Special marker for P-prefix detection
                    else:
                        existing_counts.add(int(number_str))
                    
            for f in episode_failed_files:
                m = re.match(rf"^(P?\d+)\.{re.escape(lang)}\.number\d+\.{re.escape(sxxexx_code)}\.FAILED\.srt$", f.name)
                if m:
                    number_str = m.group(1)
                    # Same logic as DRIFT files
                    if number_str.startswith('P'):
                        existing_counts.add(-1)  # Special marker for P-prefix detection
                    else:
                        existing_counts.add(int(number_str))
            
            # Count total for this episode only
            normal_count = len([f for f in episode_files if not (f.name.endswith('.DRIFT.srt') or f.name.endswith('.FAILED.srt'))])
            total_existing = normal_count + len(episode_drift_files) + len(episode_failed_files)
            return existing_counts, total_existing
    
    # Original movie logic for non-series mode
    for f in get_subtitle_files_by_pattern(movie_path.parent, lang):
        if f.name.endswith('.DRIFT.srt') or f.name.endswith('.FAILED.srt'):
            continue
        m = re.match(r"^(P?\d+)\." + re.escape(lang) + r"\.number\d+\.srt$", f.name)
        if m:
            number_str = m.group(1)
            # Skip P-prefixed files in normal counting (they're pre-downloaded)
            if not number_str.startswith('P'):
                existing_counts.add(int(number_str))
    
    for f in get_subtitle_files_by_pattern(movie_path.parent, lang, ".DRIFT"):
        m = re.match(r"^(P?\d+)\." + re.escape(lang) + r"\.number\d+\.DRIFT\.srt$", f.name)
        if m:
            number_str = m.group(1)
            # Handle P-prefix: if highest number is P-prefixed, start downloads at 1
            if number_str.startswith('P'):
                existing_counts.add(-1)  # Special marker for P-prefix detection
            else:
                existing_counts.add(int(number_str))
    
    for f in get_subtitle_files_by_pattern(movie_path.parent, lang, ".FAILED"):
        m = re.match(r"^(P?\d+)\." + re.escape(lang) + r"\.number\d+\.FAILED\.srt$", f.name)
        if m:
            number_str = m.group(1)
            # Same logic as DRIFT files
            if number_str.startswith('P'):
                existing_counts.add(-1)  # Special marker for P-prefix detection
            else:
                existing_counts.add(int(number_str))
    all_srt_files = get_subtitle_files_by_pattern(movie_path.parent, lang)
    normal_count = len([f for f in all_srt_files if not (f.name.endswith('.DRIFT.srt') or f.name.endswith('.FAILED.srt'))])
    total_existing = normal_count + \
                    len(get_subtitle_files_by_pattern(movie_path.parent, lang, ".DRIFT")) + \
                    len(get_subtitle_files_by_pattern(movie_path.parent, lang, ".FAILED"))
    return existing_counts, total_existing

def build_search_query(raw_title: str, official_words=None) -> str:
    # For series mode, truncate everything after SxxExx pattern
    if SERIES_MODE:
        series_match = re.search(r'([sS](\d{1,2})[eE](\d{1,3}))', raw_title)
        if series_match:
            # Find the end of the SxxExx pattern
            series_end_pos = series_match.end()
            # Keep everything up to and including SxxExx, remove everything after
            truncated_title = raw_title[:series_end_pos]
            # Normalize a 3-digit episode (e.g. S06E006) down to 2 digits (S06E06) for search
            season_num, episode_num = series_match.group(2), series_match.group(3)
            normalized_code = f"S{int(season_num):02d}E{int(episode_num):02d}"
            truncated_title = truncated_title[:series_match.start()] + normalized_code
            
            # Simple cleaning for series: only remove brackets and their contents
            # Example: [TorrentCouch.com].13.Reasons.Why.S02E04 -> .13.Reasons.Why.S02E04
            cleaned = re.sub(r'\[[^\]]*\]', '', truncated_title)
            # Replace dots with spaces and clean up
            cleaned = cleaned.replace('.', ' ')
            # Clean up multiple spaces
            cleaned = re.sub(r'\s+', ' ', cleaned)
            
            return cleaned.strip()
    
    # Original movie logic for non-series mode
    year_match = re.search(r'(19|20)\d{2}', raw_title)
    if year_match:
        year = year_match.group(0)
        # Get everything before the year
        title_part = raw_title[:year_match.start()].rstrip(" ._-()[]")
        # Clean the title part to remove unwanted terms
        cleaned_title = clean_title(title_part, all_before_anchor=True, official_words=official_words)
        # Combine cleaned title with year
        query = f"{cleaned_title} {year}".strip()
    else:
        query = clean_title(raw_title, official_words=official_words)
    return clean_query(query)

def clean_query(query):
    query = re.sub(r'\s*\[[A-Z]{2}\]?$', '', query, flags=re.IGNORECASE).strip()
    query = re.sub(r'\[[A-Z]{2}\]', '', query, flags=re.IGNORECASE)
    query = re.sub(r'[\[\](){}]', '', query)
    query = query.replace('.', ' ')
    query = re.sub(r'(19|20)\d{2}$', lambda m: m.group(0), query)
    # Don't remove sequel numbers (1-99) from the end - keep them for accurate matching
    # This line is now commented out to preserve sequel numbers like "Lion King 3"
    # query = re.sub(r'(?<!\d)(\d{1,2})$', '', query).strip()
    return query

def remove_all_short_numbers(query):
    years = re.findall(r'(19|20)\d{2}', query)
    year_placeholders = []
    for i, year in enumerate(years):
        placeholder = f'__YEAR{i}__'
        query = query.replace(year, placeholder, 1)
        year_placeholders.append((placeholder, year))
    three_digits = re.findall(r'\b\d{3}\b', query)
    three_placeholders = []
    for i, three in enumerate(three_digits):
        placeholder = f'__THREE{i}__'
        query = re.sub(r'\b' + re.escape(three) + r'\b', placeholder, query, count=1)
        three_placeholders.append((placeholder, three))
    # Don't remove 1-2 digit numbers anymore - these can be sequel numbers
    # This line removed to preserve "Lion King 3", "Avatar 2", etc.
    # query = re.sub(r'\b\d{1,2}\b', '', query)
    for placeholder, year in year_placeholders:
        query = query.replace(placeholder, year)
    for placeholder, three in three_placeholders:
        query = query.replace(placeholder, three)
    query = re.sub(r'\s+', ' ', query).strip()
    return query

def write_subtitle_metadata(video_folder: Path, video_name: str, lang: str, imdb_match: bool):
    """Write metadata about subtitle acquisition for manual verification decision."""
    metadata_file = SNAPSHOT_DIR / ".subtitle_metadata.txt"
    try:
        # Read existing entries
        entries = {}
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if '|' in line:
                        parts = line.strip().split('|')
                        if len(parts) >= 3:
                            # Format: video_name|lang|imdb_status|rejected_count
                            rejected = parts[3] if len(parts) >= 4 else "0"
                            entries[f"{parts[0]}|{parts[1]}"] = (parts[2], rejected)
        
        # Add/update entry for this video+lang (preserve rejected count if exists)
        key = f"{video_name}|{lang}"
        imdb_status = "imdb_match" if imdb_match else "no_imdb_match"
        rejected_count = entries[key][1] if key in entries else "0"
        entries[key] = (imdb_status, rejected_count)
        
        # Write all entries back
        with open(metadata_file, 'w', encoding='utf-8') as f:
            for key, (status, rejected) in entries.items():
                video, language = key.split('|')
                f.write(f"{video}|{language}|{status}|{rejected}\n")
    except Exception as e:
        print_and_log(f"{acq_tag()} {Fore.YELLOW}Warning: Could not write subtitle metadata: {e}{Style.RESET_ALL}")

def read_subtitle_metadata(video_folder: Path, video_name: str, lang: str):
    """Read metadata about subtitle acquisition. Returns True if IMDb match, False otherwise."""
    metadata_file = SNAPSHOT_DIR / ".subtitle_metadata.txt"
    if not metadata_file.exists():
        return False
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            for line in f:
                if '|' in line:
                    parts = line.strip().split('|')
                    if len(parts) >= 3:
                        if parts[0] == video_name and parts[1] == lang:
                            return parts[2] == "imdb_match"
    except Exception:
        pass
    return False

def search_subtitles(movie_path: Path, jwt_token: str):
    global quota_exceeded
    raw_title = movie_path.stem
    query = build_search_query(raw_title)
    query = remove_all_short_numbers(query)
    already_synced = check_existing_subtitles(movie_path)
    skip_langs = set()
    for lang, synced in already_synced.items():
        if synced:
            print_and_log(f"{acq_tag()} {Fore.GREEN}Skipping {lang.upper()}: already synced subtitle present!{Style.RESET_ALL}")
            skip_langs.add(lang)
    for lang in LANGUAGES:
        if is_movie_language_skipped(movie_path, lang):
            print_and_log(f"{acq_tag()} {Fore.MAGENTA}Skipping {lang.upper()}: language indefinitely skipped for this movie!{Style.RESET_ALL}")
            skip_langs.add(lang)
    base = movie_path.with_suffix("")
    # Use episode-specific checking for series mode
    missing_langs = []
    drift_langs = {}
    for lang in LANGUAGES:
        if lang in skip_langs:
            continue
        
        # Check for extracted subtitles from pre-downloaded folders (series mode only)
        if SERIES_MODE:
            sxxexx_code = extract_sxxexx_code(movie_path.name)
            if sxxexx_code:
                # Check for extracted and renamed subtitles in the main folder
                # Only skip if there are ACTIVE extracted files (not just DRIFT)
                extracted_pattern = f"*.{lang}.number*.{sxxexx_code}.srt"
                extracted_files = list(movie_path.parent.glob(extracted_pattern))
                
                if extracted_files:
                    print_and_log(f"{acq_tag()} {Fore.GREEN}Skipping {lang.upper()}: {len(extracted_files)} extracted subtitles found!{Style.RESET_ALL}")
                    skip_langs.add(lang)
                    continue
            
        # Check for episode-specific subtitle files
        base = movie_path.with_suffix("")
        
        # Standard naming: filename.lang.srt
        normal = base.with_name(f"{base.name}.{lang}.srt")
        
        # Series naming
        series_srt = None
        if SERIES_MODE:
            sxxexx_code = extract_sxxexx_code(movie_path.name)
            if sxxexx_code:
                # Check if video filename already contains the episode code
                if sxxexx_code.lower() in base.name.lower():
                    # Video already has SxxExx in name, subtitle should use standard naming
                    series_srt = base.with_name(f"{base.name}.{lang}.srt")
                else:
                    # Video doesn't have SxxExx, subtitle should have SxxExx before language
                    series_srt = base.with_name(f"{base.name}.{sxxexx_code}.{lang}.srt")
        
        # Check for episode-specific candidate files (downloaded but not yet finalized)
        episode_specific_candidates = []
        if SERIES_MODE and sxxexx_code:
            episode_specific_candidates = list(movie_path.parent.glob(f"*.{lang}.number*.{sxxexx_code}.srt"))
        else:
            episode_specific_candidates = list(movie_path.parent.glob(f"*.{lang}.number*.srt"))
        
        # Filter out DRIFT and FAILED files
        sync = [f for f in episode_specific_candidates if not (f.name.endswith('.DRIFT.srt') or f.name.endswith('.FAILED.srt'))]
        
        # Check for DRIFT files with series-awareness
        if SERIES_MODE:
            sxxexx_code = extract_sxxexx_code(movie_path.name)
            if sxxexx_code:
                drift_files = list(movie_path.parent.glob(f"*.{lang}.number*.{sxxexx_code}.DRIFT.srt"))
            else:
                drift_files = list(movie_path.parent.glob(f"*.{lang}.number*.DRIFT.srt"))
        else:
            drift_files = list(movie_path.parent.glob(f"*.{lang}.number*.DRIFT.srt"))
        
        if drift_files:
            drift_langs[lang] = drift_files
        
        # Language has subtitles if either standard or series file exists, or valid candidates exist
        has_subtitles = normal.exists() or (series_srt and series_srt.exists()) or sync
        
        # For series mode with extracted subtitles, check if we need more based on batch size
        if SERIES_MODE and sync and not (normal.exists() or (series_srt and series_srt.exists())):
            # Count existing extracted subtitles for this episode
            current_count = len(sync)
            batch_size = SUBTITLE_BATCH_SIZE  # Use SUBTITLE_BATCH_SIZE as batch size
            
            if current_count >= batch_size:
                print_and_log(f"{acq_tag()} {Fore.GREEN}Skipping {lang.upper()}: {current_count} extracted subtitles available (batch size: {batch_size})!{Style.RESET_ALL}")
                has_subtitles = True  # Mark as having subtitles to skip downloading
            else:
                print_and_log(f"{acq_tag()} {Fore.YELLOW}Language {lang.upper()}: {current_count} extracted subtitles found, downloading {batch_size - current_count} more to reach batch size{Style.RESET_ALL}")
                # We'll allow downloading but adjust the amount needed
        
        if not has_subtitles and not drift_files:
            missing_langs.append(lang)
    if drift_langs:
        def process_drift_batch(top_results, drift_files, lang, used_fallback):
            drift_numbers = set()
            # Use series-aware DRIFT detection
            # IMPORTANT: Only count non-P-prefix DRIFT files as "already tried"
            # P-prefix files are pre-downloaded and separate from OpenSubtitles ranking
            if SERIES_MODE:
                sxxexx_code = extract_sxxexx_code(movie_path.name)
                if sxxexx_code:
                    # Series mode: look for episode-specific DRIFT files
                    for f in drift_files:
                        # Match both normal and P-prefix files, but only count normal ones
                        m = re.search(rf"^(P)?(\d+)\.{re.escape(lang)}\.number(\d+)\.{re.escape(sxxexx_code)}\.DRIFT\.srt$", f.name)
                        if m:
                            is_p_prefix = bool(m.group(1))  # Group 1 is 'P' or None
                            number_index = int(m.group(3))  # Group 3 is the number index
                            if not is_p_prefix:
                                # Only count non-P-prefix files as tried indices
                                drift_numbers.add(number_index)
                else:
                    # Fallback to standard pattern if no SxxExx found
                    for f in drift_files:
                        m = re.search(rf"^(P)?(\d+)\.{re.escape(lang)}\.number(\d+)\.DRIFT\.srt$", f.name)
                        if m:
                            is_p_prefix = bool(m.group(1))
                            number_index = int(m.group(3))
                            if not is_p_prefix:
                                drift_numbers.add(number_index)
            else:
                # Movie mode: use standard pattern
                for f in drift_files:
                    m = re.search(rf"^(P)?(\d+)\.{re.escape(lang)}\.number(\d+)\.DRIFT\.srt$", f.name)
                    if m:
                        is_p_prefix = bool(m.group(1))
                        number_index = int(m.group(3))
                        if not is_p_prefix:
                            drift_numbers.add(number_index)
            drift_numbers = sorted(drift_numbers)
            available_count = len(top_results)
            all_indices = set(range(1, available_count + 1))
            drift_set = set(drift_numbers)
            not_tried_indices = sorted(all_indices - drift_set)
            batch_to_try = not_tried_indices[:SUBTITLE_BATCH_SIZE]
            if not batch_to_try:
                print_and_log(f"{acq_tag()} {Fore.RED}No new candidates left to try for {lang.upper()}!{Style.RESET_ALL}")
                params_unfiltered = {
                    "query": query,
                    "languages": lang
                }
                search_term_msg = f"Broader search term for {lang.upper()}: '{query}'"
                print_and_log_colored(f"{acq_tag()} {Fore.LIGHTYELLOW_EX}{search_term_msg}{Style.RESET_ALL}")
                print_and_log(f"{acq_tag()} {search_term_msg}")
                print_and_log(f"{acq_tag()} {Fore.YELLOW}Broader search: performing unfiltered search for {lang.upper()}!{Style.RESET_ALL}")
                response_unfiltered = requests.get(f"{API_URL}/subtitles", headers=headers, params=params_unfiltered)
                time.sleep(0.5)
                if response_unfiltered.status_code == 200:
                    data_unfiltered = response_unfiltered.json()
                    unfiltered_results = data_unfiltered.get("data", [])
                    drift_download_counts = set()
                    for f in drift_files:
                        m = re.search(rf"^(\\d+)\\.{lang}\\.number\\d+\\.DRIFT\\.srt$", f.name)
                        if m:
                            drift_download_counts.add(int(m.group(1)))
                    genuinely_new = []
                    for candidate in unfiltered_results:
                        cand_downloads = candidate['attributes'].get('download_count', 0)
                        drift_exists = any(
                            f.name.startswith(f"{cand_downloads}.{lang}.") and f.name.endswith(".DRIFT.srt")
                            for f in movie_path.parent.glob(f"*.{lang}.number*.DRIFT.srt")
                        )
                        failed_exists = any(
                            f.name.startswith(f"{cand_downloads}.{lang}.") and f.name.endswith(".FAILED.srt")
                            for f in movie_path.parent.glob(f"*.{lang}.number*.FAILED.srt")
                        )
                        if drift_exists or failed_exists:
                            continue
                        genuinely_new.append(candidate)
                    genuinely_new = prioritize_release_matches(sorted(genuinely_new, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:MAX_SEARCH_RESULTS], movie_path)
                    if genuinely_new:
                        all_srt_files = list(movie_path.parent.glob(f"*.{lang}.number*.srt"))
                        existing_downloads = len([f for f in all_srt_files if not (f.name.endswith('.DRIFT.srt') or f.name.endswith('.FAILED.srt'))])
                        
                        # Count DRIFT/FAILED files with series-awareness
                        if SERIES_MODE:
                            sxxexx_code = extract_sxxexx_code(movie_path.name)
                            if sxxexx_code:
                                existing_drifts = sum(1 for _ in movie_path.parent.glob(f"*.{lang}.number*.{sxxexx_code}.DRIFT.srt"))
                                existing_failed = sum(1 for _ in movie_path.parent.glob(f"*.{lang}.number*.{sxxexx_code}.FAILED.srt"))
                            else:
                                existing_drifts = sum(1 for _ in movie_path.parent.glob(f"*.{lang}.number*.DRIFT.srt"))
                                existing_failed = sum(1 for _ in movie_path.parent.glob(f"*.{lang}.number*.FAILED.srt"))
                        else:
                            existing_drifts = sum(1 for _ in movie_path.parent.glob(f"*.{lang}.number*.DRIFT.srt"))
                            existing_failed = sum(1 for _ in movie_path.parent.glob(f"*.{lang}.number*.FAILED.srt"))
                        total_downloaded = existing_downloads + existing_drifts + existing_failed
                        if total_downloaded >= MAX_SEARCH_RESULTS:
                            print_and_log(f"{acq_tag()} {Fore.YELLOW}MAX_SEARCH_RESULTS limit ({MAX_SEARCH_RESULTS}) reached for {lang.upper()}. Forcing to last resort.{Style.RESET_ALL}")
                            genuinely_new = []
                        else:
                            remaining_slots = MAX_SEARCH_RESULTS - total_downloaded
                            candidates_to_download = genuinely_new[:min(SUBTITLE_BATCH_SIZE, remaining_slots)]
                            print_and_log(f"{acq_tag()} {Fore.YELLOW}Broader search found {len(candidates_to_download)} genuinely new candidates for {lang.upper()}. (Downloaded: {total_downloaded}/{MAX_SEARCH_RESULTS}){Style.RESET_ALL}")
                            print_subtitle_list(candidates_to_download, lang, color=Fore.LIGHTYELLOW_EX)
                            drift_indices = []
                            # Use series-aware DRIFT detection
                            if SERIES_MODE:
                                sxxexx_code = extract_sxxexx_code(movie_path.name) 
                                if sxxexx_code:
                                    # Series mode: look for episode-specific DRIFT files
                                    for f in drift_files:
                                        m = re.search(rf"\.{re.escape(lang)}\.number(\d+)\.{re.escape(sxxexx_code)}\.DRIFT\.srt$", f.name)
                                        if m:
                                            drift_indices.append(int(m.group(1)))
                                else:
                                    # Fallback to standard pattern if no SxxExx found
                                    for f in drift_files:
                                        m = re.search(rf"\.number(\d+)\.DRIFT\.srt$", f.name)
                                        if m:
                                            drift_indices.append(int(m.group(1)))
                            else:
                                # Movie mode: use standard pattern
                                for f in drift_files:
                                    m = re.search(rf"\.number(\d+)\.DRIFT\.srt$", f.name)
                                    if m:
                                        drift_indices.append(int(m.group(1)))
                            start_index = max(drift_indices) + 1 if drift_indices else 1
                            
                            for i, candidate in enumerate(candidates_to_download, start=start_index):
                                candidate_file_name = candidate['attributes']['files'][0]['file_name']
                                cand_downloads = candidate['attributes'].get('download_count', 0)
                                download_top_subtitles([candidate], lang, movie_path.parent, jwt_token, mkv_path=movie_path, candidate_index=i)
                                if quota_exceeded:
                                    return
                            print_and_log(f"{acq_tag()} {Fore.GREEN}*{Style.RESET_ALL} Broader batch download complete for {lang.upper()}!\n{Style.RESET_ALL}")
                            if (query, movie_path, lang) in missing_queries:
                                missing_queries.remove((query, movie_path, lang))
                            return
                    if not genuinely_new:
                        print_and_log(f"{acq_tag()} {Fore.YELLOW}Broader search found no genuinely new candidates for {lang.upper()}.".format(lang=lang))
                        
                        # Check if last resort search is enabled in config
                        if not LAST_RESORT_SEARCH:
                            print_and_log(f"{acq_tag()} {Fore.YELLOW}Last resort search is disabled in config. Marking DRIFT files as FAILED.{Style.RESET_ALL}")
                            mark_drift_as_failed(movie_path.parent, lang)
                            if not is_movie_language_skipped(movie_path, lang) and (query, movie_path, lang) not in missing_queries:
                                missing_queries.append((query, movie_path, lang))
                            return
                        
                        last_resort_msg = f"Last resort search term for {lang.upper()}: '{query}'"
                        print_and_log_colored(f"{acq_tag()} {Fore.LIGHTYELLOW_EX}{last_resort_msg}{Style.RESET_ALL}")
                        print_and_log(f"{acq_tag()} {last_resort_msg}")
                        print_and_log(f"{acq_tag()} {Fore.RED}Last resort: downloading ALL candidates for {lang.upper()} (no filtering)!{Style.RESET_ALL}")
                        all_candidates = sorted(unfiltered_results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:SUBTITLE_BATCH_SIZE]
                        unique_candidates = {}
                        for candidate in all_candidates:
                            cand_downloads = candidate['attributes'].get('download_count', 0)
                            if cand_downloads not in unique_candidates:
                                unique_candidates[cand_downloads] = candidate
                        all_candidates = prioritize_release_matches(list(unique_candidates.values()), movie_path)
                        print_subtitle_list(all_candidates, lang, color=Fore.LIGHTRED_EX)
                        any_downloaded = False
                        for i, candidate in enumerate(all_candidates, start=1):
                            candidate_file_name = candidate['attributes']['files'][0]['file_name']
                            cand_downloads = candidate['attributes'].get('download_count', 0)
                            srt_exists = any(f.name.startswith(f"{cand_downloads}.{lang}.") and f.name.endswith(".srt") and not (f.name.endswith(".DRIFT.srt") or f.name.endswith(".FAILED.srt")) for f in movie_path.parent.glob(f"*.{lang}.number*.srt"))
                            
                            # Check DRIFT/FAILED with series-awareness
                            if SERIES_MODE:
                                sxxexx_code = extract_sxxexx_code(movie_path.name)
                                if sxxexx_code:
                                    drift_exists = any(f.name.startswith(f"{cand_downloads}.{lang}.") and f.name.endswith(".DRIFT.srt") for f in movie_path.parent.glob(f"*.{lang}.number*.{sxxexx_code}.DRIFT.srt"))
                                    failed_exists = any(f.name.startswith(f"{cand_downloads}.{lang}.") and f.name.endswith(".FAILED.srt") for f in movie_path.parent.glob(f"*.{lang}.number*.{sxxexx_code}.FAILED.srt"))
                                else:
                                    drift_exists = any(f.name.startswith(f"{cand_downloads}.{lang}.") and f.name.endswith(".DRIFT.srt") for f in movie_path.parent.glob(f"*.{lang}.number*.DRIFT.srt"))
                                    failed_exists = any(f.name.startswith(f"{cand_downloads}.{lang}.") and f.name.endswith(".FAILED.srt") for f in movie_path.parent.glob(f"*.{lang}.number*.FAILED.srt"))
                            else:
                                drift_exists = any(f.name.startswith(f"{cand_downloads}.{lang}.") and f.name.endswith(".DRIFT.srt") for f in movie_path.parent.glob(f"*.{lang}.number*.DRIFT.srt"))
                                failed_exists = any(f.name.startswith(f"{cand_downloads}.{lang}.") and f.name.endswith(".FAILED.srt") for f in movie_path.parent.glob(f"*.{lang}.number*.FAILED.srt"))
                            if srt_exists or drift_exists or failed_exists:
                                print_and_log_colored(f"{acq_tag()} {Fore.YELLOW}Skipping LASTRESORT candidate index {i}: already present as .srt, .DRIFT.srt, or .FAILED.srt.{Style.RESET_ALL}", Fore.YELLOW)
                                continue
                            dest_path = movie_path.parent / f"{cand_downloads}.{lang}.number{i}.LASTRESORT.srt"
                            if dest_path.exists():
                                print_and_log_colored(f"{acq_tag()} {Fore.YELLOW}Skipping LASTRESORT candidate index {i}: file already exists.{Style.RESET_ALL}", Fore.YELLOW)
                                continue
                            files_before = set(movie_path.parent.glob(f"*.{lang}.number{i}.*.srt"))
                            download_top_subtitles([candidate], lang, movie_path.parent, jwt_token, mkv_path=movie_path, candidate_index=i)
                            if quota_exceeded:
                                return
                            files_after = set(movie_path.parent.glob(f"*.{lang}.number{i}.*.srt"))
                            if files_after - files_before:
                                any_downloaded = True
                                print_and_log(f"{acq_tag()} {Fore.GREEN}Successfully downloaded LASTRESORT candidate {i}.{Style.RESET_ALL}")
                            else:
                                print_and_log(f"{acq_tag()} {Fore.YELLOW}LASTRESORT candidate {i} download failed or was skipped.{Style.RESET_ALL}")
                        print_and_log(f"{acq_tag()} {Fore.GREEN}Last resort batch download complete for {lang.upper()}!\n{Style.RESET_ALL}")
                        if not any_downloaded:
                            print_and_log(f"{acq_tag()} {Fore.RED}No candidates could be downloaded in last resort for {lang.upper()}. Marking DRIFT files as FAILED.{Style.RESET_ALL}")
                            mark_drift_as_failed(movie_path.parent, lang)
                            if not is_movie_language_skipped(movie_path, lang) and (query, movie_path, lang) not in missing_queries:
                                missing_queries.append((query, movie_path, lang))
                            return
                else:
                    print_and_log(f"{acq_tag()} {Fore.RED}Broader search failed for {lang.upper()} (HTTP {response_unfiltered.status_code}){Style.RESET_ALL}")
                    if not is_movie_language_skipped(movie_path, lang) and (query, movie_path, lang) not in missing_queries:
                        missing_queries.append((query, movie_path, lang))
                return
            all_srt_files = list(movie_path.parent.glob(f"*.{lang}.number*.srt"))
            existing_downloads = len([f for f in all_srt_files if not (f.name.endswith('.DRIFT.srt') or f.name.endswith('.FAILED.srt'))])
            
            # Count DRIFT/FAILED files with series-awareness  
            if SERIES_MODE:
                sxxexx_code = extract_sxxexx_code(movie_path.name)
                if sxxexx_code:
                    existing_drifts = sum(1 for _ in movie_path.parent.glob(f"*.{lang}.number*.{sxxexx_code}.DRIFT.srt"))
                    existing_failed = sum(1 for _ in movie_path.parent.glob(f"*.{lang}.number*.{sxxexx_code}.FAILED.srt"))
                else:
                    existing_drifts = sum(1 for _ in movie_path.parent.glob(f"*.{lang}.number*.DRIFT.srt"))
                    existing_failed = sum(1 for _ in movie_path.parent.glob(f"*.{lang}.number*.FAILED.srt"))
            else:
                existing_drifts = sum(1 for _ in movie_path.parent.glob(f"*.{lang}.number*.DRIFT.srt"))
                existing_failed = sum(1 for _ in movie_path.parent.glob(f"*.{lang}.number*.FAILED.srt"))
            total_downloaded = existing_downloads + existing_drifts + existing_failed
            if total_downloaded >= MAX_SEARCH_RESULTS:
                print_and_log(f"{acq_tag()} {Fore.YELLOW}MAX_SEARCH_RESULTS limit ({MAX_SEARCH_RESULTS}) reached for {lang.upper()}. Skipping to broader search.{Style.RESET_ALL}")
                batch_to_try = []
            for idx in batch_to_try:
                if idx <= len(top_results):
                    candidate = top_results[idx-1]
                    candidate_file_name = candidate['attributes']['files'][0]['file_name']
                    download_top_subtitles([candidate], lang, movie_path.parent, jwt_token, mkv_path=movie_path, candidate_index=idx)
                    if quota_exceeded:
                        return
            if batch_to_try:
                print_and_log(f"{acq_tag()} {Fore.GREEN}Batch download complete for {lang.upper()}!\n{Style.RESET_ALL}")
            else:
                print_and_log(f"{acq_tag()} {Fore.YELLOW}No candidates to download for {lang.upper()} (limit reached or no new candidates).{Style.RESET_ALL}")
        for lang, drift_files in drift_langs.items():
            current_drift_files = get_subtitle_files_by_pattern(movie_path.parent, lang, ".DRIFT")
            if not current_drift_files:
                print_and_log(f"{acq_tag()} {Fore.YELLOW}No DRIFT files remaining for {lang.upper()} (already processed or marked as FAILED). Skipping.{Style.RESET_ALL}")
                continue
            display_query = query
            headers = {
                "Authorization": f"Bearer {jwt_token}",
                "User-Agent": "NexigenSubtitleBot v1.0",
                "Api-Key": API_KEY
            }

            # Try IMDb ID search first if OMDb is configured
            response = None
            results = []
            imdb_trusted_ids = set()
            if OMDB_API_KEY:
                try:
                    # For series: strip SxxExx from query and get year from filename
                    # For movies: extract year from query as before
                    if SERIES_MODE:
                        _sxxexx_q = extract_sxxexx_code(movie_path.name)
                        _title_for_omdb = re.sub(r'\s*[sS]\d{1,2}[eE]\d{1,2}.*', '', query).strip()
                        _title_for_omdb = clean_title(_title_for_omdb, all_before_anchor=True)
                        _year_match = re.search(r'(19|20)\d{2}', movie_path.name)
                        year = _year_match.group(0) if _year_match else None
                        title = _title_for_omdb
                    else:
                        year_match = re.search(r'(19|20)\d{2}', query)
                        if year_match:
                            year = year_match.group(0)
                            title = query[:year_match.start()].strip()
                        else:
                            year = None
                            title = query.strip()
                        title = clean_title(title, all_before_anchor=True)
                    
                    # Lookup IMDb ID
                    _omdb_type = 'series' if SERIES_MODE else 'movie'
                    imdb_id = lookup_imdb_id_leading(title, year, media_type=_omdb_type)
                    if imdb_id:
                        query = refine_query_with_imdb_title(raw_title, query)
                        params_imdb = {
                            "imdb_id": imdb_id,
                            "languages": lang
                        }
                        if SERIES_MODE:
                            _sxxexx = extract_sxxexx_code(movie_path.name)
                            if _sxxexx:
                                params_imdb["season_number"] = int(_sxxexx[1:3])
                                params_imdb["episode_number"] = int(_sxxexx[4:6])
                        print_and_log(f"{acq_tag()} {Fore.LIGHTCYAN_EX}[IMDb SEARCH]{Style.RESET_ALL} Searching for {Fore.LIGHTYELLOW_EX}{lang.upper()}{Style.RESET_ALL} subtitles using IMDb ID: {Fore.CYAN}{imdb_id}{Style.RESET_ALL}")
                        response = requests.get(f"{API_URL}/subtitles", headers=headers, params=params_imdb)
                        time.sleep(0.5)
                        if response.status_code == 200:
                            data = response.json()
                            imdb_results = data.get("data", [])
                            if imdb_results:
                                print_and_log(f"{acq_tag()} {Fore.GREEN}[OK] [IMDb MATCH]{Style.RESET_ALL} Found {Fore.GREEN}{len(imdb_results)}{Style.RESET_ALL} subtitle(s) for {Fore.LIGHTYELLOW_EX}{lang.upper()}{Style.RESET_ALL}")
                                results = imdb_results
                                imdb_trusted_ids = {r['id'] for r in imdb_results}
                                # Also run text search and merge — some uploads are indexed under a different IMDb ID
                                try:
                                    _params_text = {"query": query, "languages": lang}
                                    _resp_text = requests.get(f"{API_URL}/subtitles", headers=headers, params=_params_text)
                                    time.sleep(0.5)
                                    if _resp_text.status_code == 200:
                                        _text_results = _resp_text.json().get("data", [])
                                        _existing_ids = {r['id'] for r in results}
                                        _new = [r for r in _text_results if r['id'] not in _existing_ids]
                                        if _new:
                                            print_and_log(f"{acq_tag()} {Fore.CYAN}[IMDb+Text merge]{Style.RESET_ALL} Added {len(_new)} extra result(s) from text search")
                                            results = results + _new
                                        else:
                                            print_and_log(f"{acq_tag()} {Fore.LIGHTBLACK_EX}[IMDb+Text merge] No new results from text search{Style.RESET_ALL}")
                                except Exception as _merge_e:
                                    print_and_log(f"{acq_tag()} {Fore.YELLOW}[IMDb+Text merge] Failed: {_merge_e}{Style.RESET_ALL}")
                                # In series mode: also search by episode-specific IMDb ID
                                if SERIES_MODE and OMDB_API_KEY:
                                    try:
                                        _sxxexx_ep = extract_sxxexx_code(movie_path.name)
                                        if _sxxexx_ep:
                                            _ep_season = int(_sxxexx_ep[1:3])
                                            _ep_episode = int(_sxxexx_ep[4:6])
                                            _ep_imdb_id = get_episode_imdb_id_from_omdb(title, _ep_season, _ep_episode)
                                            if _ep_imdb_id and _ep_imdb_id != imdb_id:
                                                _params_ep = {"imdb_id": _ep_imdb_id, "languages": lang}
                                                _resp_ep = requests.get(f"{API_URL}/subtitles", headers=headers, params=_params_ep)
                                                time.sleep(0.5)
                                                if _resp_ep.status_code == 200:
                                                    _ep_results = _resp_ep.json().get("data", [])
                                                    # Mark ALL episode IMDb results as trusted (even if already in results via text merge)
                                                    imdb_trusted_ids.update(r['id'] for r in _ep_results)
                                                    _existing_ids = {r['id'] for r in results}
                                                    _new_ep = [r for r in _ep_results if r['id'] not in _existing_ids]
                                                    if _new_ep:
                                                        print_and_log(f"{acq_tag()} {Fore.CYAN}[IMDb+Episode merge]{Style.RESET_ALL} Added {len(_new_ep)} extra result(s) via episode IMDb ID {_ep_imdb_id}")
                                                        results = results + _new_ep
                                                    else:
                                                        _newly_trusted = len([r for r in _ep_results if r['id'] in imdb_trusted_ids]) - len([r for r in imdb_results if r['id'] in imdb_trusted_ids])
                                                        print_and_log(f"{acq_tag()} {Fore.LIGHTBLACK_EX}[IMDb+Episode merge] No new results, but {len(_ep_results)} result(s) now trusted via episode IMDb ID{Style.RESET_ALL}")
                                    except Exception as _ep_e:
                                        print_and_log(f"{acq_tag()} {Fore.YELLOW}[IMDb+Episode merge] Failed: {_ep_e}{Style.RESET_ALL}")
                            else:
                                print_and_log(f"{acq_tag()} {Fore.YELLOW}[IMDb] No results found{Style.RESET_ALL}")
                                response = None
                        else:
                            print_and_log(f"{acq_tag()} {Fore.YELLOW}[IMDb] Search failed (HTTP {response.status_code}){Style.RESET_ALL}")
                            response = None
                except Exception as e:
                    print_and_log(f"{acq_tag()} {Fore.YELLOW}[IMDb] Lookup failed: {str(e)}{Style.RESET_ALL}")
                    response = None

            # Try hash-based search if IMDb search failed and hash is enabled
            if (not response or response.status_code != 200) and USE_MOVIE_HASH:
                try:
                    movie_hash = calculate_hash(movie_path)
                    file_size = movie_path.stat().st_size
                    params_hash = {
                        "moviehash": movie_hash,
                        "moviebytesize": str(file_size),
                        "languages": lang
                    }
                    print_and_log(f"{acq_tag()} {Fore.LIGHTMAGENTA_EX}[HASH SEARCH]{Style.RESET_ALL} Searching for {Fore.LIGHTYELLOW_EX}{lang.upper()}{Style.RESET_ALL} subtitles using file hash")
                    response = requests.get(f"{API_URL}/subtitles", headers=headers, params=params_hash)
                    time.sleep(0.5)
                    if response.status_code == 200:
                        data = response.json()
                        hash_results = data.get("data", [])
                        if hash_results:
                            print_and_log(f"{acq_tag()} {Fore.GREEN}[OK] [HASH MATCH]{Style.RESET_ALL} Found {Fore.GREEN}{len(hash_results)}{Style.RESET_ALL} subtitle(s) for {Fore.LIGHTYELLOW_EX}{lang.upper()}{Style.RESET_ALL}")
                            results = hash_results
                        else:
                            print_and_log(f"{acq_tag()} {Fore.YELLOW}[HASH] No results found{Style.RESET_ALL}")
                            response = None
                    else:
                        print_and_log(f"{acq_tag()} {Fore.YELLOW}[HASH] Search failed (HTTP {response.status_code}){Style.RESET_ALL}")
                        response = None
                except Exception as e:
                    print_and_log(f"{acq_tag()} {Fore.YELLOW}[HASH] Calculation failed: {str(e)}{Style.RESET_ALL}")
                    response = None

            # Fallback to text-based search if IMDb and hash search failed
            if not response or response.status_code != 200:
                params = {
                    "query": query,
                    "languages": lang
                }
                print_and_log(f"{acq_tag()} {Fore.CYAN}[TEXT SEARCH]{Style.RESET_ALL} Searching for {Fore.LIGHTYELLOW_EX}{lang.upper()}{Style.RESET_ALL}: '{Fore.WHITE}{display_query}{Style.RESET_ALL}'")
                response = requests.get(f"{API_URL}/subtitles", headers=headers, params=params)
                time.sleep(0.5)

            if response.status_code == 200:
                if not results:  # Only get results if not already retrieved from hash search
                    data = response.json()
                    results = data.get("data", [])
                trusted = [r for r in results if r['id'] in imdb_trusted_ids]
                untrusted = [r for r in results if r['id'] not in imdb_trusted_ids]
                filtered_results = trusted + filter_subtitles_by_query(untrusted, query)
                top_results = prioritize_release_matches(sorted(filtered_results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:MAX_SEARCH_RESULTS], movie_path)
                header = f"\n{acq_tag()} Top {len(top_results)} subtitles ({lang.upper()}):"
                print_and_log(header)
                print_subtitle_list(top_results, lang, color=Fore.LIGHTBLUE_EX)
                if top_results:
                    process_drift_batch(top_results, drift_files, lang, used_fallback=False)
                    continue
                print_and_log(f"{acq_tag()} No results with filter, trying without a filter...")
                top_results_unfiltered = prioritize_release_matches(sorted(results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:MAX_SEARCH_RESULTS], movie_path)
                header_unfiltered = f"\n{acq_tag()} Top {len(top_results_unfiltered)} unfiltered subtitles: ({lang.upper()}):"
                print_and_log(header_unfiltered)
                print_subtitle_list(top_results_unfiltered, lang, color=Fore.LIGHTBLUE_EX)
                if top_results_unfiltered:
                    process_drift_batch(top_results_unfiltered, drift_files, lang, used_fallback=True)
                    continue
                print_and_log(f"{acq_tag()} No results without a filter, trying fallback search...")
                fallback_query = clean_title(raw_title)
                params["query"] = fallback_query
                response = requests.get(f"{API_URL}/subtitles", headers=headers, params=params)
                time.sleep(0.5)
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("data", [])
                    filtered_results = filter_subtitles_by_query(results, fallback_query)
                    top_results = prioritize_release_matches(sorted(filtered_results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:MAX_SEARCH_RESULTS], movie_path)
                    print_and_log(f"\n{acq_tag()} Top {len(top_results)} subtitles (fallback, {lang.upper()}):")
                    print_subtitle_list(top_results, lang, color=Fore.LIGHTBLUE_EX)
                    if top_results:
                        process_drift_batch(top_results, drift_files, lang, used_fallback=True)
                    else:
                        print_and_log(f"{acq_tag()} No results found for DRIFT file..")
                        mark_drift_as_failed(movie_path.parent, lang)
                        if not is_movie_language_skipped(movie_path, lang) and (query, movie_path, lang) not in missing_queries:
                            missing_queries.append((query, movie_path, lang))
                elif response.status_code == 401:
                    print_and_log(f"{acq_tag()} # JWT token invalid or expired. Fetching new token...")
                    new_token = get_jwt_token()
                    if new_token and new_token != jwt_token:
                        continue
                    else:
                        print_and_log(f"{acq_tag()} # Failed to retrieve new JWT token. Search stopped.")
                elif response.status_code == 403:
                    handle_api_error(response, {
                        "URL": f"{API_URL}/subtitles",
                        "Headers": headers,
                        "Params": params
                    })
            continue

    for lang in missing_langs:
        display_query = query
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "User-Agent": "NexigenSubtitleBot v1.0",
            "Api-Key": API_KEY
        }

        # Try IMDb ID search first if OMDb is configured
        response = None
        results = []
        imdb_trusted_ids = set()  # IDs from IMDb searches — never filtered by filename
        imdb_match_found = False  # Track if IMDb match was successful
        if OMDB_API_KEY:
            try:
                # For series: strip SxxExx from query and get year from filename
                # For movies: extract year from query as before
                if SERIES_MODE:
                    _sxxexx_q = extract_sxxexx_code(movie_path.name)
                    _title_for_omdb = re.sub(r'\s*[sS]\d{1,2}[eE]\d{1,2}.*', '', query).strip()
                    _title_for_omdb = clean_title(_title_for_omdb, all_before_anchor=True)
                    _year_match = re.search(r'(19|20)\d{2}', movie_path.name)
                    year = _year_match.group(0) if _year_match else None
                    title = _title_for_omdb
                else:
                    year_match = re.search(r'(19|20)\d{2}', query)
                    if year_match:
                        year = year_match.group(0)
                        title = query[:year_match.start()].strip()
                    else:
                        year = None
                        title = query.strip()
                    title = clean_title(title, all_before_anchor=True)
                
                # Lookup IMDb ID
                _omdb_type = 'series' if SERIES_MODE else 'movie'
                imdb_id = lookup_imdb_id_leading(title, year, media_type=_omdb_type)
                if imdb_id:
                    query = refine_query_with_imdb_title(raw_title, query)
                    params_imdb = {
                        "imdb_id": imdb_id,
                        "languages": lang
                    }
                    if SERIES_MODE:
                        _sxxexx = extract_sxxexx_code(movie_path.name)
                        if _sxxexx:
                            params_imdb["season_number"] = int(_sxxexx[1:3])
                            params_imdb["episode_number"] = int(_sxxexx[4:6])
                    print_and_log(f"{acq_tag()} {Fore.LIGHTCYAN_EX}[IMDb SEARCH]{Style.RESET_ALL} Searching for {Fore.LIGHTYELLOW_EX}{lang.upper()}{Style.RESET_ALL} subtitles using IMDb ID: {Fore.CYAN}{imdb_id}{Style.RESET_ALL}")
                    response = requests.get(f"{API_URL}/subtitles", headers=headers, params=params_imdb)
                    time.sleep(0.5)
                    if response.status_code == 200:
                        data = response.json()
                        imdb_results = data.get("data", [])
                        if imdb_results:
                            print_and_log(f"{acq_tag()} {Fore.GREEN}[OK] [IMDb MATCH]{Style.RESET_ALL} Found {Fore.GREEN}{len(imdb_results)}{Style.RESET_ALL} subtitle(s) for {Fore.LIGHTYELLOW_EX}{lang.upper()}{Style.RESET_ALL}")
                            results = imdb_results
                            imdb_trusted_ids = {r['id'] for r in imdb_results}
                            imdb_match_found = True  # Mark as IMDb match
                            # Also run text search and merge — some uploads are indexed under a different IMDb ID
                            try:
                                _params_text = {"query": query, "languages": lang}
                                _resp_text = requests.get(f"{API_URL}/subtitles", headers=headers, params=_params_text)
                                time.sleep(0.5)
                                if _resp_text.status_code == 200:
                                    _text_results = _resp_text.json().get("data", [])
                                    _existing_ids = {r['id'] for r in results}
                                    _new = [r for r in _text_results if r['id'] not in _existing_ids]
                                    if _new:
                                        print_and_log(f"{acq_tag()} {Fore.CYAN}[IMDb+Text merge]{Style.RESET_ALL} Added {len(_new)} extra result(s) from text search")
                                        results = results + _new
                                    else:
                                        print_and_log(f"{acq_tag()} {Fore.LIGHTBLACK_EX}[IMDb+Text merge] No new results from text search{Style.RESET_ALL}")
                            except Exception as _merge_e:
                                print_and_log(f"{acq_tag()} {Fore.YELLOW}[IMDb+Text merge] Failed: {_merge_e}{Style.RESET_ALL}")
                            # In series mode: also search by episode-specific IMDb ID
                            # (some uploads are indexed under the episode's own IMDb ID, not the show's)
                            if SERIES_MODE and OMDB_API_KEY:
                                try:
                                    _sxxexx_ep = extract_sxxexx_code(movie_path.name)
                                    if _sxxexx_ep:
                                        _ep_season = int(_sxxexx_ep[1:3])
                                        _ep_episode = int(_sxxexx_ep[4:6])
                                        _ep_imdb_id = get_episode_imdb_id_from_omdb(title, _ep_season, _ep_episode)
                                        if _ep_imdb_id and _ep_imdb_id != imdb_id:
                                            _params_ep = {"imdb_id": _ep_imdb_id, "languages": lang}
                                            _resp_ep = requests.get(f"{API_URL}/subtitles", headers=headers, params=_params_ep)
                                            time.sleep(0.5)
                                            if _resp_ep.status_code == 200:
                                                _ep_results = _resp_ep.json().get("data", [])
                                                # Mark ALL episode IMDb results as trusted (even if already in results via text merge)
                                                imdb_trusted_ids.update(r['id'] for r in _ep_results)
                                                _existing_ids = {r['id'] for r in results}
                                                _new_ep = [r for r in _ep_results if r['id'] not in _existing_ids]
                                                if _new_ep:
                                                    print_and_log(f"{acq_tag()} {Fore.CYAN}[IMDb+Episode merge]{Style.RESET_ALL} Added {len(_new_ep)} extra result(s) via episode IMDb ID {_ep_imdb_id}")
                                                    results = results + _new_ep
                                                else:
                                                    print_and_log(f"{acq_tag()} {Fore.LIGHTBLACK_EX}[IMDb+Episode merge] No new results, but {len(_ep_results)} result(s) now trusted via episode IMDb ID{Style.RESET_ALL}")
                                except Exception as _ep_e:
                                    print_and_log(f"{acq_tag()} {Fore.YELLOW}[IMDb+Episode merge] Failed: {_ep_e}{Style.RESET_ALL}")
                        else:
                            print_and_log(f"{acq_tag()} {Fore.YELLOW}[IMDb] No results found{Style.RESET_ALL}")
                            response = None
                    else:
                        print_and_log(f"{acq_tag()} {Fore.YELLOW}[IMDb] Search failed (HTTP {response.status_code}){Style.RESET_ALL}")
                        response = None
            except Exception as e:
                print_and_log(f"{acq_tag()} {Fore.YELLOW}[IMDb] Lookup failed: {str(e)}{Style.RESET_ALL}")
                response = None

        # Try hash-based search if IMDb search failed and hash is enabled
        if (not response or response.status_code != 200) and USE_MOVIE_HASH:
            try:
                movie_hash = calculate_hash(movie_path)
                file_size = movie_path.stat().st_size
                params_hash = {
                    "moviehash": movie_hash,
                    "moviebytesize": str(file_size),
                    "languages": lang
                }
                print_and_log(f"{acq_tag()} {Fore.LIGHTMAGENTA_EX}[HASH SEARCH]{Style.RESET_ALL} Searching for {Fore.LIGHTYELLOW_EX}{lang.upper()}{Style.RESET_ALL} subtitles using file hash")
                response = requests.get(f"{API_URL}/subtitles", headers=headers, params=params_hash)
                time.sleep(0.5)
                if response.status_code == 200:
                    data = response.json()
                    hash_results = data.get("data", [])
                    if hash_results:
                        print_and_log(f"{acq_tag()} {Fore.GREEN}[OK] [HASH MATCH]{Style.RESET_ALL} Found {Fore.GREEN}{len(hash_results)}{Style.RESET_ALL} subtitle(s) for {Fore.LIGHTYELLOW_EX}{lang.upper()}{Style.RESET_ALL}")
                        results = hash_results
                    else:
                        print_and_log(f"{acq_tag()} {Fore.YELLOW}[HASH] No results found{Style.RESET_ALL}")
                        response = None
                else:
                    print_and_log(f"{acq_tag()} {Fore.YELLOW}[HASH] Search failed (HTTP {response.status_code}){Style.RESET_ALL}")
                    response = None
            except Exception as e:
                print_and_log(f"{acq_tag()} {Fore.YELLOW}[HASH] Calculation failed: {str(e)}{Style.RESET_ALL}")
                response = None

        # Fallback to text-based search if IMDb and hash search failed
        if not response or response.status_code != 200:
            params = {
                "query": query,
                "languages": lang
            }
            print_and_log(f"{acq_tag()} {Fore.CYAN}[TEXT SEARCH]{Style.RESET_ALL} Searching for {Fore.LIGHTYELLOW_EX}{lang.upper()}{Style.RESET_ALL}: '{Fore.WHITE}{display_query}{Style.RESET_ALL}'")
            response = requests.get(f"{API_URL}/subtitles", headers=headers, params=params)
            time.sleep(0.5)

        if response.status_code == 200:
            if not results:  # Only get results if not already retrieved from hash search
                data = response.json()
                results = data.get("data", [])
            
            # Debug: Log raw API results count
            print_and_log(f"{acq_tag()} {Fore.LIGHTBLACK_EX}→ API returned {len(results)} raw results{Style.RESET_ALL}")
            
            # IMDb-matched results are trusted (API already filtered by season/episode) — don't apply filename filter to them
            trusted = [r for r in results if r['id'] in imdb_trusted_ids]
            untrusted = [r for r in results if r['id'] not in imdb_trusted_ids]
            filtered_untrusted = filter_subtitles_by_query(untrusted, query)
            filtered_results = trusted + filtered_untrusted
            existing_counts, total_existing = count_existing_subtitles(movie_path, lang)
            filtered_results = [r for r in filtered_results if r['attributes'].get('download_count', 0) not in existing_counts]
            
            # Calculate how many we need to download based on extracted subtitles
            target_downloads = SUBTITLE_BATCH_SIZE
            if SERIES_MODE:
                # Check for extracted subtitles for this episode
                sxxexx_code = extract_sxxexx_code(movie_path.name)
                if sxxexx_code:
                    extracted_count = len(list(movie_path.parent.glob(f"*.{lang}.number*.{sxxexx_code}.srt")))
                    if extracted_count > 0:
                        target_downloads = max(0, SUBTITLE_BATCH_SIZE - extracted_count)
                        if target_downloads == 0:
                            print_and_log(f"{acq_tag()} {Fore.GREEN}No additional downloads needed for {lang.upper()} - {extracted_count} extracted subtitles already available{Style.RESET_ALL}")
                            continue
                        else:
                            print_and_log(f"{acq_tag()} {Fore.YELLOW}Downloading {target_downloads} additional subtitles for {lang.upper()} (have {extracted_count} extracted)...{Style.RESET_ALL}")
            
            if total_existing >= MAX_SEARCH_RESULTS:
                print_and_log(f"{acq_tag()} {Fore.YELLOW}MAX_SEARCH_RESULTS limit ({MAX_SEARCH_RESULTS}) reached for {lang.upper()}. Skipping to missing_queries.{Style.RESET_ALL}")
                if not is_movie_language_skipped(movie_path, lang):
                    missing_queries.append((display_query, movie_path, lang))
                continue
            remaining_slots = MAX_SEARCH_RESULTS - total_existing
            top_results = prioritize_release_matches(sorted(filtered_results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:remaining_slots], movie_path)
            header = f"\n{acq_tag()} Top {len(top_results)} subtitles ({lang.upper()}):"
            print_and_log(header)
            print_subtitle_list(top_results, lang, color=Fore.LIGHTBLUE_EX)
            if top_results:
                start_index = get_next_sub_index(movie_path.parent, lang, movie_path)
                download_candidate_batch(top_results[:target_downloads], lang, movie_path.parent, jwt_token, movie_path, start_index)
                if quota_exceeded:
                    return
                # Write metadata about IMDb match status
                write_subtitle_metadata(movie_path.parent, movie_path.stem, lang, imdb_match_found)
                # Next language continues below on the same screen; the screen is only refreshed for the next video
                if len(missing_langs) > 1 and lang != missing_langs[-1]:
                    print_and_log("")
                continue
            print_and_log(f"{acq_tag()} No results with filter, trying without a filter...")
            unfiltered_results = [r for r in results if r['attributes'].get('download_count', 0) not in existing_counts]
            _, total_existing = count_existing_subtitles(movie_path, lang)
            
            if total_existing >= MAX_SEARCH_RESULTS:
                print_and_log(f"{acq_tag()} {Fore.YELLOW}MAX_SEARCH_RESULTS limit ({MAX_SEARCH_RESULTS}) reached for {lang.upper()} during unfiltered search.{Style.RESET_ALL}")
                if not is_movie_language_skipped(movie_path, lang):
                    missing_queries.append((display_query, movie_path, lang))
                continue
            remaining_slots = MAX_SEARCH_RESULTS - total_existing
            top_unfiltered = prioritize_release_matches(sorted(unfiltered_results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:remaining_slots], movie_path)
            print_and_log(f"\n{acq_tag()} Top {len(top_unfiltered)} subtitles UNFILTERED ({lang.upper()}):")
            print_subtitle_list(top_unfiltered, lang, color=Fore.LIGHTBLUE_EX)
            if top_unfiltered:
                start_index = get_next_sub_index(movie_path.parent, lang, movie_path)
                download_candidate_batch(top_unfiltered[:target_downloads], lang, movie_path.parent, jwt_token, movie_path, start_index)
                if quota_exceeded:
                    return
                # Write metadata about IMDb match status
                write_subtitle_metadata(movie_path.parent, movie_path.stem, lang, imdb_match_found)
                # Next language continues below on the same screen; the screen is only refreshed for the next video
                if len(missing_langs) > 1 and lang != missing_langs[-1]:
                    print_and_log("")
                continue
            print_and_log(f"{acq_tag()} No results without a filter, trying fallback search...")
            fallback_query = clean_title(raw_title)
            params_fallback = {
                "query": fallback_query,
                "languages": lang
            }
            response_fallback = requests.get(f"{API_URL}/subtitles", headers=headers, params=params_fallback)
            time.sleep(0.5)
            if response_fallback.status_code == 200:
                data_fallback = response_fallback.json()
                results_fallback = data_fallback.get("data", [])
                fallback_filtered = [r for r in results_fallback if r['attributes'].get('download_count', 0) not in existing_counts]
                _, total_existing = count_existing_subtitles(movie_path, lang)
                if total_existing >= MAX_SEARCH_RESULTS:
                    print_and_log(f"{acq_tag()} {Fore.YELLOW}MAX_SEARCH_RESULTS limit ({MAX_SEARCH_RESULTS}) reached for {lang.upper()} during fallback search.{Style.RESET_ALL}")
                    if not is_movie_language_skipped(movie_path, lang):
                        missing_queries.append((display_query, movie_path, lang))
                    continue
                remaining_slots = MAX_SEARCH_RESULTS - total_existing
                top_fallback = prioritize_release_matches(sorted(fallback_filtered, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:remaining_slots], movie_path)
                print_and_log(f"\n{acq_tag()} Top {len(top_fallback)} subtitles (clean_title, UNFILTERED, {lang.upper()}):")
                print_subtitle_list(top_fallback, lang, color=Fore.LIGHTRED_EX)
                if top_fallback:
                    start_index = get_next_sub_index(movie_path.parent, lang, movie_path)
                    download_candidate_batch(top_fallback[:target_downloads], lang, movie_path.parent, jwt_token, movie_path, start_index)
                    if quota_exceeded:
                        return
                    # Write metadata about IMDb match status
                    write_subtitle_metadata(movie_path.parent, movie_path.stem, lang, imdb_match_found)
                    # Next language continues below on the same screen; the screen is only refreshed for the next video
                    if len(missing_langs) > 1 and lang != missing_langs[-1]:
                        print_and_log("")
                    continue
            if not is_movie_language_skipped(movie_path, lang):
                missing_queries.append((display_query, movie_path, lang))
            continue
        elif response.status_code == 403:
            handle_api_error(response, {
                "URL": f"{API_URL}/subtitles",
                "Headers": headers,
                "Params": params
            })
            continue
        else:
            print_and_log(f"{acq_tag()} Error requesting OpenSubtitles for {query}: {response.status_code}")
            print_and_log(f"{acq_tag()} Response body:")
            print_and_log(response.text)
            continue
        fallback_query = clean_title(raw_title)
        params["query"] = fallback_query
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            response = requests.get(f"{API_URL}/subtitles", headers=headers, params=params)
            time.sleep(0.5)
            if response.status_code == 200:
                break
            else:
                msg = f"{acq_tag()} {Fore.YELLOW}Error {response.status_code} (attempt {attempt}/{max_retries})...{Style.RESET_ALL}"
                print(f"\r{msg}", end="", flush=True)
                if attempt < max_retries:
                    time.sleep(PAUSE_SECONDS)
                else:
                    print()
        if response.status_code == 200:
            data = response.json()
            results = data.get("data", [])
            filtered_results = filter_subtitles_by_query(results, fallback_query)
            top_results = prioritize_release_matches(sorted(filtered_results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:MAX_SEARCH_RESULTS], movie_path)
            print_and_log(f"\n{acq_tag()} Top {len(top_results)} subtitles ({lang.upper()}):")
            print_subtitle_list(top_results, lang, color=Fore.LIGHTBLUE_EX)
            if top_results:
                print_and_log(f"{acq_tag()} [PRE-INDEX] About to call get_next_sub_index for {lang}, episode {extract_sxxexx_code(movie_path.name)}")
                start_index = get_next_sub_index(movie_path.parent, lang, movie_path)
                print_and_log(f"{acq_tag()} [POST-INDEX] get_next_sub_index returned: {start_index}")
                download_candidate_batch(top_results[:target_downloads], lang, movie_path.parent, jwt_token, movie_path, start_index)
                if quota_exceeded:
                    return
        elif response.status_code == 401:
            print_and_log(f"{acq_tag()} JWT token invalid or expired. Fetching new token...")
            new_token = get_jwt_token()
            if new_token and new_token != jwt_token:
                continue 
            else:
                print_and_log(f"{acq_tag()} Failed to retrieve new JWT token. Search stopped.")
        elif response.status_code == 403:
            handle_api_error(response, {
                "URL": f"{API_URL}/subtitles",
                "Headers": headers,
                "Params": params_fallback
            })
        else:
            print_and_log(f"{acq_tag()} Error requesting OpenSubtitles for {fallback_query}: {response.status_code}")
            print_and_log(f"{acq_tag()} # Response body:")
            print_and_log(response.text)
def mark_drift_as_failed(folder: Path, lang: str):
    drift_files = get_subtitle_files_by_pattern(folder, lang, ".DRIFT")
    for drift_file in drift_files:
        failed_file = drift_file.with_name(drift_file.name.replace(".DRIFT.srt", ".FAILED.srt"))
        try:
            drift_file.rename(failed_file)
            print_and_log_colored(
                f"{acq_tag()} {Fore.MAGENTA}Marked as FAILED: {failed_file.name}{Style.RESET_ALL}",
                Fore.MAGENTA
            )
        except Exception as e:
            print_and_log_colored(
                f"{acq_tag()} {Fore.RED}Failed to mark as FAILED: {drift_file.name} ({e}){Style.RESET_ALL}",
                Fore.RED
            )

def get_skipped_movies_from_config():
    if not CONFIG_PATH.exists():
        return {}
    lines = CONFIG_PATH.read_text(encoding='utf-8').splitlines()
    in_skipped = False
    skipped = {}
    for line in lines:
        if line.strip() == '[skipped_movies]':
            in_skipped = True
            continue
        if in_skipped:
            if line.strip().startswith('['):
                break
            if line.strip():
                entry = line.strip()
                if '[' in entry and entry.endswith(']'):
                    parts = entry.rsplit(' [', 1)
                    if len(parts) == 2:
                        movie_path = parts[0]
                        lang_part = parts[1][:-1]
                        languages = {lang.strip().lower() for lang in lang_part.split(',') if lang.strip()}
                        skipped[movie_path] = languages
    return skipped

def is_movie_language_skipped(mkv_path: Path, language: str) -> bool:
    skipped_movies = get_skipped_movies_from_config()
    movie_key = str(mkv_path.resolve())
    
    if movie_key in skipped_movies:
        skipped_langs = skipped_movies[movie_key]
        return language.lower() in skipped_langs
    return False

def add_skipped_movie_language_to_config(movie_path: Path, language: str):
    skipped_movies = get_skipped_movies_from_config()
    movie_key = str(movie_path.resolve())
    
    if movie_key in skipped_movies:
        skipped_movies[movie_key].add(language.lower())
    else:
        skipped_movies[movie_key] = {language.lower()}
    skipped_entries = set()
    for path, languages in skipped_movies.items():
        if languages:
            lang_str = ','.join(sorted(languages)).upper()
            skipped_entries.add(f"{path} [{lang_str}]")
    write_runtime_blocks_to_config(skipped_entries=skipped_entries)

def handle_missing_queries():
    clear_and_print_ascii(BANNER_LINE)
    skipped_movies = get_skipped_movies_from_config()
    if not missing_queries:
        print_and_log(f"\n{acq_tag()} {Fore.GREEN}*{Style.RESET_ALL} All movies processed. Opening synchronisation.py in {int(PAUSE_SECONDS)} seconds...")
        time.sleep(PAUSE_SECONDS)
        sync_script_path = SNAPSHOT_DIR / "synchronisation.py"
        if sync_script_path.exists():
            os.system(f'python "{sync_script_path}"')
            print_and_log(f"{acq_tag()} {Fore.GREEN}*{Style.RESET_ALL} acquisition.py will now close.")
            sys.exit(0)
        return
    print_and_log(f"\n{acq_tag()} {Fore.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Style.RESET_ALL}")
    print_and_log(f"{acq_tag()} {Fore.YELLOW}{Style.BRIGHT}Out of subtitle candidates.{Style.RESET_ALL} {Fore.WHITE}Low quality scores (<20) were filtered out.{Style.RESET_ALL}")
    print_and_log(f"{acq_tag()} {Fore.WHITE}In rare cases, these might still sync reasonably well. You can now try{Style.RESET_ALL}")
    print_and_log(f"{acq_tag()} {Fore.WHITE}loading FAILED subtitles manually when prompted for each file,{Style.RESET_ALL}")
    print_and_log(f"{acq_tag()} {Fore.WHITE}increase the amount of subtitle candidates, or try any of the other options.{Style.RESET_ALL}")
    print_and_log(f"{acq_tag()} {Fore.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Style.RESET_ALL}\n")
    print_and_log(f"{acq_tag()} {Fore.YELLOW}No results for these search queries:{Style.RESET_ALL}\n")
    for i, (query, mkv_path, search_lang) in enumerate(missing_queries, 1):
        lang_disp = search_lang.upper()
        if re.search(rf'\[{lang_disp}\]$', query, flags=re.IGNORECASE):
            query_disp = re.sub(rf'\[{lang_disp}\]$', f"{Fore.YELLOW}[{lang_disp}]{Style.RESET_ALL}", query, flags=re.IGNORECASE)
        else:
            query_disp = f"{query} {Fore.YELLOW}[{lang_disp}]{Style.RESET_ALL}"
        print_and_log(f"  {Fore.RED}{i}.{Style.RESET_ALL}")
        print_and_log(f"    {Fore.CYAN}Search Query:{Style.RESET_ALL}   {Style.BRIGHT}{query_disp}{Style.RESET_ALL}")
        print_and_log(f"    {Fore.MAGENTA}File:{Style.RESET_ALL}    {mkv_path.name}")
    input_and_log(f"\n{acq_tag()} Let's decide on what to do..")
    queries = missing_queries.copy()
    total = len(queries)
    idx = 0
    display_idx = 1
    while idx < len(queries):
        query, mkv_path, search_lang = queries[idx]
        search_lang = search_lang.lower()
        if is_movie_language_skipped(mkv_path, search_lang):
            idx += 1
            display_idx += 1
            continue
        lang_tag = f"[{search_lang.upper()}]"
        if re.search(rf'\[{search_lang}\]$', query, flags=re.IGNORECASE):
            query_disp = re.sub(rf'\[{search_lang}\]$', f"{Fore.YELLOW}{lang_tag}{Style.RESET_ALL}", query, flags=re.IGNORECASE)
        else:
            query_disp = f"{query} {Fore.YELLOW}{lang_tag}{Style.RESET_ALL}"
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"\n{Style.BRIGHT}{Fore.CYAN}Movie [{display_idx}/{total}]{Style.RESET_ALL}")
        print_and_log(f"{acq_tag()} What to do with: '{Style.BRIGHT}{query_disp}{Style.RESET_ALL}{Fore.YELLOW}?{Style.RESET_ALL}'\nFile: {Fore.CYAN}{mkv_path.name}{Style.RESET_ALL}\n")
        print_and_log(f"  {Fore.LIGHTBLUE_EX}1{Style.RESET_ALL} = Type in a manual search term {Fore.LIGHTBLACK_EX}(manual search to check for subtitles){Style.RESET_ALL}")
        print_and_log(f"  {Fore.LIGHTBLUE_EX}2{Style.RESET_ALL} = Test FAILED [{Fore.LIGHTYELLOW_EX}{search_lang.upper()}{Style.RESET_ALL}] subtitles manually {Fore.LIGHTBLACK_EX}(double check if FAILED subtitles are actually wrong){Style.RESET_ALL}")
        print_and_log(f"  {Fore.LIGHTBLUE_EX}3{Style.RESET_ALL} = Increase global subtitle download limit {Fore.LIGHTBLACK_EX}(affects all movies/languages){Style.RESET_ALL}")
        print_and_log(f"  {Fore.LIGHTBLUE_EX}4{Style.RESET_ALL} = Skip {Fore.LIGHTBLACK_EX}(do nothing){Style.RESET_ALL}")
        print_and_log(f"  {Fore.LIGHTBLUE_EX}5{Style.RESET_ALL} = Skip [{Fore.LIGHTYELLOW_EX}{search_lang.upper()}{Style.RESET_ALL}] language and do not show again {Fore.LIGHTBLACK_EX}(adds movie to skipped_movies){Style.RESET_ALL}")
        print_and_log(f"\n{Fore.LIGHTYELLOW_EX}NOTE:{Style.RESET_ALL} {Fore.WHITE}If all options are exhausted (including manual FAILED subtitle testing), no matching")
        print_and_log(f"      subtitle may exist for your video release. Consider obtaining a different release or using")
        print_and_log(f"      an internal bitmap-based subtitle if one was already embedded in the video file.{Style.RESET_ALL}")
        choice = input_and_log(f"\nChoose [{Fore.LIGHTBLUE_EX}1{Style.RESET_ALL}/{Fore.LIGHTBLUE_EX}2{Style.RESET_ALL}/{Fore.LIGHTBLUE_EX}3{Style.RESET_ALL}/{Fore.LIGHTBLUE_EX}4{Style.RESET_ALL}/{Fore.LIGHTBLUE_EX}5{Style.RESET_ALL}]: ").strip()
        if choice == "1":
            print_and_log("[ACTION] User chose to type a manual search term.")
            download_successful = False
            while not download_successful:
                new_query = input_and_log(f"{acq_tag()} {Fore.LIGHTYELLOW_EX}Type in a manual search term{Style.RESET_ALL} (or press {Fore.LIGHTYELLOW_EX}enter{Style.RESET_ALL} to go back): ").strip()
                if not new_query:
                    clear_and_print_ascii(BANNER_LINE)
                    print_and_log(f"\n{Style.BRIGHT}{Fore.CYAN}Movie [{display_idx}/{total}]{Style.RESET_ALL}")
                    print_and_log(f"{acq_tag()} What to do with: '{Style.BRIGHT}{query_disp}{Style.RESET_ALL}{Fore.YELLOW}?{Style.RESET_ALL}'\nFile: {Fore.CYAN}{mkv_path.name}{Style.RESET_ALL}\n")
                    print_and_log(f"  {Fore.LIGHTBLUE_EX}1{Style.RESET_ALL} = Type in a manual search term {Fore.LIGHTBLACK_EX}(manual search to check for subtitles){Style.RESET_ALL}")
                    print_and_log(f"  {Fore.LIGHTBLUE_EX}2{Style.RESET_ALL} = Test FAILED [{Fore.LIGHTYELLOW_EX}{search_lang.upper()}{Style.RESET_ALL}] subtitles manually {Fore.LIGHTBLACK_EX}(double check if FAILED subtitles are actually wrong){Style.RESET_ALL}")
                    print_and_log(f"  {Fore.LIGHTBLUE_EX}3{Style.RESET_ALL} = Increase maximum download limit for this movie {Fore.LIGHTBLACK_EX}(affects all movies/languages){Style.RESET_ALL}")
                    print_and_log(f"  {Fore.LIGHTBLUE_EX}4{Style.RESET_ALL} = Skip {Fore.LIGHTBLACK_EX}(do nothing){Style.RESET_ALL}")
                    print_and_log(f"  {Fore.LIGHTBLUE_EX}5{Style.RESET_ALL} = Skip [{Fore.LIGHTYELLOW_EX}{search_lang.upper()}{Style.RESET_ALL}] and do not show again {Fore.LIGHTBLACK_EX}(adds movie to skipped_movies){Style.RESET_ALL}")
                    break
                headers = {
                    "Authorization": f"Bearer {get_jwt_token()}",
                    "User-Agent": "NexigenSubtitleBot v1.0",
                    "Api-Key": API_KEY
                }
                params = {
                    "query": new_query,
                    "languages": search_lang
                }
                print_and_log(f"{acq_tag()} {Fore.YELLOW}*{Style.RESET_ALL} Searching: '{Style.BRIGHT}{new_query}{Style.RESET_ALL}' (LANGUAGE: {search_lang.upper()})")
                response = requests.get(f"{API_URL}/subtitles", headers=headers, params=params)
                time.sleep(0.5)
                if response.status_code == 200:
                    results = response.json().get("data", [])
                    drift_failed_counts = set()
                    all_sub_files = [
                        *mkv_path.parent.glob(f"*.{search_lang}.number*.DRIFT.srt"),
                        *mkv_path.parent.glob(f"*.{search_lang}.number*.FAILED.srt"),
                        *mkv_path.parent.glob(f"*.{search_lang}.number*.srt")
                    ]
                    for f in all_sub_files:
                        m = re.match(r"(P?\d+)." + re.escape(search_lang) + r".number\d+", f.name)
                        if m and not m.group(1).startswith('P'):
                            drift_failed_counts.add(int(m.group(1)))
                    filtered_results = []
                    for sub in results:
                        cand_downloads = sub['attributes'].get('download_count', 0)
                        if cand_downloads in drift_failed_counts:
                            continue
                        filtered_results.append(sub)
                    top_results = sorted(filtered_results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:MAX_SEARCH_RESULTS]
                    print_and_log(f"\n{acq_tag()} Top {len(top_results)} subtitles (manual search):")
                    print_subtitle_list(top_results, search_lang, color=Fore.LIGHTBLUE_EX)
                    if not top_results:
                        print_and_log(f"{acq_tag()} No results found for this search term.")
                        continue
                    print_and_log(f"\n{Fore.GREEN}1{Style.RESET_ALL} = Download subtitle(s) from the results above")
                    print_and_log(f"{Fore.YELLOW}2{Style.RESET_ALL} = Return to the previous menu")
                    download_choice = input_and_log(f"\n{acq_tag()} {Fore.LIGHTYELLOW_EX}Choose 1 to download or 2 to return{Style.RESET_ALL} (or press {Fore.LIGHTYELLOW_EX}enter{Style.RESET_ALL} to return): ").strip()
                    
                    if not download_choice or download_choice == "2":
                        clear_and_print_ascii(BANNER_LINE)
                        print_and_log(f"\n{Style.BRIGHT}{Fore.CYAN}Movie [{display_idx}/{total}]{Style.RESET_ALL}")
                        print_and_log(f"{acq_tag()} What to do with: '{Style.BRIGHT}{query_disp}{Style.RESET_ALL}{Fore.YELLOW}?{Style.RESET_ALL}'\nFile: {Fore.CYAN}{mkv_path.name}{Style.RESET_ALL}\n")
                        print_and_log(f"  {Fore.GREEN}1{Style.RESET_ALL} = Enter a manual search term")
                        print_and_log(f"  {Fore.RED}2{Style.RESET_ALL} = Delete video file (not the folder)")
                        print_and_log(f"  {Fore.YELLOW}3{Style.RESET_ALL} = Skip this language")
                        print_and_log(f"  {Fore.MAGENTA}4{Style.RESET_ALL} = Skip this language and do not show again")
                        break
                    if download_choice != "1":
                        print_and_log(f"{acq_tag()} Invalid choice. Please enter 1 or 2.")
                        continue
                    selection = input_and_log(f"\n{acq_tag()} {Fore.LIGHTYELLOW_EX}Enter the number(s) to download (e.g. 1,2,4){Style.RESET_ALL}, or press {Fore.LIGHTYELLOW_EX}enter{Style.RESET_ALL} to cancel: ").strip()
                    if not selection:
                        clear_and_print_ascii(BANNER_LINE)
                        print_and_log(f"\n{Style.BRIGHT}{Fore.CYAN}Movie [{display_idx}/{total}]{Style.RESET_ALL}")
                        print_and_log(f"{acq_tag()} What to do with: '{Style.BRIGHT}{query_disp}{Style.RESET_ALL}{Fore.YELLOW}?{Style.RESET_ALL}'\nFile: {Fore.CYAN}{mkv_path.name}{Style.RESET_ALL}\n")
                        print_and_log(f"  {Fore.GREEN}1{Style.RESET_ALL} = Enter a manual search term")
                        print_and_log(f"  {Fore.RED}2{Style.RESET_ALL} = Delete video file (not the folder)")
                        print_and_log(f"  {Fore.YELLOW}3{Style.RESET_ALL} = Skip this language")
                        print_and_log(f"  {Fore.MAGENTA}4{Style.RESET_ALL} = Skip this language and do not show again")
                        break
                    if not re.fullmatch(r"\d+(,\d+)*", selection):
                        print_and_log(f"{acq_tag()} Invalid input. Only comma-separated numbers are allowed (e.g. 1,2,4). Try again.")
                        continue
                    raw_indices = selection.split(',')
                    indices = []
                    for s in raw_indices:
                        idx_num = int(s)
                        if 1 <= idx_num <= len(top_results):
                            if idx_num not in indices:
                                indices.append(idx_num)
                    if not indices:
                        print_and_log(f"{acq_tag()} Invalid choice. Please enter valid number(s) or press Enter to return.")
                        continue
                    next_index = get_next_sub_index(mkv_path.parent, search_lang, mkv_path)
                    for idx_to_download in indices:
                        download_top_subtitles(
                            [top_results[idx_to_download-1]],
                            search_lang,
                            mkv_path.parent,
                            get_jwt_token(),
                            mkv_path=mkv_path,
                            candidate_index=next_index,
                            force_download=True
                        )
                        print_and_log(f"{acq_tag()} Download complete for entry {idx_to_download}.")
                        next_index += 1
                    print_and_log(f"\n{Fore.LIGHTYELLOW_EX}{Style.BRIGHT}Download successful! Moving to next query in {int(PAUSE_SECONDS)} seconds...{Style.RESET_ALL}")
                    time.sleep(PAUSE_SECONDS)
                    download_successful = True
                    if (query, mkv_path, search_lang) in missing_queries:
                        missing_queries.remove((query, mkv_path, search_lang))
                    if idx < len(queries):
                        queries.pop(idx)
                    display_idx += 1
                    break
        elif choice == "2":
            print_and_log("[ACTION] User chose to test FAILED subtitles.")
            subtitle_accepted = test_failed_subtitles(mkv_path, search_lang, query_disp, display_idx, total)
            if subtitle_accepted:
                # Subtitle was accepted, remove from missing queries
                missing_queries.remove((query, mkv_path, search_lang))
                queries.pop(idx)
                display_idx += 1
            # If not accepted, continue with same query
            continue
        elif choice == "3":
            print_and_log("[ACTION] User chose to increase global download limit.")
            print_and_log(f"{acq_tag()} {Fore.LIGHTBLACK_EX}This will first open another menu before executing.{Style.RESET_ALL}")
            while True:
                new_limit_input = input_and_log(f"\n{acq_tag()} {Fore.LIGHTYELLOW_EX}Enter new global download limit (max 50){Style.RESET_ALL} (or press {Fore.LIGHTYELLOW_EX}enter{Style.RESET_ALL} to go back): ").strip()
                if not new_limit_input:
                    print_and_log(f"{acq_tag()} {Fore.YELLOW}*{Style.RESET_ALL} Returning to menu.")
                    break
                try:
                    new_limit = int(new_limit_input)
                    if new_limit <= 0:
                        print_and_log(f"{acq_tag()} {Fore.RED}Please enter a number greater than 0.{Style.RESET_ALL}")
                        continue
                    elif new_limit > 50:
                        print_and_log(f"{acq_tag()} {Fore.RED}Maximum allowed limit is 50. Please try again.{Style.RESET_ALL}")
                        continue
                    elif new_limit <= MAX_SEARCH_RESULTS:
                        print_and_log(f"{acq_tag()} {Fore.RED}New limit ({new_limit}) must be higher than current limit ({MAX_SEARCH_RESULTS}).{Style.RESET_ALL}")
                        continue
                    else:
                        clear_and_print_ascii(BANNER_LINE)
                        print_and_log(f"\n{acq_tag()} {Fore.CYAN}Configuration Change Summary:{Style.RESET_ALL}")
                        print_and_log(f"{acq_tag()} {Fore.YELLOW}Current max_search_results:{Style.RESET_ALL} {MAX_SEARCH_RESULTS}")
                        print_and_log(f"{acq_tag()} {Fore.GREEN}New max_search_results:{Style.RESET_ALL} {new_limit}")
                        print_and_log(f"\n{Fore.CYAN}What this does:{Style.RESET_ALL}")
                        print_and_log(f"  • Increases max_search_results in .config file")
                        print_and_log(f"  • Allows Subservient to download more subtitle candidates")
                        print_and_log(f"  • Restarts acquisition process with new limit")
                        print_and_log(f"\n{Fore.YELLOW}⚠ Important:{Style.RESET_ALL}")
                        print_and_log(f"  • This affects ALL videos in the current Subservient run")
                        print_and_log(f"  • Only recommended if you suspect relevant subtitle candidates")
                        print_and_log(f"    (same movie name, not completely unrelated subtitles)")
                        print_and_log(f"\n{Fore.GREEN}1{Style.RESET_ALL} = Yes, update config and restart with new limit")
                        print_and_log(f"{Fore.RED}2{Style.RESET_ALL} = No, cancel and return to menu")
                        confirm_choice = input_and_log(f"\n{acq_tag()} {Fore.LIGHTYELLOW_EX}Confirm configuration change{Style.RESET_ALL} [{Fore.GREEN}1{Style.RESET_ALL}/{Fore.RED}2{Style.RESET_ALL}]: ").strip()
                        
                        if confirm_choice == "1":
                            print_and_log(f"\n{acq_tag()} {Fore.GREEN}*{Style.RESET_ALL} Updating configuration...")
                            reset_count = reset_failed_to_drift(mkv_path.parent, search_lang)
                            if update_max_search_results_in_config(new_limit):
                                print_and_log(f"{acq_tag()} {Fore.GREEN}*{Style.RESET_ALL} Configuration updated successfully!")
                                print_and_log(f"{acq_tag()} {Fore.GREEN}*{Style.RESET_ALL} Restarting acquisition process with new limit...")
                                print_and_log(f"\n{Fore.LIGHTYELLOW_EX}Starting synchronization in {int(PAUSE_SECONDS)} seconds...{Style.RESET_ALL}")
                                time.sleep(PAUSE_SECONDS)
                                sync_script_path = SNAPSHOT_DIR / "synchronisation.py"
                                if sync_script_path.exists():
                                    os.system(f'python "{sync_script_path}"')
                                    print_and_log(f"{acq_tag()} {Fore.GREEN}*{Style.RESET_ALL} acquisition.py will now close.")
                                    sys.exit(0)
                                else:
                                    print_and_log(f"{acq_tag()} {Fore.RED}# {Style.RESET_ALL}synchronisation.py not found. Please restart manually.")
                                    sys.exit(1)
                            else:
                                print_and_log(f"{acq_tag()} {Fore.RED}Failed to update configuration. Returning to menu.{Style.RESET_ALL}")
                                break
                        else:
                            print_and_log(f"{acq_tag()} {Fore.YELLOW}*{Style.RESET_ALL} Configuration change cancelled. Returning to menu.")
                            break
                except ValueError:
                    print_and_log(f"{acq_tag()} {Fore.RED}Please enter a valid number.{Style.RESET_ALL}")
                    continue
            continue
        elif choice == "4":
            print_and_log("[ACTION] User chose to skip this movie.")
            print_and_log(f"\n{acq_tag()} {Fore.YELLOW}*{Style.RESET_ALL} {mkv_path.name} skipped.")
            input_and_log(f"{acq_tag()} Press Enter to continue...")
            missing_queries.remove((query, mkv_path, search_lang))
            queries.pop(idx)
            display_idx += 1
            continue
        elif choice == "5":
            print_and_log("[ACTION] User chose to skip and do not show again.")
            clear_and_print_ascii(BANNER_LINE)
            print_and_log(f"{Fore.CYAN}{mkv_path}{Style.RESET_ALL}\n")
            print_and_log(f"{acq_tag()} {Fore.MAGENTA}*{Style.RESET_ALL} You are about to skip this language ({search_lang.upper()}) for this movie and it will not be shown again.")
            print_and_log(f"{acq_tag()} {Fore.MAGENTA}*{Style.RESET_ALL} Other languages for this movie will still be processed.")
            print_and_log(f"{acq_tag()} {Fore.MAGENTA}*{Style.RESET_ALL} To show it again, edit the .config file and remove {search_lang.upper()} from [skipped_movies].")
            print_and_log(f"\nAre you sure? ({Fore.GREEN}y{Style.RESET_ALL}/{Fore.RED}n{Style.RESET_ALL})")
            confirm = input_and_log("").strip().lower()
            if confirm != 'y':
                print_and_log(f"{acq_tag()} {Fore.YELLOW}*{Style.RESET_ALL} Cancelled skip. Returning to menu.")
                continue
            add_skipped_movie_language_to_config(mkv_path, search_lang)
            print_and_log(f"\n{acq_tag()} {Fore.MAGENTA}*{Style.RESET_ALL} Language {search_lang.upper()} for this movie is now skipped.")
            print_and_log(f"{acq_tag()} {Fore.MAGENTA}*{Style.RESET_ALL} You can undo this by editing the .config file and removing {search_lang.upper()} from [skipped_movies].")
            input_and_log(f"\n{acq_tag()} Press Enter to continue...")
            missing_queries.remove((query, mkv_path, search_lang))
            queries.pop(idx)
            display_idx += 1
            continue
        else:
            print_and_log(f"[ACTION] User entered invalid choice: {choice}")
            print_and_log(f"{acq_tag()} {Fore.RED}# {Style.RESET_ALL}Invalid choice. Try again.")
            input_and_log(f"{acq_tag()} Press Enter to continue...")
    if missing_queries:
        handle_missing_queries()

def test_failed_subtitles(mkv_path: Path, search_lang: str, query_disp: str, display_idx: int, total: int):
    """Test FAILED and DRIFT subtitles manually by loading them in VLC and allowing user to accept/reject."""
    # In series mode, restrict to FAILED/DRIFT subtitles for this specific episode (SxxExx match)
    if SERIES_MODE:
        sxxexx = extract_sxxexx_code(mkv_path.name)
        if sxxexx:
            failed_subs = (
                list(mkv_path.parent.glob(f"*.{search_lang}.number*.{sxxexx}.FAILED.srt")) +
                list(mkv_path.parent.glob(f"*.{search_lang}.number*.{sxxexx}.DRIFT.srt"))
            )
        else:
            failed_subs = (
                list(mkv_path.parent.glob(f"*.{search_lang}.number*.FAILED.srt")) +
                list(mkv_path.parent.glob(f"*.{search_lang}.number*.DRIFT.srt"))
            )
    else:
        failed_subs = (
            list(mkv_path.parent.glob(f"*.{search_lang}.number*.FAILED.srt")) +
            list(mkv_path.parent.glob(f"*.{search_lang}.number*.DRIFT.srt"))
        )
    
    # Sort by number in filename (e.g., number1, number2, number3, etc.)
    def extract_number(sub_path):
        match = re.search(r'\.number(\d+)\.', sub_path.name)
        return int(match.group(1)) if match else 999999
    
    failed_subs = sorted(failed_subs, key=extract_number)
    
    if not failed_subs:
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"\n{Style.BRIGHT}{Fore.CYAN}Movie [{display_idx}/{total}]{Style.RESET_ALL}")
        print_and_log(f"{acq_tag()} {Fore.YELLOW}No FAILED subtitles found for {search_lang.upper()}{Style.RESET_ALL}")
        input_and_log(f"{acq_tag()} Press Enter to return to main menu...")
        return False
    
    # Track which subtitles have been tested and marked as bad
    drift_meta = load_drift_subtitle_metadata(DRIFT_METADATA_FILE)
    tested_bad = set()
    
    # FAILED subtitle selection menu
    while True:
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"\n{Style.BRIGHT}{Fore.CYAN}Movie [{display_idx}/{total}]{Style.RESET_ALL}")
        print_and_log(f"{acq_tag()} {Fore.YELLOW}FAILED subtitles for: {Style.BRIGHT}{query_disp}{Style.RESET_ALL}")
        print_and_log(f"File: {Fore.CYAN}{mkv_path.name}{Style.RESET_ALL}\n")
        
        # Show list of FAILED subtitles
        for i, sub in enumerate(failed_subs, 1):
            meta = drift_meta.get(make_drift_metadata_key(sub.name))
            if meta:
                if meta['correlation'] > 0:
                    q_str = f"  {Fore.LIGHTYELLOW_EX}Q:{int(meta['quality'])}/100{Style.RESET_ALL}"
                    c_str = f"  {Fore.CYAN}C:{meta['correlation']:.0f}{Style.RESET_ALL}"
                    bonus_str = f"  {Fore.LIGHTMAGENTA_EX}+{meta['bonus']}{Style.RESET_ALL}" if meta['bonus'] > 0 else ""
                    rej_str = f"  {Fore.RED}(rejected){Style.RESET_ALL}" if meta.get('rejected') else ""
                    meta_str = f"{q_str}{c_str}{bonus_str}{rej_str}"
                else:
                    meta_str = f"  {Fore.RED}(rejected){Style.RESET_ALL}" if meta.get('rejected') else ""
            else:
                meta_str = ""
            if sub in tested_bad:
                print_and_log(f"  {Fore.YELLOW}{i}{Style.RESET_ALL} = {Fore.LIGHTBLACK_EX}{sub.name}{Style.RESET_ALL}{meta_str}  {Fore.RED}(already tested){Style.RESET_ALL}")
            else:
                print_and_log(f"  {Fore.YELLOW}{i}{Style.RESET_ALL} = {Fore.LIGHTRED_EX}{sub.name}{Style.RESET_ALL}{meta_str}")
        
        print_and_log(f"\n{Fore.LIGHTYELLOW_EX}Please select a subtitle number.{Style.RESET_ALL}")
        print_and_log(f"{Fore.LIGHTYELLOW_EX}This will try opening your default video player loaded with the chosen subtitle.{Style.RESET_ALL}")
        print_and_log(f"\n  {Fore.YELLOW}0{Style.RESET_ALL} = Return to main menu")
        
        choice = input_and_log(f"\nChoose [1-{len(failed_subs)}/0]: ").strip()
        
        if choice == "0":
            return False
        
        try:
            idx = int(choice)
            if 1 <= idx <= len(failed_subs):
                selected_sub = failed_subs[idx - 1]
                
                # Open VLC with selected subtitle
                opened_with_vlc = False
                vlc_method = ""
                try:
                    # Try VLC first (can auto-load subtitle)
                    vlc_path = shutil.which("vlc")
                    
                    # If not in PATH, try common Windows installation paths
                    if not vlc_path:
                        common_paths = [
                            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
                        ]
                        for path in common_paths:
                            if Path(path).exists():
                                vlc_path = path
                                break
                    
                    if vlc_path:
                        subprocess.Popen([vlc_path, str(mkv_path), f':sub-file={str(selected_sub)}', '--no-sub-autodetect-file'], 
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        opened_with_vlc = True
                        vlc_method = "vlc"
                    else:
                        # Fallback to default video player (Windows)
                        os.startfile(str(mkv_path))
                        vlc_method = "default"
                except FileNotFoundError:
                    # VLC not found - show detailed error screen
                    clear_and_print_ascii(BANNER_LINE)
                    print_and_log(f"\n{Fore.RED}{Style.BRIGHT}╔═══════════════════════════════════════════════════════════════╗{Style.RESET_ALL}")
                    print_and_log(f"{Fore.RED}{Style.BRIGHT}║  VIDEO PLAYER ERROR - Could not open video automatically     ║{Style.RESET_ALL}")
                    print_and_log(f"{Fore.RED}{Style.BRIGHT}╚═══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}\n")
                    print_and_log(f"{Fore.CYAN}Video file:{Style.RESET_ALL}")
                    print_and_log(f"  {mkv_path}\n")
                    print_and_log(f"{Fore.CYAN}Subtitle file:{Style.RESET_ALL}")
                    print_and_log(f"  {selected_sub}\n")
                    print_and_log(f"{Fore.YELLOW}Possible causes:{Style.RESET_ALL}")
                    print_and_log(f"  {Fore.WHITE}•{Style.RESET_ALL} Video file is already open in another player")
                    print_and_log(f"  {Fore.WHITE}•{Style.RESET_ALL} VLC Media Player is not installed or not in system PATH")
                    print_and_log(f"  {Fore.WHITE}•{Style.RESET_ALL} Using a different video player (not VLC)\n")
                    print_and_log(f"{Fore.GREEN}Solutions:{Style.RESET_ALL}")
                    print_and_log(f"  {Fore.WHITE}1.{Style.RESET_ALL} Close the video if it's already open somewhere")
                    print_and_log(f"  {Fore.WHITE}2.{Style.RESET_ALL} Download and install VLC Media Player (recommended)")
                    print_and_log(f"  {Fore.WHITE}3.{Style.RESET_ALL} Manually open the video with the subtitle file above\n")
                    print_and_log(f"{Fore.CYAN}What would you like to do?{Style.RESET_ALL}")
                    print_and_log(f"  {Fore.LIGHTBLUE_EX}1{Style.RESET_ALL} = Return to subtitle selection")
                    print_and_log(f"  {Fore.LIGHTBLUE_EX}2{Style.RESET_ALL} = I will test the subtitle manually, please continue")
                    
                    error_choice = input_and_log(f"\nChoose [1/2]: ").strip()
                    if error_choice == "1":
                        continue  # Back to subtitle selection
                    elif error_choice == "2":
                        # User will test manually, proceed to assessment menu
                        pass  # Continue to assessment menu below
                    else:
                        continue  # Invalid choice, back to selection
                except Exception as e:
                    # Other errors
                    clear_and_print_ascii(BANNER_LINE)
                    print_and_log(f"\n{Fore.RED}{Style.BRIGHT}╔═══════════════════════════════════════════════════════════════╗{Style.RESET_ALL}")
                    print_and_log(f"{Fore.RED}{Style.BRIGHT}║  ERROR - Could not open video player                         ║{Style.RESET_ALL}")
                    print_and_log(f"{Fore.RED}{Style.BRIGHT}╚═══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}\n")
                    print_and_log(f"{Fore.CYAN}Video file:{Style.RESET_ALL} {mkv_path}")
                    print_and_log(f"{Fore.CYAN}Subtitle file:{Style.RESET_ALL} {selected_sub}")
                    print_and_log(f"{Fore.RED}Error:{Style.RESET_ALL} {str(e)}\n")
                    print_and_log(f"{Fore.YELLOW}Please ensure the video file is not open and VLC is installed.{Style.RESET_ALL}\n")
                    print_and_log(f"{Fore.CYAN}What would you like to do?{Style.RESET_ALL}")
                    print_and_log(f"  {Fore.LIGHTBLUE_EX}1{Style.RESET_ALL} = Return to subtitle selection")
                    print_and_log(f"  {Fore.LIGHTBLUE_EX}2{Style.RESET_ALL} = I will test the subtitle manually, please continue")
                    
                    error_choice = input_and_log(f"\nChoose [1/2]: ").strip()
                    if error_choice == "1":
                        continue  # Back to subtitle selection
                    elif error_choice == "2":
                        # User will test manually, proceed to assessment menu
                        pass  # Continue to assessment menu below
                    else:
                        continue  # Invalid choice, back to selection
                
                # Assessment menu
                clear_and_print_ascii(BANNER_LINE)
                print_and_log(f"\n{Style.BRIGHT}{Fore.CYAN}Movie [{display_idx}/{total}]{Style.RESET_ALL}")
                
                # Show status based on how video was opened
                if vlc_method == "vlc":
                    print_and_log(f"{Fore.GREEN}✓ Video opened in VLC with subtitle auto-loaded{Style.RESET_ALL}")
                elif vlc_method == "default":
                    print_and_log(f"{Fore.YELLOW}⚠ VLC not found - video opened in default player{Style.RESET_ALL}")
                    print_and_log(f"{Fore.YELLOW}  Subtitle NOT auto-loaded. Please load manually:{Style.RESET_ALL}")
                    print_and_log(f"{Fore.CYAN}  {selected_sub.name}{Style.RESET_ALL}")
                
                print_and_log(f"\n{acq_tag()} {Fore.CYAN}Testing: {selected_sub.name}{Style.RESET_ALL}\n")
                print_and_log(f"{Fore.LIGHTYELLOW_EX}Check if the subtitle matches. Press {Fore.GREEN}1{Fore.LIGHTYELLOW_EX} if correct, {Fore.YELLOW}2{Fore.LIGHTYELLOW_EX} if adjustable, or {Fore.RED}3{Fore.LIGHTYELLOW_EX} if unusable.{Style.RESET_ALL}\n")
                print_and_log(f"  {Fore.GREEN}1{Style.RESET_ALL} = Subtitle is correct - Accept and continue")
                print_and_log(f"  {Fore.YELLOW}2{Style.RESET_ALL} = Has potential - Needs offset adjustment")
                print_and_log(f"  {Fore.RED}3{Style.RESET_ALL} = Subtitle is bad - Return to selection")
                
                assess = input_and_log(f"\nChoose [{Fore.GREEN}1{Style.RESET_ALL}/{Fore.YELLOW}2{Style.RESET_ALL}/{Fore.RED}3{Style.RESET_ALL}]: ").strip()
                
                if assess == "1":
                    # Accept subtitle - rename to correct format
                    correct_name = f"{mkv_path.stem}.{search_lang}.srt"
                    correct_path = mkv_path.parent / correct_name
                    
                    try:
                        selected_sub.replace(correct_path)
                        print_and_log(f"{acq_tag()} {Fore.GREEN}✓ Subtitle accepted and renamed to {correct_name}{Style.RESET_ALL}")
                        time.sleep(1.5)
                        return True  # Subtitle accepted, exit menu
                    except Exception as e:
                        print_and_log(f"{acq_tag()} {Fore.RED}Error renaming subtitle: {e}{Style.RESET_ALL}")
                        input_and_log(f"{acq_tag()} Press Enter to continue...")
                        continue
                
                elif assess == "2":
                    # Has potential - add to movies_with_linear_offset.txt
                    correct_name = f"{mkv_path.stem}.{search_lang}.srt"
                    correct_path = mkv_path.parent / correct_name
                    
                    try:
                        selected_sub.replace(correct_path)
                    except Exception as e:
                        print_and_log(f"{acq_tag()} {Fore.RED}Error renaming subtitle: {e}{Style.RESET_ALL}")
                        input_and_log(f"{acq_tag()} Press Enter to continue...")
                        continue
                    
                    # Read first line for metadata
                    try:
                        with correct_path.open('r', encoding='utf-8', errors='ignore') as f:
                            lines = [l.strip() for l in f if l.strip() and not l.strip().isdigit()]
                            first_line = lines[0] if lines else ""
                    except:
                        first_line = ""
                    
                    # Check IMDb match status from .subtitle_metadata.txt
                    imdb_match_status = "unknown"
                    metadata_file = SNAPSHOT_DIR / ".subtitle_metadata.txt"
                    if metadata_file.exists():
                        try:
                            with metadata_file.open('r', encoding='utf-8') as f:
                                for line in f:
                                    if '|' in line:
                                        parts = line.strip().split('|')
                                        if len(parts) >= 3:
                                            if parts[0] == mkv_path.stem and parts[1] == search_lang:
                                                imdb_match_status = "yes" if parts[2] == "imdb_match" else "no"
                                                break
                        except Exception:
                            pass
                    
                    # Create entry for movies_with_linear_offset.txt
                    # Format must match what synchronisation.py's parser expects:
                    # line0: title [LANG], line1: folder, line2: video.mkv,
                    # line3: subtitle.srt, line4: offset, line5: correlation,
                    # line6: timestamp/first_line, line7: orig_numbered, then metadata
                    offset_file = SNAPSHOT_DIR / 'movies_with_linear_offset.txt'
                    
                    entry = f"{mkv_path.stem} [{search_lang.upper()}]\n"
                    entry += f"{str(mkv_path.parent)}\n"
                    entry += f"{mkv_path.name}\n"
                    entry += f"{correct_name}\n"
                    entry += f"0.000\n"  # User will adjust manually
                    entry += f"N/A\n"   # Correlation unknown from FAILED subtitle
                    entry += f"{first_line[:100]}\n"
                    entry += f"{correct_name}\n"  # orig_numbered placeholder
                    entry += f"Rejected: 0\n"
                    entry += f"IMDb_match: {imdb_match_status}\n"
                    entry += f"Quality: Manual Test (from FAILED)\n"
                    
                    # Read existing content
                    if offset_file.exists():
                        with offset_file.open('r', encoding='utf-8') as f:
                            existing_content = f.read()
                        if '\n--\n' in existing_content:
                            header = existing_content.split('\n--\n', 1)[0] + '\n--\n'
                            existing_entries = existing_content.split('\n--\n')[1:]
                        else:
                            header = "Linear offset tracking file for movies with subtitle sync corrections.\n"
                            header += "Format: movie name, path, offset, timestamp, first line, rejected count\n--\n"
                            existing_entries = []
                    else:
                        header = "Linear offset tracking file for movies with subtitle sync corrections.\n"
                        header += "Format: movie name, path, offset, timestamp, first line, rejected count\n--\n"
                        existing_entries = []
                    
                    # Write with new entry at top
                    with offset_file.open('w', encoding='utf-8') as f:
                        f.write(header)
                        f.write(entry)
                        f.write("\n--\n")
                        for existing in existing_entries:
                            if existing.strip():
                                f.write(existing.strip())
                                f.write("\n--\n")
                    
                    # Show confirmation
                    clear_and_print_ascii(BANNER_LINE)
                    print_and_log(f"\n{acq_tag()} {Fore.GREEN}✓ Subtitle saved and added to manual offset queue{Style.RESET_ALL}\n")
                    print_and_log(f"{Fore.CYAN}Next steps:{Style.RESET_ALL}")
                    print_and_log(f"  1. The subtitle will appear in the manual offset verification menu")
                    print_and_log(f"  2. You'll be able to adjust the offset in the editor")
                    print_and_log(f"  3. Changes will be applied when you save and exit the editor\n")
                    input_and_log(f"Press Enter to continue...")
                    return True  # Subtitle added to queue, exit menu
                
                elif assess == "3":
                    # Bad subtitle - mark as tested and return to selection
                    tested_bad.add(selected_sub)
                    continue
                else:
                    print_and_log(f"{acq_tag()} {Fore.RED}Invalid choice.{Style.RESET_ALL}")
                    input_and_log(f"{acq_tag()} Press Enter to continue...")
                    continue
            else:
                print_and_log(f"{acq_tag()} {Fore.RED}Invalid number.{Style.RESET_ALL}")
                input_and_log(f"{acq_tag()} Press Enter to continue...")
        except ValueError:
            print_and_log(f"{acq_tag()} {Fore.RED}Invalid input.{Style.RESET_ALL}")
            input_and_log(f"{acq_tag()} Press Enter to continue...")

def input_and_log(prompt):
    print_and_log(prompt, end='')
    answer = input('')
    with LOG_FILE.open('a', encoding='utf-8') as f:
        f.write(f'[USER INPUT] {strip_ansi(answer)}\n')
    return answer

def get_video_files_for_folder(folder: Path) -> list[Path]:
    video_files = [*folder.glob('*.mkv'), *folder.glob('*.mp4'), *folder.glob('*.avi')]
    if SERIES_MODE:
        return sorted(video_files)
    return [max(video_files, key=lambda f: f.stat().st_size)] if video_files else []
def print_video_header(video_name, idx, total):
    bar = f"{Fore.CYAN}[{idx}/{total}]{Style.RESET_ALL}  {Fore.LIGHTYELLOW_EX}{video_name.upper()}{Style.RESET_ALL}"
    print(bar.ljust(79), end='\n', flush=True)

def _get_next_p_number(video_folder: Path, lang: str, episode_sxxexx: str) -> int:
    """Find the next free P-number for a (language, episode) combination, so extracted
    subtitles are written directly in the P{n*100}.{lang}.number{n}.{SxxExx}.srt sync format."""
    existing = (
        list(video_folder.glob(f"P*.{lang.lower()}.number*.{episode_sxxexx}.srt")) +
        list(video_folder.glob(f"P*.{lang.lower()}.number*.{episode_sxxexx}.DRIFT.srt")) +
        list(video_folder.glob(f"P*.{lang.lower()}.number*.{episode_sxxexx}.FAILED.srt"))
    )
    indices = []
    for f in existing:
        m = re.search(r'\.number(\d+)\.', f.name)
        if m:
            indices.append(int(m.group(1)))
    return max(indices, default=0) + 1

def extract_subtitles_from_predownloaded_folders(video_folder: Path, video_files: list):
    """
    Extract subtitles from SUBTITLES.S##.LANG folders/zips for episodes that need them.
    Only extracts for episodes that don't already have synchronized subtitles.
    """
    import zipfile
    import shutil
    
    print_and_log(f"{acq_tag()} {Fore.CYAN}Processing pre-downloaded subtitle folders...{Style.RESET_ALL}")
    
    # Find all valid SUBTITLES folders
    subtitle_folders = []
    for item in video_folder.iterdir():
        item_name_lower = item.name.lower()
        if not re.match(r'subtitles\.s\d{1,2}(\.|$)', item_name_lower):
            continue
        if item.is_dir():
            archive_ext = None
        elif item_name_lower.endswith(('.zip', '.rar')):
            archive_ext = item_name_lower[-4:]
        else:
            continue

        stem_lower = item_name_lower[:-4] if archive_ext else item_name_lower
        parts = stem_lower.split('.')
        if len(parts) >= 3:
            # SUBTITLES.Sxx.LANG -> only this configured language
            lang = parts[-1].upper()
            if lang in [l.upper() for l in LANGUAGES]:
                subtitle_folders.append((item, lang))
        elif len(parts) == 2:
            # SUBTITLES.Sxx with no language -> search all configured languages
            subtitle_folders.append((item, None))
    
    if not subtitle_folders:
        return
    
    total_extracted = 0
    for subtitle_item, lang in subtitle_folders:
        lang_label = lang.upper() if lang else f"ALL configured ({', '.join(LANGUAGES)})"
        print_and_log(f"{acq_tag()} {Fore.YELLOW}Processing {subtitle_item.name} for language {lang_label}...{Style.RESET_ALL}")
        
        # Create temporary extraction directory if dealing with a ZIP or RAR archive
        temp_extract_dir = None
        if subtitle_item.name.lower().endswith(('.zip', '.rar')):
            temp_extract_dir = video_folder / f"temp_extract_{subtitle_item.stem}"
            temp_extract_dir.mkdir(exist_ok=True)

            if subtitle_item.name.lower().endswith('.zip'):
                with zipfile.ZipFile(subtitle_item, 'r') as zip_ref:
                    zip_ref.extractall(temp_extract_dir)
            else:
                try:
                    import rarfile
                except ImportError:
                    print_and_log(f"{acq_tag()} {Fore.RED}ERROR: The 'rarfile' package is required to extract '{subtitle_item.name}'. Install it with 'pip install rarfile' (and make sure 'unrar' or '7z' is on PATH).{Style.RESET_ALL}")
                    shutil.rmtree(temp_extract_dir, ignore_errors=True)
                    continue
                try:
                    with rarfile.RarFile(subtitle_item, 'r') as rar_ref:
                        rar_ref.extractall(temp_extract_dir)
                except Exception as e:
                    print_and_log(f"{acq_tag()} {Fore.RED}ERROR: Could not extract '{subtitle_item.name}': {e}. Make sure 'unrar' or '7z' is installed and on PATH.{Style.RESET_ALL}")
                    shutil.rmtree(temp_extract_dir, ignore_errors=True)
                    continue

            source_dir = temp_extract_dir
        else:
            source_dir = subtitle_item
        
        # Extract season number from the subtitle folder name (e.g. SUBTITLES.S02.EN -> S02, SUBTITLES.S2 -> S02)
        _season_match = re.search(r'subtitles\.(s\d{1,2})(\.|$)', subtitle_item.name, re.IGNORECASE)
        folder_season = _normalize_season_code(_season_match.group(1)) if _season_match else 'S01'

        try:
            # Collect episode folders, handling optional "Season X" / "Seizoen X" subfolder
            episode_dirs = []
            for _item in source_dir.iterdir():
                if not _item.is_dir():
                    continue
                # Recognize both "Episode N" folders and folders that carry an explicit
                # SxxExx code in their name (e.g. "Show.Name.S02E01.1080p...-RARBG[eztv.re]")
                if re.search(r'episode\s*\d+', _item.name, re.IGNORECASE) or extract_sxxexx_code(_item.name):
                    episode_dirs.append(_item)
                elif re.search(r'(season|seizoen)\s*\d+', _item.name, re.IGNORECASE):
                    # Drill one level deeper into Season X subfolder
                    for _sub in _item.iterdir():
                        if _sub.is_dir() and (re.search(r'episode\s*\d+', _sub.name, re.IGNORECASE) or extract_sxxexx_code(_sub.name)):
                            episode_dirs.append(_sub)

            if not episode_dirs:
                print_and_log(f"{acq_tag()} {Fore.YELLOW}No episode folders found in {subtitle_item.name}{Style.RESET_ALL}")

            # Process each episode folder inside the subtitle folder
            for episode_folder in episode_dirs:
                # Prefer an explicit SxxExx code in the folder name (e.g. "Show.S02E01...")
                # over the "episode N" naming convention. If neither is found on the episode
                # folder itself, also check its parent folder (e.g. a "Season 1" wrapper) and
                # a handful of other popular episode-number notations before giving up.
                folder_sxxexx = extract_sxxexx_code(episode_folder.name) or extract_sxxexx_code(episode_folder.parent.name)
                episode_match = re.search(r'episode\s*(\d{1,2})', episode_folder.name, re.IGNORECASE) or \
                    re.search(r'episode\s*(\d{1,2})', episode_folder.parent.name, re.IGNORECASE)
                if folder_sxxexx:
                    episode_sxxexx = folder_sxxexx
                elif episode_match:
                    episode_num = int(episode_match.group(1))
                    episode_sxxexx = f"{folder_season}E{episode_num:02d}"
                else:
                    loose_num = _find_episode_number_loosely(episode_folder.name) or _find_episode_number_loosely(episode_folder.parent.name)
                    if loose_num:
                        episode_sxxexx = f"{folder_season}E{loose_num:02d}"
                    else:
                        # No SxxExx (or anything resembling it) could be determined at all.
                        # We cannot safely auto-rename these subtitles without knowing the
                        # episode they belong to, so stop here and let the user fix it manually.
                        print_and_log(f"{acq_tag()} {Fore.RED}ERROR: Could not determine the season/episode for '{episode_folder.name}' in {subtitle_item.name}.{Style.RESET_ALL}")
                        print_and_log(f"{acq_tag()} {Fore.RED}Rename this folder to include a SxxExx code (e.g. 'S{folder_season[1:]}E01') so its episode can be identified, then run acquisition.py again.{Style.RESET_ALL}")
                        exit_with_prompt(f"{Fore.RED}Press any key to exit...{Style.RESET_ALL}")
                
                # Find corresponding video file
                matching_video = None
                for video_file in video_files:
                    video_sxxexx = extract_sxxexx_code(video_file.name)
                    if video_sxxexx and video_sxxexx == episode_sxxexx:
                        matching_video = video_file
                        break
                
                if not matching_video:
                    print_and_log(f"{acq_tag()} {Fore.YELLOW}No matching video found for {episode_folder.name} ({episode_sxxexx}){Style.RESET_ALL}")
                    continue

                if lang is not None:
                    # --- Single configured language (SUBTITLES.Sxx.LANG) - original behaviour ---

                    # Check if synchronized subtitle already exists
                    synced_subtitle_path = video_folder / f"{matching_video.stem}.{lang.lower()}.srt"
                    if synced_subtitle_path.exists():
                        print_and_log(f"{acq_tag()} {Fore.GREEN}Skipping {episode_folder.name} - synchronized subtitle already exists{Style.RESET_ALL}")
                        continue
                    
                    # Extended extraction prevention check
                    # Check if we already extracted subtitles from this episode folder previously
                    sxxexx_from_episode = episode_sxxexx  # S01E01 format
                    season_code = sxxexx_from_episode[:3]  # S01
                    episode_code = sxxexx_from_episode[3:]  # E01
                    
                    # Look for existing P-numbered files that match this season, episode, and language
                    p_numbered_pattern = f"P*.{lang.lower()}.number*.{sxxexx_from_episode}.srt"
                    existing_p_files = list(video_folder.glob(p_numbered_pattern))
                    
                    # Also look for any P-numbered files from this episode (any language) as indicator
                    any_p_numbered_pattern = f"P*.*.number*.{sxxexx_from_episode}.srt"
                    any_existing_p_files = list(video_folder.glob(any_p_numbered_pattern))
                    
                    if existing_p_files:
                        print_and_log(f"{acq_tag()} [DEBUG] Found {len(existing_p_files)} P-files for {lang.upper()} {sxxexx_from_episode}, checking prevention...")
                        
                        # Verify that the P-files came from this exact SUBTITLES folder and episode
                        skip_extraction = False
                        
                        # Check if season code (S01) matches the current SUBTITLES folder
                        season_match = season_code in subtitle_item.name
                        print_and_log(f"{acq_tag()} [DEBUG] Season match: {season_code} in {subtitle_item.name} = {season_match}")
                        
                        if season_match:
                            # Extract episode number from folder name like "episode 1" -> "1"
                            # Then convert to E01 format for comparison
                            folder_episode_match = re.search(r'episode\s+(\d+)', episode_folder.name.lower())
                            if folder_episode_match:
                                folder_episode_num = folder_episode_match.group(1).zfill(2)  # "1" -> "01"
                                folder_episode_code = f"E{folder_episode_num}"  # "E01"
                                episode_match = episode_code == folder_episode_code
                                print_and_log(f"{acq_tag()} [DEBUG] Episode match: {episode_code} == {folder_episode_code} = {episode_match}")
                                
                                if episode_match:
                                    skip_extraction = True
                            else:
                                print_and_log(f"{acq_tag()} [DEBUG] No episode pattern found in '{episode_folder.name}'")
                        
                        if skip_extraction:
                            print_and_log(f"{acq_tag()} {Fore.GREEN}Skipping {episode_folder.name} - P-numbered subtitles already extracted from this episode folder{Style.RESET_ALL}")
                            continue
                    elif any_existing_p_files:
                        print_and_log(f"{acq_tag()} [DEBUG] Found {len(any_existing_p_files)} P-files from {sxxexx_from_episode} (other languages), checking if from same episode folder...")
                        
                        # Check if any P-file from this episode came from the same SUBTITLES folder and episode folder
                        season_match = season_code in subtitle_item.name
                        if season_match:
                            folder_episode_match = re.search(r'episode\s+(\d+)', episode_folder.name.lower())
                            if folder_episode_match:
                                folder_episode_num = folder_episode_match.group(1).zfill(2)
                                folder_episode_code = f"E{folder_episode_num}"
                                episode_match = episode_code == folder_episode_code
                                
                                if episode_match:
                                    print_and_log(f"{acq_tag()} {Fore.GREEN}Skipping {episode_folder.name} - episode already processed (P-files from other languages exist){Style.RESET_ALL}")
                                    continue
                    
                    # Check if extracted subtitles already exist for this episode
                    # Include both active P-files and DRIFT-marked P-files
                    active_pattern = f"*.{lang.lower()}.number*.{episode_sxxexx}.srt"
                    drift_pattern = f"*.{lang.lower()}.number*.{episode_sxxexx}.DRIFT.srt"
                    
                    existing_extracted = list(video_folder.glob(active_pattern))
                    existing_drift = list(video_folder.glob(drift_pattern))
                    total_existing = existing_extracted + existing_drift
                    
                    print_and_log(f"{acq_tag()} [DEBUG-EXTRACTED] Checking active pattern: {active_pattern}")
                    print_and_log(f"{acq_tag()} [DEBUG-EXTRACTED] Found {len(existing_extracted)} active extracted files")
                    print_and_log(f"{acq_tag()} [DEBUG-EXTRACTED] Checking drift pattern: {drift_pattern}")
                    print_and_log(f"{acq_tag()} [DEBUG-EXTRACTED] Found {len(existing_drift)} drift extracted files")
                    print_and_log(f"{acq_tag()} [DEBUG-EXTRACTED] Total existing: {len(total_existing)} files")
                    
                    if total_existing:
                        print_and_log(f"{acq_tag()} {Fore.GREEN}Skipping {episode_folder.name} - extracted subtitles already exist ({len(total_existing)} files: {len(existing_extracted)} active + {len(existing_drift)} drift){Style.RESET_ALL}")
                        continue
                    
                    # Copy subtitle files from episode folder to video folder, already in the final
                    # sync-ready P-numbered format (so no Phase 2 filename re-parsing is needed).
                    # Only files whose own filename resolves to THIS folder's declared language are
                    # kept as-is; other configured languages are not relevant to a SUBTITLES.Sxx.LANG
                    # folder. Files whose language can't be detected fall back to the folder's language.
                    subtitle_files = list(episode_folder.glob('*.srt'))
                    copied_count = 0
                    next_number = _get_next_p_number(video_folder, lang, episode_sxxexx)
                    for srt_file in subtitle_files:
                        # The SUBTITLES.Sxx.LANG folder name is an explicit, deliberate language
                        # declaration - trust it over per-filename detection, since leftover release
                        # naming noise (e.g. "ITA ENG SUB" from the original torrent name) can cause
                        # false-positive detections that don't reflect the subtitle's actual language.
                        detected_lang = detect_language_from_filename(srt_file.name)
                        dest_lang = lang
                        if detected_lang and detected_lang.upper() != lang.upper():
                            print_and_log(f"{acq_tag()} {Fore.YELLOW}'{srt_file.name}' looks like {detected_lang.upper()} based on its filename, but treating it as '{dest_lang.upper()}' (the SUBTITLES.{folder_season} folder's declared language){Style.RESET_ALL}")
                        elif not detected_lang:
                            print_and_log(f"{acq_tag()} {Fore.YELLOW}Could not detect language of '{srt_file.name}' from its filename - assuming '{dest_lang.upper()}' (the SUBTITLES.{folder_season} folder's language){Style.RESET_ALL}")

                        dest_name = f"P{next_number * 100}.{dest_lang.lower()}.number{next_number}.{episode_sxxexx}.srt"
                        dest_path = video_folder / dest_name
                        shutil.copy2(srt_file, dest_path)
                        total_extracted += 1
                        copied_count += 1
                        next_number += 1
                    
                    if copied_count:
                        print_and_log(f"{acq_tag()} {Fore.GREEN}Extracted {copied_count} subtitles from {episode_folder.name} for {matching_video.name}{Style.RESET_ALL}")

                else:
                    # --- No language specified (SUBTITLES.Sxx) - search all configured languages ---
                    target_languages = list(LANGUAGES)

                    # Skip the whole episode only if EVERY configured language is already covered
                    # by a synchronized subtitle or a previously extracted P-numbered/DRIFT file.
                    all_languages_covered = True
                    for check_lang in target_languages:
                        synced_subtitle_path = video_folder / f"{matching_video.stem}.{check_lang.lower()}.srt"
                        if synced_subtitle_path.exists():
                            continue
                        active_pattern = f"*.{check_lang.lower()}.number*.{episode_sxxexx}.srt"
                        drift_pattern = f"*.{check_lang.lower()}.number*.{episode_sxxexx}.DRIFT.srt"
                        if list(video_folder.glob(active_pattern)) or list(video_folder.glob(drift_pattern)):
                            continue
                        all_languages_covered = False
                        break

                    if all_languages_covered:
                        print_and_log(f"{acq_tag()} {Fore.GREEN}Skipping {episode_folder.name} - subtitles already present for all configured languages{Style.RESET_ALL}")
                        continue

                    # Detect each file's language from its filename. Files whose language can't be
                    # detected are never skipped: guess the language (majority vote among the sibling
                    # files whose language WAS detected, else the first configured language) and log
                    # the assumption to both the terminal and the logfile.
                    subtitle_files = list(episode_folder.glob('*.srt'))
                    configured_languages_upper = [l.upper() for l in LANGUAGES]

                    detected_by_file = {srt_file: detect_language_from_filename(srt_file.name) for srt_file in subtitle_files}
                    detected_counts = {}
                    for detected in detected_by_file.values():
                        if detected:
                            detected_counts[detected.upper()] = detected_counts.get(detected.upper(), 0) + 1
                    majority_lang = max(detected_counts, key=detected_counts.get) if detected_counts else None

                    copied_count = 0
                    next_number_by_lang = {}
                    for srt_file in subtitle_files:
                        detected_lang = detected_by_file[srt_file]
                        if detected_lang:
                            if detected_lang.upper() not in configured_languages_upper:
                                continue  # Not a configured language, skip it
                            dest_lang = detected_lang.lower()
                        else:
                            guessed_lang = majority_lang or configured_languages_upper[0]
                            source_desc = "majority of sibling subtitles in this folder" if majority_lang else "first configured language"
                            print_and_log(f"{acq_tag()} {Fore.YELLOW}Could not detect language of '{srt_file.name}' from its filename or content - assuming '{guessed_lang}' ({source_desc}){Style.RESET_ALL}")
                            dest_lang = guessed_lang.lower()

                        # Copy to video folder already in the final sync-ready P-numbered format
                        if dest_lang not in next_number_by_lang:
                            next_number_by_lang[dest_lang] = _get_next_p_number(video_folder, dest_lang, episode_sxxexx)
                        number = next_number_by_lang[dest_lang]
                        dest_name = f"P{number * 100}.{dest_lang}.number{number}.{episode_sxxexx}.srt"
                        dest_path = video_folder / dest_name
                        shutil.copy2(srt_file, dest_path)
                        total_extracted += 1
                        copied_count += 1
                        next_number_by_lang[dest_lang] = number + 1

                    if copied_count:
                        print_and_log(f"{acq_tag()} {Fore.GREEN}Extracted {copied_count} subtitles from {episode_folder.name} for {matching_video.name}{Style.RESET_ALL}")
        
        finally:
            # Clean up temp directory if we created one
            if temp_extract_dir and temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir)
    
    if total_extracted > 0:
        print_and_log(f"{acq_tag()} {Fore.GREEN}Successfully extracted {total_extracted} subtitle files from pre-downloaded folders{Style.RESET_ALL}")
        
        # Phase 2: Match and rename extracted subtitles to proper format
        rename_extracted_subtitles_to_sync_format(video_folder, video_files)
    else:
        print_and_log(f"{acq_tag()} {Fore.YELLOW}No subtitles needed to be extracted (all episodes already have synchronized subtitles){Style.RESET_ALL}")

def rename_extracted_subtitles_to_sync_format(video_folder: Path, video_files: list):
    """
    Phase 2: Rename extracted subtitles to proper synchronisation format.
    Matches subtitles to video files based on SxxExx codes and renames them.
    """
    def has_sxxexx_pattern(filename):
        """Check if filename has proper SxxExx pattern."""
        sxxexx_patterns = [
            r'[Ss](\d{1,2})[Ee](\d{1,3})',  # S1E01, S01E001, s1e1, etc.
            r'(\d{1,2})[xX](\d{1,3})',       # 1x01, 01x001, etc.
        ]
        for pattern in sxxexx_patterns:
            if re.search(pattern, filename):
                return True
        return False
    
    def normalize_sxxexx(filename):
        """Extract and normalize SxxExx pattern to S00E00 format."""
        # Try S pattern first
        match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,3})', filename)
        if match:
            season = int(match.group(1))
            episode = int(match.group(2))
            return f"S{season:02d}E{episode:02d}"
        
        # Try x pattern
        match = re.search(r'(\d{1,2})[xX](\d{1,3})', filename)
        if match:
            season = int(match.group(1))
            episode = int(match.group(2))
            return f"S{season:02d}E{episode:02d}"
        
        return None
    
    print_and_log(f"{acq_tag()} {Fore.CYAN}Phase 2: Matching and renaming extracted subtitles...{Style.RESET_ALL}")
    
    # Find all extracted subtitle files (non-synchronized ones)  
    subtitle_files = []
    for srt_file in video_folder.glob('*.srt'):
        # Language-prefixed files (EN_/NL_/etc.) are always from pre-downloaded folders — process first
        if srt_file.name.startswith(('EN_', 'NL_', 'FR_', 'DE_', 'ES_')):
            subtitle_files.append(srt_file)
            continue
        # Skip already synchronized subtitles (video_name.lang.srt format)
        if re.match(r'^.+\.[a-z]{2}\.srt$', srt_file.name, re.IGNORECASE):
            continue
        # Skip already numbered subtitles (avoid double processing)
        if re.match(r'^P?\d+\.[a-z]{2}\.number\d+\.S\d{2}E\d{2}\.srt$', srt_file.name, re.IGNORECASE):
            continue
        # Process files that have SxxExx patterns
        if has_sxxexx_pattern(srt_file.name):
            subtitle_files.append(srt_file)

    if not subtitle_files:
        print_and_log(f"{acq_tag()} {Fore.YELLOW}No extracted subtitles found to rename{Style.RESET_ALL}")
        return

    # Group subtitles by SxxExx episode code AND extract language from filename
    subtitle_groups = {}
    for srt_file in subtitle_files:
        # Extract language from filename prefix (e.g., EN_The.Witcher.S01E01.srt)
        target_language = None
        filename = srt_file.name
        
        if filename.startswith(('EN_', 'NL_', 'FR_', 'DE_', 'ES_')):
            target_language = filename[:2].lower()  # EN_ -> en
            # Remove language prefix for episode code extraction
            clean_filename = filename[3:]  # Remove "EN_" prefix
        else:
            # Fallback for files without language prefix
            clean_filename = filename
            target_language = LANGUAGES[0].lower()  # Use first configured language
        
        sxxexx = normalize_sxxexx(clean_filename)
        if sxxexx:
            key = (sxxexx, target_language)
            if key not in subtitle_groups:
                subtitle_groups[key] = []
            subtitle_groups[key].append(srt_file)

    # Match subtitle groups to video files and rename  
    total_renamed = 0
    for (sxxexx, target_language), subtitles in subtitle_groups.items():
        # Find matching video file
        matching_video = None
        for video_file in video_files:
            video_sxxexx = extract_sxxexx_code(video_file.name)
            if video_sxxexx and video_sxxexx == sxxexx:
                matching_video = video_file
                break
        
        if not matching_video:
            print_and_log(f"{acq_tag()} {Fore.YELLOW}No matching video found for subtitles with code {sxxexx}{Style.RESET_ALL}")
            continue
        
        # Check if synchronized subtitle already exists (skip if so)
        synced_subtitle_path = video_folder / f"{matching_video.stem}.{target_language}.srt"
        if synced_subtitle_path.exists():
            print_and_log(f"{acq_tag()} {Fore.GREEN}Skipping {sxxexx} - synchronized subtitle already exists{Style.RESET_ALL}")
            # Clean up extracted subtitles since synchronized version exists
            for srt_file in subtitles:
                srt_file.unlink()
            continue
        
        # Rename subtitles to proper format: P{number}.{lang}.number{x}.{SxxExx}.srt
        for i, srt_file in enumerate(subtitles, 1):
            number = f"P{i * 100}"  # P100, P200, P300, etc.
            new_name = f"{number}.{target_language}.number{i}.{sxxexx}.srt"
            new_path = video_folder / new_name
            
            # Check if target file already exists
            if new_path.exists():
                print_and_log(f"{acq_tag()} {Fore.GREEN}Skipping rename: {new_name} already exists{Style.RESET_ALL}")
                # Remove the source file since target already exists
                srt_file.unlink()
                continue
            
            # Rename the file
            srt_file.rename(new_path)
            total_renamed += 1
            print_and_log(f"{acq_tag()} {Fore.GREEN}Renamed: {srt_file.name} → {new_name}{Style.RESET_ALL}")
    
    if total_renamed > 0:
        print_and_log(f"{acq_tag()} {Fore.GREEN}Successfully renamed {total_renamed} subtitle files to synchronisation format{Style.RESET_ALL}")
    else:
        print_and_log(f"{acq_tag()} {Fore.YELLOW}No subtitle files needed renaming{Style.RESET_ALL}")

def _normalize_season_code(season_str: str) -> str:
    """Normalize a season code like 's1' or 'S01' to 'S01'."""
    match = re.match(r's(\d{1,2})', season_str.strip(), re.IGNORECASE)
    return f"S{int(match.group(1)):02d}" if match else season_str.upper()

def _is_valid_subtitles_folder_name(name: str, expected_season: str, configured_languages: list) -> bool:
    """Check whether a folder/zip/rar name follows the SUBTITLES.Sxx[.LANGUAGE] convention.
    Leaving out the language is valid too - it means 'search all configured languages'."""
    name_lower = name.lower()
    stem = name_lower[:-4] if name_lower.endswith(('.zip', '.rar')) else name_lower
    parts = stem.split('.')
    if len(parts) < 2 or parts[0] != 'subtitles':
        return False
    if _normalize_season_code(parts[1]) != expected_season.upper():
        return False
    if len(parts) == 2:
        return True
    return parts[-1].upper() in configured_languages

def show_subtitle_folder_rename_screen(folder_path: Path, expected_season: str, configured_languages: list) -> bool:
    """
    In-app rename screen for a misnamed subtitle folder. Loops until the folder is
    renamed to a valid SUBTITLES.Sxx.LANGUAGE name, or the user cancels.
    Returns True if renamed, False if cancelled.
    """
    while True:
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"{Style.BRIGHT}{Fore.BLUE}[Subservient]{Style.RESET_ALL} Rename Subtitle Folder\n")
        print_and_log(f"{Fore.WHITE}Current name:{Style.RESET_ALL} {folder_path.name}")
        print_and_log(f"{Fore.WHITE}Location:{Style.RESET_ALL} {folder_path.parent}\n")
        print_and_log(f"{Fore.YELLOW}Required format:{Style.RESET_ALL} SUBTITLES.{expected_season}.LANGUAGE")
        print_and_log(f"{Fore.YELLOW}Examples:{Style.RESET_ALL} SUBTITLES.{expected_season}.{configured_languages[0]}, SUBTITLES.{expected_season}.{configured_languages[1] if len(configured_languages) > 1 else configured_languages[0]}, SUBTITLES.{expected_season} {Style.DIM}(searches all configured languages){Style.RESET_ALL}")
        print_and_log(f"{Fore.YELLOW}Configured languages:{Style.RESET_ALL} {', '.join(configured_languages)}")
        print_and_log(f"{Fore.WHITE}The new name must contain the season ({expected_season}). Leaving out the language (e.g. SUBTITLES.{expected_season}) is also valid and searches all configured languages.{Style.RESET_ALL}\n")

        # An archive file's extension must be preserved: renaming "movie.zip" to just "SUBTITLES.S02.NL"
        # would silently strip the .zip/.rar extension, making Subservient no longer recognize it as an archive.
        original_suffix = folder_path.suffix.lower() if folder_path.is_file() and folder_path.suffix.lower() in ('.zip', '.rar') else ''

        new_name = input(f"{Fore.LIGHTYELLOW_EX}Enter the new folder name (or leave empty to cancel):{Style.RESET_ALL} ").strip()
        if not new_name:
            return False

        if not _is_valid_subtitles_folder_name(new_name, expected_season, configured_languages):
            print_and_log(f"\n{Fore.RED}Invalid name: it must be 'SUBTITLES.{expected_season}' or 'SUBTITLES.{expected_season}.LANGUAGE' with LANGUAGE one of: {', '.join(configured_languages)}{Style.RESET_ALL}")
            input(f"\n{Fore.YELLOW}Press Enter to try again...{Style.RESET_ALL} ")
            continue

        final_name = new_name
        if original_suffix and not final_name.lower().endswith(('.zip', '.rar')):
            final_name += original_suffix
            print_and_log(f"\n{Fore.CYAN}Keeping the '{original_suffix}' extension: '{final_name}'{Style.RESET_ALL}")

        target_path = folder_path.parent / final_name
        if target_path.exists():
            print_and_log(f"\n{Fore.RED}A file or folder named '{final_name}' already exists here.{Style.RESET_ALL}")
            input(f"\n{Fore.YELLOW}Press Enter to try again...{Style.RESET_ALL} ")
            continue

        try:
            folder_path.rename(target_path)
            print_and_log(f"{acq_tag()} {Fore.GREEN}Renamed '{folder_path.name}' to '{final_name}'.{Style.RESET_ALL}")
            return True
        except Exception as e:
            print_and_log(f"\n{Fore.RED}Failed to rename folder: {e}{Style.RESET_ALL}")
            input(f"\n{Fore.YELLOW}Press Enter to try again...{Style.RESET_ALL} ")

def confirm_delete_subtitle_folder(folder_path: Path) -> bool:
    """Confirm and delete a folder/zip that isn't a subtitle folder, then ask whether to continue the run."""
    clear_and_print_ascii(BANNER_LINE)
    print_and_log(f"{Style.BRIGHT}{Fore.BLUE}[Subservient]{Style.RESET_ALL} Delete Folder\n")
    print_and_log(f"{Fore.WHITE}You are about to permanently delete:{Style.RESET_ALL}")
    print_and_log(f"  {folder_path}\n")
    print_and_log(f"  {Fore.GREEN}1{Style.RESET_ALL} = Yes, delete this folder")
    print_and_log(f"  {Fore.RED}2{Style.RESET_ALL} = No, go back\n")
    choice = input(f"{Fore.LIGHTYELLOW_EX}Make a choice:{Style.RESET_ALL} ").strip()
    if choice != "1":
        return False

    try:
        if folder_path.is_dir():
            shutil.rmtree(folder_path)
        else:
            folder_path.unlink()
        print_and_log(f"{acq_tag()} {Fore.GREEN}Deleted: {folder_path.name}{Style.RESET_ALL}")
    except Exception as e:
        print_and_log(f"{Fore.RED}Failed to delete '{folder_path.name}': {e}{Style.RESET_ALL}")
        input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")
        return False

    print_and_log("")
    print_and_log(f"{Fore.WHITE}Do you want Subservient to continue this run?{Style.RESET_ALL}\n")
    print_and_log(f"  {Fore.GREEN}1{Style.RESET_ALL} = Yes, continue")
    print_and_log(f"  {Fore.RED}2{Style.RESET_ALL} = No, exit Subservient\n")
    cont_choice = input(f"{Fore.LIGHTYELLOW_EX}Make a choice:{Style.RESET_ALL} ").strip()
    if cont_choice != "1":
        exit_with_prompt("Press Enter to exit...")
    return True

def handle_unrecognized_subtitle_folder(folder_path: Path, expected_season: str, configured_languages: list, problem_lines: list = None) -> str:
    """
    Interactive resolution menu for a folder that looks like it might be a subtitle
    folder but doesn't follow the SUBTITLES.Sxx[.LANGUAGE] naming convention (unrecognized
    name, wrong season code, or an unsupported language).
    Returns 'renamed', 'deleted' or 'exit'.
    """
    if problem_lines is None:
        problem_lines = [
            "Folder found that might be a subtitle folder but doesn't follow naming convention:",
            "",
            f"{Fore.RED}Unrecognized folder:{Style.RESET_ALL}",
            f"  - {folder_path.name} (in {folder_path.parent})",
        ]
    while True:
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"{Fore.RED}{Style.BRIGHT}[ERROR] Subtitle Folder Configuration Error!{Style.RESET_ALL}\n")
        for line in problem_lines:
            print_and_log(line)
        print_and_log("")
        print_and_log(f"{Fore.YELLOW}Required format:{Style.RESET_ALL} SUBTITLES.{expected_season}.LANGUAGE {Fore.WHITE}(or SUBTITLES.{expected_season} to search all configured languages){Style.RESET_ALL}")
        print_and_log(f"{Fore.YELLOW}Examples:{Style.RESET_ALL} SUBTITLES.{expected_season}.{configured_languages[0]}, SUBTITLES.{expected_season}.{configured_languages[1] if len(configured_languages) > 1 else configured_languages[0]}, SUBTITLES.{expected_season} {Style.DIM}(searches all configured languages){Style.RESET_ALL}\n")

        print_and_log(f"{Fore.WHITE}What would you like to do?{Style.RESET_ALL}\n")
        print_and_log(f"  {Fore.GREEN}1{Style.RESET_ALL} = Rename the folder {Style.DIM}(rename it here, then continue automatically){Style.RESET_ALL}")
        print_and_log(f"  {Fore.GREEN}2{Style.RESET_ALL} = Delete the folder {Style.DIM}(it's not a subtitle folder){Style.RESET_ALL}")
        print_and_log(f"  {Fore.RED}3{Style.RESET_ALL} = Exit Subservient {Style.DIM}(fix it yourself, then run again){Style.RESET_ALL}\n")

        choice = input(f"{Fore.LIGHTYELLOW_EX}Make a choice:{Style.RESET_ALL} ").strip()

        if choice == "1":
            if show_subtitle_folder_rename_screen(folder_path, expected_season, configured_languages):
                return 'renamed'
        elif choice == "2":
            if confirm_delete_subtitle_folder(folder_path):
                return 'deleted'
        elif choice == "3":
            exit_with_prompt("Press Enter to exit...")
            return 'exit'
        else:
            print_and_log(f"{Fore.RED}Invalid choice. Please select 1, 2, or 3.{Style.RESET_ALL}")
            time.sleep(1)

def validate_subtitle_folders_in_directory(video_folder: Path, video_files: list):
    """
    Validate all SUBTITLES folders in directory ONCE before processing episodes.
    Check for wrong season codes, missing language specifications, etc.
    """
    # Get season code from first video file
    first_video = video_files[0] if video_files else None
    if not first_video or not has_strict_series_naming_pattern(first_video.name):
        return  # Not a series or no video files
        
    sxxexx_code = extract_sxxexx_code(first_video.name)
    if not sxxexx_code:
        return
        
    expected_season = sxxexx_code[:3]  # "S01E01" -> "S01"
    
    print_and_log(f"{acq_tag()} {Fore.CYAN}Checking subtitle folder configuration...{Style.RESET_ALL}")
    
    # Get skip_dirs for checking against unrecognized folders
    from utils import get_skip_dirs_from_config
    skip_dirs = get_skip_dirs_from_config()
    
    # Find all SUBTITLES folders
    subtitle_folders = []
    wrong_season_folders = []
    wrong_language_folders = []
    unrecognized_folders = []
    packed_archives = []

    # Archive extensions that indicate an unpacked subtitle folder. .zip and .rar are handled
    # natively (see extract_subtitles_from_predownloaded_folders) and are excluded here.
    PACKED_EXTENSIONS = {'.7z', '.tar', '.gz', '.bz2', '.xz', '.tar.gz', '.tar.bz2', '.tar.xz', '.tgz', '.tbz2', '.cab', '.iso', '.ace', '.arj', '.lzh', '.lha', '.zst', '.tar.zst'}

    # Get configured languages (convert to uppercase for comparison)
    configured_languages = [lang.upper() for lang in LANGUAGES]
    
    for item in video_folder.iterdir():
        item_name_lower = item.name.lower()

        # Check for packed archives that look like subtitle folders (before other checks)
        if item.is_file():
            # Build the full lowercased name and check for any packed extension
            _is_packed = False
            for _ext in PACKED_EXTENSIONS:
                if item_name_lower.endswith(_ext):
                    _is_packed = True
                    break
            if _is_packed:
                packed_archives.append(item.name)
                continue

        if (item.is_dir() or item_name_lower.endswith(('.zip', '.rar'))):
            if item_name_lower.startswith('subtitles.s'):
                # Extract season from folder name using regex (accepts 1 or 2 digits, e.g. S1 or S01)
                # Handle "subtitles.s01", "subtitles.s1.en", "subtitles.s01.zip" and "subtitles.s01.rar" formats
                season_match = re.search(r'subtitles\.(s\d{1,2})(\.|$)', item_name_lower)
                if season_match:
                    folder_season_raw = season_match.group(1)  # e.g. "s1" or "s01", as written
                    folder_season = _normalize_season_code(folder_season_raw)
                    
                    if folder_season != expected_season:
                        # Wrong season detected
                        wrong_season_folders.append((item.name, folder_season))
                    else:
                        # Correct season - a missing language (e.g. SUBTITLES.S01) is valid too and
                        # means "search all configured languages"; otherwise the language must be configured.
                        if item.is_dir():
                            if item_name_lower == f"subtitles.{folder_season_raw}":
                                subtitle_folders.append(item.name)
                            elif item_name_lower.startswith(f"subtitles.{folder_season_raw}."):
                                # Extract language and check if it's configured
                                folder_lang = item.name.split('.')[-1].upper()
                                if folder_lang not in configured_languages:
                                    wrong_language_folders.append((item.name, folder_lang))
                                else:
                                    subtitle_folders.append(item.name)
                        elif item.is_file() and item_name_lower.endswith(('.zip', '.rar')):
                            # For ZIP/RAR files, check the name before the archive extension
                            zip_name_without_ext = item_name_lower[:-4]  # Remove .zip or .rar (both 4 chars)
                            if zip_name_without_ext == f"subtitles.{folder_season_raw}":
                                subtitle_folders.append(item.name)
                            elif zip_name_without_ext.startswith(f"subtitles.{folder_season_raw}."):
                                # Extract language and check if it's configured
                                folder_lang = item.name.split('.')[-2].upper()  # SUBTITLES.S01.DE.zip -> DE
                                if folder_lang not in configured_languages:
                                    wrong_language_folders.append((item.name, folder_lang))
                                else:
                                    subtitle_folders.append(item.name)
                else:
                    # Debug: log unmatched subtitles folders
                    print_and_log(f"{acq_tag()} {Fore.YELLOW}DEBUG: Could not extract season from folder: {item.name}{Style.RESET_ALL}")
            elif item.is_dir() and item.name.lower() not in skip_dirs:
                # Any folder not in skip_dirs is considered a potential subtitle folder with wrong naming
                unrecognized_folders.append(item.name)
            elif item.is_file() and item_name_lower.endswith(('.zip', '.rar')) and not item_name_lower.startswith('subtitles.s'):
                # Any ZIP/RAR file that doesn't follow SUBTITLES.S##.* format is also unrecognized
                unrecognized_folders.append(item.name)
    
    # Show errors if any problems found
    if packed_archives or wrong_season_folders or wrong_language_folders or unrecognized_folders:
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"{Fore.RED}{Style.BRIGHT}[ERROR] Subtitle Folder Configuration Error!{Style.RESET_ALL}")
        print_and_log("")

        if packed_archives:
            print_and_log(f"Archive file(s) found that appear to be subtitle folders, but have not been extracted yet:")
            print_and_log("")
            print_and_log(f"{Fore.RED}Packed/compressed archives:{Style.RESET_ALL}")
            for archive_name in packed_archives:
                print_and_log(f"  - {archive_name} (in {video_folder})")
            print_and_log("")
            print_and_log(f"{Fore.YELLOW}These files need to be extracted before Subservient can use them.{Style.RESET_ALL}")
            print_and_log(f"{Fore.YELLOW}After extracting, rename the resulting folder to match the required format:{Style.RESET_ALL}")
            print_and_log(f"{Fore.YELLOW}Required format:{Style.RESET_ALL} SUBTITLES.{expected_season}.LANGUAGE")
            print_and_log(f"{Fore.YELLOW}Examples:{Style.RESET_ALL} SUBTITLES.{expected_season}.EN, SUBTITLES.{expected_season}.NL")
            print_and_log("")
            print_and_log(f"{Fore.YELLOW}If this is not a subtitle archive, remove it from the folder or add it to skip_dirs in .config.{Style.RESET_ALL}")
            print_and_log("")
        
        if unrecognized_folders:
            print_and_log(f"Folder(s) found that might be subtitle folders but don't follow naming convention:")
            print_and_log("")
            print_and_log(f"{Fore.RED}Unrecognized folders:{Style.RESET_ALL}")
            for folder_name in unrecognized_folders:
                print_and_log(f"  - {folder_name} (in {video_folder})")
            print_and_log("")
            print_and_log(f"{Fore.YELLOW}Required format:{Style.RESET_ALL} SUBTITLES.{expected_season}.LANGUAGE")
            print_and_log(f"{Fore.YELLOW}Examples:{Style.RESET_ALL} SUBTITLES.{expected_season}.EN, SUBTITLES.{expected_season}.NL")
            print_and_log("")
        
        if wrong_season_folders:
            print_and_log(f"Subtitle folder(s) found with wrong season code:")
            print_and_log("")
            print_and_log(f"{Fore.RED}Wrong season folders:{Style.RESET_ALL}")
            for folder_name, folder_season in wrong_season_folders:
                print_and_log(f"  - {folder_name} (Found: {folder_season}, Expected: {expected_season}) (in {video_folder})")
            print_and_log("")
            print_and_log(f"{Fore.YELLOW}Expected season:{Style.RESET_ALL} {expected_season}")
            print_and_log(f"{Fore.YELLOW}Video files contain:{Style.RESET_ALL} {expected_season}E01, {expected_season}E02, etc.")
            print_and_log("")
        
        if wrong_language_folders:
            print_and_log(f"Subtitle folder(s) found with unsupported language:")
            print_and_log("")
            print_and_log(f"{Fore.RED}Wrong language folders:{Style.RESET_ALL}")
            for folder_name, folder_lang in wrong_language_folders:
                print_and_log(f"  - {folder_name} (Found: {folder_lang}, not in configured languages) (in {video_folder})")
            print_and_log("")
            print_and_log(f"{Fore.YELLOW}Configured languages:{Style.RESET_ALL} {', '.join(configured_languages)}")
            print_and_log(f"{Fore.YELLOW}Examples:{Style.RESET_ALL} SUBTITLES.{expected_season}.{configured_languages[0]}, SUBTITLES.{expected_season}.{configured_languages[1] if len(configured_languages) > 1 else configured_languages[0]}")
            print_and_log("")
        
        # Folders that only fail because they don't follow the naming convention (unrecognized name,
        # wrong season, or an unsupported language) get an interactive rename/delete/exit menu instead
        # of a hard exit. A folder without a language (already merged into subtitle_folders above) is
        # valid on its own and never reaches this point. Packed archives still need manual extraction.
        if not packed_archives and (unrecognized_folders or wrong_season_folders or wrong_language_folders):
            problem_folders = []
            for folder_name in unrecognized_folders:
                problem_folders.append((video_folder / folder_name, [
                    "Folder found that might be a subtitle folder but doesn't follow naming convention:",
                    "",
                    f"{Fore.RED}Unrecognized folder:{Style.RESET_ALL}",
                    f"  - {folder_name} (in {video_folder})",
                ]))
            for folder_name, folder_season in wrong_season_folders:
                problem_folders.append((video_folder / folder_name, [
                    "Subtitle folder found with wrong season code:",
                    "",
                    f"{Fore.RED}Wrong season folder:{Style.RESET_ALL}",
                    f"  - {folder_name} (Found: {folder_season}, Expected: {expected_season}) (in {video_folder})",
                ]))
            for folder_name, folder_lang in wrong_language_folders:
                problem_folders.append((video_folder / folder_name, [
                    "Subtitle folder found with unsupported language:",
                    "",
                    f"{Fore.RED}Wrong language folder:{Style.RESET_ALL}",
                    f"  - {folder_name} (Found: {folder_lang}, not in configured languages) (in {video_folder})",
                ]))

            for folder_path, problem_lines in problem_folders:
                if not folder_path.exists():
                    continue  # Already resolved above (e.g. renamed away)
                action = handle_unrecognized_subtitle_folder(folder_path, expected_season, configured_languages, problem_lines)
                if action == 'exit':
                    return  # exit_with_prompt() already terminated the process
            # Re-scan now that the problem folder(s) were renamed or deleted
            validate_subtitle_folders_in_directory(video_folder, video_files)
            return

        print_and_log(f"{Fore.YELLOW}Possible solutions:{Style.RESET_ALL}")
        print_and_log(f"  1. Create subtitle folders with proper naming: SUBTITLES.{expected_season}.LANGUAGE") 
        print_and_log(f"  2. Add folder name to skip_dirs in config if it's not a subtitle folder")
        print_and_log(f"  3. Remove the subtitle folders if not needed")
        print_and_log("")
        print_and_log(f"{Fore.RED}Subservient in TV-Series mode cannot proceed with improper folder configuration.{Style.RESET_ALL}")
        
        exit_with_prompt("Press Enter to exit...")
    if subtitle_folders:
        print_and_log(f"{acq_tag()} {Fore.GREEN}Subtitle folder configuration is valid{Style.RESET_ALL}")
        
        # Log found subtitle languages
        languages = []
        for folder in subtitle_folders:
            stem = folder[:-4] if folder.lower().endswith(('.zip', '.rar')) else folder
            parts = stem.split('.')
            if len(parts) >= 3:
                languages.append(parts[-1].upper())
            else:
                languages.append(f"ALL configured ({', '.join(configured_languages)})")
        
        print_and_log(f"{acq_tag()} {Fore.CYAN}Found subtitle folders for: {', '.join(languages)}{Style.RESET_ALL}")
        
        # Extract subtitles from pre-downloaded folders for episodes that need them
        extract_subtitles_from_predownloaded_folders(video_folder, video_files)
    else:
        print_and_log(f"{acq_tag()} {Fore.CYAN}No subtitle folders found - normal download mode{Style.RESET_ALL}")

def process_folder(folder: Path, scanned_folders: set, jwt_token: str, skipped_movies: set, idx_offset=0, total_videos=None, video_idx_start=1):
    global quota_exceeded
    video_files = get_video_files_for_folder(folder)
    processed = 0
    if not video_files:
        return processed
   
    # Log folder being processed (only to log file, not terminal)
    with LOG_FILE.open('a', encoding='utf-8') as f:
        f.write(f"\n=== Processing folder: {folder.name} ===\n")
    
    # Check for subtitle folders ONCE per folder (series mode only)
    if SERIES_MODE:
        validate_subtitle_folders_in_directory(folder, video_files)
   
    for i, video_file in enumerate(video_files, 1):
        all_languages_skipped = all(is_movie_language_skipped(video_file, lang) for lang in LANGUAGES)
        if all_languages_skipped:
            print_and_log(f"{acq_tag()} {Fore.MAGENTA}*{Style.RESET_ALL} Skipping {video_file.name} (all languages marked as 'do not show again').")
            continue
        
        # Always show video header with screen refresh
        clear_and_print_ascii(BANNER_LINE)
        if total_videos is not None:
            print_video_header(video_file.stem, idx_offset + i, total_videos)
        else:
            # Single video mode - show [1/1]
            print_video_header(video_file.stem, 1, 1)
            
        # Use the proper check_existing_subtitles function that handles both standard and series naming
        # Check without verbose logging (detailed check will happen in search_subtitles)
        lang_status = check_existing_subtitles_silent(video_file)
        
        if all(lang_status.values()):
            print_and_log(f"{acq_tag()} * All subtitles present or in sync. Skipping {video_file.name}.")
            continue
        scanned_folders.add(folder)
        print_and_log(f"{acq_tag()} -> Video found: {video_file.name}")
        search_subtitles(video_file, jwt_token)
        print_and_log(f"---\n")
        processed += 1

        # Check if quota was hit during this video's downloads
        if quota_exceeded:
            while show_quota_exceeded_screen():
                # User chose Retry — reset flag and re-process this video
                quota_exceeded = False
                search_subtitles(video_file, jwt_token)
                if not quota_exceeded:
                    break  # Download succeeded, continue with remaining videos
            if quota_exceeded:
                return processed  # User exited via the screen

    return processed

def ensure_initial_setup():
    config_dir = Path(user_config_dir()) / "Subservient"
    pathfile = config_dir / "Subservient_pathfiles"
    required_keys = [
        "subservient_anchor",
        "subordinate_path",
        "extraction_path",
        "acquisition_path",
        "synchronisation_path"
    ]
    if not pathfile.exists():
        print_and_log(f"{Fore.RED}{Style.BRIGHT}[ERROR]{Style.RESET_ALL} Initial setup not complete.\n\n"
              f"{Fore.YELLOW}To get started with Subservient, please do the following:{Style.RESET_ALL}\n"
              f"{Fore.CYAN}1.{Style.RESET_ALL} Make sure that subordinate.py is located in the main folder, next to extraction.py, acquisition.py and synchronisation.py\n"
              f"{Fore.CYAN}2.{Style.RESET_ALL} Run subordinate.py. This will perform the internal setup and register all necessary script paths.\n"
              f"{Fore.CYAN}3.{Style.RESET_ALL} After setup, you can move subordinate.py to the movie(s) you want to process and run it again.\n\n"
              f"{Fore.YELLOW}If you need help, see the README file for more details.{Style.RESET_ALL}\n")
        exit_with_prompt("Press Enter to exit...")
    lines = pathfile.read_text(encoding="utf-8").splitlines()
    keys = {l.split('=')[0] for l in lines if '=' in l}
    if not all(k in keys for k in required_keys):
        print_and_log(f"{Fore.RED}{Style.BRIGHT}[ERROR]{Style.RESET_ALL} Initial setup incomplete.\n\n"
              f"{Fore.YELLOW}To get started with Subservient, please do the following:{Style.RESET_ALL}\n"
              f"{Fore.CYAN}1.{Style.RESET_ALL} Make sure that subordinate.py is located in the main folder, next to extraction.py, acquisition.py and synchronisation.py\n"
              f"{Fore.CYAN}2.{Style.RESET_ALL} Run subordinate.py. This will perform the internal setup and register all necessary script paths.\n"
              f"{Fore.CYAN}3.{Style.RESET_ALL} After setup, you can move subordinate.py to the movie(s) you want to process and run it again.\n\n"
              f"{Fore.YELLOW}If you need help, see the README file for more details.{Style.RESET_ALL}\n")
        exit_with_prompt("Press Enter to exit...")
ensure_initial_setup()

def get_next_sub_index(folder: Path, lang: str, mkv_path: Path = None) -> int:
    # For series mode, only look at episode-specific files
    if SERIES_MODE and mkv_path:
        sxxexx_code = extract_sxxexx_code(mkv_path.name)
        if sxxexx_code:
            # Count ALL files for this specific episode: normal, DRIFT, and FAILED
            indices = []
            has_any_p_prefix = False
            
            # Pattern for all episode-specific files
            all_files = list(folder.glob(f"*.{lang}.number*.{sxxexx_code}.srt")) + \
                       list(folder.glob(f"*.{lang}.number*.{sxxexx_code}.DRIFT.srt")) + \
                       list(folder.glob(f"*.{lang}.number*.{sxxexx_code}.FAILED.srt"))
            
            for f in all_files:
                # Extract number from any of these patterns:
                # P{id}.{lang}.number{X}.{sxxexx_code}.srt
                # {id}.{lang}.number{X}.{sxxexx_code}.srt
                # P{id}.{lang}.number{X}.{sxxexx_code}.DRIFT.srt  
                # {id}.{lang}.number{X}.{sxxexx_code}.FAILED.srt
                m = re.search(rf"\.{re.escape(lang)}\.number(\d+)\.{re.escape(sxxexx_code)}\.(srt|DRIFT\.srt|FAILED\.srt)$", f.name)
                if m:
                    # Check if ANY P-prefix file exists (active or DRIFT/FAILED)
                    if f.name.startswith('P'):
                        has_any_p_prefix = True
                        # Don't add P-prefixed numbers to normal counting
                        continue
                    indices.append(int(m.group(1)))
            
            # P-prefix amendment: If ANY P-prefix file exists, start downloads at 1
            # This ensures we get best quality downloads when P-files are present/removed
            if has_any_p_prefix:
                return 1
                    
            next_index = max(indices, default=0) + 1
            return next_index
    
    # Original movie logic - count all files in folder (including DRIFT/FAILED)
    # P-prefix amendment also applies to movie mode
    pattern_files = list(folder.glob(f"*.{lang}.number*.srt")) + \
                   list(folder.glob(f"*.{lang}.number*.DRIFT.srt")) + \
                   list(folder.glob(f"*.{lang}.number*.FAILED.srt"))
    
    indices = []
    has_any_p_prefix = False
    for f in pattern_files:
        # Check if ANY P-prefix file exists (active or DRIFT/FAILED)
        if f.name.startswith('P'):
            has_any_p_prefix = True
            continue
        m = re.search(rf"\.{lang}\.number(\d+)", f.name)
        if m:
            indices.append(int(m.group(1)))
    
    # P-prefix amendment: If ANY P-prefix file exists, start downloads at 1
    # This ensures we get best quality downloads when P-files are present/removed
    if has_any_p_prefix:
        return 1
        
    return max(indices, default=0) + 1

def get_total_available_candidates(movie_path: Path, lang: str, jwt_token: str) -> int:
    try:
        raw_title = movie_path.stem
        query = build_search_query(raw_title)
        query = remove_all_short_numbers(query)
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "User-Agent": "NexigenSubtitleBot v1.0",
            "Api-Key": API_KEY
        }
        existing_counts, _ = count_existing_subtitles(movie_path, lang)
        unique_candidates = set()
        
        params = {"query": query, "languages": lang}
        response = requests.get(f"{API_URL}/subtitles", headers=headers, params=params)
        time.sleep(0.5)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("data", [])
            filtered_results = filter_subtitles_by_query(results, query)
            
            for candidate in filtered_results:
                download_count = candidate['attributes'].get('download_count', 0)
                if download_count not in existing_counts:
                    unique_candidates.add(download_count)
            if not filtered_results:
                for candidate in results:
                    download_count = candidate['attributes'].get('download_count', 0)
                    if download_count not in existing_counts:
                        unique_candidates.add(download_count)
                if not results:
                    fallback_query = clean_title(raw_title)
                    params_fallback = {"query": fallback_query, "languages": lang}
                    response_fallback = requests.get(f"{API_URL}/subtitles", headers=headers, params=params_fallback)
                    time.sleep(0.5)
                    if response_fallback.status_code == 200:
                        fallback_data = response_fallback.json()
                        fallback_results = fallback_data.get("data", [])
                        
                        for candidate in fallback_results:
                            download_count = candidate['attributes'].get('download_count', 0)
                            if download_count not in existing_counts:
                                unique_candidates.add(download_count)
        return len(unique_candidates)
    except Exception:
        return 0

def main():
    clear_and_print_ascii(BANNER_LINE)
    print_and_log(f"{acq_tag()} -> Getting JWT token...")
    jwt_token = get_jwt_token()
    if jwt_token:
        print_and_log(f"{acq_tag()} * JWT token: {jwt_token[:32]}...")
        set_token_in_config(jwt_token)
    else:
        print_and_log(f"{acq_tag()} # Failed to get JWT token. Token is None.")
    if not jwt_token:
        exit_with_prompt("JWT token error. Press any key to exit...")
        return
    skipped_movies = get_skipped_movies_from_config()
    current_folder = Path(__file__).resolve().parent
    scanned_folders = set()
    extras_folder_name = setup.get('extras_folder_name', 'extras')
    all_folders = []
    skip_dirs = get_skip_dirs_from_config()
    if extras_folder_name:
        skip_dirs.add(extras_folder_name.lower())
    anchor_videos = get_video_files_for_folder(current_folder)
    if anchor_videos:
        all_folders = [(current_folder, anchor_videos)]
    else:
        for dirpath, dirnames, _ in os.walk(current_folder):
            dirnames[:] = [d for d in dirnames if d.lower() not in skip_dirs]
            folder = Path(dirpath)
            video_files = get_video_files_for_folder(folder)
            if video_files:
                all_folders.append((folder, video_files))
    total_videos = sum(len(v) for _, v in all_folders) or 1
    idx = 1
    for folder, video_files in all_folders:
        processed = process_folder(folder, scanned_folders, jwt_token, skipped_movies, idx_offset=idx-1, total_videos=total_videos)
        idx += len(video_files)
    handle_missing_queries()
    if SERIES_MODE and unknown_sxxexx_files:
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"{Fore.YELLOW}{Style.BRIGHT}WARNING: Some subtitles could not be categorized under a season and episode!{Style.RESET_ALL}\n")
        print_and_log(f"The following subtitle files were named with 'UNKNOWN':\n")
        for f in unknown_sxxexx_files:
            print_and_log(f"   - {f}")
        print_and_log(f"\n{Fore.YELLOW}Before the synchronisation phase can commence, you must manually rename these files.\nUsually you can make a good guess based on the other subtitles that were categorized correctly.{Style.RESET_ALL}\n")
        input_and_log(f"\nPress Enter after you have checked/renamed these files (or to continue)...")
    sync_script_path = SNAPSHOT_DIR / "synchronisation.py"
    if not missing_queries and sync_script_path.exists():
        print_and_log(f"\n{acq_tag()} {Fore.GREEN}*{Style.RESET_ALL} All movies processed. Opening synchronisation.py in {int(PAUSE_SECONDS)} seconds...")
        time.sleep(PAUSE_SECONDS)
        print_and_log(f"\n{acq_tag()} {Fore.GREEN}*{Style.RESET_ALL} Opening synchronisation.py...")
        os.system(f'python "{sync_script_path}"')
        print_and_log(f"{acq_tag()} {Fore.GREEN}*{Style.RESET_ALL} acquisition.py will now close.")
        sys.exit(0)
    elif not sync_script_path.exists():
        print_and_log(f"\n{acq_tag()} {Fore.RED}# {Style.RESET_ALL}synchronisation.py not found in this directory. Please run it manually if needed.")
        exit_with_prompt()

def update_max_search_results_in_config(new_limit):
    if not CONFIG_PATH.exists():
        print_and_log(f"{acq_tag()} {Fore.RED}Config file not found.{Style.RESET_ALL}")
        return False
    
    try:
        lines = CONFIG_PATH.read_text(encoding='utf-8').splitlines()
        updated_lines = []
        updated = False
        
        for line in lines:
            if line.strip().startswith('max_search_results='):
                updated_lines.append(f'max_search_results= {new_limit}')
                updated = True
            else:
                updated_lines.append(line)
        
        if updated:
            CONFIG_PATH.write_text('\n'.join(updated_lines) + '\n', encoding='utf-8')
            print_and_log(f"{acq_tag()} {Fore.GREEN}*{Style.RESET_ALL} Config updated: max_search_results set to {new_limit}")
            return True
        else:
            print_and_log(f"{acq_tag()} {Fore.RED}Could not find max_search_results setting in config.{Style.RESET_ALL}")
            return False
    except Exception as e:
        print_and_log(f"{acq_tag()} {Fore.RED}Error updating config: {e}{Style.RESET_ALL}")
        return False

def reset_failed_to_drift(folder: Path, lang: str):
    failed_files = get_subtitle_files_by_pattern(folder, lang, ".FAILED")
    reset_count = 0
    for failed_file in failed_files:
        drift_file = failed_file.with_name(failed_file.name.replace(".FAILED.srt", ".DRIFT.srt"))
        try:
            failed_file.rename(drift_file)
            reset_count += 1
            print_and_log(f"{acq_tag()} {Fore.CYAN}Reset to DRIFT: {drift_file.name}{Style.RESET_ALL}")
        except Exception as e:
            print_and_log(f"{acq_tag()} {Fore.RED}Failed to reset: {failed_file.name} ({e}){Style.RESET_ALL}")
    
    if reset_count > 0:
        print_and_log(f"{acq_tag()} {Fore.GREEN}*{Style.RESET_ALL} Reset {reset_count} FAILED file(s) back to DRIFT for retry.")
    return reset_count
if __name__ == "__main__":
    main()
