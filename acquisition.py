import os
import sys
import subprocess

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
from utils import ASCII_ART, clear_and_print_ascii, get_skip_dirs_from_config
SNAPSHOT_DIR = Path(__file__).parent.resolve()
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
    'top_downloads',
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
TOP_DOWNLOADS = int(setup['top_downloads'])
DOWNLOAD_RETRY_503 = int(setup.get('download_retry_503', 6))
SERIES_MODE = setup['series_mode']
def acq_tag():
    """Return formatted acquisition tag for console output."""
    return f"{Style.BRIGHT}{Fore.BLUE}[Acquisition]{Style.RESET_ALL}"

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

def exit_with_prompt(message="Press any key to exit..."):
    """Display message and wait for user input before exiting."""
    try:
        input(f"{acq_tag()} {message}")
    except EOFError:
        os.system("pause")
    sys.exit(1)

def get_jwt_token():
    """Obtain JWT token through API authentication."""
    token = get_token_from_config()
    if token:
        return token
    print_and_log(f"{acq_tag()} * No valid JWT token in .config. Logging in...")
    login_url = f"{API_URL}/login"
    login_headers = {
        "Api-Key": API_KEY,
        "Content-Type": "application/json",
        "User-Agent": "NexigenSubtitleBot v0.02"
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
            set_token_in_config(token)
            print_and_log(f"{acq_tag()} * New JWT token saved to .config.")
            return token
    elif response.status_code == 429:
        print_and_log(f"{acq_tag()} 429: Too many requests. Waiting {int(PAUSE_SECONDS)} seconds...")
        time.sleep(PAUSE_SECONDS)
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

def clean_title(raw_title: str) -> str:
    """Clean and normalize video title for subtitle searching."""
    UNWANTED_TERMS = get_unwanted_terms_from_config()
    UNWANTED_CHARS = r"[\[\]\(\)\{\}_\+\.-]"
    WHITELIST = {"a", "i", "z", "o", "u"}
    cleaned = raw_title.replace('.', ' ')
    pattern = r"\\b(" + "|".join(re.escape(term) for term in UNWANTED_TERMS) + r")\\b"
    cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[\[\(\{][^\]\)\}]*[\]\)\}]", "", cleaned)
    cleaned = re.sub(r"\\b(?!(?:19|20)\\d{2})\\d+\\b", "", cleaned)
    cleaned = re.sub(UNWANTED_CHARS, " ", cleaned)
    cleaned = re.sub(r"[^a-zA-Z ]", "", cleaned)
    cleaned = re.sub(r"\\s+", " ", cleaned)
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


def check_existing_subtitles(mkv_path: Path) -> dict:
    """Check which subtitle languages already exist for video file."""
    base = mkv_path.with_suffix('')
    return {
        lang: (srt_file := base.with_name(f"{base.name}.{lang}.srt")).exists() 
              and not get_subtitle_files_by_pattern(mkv_path.parent, lang, ".DRIFT")
        for lang in LANGUAGES
    }
def extract_sxxexx_code(name: str) -> str | None:
    """Extract season/episode code from filename."""
    match = re.search(r"[sS](\d{1,2})[eE](\d{1,2})", name)
    return f"S{int(match.group(1)):02d}E{int(match.group(2)):02d}" if match else None
