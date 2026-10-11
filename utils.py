from platformdirs import user_config_dir
from pathlib import Path
from colorama import Fore, Style
import os
import subprocess
import time
import re
import shutil

def set_console_size(cols=120, lines=40):
    """Set the console window size. Only has effect on Windows conhost (cmd.exe).
    Has no effect in Windows Terminal, which manages its own window size.
    Values are read from .config (console_width / console_height) when available."""
    if os.name != 'nt':
        return
    # Try to read from config
    try:
        config_path = get_subservient_folder() / '.config'
        if config_path.exists():
            for line in config_path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line.startswith('console_width='):
                    cols = int(line.split('=', 1)[1].strip())
                elif line.startswith('console_height='):
                    lines = int(line.split('=', 1)[1].strip())
    except Exception:
        pass
    if os.name != 'nt':
        return
    try:
        import ctypes
        import ctypes.wintypes as wintypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE... use output
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE

        # Set screen buffer size
        class COORD(ctypes.Structure):
            _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]
        class SMALL_RECT(ctypes.Structure):
            _fields_ = [("Left", wintypes.SHORT), ("Top", wintypes.SHORT),
                        ("Right", wintypes.SHORT), ("Bottom", wintypes.SHORT)]
        class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
            _fields_ = [("dwSize", COORD), ("dwCursorPosition", COORD),
                        ("wAttributes", wintypes.WORD),
                        ("srWindow", SMALL_RECT), ("dwMaximumWindowSize", COORD)]

        info = CONSOLE_SCREEN_BUFFER_INFO()
        kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info))

        # First shrink the window to avoid buffer-smaller-than-window errors
        small_rect = SMALL_RECT(0, 0, 1, 1)
        kernel32.SetConsoleWindowInfo(handle, True, ctypes.byref(small_rect))

        # Set buffer size
        buf_size = COORD(cols, max(lines, 9000))
        kernel32.SetConsoleScreenBufferSize(handle, buf_size)

        # Set window size
        win_rect = SMALL_RECT(0, 0, cols - 1, lines - 1)
        kernel32.SetConsoleWindowInfo(handle, True, ctypes.byref(win_rect))
    except Exception:
        # Fallback for classic cmd.exe
        try:
            os.system(f"mode con: cols={cols} lines={lines}")
        except Exception:
            pass

