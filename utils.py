from platformdirs import user_config_dir
from pathlib import Path
from colorama import Fore, Style
import os
import subprocess
import time
import re
import shutil

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

def scan_subtitle_coverage(videos, languages, show_progress=True, logger_func=None, sync_tag_func=None):
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
            for ext in ('.srt', '.ass'):
                expected_path = video_dir / f"{video_basename}.{lang}{ext}"
                if expected_path.exists():
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

def display_coverage_results(coverage_results, languages, banner_line=None, return_to_menu=True, logger_func=None, sync_tag_func=None):
    """Display formatted subtitle coverage report with statistics."""
    log_func = logger_func if logger_func else print
    tag_func = sync_tag_func if sync_tag_func else lambda: ""
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
    if not sync_tag_func:
        pass
    else:
        time.sleep(1)
        log_func(f"\n{Style.BRIGHT}INFO:{Style.RESET_ALL} If all your movies show {Fore.GREEN}external .SRT files{Style.RESET_ALL} or you're satisfied with {Fore.YELLOW}internal subtitles{Style.RESET_ALL}, you're all set!\n")
        
        log_func(f"{Fore.LIGHTYELLOW_EX}However, if some movies only have internal subtitles or missing subtitles, here's what you should know:{Style.RESET_ALL}")
        log_func(f"• Movies with long silences, background noise, or non-English dialogue can be challenging for AI synchronization.")
        log_func(f"• The AI may incorrectly flag perfectly good subtitles as 'out of sync' (false positives).")
        log_func("")
        
        log_func(f"These rare cases are easy to spot: ALL subtitles for a movie show as 'internal only' or 'missing' for ALL languages.")
        log_func(f"When you see this pattern, it's usually the AI being overly cautious, not a real sync problem!")
        log_func("")
        
        log_func(f"{Fore.LIGHTYELLOW_EX}If any movie shows only internal subtitles or missing subtitles, then delete those subtitles and:{Style.RESET_ALL}")
        log_func(f"{Fore.CYAN}1.{Style.RESET_ALL} Run acquisition.py to download fresh subtitles")
        log_func(f"{Fore.CYAN}2.{Style.RESET_ALL} Exit before synchronisation.py starts")
        log_func(f"{Fore.CYAN}3.{Style.RESET_ALL} Manually check the downloaded subtitles - they're often perfectly synced already!")
        log_func(f"{Fore.CYAN}4.{Style.RESET_ALL} Simply rename them to match your video (e.g., 'MovieName.en.srt')")
        log_func("")
        
        log_func(f"{Fore.GREEN}By recognizing this pattern, even the last few rare subtitles that Subservient misinterprets won't slip past you!{Style.RESET_ALL}")
    
    if return_to_menu:
        input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")

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