unknown_sxxexx_files = []
def download_top_subtitles(subs, lang, dest_folder, jwt_token, mkv_path=None, candidate_index=None, force_download=False):
    """Download the top-rated subtitles for specified language and video."""
    global unknown_sxxexx_files
    headers = {
        "Api-Key": API_KEY,
        "User-Agent": "NexigenSubtitleBot v1.0",
        "Authorization": f"Bearer {jwt_token}"
    }
    sxxexx_from_mkv = None
    if SERIES_MODE and mkv_path is not None:
        sxxexx_from_mkv = extract_sxxexx_code(mkv_path.name)
    for i, sub in enumerate(subs[:TOP_DOWNLOADS], 1):
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
                time.sleep(0.5)
                
                if resp is None or resp.status_code >= 400:
                    if resp and resp.status_code == 503:
                        if attempt < max_retries_503:
                            delay = min(5 * attempt, 30)
                            print_and_log_colored(f"{acq_tag()} {Fore.YELLOW}503 Service Unavailable (server overloaded). Retrying in {delay}s... (attempt {attempt}/{max_retries_503}){Style.RESET_ALL}", Fore.YELLOW)
                            time.sleep(delay)
                            continue
                        else:
                            print_and_log_colored(f"{acq_tag()} {Fore.RED}Failed to download after {max_retries_503} attempts (503 Service Unavailable). OpenSubtitles servers are overloaded. Skipping.{Style.RESET_ALL}", Fore.RED)
                            break
                    elif attempt < max_retries_503:
                        print_and_log_colored(f"{acq_tag()} {Fore.YELLOW}HTTP error (status {getattr(resp, 'status_code', 'N/A')}). Retrying in {int(PAUSE_SECONDS)}s... (attempt {attempt}/{max_retries_503}){Style.RESET_ALL}", Fore.YELLOW)
                        time.sleep(PAUSE_SECONDS)
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
                            time.sleep(0.5)
                            
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
                                    print_and_log_colored(f"{acq_tag()} {Fore.YELLOW}SRT HTTP error (status {getattr(srt_resp, 'status_code', 'N/A')}). Retrying in {int(PAUSE_SECONDS)}s... (attempt {srt_attempt}/{max_retries_503}){Style.RESET_ALL}", Fore.YELLOW)
                                    time.sleep(PAUSE_SECONDS)
                                    continue
                                else:
                                    print_and_log_colored(f"{acq_tag()} {Fore.RED}Failed to download SRT after {max_retries_503} attempts (HTTP error). Skipping.{Style.RESET_ALL}", Fore.RED)
                                    break
                            elif srt_resp.status_code == 200:
                                srt_data = srt_resp.content
                                dest_path = dest_folder / file_name
                                with open(dest_path, 'wb') as f:
                                    f.write(srt_data)
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
def filter_subtitles_by_query(subs, query):
    """Filter subtitle results by search query terms."""
    match = re.search(r'(.*?)([\s._-]?)(19|20)\\d{2}', query)
    if match:
        left = match.group(1).strip().split()
        year = match.group(3) + match.group(0)[-2:]
        filter_words = [w.lower() for w in left if w] + [year]
    else:
        filter_words = [w.lower() for w in query.strip().split() if w]
    filtered = []
    for sub in subs:
        file_name = sub['attributes']['files'][0]['file_name'].lower()
        if all(word in file_name for word in filter_words):
            filtered.append(sub)
    return filtered
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
    for f in get_subtitle_files_by_pattern(movie_path.parent, lang):
        if f.name.endswith('.DRIFT.srt') or f.name.endswith('.FAILED.srt'):
            continue
        m = re.match(r"^(\d+)\." + re.escape(lang) + r"\.number\d+\.srt$", f.name)
        if m:
            existing_counts.add(int(m.group(1)))
    
    for f in get_subtitle_files_by_pattern(movie_path.parent, lang, ".DRIFT"):
        m = re.match(r"^(\d+)\." + re.escape(lang) + r"\.number\d+\.DRIFT\.srt$", f.name)
        if m:
            existing_counts.add(int(m.group(1)))
    
    for f in get_subtitle_files_by_pattern(movie_path.parent, lang, ".FAILED"):
        m = re.match(r"^(\d+)\." + re.escape(lang) + r"\.number\d+\.FAILED\.srt$", f.name)
        if m:
            existing_counts.add(int(m.group(1)))
    all_srt_files = get_subtitle_files_by_pattern(movie_path.parent, lang)
    normal_count = len([f for f in all_srt_files if not (f.name.endswith('.DRIFT.srt') or f.name.endswith('.FAILED.srt'))])
    total_existing = normal_count + \
                    len(get_subtitle_files_by_pattern(movie_path.parent, lang, ".DRIFT")) + \
                    len(get_subtitle_files_by_pattern(movie_path.parent, lang, ".FAILED"))
    return existing_counts, total_existing

