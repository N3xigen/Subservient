from platformdirs import user_config_dir
from pathlib import Path
from colorama import Fore, Style
import os
import subprocess
import time
import re

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

def clear_and_print_ascii(banner_line):
    """Clear screen and display ASCII art with banner."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Style.BRIGHT}{Fore.BLUE}{ASCII_ART}{Style.RESET_ALL}\n")
    print(f"{Style.BRIGHT}{banner_line}{Style.RESET_ALL}\n")

def map_lang_3to2(code):
    """Convert 3-letter language code to 2-letter equivalent."""
    code = code.lower()
    return LANG_3TO2_MAP.get(code, code)

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
        log_func(f"\n{Fore.LIGHTYELLOW_EX}{Style.BRIGHT}INFO{Style.RESET_ALL}: If all your movies show {Fore.GREEN}external .SRT files{Style.RESET_ALL} or you're satisfied with {Fore.YELLOW}internal subtitles{Style.RESET_ALL}, you're all set!\n")
        
        log_func(f"{Fore.CYAN}However, if some movies only have internal subtitles or missing subtitles, here's what you should know:{Style.RESET_ALL}")
        log_func(f"• Movies with {Fore.LIGHTBLACK_EX}long silences{Style.RESET_ALL}, {Fore.LIGHTBLACK_EX}background noise{Style.RESET_ALL}, or {Fore.LIGHTBLACK_EX}non-English dialogue{Style.RESET_ALL} can be challenging for AI synchronization.")
        log_func(f"• The AI may incorrectly flag perfectly good subtitles as {Fore.LIGHTRED_EX}'out of sync'{Style.RESET_ALL} (false positives).")
        log_func("")
        
        log_func(f"{Fore.YELLOW}These rare cases are easy to spot:{Style.RESET_ALL} {Style.BRIGHT}ALL{Style.RESET_ALL} subtitles for a movie show as {Fore.YELLOW}'internal only'{Style.RESET_ALL} or {Fore.RED}'missing'{Style.RESET_ALL} for {Style.BRIGHT}ALL{Style.RESET_ALL} languages.")
        log_func(f"When you see this pattern, it's usually the AI being overly cautious, not a real sync problem!")
        log_func("")
        
        log_func(f"{Fore.CYAN}If any movie shows only internal subtitles or missing subtitles, then delete those subtitles and:{Style.RESET_ALL}")
        log_func(f"{Fore.LIGHTCYAN_EX}1.{Style.RESET_ALL} Run {Fore.WHITE}acquisition.py{Style.RESET_ALL} to download fresh subtitles")
        log_func(f"{Fore.LIGHTCYAN_EX}2.{Style.RESET_ALL} Exit before {Fore.WHITE}synchronisation.py{Style.RESET_ALL} starts")
        log_func(f"{Fore.LIGHTCYAN_EX}3.{Style.RESET_ALL} Manually check the downloaded subtitles - they're often {Fore.GREEN}perfectly synced already{Style.RESET_ALL}!")
        log_func(f"{Fore.LIGHTCYAN_EX}4.{Style.RESET_ALL} Simply rename them to match your video (e.g., {Fore.WHITE}'MovieName.en.srt'{Style.RESET_ALL})")
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