def clean_display_name(filename, config_path=None):
    """Clean video/subtitle filename for display by removing unwanted terms."""
    if not filename:
        return filename
    
    unwanted_terms = []
    if config_path and config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('UNWANTED_TERMS='):
                        terms_str = line.split('=', 1)[1].strip()
                        unwanted_terms = [term.strip() for term in terms_str.split(',') if term.strip()]
                        break
        except Exception:
            pass
    
    if not unwanted_terms:
        unwanted_terms = [
            'sample', 'cam', 'ts', 'workprint', 'unrated', 'uncut', '720p', '1080p', '2160p', '480p', 
            '4k', 'uhd', 'imax', 'eng', 'ita', 'jap', 'hindi', 'web', 'webrip', 'web-dl', 'bluray', 
            'brrip', 'bdrip', 'dvdrip', 'hdrip', 'hdtv', 'remux', 'x264', 'x265', 'h.264', 'h.265', 
            'hevc', 'avc', 'hdr', 'hdr10', 'hdr10+', 'dv', 'dolby.vision', 'sdr', '10bit', '8bit', 
            'ddp', 'dd+', 'dts', 'aac', 'ac3', 'eac3', 'truehd', 'atmos', 'flac', '5.1', '7.1', '2.0'
        ]
    
    year_match = re.search(r'\b(19|20)\d{2}\b', filename)
    if year_match:
        year_end = year_match.end()
        clean_name = filename[:year_end]
        
        remaining = filename[year_end:].strip()
        if remaining:
            remaining = re.sub(r'\s*[\[\(].*?[\]\)]', '', remaining)
            for term in unwanted_terms:
                remaining = re.sub(r'\b' + re.escape(term) + r'\b', '', remaining, flags=re.IGNORECASE)
            remaining = re.sub(r'\s+', ' ', remaining).strip()
            if remaining and not re.match(r'^[\s\.\-_]+$', remaining):
                clean_name += ' ' + remaining
    else:
        clean_name = filename
        for term in unwanted_terms:
            clean_name = re.sub(r'\b' + re.escape(term) + r'\b', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
    
    return clean_name.strip()

def ensure_file_writable(file_path):
    """Ensure a file is writable by setting appropriate permissions."""
    try:
        if os.name == 'nt':
            subprocess.run(['attrib', '-r', str(file_path)], capture_output=True, check=False)
        else:
            os.chmod(file_path, 0o644)
        return True
    except Exception:
        return False

def ensure_directory_writable(dir_path):
    """Ensure a directory is writable by setting appropriate permissions."""
    try:
        if os.name == 'nt':
            subprocess.run(['attrib', '-r', str(dir_path), '/d'], capture_output=True, check=False)
        else: 
            os.chmod(dir_path, 0o755)
        return True
    except Exception:
        return False

def fix_permissions_proactively(file_path):
    """Proactively fix permissions for a file and its parent directory."""
    fixed_items = []
    try:
        parent_dir = file_path.parent
        if ensure_directory_writable(parent_dir):
            fixed_items.append(f"directory {parent_dir.name}")
        if file_path.exists() and ensure_file_writable(file_path):
            fixed_items.append(f"file {file_path.name}")
            
        return fixed_items
    except Exception:
        return []

ASCII_ART = r"""
  _________    ___.                             .__               __   
 /   _____/__ _\_ |__   ______ ______________  _|__| ____   _____/  |_ 
 \_____  \|  |  \ __ \ /  ___// __ \_  __ \  \/ /  |/ __ \ /    \   __\
 /        \  |  / \_\ \\___ \\  ___/|  | \/\   /|  \  ___/|   |  \  |  
/_______  /____/|___  /____  >\___  >__|    \_/ |__|\___  >___|  /__|  
        \/          \/     \/     \/                    \/     \/      
"""

LANG_3TO2_MAP = {
    'eng': 'en', 'dut': 'nl', 'nld': 'nl', 'ger': 'de', 'deu': 'de',
    'fre': 'fr', 'fra': 'fr', 'spa': 'es', 'ita': 'it', 'por': 'pt',
    'rus': 'ru', 'jpn': 'ja', 'jpn': 'ja', 'kor': 'ko', 'chi': 'zh', 'zho': 'zh',
    'swe': 'sv', 'nor': 'no', 'dan': 'da', 'fin': 'fi', 'pol': 'pl', 'hun': 'hu',
    'cze': 'cs', 'ces': 'cs', 'slo': 'sk', 'slk': 'sk', 'slv': 'sl', 'est': 'et',
    'lav': 'lv', 'lat': 'lv', 'lit': 'lt', 'ell': 'el', 'gre': 'el', 'tur': 'tr',
    'ara': 'ar', 'heb': 'he', 'hin': 'hi', 'tha': 'th', 'vie': 'vi', 'ind': 'id',
    'msa': 'ms', 'may': 'ms', 'tgl': 'tl', 'fil': 'tl', 'ukr': 'uk', 'bul': 'bg',
    'hrv': 'hr', 'scr': 'hr', 'srp': 'sr', 'ron': 'ro', 'rum': 'ro', 'cat': 'ca',
    'baq': 'eu', 'eus': 'eu', 'glg': 'gl', 'isl': 'is', 'ice': 'is', 'mal': 'mt',
    'mkd': 'mk', 'mac': 'mk', 'alb': 'sq', 'sqi': 'sq', 'bos': 'bs', 'aze': 'az',
    'kaz': 'kk', 'uzb': 'uz', 'tat': 'tt', 'kir': 'ky', 'arm': 'hy', 'hye': 'hy',
    'geo': 'ka', 'kat': 'ka', 'mya': 'my', 'bur': 'my', 'khm': 'km', 'lao': 'lo',
    'nep': 'ne', 'pan': 'pa', 'sin': 'si', 'tam': 'ta', 'tel': 'te', 'kan': 'kn',
    'mal': 'ml', 'ori': 'or', 'guj': 'gu', 'ben': 'bn', 'asm': 'as', 'mar': 'mr',
    'san': 'sa', 'urd': 'ur', 'pes': 'fa', 'fas': 'fa', 'kur': 'ku', 'pus': 'ps',
    'bal': 'bal', 'sind': 'sd', 'som': 'so', 'amh': 'am', 'tir': 'ti', 'orm': 'om',
    'swa': 'sw', 'kin': 'rw', 'run': 'rn', 'nya': 'ny', 'zul': 'zu', 'xho': 'xh',
    'afr': 'af', 'ibo': 'ig', 'yor': 'yo', 'hau': 'ha', 'sna': 'sn', 'tsn': 'tn',
    'tso': 'ts', 'ven': 've', 'wol': 'wo', 'fao': 'fo', 'grn': 'gn', 'aym': 'ay',
    'que': 'qu', 'aym': 'ay', 'guj': 'gu', 'ori': 'or', 'mlg': 'mg', 'nav': 'nv',
    'ota': 'ota', 'gla': 'gd', 'gle': 'ga', 'cor': 'kw', 'cym': 'cy', 'wel': 'cy',
    'gag': 'gag', 'ava': 'av', 'che': 'ce', 'chu': 'cu', 'chv': 'cv', 'kom': 'kv',
    'udm': 'udm', 'sah': 'sah', 'tuv': 'tyv', 'sco': 'sco', 'gag': 'gag',
}

LANG_2TO3_PREFERRED = {
    'en': 'eng', 'nl': 'dut', 'de': 'ger', 'fr': 'fre', 'es': 'spa', 'it': 'ita', 'pt': 'por',
    'ru': 'rus', 'ja': 'jpn', 'ko': 'kor', 'zh': 'zho', 'sv': 'swe', 'no': 'nor', 'da': 'dan',
    'fi': 'fin', 'pl': 'pol', 'hu': 'hun', 'cs': 'ces', 'sk': 'slk', 'sl': 'slv', 'et': 'est',
    'lv': 'lav', 'lt': 'lit', 'el': 'ell', 'tr': 'tur', 'ar': 'ara', 'he': 'heb', 'hi': 'hin',
    'th': 'tha', 'vi': 'vie', 'id': 'ind', 'ms': 'msa', 'tl': 'tgl', 'uk': 'ukr', 'bg': 'bul',
    'hr': 'hrv', 'sr': 'srp', 'ro': 'ron', 'ca': 'cat', 'eu': 'eus', 'gl': 'glg', 'is': 'isl',
    'mt': 'mal', 'mk': 'mkd', 'sq': 'alb', 'bs': 'bos', 'az': 'aze', 'kk': 'kaz', 'uz': 'uzb',
    'tt': 'tat', 'ky': 'kir', 'hy': 'arm', 'ka': 'geo', 'my': 'mya', 'km': 'khm', 'lo': 'lao',
    'ne': 'nep', 'pa': 'pan', 'si': 'sin', 'ta': 'tam', 'te': 'tel', 'kn': 'kan', 'ml': 'mal',
    'or': 'ori', 'gu': 'guj', 'bn': 'ben', 'as': 'asm', 'mr': 'mar', 'sa': 'san', 'ur': 'urd',
    'fa': 'fas', 'ku': 'kur', 'ps': 'pus', 'sd': 'sind', 'so': 'som', 'am': 'amh', 'ti': 'tir',
    'om': 'orm', 'sw': 'swa', 'rw': 'kin', 'rn': 'run', 'ny': 'nya', 'zu': 'zul', 'xh': 'xho',
    'af': 'afr', 'ig': 'ibo', 'yo': 'yor', 'ha': 'hau', 'sn': 'sna', 'tn': 'tsn', 'ts': 'tso',
    've': 'ven', 'wo': 'wol', 'fo': 'fao', 'gn': 'grn', 'ay': 'aym', 'qu': 'que', 'mg': 'mlg',
    'nv': 'nav', 'gd': 'gla', 'ga': 'gle', 'kw': 'cor', 'cy': 'cym', 'av': 'ava', 'ce': 'che',
    'cu': 'chu', 'cv': 'chv', 'kv': 'kom'
}

# Full language names (as commonly used by subtitle sites, e.g. "31_Dutch.srt") mapped to 2-letter codes.
LANG_FULLNAME_TO_2 = {
    'english': 'en', 'dutch': 'nl', 'german': 'de', 'french': 'fr', 'spanish': 'es',
    'italian': 'it', 'portuguese': 'pt', 'brazilian': 'pt', 'russian': 'ru', 'japanese': 'ja',
    'korean': 'ko', 'chinese': 'zh', 'swedish': 'sv', 'norwegian': 'no', 'bokmal': 'no',
    'danish': 'da', 'finnish': 'fi', 'polish': 'pl', 'hungarian': 'hu', 'czech': 'cs',
    'slovak': 'sk', 'slovenian': 'sl', 'estonian': 'et', 'latvian': 'lv', 'lithuanian': 'lt',
    'greek': 'el', 'turkish': 'tr', 'arabic': 'ar', 'hebrew': 'he', 'hindi': 'hi',
    'thai': 'th', 'vietnamese': 'vi', 'indonesian': 'id', 'malay': 'ms', 'tagalog': 'tl',
    'filipino': 'tl', 'ukrainian': 'uk', 'bulgarian': 'bg', 'croatian': 'hr', 'serbian': 'sr',
    'romanian': 'ro', 'catalan': 'ca', 'basque': 'eu', 'galician': 'gl', 'icelandic': 'is',
    'albanian': 'sq', 'bosnian': 'bs', 'azerbaijani': 'az', 'kazakh': 'kk', 'uzbek': 'uz',
    'armenian': 'hy', 'georgian': 'ka', 'burmese': 'my', 'khmer': 'km', 'lao': 'lo',
    'nepali': 'ne', 'punjabi': 'pa', 'sinhala': 'si', 'tamil': 'ta', 'telugu': 'te',
    'kannada': 'kn', 'malayalam': 'ml', 'oriya': 'or', 'gujarati': 'gu', 'bengali': 'bn',
    'assamese': 'as', 'marathi': 'mr', 'sanskrit': 'sa', 'urdu': 'ur', 'persian': 'fa',
    'farsi': 'fa', 'kurdish': 'ku', 'pashto': 'ps', 'somali': 'so', 'amharic': 'am',
    'swahili': 'sw', 'afrikaans': 'af', 'yoruba': 'yo', 'hausa': 'ha', 'welsh': 'cy',
    'irish': 'ga', 'macedonian': 'mk', 'maltese': 'mt', 'esperanto': 'eo', 'big5': 'zh',
    'mandarin': 'zh', 'cantonese': 'zh',
}

def detect_language_from_filename(filename: str):
    """
    Detect a 2-letter language code from a subtitle filename that identifies
    its language via a full language name (e.g. "31_Dutch.srt") or a 2/3-letter
    language code, rather than (or in addition to) an SxxExx episode code.
    Returns the 2-letter code, or None if nothing recognizable was found.
    """
    stem = Path(filename).stem
    tokens = re.split(r'[._\-\s]+', stem)
    for token in reversed(tokens):
        t = token.lower()
        if t in LANG_FULLNAME_TO_2:
            return LANG_FULLNAME_TO_2[t]
        if len(t) == 3 and t in LANG_3TO2_MAP:
            return LANG_3TO2_MAP[t]
        if len(t) == 2 and t in LANG_2TO3_PREFERRED:
            return t
    return None

def get_subservient_folder():
    """Get the Subservient anchor folder path from config file."""
    config_dir = Path(user_config_dir()) / "Subservient"
    pathfile = config_dir / "Subservient_pathfiles"
    if pathfile.exists():
        with open(pathfile, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("subservient_anchor="):
                    path = line.split("=", 1)[1].strip()
                    if path:
                        candidate_path = Path(path)
                        if candidate_path.exists() and (candidate_path / '.config').exists():
                            return candidate_path
    return Path(__file__).parent

def get_subordinate_directory():
    """Get the directory where subordinate.py is located from pathfile."""
    config_dir = Path(user_config_dir()) / "Subservient"
    pathfile = config_dir / "Subservient_pathfiles"
    
    if pathfile.exists():
        with open(pathfile, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("subordinate_path="):
                    path = line.split("=", 1)[1].strip()
                    if path:
                        subordinate_path = Path(path)
                        if subordinate_path.exists():
                            return subordinate_path.parent
    
    cwd = Path.cwd()
    if (cwd / "subordinate.py").exists():
        return cwd
    
    return get_subservient_folder()

def clear_and_print_ascii(banner_line):
    """Clear screen and display ASCII art with banner."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Style.BRIGHT}{Fore.BLUE}{ASCII_ART}{Style.RESET_ALL}\n")
    print(f"{Style.BRIGHT}{banner_line}{Style.RESET_ALL}\n")

def map_lang_3to2(code):
    """Convert 3-letter language code to 2-letter equivalent."""
    code = code.lower()
    return LANG_3TO2_MAP.get(code, code)

def are_languages_equivalent(lang1, lang2):
    """Check if two language codes represent the same language (handles both 2-letter and 3-letter codes)."""
    lang1 = (lang1 or '').lower()
    lang2 = (lang2 or '').lower()
    
    if lang1 == lang2:
        return True
    
    if len(lang1) == 3:
        lang1_2letter = map_lang_3to2(lang1)
    else:
        lang1_2letter = lang1
        
    if len(lang2) == 3:
        lang2_2letter = map_lang_3to2(lang2)
    else:
        lang2_2letter = lang2
    
    return lang1_2letter == lang2_2letter

def lang_in_list(target_lang, lang_list):
    """Check if target language is semantically present in language list (handles different 3-letter variants)."""
    return any(are_languages_equivalent(target_lang, lang) for lang in lang_list)

def get_internal_subtitle_languages(video_path):
    """Extract internal subtitle languages from video file using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "s", "-show_entries",
        "stream=index:stream_tags=language", "-of", "csv=p=0", video_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        lines = [l for l in result.stdout.strip().split('\n') if l.strip()]
        languages = set()
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 2:
                lang_code = parts[1].strip()
                if lang_code and lang_code != 'und':
                    if len(lang_code) == 3:
                        lang_code = map_lang_3to2(lang_code)
                    languages.add(lang_code.lower())
        return sorted(list(languages))
    except Exception:
        return []
def trim_movie_name(filename):
    """Extract clean movie name by removing year and extension patterns."""
    m = re.search(r'^(.*?)(\(|\.|\s)(19|20)\d{2}(\)|\.|\s)', filename)
    if m:
        base = filename[:m.end(4)].strip()
        base = re.sub(r'\.+$', '', base).strip()
        return base
    return filename

def extract_sxxexx_code(name: str) -> str | None:
    """Extract season/episode code from filename."""
    import re
    # Episode allows up to 3 digits (e.g. "S06E001") so it isn't truncated to just the first 2 digits
    match = re.search(r"[sS](\d{1,2})[eE](\d{1,3})", name)
    return f"S{int(match.group(1)):02d}E{int(match.group(2)):02d}" if match else None

def scan_subtitle_coverage(videos, languages, series_mode=False, show_progress=True, logger_func=None, sync_tag_func=None):
    """Scan video files and analyze subtitle coverage for specified languages."""
    if not videos:
        return []
    log_func = logger_func if logger_func else print
    tag_func = sync_tag_func if sync_tag_func else lambda: ""
    if show_progress:
        if sync_tag_func:
            clear_and_print_ascii("                   [Phase 4/4] Subtitle Synchronisation")
            log_func(f"{Fore.CYAN}Checking subtitle availability for all movies..{Style.RESET_ALL}\n")
        else:
            clear_and_print_ascii("                   Subtitle Coverage Scan")
            log_func(f"{Fore.CYAN}Checking subtitle availability for all movies..{Style.RESET_ALL}\n")
    coverage_results = []
    total_videos = len(videos)
    for idx, video in enumerate(videos, 1):
        video_path = Path(video)
        video_name = trim_movie_name(video_path.name)
        if series_mode:
            _sxxexx = extract_sxxexx_code(video_path.name)
            if _sxxexx:
                video_name = f"{video_name} {_sxxexx.upper()}"
        if show_progress:
            if sync_tag_func:
                clear_and_print_ascii("                   [Phase 4/4] Subtitle Synchronisation")
                log_func(f"{Fore.CYAN}[{idx}/{total_videos}]{Style.RESET_ALL}  {Fore.LIGHTYELLOW_EX}{video_name.upper()}{Style.RESET_ALL}")
                log_func(f"{tag_func()} {Fore.YELLOW}Scanning subtitle coverage...{Style.RESET_ALL}")
            else:
                clear_and_print_ascii("                   Subtitle Coverage Scan")
                log_func(f"{Fore.CYAN}[{idx}/{total_videos}]{Style.RESET_ALL}  {Fore.LIGHTYELLOW_EX}{video_name.upper()}{Style.RESET_ALL}")
                log_func(f"{Fore.YELLOW}Scanning subtitle coverage...{Style.RESET_ALL}")
        video_basename = video_path.stem
        video_dir = video_path.parent
        coverage = {}
        internal_langs = get_internal_subtitle_languages(str(video_path))
        for lang in languages:
            external_found = False
            internal_found = lang.lower() in internal_langs
            
            # Check for external subtitles (both standard and series naming)
            for ext in ('.srt', '.ass'):
                # Check standard naming: filename.lang.ext
                expected_standard = video_dir / f"{video_basename}.{lang}{ext}"
                if expected_standard.exists():
                    external_found = True
                    break
                
                # Check series naming if in series mode: filename.lang.S01E01.ext
                if series_mode:
                    sxxexx_code = extract_sxxexx_code(video_path.name)
                    if sxxexx_code:
                        expected_series = video_dir / f"{video_basename}.{lang}.{sxxexx_code}{ext}"
                        if expected_series.exists():
                            external_found = True
                            break
            if external_found:
                coverage[lang] = 'external'
            elif internal_found:
                coverage[lang] = 'internal'
            else:
                coverage[lang] = 'missing'
        
        coverage_results.append((str(video_path), video_name, coverage))
        if show_progress:
            time.sleep(0.1)
    
    return coverage_results

def display_coverage_results(coverage_results, languages, banner_line=None, return_to_menu=True, logger_func=None, sync_tag_func=None, series_mode=False):
    """Display formatted subtitle coverage report with statistics."""
    log_func = logger_func if logger_func else print
    tag_func = sync_tag_func if sync_tag_func else lambda: ""

    # Sort episodes within each series group (preserving series order)
    if series_mode and coverage_results:
        from collections import OrderedDict
        groups = OrderedDict()
        for item in coverage_results:
            _vpath, _vname, _cov = item
            _base = re.sub(r'\s+[Ss]\d{2}[Ee]\d{2}.*', '', _vname).strip()
            groups.setdefault(_base, []).append(item)
        coverage_results = []
        for _items in groups.values():
            _items.sort(key=lambda x: extract_sxxexx_code(Path(x[0]).name) or '')
            coverage_results.extend(_items)

    if banner_line:
        clear_and_print_ascii(banner_line)
    else:
        clear_and_print_ascii("                   Subtitle Coverage Report:")
    log_func(f"{tag_func()}{Style.BRIGHT}{Fore.CYAN}Subtitle Coverage Report:{Style.RESET_ALL}\n")
    if not coverage_results:
        log_func(f"{tag_func()}{Fore.YELLOW}No videos found to scan.{Style.RESET_ALL}")
        if return_to_menu:
            input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")
        return
    for video_path, video_name, coverage in coverage_results:
        status_parts = []
        
        for lang in languages:
            time.sleep(0.1)
            status = coverage.get(lang, 'missing')
            lang_upper = lang.upper()
            if status == 'external':
                status_parts.append(f"{Fore.GREEN}[{lang_upper} SRT]{Style.RESET_ALL}")
            elif status == 'internal':
                status_parts.append(f"{Fore.YELLOW}[{lang_upper} internal]{Style.RESET_ALL}")
            else:
                status_parts.append(f"{Fore.RED}[{lang_upper} missing]{Style.RESET_ALL}")
        
        status_line = " ".join(status_parts)
        log_func(f"{video_name} {status_line}")
    log_func(f"\n{tag_func()}{Style.BRIGHT}{Fore.CYAN}Summary:{Style.RESET_ALL}")
    total_videos = len(coverage_results)
    total_subtitles = total_videos * len(languages)
    external_count = sum(1 for _, _, coverage in coverage_results for lang in languages if coverage.get(lang) == 'external')
    internal_count = sum(1 for _, _, coverage in coverage_results for lang in languages if coverage.get(lang) == 'internal')
    missing_count = sum(1 for _, _, coverage in coverage_results for lang in languages if coverage.get(lang) == 'missing')
    time.sleep(1)
    log_func(f"{tag_func()}Total videos: {total_videos}")
    log_func(f"{tag_func()}Total subtitles: {total_subtitles}")
    log_func(f"{tag_func()}{Fore.GREEN}External (.SRT) subtitles: {external_count}{Style.RESET_ALL}")
    log_func(f"{tag_func()}{Fore.YELLOW}Internal subtitles: {internal_count}{Style.RESET_ALL}")
    log_func(f"{tag_func()}{Fore.RED}Missing subtitles: {missing_count}{Style.RESET_ALL}")
    
    if missing_count == 0:
        log_func(f"\n{tag_func()}{Fore.GREEN}{Style.BRIGHT}✓ All required subtitles are available!{Style.RESET_ALL}")
    else:
        log_func(f"\n{tag_func()}{Fore.LIGHTRED_EX}⚠ {missing_count} subtitle(s) are missing.{Style.RESET_ALL}")
    
    # First pause after coverage results
    if return_to_menu and sync_tag_func:
        input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")
    
    if not sync_tag_func:
        # When called from menu (no sync_tag_func), add enter prompt to return to menu
        if return_to_menu:
            input(f"\n{Fore.YELLOW}Press Enter to return to the main menu...{Style.RESET_ALL} ")
        return
    else:
        # Check run_counter to decide if INFO screen should be shown
        run_counter = get_run_counter_from_config()
        
        # INFO screen disabled
        if False and run_counter < 2:
            # Show INFO section on new screen
            if banner_line:
                clear_and_print_ascii(banner_line)
            else:
                clear_and_print_ascii("                   Subtitle Analysis Tips")
            
            time.sleep(1)
            log_func(f"\n{Style.BRIGHT}INFO:{Style.RESET_ALL} If all your movies show {Fore.GREEN}external .SRT files{Style.RESET_ALL} or you're satisfied with {Fore.YELLOW}internal subtitles{Style.RESET_ALL}, you're all set!\n")

            log_func(f"{Fore.LIGHTYELLOW_EX}If a subtitle ended up as {Fore.RED}missing{Fore.LIGHTYELLOW_EX} or only {Fore.YELLOW}internal{Fore.LIGHTYELLOW_EX}, Subservient has already tried multiple candidates automatically.{Style.RESET_ALL}")
            log_func(f"In rare cases none of the downloaded candidates synced well enough — those are marked as {Fore.YELLOW}DRIFT{Style.RESET_ALL}.")
            log_func("")

            log_func(f"{Fore.LIGHTYELLOW_EX}What you can do:{Style.RESET_ALL}")
            log_func(f"{Fore.CYAN}1.{Style.RESET_ALL} Run Subservient again — during the {Fore.YELLOW}manual verification{Style.RESET_ALL} step you can browse all DRIFT candidates")
            log_func(f"   and pick one that looks good, without downloading anything new.")
            log_func(f"{Fore.CYAN}2.{Style.RESET_ALL} If none of the DRIFT candidates work either, Subservient will automatically")
            log_func(f"   start a new acquisition run to fetch fresh subtitles.")
            log_func("")

            log_func(f"{Fore.GREEN}In most cases everything is handled automatically — this screen is just here to explain the rare exceptions.{Style.RESET_ALL}")
            
            if return_to_menu:
                input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")
    
    # If run_counter >= 2, no INFO screen is shown and no input is needed

def get_languages_from_config(config_path=None):
    """Read languages setting from config file."""
    if config_path is None:
        subservient_folder = get_subservient_folder()
        config_path = subservient_folder / '.config'
    languages = ['en']
    if config_path and Path(config_path).exists():
        try:
            with open(config_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('languages='):
                        lang_str = line.split('=', 1)[1].strip()
                        if lang_str:
                            languages = [lang.strip() for lang in lang_str.split(',') if lang.strip()]
                        break
        except Exception:
            pass
    return languages

def get_series_mode_from_config(config_path=None):
    """Read series_mode setting from config file."""
    if config_path is None:
        subservient_folder = get_subservient_folder()
        config_path = subservient_folder / '.config'
    series_mode = False
    if config_path and Path(config_path).exists():
        try:
            with open(config_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('series_mode='):
                        val = line.split('=', 1)[1].strip().lower()
                        series_mode = val in ['1', 'true', 'yes', 'on']
                        break
        except Exception:
            pass
    return series_mode

def get_run_counter_from_config(config_path=None):
    """Read run_counter setting from config file."""
    if config_path is None:
        subservient_folder = get_subservient_folder()
        config_path = subservient_folder / '.config'
    run_counter = 0
    if config_path and Path(config_path).exists():
        try:
            with open(config_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('run_counter='):
                        try:
                            run_counter = int(line.split('=', 1)[1].strip())
                        except ValueError:
                            run_counter = 0
                        break
        except Exception:
            pass
    return run_counter

def get_skip_dirs_from_config(config_path=None):
    """Read skip_dirs setting from config file and return as lowercase set."""
    if config_path is None:
        subservient_folder = get_subservient_folder()
        config_path = subservient_folder / '.config'
    skip_dirs = set()
    extras_folder_name = None
    
    if config_path and Path(config_path).exists():
        try:
            with open(config_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('skip_dirs='):
                        skip_str = line.split('=', 1)[1].strip()
                        if skip_str:
                            skip_dirs = {dir.strip().lower() for dir in skip_str.split(',') if dir.strip()}
                    elif line.startswith('extras_folder_name='):
                        value = line.split('=', 1)[1].strip()
                        if value:
                            extras_folder_name = value.lower()
        except Exception:
            pass
    
    if not skip_dirs:
        skip_dirs = {
            "new folder", "nieuwe map", "extra", "extra's", "extras", "featurettes", "bonus", "bonusmaterial", "bonus_material",
            "behindthescenes", "behind_the_scenes", "deletedscenes", "deleted_scenes",
            "interviews", "makingof", "making_of", "scenes", "trailer", "trailers",
            "sample", "samples", "other", "misc", "specials", "special_features",
            "documentary", "docs", "docu", "promo", "promos", "bloopers", "outtakes"
        }
    
    if extras_folder_name:
        skip_dirs.add(extras_folder_name)
    elif 'extras' not in skip_dirs:
        skip_dirs.add('extras')
    
    return skip_dirs

def find_videos_in_directory(directory, config_path=None):
    """Find all video files in directory while respecting skip_dirs config."""
    directory = Path(directory)
    video_exts = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
    videos = []
    skip_dirs = get_skip_dirs_from_config(config_path)
    
    direct_videos = [f for f in directory.iterdir() if f.is_file() and f.suffix.lower() in video_exts]
    if direct_videos:
        videos = [str(f) for f in direct_videos]
    else:
        import os
        for dirpath, dirnames, filenames in os.walk(directory):
            dirnames[:] = [d for d in dirnames if d.lower() not in skip_dirs]
            
            for filename in filenames:
                if Path(filename).suffix.lower() in video_exts:
                    videos.append(str(Path(dirpath) / filename))
    
    return videos

def find_subtitle_files_for_video(video_path):
    """Find all subtitle files (.srt, .ass) for a specific video file."""
    video_path = Path(video_path)
    video_basename = video_path.stem
    video_dir = video_path.parent
    subtitle_files = []

    for subtitle_file in video_dir.glob(f"{video_basename}.*"):
        if subtitle_file.suffix.lower() in ('.srt', '.ass'):
            subtitle_files.append(subtitle_file)
    
    return sorted(subtitle_files)

def scan_subtitle_files_for_cleaning(directory=None, show_progress=True):
    """Scan directory for videos and their associated subtitle files for cleaning."""
    if directory is None:
        directory = get_subordinate_directory()
    else:
        directory = Path(directory)
    
    if show_progress:
        clear_and_print_ascii("                   Subtitle Cleaner Tool")
        print(f"{Fore.CYAN}Scanning for videos and subtitle files...{Style.RESET_ALL}\n")
    
    videos = find_videos_in_directory(directory)
    if not videos:
        return []

    results = []
    for video_path in videos:
        video_path = Path(video_path)
        video_name = trim_movie_name(video_path.name)
        subtitle_files = find_subtitle_files_for_video(video_path)
        
        if subtitle_files:
            results.append((str(video_path), video_name, subtitle_files))
    
    return results

def clean_up_backup_directory():
    """Clean up empty backup subdirectories and provide backup management."""
    backup_dir = get_centralized_backup_directory()
    
    if not backup_dir.exists():
        return 0, 0
    
    total_backups = 0
    empty_dirs_removed = 0
    
    for subfolder in backup_dir.iterdir():
        if subfolder.is_dir():
            backup_files = list(subfolder.glob("*"))
            if not backup_files:
                subfolder.rmdir()
                empty_dirs_removed += 1
            else:
                total_backups += len([f for f in backup_files if f.suffix in ('.srt', '.json')])
    
    return total_backups, empty_dirs_removed

def get_centralized_backup_directory():
    """Get the centralized backup directory in the Subservient data folder."""
    subservient_folder = get_subservient_folder()
    backup_dir = subservient_folder / "data" / "subtitle_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir

def get_backup_file_path(subtitle_file_path, file_type="original"):
    """Get the path for a backup file in the centralized backup directory."""
    subtitle_file = Path(subtitle_file_path)
    backup_dir = get_centralized_backup_directory()
    
    import hashlib
    absolute_parent = subtitle_file.parent.resolve()
    video_dir_hash = hashlib.md5(str(absolute_parent).encode()).hexdigest()[-8:]
    video_dir_name = absolute_parent.name
    subfolder_name = f"{video_dir_name}_{video_dir_hash}"
    
    subfolder = backup_dir / subfolder_name
    subfolder.mkdir(exist_ok=True)
    
    if file_type == "original":
        return subfolder / f"{subtitle_file.stem}_original.srt"
    elif file_type == "changes":
        return subfolder / f"{subtitle_file.stem}_changes.json"
    else:
        return subfolder / f"{subtitle_file.stem}_{file_type}"

def find_backup_file_with_fallback(subtitle_file_path, file_type="original"):
    """Find backup file, checking both new and old backup folder naming schemes."""
    subtitle_file = Path(subtitle_file_path)
    backup_dir = get_centralized_backup_directory()
    
    primary_path = get_backup_file_path(subtitle_file_path, file_type)
    if primary_path.exists():
        return primary_path
    
    import hashlib
    absolute_parent = subtitle_file.parent.resolve()
    video_dir_name = absolute_parent.name
    
    for folder in backup_dir.iterdir():
        if folder.is_dir() and folder.name.startswith(f"{video_dir_name}_"):
            if file_type == "original":
                fallback_file = folder / f"{subtitle_file.stem}_original.srt"
            elif file_type == "changes":
                fallback_file = folder / f"{subtitle_file.stem}_changes.json"
            else:
                fallback_file = folder / f"{subtitle_file.stem}_{file_type}"
            
            if fallback_file.exists():
                return fallback_file

    return primary_path

def restore_subtitle_file_completely(subtitle_file_path):
    """Restore a subtitle file completely from backup."""
    subtitle_file = Path(subtitle_file_path)
    backup_file = find_backup_file_with_fallback(subtitle_file_path, "original")
    changes_file = find_backup_file_with_fallback(subtitle_file_path, "changes")
    
    if not backup_file.exists():
        return False, f"No backup found for {subtitle_file.name}"
    
    try:
        shutil.copy2(backup_file, subtitle_file)

        if changes_file.exists():
            changes_file.unlink()
        
        return True, f"Successfully restored original: {subtitle_file.name}"
    except Exception as e:
        return False, f"Error restoring {subtitle_file.name}: {str(e)}"

def undo_specific_subtitle_changes(subtitle_file_path, change_ids):
    """Undo specific changes by restoring specific lines."""
    subtitle_file = Path(subtitle_file_path)
    backup_file = find_backup_file_with_fallback(subtitle_file_path, "original")
    changes_file = find_backup_file_with_fallback(subtitle_file_path, "changes")
    
    if not backup_file.exists() or not changes_file.exists():
        return False, f"No backup or change log found for {subtitle_file.name}"
    
    try:
        import json
        
        with open(changes_file, 'r', encoding='utf-8') as f:
            changes_data = json.load(f)
        
        with open(backup_file, 'r', encoding='utf-8') as f:
            original_lines = f.read().strip().split('\n')
        
        with open(subtitle_file, 'r', encoding='utf-8') as f:
            current_lines = f.read().strip().split('\n')
        
        lines_to_restore = []
        for change in changes_data:
            if change['id'] in change_ids:
                lines_to_restore.append({
                    'line_number': change['line_number'],
                    'content': change['content'],
                    'context_before': change['context_before'],
                    'context_after': change['context_after']
                })
        
        if not lines_to_restore:
            return False, f"No matching changes found to restore"
        
        restored_lines = current_lines.copy()
        
        for restore_info in sorted(lines_to_restore, key=lambda x: x['line_number']):
            original_line = restore_info['content']
            context_before = restore_info['context_before']
            context_after = restore_info['context_after']
            
            best_position = find_best_insertion_point(restored_lines, context_before, context_after)
            if best_position is not None:
                restored_lines.insert(best_position, original_line)
        
        with open(subtitle_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(restored_lines))
        
        remaining_changes = [change for change in changes_data if change['id'] not in change_ids]
        if remaining_changes:
            with open(changes_file, 'w', encoding='utf-8') as f:
                json.dump(remaining_changes, f, ensure_ascii=False, indent=2)
        else:
            changes_file.unlink()
        
        return True, f"Successfully restored {len(lines_to_restore)} line(s) in {subtitle_file.name}"
        
    except Exception as e:
        return False, f"Error restoring changes in {subtitle_file.name}: {str(e)}"

def find_best_insertion_point(lines, context_before, context_after):
    """Find the best position to insert a restored line based on context."""
    if not context_before and not context_after:
        return len(lines)
    
    for i, line in enumerate(lines):
        if context_before:
            before_match = all(
                i - len(context_before) + j >= 0 and 
                lines[i - len(context_before) + j].strip() == ctx.strip()
                for j, ctx in enumerate(context_before)
            )
            if before_match:
                return i
        
        if context_after:
            after_match = all(
                i + j < len(lines) and 
                lines[i + j].strip() == ctx.strip()
                for j, ctx in enumerate(context_after)
            )
            if after_match:
                return i
    
    return len(lines)

def get_subtitle_changes_for_review(subtitle_file_path):
    """Get list of changes made to a subtitle file for review."""
    changes_file = find_backup_file_with_fallback(subtitle_file_path, "changes")
    
    if not changes_file.exists():
        return []
    
    try:
        import json
        with open(changes_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def display_subtitle_restore_menu(subtitle_file_path, video_name):
    """Display menu for restoring subtitle changes."""
    subtitle_file = Path(subtitle_file_path)
    changes = get_subtitle_changes_for_review(subtitle_file_path)
    
    clean_video_name = clean_display_name(video_name)
    
    if not changes:
        clear_and_print_ascii("                   Subtitle Restore Tool")
        print(f"{Style.BRIGHT}{Fore.BLUE}[Subtitle Restore]{Style.RESET_ALL} {Fore.CYAN}› {clean_video_name} › {subtitle_file.name}{Style.RESET_ALL}\n")
        print(f"{Fore.YELLOW}No changes found to restore for this file.{Style.RESET_ALL}")
        input(f"\n{Fore.YELLOW}Press Enter to return...{Style.RESET_ALL} ")
        return
    
    while True:
        clear_and_print_ascii("                   Subtitle Restore Tool")
        print(f"{Style.BRIGHT}{Fore.BLUE}[Subtitle Restore]{Style.RESET_ALL} {Fore.CYAN}› {clean_video_name} › {subtitle_file.name}{Style.RESET_ALL}\n")
        
        print(f"{Style.BRIGHT}{Fore.LIGHTCYAN_EX}Removed Content (select to restore):{Style.RESET_ALL}")
        for change in changes:
            content = change['content']
            if len(content) > 80:
                content = content[:77] + "..."
            print(f"  {Fore.BLUE}{change['id']:2}{Style.RESET_ALL} = {Fore.LIGHTRED_EX}{content}{Style.RESET_ALL}")
        
        print(f"\n{Style.BRIGHT}{Fore.LIGHTCYAN_EX}Actions:{Style.RESET_ALL}")
        print(f"  {Fore.BLUE}{'R':>2}{Style.RESET_ALL} = {Fore.WHITE}Restore complete original file{Style.RESET_ALL}")
        print(f"  {Fore.BLUE}{'B':>2}{Style.RESET_ALL} = {Fore.LIGHTRED_EX}Return to subtitle list{Style.RESET_ALL}")
        
        choice = input(f"\n{Fore.LIGHTYELLOW_EX}Select item ID to restore, or action (R/B):{Style.RESET_ALL} ").strip().upper()
        
        if choice == 'B':
            return
        elif choice == 'R':
            success, message = restore_subtitle_file_completely(subtitle_file_path)
            print(f"\n{Fore.GREEN if success else Fore.RED}{message}{Style.RESET_ALL}")
            input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")
            if success:
                return
        else:
            try:
                change_id = int(choice)
                if any(change['id'] == change_id for change in changes):
                    success, message = undo_specific_subtitle_changes(subtitle_file_path, [change_id])
                    print(f"\n{Fore.GREEN if success else Fore.RED}{message}{Style.RESET_ALL}")
                    input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")
                    if success:
                        changes = get_subtitle_changes_for_review(subtitle_file_path)
                        if not changes:
                            print(f"\n{Fore.GREEN}All changes have been restored!{Style.RESET_ALL}")
                            input(f"\n{Fore.YELLOW}Press Enter to return...{Style.RESET_ALL} ")
                            return
                else:
                    print(f"{Fore.RED}Invalid ID. Please select a valid change ID.{Style.RESET_ALL}")
                    time.sleep(1)
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number or R/B.{Style.RESET_ALL}")
                time.sleep(1)

def display_video_list_for_cleaning(scan_results, scan_directory=None):
    """Display list of videos with subtitle files and return user choice."""
    clear_and_print_ascii("                   Subtitle Cleaner Tool")
    print(f"{Style.BRIGHT}{Fore.BLUE}[Subtitle Cleaner]{Style.RESET_ALL} {Fore.CYAN}› Video Selection{Style.RESET_ALL}\n")
    
    if not scan_results:
        print(f"{Fore.YELLOW}No videos with subtitle files found in current directory.{Style.RESET_ALL}")
        if scan_directory:
            print(f"{Fore.LIGHTBLACK_EX}Scanned directory: {scan_directory}{Style.RESET_ALL}")
        input(f"\n{Fore.YELLOW}Press Enter to return...{Style.RESET_ALL} ")
        return None
    
    def highlight_languages_in_filename(filename):
        """Highlight common language codes in subtitle filenames."""
        import re
        lang_pattern = r'\b([A-Z]{2,3})\b'
        highlighted = re.sub(lang_pattern, f'{Fore.LIGHTYELLOW_EX}\\1{Style.RESET_ALL}', filename)
        return highlighted
    
    def get_subtitle_languages(subtitle_files):
        """Extract language codes from subtitle filenames."""
        import re
        languages = set()
        for subtitle_file in subtitle_files:
            matches = re.findall(r'\.([a-zA-Z]{2,3})\.srt$', subtitle_file.name, re.IGNORECASE)
            if matches:
                languages.update([lang.upper() for lang in matches])
        return sorted(languages)
    
    print(f"{Style.BRIGHT}{Fore.LIGHTCYAN_EX}Videos:{Style.RESET_ALL}")
    for idx, (video_path, video_name, subtitle_files) in enumerate(scan_results, 1):
        subtitle_count = len(subtitle_files)
        languages = get_subtitle_languages(subtitle_files)
        lang_info = f" [{', '.join(languages)}]" if languages else ""
        
        clean_video_name = clean_display_name(video_name)
        highlighted_name = highlight_languages_in_filename(clean_video_name)
        print(f"  {Fore.BLUE}{idx:2}{Style.RESET_ALL} = {Fore.GREEN}{highlighted_name}{Style.RESET_ALL} {Fore.WHITE}({subtitle_count} subtitle file{'s' if subtitle_count != 1 else ''}){Fore.LIGHTYELLOW_EX}{lang_info}{Style.RESET_ALL}")
    
    print(f"\n{Style.BRIGHT}{Fore.LIGHTCYAN_EX}Actions:{Style.RESET_ALL}")
    print(f"  {Fore.BLUE}{len(scan_results) + 1:2}{Style.RESET_ALL} = {Fore.WHITE}Clean ALL subtitle files for all videos{Style.RESET_ALL}")
    print(f"  {Fore.BLUE}{len(scan_results) + 2:2}{Style.RESET_ALL} = {Fore.LIGHTRED_EX}Return to subtitle tools menu{Style.RESET_ALL}")
    
    while True:
        try:
            choice = input(f"\n{Fore.LIGHTYELLOW_EX}Select a video or action (1-{len(scan_results) + 2}):{Style.RESET_ALL} ").strip()
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(scan_results):
                return choice_num - 1
            elif choice_num == len(scan_results) + 1:
                return 'all'
            elif choice_num == len(scan_results) + 2:
                return 'back'
            else:
                print(f"{Fore.RED}Invalid choice. Please select 1-{len(scan_results) + 2}.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")

def display_subtitle_list_for_video(video_path, video_name, subtitle_files):
    """Display subtitle files for a specific video and return user choice."""
    clear_and_print_ascii("                   Subtitle Cleaner Tool")
    
    def highlight_languages_in_filename(filename):
        """Highlight common language codes in subtitle filenames."""
        import re
        lang_pattern = r'\b([A-Z]{2,3})\b'
        highlighted = re.sub(lang_pattern, f'{Fore.LIGHTYELLOW_EX}\\1{Style.RESET_ALL}', filename)
        return highlighted
    
    clean_video_name = clean_display_name(video_name)
    highlighted_video_name = highlight_languages_in_filename(clean_video_name)
    print(f"{Style.BRIGHT}{Fore.BLUE}[Subtitle Cleaner]{Style.RESET_ALL} {Fore.CYAN}› Video Selection › File Selection{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Selected:{Style.RESET_ALL} {Fore.GREEN}{highlighted_video_name}{Style.RESET_ALL}\n")
    
    print(f"{Style.BRIGHT}{Fore.LIGHTCYAN_EX}Subtitle Files:{Style.RESET_ALL}")
    for idx, subtitle_file in enumerate(subtitle_files, 1):
        file_size = subtitle_file.stat().st_size if subtitle_file.exists() else 0
        size_str = f"({file_size:,} bytes)" if file_size > 0 else "(empty)"
        
        highlighted_filename = highlight_languages_in_filename(subtitle_file.name)
        
        print(f"  {Fore.BLUE}{idx:2}{Style.RESET_ALL} = {Fore.GREEN}{highlighted_filename}{Style.RESET_ALL} {Fore.WHITE}{size_str}{Style.RESET_ALL}")
    
    print(f"\n{Style.BRIGHT}{Fore.LIGHTCYAN_EX}Actions:{Style.RESET_ALL}")
    print(f"  {Fore.BLUE}{len(subtitle_files) + 1:2}{Style.RESET_ALL} = {Fore.WHITE}Clean ALL subtitle files for this video{Style.RESET_ALL}")
    print(f"  {Fore.BLUE}{len(subtitle_files) + 2:2}{Style.RESET_ALL} = {Fore.LIGHTRED_EX}Return to video list{Style.RESET_ALL}")
    
    while True:
        try:
            choice = input(f"\n{Fore.LIGHTYELLOW_EX}Select a subtitle file or action (1-{len(subtitle_files) + 2}):{Style.RESET_ALL} ").strip()
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(subtitle_files):
                return choice_num - 1
            elif choice_num == len(subtitle_files) + 1:
                return 'all'
            elif choice_num == len(subtitle_files) + 2:
                return 'back'
            else:
                print(f"{Fore.RED}Invalid choice. Please select 1-{len(subtitle_files) + 2}.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")

def clean_subtitle_file_with_subcleaner(subtitle_file_path):
    """Clean a single subtitle file using the integrated Subcleaner."""
    subtitle_file = Path(subtitle_file_path)
    
    if not subtitle_file.exists():
        return False, f"File not found: {subtitle_file}"
    
    if subtitle_file.suffix.lower() != '.srt':
        return False, f"Only .srt files are supported for cleaning. File: {subtitle_file.name}"
    
    try:
        import subprocess
        import sys
        import tempfile
        import shutil
        import json
        
        subservient_folder = get_subservient_folder()
        subcleaner_path = subservient_folder / "data" / "subcleaner-master"
        subcleaner_script = subcleaner_path / "subcleaner.py"
        
        if not subcleaner_script.exists():
            return False, f"Subcleaner script not found at: {subcleaner_script}"
        
        backup_file = get_backup_file_path(subtitle_file_path, "original")
        changes_file = get_backup_file_path(subtitle_file_path, "changes")
        
        if not backup_file.exists():
            shutil.copy2(subtitle_file, backup_file)
        
        with open(subtitle_file, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        cmd = [sys.executable, str(subcleaner_script), str(subtitle_file)]
        
        result = subprocess.run(
            cmd,
            cwd=str(subcleaner_path),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            with open(subtitle_file, 'r', encoding='utf-8') as f:
                cleaned_content = f.read()
            
            original_lines = original_content.strip().split('\n')
            cleaned_lines = cleaned_content.strip().split('\n')
            
            removed_lines = []
            changes_data = []
            original_set = set(original_lines)
            cleaned_set = set(cleaned_lines)
            
            for i, line in enumerate(original_lines):
                line_stripped = line.strip()
                if line_stripped and line_stripped not in cleaned_set:
                    if not line_stripped.isdigit() and '-->' not in line_stripped:
                        change_info = {
                            "id": len(changes_data) + 1,
                            "line_number": i + 1,
                            "content": line_stripped,
                            "context_before": original_lines[max(0, i-1):i] if i > 0 else [],
                            "context_after": original_lines[i+1:min(len(original_lines), i+2)] if i < len(original_lines)-1 else []
                        }
                        changes_data.append(change_info)
                        
                        display_content = line_stripped
                        if len(display_content) > 60:
                            display_content = display_content[:57] + "..."
                        if display_content not in removed_lines:
                            removed_lines.append(display_content)
            
            if changes_data:
                with open(changes_file, 'w', encoding='utf-8') as f:
                    json.dump(changes_data, f, ensure_ascii=False, indent=2)
            
            base_message = f"Successfully cleaned: {subtitle_file.name}"
            if removed_lines:
                removed_text = f"\n{Fore.LIGHTBLACK_EX}  Removed content:{Style.RESET_ALL}"
                for i, line in enumerate(removed_lines[:5], 1):
                    removed_text += f"\n{Fore.LIGHTBLACK_EX}  {i}. {line}{Style.RESET_ALL}"
                if len(removed_lines) > 5:
                    remaining = len(removed_lines) - 5
                    removed_text += f"\n{Fore.LIGHTBLACK_EX}  ... and {remaining} more line{'s' if remaining > 1 else ''}{Style.RESET_ALL}"
                return True, base_message + removed_text
            else:
                return True, base_message + f"\n{Fore.LIGHTBLACK_EX}  No unwanted content found to remove{Style.RESET_ALL}"
        else:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            return False, f"Failed to clean {subtitle_file.name}: {error_msg}"
            
    except subprocess.TimeoutExpired:
        return False, f"Timeout while cleaning {subtitle_file.name}"
    except Exception as e:
        return False, f"Error cleaning {subtitle_file.name}: {str(e)}"

def run_subtitle_cleaning_interface():
    """Main interface for subtitle cleaning functionality."""
    while True:
        scan_directory = get_subordinate_directory()
        scan_results = scan_subtitle_files_for_cleaning(directory=scan_directory)
        
        if not scan_results:
            clear_and_print_ascii("                   Subtitle Cleaner Tool")
            print(f"{Fore.YELLOW}No videos with subtitle files found in current directory.{Style.RESET_ALL}")
            print(f"{Fore.LIGHTBLACK_EX}Scanned directory: {scan_directory}{Style.RESET_ALL}")
            print(f"{Fore.WHITE}Make sure you're in a directory with video files and their associated .srt subtitle files.{Style.RESET_ALL}")
            input(f"\n{Fore.YELLOW}Press Enter to return to subtitle tools...{Style.RESET_ALL} ")
            return
        
        choice = display_video_list_for_cleaning(scan_results, scan_directory)
        
        if choice == 'back':
            return
        elif choice == 'all':
            total_files = sum(len(subtitle_files) for _, _, subtitle_files in scan_results)
            if total_files == 0:
                print(f"{Fore.YELLOW}No subtitle files found to clean.{Style.RESET_ALL}")
                input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")
                continue
            
            clear_and_print_ascii("                   Subtitle Cleaner Tool")
            print(f"{Style.BRIGHT}{Fore.CYAN}Cleaning all subtitle files...{Style.RESET_ALL}\n")
            
            processed = 0
            successful = 0
            failed = 0
            
            for video_path, video_name, subtitle_files in scan_results:
                clean_video_name = clean_display_name(video_name)
                print(f"{Fore.CYAN}Processing: {clean_video_name}{Style.RESET_ALL}")
                for subtitle_file in subtitle_files:
                    processed += 1
                    print(f"  [{processed}/{total_files}] Cleaning {subtitle_file.name}...")
                    success, message = clean_subtitle_file_with_subcleaner(subtitle_file)
                    if success:
                        successful += 1
                        print(f"    {Fore.GREEN}✓ {message}{Style.RESET_ALL}")
                    else:
                        failed += 1
                        print(f"    {Fore.RED}✗ {message}{Style.RESET_ALL}")
                    time.sleep(0.1)
            
            print(f"\n{Style.BRIGHT}{Fore.CYAN}Cleaning completed!{Style.RESET_ALL}")
            print(f"Total files processed: {processed}")
            print(f"{Fore.GREEN}Successfully cleaned: {successful}{Style.RESET_ALL}")
            print(f"{Fore.RED}Failed: {failed}{Style.RESET_ALL}")
            input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")
            
        elif isinstance(choice, int):
            video_path, video_name, subtitle_files = scan_results[choice]
            
            while True:
                sub_choice = display_subtitle_list_for_video(Path(video_path), video_name, subtitle_files)
                
                if sub_choice == 'back':
                    break
                elif sub_choice == 'all':
                    clear_and_print_ascii("                   Subtitle Cleaner Tool")
                    clean_video_name = clean_display_name(video_name)
                    print(f"{Style.BRIGHT}{Fore.CYAN}Cleaning all subtitle files for: {Fore.YELLOW}{clean_video_name}{Style.RESET_ALL}\n")
                    
                    successful = 0
                    failed = 0
                    
                    for idx, subtitle_file in enumerate(subtitle_files, 1):
                        print(f"  [{idx}/{len(subtitle_files)}] Cleaning {subtitle_file.name}...")
                        success, message = clean_subtitle_file_with_subcleaner(subtitle_file)
                        if success:
                            successful += 1
                            print(f"    {Fore.GREEN}✓ {message}{Style.RESET_ALL}")
                        else:
                            failed += 1
                            print(f"    {Fore.RED}✗ {message}{Style.RESET_ALL}")
                        time.sleep(0.1)
                    
                    clean_video_name = clean_display_name(video_name)
                    print(f"\n{Style.BRIGHT}{Fore.CYAN}Cleaning completed for {clean_video_name}!{Style.RESET_ALL}")
                    print(f"{Fore.GREEN}Successfully cleaned: {successful}{Style.RESET_ALL}")
                    print(f"{Fore.RED}Failed: {failed}{Style.RESET_ALL}")
                    input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")
                    
                elif isinstance(sub_choice, int):
                    subtitle_file = subtitle_files[sub_choice]
                    
                    clear_and_print_ascii("                   Subtitle Cleaner Tool")
                    print(f"{Style.BRIGHT}{Fore.CYAN}Cleaning subtitle file:{Style.RESET_ALL}")
                    clean_video_name = clean_display_name(video_name)
                    print(f"Video: {Fore.YELLOW}{clean_video_name}{Style.RESET_ALL}")
                    print(f"File: {Fore.WHITE}{subtitle_file.name}{Style.RESET_ALL}\n")
                    
                    print(f"Processing...")
                    success, message = clean_subtitle_file_with_subcleaner(subtitle_file)
                    
                    if success:
                        print(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ {message}{Style.RESET_ALL}")
                    
                    input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")

def run_subtitle_restore_interface():
    """Main interface for subtitle restore functionality."""
    while True:
        scan_directory = get_subordinate_directory()
        scan_results = scan_subtitle_files_for_cleaning(directory=scan_directory, show_progress=False)
        
        if not scan_results:
            clear_and_print_ascii("                   Subtitle Restore Tool")
            print(f"{Fore.YELLOW}No videos with subtitle files found in current directory.{Style.RESET_ALL}")
            print(f"{Fore.LIGHTBLACK_EX}Scanned directory: {scan_directory}{Style.RESET_ALL}")
            input(f"\n{Fore.YELLOW}Press Enter to return to subtitle tools...{Style.RESET_ALL} ")
            return
        
        choice = display_video_list_for_restore(scan_results, scan_directory)
        
        if choice == 'back':
            return
        elif isinstance(choice, int):
            video_path, video_name, subtitle_files = scan_results[choice]
            
            while True:
                sub_choice = display_subtitle_list_for_restore(Path(video_path), video_name, subtitle_files)
                
                if sub_choice == 'back':
                    break
                elif isinstance(sub_choice, int):
                    subtitle_file = subtitle_files[sub_choice]
                    display_subtitle_restore_menu(str(subtitle_file), video_name)

def display_video_list_for_restore(scan_results, scan_directory=None):
    """Display list of videos with subtitle files for restore and return user choice."""
    clear_and_print_ascii("                   Subtitle Restore Tool")
    print(f"{Style.BRIGHT}{Fore.BLUE}[Subtitle Restore]{Style.RESET_ALL} {Fore.CYAN}› Video Selection{Style.RESET_ALL}\n")
    
    if not scan_results:
        print(f"{Fore.YELLOW}No videos with subtitle files found in current directory.{Style.RESET_ALL}")
        if scan_directory:
            print(f"{Fore.LIGHTBLACK_EX}Scanned directory: {scan_directory}{Style.RESET_ALL}")
        input(f"\n{Fore.YELLOW}Press Enter to return...{Style.RESET_ALL} ")
        return None
    
    def highlight_languages_in_filename(filename):
        """Highlight common language codes in subtitle filenames."""
        import re
        lang_pattern = r'\b([A-Z]{2,3})\b'
        highlighted = re.sub(lang_pattern, f'{Fore.LIGHTYELLOW_EX}\\1{Style.RESET_ALL}', filename)
        return highlighted
    
    def get_subtitle_languages(subtitle_files):
        """Extract language codes from subtitle filenames."""
        import re
        languages = set()
        for subtitle_file in subtitle_files:
            matches = re.findall(r'\.([a-zA-Z]{2,3})\.srt$', subtitle_file.name, re.IGNORECASE)
            if matches:
                languages.update([lang.upper() for lang in matches])
        return sorted(languages)
    
    def has_backups(subtitle_files):
        """Check if any subtitle files have backups."""
        for subtitle_file in subtitle_files:
            changes_file = find_backup_file_with_fallback(str(subtitle_file), "changes")
            backup_file = find_backup_file_with_fallback(str(subtitle_file), "original")
            
            if changes_file.exists() or backup_file.exists():
                return True
        return False
    
    print(f"{Style.BRIGHT}{Fore.LIGHTCYAN_EX}Videos:{Style.RESET_ALL}")
    for idx, (video_path, video_name, subtitle_files) in enumerate(scan_results, 1):
        subtitle_count = len(subtitle_files)
        languages = get_subtitle_languages(subtitle_files)
        lang_info = f" [{', '.join(languages)}]" if languages else ""
        
        backup_indicator = f" {Fore.GREEN}[Has Backups]{Style.RESET_ALL}" if has_backups(subtitle_files) else f" {Fore.LIGHTBLACK_EX}[No Backups]{Style.RESET_ALL}"
        
        clean_video_name = clean_display_name(video_name)
        highlighted_name = highlight_languages_in_filename(clean_video_name)
        print(f"  {Fore.BLUE}{idx:2}{Style.RESET_ALL} = {Fore.GREEN}{highlighted_name}{Style.RESET_ALL} {Fore.WHITE}({subtitle_count} subtitle file{'s' if subtitle_count != 1 else ''}){Fore.LIGHTYELLOW_EX}{lang_info}{Style.RESET_ALL}{backup_indicator}")
    
    print(f"\n{Style.BRIGHT}{Fore.LIGHTCYAN_EX}Actions:{Style.RESET_ALL}")
    print(f"  {Fore.BLUE}{len(scan_results) + 1:2}{Style.RESET_ALL} = {Fore.LIGHTRED_EX}Return to subtitle tools menu{Style.RESET_ALL}")
    
    while True:
        try:
            choice = input(f"\n{Fore.LIGHTYELLOW_EX}Select a video or action (1-{len(scan_results) + 1}):{Style.RESET_ALL} ").strip()
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(scan_results):
                return choice_num - 1
            elif choice_num == len(scan_results) + 1:
                return 'back'
            else:
                print(f"{Fore.RED}Invalid choice. Please select 1-{len(scan_results) + 1}.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")

def display_subtitle_list_for_restore(video_path, video_name, subtitle_files):
    """Display subtitle files for a specific video for restore and return user choice."""
    clear_and_print_ascii("                   Subtitle Restore Tool")
    
    def highlight_languages_in_filename(filename):
        """Highlight common language codes in subtitle filenames."""
        import re
        lang_pattern = r'\b([A-Z]{2,3})\b'
        highlighted = re.sub(lang_pattern, f'{Fore.LIGHTYELLOW_EX}\\1{Style.RESET_ALL}', filename)
        return highlighted
    
    def has_changes(subtitle_file):
        """Check if a subtitle file has changes that can be restored."""
        changes_file = find_backup_file_with_fallback(str(subtitle_file), "changes")
        return changes_file.exists()
    
    clean_video_name = clean_display_name(video_name)
    highlighted_video_name = highlight_languages_in_filename(clean_video_name)
    print(f"{Style.BRIGHT}{Fore.BLUE}[Subtitle Restore]{Style.RESET_ALL} {Fore.CYAN}› Video Selection › File Selection{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Selected:{Style.RESET_ALL} {Fore.GREEN}{highlighted_video_name}{Style.RESET_ALL}\n")
    
    print(f"{Style.BRIGHT}{Fore.LIGHTCYAN_EX}Subtitle Files:{Style.RESET_ALL}")
    restorable_files = []
    for idx, subtitle_file in enumerate(subtitle_files, 1):
        file_size = subtitle_file.stat().st_size if subtitle_file.exists() else 0
        size_str = f"({file_size:,} bytes)" if file_size > 0 else "(empty)"
        
        highlighted_filename = highlight_languages_in_filename(subtitle_file.name)
        
        if has_changes(subtitle_file):
            changes = get_subtitle_changes_for_review(str(subtitle_file))
            change_count = len(changes)
            status = f" {Fore.GREEN}[{change_count} change{'s' if change_count != 1 else ''} available]{Style.RESET_ALL}"
            restorable_files.append(idx)
        else:
            status = f" {Fore.LIGHTBLACK_EX}[No changes to restore]{Style.RESET_ALL}"
        
        print(f"  {Fore.BLUE}{idx:2}{Style.RESET_ALL} = {Fore.GREEN}{highlighted_filename}{Style.RESET_ALL} {Fore.WHITE}{size_str}{Style.RESET_ALL}{status}")
    
    if not restorable_files:
        print(f"\n{Fore.YELLOW}No subtitle files have changes that can be restored.{Style.RESET_ALL}")
        input(f"\n{Fore.YELLOW}Press Enter to return...{Style.RESET_ALL} ")
        return 'back'
    
    print(f"\n{Style.BRIGHT}{Fore.LIGHTCYAN_EX}Actions:{Style.RESET_ALL}")
    print(f"  {Fore.BLUE}{len(subtitle_files) + 1:2}{Style.RESET_ALL} = {Fore.LIGHTRED_EX}Return to video list{Style.RESET_ALL}")
    
    while True:
        try:
            choice = input(f"\n{Fore.LIGHTYELLOW_EX}Select a subtitle file or action (1-{len(subtitle_files) + 1}):{Style.RESET_ALL} ").strip()
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(subtitle_files):
                if choice_num in restorable_files:
                    return choice_num - 1
                else:
                    print(f"{Fore.RED}No changes available to restore for this file.{Style.RESET_ALL}")
            elif choice_num == len(subtitle_files) + 1:
                return 'back'
            else:
                print(f"{Fore.RED}Invalid choice. Please select 1-{len(subtitle_files) + 1}.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")

def detect_series_structure(local_path, check_parents=True):
    """Simplified content type detection for clear movie vs series identification.
    
    This function determines:
    1. Content type: 'movie' or 'series' (based on actual content, not config)
    2. Quantity: 'single' or 'multiple' 
    3. Works hierarchically when subordinate.py is placed at any level
    
    Args:
        local_path: Path to check
        check_parents: If False, only checks current directory (useful for movie mode)
    
    Returns simple, reliable detection for config validation and processing type.
    """
    import os
    import re
    from pathlib import Path
    
    local_path = Path(local_path)
    video_exts = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
    skip_dirs = get_skip_dirs_from_config()
    
    def should_skip_dir(dirname):
        """Check if directory should be skipped."""
        return any(skip_pattern.lower() in dirname.lower() for skip_pattern in skip_dirs)
    
    def count_videos_in_folder(folder_path):
        """Count video files directly in folder."""
        try:
            return sum(1 for item in folder_path.iterdir() 
                      if item.is_file() and item.suffix.lower() in video_exts)
        except (PermissionError, OSError):
            return 0
    
    def has_series_indicators(folder_path):
        """Check if folder contains series indicators."""
        folder_path = Path(folder_path)
        
        # 1. Season folders
        season_folders = []
        series_folders = []
        
        for item in folder_path.iterdir():
            if item.is_dir() and not should_skip_dir(item.name):
                videos_in_folder = count_videos_in_folder(item)
                
                # Check if this is a season folder
                if re.search(r'(?i)(?:season|seizoen|saison|staffel|temporada)\s*\d+|s\d+', item.name):
                    if videos_in_folder > 0:
                        season_folders.append(item)
                
                # Check if this folder contains series-like content (3+ videos or SxxExx patterns)
                elif videos_in_folder >= 3:
                    series_folders.append(item)
                elif videos_in_folder >= 2:
                    # Only count as series if we find SxxExx patterns
                    video_files = [f for f in item.iterdir() 
                                 if f.is_file() and f.suffix.lower() in video_exts]
                    sxxexx_count = sum(1 for f in video_files 
                                     if re.search(r'[Ss]\d{1,2}[Ee]\d{1,2}', f.name))
                    if sxxexx_count >= videos_in_folder * 0.5:
                        series_folders.append(item)
        
        # If we found season folders, it's definitely series
        if season_folders:
            return True, 'season_folders'
        
        # If we found series folders, it's series
        if series_folders:
            return True, 'multiple_episodes'
        
        # 2. Check if we have multiple folders but they all look like movie folders (1 video each)
        all_folders = [item for item in folder_path.iterdir() 
                      if item.is_dir() and not should_skip_dir(item.name)]
        
        if len(all_folders) >= 2:
            # Check if all folders have exactly 1 video (movie-like) vs 3+ videos (series-like)
            movie_like_folders = 0
            series_like_folders = 0
            
            for folder in all_folders:
                videos = count_videos_in_folder(folder)
                if videos == 1:
                    movie_like_folders += 1
                elif videos >= 3:
                    series_like_folders += 1
            
            # If we only have movie-like folders (1 video each), don't treat as series
            if movie_like_folders >= 2 and series_like_folders == 0:
                return False, 'movie_folders'
        
        # 3. SxxExx patterns in current folder
        video_files = [f for f in folder_path.iterdir() 
                      if f.is_file() and f.suffix.lower() in video_exts]
        
        if len(video_files) >= 2:
            sxxexx_count = sum(1 for f in video_files 
                             if re.search(r'[Ss]\d{1,2}[Ee]\d{1,2}', f.name))
            if sxxexx_count >= max(2, len(video_files) * 0.5):
                return True, 'episode_naming'
        
        # 4. Multiple episodes in current folder (3+ videos)
        if len(video_files) >= 3:
            return True, 'multiple_episodes'
        
        return False, 'none'
    
    def detect_content_type_hierarchical(start_path):
        """Detect content type by checking current and parent directories."""
        current_path = Path(start_path)
        
        # Check current directory first
        has_series, reason = has_series_indicators(current_path)
        if has_series:
            return 'series', reason, str(current_path)
        
        # If current directory looks like a season folder, check parent
        current_name = current_path.name
        if re.search(r'(?i)(?:season|seizoen|saison|staffel|temporada)\s*\d+|s\d+', current_name):
            parent_path = current_path.parent
            if parent_path != current_path and parent_path.exists():
                has_series, reason = has_series_indicators(parent_path)
                if has_series:
                    return 'series', reason, str(parent_path)
        
        # Check parent directories up to 2 levels (only if check_parents=True)
        if check_parents:
            for level in range(1, 3):
                parent_path = current_path
                for _ in range(level):
                    parent_path = parent_path.parent
                    if parent_path == current_path:
                        break
                
                if parent_path.exists() and parent_path != current_path:
                    has_series, reason = has_series_indicators(parent_path)
                    if has_series:
                        return 'series', reason, str(parent_path)
        
        # No series indicators found - assume movie content
        return 'movie', 'no_series_indicators', str(current_path)
    
    def detect_quantity(content_type, detection_path, detection_reason):
        """Detect if content is single or multiple."""
        detection_path = Path(detection_path)
        
        if content_type == 'series':
            if detection_reason == 'season_folders':
                # Single series with season structure
                return 'single'
            elif detection_reason in ['episode_naming', 'multiple_episodes']:
                # Check if this is one series with episodes or multiple series folders
                series_folders = []
                for item in detection_path.iterdir():
                    if item.is_dir() and not should_skip_dir(item.name):
                        videos = count_videos_in_folder(item)
                        # Count folder as series if it has 3+ videos OR SxxExx patterns
                        if videos >= 3:
                            series_folders.append(item)
                        elif videos >= 2:
                            # Check for SxxExx patterns
                            video_files = [f for f in item.iterdir() 
                                         if f.is_file() and f.suffix.lower() in video_exts]
                            sxxexx_count = sum(1 for f in video_files 
                                             if re.search(r'[Ss]\d{1,2}[Ee]\d{1,2}', f.name))
                            if sxxexx_count >= videos * 0.5:  # At least half have SxxExx patterns
                                series_folders.append(item)
                
                return 'single' if len(series_folders) <= 1 else 'multiple'
        
        else:  # movie content
            # Count direct videos and video folders
            direct_videos = count_videos_in_folder(detection_path)
            video_folders = sum(1 for item in detection_path.iterdir()
                              if item.is_dir() and not should_skip_dir(item.name)
                              and count_videos_in_folder(item) > 0)
            
            total_content = direct_videos + video_folders
            return 'single' if total_content <= 1 else 'multiple'
    
    # Perform detection
    content_type, detection_reason, detection_path = detect_content_type_hierarchical(local_path)
    quantity = detect_quantity(content_type, detection_path, detection_reason)
    
    # Legacy format for compatibility
    if content_type == 'series':
        series_detected = True
        if quantity == 'single':
            series_type = 'single'
        else:
            series_type = 'multiple'
    else:
        series_detected = False
        series_type = 'none'
    
    # Simple series names for display (keep it simple)
    if series_detected:
        series_names = [os.path.basename(detection_path)]
    else:
        series_names = []
    
    # Legacy compatibility: Add folder_analysis for backward compatibility with subordinate.py
    # Count actual folders with video content
    video_exts = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
    
    def count_videos_in_folder(folder_path):
        try:
            return sum(1 for item in folder_path.iterdir() 
                      if item.is_file() and item.suffix.lower() in video_exts)
        except (PermissionError, OSError):
            return 0
    
    # Count folders with video content
    video_folders_count = 0
    folders_with_videos = []
    
    def count_video_folders_recursive(path, max_depth=2, current_depth=0):
        """Count folders that contain videos, recursively up to max_depth."""
        count = 0
        try:
            for item in path.iterdir():
                if not item.is_dir() or should_skip_dir(item.name):
                    continue
                
                # Check if this folder has direct videos
                videos_in_folder = count_videos_in_folder(item)
                if videos_in_folder > 0:
                    count += 1
                    folders_with_videos.append(item)
                elif current_depth < max_depth:
                    # If no direct videos but we can go deeper, recurse
                    count += count_video_folders_recursive(item, max_depth, current_depth + 1)
        except (PermissionError, OSError):
            pass
        return count
    
    video_folders_count = count_video_folders_recursive(local_path)
    
    # If no folders with videos found, check for direct videos
    if video_folders_count == 0:
        direct_videos = count_videos_in_folder(local_path)
        if direct_videos > 0:
            video_folders_count = 1
            folders_with_videos = [local_path]
    
    legacy_folder_analysis = {
        'total_folders': video_folders_count,
        'video_folders': video_folders_count,
        'folders_info': folders_with_videos,
        'all_series': {}
    }
    
    if series_detected:
        legacy_folder_analysis['all_series'][os.path.basename(detection_path)] = {
            'path': detection_path,
            'episode_count': 5,  # Placeholder - not critical for display
            'seasons': 1 if quantity == 'single' else 2
        }
    
    return {
        'series_detected': series_detected,
        'series_type': series_type,
        'series_names': series_names,
        'content_type': content_type,
        'quantity': quantity,
        'detection_reason': detection_reason,
        'detection_path': detection_path,
        # Legacy compatibility
        'folder_analysis': legacy_folder_analysis
    }

def detect_potential_series_in_video_mode(local_path, config_path=None):
    """Simple detection for series content when in movie mode.
    
    In movie mode, we only check the current directory and don't look at parent
    directories to avoid false positives from series content in parent folders.
    
    Returns basic information about whether series-like content is detected
    to trigger config mismatch warning.
    """
    # In movie mode, only check current directory - don't check parents
    result = detect_series_structure(local_path, check_parents=False)
    
    return {
        'has_potential_series': result['series_detected'],
        'content_type': result['content_type'],
        'detection_reason': result.get('detection_reason', 'unknown')
    }

def needs_sxxexx_normalization(filename):
    """Check if filename has SxxExx pattern that needs normalization to S##E## format."""
    import re
    # Check for patterns that need fixing: S1E01, S01E1, S1E1
    improperly_formatted_patterns = [
        r'\b[Ss](\d{1})[Ee](\d{1,3})\b',     # S1E01, S1E1, S1E001
        r'\b[Ss](\d{2,})[Ee](\d{1})\b',      # S01E1, S001E1
    ]
    
    for pattern in improperly_formatted_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            return True
    return False

def normalize_sxxexx_in_filename(filepath):
    """Normalize SxxExx patterns in filename to proper S##E## format.
    
    Returns:
        tuple: (success: bool, new_filepath: Path or None, was_renamed: bool)
    """
    import re
    from pathlib import Path
    
    try:
        filepath = Path(filepath)
        original_name = filepath.name
        
        def replace_sxxexx(match):
            season = int(match.group(1))
            episode = int(match.group(2))
            return f"S{season:02d}E{episode:02d}"
        
        # Normalize SxxExx patterns
        new_name = re.sub(r'[Ss](\d{1,2})[Ee](\d{1,3})', replace_sxxexx, original_name, flags=re.IGNORECASE)
        
        if new_name != original_name:
            new_filepath = filepath.parent / new_name
            
            # Check if target file already exists
            if new_filepath.exists():
                return (False, None, False)  # Cannot rename - target exists
            
            # Perform the rename
            filepath.rename(new_filepath)
            return (True, new_filepath, True)
        else:
            return (True, filepath, False)  # No rename needed
            
    except Exception as e:
        return (False, None, False)

def has_strict_series_naming_pattern(name):
    """Check if folder or file name has STRICT series/season/episode naming patterns.
    
    This function uses STRICT checking - only properly formatted SxxExx 
    (with leading zeros) are considered valid series patterns.
    """
    import re
    # Note: digit-terminated alternatives use a negative lookahead (?!\d) instead of a
    # trailing \b, since \b fails to match when the digits are immediately followed by
    # another word character (e.g. an underscore, as in "S06E001_Piegato..."). The
    # lookahead only guards against matching a partial number, not the following text.
    series_patterns = [
        # Season patterns
        r'\b[Ss](\d{2,})(?!\d)',              # S01, S001, s01 (at least 2 digits)
        r'\b[Ss]eason\s*(\d+)\b',            # Season 1, season 01
        r'\b[Ss]érie\s*(\d+)\b',             # Série 1 (French)
        r'\b[Ss]eizoen\s*(\d+)\b',           # Seizoen 1 (Dutch)
        r'\b[Ss]aison\s*(\d+)\b',            # Saison 1 (French)
        r'\b[Ss]taffel\s*(\d+)\b',           # Staffel 1 (German)
        r'\b[Tt]emporada\s*(\d+)\b',         # Temporada 1 (Spanish)
        r'\b[Ss]tagione\s*(\d+)\b',          # Stagione 1 (Italian)
        
        # Episode patterns
        r'\b[Ee](\d{2,})(?!\d)',              # E01, E001, e01 (at least 2 digits)
        r'\b[Ee]pisode\s*(\d+)\b',           # Episode 1, episode 01
        r'\bEp\s*(\d+)\b',                   # Ep 1, Ep01
        
        # Combined patterns - STRICT: only accept properly formatted SxxExx
        r'\b(\d+)[xX](\d{2,})(?!\d)',         # 1x01, 1X01 (episode must have 2+ digits)
        r'\b[Ss](\d{2,})[Ee](\d{2,})(?!\d)',  # STRICT: S01E01, S001E001 (both must have 2+ digits)
        r'\b[Ss](\d{2,})\s*[Ee](\d{2,})(?!\d)', # STRICT: S01 E01, S001 E001
        
        # Alternative patterns
        r'\b[Pp]art\s*(\d+)\b',              # Part 1
        r'\b[Vv]ol(?:ume)?\s*(\d+)\b',       # Vol 1, Volume 1
    ]
    
    for pattern in series_patterns:
        if re.search(pattern, name, re.IGNORECASE):
            return True
    return False

# Word-based season/episode names in several languages, used by the loose detector below
_SEASON_WORD_PATTERN = r'(?:season|seizoen|saison|staffel|temporada|stagione|s[ée]rie)'
_EPISODE_WORD_PATTERN = r'(?:episode|aflevering|folge|epis[oó]dio|ep)'

def _extract_season_from_folder_name(folder_name):
    """Try to extract a season number from a folder name like 'Season 1', 'Seizoen 02', 'S01'."""
    import re
    if not folder_name:
        return None
    match = re.search(rf'{_SEASON_WORD_PATTERN}\.?\s*#?(\d{{1,4}})', folder_name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r'\b[Ss](\d{1,4})\b', folder_name)
    if match:
        return int(match.group(1))
    return None

def detect_episode_info_loose(filename, folder_name=None):
    """Try to detect a (season, episode) pair from a filename using a wide range of common,
    non-strict naming conventions, falling back to the parent folder name for the season
    number when only an episode number is present in the filename.

    Recognizes (among others):
    - Word-based season/episode names in several languages, e.g. 'Season 1 Episode 01',
      'Seizoen 1 Aflevering 3', 'Saison 1 Épisode 2', 'Staffel 1 Folge 4'
    - '1x01' / '01x001' style codes
    - Loosely formatted SxxExx, e.g. 'S1E1', 'S1 E01', 'S01.E01'
    - Episode-only notations (e.g. 'Episode 5', 'Ep 05') combined with a season number
      taken from the parent folder name (e.g. a 'Season 1' folder)
    - Leading numeric episode indices (e.g. '01 - Title.mkv') combined with a parent
      folder season number

    Returns a (season, episode) tuple of ints, or (None, None) if nothing was recognized.
    """
    import re
    name = filename

    # 1. Word-based 'Season <n> ... Episode <n>' in any supported language/order of words
    match = re.search(
        rf'{_SEASON_WORD_PATTERN}\.?\s*#?(\d{{1,4}}).{{0,20}}?{_EPISODE_WORD_PATTERN}\.?\s*#?(\d{{1,4}})',
        name, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))

    # 2. '1x01' / '01x001' style codes
    match = re.search(r'\b(\d{1,2})[xX](\d{1,3})\b', name)
    if match:
        return int(match.group(1)), int(match.group(2))

    # 3. Loosely formatted SxxExx (any digit width, optional separators): S1E1, S01 E1, S01.E01
    match = re.search(r'\b[Ss](\d{1,4})\s*[.\-_ ]?\s*[Ee](\d{1,4})\b', name)
    if match:
        return int(match.group(1)), int(match.group(2))

    # 4. Episode-only word notation -> season number comes from the parent folder name
    match = re.search(rf'{_EPISODE_WORD_PATTERN}\.?\s*#?(\d{{1,4}})', name, re.IGNORECASE)
    if match:
        season = _extract_season_from_folder_name(folder_name)
        if season is not None:
            return season, int(match.group(1))

    # 5. Leading numeric episode index (e.g. '01 - Title', '01. Title') -> season from folder name
    match = re.match(r'^\s*(\d{1,3})\s*[-._]\s*\S', name)
    if match:
        season = _extract_season_from_folder_name(folder_name)
        if season is not None:
            return season, int(match.group(1))

    return (None, None)

def attempt_rename_problematic_series_file(file_path, folder_name=None):
    """Try to auto-rename a single problematic series video file by detecting its
    season/episode number (see detect_episode_info_loose) and appending a normalized
    'SxxExx' code to the end of the original filename, keeping the original name intact.

    Returns a dict:
        success (bool): whether a rename was performed
        recognized (bool): whether season/episode info could be detected at all
        old_name (str), new_name (str or None), error (str or None)
    """
    from pathlib import Path
    file_path = Path(file_path)
    season, episode = detect_episode_info_loose(file_path.stem, folder_name)
    if season is None or episode is None:
        return {'success': False, 'recognized': False, 'old_name': file_path.name, 'new_name': None, 'error': None}

    sxxexx = f"S{season:02d}E{episode:02d}"
    new_stem = file_path.stem.rstrip(' .-_') + f" {sxxexx}"
    new_name = f"{new_stem}{file_path.suffix}"
    new_path = file_path.parent / new_name

    if new_path.exists() and new_path != file_path:
        return {'success': False, 'recognized': True, 'old_name': file_path.name, 'new_name': new_name, 'error': 'target_exists'}

    try:
        file_path.rename(new_path)
        return {'success': True, 'recognized': True, 'old_name': file_path.name, 'new_name': new_name, 'error': None}
    except Exception as e:
        return {'success': False, 'recognized': True, 'old_name': file_path.name, 'new_name': new_name, 'error': str(e)}

def auto_rename_series_naming_issues(local_path, problematic_files):
    """Attempt to automatically fix a list of problematic series video files (as returned
    by validate_series_naming) by detecting season/episode info from common filename
    and parent-folder conventions and renaming files accordingly.

    Returns a dict:
        renamed (list of {'old': relative path, 'new': relative path}),
        still_problematic (list of the original problematic_file entries that could not be fixed),
        renamed_count (int), still_problematic_count (int)
    """
    from pathlib import Path
    local_path = Path(local_path)
    renamed = []
    still_problematic = []

    for info in problematic_files:
        full_path = local_path / info['path']
        result = attempt_rename_problematic_series_file(full_path, folder_name=info.get('folder'))
        if result['success']:
            new_relative = str(Path(info['path']).parent / result['new_name'])
            renamed.append({'old': info['path'], 'new': new_relative})
        else:
            still_problematic.append(info)

    return {
        'renamed': renamed,
        'still_problematic': still_problematic,
        'renamed_count': len(renamed),
        'still_problematic_count': len(still_problematic),
    }

def detect_potential_movies_in_series_mode(local_path, config_path=None):
    """Detect folders with single videos or non-series naming in series mode.
    
    This function scans all directories for folders containing single video files
    or folders without season/episode naming patterns, which might indicate 
    movies mixed with series content.
    Used to warn users when series_mode=true but movie-like content is detected.
    
    Returns a dictionary with potential movie folder information.
    """
    from pathlib import Path
    
    # Ensure we have a Path object
    local_path = Path(local_path)
    
    video_exts = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
    skip_dirs = get_skip_dirs_from_config(config_path)
    
    def count_videos_in_folder(folder_path):
        """Count video files directly in folder (not recursively)."""
        try:
            return sum(1 for item in folder_path.iterdir() 
                      if item.is_file() and item.suffix.lower() in video_exts)
        except (PermissionError, OSError):
            return 0
    
    def should_skip_folder(folder_name):
        """Check if folder should be skipped based on skip_dirs config."""
        return folder_name.lower() in skip_dirs
    
    def get_video_files_in_folder(folder_path):
        """Get list of video files in folder."""
        try:
            return [item for item in folder_path.iterdir() 
                   if item.is_file() and item.suffix.lower() in video_exts]
        except (PermissionError, OSError):
            return []
    
    def scan_directory_recursive(directory, max_depth=3, current_depth=0):
        """Recursively scan directory for folders with movie-like content."""
        potential_movies = []
        
        if current_depth >= max_depth:
            return potential_movies
        
        try:
            for item in directory.iterdir():
                if not item.is_dir():
                    continue
                
                # Skip folders in skip_dirs config
                if should_skip_folder(item.name):
                    continue
                
                # Get videos in this folder
                video_files = get_video_files_in_folder(item)
                video_count = len(video_files)
                
                # Check if this looks like a movie folder
                is_potential_movie = False
                
                # Case 1: Folder with exactly 1 video file
                if video_count == 1:
                    video_file = video_files[0]
                    
                    # FIRST: Try to auto-rename if it needs SxxExx normalization
                    if needs_sxxexx_normalization(video_file.name):
                        success, new_path, was_renamed = normalize_sxxexx_in_filename(video_file)
                        if was_renamed and success:
                            video_file = new_path  # Update reference
                    
                    # Check if neither folder nor file has series naming (after potential rename)
                    if not has_strict_series_naming_pattern(item.name) and not has_strict_series_naming_pattern(video_file.stem):
                        is_potential_movie = True
                
                # Case 2: Folder with multiple videos but inconsistent or missing series naming patterns
                elif video_count > 1:
                    # FIRST: Try to auto-rename files that need SxxExx normalization
                    auto_renamed_files = []
                    current_video_files = get_video_files_in_folder(item)  # Refresh list
                    
                    for video_file in current_video_files:
                        if needs_sxxexx_normalization(video_file.name):
                            success, new_path, was_renamed = normalize_sxxexx_in_filename(video_file)
                            if was_renamed and success:
                                auto_renamed_files.append({
                                    'old_name': video_file.name,
                                    'new_name': new_path.name
                                })
                    
                    # Refresh video files list after potential renames
                    video_files = get_video_files_in_folder(item)
                    video_count = len(video_files)
                    
                    # Check folder name
                    folder_has_series_pattern = has_strict_series_naming_pattern(item.name)
                    # Check how many video files have series patterns (after auto-rename)
                    files_with_series_pattern = [vf for vf in video_files if has_strict_series_naming_pattern(vf.stem)]
                    files_have_series_pattern_count = len(files_with_series_pattern)
                    
                    # Case 2a: No folder pattern and NO files have series patterns = likely movie collection
                    if not folder_has_series_pattern and files_have_series_pattern_count == 0:
                        is_potential_movie = True
                    # Case 2b: Some files have series patterns but not all = inconsistent naming (also problematic)
                    elif files_have_series_pattern_count > 0 and files_have_series_pattern_count < video_count:
                        is_potential_movie = True
                
                if is_potential_movie:
                    potential_movies.append({
                        'path': item,
                        'name': item.name,
                        'video_count': video_count,
                        'relative_path': str(item.relative_to(local_path)),
                        'video_files': [vf.name for vf in video_files]
                    })
                
                # Continue recursively scanning subdirectories
                if current_depth < max_depth - 1:
                    sub_potential = scan_directory_recursive(item, max_depth, current_depth + 1)
                    potential_movies.extend(sub_potential)
        
        except (PermissionError, OSError):
            pass
        
        return potential_movies
    
    # Start scanning from the local path
    potential_movie_folders = scan_directory_recursive(local_path)
    
    # ALSO check the current folder itself (not just subfolders)
    current_folder_videos = get_video_files_in_folder(local_path)
    if len(current_folder_videos) > 0:
        
        # FIRST: Try to auto-rename files that need SxxExx normalization in current folder
        for video_file in current_folder_videos:
            if needs_sxxexx_normalization(video_file.name):
                success, new_path, was_renamed = normalize_sxxexx_in_filename(video_file)
                # Note: We don't track renames here for simplicity, just do them
        
        # Refresh video files list after potential renames
        current_folder_videos = get_video_files_in_folder(local_path)
        
        # Check if current folder looks like a movie folder or has inconsistent naming
        folder_has_series_pattern = has_strict_series_naming_pattern(local_path.name)
        files_with_series_pattern = [vf for vf in current_folder_videos if has_strict_series_naming_pattern(vf.stem)]
        files_have_series_pattern_count = len(files_with_series_pattern)
        
        # Case 1: Single file without series pattern in current folder
        if len(current_folder_videos) == 1 and not folder_has_series_pattern and files_have_series_pattern_count == 0:
            potential_movie_folders.append({
                'path': local_path,
                'name': local_path.name,
                'video_count': len(current_folder_videos),
                'relative_path': '.',  # Current folder
                'video_files': [vf.name for vf in current_folder_videos]
            })
        # Case 2: Multiple files - either no series patterns or inconsistent patterns
        elif len(current_folder_videos) > 1:
            if (not folder_has_series_pattern and files_have_series_pattern_count == 0) or \
               (files_have_series_pattern_count > 0 and files_have_series_pattern_count < len(current_folder_videos)):
                potential_movie_folders.append({
                    'path': local_path,
                    'name': local_path.name,
                    'video_count': len(current_folder_videos),
                    'relative_path': '.',  # Current folder
                    'video_files': [vf.name for vf in current_folder_videos]
                })
    
    # Sort by folder name for consistent display
    potential_movie_folders.sort(key=lambda x: x['name'].lower())
    
    return {
        'has_potential_movies': len(potential_movie_folders) > 0,
        'potential_movie_count': len(potential_movie_folders),
        'potential_movie_folders': potential_movie_folders,
        'total_videos_in_potential_movies': sum(folder['video_count'] for folder in potential_movie_folders)
    }

def run_subtitle_tools_menu():
    """Main subtitle tools menu interface."""
    while True:
        clear_and_print_ascii("                   Subtitle Tools")
        print(f"{Style.BRIGHT}{Fore.BLUE}[Subtitle Tools]{Style.RESET_ALL} {Fore.CYAN}› Main Menu{Style.RESET_ALL}\n")
        
        print(f"{Style.BRIGHT}{Fore.LIGHTCYAN_EX}Available Tools:{Style.RESET_ALL}")
        print(f"  {Fore.BLUE}{'1':>2}{Style.RESET_ALL} = {Fore.WHITE}Clean Subtitle Files{Style.RESET_ALL} {Fore.LIGHTBLACK_EX}(Remove unwanted content from .srt files){Style.RESET_ALL}")
        print(f"  {Fore.BLUE}{'2':>2}{Style.RESET_ALL} = {Fore.WHITE}Restore Subtitle Changes{Style.RESET_ALL} {Fore.LIGHTBLACK_EX}(Undo cleaning changes){Style.RESET_ALL}")
        
        print(f"\n{Style.BRIGHT}{Fore.LIGHTCYAN_EX}Actions:{Style.RESET_ALL}")
        print(f"  {Fore.BLUE}{'B':>2}{Style.RESET_ALL} = {Fore.LIGHTRED_EX}Return to main menu{Style.RESET_ALL}")
        
        choice = input(f"\n{Fore.LIGHTYELLOW_EX}Select a tool or action (1/2/B):{Style.RESET_ALL} ").strip().upper()
        
        if choice == '1':
            run_subtitle_cleaning_interface()
        elif choice == '2':
            run_subtitle_restore_interface()
        elif choice == 'B':
            return
        else:
            print(f"{Fore.RED}Invalid choice. Please select 1, 2, or B.{Style.RESET_ALL}")
            time.sleep(1)

def validate_config_mode_match(local_path, series_mode_config, config_path=None):
    """Validate if the configured series mode matches the detected content type.
    
    Returns information about config mismatch for warning purposes.
    """
    result = detect_series_structure(local_path)
    
    detected_is_series = result['series_detected']
    config_is_series = series_mode_config
    
    # Determine if there's a mismatch
    has_mismatch = detected_is_series != config_is_series
    
    return {
        'has_mismatch': has_mismatch,
        'detected_content': 'series' if detected_is_series else 'movie',
        'config_mode': 'series' if config_is_series else 'movie',
        'should_warn': has_mismatch,
        'recommendation': 'series' if detected_is_series else 'movie'
    }

def validate_series_naming(local_path, config_path=None):
    """Validate that all series files have proper SxxExx naming patterns.
    
    Scans all video files in series folders and checks for proper season/episode naming.
    Returns information about files that need manual naming intervention.
    
    Returns a dictionary with validation results and problematic files.
    """
    from pathlib import Path
    import re
    
    local_path = Path(local_path)
    video_exts = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
    skip_dirs = get_skip_dirs_from_config(config_path)
    
    def should_skip_dir(dirname):
        return any(skip_pattern.lower() in dirname.lower() for skip_pattern in skip_dirs)
    
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
    
    def scan_series_folder(folder_path, relative_path=""):
        """Scan a folder for video files and check their naming."""
        problematic_files = []
        good_files = []
        
        try:
            for item in folder_path.iterdir():
                if item.is_file() and item.suffix.lower() in video_exts:
                    rel_file_path = str(Path(relative_path) / item.name)
                    
                    if has_sxxexx_pattern(item.name):
                        normalized = normalize_sxxexx(item.name)
                        good_files.append({
                            'file': item.name,
                            'path': rel_file_path,
                            'current_pattern': normalized,
                            'needs_rename': normalized != item.name
                        })
                    else:
                        problematic_files.append({
                            'file': item.name,
                            'path': rel_file_path,
                            'folder': folder_path.name
                        })
                
                elif item.is_dir() and not should_skip_dir(item.name):
                    # Recursively check subdirectories (for nested season structures)
                    sub_rel_path = str(Path(relative_path) / item.name) if relative_path else item.name
                    sub_prob, sub_good = scan_series_folder(item, sub_rel_path)
                    problematic_files.extend(sub_prob)
                    good_files.extend(sub_good)
        
        except (PermissionError, OSError):
            pass
        
        return problematic_files, good_files
    
    # Only validate if we're in series mode
    series_info = detect_series_structure(local_path)
    if not series_info['series_detected']:
        return {
            'validation_needed': False,
            'reason': 'not_series_content'
        }
    
    all_problematic_files = []
    all_good_files = []
    
    # Scan all series folders
    try:
        for item in local_path.iterdir():
            if item.is_dir() and not should_skip_dir(item.name):
                prob_files, good_files = scan_series_folder(item, item.name)
                all_problematic_files.extend(prob_files)
                all_good_files.extend(good_files)
    except (PermissionError, OSError):
        pass
    
    # Also check for video files directly in the current folder (subfolders were
    # already scanned recursively above, so only look at files here to avoid duplicates)
    try:
        for item in local_path.iterdir():
            if item.is_file() and item.suffix.lower() in video_exts:
                if has_sxxexx_pattern(item.name):
                    normalized = normalize_sxxexx(item.name)
                    all_good_files.append({
                        'file': item.name,
                        'path': item.name,
                        'current_pattern': normalized,
                        'needs_rename': normalized != item.name
                    })
                else:
                    all_problematic_files.append({
                        'file': item.name,
                        'path': item.name,
                        'folder': local_path.name
                    })
    except (PermissionError, OSError):
        pass
    
    return {
        'validation_needed': True,
        'has_issues': len(all_problematic_files) > 0,
        'problematic_files': all_problematic_files,
        'good_files': all_good_files,
        'total_files_checked': len(all_problematic_files) + len(all_good_files),
        'files_needing_rename': len([f for f in all_good_files if f.get('needs_rename', False)])
    }


def make_drift_metadata_key(filename: str) -> str:
    """Extract a stable matching key from a DRIFT/FAILED subtitle filename.

    Works for:  166587.en.number1.S06E02.srt
                166587.en.number1.S06E02.DRIFT.srt
                166587.en.number1.S06E02.FAILED.srt
    Returns: '166587.en.number1'  (download_count.lang.numberN)
    """
    parts = filename.split('.')
    if len(parts) >= 3:
        return f"{parts[0]}.{parts[1]}.{parts[2]}"
    return filename


def save_drift_subtitle_metadata(metadata_path: str, sub_path: str, quality_score: float,
                                  correlation_score: float, bonus: int, offset: float,
                                  rejected: bool = False):
    """Save sync quality metadata for a batch DRIFT candidate.

    Writes to the file at metadata_path (full path).
    Key = download_count.lang.numberN, so it matches both DRIFT and FAILED filenames.
    """
    key = make_drift_metadata_key(os.path.basename(sub_path))
    metadata_file = metadata_path
    existing = {}
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split('|')
                    if len(parts) >= 5:
                        existing[parts[0]] = line
        except Exception:
            pass
    rejected_flag = '1' if rejected else '0'
    existing[key] = f"{key}|{quality_score:.1f}|{correlation_score:.1f}|{bonus}|{offset:.4f}|{rejected_flag}"
    try:
        with open(metadata_file, 'w', encoding='utf-8') as f:
            f.write("# Drift/Failed subtitle metadata - auto-generated by Subservient\n")
            for entry_line in existing.values():
                f.write(entry_line + "\n")
    except Exception:
        pass


def load_drift_subtitle_metadata(metadata_path: str) -> dict:
    """Load sync quality metadata from the file at metadata_path (full path).

    Returns dict mapping key (download_count.lang.numberN) to:
        {'quality': float, 'correlation': float, 'bonus': int, 'offset': float, 'rejected': bool}
    """
    metadata_file = metadata_path
    result = {}
    if not os.path.exists(metadata_file):
        return result
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('|')
                if len(parts) >= 5:
                    result[parts[0]] = {
                        'quality': float(parts[1]),
                        'correlation': float(parts[2]),
                        'bonus': int(parts[3]),
                        'offset': float(parts[4]),
                        'rejected': len(parts) >= 6 and parts[5] == '1'
                    }
    except Exception:
        pass
    return result


def clean_drift_subtitle_metadata(metadata_path: str, keys_to_remove: set):
    """Remove specific entries from the metadata file at metadata_path (full path).

    Deletes the file entirely if no entries remain.
    """
    metadata_file = metadata_path
    if not os.path.exists(metadata_file):
        return
    try:
        remaining = {}
        with open(metadata_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('|')
                if parts[0] not in keys_to_remove:
                    remaining[parts[0]] = line
        if not remaining:
            os.remove(metadata_file)
        else:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                f.write("# Drift/Failed subtitle metadata - auto-generated by Subservient\n")
                for entry_line in remaining.values():
                    f.write(entry_line + "\n")
    except Exception:
        pass