def build_search_query(raw_title: str) -> str:
    year_match = re.search(r'(19|20)\d{2}', raw_title)
    if year_match:
        year = year_match.group(0)
        idx = year_match.end()
        left = raw_title[:idx].rstrip(" ._-()[]")
        query = left.strip()
    else:
        query = clean_title(raw_title)
    return clean_query(query)

def clean_query(query):
    query = re.sub(r'\s*\[[A-Z]{2}\]?$', '', query, flags=re.IGNORECASE).strip()
    query = re.sub(r'\[[A-Z]{2}\]', '', query, flags=re.IGNORECASE)
    query = re.sub(r'[\[\](){}]', '', query)
    query = query.replace('.', ' ')
    query = re.sub(r'(19|20)\d{2}$', lambda m: m.group(0), query)
    query = re.sub(r'(?<!\d)(\d{1,2})$', '', query).strip()
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
    query = re.sub(r'\b\d{1,2}\b', '', query)
    for placeholder, year in year_placeholders:
        query = query.replace(placeholder, year)
    for placeholder, three in three_placeholders:
        query = query.replace(placeholder, three)
    query = re.sub(r'\s+', ' ', query).strip()
    return query

def search_subtitles(movie_path: Path, jwt_token: str):
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
    missing_langs = []
    drift_langs = {}
    for lang in LANGUAGES:
        if lang in skip_langs:
            continue
        normal = base.with_name(f"{base.name}.{lang}.srt")
        all_srt_files = get_subtitle_files_by_pattern(movie_path.parent, lang)
        sync = [f for f in all_srt_files if not (f.name.endswith('.DRIFT.srt') or f.name.endswith('.FAILED.srt'))]
        drift = get_subtitle_files_by_pattern(movie_path.parent, lang, ".DRIFT")
        if drift:
            drift_langs[lang] = drift
        if not normal.exists() and not sync and not drift:
            missing_langs.append(lang)
    if drift_langs:
        def process_drift_batch(top_results, drift_files, lang, used_fallback):
            drift_numbers = set()
            for f in drift_files:
                m = re.search(rf"\.{lang}\.number(\d+)\.DRIFT\.srt$", f.name)
                if m:
                    drift_numbers.add(int(m.group(1)))
            drift_numbers = sorted(drift_numbers)
            available_count = len(top_results)
            all_indices = set(range(1, available_count + 1))
            drift_set = set(drift_numbers)
            not_tried_indices = sorted(all_indices - drift_set)
            batch_to_try = not_tried_indices[:TOP_DOWNLOADS]
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
                    genuinely_new = sorted(genuinely_new, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:MAX_SEARCH_RESULTS]
                    if genuinely_new:
                        all_srt_files = list(movie_path.parent.glob(f"*.{lang}.number*.srt"))
                        existing_downloads = len([f for f in all_srt_files if not (f.name.endswith('.DRIFT.srt') or f.name.endswith('.FAILED.srt'))])
                        existing_drifts = sum(1 for _ in movie_path.parent.glob(f"*.{lang}.number*.DRIFT.srt"))
                        existing_failed = sum(1 for _ in movie_path.parent.glob(f"*.{lang}.number*.FAILED.srt"))
                        total_downloaded = existing_downloads + existing_drifts + existing_failed
                        if total_downloaded >= MAX_SEARCH_RESULTS:
                            print_and_log(f"{acq_tag()} {Fore.YELLOW}MAX_SEARCH_RESULTS limit ({MAX_SEARCH_RESULTS}) reached for {lang.upper()}. Forcing to last resort.{Style.RESET_ALL}")
                            genuinely_new = []
                        else:
                            remaining_slots = MAX_SEARCH_RESULTS - total_downloaded
                            candidates_to_download = genuinely_new[:min(TOP_DOWNLOADS, remaining_slots)]
                            print_and_log(f"{acq_tag()} {Fore.YELLOW}Broader search found {len(candidates_to_download)} genuinely new candidates for {lang.upper()}. (Downloaded: {total_downloaded}/{MAX_SEARCH_RESULTS}){Style.RESET_ALL}")
                            print_subtitle_list(candidates_to_download, lang, color=Fore.LIGHTYELLOW_EX)
                            drift_indices = []
                            for f in drift_files:
                                m = re.search(rf"\.number(\d+)\.DRIFT\.srt$", f.name)
                                if m:
                                    drift_indices.append(int(m.group(1)))
                            start_index = max(drift_indices) + 1 if drift_indices else 1
                            
                            for i, candidate in enumerate(candidates_to_download, start=start_index):
                                candidate_file_name = candidate['attributes']['files'][0]['file_name']
                                cand_downloads = candidate['attributes'].get('download_count', 0)
                                download_top_subtitles([candidate], lang, movie_path.parent, jwt_token, mkv_path=movie_path, candidate_index=i)
                            print_and_log(f"{acq_tag()} {Fore.GREEN}*{Style.RESET_ALL} Broader batch download complete for {lang.upper()}!\n{Style.RESET_ALL}")
                            if (query, movie_path, lang) in missing_queries:
                                missing_queries.remove((query, movie_path, lang))
                            return
                    if not genuinely_new:
                        print_and_log(f"{acq_tag()} {Fore.YELLOW}Broader search found no genuinely new candidates for {lang.upper()}.".format(lang=lang))
                        last_resort_msg = f"Last resort search term for {lang.upper()}: '{query}'"
                        print_and_log_colored(f"{acq_tag()} {Fore.LIGHTYELLOW_EX}{last_resort_msg}{Style.RESET_ALL}")
                        print_and_log(f"{acq_tag()} {last_resort_msg}")
                        print_and_log(f"{acq_tag()} {Fore.RED}Last resort: downloading ALL candidates for {lang.upper()} (no filtering)!{Style.RESET_ALL}")
                        all_candidates = sorted(unfiltered_results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:TOP_DOWNLOADS]
                        unique_candidates = {}
                        for candidate in all_candidates:
                            cand_downloads = candidate['attributes'].get('download_count', 0)
                            if cand_downloads not in unique_candidates:
                                unique_candidates[cand_downloads] = candidate
                        all_candidates = list(unique_candidates.values())
                        print_subtitle_list(all_candidates, lang, color=Fore.LIGHTRED_EX)
                        any_downloaded = False
                        for i, candidate in enumerate(all_candidates, start=1):
                            candidate_file_name = candidate['attributes']['files'][0]['file_name']
                            cand_downloads = candidate['attributes'].get('download_count', 0)
                            srt_exists = any(f.name.startswith(f"{cand_downloads}.{lang}.") and f.name.endswith(".srt") and not (f.name.endswith(".DRIFT.srt") or f.name.endswith(".FAILED.srt")) for f in movie_path.parent.glob(f"*.{lang}.number*.srt"))
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
            params = {
                "query": query,
                "languages": lang
            }
            print_and_log(f"\n{acq_tag()} {Fore.CYAN}Search query for {lang.upper()}: '{display_query}'{Style.RESET_ALL}")
            headers = {
                "Authorization": f"Bearer {jwt_token}",
                "User-Agent": "NexigenSubtitleBot v1.0",
                "Api-Key": API_KEY
            }
            response = requests.get(f"{API_URL}/subtitles", headers=headers, params=params)
            time.sleep(0.5)
            if response.status_code == 200:
                data = response.json()
                results = data.get("data", [])
                filtered_results = filter_subtitles_by_query(results, query)
                top_results = sorted(filtered_results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:MAX_SEARCH_RESULTS]
                header = f"\n{acq_tag()} Top {len(top_results)} subtitles ({lang.upper()}):"
                print_and_log(header)
                print_subtitle_list(top_results, lang, color=Fore.LIGHTBLUE_EX)
                if top_results:
                    process_drift_batch(top_results, drift_files, lang, used_fallback=False)
                    continue
                print_and_log(f"{acq_tag()} No results with filter, trying without a filter...")
                top_results_unfiltered = sorted(results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:MAX_SEARCH_RESULTS]
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
                    top_results = sorted(filtered_results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:MAX_SEARCH_RESULTS]
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
        params = {
            "query": query,
            "languages": lang
        }
        print_and_log(f"\n{acq_tag()} * Search query for language '{lang}': '{display_query}'")
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "User-Agent": "NexigenSubtitleBot v1.0",
            "Api-Key": API_KEY
        }
        response = requests.get(f"{API_URL}/subtitles", headers=headers, params=params)
        time.sleep(0.5)
        if response.status_code == 200:
            data = response.json()
            results = data.get("data", [])
            filtered_results = filter_subtitles_by_query(results, query)
            existing_counts, total_existing = count_existing_subtitles(movie_path, lang)
            filtered_results = [r for r in filtered_results if r['attributes'].get('download_count', 0) not in existing_counts]
            if total_existing >= MAX_SEARCH_RESULTS:
                print_and_log(f"{acq_tag()} {Fore.YELLOW}MAX_SEARCH_RESULTS limit ({MAX_SEARCH_RESULTS}) reached for {lang.upper()}. Skipping to missing_queries.{Style.RESET_ALL}")
                if not is_movie_language_skipped(movie_path, lang):
                    missing_queries.append((display_query, movie_path, lang))
                continue
            remaining_slots = MAX_SEARCH_RESULTS - total_existing
            top_results = sorted(filtered_results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:remaining_slots]
            header = f"\n{acq_tag()} Top {len(top_results)} subtitles ({lang.upper()}):"
            print_and_log(header)
            print_subtitle_list(top_results, lang, color=Fore.LIGHTBLUE_EX)
            if top_results:
                start_index = get_next_sub_index(movie_path.parent, lang)
                for i, candidate in enumerate(top_results[:TOP_DOWNLOADS], start=start_index):
                    download_top_subtitles([candidate], lang, movie_path.parent, jwt_token, mkv_path=movie_path, candidate_index=i)
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
            top_unfiltered = sorted(unfiltered_results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:remaining_slots]
            print_and_log(f"\n{acq_tag()} Top {len(top_unfiltered)} subtitles UNFILTERED ({lang.upper()}):")
            print_subtitle_list(top_unfiltered, lang, color=Fore.LIGHTBLUE_EX)
            if top_unfiltered:
                start_index = get_next_sub_index(movie_path.parent, lang)
                for i, candidate in enumerate(top_unfiltered[:TOP_DOWNLOADS], start=start_index):
                    download_top_subtitles([candidate], lang, movie_path.parent, jwt_token, mkv_path=movie_path, candidate_index=i)
                continue
            print_and_log(f"{acq_tag()} No results without a filter, trying fallback search...")
            fallback_query = clean_title(raw_title)
            params_fallback = dict(params)
            params_fallback["query"] = fallback_query
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
                top_fallback = sorted(fallback_filtered, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:remaining_slots]
                print_and_log(f"\n{acq_tag()} Top {len(top_fallback)} subtitles (clean_title, UNFILTERED, {lang.upper()}):")
                print_subtitle_list(top_fallback, lang, color=Fore.LIGHTRED_EX)
                if top_fallback:
                    start_index = get_next_sub_index(movie_path.parent, lang)
                    for i, candidate in enumerate(top_fallback[:TOP_DOWNLOADS], start=start_index):
                        download_top_subtitles([candidate], lang, movie_path.parent, jwt_token, mkv_path=movie_path, candidate_index=i)
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
            top_results = sorted(filtered_results, key=lambda r: r['attributes'].get('download_count', 0), reverse=True)[:MAX_SEARCH_RESULTS]
            print_and_log(f"\n{acq_tag()} Top {len(top_results)} subtitles ({lang.upper()}):")
            print_subtitle_list(top_results, lang, color=Fore.LIGHTBLUE_EX)
            if top_results:
                start_index = get_next_sub_index(movie_path.parent, lang)
                for i, candidate in enumerate(top_results[:TOP_DOWNLOADS], start=start_index):
                    download_top_subtitles([candidate], lang, movie_path.parent, jwt_token, mkv_path=movie_path, candidate_index=i)
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
        print_and_log(f"  {Fore.LIGHTBLUE_EX}1{Style.RESET_ALL} = Type in a manual search term")
        print_and_log(f"  {Fore.RED}2{Style.RESET_ALL} = Delete mkv")
        print_and_log(f"  {Fore.LIGHTYELLOW_EX}3{Style.RESET_ALL} = Increase global subtitle download limit (affects all languages/movies)")
        print_and_log(f"  {Fore.YELLOW}4{Style.RESET_ALL} = Skip")
        print_and_log(f"  {Fore.MAGENTA}5{Style.RESET_ALL} = Skip {search_lang.upper()} language and do not show again")
        print_and_log(f"\n{Fore.LIGHTYELLOW_EX}Tip:{Style.RESET_ALL} When many subtitles are found but all fail, some may still match the audio, but are actually rejected false positives. Try testing a few failed subtitles manually, as there could be a good sync among them. Consider lowering reject_offset_threshold in the .config when you get this more often. If problems persist, then the video encoding may be incompatible. Using a different source might yield better results. More info can be found in the readme file.\n")
        choice = input_and_log(f"Choose [{Fore.LIGHTBLUE_EX}1{Style.RESET_ALL}/{Fore.RED}2{Style.RESET_ALL}/{Fore.LIGHTYELLOW_EX}3{Style.RESET_ALL}/{Fore.YELLOW}4{Style.RESET_ALL}/{Fore.MAGENTA}5{Style.RESET_ALL}]: ").strip()
        if choice == "1":
            print_and_log("[ACTION] User chose to type a manual search term.")
            download_successful = False
            while not download_successful:
                new_query = input_and_log(f"{acq_tag()} {Fore.LIGHTYELLOW_EX}Type in a manual search term{Style.RESET_ALL} (or press {Fore.LIGHTYELLOW_EX}enter{Style.RESET_ALL} to go back): ").strip()
                if not new_query:
                    clear_and_print_ascii(BANNER_LINE)
                    print_and_log(f"\n{Style.BRIGHT}{Fore.CYAN}Movie [{display_idx}/{total}]{Style.RESET_ALL}")
                    print_and_log(f"{acq_tag()} What to do with: '{Style.BRIGHT}{query_disp}{Style.RESET_ALL}{Fore.YELLOW}?{Style.RESET_ALL}'\nFile: {Fore.CYAN}{mkv_path.name}{Style.RESET_ALL}\n")
                    print_and_log(f"  {Fore.LIGHTBLUE_EX}1{Style.RESET_ALL} = Type in a manual search term")
                    print_and_log(f"  {Fore.RED}2{Style.RESET_ALL} = Delete mkv")
                    print_and_log(f"  {Fore.LIGHTYELLOW_EX}3{Style.RESET_ALL} = Increase maximum download limit for this movie")
                    print_and_log(f"  {Fore.YELLOW}4{Style.RESET_ALL} = Skip")
                    print_and_log(f"  {Fore.MAGENTA}5{Style.RESET_ALL} = Skip and do not show again")
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
                        m = re.match(r"(\d+)." + re.escape(search_lang) + r".number\d+", f.name)
                        if m:
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
                    next_index = get_next_sub_index(mkv_path.parent, search_lang)
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
            print_and_log("[ACTION] User chose to delete mkv.")
            try:
                mkv_path.unlink()
                print_and_log(f"\n{acq_tag()} {Fore.GREEN}*{Style.RESET_ALL} {mkv_path.name} deleted.")
                input_and_log(f"{acq_tag()} Press Enter to continue...")
            except Exception as e:
                print_and_log(f"\n{acq_tag()} {Fore.RED}# {Style.RESET_ALL}Could not delete {mkv_path.name}: {e}")
                input_and_log(f"{acq_tag()} Press Enter to continue...")
            missing_queries.remove((query, mkv_path, search_lang))
            queries.pop(idx)
            display_idx += 1
            continue
        elif choice == "3":
            print_and_log("[ACTION] User chose to increase global download limit.")
            while True:
                new_limit_input = input_and_log(f"{acq_tag()} {Fore.LIGHTYELLOW_EX}Enter new global download limit (max 50){Style.RESET_ALL} (or press {Fore.LIGHTYELLOW_EX}enter{Style.RESET_ALL} to go back): ").strip()
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
                        print_and_log(f"{acq_tag()} {Fore.YELLOW}Current global max_search_results:{Style.RESET_ALL} {MAX_SEARCH_RESULTS}")
                        print_and_log(f"{acq_tag()} {Fore.GREEN}New global max_search_results:{Style.RESET_ALL} {new_limit}")
                        print_and_log(f"\n{Fore.LIGHTYELLOW_EX}This will update the .config file and restart the acquisition process.{Style.RESET_ALL}")
                        print_and_log(f"{Fore.LIGHTYELLOW_EX}Increasing max_search_results gives subservient the opportunity to download more subtitles.{Style.RESET_ALL}")
                        print_and_log(f"{Fore.LIGHTYELLOW_EX}The new limit will apply for all movies that have yet to be synced, so not just {search_lang.upper()}.{Style.RESET_ALL}")
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

def input_and_log(prompt):
    print_and_log(prompt, end='')
    answer = input('')
    with LOG_FILE.open('a', encoding='utf-8') as f:
        f.write(f'[USER INPUT] {strip_ansi(answer)}\n')
    return answer

def get_video_files_for_folder(folder: Path) -> list[Path]:
    video_files = [*folder.glob('*.mkv'), *folder.glob('*.mp4')]
    if SERIES_MODE:
        return sorted(video_files)
    return [max(video_files, key=lambda f: f.stat().st_size)] if video_files else []
def print_video_header(video_name, idx, total):
    bar = f"{Fore.CYAN}[{idx}/{total}]{Style.RESET_ALL}  {Fore.LIGHTYELLOW_EX}{video_name.upper()}{Style.RESET_ALL}"
    print(bar.ljust(79), end='\n', flush=True)

def process_folder(folder: Path, scanned_folders: set, jwt_token: str, skipped_movies: set, idx_offset=0, total_videos=None, video_idx_start=1):
    video_files = get_video_files_for_folder(folder)
    processed = 0
    if not video_files:
        return processed
   
    for i, video_file in enumerate(video_files, 1):
        all_languages_skipped = all(is_movie_language_skipped(video_file, lang) for lang in LANGUAGES)
        if all_languages_skipped:
            print_and_log(f"{acq_tag()} {Fore.MAGENTA}*{Style.RESET_ALL} Skipping {video_file.name} (all languages marked as 'do not show again').")
            continue
        if total_videos is not None:
            clear_and_print_ascii(BANNER_LINE)
            print_video_header(video_file.stem, idx_offset + i, total_videos)
        base = video_file.with_suffix("")
        lang_status = {}
        drift_detected = False
        for lang in LANGUAGES:
            normal = base.with_name(f"{base.name}.{lang}.srt")
            all_srt_files = list(folder.glob(f"*.{lang}.number*.srt"))
            sync = [f for f in all_srt_files if not (f.name.endswith('.DRIFT.srt') or f.name.endswith('.FAILED.srt'))]
            drift = any(folder.glob(f"*.{lang}.number*.DRIFT.srt"))
            if drift:
                drift_detected = True
            lang_status[lang] = (normal.exists() or sync) and not drift
        if all(lang_status.values()) and not drift_detected:
            print_and_log(f"{acq_tag()} * All subtitles present or in sync. Skipping {video_file.name}.")
            continue
        scanned_folders.add(folder)
        print_and_log(f"{acq_tag()} -> Video found: {video_file.name}")
        search_subtitles(video_file, jwt_token)
        print_and_log(f"---\n")
        processed += 1
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

def get_next_sub_index(folder: Path, lang: str) -> int:
    pattern = f"*.{lang}.number*.srt"
    indices = []
    for f in folder.glob(pattern):
        m = re.search(rf"\.{lang}\.number(\d+)", f.name)
        if m:
            indices.append(int(m.group(1)))
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
