import os, re, subprocess, tempfile, shutil, time, sys, stat, datetime, threading, math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

def is_running_in_docker():
    """Check if running inside a Docker container."""
    try:
        if os.path.exists('/.dockerenv'):
            return True
        with open('/proc/1/cgroup', 'r') as f:
            return 'docker' in f.read()
    except:
        return False

def read_subtitle_metadata(video_folder: Path, video_name: str, lang: str):
    """Read metadata about subtitle acquisition. Returns True if IMDb match, False otherwise."""
    # Get the main Subservient folder (where synchronisation.py is located)
    main_folder = Path(__file__).parent.resolve()
    metadata_file = main_folder / ".subtitle_metadata.txt"
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

def get_skipped_movies_from_config():
    """Read skipped movies from config file."""
    CONFIG_PATH = Path(__file__).parent.resolve() / '.config'
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

def add_skipped_movie_language_to_config(movie_path: Path, language: str):
    """Add a movie-language combination to skipped_movies in config."""
    CONFIG_PATH = Path(__file__).parent.resolve() / '.config'
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
    
    # Write to config
    write_runtime_blocks_to_config_sync(skipped_entries=skipped_entries)

def write_runtime_blocks_to_config_sync(token=None, skipped_entries=None):
    """Write runtime configuration blocks to config file."""
    CONFIG_PATH = Path(__file__).parent.resolve() / '.config'
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
        out.append(line)
        if line.strip().lower() == RUNTIME_TAG.lower():
            break
    
    runtime_blocks = []
    runtime_blocks.append('')
    runtime_blocks.append(SEP)
    runtime_blocks.append(TOKEN_COMMENT)
    runtime_blocks.append(TOKEN_TAG)
    
    if token is None:
        # Try to get existing token from config
        for line in lines:
            if line.strip() and not line.startswith('[') and not line.startswith('--') and 'JWT' not in line:
                idx = lines.index(line)
                if idx > 0 and '[token]' in lines[idx-1]:
                    token = line.strip()
                    break
    
    if token:
        runtime_blocks.append(token)
    else:
        runtime_blocks.append('')
    
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
    out.extend(runtime_blocks)
    
    CONFIG_PATH.write_text('\n'.join(out), encoding='utf-8')

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

def synchronize_subtitle_with_ffsubsync(video_path, subtitle_path, output_path, progress_callback=None):
    """Synchronize subtitle file with video using ffsubsync and return success status with offset and correlation score.
    
    Args:
        progress_callback: Optional ProgressBarAnimator instance for real-time updates
    """
    try:
        if not os.path.exists(video_path):
            print_and_log(f"{sync_tag()} {Fore.RED}Video file not found: {video_path}{Style.RESET_ALL}")
            return False, 0.0, 0.0
        if not os.path.exists(subtitle_path):
            print_and_log(f"{sync_tag()} {Fore.RED}Subtitle file not found: {subtitle_path}{Style.RESET_ALL}")
            return False, 0.0, 0.0
        # Don't print "Synchronizing..." message - progress bar shows this
        cmd = [
            'ffsubsync', video_path, 
            '-i', subtitle_path, 
            '-o', output_path,
            '--vad', FFSUBSYNC_VAD
        ]
        try:
            # Use Popen to read output in real-time
            import re
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            
            stderr_lines = []
            correlation_score = 0.0
            
            # Read stderr line by line for progress updates
            for line in process.stderr:
                stderr_lines.append(line)
                
                # Look for percentage indicators in ffsubsync output
                # Common patterns: "50%", "Progress: 75%", etc.
                percent_match = re.search(r'(\d+)%', line)
                if percent_match and progress_callback:
                    try:
                        percent = float(percent_match.group(1))
                        # Update progress bar with actual percentage
                        progress_callback.progress = min(100, percent)  # Cap at 95% until complete
                        progress_callback._draw_bar(progress_callback.progress)
                    except (ValueError, AttributeError):
                        pass
            
            # Wait for process to complete
            process.wait(timeout=600)
            stderr_output = ''.join(stderr_lines)
            
            if process.returncode == 0 and os.path.exists(output_path):
                offset_seconds = calculate_subtitle_offset(subtitle_path, output_path)
                
                # Extract correlation score from stderr output
                patterns = [
                    r'score[:\s=]+([0-9.-]+)',  # "score: 123456.78" or "score=-12345"
                    r'correlation[:\s=]+([0-9.-]+)',  # "correlation: 0.1234"
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, stderr_output, re.IGNORECASE)
                    if match:
                        try:
                            correlation_score = float(match.group(1))
                            break
                        except (ValueError, IndexError):
                            continue
                
                # Format correlation score for display
                if correlation_score > 0.0:
                    score_display = f" | Score: {Fore.LIGHTYELLOW_EX}{correlation_score:.0f}{Style.RESET_ALL}"
                    if correlation_score >= 200000:
                        quality = f"{Fore.GREEN}Excellent{Style.RESET_ALL}"
                    elif correlation_score >= 100000:
                        quality = f"{Fore.GREEN}Good{Style.RESET_ALL}"
                    elif correlation_score >= 50000:
                        quality = f"{Fore.YELLOW}Moderate{Style.RESET_ALL}"
                    else:
                        quality = f"{Fore.YELLOW}Low{Style.RESET_ALL}"
                    score_display += f" ({quality})"
                elif correlation_score < 0:
                    score_display = f" | Score: {Fore.RED}{correlation_score:.0f} (Poor Match){Style.RESET_ALL}"
                else:
                    score_display = f" | Score: {Fore.LIGHTBLACK_EX}N/A{Style.RESET_ALL}"
                
                print_and_log(f"{sync_tag()} {Fore.GREEN}Synchronization successful! Offset: {offset_seconds:.3f}s{score_display}{Style.RESET_ALL}")
                return True, offset_seconds, correlation_score
            else:
                print_and_log(f"{sync_tag()} {Fore.RED}FFSubSync failed with return code {process.returncode}{Style.RESET_ALL}")
                return False, 0.0, 0.0
        except Exception as proc_error:
            print_and_log(f"{sync_tag()} {Fore.RED}Process error during synchronization: {str(proc_error)}{Style.RESET_ALL}")
            return False, 0.0, 0.0
    except subprocess.TimeoutExpired:
        print_and_log(f"{sync_tag()} {Fore.RED}FFSubSync timed out after 10 minutes{Style.RESET_ALL}")
        return False, 0.0, 0.0
    except Exception as e:
        print_and_log(f"{sync_tag()} {Fore.RED}Error during synchronization: {str(e)}{Style.RESET_ALL}")
        return False, 0.0, 0.0

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
                   get_skip_dirs_from_config, make_drift_metadata_key,
                   save_drift_subtitle_metadata, load_drift_subtitle_metadata,
                   clean_drift_subtitle_metadata)

init(autoreset=True)

class ProgressBarAnimator:
    """Animated progress bar that goes from 0-100% and updates every 0.25s."""
    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = None
        self.current_candidate = 0
        self.total_candidates = 0
        self.subtitle_name = ""
        self.status = "Syncing"
        self.progress = 0.0
        self.start_time = None
        self.estimated_duration = 30.0  # Estimate 30 seconds per sync
        self.bar_start_line = 0  # Track where progress bar starts
        self.first_draw = True  # Track if this is the first draw
        self.info_text = "Synchronizing text to speech..."  # Info text to show above bar
        self.completing = False  # Flag to indicate we're in final completion phase
        
    def start(self, current, total, subtitle_name, status="Audio analysis"):
        """Start animating progress bar (legacy method for compatibility)."""
        self.current_candidate = current
        self.total_candidates = total
        self.subtitle_name = subtitle_name[:48] if len(subtitle_name) > 48 else subtitle_name
        self.status = status
        self.progress = 0.0
        self.start_time = time.time()
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()
    
    def stop(self, force_complete=True):
        """Stop the animation and smoothly complete to 100%."""
        if force_complete:
            # Signal to start smooth completion from current progress to 100%
            self.completing = True
            # Wait a bit for smooth completion
            if self.thread:
                self.thread.join(timeout=1.5)
        
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=0.5)
    
    def _draw_bar(self, progress):
        """Draw the progress bar at a specific progress level."""
        bar_length = 30
        filled_length = int(bar_length * progress / 100.0)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        if self.first_draw:
            # First time - write info text and progress bar
            self.first_draw = False
            sys.stdout.write(f'{Fore.LIGHTYELLOW_EX}{self.info_text}{Style.RESET_ALL}\n')
            sys.stdout.write(f'{Fore.LIGHTCYAN_EX}[{self.current_candidate}/{self.total_candidates}]{Style.RESET_ALL} [{Fore.CYAN}{bar}{Style.RESET_ALL}] {progress:>5.1f}% | {self.subtitle_name}\n')
        else:
            # Subsequent times - move up 2 lines (info + bar) and overwrite both
            sys.stdout.write('\033[F\033[F')
            sys.stdout.write(f'\033[K{Fore.LIGHTYELLOW_EX}{self.info_text}{Style.RESET_ALL}\n')
            sys.stdout.write(f'\033[K{Fore.LIGHTCYAN_EX}[{self.current_candidate}/{self.total_candidates}]{Style.RESET_ALL} [{Fore.CYAN}{bar}{Style.RESET_ALL}] {progress:>5.1f}% | {self.subtitle_name}\n')
        sys.stdout.flush()
    
    def _animate(self):
        """Animation loop - only for fallback when no real progress is available."""
        completion_start_progress = None
        completion_start_time = None
        last_update = 0.0
        
        while not self.stop_event.is_set():
            # Check if we're in completion phase
            if self.completing and completion_start_progress is None:
                # Start smooth completion from current progress to 100%
                completion_start_progress = self.progress
                completion_start_time = time.time()
            
            if self.completing and completion_start_progress is not None:
                # Smooth linear interpolation to 100% over ~1 second
                elapsed_completion = time.time() - completion_start_time
                completion_duration = 1.0  # Take 1 second to reach 100%
                
                if elapsed_completion >= completion_duration:
                    self.progress = 100.0
                    self._draw_bar(self.progress)
                    break  # Exit after reaching 100%
                else:
                    # Linear interpolation from start progress to 100%
                    progress_range = 100.0 - completion_start_progress
                    self.progress = completion_start_progress + (progress_range * (elapsed_completion / completion_duration))
            else:
                # Only update fallback progress if we haven't had a real update recently
                # This allows real progress to take precedence
                if self.progress < 95.0:
                    elapsed = time.time() - self.start_time
                    # Slow fallback progress - only used if ffsubsync doesn't report progress
                    fallback_progress = min(85.0, 85.0 * (1 - math.exp(-elapsed / 10.0)))
                    # Only use fallback if it's higher than current (don't go backwards)
                    if fallback_progress > self.progress:
                        self.progress = fallback_progress
            
            self._draw_bar(self.progress)
            time.sleep(0.25)
    
    def draw_initial(self):
        """Draw initial empty progress bar (2 lines)."""
        bar_length = 30
        bar = '░' * bar_length
        sys.stdout.write(f'[{self.current_candidate}/{self.total_candidates}] {self.subtitle_name:<48}\n')
        sys.stdout.write(f'[{Fore.CYAN}{bar}{Style.RESET_ALL}]   0.0% | {self.status:<15}\n')
        sys.stdout.flush()

# Create global progress animator
progress_animator = ProgressBarAnimator()

def print_progress_bar(current, total, subtitle_name, status="Syncing"):
    """Legacy function for backward compatibility."""
    bar_length = 30
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    percent = 100 * (current / float(total))
    
    sys.stdout.write(f'\r{Fore.LIGHTBLUE_EX}┌{"─" * 65}┐{Style.RESET_ALL}\n')
    sys.stdout.write(f'{Fore.LIGHTBLUE_EX}│{Style.RESET_ALL} [{current}/{total}] {subtitle_name:<50} {Fore.LIGHTBLUE_EX}│{Style.RESET_ALL}\n')
    sys.stdout.write(f'{Fore.LIGHTBLUE_EX}│{Style.RESET_ALL} [{Fore.CYAN}{bar}{Style.RESET_ALL}] {percent:>3.0f}% | {status:<20} {Fore.LIGHTBLUE_EX}│{Style.RESET_ALL}\n')
    sys.stdout.write(f'{Fore.LIGHTBLUE_EX}└{"─" * 65}┘{Style.RESET_ALL}')
    sys.stdout.flush()

def print_rankings_table(rankings, final=False, clear_lines=0):
    """Print current rankings table below the progress bar."""
    if not rankings:
        return
    
    print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  SMART SYNC RESULTS - Highest scoring subtitle will be used{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")
    
    # Tuples may be 5-element (rank, name, off, sc, status) or 6-element with bonus
    def _unpack(e):
        return (e[0], e[1], e[2], e[3], e[4], e[5] if len(e) > 5 else 0)
    
    valid_rankings  = [_unpack(e) for e in rankings if e[4] != "rejected"]
    rejected_rankings = [(None, e[1], e[2], e[3], e[4], e[5] if len(e) > 5 else 0)
                         for e in rankings if e[4] == "rejected"]
    
    for rank, sub_name, offset, score, status, bonus in valid_rankings + rejected_rankings:
        if rank == 1:
            rank_display = f"{Fore.YELLOW}#{rank}{Style.RESET_ALL}"  # Gold #1
            color = Fore.YELLOW
        elif rank is not None:
            rank_display = f"{Fore.WHITE}#{rank}{Style.RESET_ALL}"
            color = Fore.WHITE
        else:
            rank_display = f"{Fore.RED}  X{Style.RESET_ALL}"  # Rejected (red X)
            color = Fore.WHITE
        
        offset_str = f"{offset:.3f}s" if offset is not None else "N/A"
        score_str = f"{score:,.0f}" if score is not None else "N/A"
        
        # Calculate quality score and build bonus display
        if offset is not None and score is not None:
            quality_score = calculate_quality_score(offset, score)
            quality_tier, tier_color = get_quality_tier(quality_score)
            if bonus > 0:
                quality_numeric = f"{quality_score}+{bonus}"
                quality_display = f"{tier_color}{quality_score}{Fore.LIGHTMAGENTA_EX}+{bonus}{tier_color}/100{Style.RESET_ALL}"
            else:
                quality_numeric = f"{quality_score}"
                quality_display = f"{tier_color}{quality_score}{tier_color}/100{Style.RESET_ALL}"
        else:
            quality_numeric = "N/A"
            quality_display = f"{Fore.WHITE}N/A{Style.RESET_ALL}"
            quality_tier = "N/A"
            tier_color = Fore.WHITE
        # Truncate subtitle name if too long (reduced to fit quality column)
        display_name = sub_name[:23] if len(sub_name) <= 23 else sub_name[:20] + "..."
        
        # Pad quality field to consistent width (6 chars for numeric part)
        padding = " " * max(0, 6 - len(quality_numeric))
        
        # Display all entries the same way (rejected ones will naturally show red due to Bad tier)
        print(f"  {rank_display} {color}{display_name:<23}{Style.RESET_ALL} {Fore.CYAN}{offset_str:>7}{Style.RESET_ALL} {Fore.GREEN}{score_str:>9}{Style.RESET_ALL} {padding}{quality_display} {tier_color}{quality_tier}{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")


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

def sync_mode_tag():
    """Return formatted synchronisation tag with mode indicator for sync-specific messages."""
    mode_tag = f"{Style.DIM}{Fore.YELLOW}[Smart Sync]{Style.RESET_ALL}" if SMART_SYNC else f"{Style.DIM}{Fore.YELLOW}[First Match]{Style.RESET_ALL}"
    return f"{Style.BRIGHT}{Fore.BLUE}[Synchronisation]{Style.RESET_ALL} {mode_tag}"

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
    if any(f.endswith((".mkv", ".mp4", ".avi")) for f in files):
        videos.extend(os.path.join(root, f) for f in files if f.endswith((".mkv", ".mp4", ".avi")))
        dirs[:] = []

config_values = read_config_as_dict(CONFIG_PATH)
pause_seconds = int(float(config_values.get('pause_seconds', 3)))
MOVIES_ACCEPT_SCORE = float(config_values.get('movies_accept_score', config_values.get('auto_accept_score', 70)))
SERIES_ACCEPT_SCORE = float(config_values.get('series_accept_score', config_values.get('auto_accept_score', 80)))
AUTO_REJECT_SCORE = float(config_values.get('auto_reject_score', 20))
ACCEPT_OFFSET_THRESHOLD = float(config_values.get('accept_offset_threshold', 0.05))
REJECT_OFFSET_THRESHOLD = float(config_values.get('reject_offset_threshold', 60.0))
PRESERVE_FORCED_SUBTITLES = config_values.get('preserve_forced_subtitles', 'false').lower() in ('true', '1', 'yes', 'on')
PRESERVE_UNWANTED_SUBTITLES = config_values.get('preserve_unwanted_subtitles', 'false').lower() in ('true', '1', 'yes', 'on')
SMART_SYNC = config_values.get('smart_sync', 'false').lower() in ('true', '1', 'yes', 'on')
QUALITY_SCORE_SKIP = float(config_values.get('quality_score_skip', 90))
REQUIRE_IMDB_VALIDATION = config_values.get('require_imdb_validation', 'false').lower() in ('true', '1', 'yes', 'on')
COUNT_REJECTED = config_values.get('count_rejected', 'false').lower() in ('true', '1', 'yes', 'on')
MAX_SEARCH_RESULTS = int(config_values.get('max_search_results', 5))
drift_marked = False

# Track rejected subtitle counts per (movie_name, lang) for auto-accept decisions
rejected_subtitle_counts = {}

# Auto-accepted movies tracking file
AUTO_ACCEPTED_FILE = os.path.join(script_dir, 'auto_accepted_movies.txt')

# Central drift/failed metadata file (in Subservient folder, not the video folder)
DRIFT_METADATA_FILE = os.path.join(script_dir, '.drifted_and_failed_subtitles.txt')

# ============================================================================
# QUALITY SCORING SYSTEM
# ============================================================================

def find_video_by_name(movie_name, video_list):
    """Find a video file by matching movie name.
    
    Searches through video list to find a match based on movie name.
    Handles various naming patterns and tries to find the best match.
    
    Returns: (video_path, video_name) tuple or (None, None) if not found
    """
    # Clean the search name
    search_name = movie_name.strip()
    
    # Try exact matches first
    for video_path in video_list:
        video_name = os.path.basename(video_path)
        video_basename = os.path.splitext(video_name)[0]
        
        # Exact match (ignoring extension)
        if video_basename == search_name:
            return (video_path, video_name)
        
        # Check if search name is contained in video name
        if search_name in video_name:
            return (video_path, video_name)
    
    # Try fuzzy matching by removing common patterns
    search_normalized = re.sub(r'\s*\([^\)]*\)\s*', '', search_name).strip()
    search_normalized = re.sub(r'\s+', ' ', search_normalized).lower()
    
    best_match = None
    best_score = 0
    
    for video_path in video_list:
        video_name = os.path.basename(video_path)
        video_basename = os.path.splitext(video_name)[0]
        video_normalized = re.sub(r'\s*\([^\)]*\)\s*', '', video_basename).strip()
        video_normalized = re.sub(r'\s+', ' ', video_normalized).lower()
        
        # Calculate similarity score (simple word matching)
        search_words = set(search_normalized.split())
        video_words = set(video_normalized.split())
        
        if search_words and video_words:
            common_words = search_words & video_words
            score = len(common_words) / max(len(search_words), len(video_words))
            
            if score > best_score and score > 0.5:  # At least 50% match
                best_score = score
                best_match = (video_path, video_name)
    
    return best_match if best_match else (None, None)

def calculate_offset_score(offset_seconds):
    """Calculate offset score (max 70 points) based on offset correction."""
    abs_offset = abs(offset_seconds)
    
    if abs_offset < 0.05:
        return 70
    elif abs_offset < 0.1:
        return 70 - ((abs_offset - 0.05) / 0.05) * 5  # lerp 70→65
    elif abs_offset < 0.2:
        return 65 - ((abs_offset - 0.1) / 0.1) * 5    # lerp 65→60
    elif abs_offset < 0.5:
        return 60 - ((abs_offset - 0.2) / 0.3) * 10   # lerp 60→50
    elif abs_offset < 1.0:
        return 50 - ((abs_offset - 0.5) / 0.5) * 10   # lerp 50→40
    elif abs_offset < 2.0:
        return 40 - ((abs_offset - 1.0) / 1.0) * 20   # lerp 40→20
    elif abs_offset < 15.0:
        return 20 - ((abs_offset - 2.0) / 13.0) * 10  # lerp 20→10 (gradual decline)
    elif abs_offset < 30.0:
        return 10 - ((abs_offset - 15.0) / 15.0) * 10 # lerp 10→0 (final decline)
    else:
        return 0

def calculate_correlation_score(correlation):
    """Calculate correlation score (max 30 points) based on ffsubsync correlation."""
    if correlation < 30000:
        return 0
    elif correlation < 100000:
        return (correlation - 30000) / 70000 * 15     # lerp 0→15
    elif correlation < 200000:
        return 15 + ((correlation - 100000) / 100000) * 7  # lerp 15→22
    elif correlation < 300000:
        return 22 + ((correlation - 200000) / 100000) * 8  # lerp 22→30
    else:
        return 30  # cap at 30

def calculate_quality_score(offset_seconds, correlation):
    """Calculate combined quality score (max 100 points)."""
    offset_points = calculate_offset_score(offset_seconds)
    correlation_points = calculate_correlation_score(correlation)
    return math.floor(offset_points + correlation_points)

def calculate_batch_bonuses(candidates):
    """Calculate per-candidate confidence bonus for smart sync batch ranking.

    Input: list of (sub_name, offset, correlation, base_quality)
    Returns: list of (sub_name, offset, correlation, base_quality, bonus)

    The candidate with the highest correlation in the batch gets +10 pts.
    Candidates within 5% of the top correlation get +5 pts.
    Bonus is capped so that base_quality + bonus does not exceed 100.
    """
    if not candidates:
        return []
    max_conf = max(c[2] for c in candidates)
    result = []
    for sub_name, offset, correlation, base_quality in candidates:
        if correlation >= max_conf * 0.9999:
            bonus = min(10, 100 - base_quality)
        elif correlation >= max_conf * 0.95:
            bonus = min(5, 100 - base_quality)
        else:
            bonus = 0
        result.append((sub_name, offset, correlation, base_quality, bonus))
    return result

def _build_display_rankings(current_rankings, rejected_subs, show_bonuses=False):
    """Build display_rankings list for print_rankings_table.
    show_bonuses: if True, calculate and show confidence bonuses (post-batch only).
    Returns list of (rank, name, offset, correlation, status, bonus) tuples.
    """
    if show_bonuses:
        bonused = calculate_batch_bonuses(current_rankings)
    else:
        bonused = [(name, off, sc, base_qual, 0) for name, off, sc, base_qual in current_rankings]
    sorted_bonused = sorted(bonused, key=lambda x: x[3] + x[4], reverse=True)
    display = []
    for rank, (name, off, sc, base_qual, bonus) in enumerate(sorted_bonused, 1):
        display.append((rank, name, off, sc, "valid", bonus))
    for name, off, sc in rejected_subs:
        display.append((None, name, off, sc, "rejected", 0))
    return display

def get_quality_tier(score):
    """Get quality tier and color based on score."""
    if score >= 90:
        return "Excellent", Fore.LIGHTCYAN_EX
    elif score >= 70:
        return "Good", Fore.GREEN
    elif score >= 40:
        return "Decent", Fore.LIGHTYELLOW_EX
    elif score >= 20:
        return "Poor", Fore.YELLOW
    else:
        return "Bad", Fore.RED

# FFsubsync accuracy mapping (2 reliable levels only)
FFSUBSYNC_ACCURACY_MAP = {
    1: 'webrtc',               # Fast - Pure audio detection
    2: 'subs_then_webrtc'      # Smart - Subtitle hints + audio (RECOMMENDED)
}
ffsubsync_accuracy = int(config_values.get('ffsubsync_accuracy', 2))
FFSUBSYNC_VAD = FFSUBSYNC_ACCURACY_MAP.get(ffsubsync_accuracy, 'subs_then_webrtc')

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

def extract_sxxexx_code(name: str) -> str | None:
    """Extract season/episode code from filename."""
    import re
    # Episode allows up to 3 digits (e.g. "S06E001") so it isn't truncated to just the first 2 digits
    match = re.search(r"[sS](\d{1,2})[eE](\d{1,3})", name)
    return f"S{int(match.group(1)):02d}E{int(match.group(2)):02d}" if match else None


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

# Resolve AUTO_ACCEPT_SCORE based on mode (movies vs series)
AUTO_ACCEPT_SCORE = SERIES_ACCEPT_SCORE if SERIES_MODE else MOVIES_ACCEPT_SCORE

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
def print_video_header(video_name, idx, total, lang=None):
    """Print formatted header for current video being processed."""
    lang_str = f" [{Fore.LIGHTRED_EX}{lang.upper()}{Style.RESET_ALL}]" if lang else ""
    bar = f"{Fore.CYAN}[{idx}/{total}]{Style.RESET_ALL}  {Fore.LIGHTYELLOW_EX}{os.path.basename(video_name).upper()}{Style.RESET_ALL}{lang_str}"
    print(bar.ljust(79), end='\n', flush=True)

def update_subtitle_metadata_rejected_counts():
    """Update .subtitle_metadata.txt with rejected counts from smart sync."""
    metadata_file = os.path.join(script_dir, ".subtitle_metadata.txt")
    if not os.path.exists(metadata_file):
        return
    
    try:
        # Read existing entries
        entries = {}
        with open(metadata_file, 'r', encoding='utf-8') as f:
            for line in f:
                if '|' in line:
                    parts = line.strip().split('|')
                    if len(parts) >= 3:
                        video_name, lang, imdb_status = parts[0], parts[1], parts[2]
                        rejected = parts[3] if len(parts) >= 4 else "0"
                        entries[(video_name, lang)] = (imdb_status, rejected)
        
        # Update with rejected counts from smart sync
        for (video_name, lang), count in rejected_subtitle_counts.items():
            if (video_name, lang) in entries:
                imdb_status, _ = entries[(video_name, lang)]
                entries[(video_name, lang)] = (imdb_status, str(count))
        
        # Write back
        with open(metadata_file, 'w', encoding='utf-8') as f:
            for (video_name, lang), (imdb_status, rejected) in entries.items():
                f.write(f"{video_name}|{lang}|{imdb_status}|{rejected}\n")
    except Exception as e:
        print_and_log(f"{sync_tag()} {Fore.YELLOW}Warning: Could not update rejected counts: {e}{Style.RESET_ALL}")

def remove_metadata_entry(video_filename, title):
    """Remove specific entry from .subtitle_metadata.txt based on video filename and title.
    
    Args:
        video_filename: Full video filename (e.g., "Kung Fu Panda 2 [2011].mkv")
        title: Title with language tag (e.g., "Kung Fu Panda 2 [2011] [EN]")
    """
    metadata_file = os.path.join(script_dir, ".subtitle_metadata.txt")
    if not os.path.exists(metadata_file):
        return
    
    try:
        # Extract video basename (without extension)
        video_basename = os.path.splitext(video_filename)[0]
        
        # Extract language from title (e.g., "Movie [EN]" -> "en")
        lang_match = re.search(r'\[([A-Z]{2})\]$', title)
        if not lang_match:
            return
        lang = lang_match.group(1).lower()
        
        # Read existing entries
        entries = {}
        with open(metadata_file, 'r', encoding='utf-8') as f:
            for line in f:
                if '|' in line:
                    parts = line.strip().split('|')
                    if len(parts) >= 3:
                        video_name, entry_lang, imdb_status = parts[0], parts[1], parts[2]
                        rejected = parts[3] if len(parts) >= 4 else "0"
                        entries[(video_name, entry_lang)] = (imdb_status, rejected)
        
        # Remove the specific entry
        key = (video_basename, lang)
        if key in entries:
            del entries[key]
            
            # Write back remaining entries
            if entries:
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    for (video_name, entry_lang), (imdb_status, rejected) in entries.items():
                        f.write(f"{video_name}|{entry_lang}|{imdb_status}|{rejected}\n")
            else:
                # No entries left, remove the file
                os.remove(metadata_file)
    except Exception as e:
        print_and_log(f"{sync_tag()} {Fore.YELLOW}Warning: Could not remove metadata entry: {e}{Style.RESET_ALL}")

def cleanup_duplicates_in_folder(folder: str, languages):
    """Remove redundant numbered subtitle files when correct ones exist."""
    try:
        files = os.listdir(folder)
    except Exception:
        return
    
    for f in files:
        if f.endswith(('.mkv', '.mp4', '.avi')):
            base_name = os.path.splitext(f)[0]
            
            # Extract series code if in series mode
            sxxexx_code = None
            if SERIES_MODE:
                sxxexx_code = extract_sxxexx_code(f)
            
            for lang in languages:
                # Determine correct filename patterns based on mode and content
                correct_patterns = []
                
                if SERIES_MODE and sxxexx_code:
                    # Series mode with SxxExx code
                    if sxxexx_code.lower() in base_name.lower():
                        # Video already has SxxExx in name
                        correct_patterns.append(f"{base_name}.{lang}.srt")
                    else:
                        # Video doesn't have SxxExx
                        correct_patterns.append(f"{base_name}.{sxxexx_code}.{lang}.srt")
                else:
                    # Movie mode or series without clear SxxExx
                    correct_patterns.append(f"{base_name}.{lang}.srt")
                
                # Check if any correct pattern exists
                correct_exists = any(os.path.exists(os.path.join(folder, pattern)) for pattern in correct_patterns)
                
                if correct_exists:
                    # Clean up numbered files - multiple patterns:
                    # Pattern 1: filename.number1.lang.srt (old pattern)
                    # Pattern 2: 1234.lang.number1.S01E01.srt (acquisition pattern)
                    for g in files:
                        is_numbered_old_pattern = (
                            g.startswith(f"{base_name}.") and 
                            f".{lang}.srt" in g and
                            any(f".number{num}." in g for num in range(1, 100))
                        )
                        
                        is_numbered_acquisition_pattern = (
                            f".{lang}.number" in g and 
                            g.endswith('.srt') and
                            any(f".number{num}." in g for num in range(1, 100)) and
                            (sxxexx_code is None or sxxexx_code in g)
                        )
                        
                        if (g not in correct_patterns and 
                            (is_numbered_old_pattern or is_numbered_acquisition_pattern) and
                            not g.endswith('.FAILED.srt') and
                            not g.endswith('.DRIFT.srt')):
                            try:
                                os.remove(os.path.join(folder, g))
                                print_and_log(f"{sync_tag()} {Fore.YELLOW}Removed redundant numbered subtitle: {g}{Style.RESET_ALL}")
                            except Exception as e:
                                print_and_log(f"{sync_tag()} {Fore.RED}Could not remove {g}: {e}{Style.RESET_ALL}")

def comprehensive_cleanup_extracted_files():
    """
    Comprehensive cleanup of all non-synchronized subtitle files and extracted folders.
    Removes everything that is not a proper synchronized subtitle (video_name.lang.srt).
    """
    print_and_log(f"{sync_tag()} {Fore.LIGHTYELLOW_EX}Comprehensive cleanup: removing all non-synchronized files...{Style.RESET_ALL}")
    
    total_dirs = 1
    all_dirs = []
    all_dirs.append(anchor_path)
    
    # Collect all directories to process
    for root, dirs, files in os.walk(anchor_path):
        dirs[:] = [d for d in dirs if d.lower() not in skip_dirs]
        for d in dirs:
            dir_path = os.path.join(root, d)
            all_dirs.append(dir_path)
            total_dirs += 1
    
    processed_dirs = 0
    start_time = time.time()
    total_removed = 0
    total_folders_removed = 0
    
    def update_progress():
        elapsed = time.time() - start_time
        progress = processed_dirs / total_dirs if total_dirs > 0 else 0
        bar_length = 40
        filled_length = int(bar_length * progress)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        print(f"\\r{sync_tag()} {Fore.CYAN}[{bar}]{Style.RESET_ALL} {progress*100:.1f}% ({processed_dirs}/{total_dirs}) - {elapsed:.1f}s", end='', flush=True)
    
    # Process root directory first
    removed = cleanup_non_sync_files_in_folder(anchor_path)
    total_removed += removed
    processed_dirs += 1
    update_progress()
    
    # Process all subdirectories
    for root, dirs, files in os.walk(anchor_path):
        dirs[:] = [d for d in dirs if d.lower() not in skip_dirs]
        for d in dirs:
            folder_path = os.path.join(root, d)
            time.sleep(0.1)
            removed = cleanup_non_sync_files_in_folder(folder_path)
            total_removed += removed
            processed_dirs += 1
            update_progress()
    
    print()  # New line after progress bar
    
    # Remove episode folders and temp directories
    folders_removed = cleanup_episode_and_temp_folders()
    total_folders_removed += folders_removed
    
    if total_removed > 0 or total_folders_removed > 0:
        print_and_log(f"{sync_tag()} {Fore.GREEN}Comprehensive cleanup complete: removed {total_removed} files and {total_folders_removed} folders{Style.RESET_ALL}")
    else:
        print_and_log(f"{sync_tag()} {Fore.YELLOW}Comprehensive cleanup complete: no files needed removal{Style.RESET_ALL}")

def cleanup_non_sync_files_in_folder(folder: str):
    """
    Remove all subtitle files that are not synchronized subtitles.
    Keeps only files matching video_name.lang.srt pattern.
    """
    removed_count = 0
    try:
        files = os.listdir(folder)
    except Exception:
        return removed_count
    
    # Get video files in this folder to determine valid synchronized subtitle names
    video_files = [f for f in files if f.endswith(('.mkv', '.mp4', '.avi'))]
    
    # Create set of valid synchronized subtitle names
    valid_sync_names = set()
    for video_file in video_files:
        base_name = os.path.splitext(video_file)[0]
        
        # Extract series code if in series mode
        sxxexx_code = None
        if SERIES_MODE:
            sxxexx_code = extract_sxxexx_code(video_file)
        
        for lang in LANGUAGES:
            # Determine correct filename patterns based on mode and content
            if SERIES_MODE and sxxexx_code:
                # Series mode with SxxExx code
                if sxxexx_code.lower() in base_name.lower():
                    # Video already has SxxExx in name
                    valid_sync_names.add(f"{base_name}.{lang}.srt")
                else:
                    # Video doesn't have SxxExx
                    valid_sync_names.add(f"{base_name}.{sxxexx_code}.{lang}.srt")
            else:
                # Movie mode or series without clear SxxExx
                valid_sync_names.add(f"{base_name}.{lang}.srt")
    
    # Remove any subtitle file that doesn't match synchronized pattern
    for file in files:
        if file.endswith('.srt'):
            # Keep synchronized subtitles
            if file in valid_sync_names:
                continue
            
            # Keep FAILED and DRIFT files (user might want to inspect them)
            if file.endswith(('.FAILED.srt', '.DRIFT.srt')):
                continue
            
            # Remove everything else (numbered, extracted, temporary, etc.)
            try:
                file_path = os.path.join(folder, file)
                os.remove(file_path)
                print_and_log(f"{sync_tag()} {Fore.YELLOW}Removed non-sync subtitle: {file}{Style.RESET_ALL}")
                removed_count += 1
            except Exception as e:
                print_and_log(f"{sync_tag()} {Fore.RED}Could not remove {file}: {e}{Style.RESET_ALL}")
        
        # Remove SUBTITLES.S##.LANG.zip files only at the END of synchronization
        elif (file.lower().startswith('subtitles.s') and 
              file.lower().endswith('.zip') and 
              '.' in file):
            try:
                file_path = os.path.join(folder, file)
                os.remove(file_path)
                print_and_log(f"{sync_tag()} {Fore.YELLOW}Removed processed SUBTITLES archive: {file}{Style.RESET_ALL}")
                removed_count += 1
            except Exception as e:
                print_and_log(f"{sync_tag()} {Fore.RED}Could not remove {file}: {e}{Style.RESET_ALL}")
    
    return removed_count

def cleanup_episode_and_temp_folders():
    """
    Remove episode folders and temporary extraction directories.
    """
    removed_count = 0
    
    # Walk through all directories
    for root, dirs, files in os.walk(anchor_path, topdown=False):  # topdown=False to delete children before parents
        dirs[:] = [d for d in dirs if d.lower() not in skip_dirs]
        
        for d in dirs[:]:  # Use slice copy since we'll be modifying the list
            folder_path = os.path.join(root, d)
            folder_name_lower = d.lower()
            parent_name_lower = os.path.basename(root).lower()
            grandparent_name_lower = os.path.basename(os.path.dirname(root)).lower()
            # An episode subfolder can sit directly inside a SUBTITLES.Sxx(.LANG) folder,
            # or one level deeper inside a "Season X"/"Seizoen X" wrapper folder.
            is_inside_subtitles_folder = (
                parent_name_lower.startswith('subtitles.s') or
                (re.match(r'(season|seizoen)\s*\d+', parent_name_lower) and grandparent_name_lower.startswith('subtitles.s'))
            )

            # Remove episode folders (episode 1, episode 01, etc., or a SxxExx-style
            # folder name such as "Show.Name.S01E01...") sitting inside a SUBTITLES
            # folder - these are the per-episode subfolders left over after extraction.
            if re.match(r'episode\s*\d+', folder_name_lower) or (is_inside_subtitles_folder and extract_sxxexx_code(d)):
                try:
                    import shutil
                    shutil.rmtree(folder_path)
                    print_and_log(f"{sync_tag()} {Fore.YELLOW}Removed episode folder: {d}{Style.RESET_ALL}")
                    dirs.remove(d)  # Remove from dirs list so os.walk doesn't try to descend into it
                    removed_count += 1
                except Exception as e:
                    print_and_log(f"{sync_tag()} {Fore.RED}Could not remove episode folder {d}: {e}{Style.RESET_ALL}")
            
            # Remove temp extraction directories
            elif folder_name_lower.startswith('temp_extract_'):
                try:
                    import shutil
                    shutil.rmtree(folder_path)
                    print_and_log(f"{sync_tag()} {Fore.YELLOW}Removed temp folder: {d}{Style.RESET_ALL}")
                    dirs.remove(d)
                    removed_count += 1
                except Exception as e:
                    print_and_log(f"{sync_tag()} {Fore.RED}Could not remove temp folder {d}: {e}{Style.RESET_ALL}")
            
            # Remove empty SUBTITLES.S##.LANG folders (keep ZIP files)
            elif (folder_name_lower.startswith('subtitles.s') and 
                  '.' in folder_name_lower and 
                  not folder_name_lower.endswith('.zip')):
                try:
                    # Check if folder is empty or only contains files we don't need
                    folder_files = os.listdir(folder_path)
                    if not folder_files:  # Empty folder
                        os.rmdir(folder_path)
                        print_and_log(f"{sync_tag()} {Fore.YELLOW}Removed empty SUBTITLES folder: {d}{Style.RESET_ALL}")
                        dirs.remove(d)
                        removed_count += 1
                except Exception as e:
                    print_and_log(f"{sync_tag()} {Fore.RED}Could not remove SUBTITLES folder {d}: {e}{Style.RESET_ALL}")
    
    return removed_count

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
    ext = os.path.splitext(video_path)[1].lower()
    final_path = video_path if ext == '.mkv' else os.path.splitext(video_path)[0] + '.mkv'
    cmd = ["ffmpeg", "-hide_banner", "-y", "-i", video_path,
           "-map", "0:v", "-map", "0:a", "-c", "copy", "-sn", temp_path]
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0 and os.path.exists(temp_path):
        if final_path != video_path and os.path.exists(video_path):
            os.remove(video_path)
        os.replace(temp_path, final_path)
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
        not (os.path.exists(f"{os.path.splitext(video)[0]}.{lang}.srt") or 
             (SERIES_MODE and extract_sxxexx_code(video) and 
              os.path.exists(f"{os.path.splitext(video)[0]}.{extract_sxxexx_code(video)}.{lang}.srt")))
        for lang in LANGUAGES)
    )
    idx = 0
    for video in videos:
        video_basename, ext = os.path.splitext(video)
        all_present = True
        missing_langs = []
        for lang in LANGUAGES:
            found = False
            
            # Check standard naming: filename.lang.srt
            expected_standard = f"{video_basename}.{lang}.srt"
            if os.path.exists(expected_standard):
                found = True
            
            # Check series naming if in series mode
            if not found and SERIES_MODE:
                sxxexx_code = extract_sxxexx_code(video)
                if sxxexx_code:
                    # Check if video filename already contains the episode code
                    if sxxexx_code.lower() in video_basename.lower():
                        # Video already has SxxExx in name, subtitle should use standard naming
                        expected_series = f"{video_basename}.{lang}.srt"
                    else:
                        # Video doesn't have SxxExx, subtitle should have SxxExx before language
                        expected_series = f"{video_basename}.{sxxexx_code}.{lang}.srt"
                    
                    if os.path.exists(expected_series):
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
                    found_external = False
                    
                    # Check standard naming: filename.lang.srt
                    expected_standard = f"{video_basename}.{lang}.srt"
                    if os.path.exists(expected_standard):
                        found_external = True
                    
                    # Check series naming if in series mode: filename.S01E01.lang.srt
                    if not found_external and SERIES_MODE:
                        sxxexx_code = extract_sxxexx_code(video)
                        if sxxexx_code:
                            if sxxexx_code.lower() in video_basename.lower():
                                expected_series = f"{video_basename}.{lang}.srt"
                            else:
                                expected_series = f"{video_basename}.{sxxexx_code}.{lang}.srt"
                            if os.path.exists(expected_series):
                                found_external = True
                    
                    if found_external:
                        external_langs.add(lang)
                present_langs = internal_langs.union(external_langs)
                duplicates = internal_langs.intersection(external_langs)
                all_present = all(lang in present_langs for lang in LANGUAGES)
                if all_present and not duplicates:
                    print_and_log(f"\n{Fore.GREEN}All required languages are present (internally and/or externally), no duplicates found.{Style.RESET_ALL}")
                    print_and_log(f"{Fore.GREEN}Recommended: Keep internal subtitles to ensure all subtitle languages remain available.{Style.RESET_ALL}")
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
                            _vext = os.path.splitext(video)[1].lower()
                            final_video = video if _vext == '.mkv' else os.path.splitext(video)[0] + '.mkv'
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
                                if final_video != video and os.path.exists(video):
                                    os.remove(video)
                                os.replace(temp_path, final_video)
                                video = final_video
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
                                        _vext = os.path.splitext(video)[1].lower()
                                        final_video = video if _vext == '.mkv' else os.path.splitext(video)[0] + '.mkv'
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
                                            if final_video != video and os.path.exists(video):
                                                os.remove(video)
                                            os.replace(temp_path, final_video)
                                            video = final_video
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
                            _vext = os.path.splitext(video)[1].lower()
                            final_video = video if _vext == '.mkv' else os.path.splitext(video)[0] + '.mkv'
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
                                if final_video != video and os.path.exists(video):
                                    os.remove(video)
                                os.replace(temp_path, final_video)
                                video = final_video
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

def move_entries_to_manual_verification(selected_entries):
    """Move selected auto-accepted entries to the TOP of the manual offset file."""
    if not selected_entries:
        return
    
    # Get videos list from global scope (set by subordinate.py)
    global videos
    available_videos = videos if 'videos' in globals() else []
    
    # Parse the auto-accepted entries to extract needed info
    entries_to_add = []
    for entry in selected_entries:
        if '|' not in entry:
            continue
        
        parts = entry.split('|')
        if len(parts) < 3:
            continue
        
        # Parse: "Movie Name (Year) [LANG] | offset | correlation_score"
        title_lang = parts[0].strip()
        offset_str = parts[1].strip()
        correlation_score = parts[2].strip()
        
        # Extract movie name and language
        if '[' in title_lang and ']' in title_lang:
            lang_start = title_lang.rfind('[')
            lang_end = title_lang.rfind(']')
            movie_name = title_lang[:lang_start].strip()
            lang = title_lang[lang_start+1:lang_end].strip().lower()
        else:
            continue  # Skip if format is unexpected
        
        # Try to find the video path by scanning available videos
        video_path = None
        subtitle_path = None
        for video in available_videos:
            video_basename = os.path.splitext(os.path.basename(video))[0]
            # Try to match the trimmed name
            trimmed_video_name = trim_movie_name(video_basename)
            if trimmed_video_name.lower() == movie_name.lower() or video_basename.lower() in movie_name.lower():
                video_path = video
                # Try to find the subtitle file
                video_dir = os.path.dirname(video)
                subtitle_pattern = f"{video_basename}.{lang}.srt"
                potential_sub = os.path.join(video_dir, subtitle_pattern)
                if os.path.exists(potential_sub):
                    subtitle_path = potential_sub
                break
        
        # Skip entry entirely if we couldn't locate the video file on disk.
        # Without a real path we cannot build a valid positional entry and the
        # validator would immediately discard it anyway.
        if not video_path:
            print_and_log(f"{sync_tag()} {Fore.YELLOW}Warning: Could not locate video for '{movie_name}' — skipping manual verification entry.{Style.RESET_ALL}")
            continue

        video_dir_str    = os.path.dirname(video_path)
        video_base_str   = os.path.basename(video_path)
        video_stem_str   = os.path.splitext(video_base_str)[0]

        # Subtitle filename — use the existing synced file if we found it, else construct it
        sub_base_str = (os.path.basename(subtitle_path)
                        if subtitle_path and os.path.exists(subtitle_path)
                        else f"{video_stem_str}.{lang}.srt")

        # Get first subtitle line (both time and text)
        first_time_str = "00:00:00"
        first_line_str = "N/A"
        if subtitle_path and os.path.exists(subtitle_path):
            try:
                first_time_val, first_line_val = get_first_line_and_time(subtitle_path)
                first_time_str = first_time_val if first_time_val else "00:00:00"
                first_line_str = first_line_val if first_line_val else "N/A"
            except:
                pass

        # Calculate quality score
        try:
            offset_float = float(offset_str.replace('s', '').strip())
            correlation_float = float(correlation_score)
            quality_score = calculate_quality_score(offset_float, correlation_float)
            quality_label = "Excellent" if quality_score >= 80 else "Good" if quality_score >= 65 else "Decent" if quality_score >= 50 else "Poor"
        except:
            offset_float = 0.0
            quality_score = 0
            quality_label = "Unknown"

        # Derive the orig-numbered placeholder (best-effort; DRIFT cleanup may have
        # already removed the numbered files for auto-accepted subtitles)
        orig_numbered_name = f"{video_stem_str}.{lang}.number1.srt"

        # Build entry in the SAME POSITIONAL FORMAT used by add_offset_entry().
        # Every reader (validate_and_update_offset_file_paths, show_manual_correction_menu,
        # etc.) depends on these exact line positions:
        #   line[0]  title + [LANG]
        #   line[1]  video folder (directory only)
        #   line[2]  video filename  ← MUST end with .mkv/.mp4/.avi or entry is silently skipped
        #   line[3]  subtitle filename
        #   line[4]  offset as a plain float string  (e.g. "0.060", NOT "0.060s")
        #   line[5]  correlation score
        #   line[6]  first_time  first_line
        #   line[7]  orig numbered subtitle name
        #   then "Rejected:", "BatchSize:", "IMDb_match:", "Quality:" metadata lines
        #
        # BUG HISTORY: previously this function wrote Key:Value lines ("Name:", "Path:",
        # "Offset:") which caused lines[2] to be "Offset: 0.040s" instead of the video
        # filename, making validate_and_update_offset_file_paths immediately discard
        # every moved entry with "Video not found anywhere, removing from verification list".
        entry_text  = f"{movie_name} [{lang.upper()}]\n"
        entry_text += f"{video_dir_str}\n"
        entry_text += f"{video_base_str}\n"
        entry_text += f"{sub_base_str}\n"
        entry_text += f"{offset_float:.3f}\n"
        entry_text += f"{correlation_score}\n"
        entry_text += f"{first_time_str}  {first_line_str}\n"
        entry_text += f"{orig_numbered_name}\n"
        entry_text += f"Rejected: 0\n"
        entry_text += f"BatchSize: 0\n"
        entry_text += f"IMDb_match: yes\n"
        entry_text += f"Quality: {quality_label} ({quality_score:.0f}/100)\n"

        entries_to_add.append(entry_text)
    
    if not entries_to_add:
        return
    
    # Read existing offset file
    existing_content = ""
    header = ""
    existing_entries_text = ""
    
    if os.path.exists(MOVIES_WITH_LINEAR_OFFSET_FILE):
        try:
            with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split header from entries
            if '--\n' in content:
                parts = content.split('--\n', 1)
                header = parts[0] + '--\n'
                if len(parts) > 1:
                    existing_entries_text = parts[1]
            else:
                header = content
        except Exception as e:
            print_and_log(f"{sync_tag()} {Fore.YELLOW}Warning: Could not read offset file: {e}{Style.RESET_ALL}")
    else:
        # Create header if file doesn't exist
        header = "Linear offset tracking file for movies with subtitle sync corrections.\n"
        header += "Format: movie name, path, offset, timestamp, first line, rejected count\n--\n"
    
    # Write new file with selected entries at the TOP
    try:
        with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'w', encoding='utf-8') as f:
            f.write(header)
            # Add selected entries FIRST (at the top)
            for entry_text in entries_to_add:
                f.write(entry_text)
                f.write("--\n")
            # Then add existing entries
            if existing_entries_text:
                f.write(existing_entries_text)
        
        print_and_log(f"{sync_tag()} {Fore.GREEN}Added {len(entries_to_add)} entry/entries to manual verification queue (at the top).{Style.RESET_ALL}")
    except Exception as e:
        print_and_log(f"{sync_tag()} {Fore.RED}Error writing to offset file: {e}{Style.RESET_ALL}")

def add_offset_entry(video, video_dir, lang, output_sub, diffs, anchor_path, sub_files, correlation_score=0.0, batch_size=0):
    """Add or update offset entry in tracking file for manual verification."""
    if not os.path.exists(MOVIES_WITH_LINEAR_OFFSET_FILE):
        with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'w', encoding='utf-8') as f:
            f.write("Linear offset tracking file for movies with subtitle sync corrections.\n")
            f.write("Format: movie name, path, offset, timestamp, first line, rejected count\n--\n")
    
    rel_video_path = os.path.relpath(video, anchor_path)
    _base = trim_movie_name(os.path.basename(video))
    if SERIES_MODE:
        _sxxexx = extract_sxxexx_code(os.path.basename(video))
        if _sxxexx:
            _base = f"{_base} {_sxxexx.upper()}"
    trimmed_name = f"{_base} [{lang.upper()}]"
    first_time, first_line = get_first_line_and_time(output_sub)

    orig_numbered = next((s for s in sub_files if '.number' in s), None)
    
    # Get rejected count for this video+lang combination
    video_basename = os.path.basename(video)
    video_basename_no_ext = os.path.splitext(video_basename)[0]
    # Use basename WITHOUT extension to match the key used in Smart Sync
    rejected_count = rejected_subtitle_counts.get((video_basename_no_ext, lang), 0)
    
    # Get IMDb match status from metadata file
    # Note: metadata file stores video names WITHOUT extension
    metadata_file = os.path.join(script_dir, ".subtitle_metadata.txt")
    imdb_status = "unknown"
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if '|' in line:
                        parts = line.strip().split('|')
                        if len(parts) >= 3:
                            meta_video, meta_lang, meta_imdb = parts[0], parts[1], parts[2]
                            if meta_video == video_basename_no_ext and meta_lang == lang:
                                imdb_status = "yes" if meta_imdb == "imdb_match" else "no"
                                break
        except Exception as e:
            print_and_log(f"{sync_tag()} {Fore.YELLOW}Warning: Could not read metadata file: {e}{Style.RESET_ALL}")
    
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
        f"{correlation_score:.0f}" if correlation_score != 0.0 else "N/A",
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
    
    # Add rejected count, IMDb match status, and quality score at the end
    new_entry_lines.append(f"Rejected: {rejected_count}")
    new_entry_lines.append(f"BatchSize: {batch_size}")
    new_entry_lines.append(f"IMDb_match: {imdb_status}")
    
    # Calculate and add quality score
    quality_score = calculate_quality_score(diffs[0], correlation_score)
    quality_tier, _ = get_quality_tier(quality_score)
    new_entry_lines.append(f"Quality: {quality_tier} ({quality_score:.0f}/100)")
    
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

def add_auto_accepted_entry(video, lang, offset, correlation_score, bonus=0):
    """Add entry to auto_accepted_movies.txt for display before manual verification."""
    if not os.path.exists(AUTO_ACCEPTED_FILE):
        with open(AUTO_ACCEPTED_FILE, 'w', encoding='utf-8') as f:
            f.write("Auto-accepted subtitles tracking file.\n")
            f.write("Format: movie name [LANG] | offset | correlation score | video basename | bonus\n--\n")
    
    # Get clean movie name (no pirate tags, just name + year)
    _base = trim_movie_name(os.path.basename(video))
    if SERIES_MODE:
        _sxxexx = extract_sxxexx_code(os.path.basename(video))
        if _sxxexx:
            _base = f"{_base} {_sxxexx.upper()}"
    trimmed_name = _base
    video_basename = os.path.basename(video)
    entry_line = f"{trimmed_name} [{lang.upper()}] | {offset:.3f}s | {correlation_score:.0f} | {video_basename} | {bonus}"
    
    with open(AUTO_ACCEPTED_FILE, 'a', encoding='utf-8') as f:
        f.write(entry_line + "\n")

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
        
        # Use os.replace (not os.rename) so that if the DRIFT file already exists
        # (e.g. batch-DRIFT preservation already ran for this number), it is
        # silently overwritten instead of raising FileExistsError on Windows.
        os.replace(subtitle_path, drift_path)
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

def cleanup_drift_and_failed(video_dir, lang, keep_file=None, clean_drifts=True, video=None, silent=False, clean_numbered=True):
    """Clean up numbered, failed, and drift subtitle files for a language.

    clean_numbered=False leaves plain (untested-by-other-parts) numbered candidates alone,
    used while a multi-part episode still has sibling parts that need the shared candidate pool.
    """
    deleted_drift_keys = set()
    for f in os.listdir(video_dir):
        full_path = os.path.abspath(os.path.join(video_dir, f))
        
        # Series-aware pattern matching
        is_numbered = False
        is_failed = False 
        is_drift = False
        
        if SERIES_MODE and video:
            sxxexx_code = extract_sxxexx_code(video)
            if sxxexx_code:
                # Series mode patterns with episode code
                if re.match(rf".*\.{lang}\.number\d+\.{re.escape(sxxexx_code)}\.srt$", f, re.IGNORECASE):
                    is_numbered = True
                elif re.match(rf".*\.{lang}\.number\d+\.{re.escape(sxxexx_code)}\.FAILED\.srt$", f, re.IGNORECASE):
                    is_failed = True
                elif re.match(rf".*\.{lang}\.number\d+\.{re.escape(sxxexx_code)}\.DRIFT\.srt$", f, re.IGNORECASE):
                    is_drift = True
        
        # Fallback to movie mode patterns (or if no series episode code)
        if not (is_numbered or is_failed or is_drift):
            if re.match(rf".*\.{lang}\.number\d+\.srt$", f, re.IGNORECASE):
                is_numbered = True
            elif re.match(rf".*\.{lang}\.number\d+\.FAILED\.srt$", f, re.IGNORECASE):
                is_failed = True
            elif re.match(rf".*\.{lang}\.number\d+\.DRIFT\.srt$", f, re.IGNORECASE):
                is_drift = True
        
        # Remove files based on patterns
        if is_numbered:
            if not clean_numbered:
                continue
            if keep_file and full_path == os.path.abspath(keep_file):
                continue
            try:
                os.remove(full_path)
                if not silent:
                    print_and_log(f"{sync_tag()} {Fore.YELLOW}Cleanup: removed numbered sub: {f}{Style.RESET_ALL}")
            except Exception as e:
                if not silent:
                    print_and_log(f"{sync_tag()} {Fore.RED}Could not remove {f}: {e}{Style.RESET_ALL}")
        elif is_failed:
            try:
                os.remove(full_path)
                if not silent:
                    print_and_log(f"{sync_tag()} {Fore.YELLOW}Cleanup: removed FAILED: {f}{Style.RESET_ALL}")
            except Exception as e:
                if not silent:
                    print_and_log(f"{sync_tag()} {Fore.RED}Could not remove {f}: {e}{Style.RESET_ALL}")
        elif clean_drifts and is_drift:
            try:
                os.remove(full_path)
                deleted_drift_keys.add(make_drift_metadata_key(f))
                if not silent:
                    print_and_log(f"{sync_tag()} {Fore.YELLOW}Cleanup: removed DRIFT: {f}{Style.RESET_ALL}")
            except Exception as e:
                if not silent:
                    print_and_log(f"{sync_tag()} {Fore.RED}Could not remove {f}: {e}{Style.RESET_ALL}")
    if deleted_drift_keys:
        clean_drift_subtitle_metadata(DRIFT_METADATA_FILE, deleted_drift_keys)
processed_subs = set()
total_videos = len(videos)
acquisition_needed = False  

# Multi-part episodes (e.g. "Broken (Part 1)"/"Broken (Part 2)") share the same SxxExx code
# across several video files. Track how many siblings still need this code's candidate pool
# so DRIFT-marking of non-winning candidates can be deferred until the last part is done.
series_code_totals = {}
if SERIES_MODE:
    for _v in videos:
        _c = extract_sxxexx_code(_v)
        if _c:
            _key = (os.path.dirname(_v), _c)
            series_code_totals[_key] = series_code_totals.get(_key, 0) + 1
series_code_seen = {}

for idx, video in enumerate(videos, 1):
    clear_and_print_ascii(BANNER_LINE)
    print_video_header(video, idx, total_videos)
    video_dir = os.path.dirname(video)
    video_basename, _ = os.path.splitext(video)

    is_last_part_for_code = True
    if SERIES_MODE:
        _code = extract_sxxexx_code(video)
        if _code:
            _key = (video_dir, _code)
            series_code_seen[_key] = series_code_seen.get(_key, 0) + 1
            is_last_part_for_code = series_code_seen[_key] >= series_code_totals.get(_key, 1)
    
    all_subs_exist = True
    has_numbered_subs = False
    
    for lang in LANGUAGES:
        # Check if final subtitles exist (either standard or series naming)
        final_exists = False
        
        # Check standard naming: filename.lang.srt  
        expected_standard = f"{video_basename}.{lang}.srt"
        if os.path.exists(expected_standard):
            final_exists = True
        
        # Check series naming if in series mode: filename.lang.S01E01.srt
        if not final_exists and SERIES_MODE:
            sxxexx_code = extract_sxxexx_code(video)
            if sxxexx_code:
                expected_series = f"{video_basename}.{lang}.{sxxexx_code}.srt"
                if os.path.exists(expected_series):
                    final_exists = True
        
        # Check if there are numbered subtitle files to sync
        if not final_exists:
            import glob
            # Check for both movie and series patterns
            if SERIES_MODE:
                current_episode_code = extract_sxxexx_code(video)
                if current_episode_code:
                    # Series pattern: downloads.lang.number1.S01E01.srt (for THIS episode)
                    numbered_files = glob.glob(os.path.join(video_dir, f"*.{lang}.number*.{current_episode_code}.srt"))
                else:
                    numbered_files = []
                if not numbered_files:
                    # Fallback to movie pattern
                    numbered_files = glob.glob(os.path.join(video_dir, f"*.{lang}.number*.srt"))
            else:
                # Movie pattern: filename.lang.number1.srt
                numbered_files = glob.glob(os.path.join(video_dir, f"*.{lang}.number*.srt"))
                
            if numbered_files:
                has_numbered_subs = True
            all_subs_exist = False
    
    if all_subs_exist and not has_numbered_subs:
        print_and_log(f"{sync_tag()} {Fore.GREEN}All required subtitles already exist for this video - skipping{Style.RESET_ALL}")
        continue
    
    candidate_subs = defaultdict(list)
    current_episode_code = None
    if SERIES_MODE:
        current_episode_code = extract_sxxexx_code(video)
    
    for f in os.listdir(video_dir):
        f_path = os.path.join(video_dir, f)
        
        # Check for both formats:
        # Movie mode: filename.lang.number1.srt
        # Series mode: downloads.lang.number1.S01E01.srt
        match = None
        
        if not SERIES_MODE:
            # Movie mode pattern
            match = re.match(r".*\.(?P<lang>[a-z]{2})\.number\d+\.srt$", f)
        else:
            # Series mode: only match files for THIS episode
            if current_episode_code:
                # Try series mode pattern with matching episode code
                pattern = rf".*\.(?P<lang>[a-z]{{2}})\.number\d+\.{re.escape(current_episode_code)}\.srt$"
                match = re.match(pattern, f)
            if not match:
                # Fallback to movie mode pattern for backwards compatibility
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
        
        if SMART_SYNC:
            # SMART SYNC MODE: Sync all candidates first, then pick the best one
            sync_results = []  # List of (sub, output_sub, sync_success, offset_seconds)
            
            # Track rejected count for this movie+lang combo
            movie_key = (os.path.basename(video_basename), lang)
            rejected_count = 0
            
            # Clear screen and show fresh header for new language
            clear_and_print_ascii(BANNER_LINE)
            print_video_header(video, idx, total_videos, lang)
            
            if not logged_video_context:
                print_and_log(f"➤ {os.path.basename(video)}", log_only=True)
                logged_video_context = True
            
            print_and_log(f"{sync_mode_tag()}: {Fore.CYAN}Testing {len(subs_sorted)} {lang.upper()} subtitle candidates{Style.RESET_ALL}\n")
            
            # Track rankings as we go
            current_rankings = []
            rejected_subs = []
            
            # Synchronize ALL subtitles in the batch
            for i, sub in enumerate(subs_sorted, 1):
                if sub.endswith('.DRIFT.srt') or sub.endswith('.FAILED.srt'):
                    continue
                    
                ext = os.path.splitext(sub)[1].lower()
                sub_name = os.path.basename(sub)
                
                # Determine output filename (series vs standard naming)
                if SERIES_MODE:
                    sxxexx_code = extract_sxxexx_code(video)
                    if sxxexx_code:
                        if sxxexx_code.lower() in video_basename.lower():
                            temp_output = f"{video_basename}.{lang}.temp{i}{ext}"
                        else:
                            temp_output = f"{video_basename}.{sxxexx_code}.{lang}.temp{i}{ext}"
                    else:
                        temp_output = f"{video_basename}.{lang}.temp{i}{ext}"
                else:
                    temp_output = f"{video_basename}.{lang}.temp{i}{ext}"
                
                # Screen refresh between candidates (except for first)
                if i > 1:
                    time.sleep(0.5)
                    clear_and_print_ascii(BANNER_LINE)
                    print_video_header(video, idx, total_videos, lang)
                    # Re-print Smart Sync header
                    print_and_log(f"{sync_mode_tag()} {Fore.CYAN}Smart Sync: Testing {len(subs_sorted)} {lang.upper()} subtitle candidates{Style.RESET_ALL}\n")
                    # Show current rankings so far
                    if current_rankings or rejected_subs:
                        display_rankings = _build_display_rankings(current_rankings, rejected_subs)
                        print_rankings_table(display_rankings, final=False, clear_lines=0)
                        print()  # Empty line before progress bar
                
                # Draw fresh progress bar for this candidate
                # Start animation directly
                progress_animator.current_candidate = i
                progress_animator.total_candidates = len(subs_sorted)
                progress_animator.subtitle_name = sub_name[:48] if len(sub_name) > 48 else sub_name
                progress_animator.status = "Audio analysis"
                progress_animator.progress = 0.0
                progress_animator.start_time = time.time()
                progress_animator.stop_event.clear()
                progress_animator.first_draw = True  # Flag to indicate first draw
                
                # Start animation thread - it will draw everything
                progress_animator.thread = threading.Thread(target=progress_animator._animate, daemon=True)
                progress_animator.thread.start()
                
                sync_success, offset_seconds, correlation_score = synchronize_subtitle_with_ffsubsync(video, sub, temp_output, progress_callback=progress_animator)
                
                # Stop animation and show 100%
                progress_animator.stop(force_complete=True)
                
                sync_results.append((sub, temp_output, sync_success, offset_seconds, correlation_score))
                
                # Update rankings
                if sync_success:
                    # Calculate quality score
                    quality_score = calculate_quality_score(offset_seconds, correlation_score)
                    
                    # Reject if low/negative correlation OR quality score below AUTO_REJECT_SCORE
                    if correlation_score < 2500:
                        rejected_subs.append((sub_name, offset_seconds, 0))  # Force score=0 → 0/100 Bad in rankings
                        rejected_count += 1
                        print(f"{Fore.RED}✗ Rejected: {offset_seconds:.3f}s offset | Score: {correlation_score:.0f} (< 2500 auto-reject){Style.RESET_ALL}")
                    elif quality_score < AUTO_REJECT_SCORE:
                        rejected_subs.append((sub_name, offset_seconds, correlation_score))
                        rejected_count += 1
                        quality_tier, tier_color = get_quality_tier(quality_score)
                        print(f"{Fore.RED}✗ Rejected: {offset_seconds:.3f}s offset | Score: {correlation_score:.0f} | Quality: {tier_color}{quality_tier} ({quality_score:.0f}/100){Style.RESET_ALL} - below threshold ({AUTO_REJECT_SCORE:.0f})")
                    else:
                        # Store with quality_score for sorting
                        current_rankings.append((sub_name, offset_seconds, correlation_score, quality_score))
                        quality_tier, tier_color = get_quality_tier(quality_score)
                        print(f"{Fore.GREEN}Synced: {offset_seconds:.3f}s offset | Score: {correlation_score:.0f} | Quality: {tier_color}{quality_tier} ({quality_score:.0f}/100){Style.RESET_ALL}")
                        
                        # Early exit: skip remaining candidates if quality meets or exceeds QUALITY_SCORE_SKIP
                        if quality_score >= QUALITY_SCORE_SKIP and i < len(subs_sorted):
                            remaining = len(subs_sorted) - i
                            print_and_log(f"{Fore.GREEN}Quality score {quality_score:.0f}/100 ≥ {QUALITY_SCORE_SKIP:.0f} threshold — skipping remaining {remaining} candidate(s){Style.RESET_ALL}")
                            break
                else:
                    print(f"{Fore.RED}✗ Failed to sync{Style.RESET_ALL}")
                
                # Show updated rankings after each candidate (except last - we'll show it after refresh)
                if i < len(subs_sorted) and (current_rankings or rejected_subs):
                    display_rankings = _build_display_rankings(current_rankings, rejected_subs)
                    print_rankings_table(display_rankings, final=False, clear_lines=0)
            
            # After all candidates: refresh screen and show final rankings
            if current_rankings or rejected_subs:
                time.sleep(0.5)
                # Clear screen and show fresh header
                clear_and_print_ascii(BANNER_LINE)
                print_video_header(video, idx, total_videos, lang)
                print()
                
                # Show final rankings (with bonuses applied — full batch now known)
                display_rankings = _build_display_rankings(current_rankings, rejected_subs, show_bonuses=True)
                print_rankings_table(display_rankings, final=False, clear_lines=0)
            
            # Find the best result based on quality score
            valid_results = []
            for sub, temp_out, success, offset, score in sync_results:
                if success and score >= 2500:
                    quality_score = calculate_quality_score(offset, score)
                    if quality_score >= AUTO_REJECT_SCORE:  # Not rejected
                        valid_results.append((sub, temp_out, offset, score, quality_score))
            
            if valid_results:
                # Apply batch confidence bonuses and pick winner on base + bonus
                max_conf = max(v[3] for v in valid_results)
                bonused_results = []
                for sub, temp_out, offset, score, base_quality in valid_results:
                    if score >= max_conf * 0.9999:
                        bonus = min(10, 100 - base_quality)
                    elif score >= max_conf * 0.95:
                        bonus = min(5, 100 - base_quality)
                    else:
                        bonus = 0
                    bonused_results.append((sub, temp_out, offset, score, base_quality, bonus))
                
                best_sub, best_temp_output, best_offset, best_score, best_quality, best_bonus = max(bonused_results, key=lambda x: x[4] + x[5])
                
                # Show which subtitle was selected (single line)
                best_sub_name = os.path.basename(best_sub)
                print(f"\n{Fore.GREEN}>>> SELECTED: {best_sub_name} ({best_offset:.3f}s | Score: {best_score:.0f}){Style.RESET_ALL}")
                
                # Determine final output filename
                if SERIES_MODE:
                    sxxexx_code = extract_sxxexx_code(video)
                    if sxxexx_code:
                        if sxxexx_code.lower() in video_basename.lower():
                            final_output = f"{video_basename}.{lang}{os.path.splitext(best_sub)[1].lower()}"
                        else:
                            final_output = f"{video_basename}.{sxxexx_code}.{lang}{os.path.splitext(best_sub)[1].lower()}"
                    else:
                        final_output = f"{video_basename}.{lang}{os.path.splitext(best_sub)[1].lower()}"
                else:
                    final_output = f"{video_basename}.{lang}{os.path.splitext(best_sub)[1].lower()}"
                
                # Move best result to final location
                try:
                    os.rename(best_temp_output, final_output)
                    
                    # Check if subtitle was acquired with IMDb match
                    had_imdb_match = read_subtitle_metadata(Path(video_dir), Path(video).stem, lang)
                    
                    # Store rejected count BEFORE calling add_offset_entry so it can be read
                    rejected_subtitle_counts[movie_key] = rejected_count
                    
                    # Calculate quality score (base) - bonus only affects batch ranking, never the
                    # accept/reject decision below, so the tier label must reflect the base score too.
                    quality_score = calculate_quality_score(best_offset, best_score)
                    quality_tier, tier_color = get_quality_tier(quality_score)
                    score_display = f"{quality_score}+{best_bonus}" if best_bonus > 0 else f"{quality_score}"
                    
                    # Determine if manual verification is needed
                    # Auto-accept only if ALL criteria met:
                    # 1. Quality score ≥ AUTO_ACCEPT_SCORE (configurable, default 65/100)
                    # 2. Not more than 50% of batch rejected (only if COUNT_REJECTED = true)
                    # 3. IMDb match found (only if REQUIRE_IMDB_VALIDATION = true)
                    needs_manual_verification = False
                    verification_reason = ""
                    batch_size = len(subs_sorted)
                    reject_threshold = math.ceil(batch_size / 2)
                    
                    if quality_score < AUTO_ACCEPT_SCORE:
                        needs_manual_verification = True
                        verification_reason = f"Quality score {score_display}/100 < {AUTO_ACCEPT_SCORE:.0f} ({quality_tier})"
                    elif COUNT_REJECTED and rejected_count > reject_threshold:
                        needs_manual_verification = True
                        verification_reason = f"{rejected_count}/{batch_size} rejected (>50% of batch)"
                    elif REQUIRE_IMDB_VALIDATION and not had_imdb_match:
                        needs_manual_verification = True
                        verification_reason = "No IMDb match"
                    
                    # Handle the best result based on verification decision
                    if needs_manual_verification:
                        print_and_log(f"\n{sync_tag()} {Fore.YELLOW}[>>] Selected: {os.path.basename(best_sub)} ({best_offset:.3f}s | Score: {best_score:.0f}) - manual verification required ({verification_reason}){Style.RESET_ALL}")
                        # Only add to offset file if manual verification needed
                        try:
                            add_offset_entry(video, video_dir, lang, final_output, [best_offset], anchor_path, [os.path.basename(best_sub)], best_score, batch_size=len(subs_sorted))
                        except Exception as e:
                            print_and_log(f"{sync_tag()} {Fore.RED}Error adding offset entry: {str(e)}{Style.RESET_ALL}")
                    else:
                        print_and_log(f"\n{sync_tag()} {Fore.GREEN}Selected: {os.path.basename(best_sub)} ({best_offset:.3f}s | Score: {best_score:.0f}) - Quality: {tier_color}{quality_tier} ({score_display}/100){Style.RESET_ALL} {Fore.GREEN}- auto-accepted{Style.RESET_ALL}")
                        # Add to auto-accepted tracking file for summary display
                        try:
                            add_auto_accepted_entry(video, lang, best_offset, best_score, best_bonus)
                        except Exception as e:
                            print_and_log(f"{sync_tag()} {Fore.RED}Error adding auto-accepted entry: {str(e)}{Style.RESET_ALL}")
                    
                    # Smart Sync: mark ALL batch candidates (including the winner's original) as
                    # DRIFT so acquisition knows the full batch has been tried. If the chosen
                    # subtitle is later rejected in the verification menu, acquisition will
                    # correctly skip past the entire batch instead of re-downloading candidates.
                    # This also covers candidates skipped via the QUALITY_SCORE_SKIP early exit.
                    synced_subs = {batch_sub for batch_sub, _, _, _, _ in sync_results}
                    all_batch_subs = synced_subs | {s for s in subs_sorted
                                                    if not s.endswith('.DRIFT.srt')
                                                    and not s.endswith('.FAILED.srt')}
                    if is_last_part_for_code:
                        for batch_sub in all_batch_subs:
                            if os.path.exists(batch_sub):
                                batch_base, batch_ext = os.path.splitext(batch_sub)
                                batch_drift = f"{batch_base}.DRIFT{batch_ext}"
                                try:
                                    os.rename(batch_sub, batch_drift)
                                except Exception as e:
                                    print_and_log(f"{sync_tag()} {Fore.RED}Could not preserve batch candidate as DRIFT: {e}{Style.RESET_ALL}")
                    else:
                        print_and_log(f"{sync_tag()} {Fore.CYAN}Multi-part episode - keeping {len(all_batch_subs)} candidate(s) available for remaining part(s), not marking as DRIFT{Style.RESET_ALL}")

                    # Save sync quality metadata for DRIFT/FAILED selection menus
                    for b_sub, _, b_offset, b_score, b_quality, b_bonus in bonused_results:
                        try:
                            save_drift_subtitle_metadata(DRIFT_METADATA_FILE, b_sub, b_quality, b_score, b_bonus, b_offset)
                        except Exception:
                            pass

                    # Save rejected subs (synced but below threshold) with rejected flag
                    valid_sub_paths = {v_sub for v_sub, _, _, _, _ in valid_results}
                    for r_sub, _, r_success, r_offset, r_score in sync_results:
                        if r_sub in valid_sub_paths:
                            continue
                        try:
                            r_quality = calculate_quality_score(r_offset, r_score) if r_success and r_score >= 2500 else 0.0
                            r_corr = float(r_score) if r_success else 0.0
                            r_off = r_offset if r_success else 0.0
                            save_drift_subtitle_metadata(DRIFT_METADATA_FILE, r_sub, r_quality, r_corr, 0, r_off, rejected=True)
                        except Exception:
                            pass

                    # Perform cleanup silently first (clean_drifts=False: preserve batch DRIFT markers)
                    cleanup_drift_and_failed(video_dir, lang, keep_file=final_output, clean_drifts=False, video=video, silent=True, clean_numbered=is_last_part_for_code)
                    
                    # Give user 5 seconds to review the final rankings and selection
                    time.sleep(5)
                    
                    # Now show cleanup messages
                    cleanup_drift_and_failed(video_dir, lang, keep_file=final_output, clean_drifts=False, video=video, silent=False, clean_numbered=is_last_part_for_code)
                    
                    found_good = True
                    successful_syncs += 1
                    successful_syncs_per_lang[lang] = successful_syncs_per_lang.get(lang, 0) + 1
                    processed_subs.add(best_sub)
                    
                except Exception as e:
                    print_and_log(f"{sync_tag()} {Fore.RED}Error finalizing best result: {str(e)}{Style.RESET_ALL}")
            else:
                print_and_log(f"{sync_mode_tag()} {Fore.RED}Smart Sync: No acceptable results found for {lang.upper()}{Style.RESET_ALL}")
                # Save all synced subs as rejected (none met valid threshold)
                for r_sub, _, r_success, r_offset, r_score in sync_results:
                    try:
                        r_quality = calculate_quality_score(r_offset, r_score) if r_success and r_score >= 2500 else 0.0
                        r_corr = float(r_score) if r_success else 0.0
                        r_off = r_offset if r_success else 0.0
                        save_drift_subtitle_metadata(DRIFT_METADATA_FILE, r_sub, r_quality, r_corr, 0, r_off, rejected=True)
                    except Exception:
                        pass
            
            # Clean up all temporary files
            for sub, temp_output, success, offset, score in sync_results:
                try:
                    if os.path.exists(temp_output):
                        os.remove(temp_output)
                except:
                    pass
            
            # Mark as DRIFT (not FAILED) so acquisition can try next batch
            if not found_good:
                if is_last_part_for_code:
                    for sub in subs_sorted:
                        if not sub.endswith('.DRIFT.srt') and not sub.endswith('.FAILED.srt'):
                            base_name = os.path.splitext(sub)[0]
                            drift_name = f"{base_name}.DRIFT{os.path.splitext(sub)[1]}"
                            try:
                                os.rename(sub, drift_name)
                                print_and_log(f"{sync_tag()} {Fore.YELLOW}Marked as DRIFT: {os.path.basename(drift_name)}{Style.RESET_ALL}")
                                drift_subs.append(sub)
                            except Exception as e:
                                print_and_log(f"{sync_tag()} {Fore.RED}Could not rename to DRIFT: {str(e)}{Style.RESET_ALL}")
                else:
                    print_and_log(f"{sync_tag()} {Fore.CYAN}Multi-part episode - leaving {len(subs_sorted)} candidate(s) untouched for remaining part(s){Style.RESET_ALL}")
        
        else:
            # STANDARD MODE: First match mode (original behavior)
            for sub in subs_sorted:
                if sub.endswith('.DRIFT.srt') or sub.endswith('.FAILED.srt'):
                    continue
                    
                ext = os.path.splitext(sub)[1].lower()
                
                # Determine output filename (series vs standard naming)
                if SERIES_MODE:
                    sxxexx_code = extract_sxxexx_code(video)
                    if sxxexx_code:
                        # Check if video filename already contains the episode code
                        if sxxexx_code.lower() in video_basename.lower():
                            # Video already has SxxExx in name, use standard naming
                            output_sub = f"{video_basename}.{lang}{ext}"
                        else:
                            # Video doesn't have SxxExx, add it BEFORE language (for media player compatibility)
                            output_sub = f"{video_basename}.{sxxexx_code}.{lang}{ext}"
                    else:
                        output_sub = f"{video_basename}.{lang}{ext}"
                else:
                    output_sub = f"{video_basename}.{lang}{ext}"
                
                if os.path.exists(output_sub):
                    found_good = True
                    break
                
                if not logged_video_context:
                    print_and_log(f"➤ {os.path.basename(video)}", log_only=True)
                    logged_video_context = True
                
                print_and_log(f"{Fore.YELLOW}Synchronizing {os.path.basename(sub)} {Fore.LIGHTYELLOW_EX}[{lang.upper()}]{Style.RESET_ALL}")
                
                sync_success, offset_seconds, correlation_score = synchronize_subtitle_with_ffsubsync(video, sub, output_sub)
                
                if sync_success:
                    # Reject low/negative correlation scores (empty or mismatched subtitle)
                    if correlation_score < 2500:
                        if not is_last_part_for_code:
                            print_and_log(f"{sync_tag()} {Fore.CYAN}Correlation score too low ({correlation_score:.0f}) - multi-part episode, leaving candidate for remaining part(s) instead of marking as DRIFT{Style.RESET_ALL}")
                            try:
                                os.remove(output_sub)
                            except Exception:
                                pass
                            continue
                        print_and_log(f"{sync_tag()} {Fore.RED}⚠ Correlation score too low ({correlation_score:.0f}) - likely empty or mismatched subtitle, marking as DRIFT{Style.RESET_ALL}")
                        
                        try:
                            os.remove(output_sub)
                            mark_subtitle_as_drift(sub, lang, create_copies=False)
                            drift_subs.append(sub)
                            try:
                                save_drift_subtitle_metadata(DRIFT_METADATA_FILE, sub, 0.0, float(correlation_score), 0, float(offset_seconds), rejected=True)
                            except Exception:
                                pass
                            continue
                        except Exception as e:
                            print_and_log(f"{sync_tag()} {Fore.RED}Error handling negative score: {str(e)}{Style.RESET_ALL}")
                            continue
                    
                    if offset_seconds > REJECT_OFFSET_THRESHOLD:
                        if not is_last_part_for_code:
                            print_and_log(f"{sync_tag()} {Fore.CYAN}High offset detected ({offset_seconds:.3f}s) - multi-part episode, leaving candidate for remaining part(s) instead of marking as DRIFT{Style.RESET_ALL}")
                            try:
                                os.remove(output_sub)
                            except Exception:
                                pass
                            continue
                        print_and_log(f"{sync_tag()} {Fore.RED}⚠ High offset detected ({offset_seconds:.3f}s > {REJECT_OFFSET_THRESHOLD}s) - marking as DRIFT{Style.RESET_ALL}")
                        
                        try:
                            os.remove(output_sub)
                            mark_subtitle_as_drift(sub, lang, create_copies=False)  
                            drift_subs.append(sub)
                            try:
                                _q = calculate_quality_score(offset_seconds, correlation_score)
                                save_drift_subtitle_metadata(DRIFT_METADATA_FILE, sub, _q, float(correlation_score), 0, float(offset_seconds), rejected=True)
                            except Exception:
                                pass
                            continue
                        except Exception as e:
                            print_and_log(f"{sync_tag()} {Fore.RED}Error handling high offset: {str(e)}{Style.RESET_ALL}")
                            continue
                            
                    elif offset_seconds > ACCEPT_OFFSET_THRESHOLD:
                        # First-match requires manual verification for all non-excellent syncs
                        print_and_log(f"{sync_tag()} {Fore.YELLOW}[>>] Synchronized ({offset_seconds:.3f}s offset) - requires manual verification{Style.RESET_ALL}")
                        
                        try:
                            add_offset_entry(video, video_dir, lang, output_sub, [offset_seconds], anchor_path, [os.path.basename(sub)], correlation_score)
                        except Exception as e:
                            print_and_log(f"{sync_tag()} {Fore.RED}Error adding offset entry: {str(e)}{Style.RESET_ALL}")
                            
                    else:
                        print_and_log(f"{sync_tag()} {Fore.GREEN}Synchronized with excellent precision ({offset_seconds:.3f}s ≤ {ACCEPT_OFFSET_THRESHOLD}s){Style.RESET_ALL}")
                    
                    found_good = True
                    successful_syncs += 1
                    successful_syncs_per_lang[lang] = successful_syncs_per_lang.get(lang, 0) + 1
                    processed_subs.add(sub)
                    
                    cleanup_drift_and_failed(video_dir, lang, keep_file=output_sub, clean_drifts=True, video=video, clean_numbered=is_last_part_for_code)
                    
                    break
                else:
                    print_and_log(f"{sync_tag()} {Fore.RED}✗ Synchronization failed for {os.path.basename(sub)}{Style.RESET_ALL}")
                    
                    # Clean up empty output file FFSubSync may have created on failure
                    if os.path.exists(output_sub) and os.path.getsize(output_sub) == 0:
                        try:
                            os.remove(output_sub)
                        except Exception:
                            pass
                    
                    base_name = os.path.splitext(sub)[0]
                    failed_name = f"{base_name}.FAILED{ext}"
                    
                    try:
                        os.rename(sub, failed_name)
                        print_and_log(f"{sync_tag()} {Fore.YELLOW}Marked as FAILED: {os.path.basename(failed_name)}{Style.RESET_ALL}")
                        try:
                            save_drift_subtitle_metadata(DRIFT_METADATA_FILE, sub, 0.0, 0.0, 0, 0.0, rejected=True)
                        except Exception:
                            pass
                    except Exception as e:
                        print_and_log(f"{sync_tag()} {Fore.RED}Could not rename to FAILED: {str(e)}{Style.RESET_ALL}")
        
        if not found_good:
            all_current_drifted = all(f.endswith('.DRIFT.srt') or f.endswith('.FAILED.srt') 
                                    for f in [os.path.basename(s) for s in subs_sorted])
            
            # In series mode, only count DRIFT files for THIS episode to avoid
            # triggering acquisition loops caused by other episodes' DRIFT markers
            # sharing the same season folder.
            if SERIES_MODE and current_episode_code:
                existing_drifts = [f for f in os.listdir(video_dir)
                                 if f.endswith('.DRIFT.srt') and f'.{lang}.' in f
                                 and f'.{current_episode_code}.' in f]
            else:
                existing_drifts = [f for f in os.listdir(video_dir) 
                                 if f.endswith('.DRIFT.srt') and f'.{lang}.' in f]
            
            if (all_current_drifted and subs_sorted) or existing_drifts:
                # Don't trigger acquisition if this lang is indefinitely skipped for this video —
                # the DRIFT files are leftover noise and acquisition would do nothing anyway.
                _skipped_movies = get_skipped_movies_from_config()
                _video_key = str(Path(video).resolve())
                _lang_is_skipped = lang in _skipped_movies.get(_video_key, set())
                if not _lang_is_skipped:
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
    print_and_log(f"{sync_tag()} {Fore.GREEN}Synchronization completed successfully{' - cleaning up remaining DRIFT files' if not SMART_SYNC else ''}{Style.RESET_ALL}")
    if not SMART_SYNC:
        # First Match mode: remove all leftover DRIFT files (they were used as skip-markers only)
        for video in videos:
            video_dir = os.path.dirname(video)
            for lang in LANGUAGES:
                for f in os.listdir(video_dir):
                    is_drift = False
                    
                    # Series-aware DRIFT detection
                    if SERIES_MODE:
                        sxxexx_code = extract_sxxexx_code(video)
                        if sxxexx_code:
                            # Series pattern: *.lang.number*.S01E02.DRIFT.srt
                            if re.match(rf".*\.{lang}\.number\d+\.{re.escape(sxxexx_code)}\.DRIFT\.srt$", f, re.IGNORECASE):
                                is_drift = True
                    
                    # Fallback to movie mode pattern
                    if not is_drift and re.match(rf".*\.{lang}\.number\d+\.DRIFT\.srt$", f, re.IGNORECASE):
                        is_drift = True
                    
                    if is_drift:
                        try:
                            drift_path = os.path.join(video_dir, f)
                            os.remove(drift_path)
                            print_and_log(f"{sync_tag()} {Fore.YELLOW}Final cleanup: removed DRIFT: {f}{Style.RESET_ALL}")
                        except Exception as e:
                            print_and_log(f"{sync_tag()} {Fore.RED}Could not remove DRIFT {f}: {e}{Style.RESET_ALL}")
    # Smart Sync: DRIFT files are intentionally kept as batch markers for acquisition.
    # Note: DRIFT_METADATA_FILE is kept until manual verification is fully done — it feeds
    # the Q/C/bonus info shown when browsing DRIFT candidates in the verification menu.
all_subs_present = True
missing_langs = set()
missing_details = {}
missing_per_video = {}
if SERIES_MODE:
    for code, video in sxxexx_to_video.items():
        video_basename, _ = os.path.splitext(video)
        for lang in LANGUAGES:
            found = False
            
            # Check standard naming: filename.lang.srt
            expected_standard = f"{video_basename}.{lang}.srt"
            if os.path.exists(expected_standard):
                found = True
            
            # Check series naming
            if not found:
                sxxexx_code = extract_sxxexx_code(video)
                if sxxexx_code:
                    # Check if video filename already contains the episode code
                    if sxxexx_code.lower() in video_basename.lower():
                        # Video already has SxxExx in name, subtitle should use standard naming
                        expected_series = f"{video_basename}.{lang}.srt"
                    else:
                        # Video doesn't have SxxExx, subtitle should have SxxExx before language
                        expected_series = f"{video_basename}.{sxxexx_code}.{lang}.srt"
                    
                    if os.path.exists(expected_series):
                        found = True
            
            if not found:
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

def ensure_quality_scores_in_offset_file():
    """Add Quality score to entries in offset file that are missing it."""
    if not os.path.exists(MOVIES_WITH_LINEAR_OFFSET_FILE):
        return
    
    try:
        with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split entries by delimiter
        if '\n--\n' not in content:
            return
        
        parts = content.split('\n--\n')
        header = parts[0] + '\n--\n'
        
        updated_entries = []
        changes_made = False
        
        for part in parts[1:]:
            if not part.strip():
                continue
            
            entry = part.strip()
            lines = entry.split('\n')
            
            # Check if Quality line exists
            has_quality = any(line.startswith('Quality:') for line in lines)
            
            if not has_quality:
                # Parse entry to get offset and correlation
                entry_data = {}
                
                # Try NEW format first (key:value pairs)
                for line in lines:
                    if ':' in line and not line.startswith('00:'):  # Skip timestamps
                        key, value = line.split(':', 1)
                        entry_data[key.strip()] = value.strip()
                
                # Fall back to OLD format if no keys found
                offset_str = entry_data.get('Offset', '').replace('s', '').strip()
                correlation_str = entry_data.get('Correlation', '').strip()
                
                if not offset_str and len(lines) > 4:
                    offset_str = lines[4].strip()  # Line 4 in old format
                if not correlation_str and len(lines) > 5:
                    correlation_str = lines[5].strip()  # Line 5 in old format
                
                try:
                    offset = float(offset_str)
                    correlation = float(correlation_str)
                    quality_score = calculate_quality_score(offset, correlation)
                    quality_label = "Excellent" if quality_score >= 80 else "Good" if quality_score >= 65 else "Decent" if quality_score >= 50 else "Poor"
                    
                    # Add Quality line to entry
                    entry += f"\nQuality: {quality_label} ({quality_score:.0f}/100)"
                    changes_made = True
                except:
                    pass  # Skip if can't calculate
            
            updated_entries.append(entry)
        
        # Write back if changes were made
        if changes_made:
            with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'w', encoding='utf-8') as f:
                f.write(header)
                for entry in updated_entries:
                    f.write(entry)
                    f.write('\n--\n')
            print_and_log(f"{sync_tag()} {Fore.GREEN}Added missing Quality scores to offset file entries{Style.RESET_ALL}")
    
    except Exception as e:
        print_and_log(f"{sync_tag()} {Fore.YELLOW}Warning: Could not update Quality scores: {e}{Style.RESET_ALL}")

def sync_auto_accept_with_config():
    """Sync auto-accepted and manual verification lists based on current config thresholds."""
    print_and_log(f"{sync_tag()} {Fore.CYAN}Syncing auto-accept list with config (threshold: {AUTO_ACCEPT_SCORE:.0f})...{Style.RESET_ALL}")
    
    # Read both files
    auto_accepted_entries = []
    manual_offset_entries = []
    
    # Parse auto_accepted_movies.txt
    if os.path.exists(AUTO_ACCEPTED_FILE):
        try:
            with open(AUTO_ACCEPTED_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            auto_accepted_entries = [line.strip() for line in lines 
                                    if line.strip() and not line.startswith('Auto-accepted') 
                                    and not line.startswith('Format:') 
                                    and not line.startswith('=')
                                    and not line.startswith('--')]
            print_and_log(f"{sync_tag()} Found {len(auto_accepted_entries)} auto-accepted entries")
        except Exception as e:
            print_and_log(f"{sync_tag()} {Fore.YELLOW}Warning: Could not read auto-accepted file: {e}{Style.RESET_ALL}")
    
    # Parse movies_with_linear_offset.txt
    if os.path.exists(MOVIES_WITH_LINEAR_OFFSET_FILE):
        try:
            with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split entries by delimiter (format is "\n--\n" between entries)
            if '\n--\n' in content:
                parts = content.split('\n--\n')
                for part in parts[1:]:  # Skip header
                    if part.strip():
                        manual_offset_entries.append(part.strip())
            print_and_log(f"{sync_tag()} Found {len(manual_offset_entries)} manual offset entries")
        except Exception as e:
            print_and_log(f"{sync_tag()} {Fore.YELLOW}Warning: Could not read offset file: {e}{Style.RESET_ALL}")
    
    # Track what to move
    to_auto_accept = []  # From manual -> auto-accepted
    to_manual_verify = []  # From auto-accepted -> manual
    
    # Check manual offset entries: can any be auto-accepted now?
    checked_count = 0
    for entry in manual_offset_entries:
        # Parse entry fields - support OLD format (positional) and NEW format (key:value)
        lines = entry.split('\n')
        entry_data = {}
        
        # Try new format first (key:value pairs)
        for line in lines:
            if ':' in line and not line.startswith('00:'):  # Skip timestamp lines
                key, value = line.split(':', 1)
                entry_data[key.strip()] = value.strip()
        
        # Extract values - try new format first, fall back to old format
        try:
            # Movie name
            name = entry_data.get('Name', lines[0] if len(lines) > 0 else 'Unknown')
            
            # Offset (line 4 in old format, or Offset: key in new format)
            offset_str = entry_data.get('Offset', '').replace('s', '').strip()
            if not offset_str and len(lines) > 4:
                offset_str = lines[4].strip()
            
            # Correlation (line 5 in old format, or Correlation: key in new format)
            correlation_str = entry_data.get('Correlation', '').strip()
            if not correlation_str and len(lines) > 5:
                correlation_str = lines[5].strip()
            
            # Rejected count (line 8 in old format: "Rejected: X")
            rejected_str = entry_data.get('Rejected', '0').strip()
            batch_size_str = entry_data.get('BatchSize', '0').strip()
            
            # IMDb match (line 9 in old format: "IMDb_match: yes")
            imdb_match = entry_data.get('IMDb_match', 'unknown').strip()
            
            if not offset_str or not correlation_str:
                continue
            
            offset = float(offset_str)
            correlation = float(correlation_str)
            rejected_count = int(rejected_str)
            batch_size = int(batch_size_str) if int(batch_size_str) > 0 else MAX_SEARCH_RESULTS
            reject_threshold = math.ceil(batch_size / 2)
            
            # Calculate quality score
            quality_score = calculate_quality_score(offset, correlation)
            
            checked_count += 1
            
            # Check if this meets auto-accept criteria
            meets_criteria = (
                quality_score >= AUTO_ACCEPT_SCORE and
                (not REQUIRE_IMDB_VALIDATION or imdb_match == 'yes') and
                (not COUNT_REJECTED or rejected_count <= reject_threshold)
            )
            
            # Debug: show why entries don't qualify
            if quality_score >= AUTO_ACCEPT_SCORE - 10 and not meets_criteria:
                reasons = []
                if quality_score < AUTO_ACCEPT_SCORE:
                    reasons.append(f"score {quality_score:.0f} < {AUTO_ACCEPT_SCORE:.0f}")
                if REQUIRE_IMDB_VALIDATION and imdb_match != 'yes':
                    reasons.append(f"IMDb={imdb_match}")
                if COUNT_REJECTED and rejected_count > reject_threshold:
                    reasons.append(f"rejected={rejected_count}")
                print_and_log(f"{sync_tag()}   {name[:40]}: score={quality_score:.0f} - NOT auto-accepted ({', '.join(reasons)})")
            
            if meets_criteria:
                # This should be auto-accepted now
                # Extract language - from Language: key (new format) or from name [XX] (old format)
                lang = entry_data.get('Language', '')
                if not lang and '[' in name and ']' in name:
                    # Extract from name like "Movie [EN]"
                    lang_start = name.rfind('[')
                    lang_end = name.rfind(']')
                    if lang_start >= 0 and lang_end > lang_start:
                        lang = name[lang_start+1:lang_end].strip().lower()
                
                if name and lang:
                    # Remove [LANG] from name if present (old format)
                    clean_name = name
                    if '[' in name and ']' in name:
                        lang_start = clean_name.rfind('[')
                        lang_end = clean_name.rfind(']')
                        if lang_start >= 0 and lang_end > lang_start:
                            # Check if it's a language code (2-3 letters)
                            potential_lang = clean_name[lang_start+1:lang_end].strip()
                            if len(potential_lang) <= 3:
                                clean_name = clean_name[:lang_start].strip()
                    
                    # Format for auto-accepted file: "Name [LANG] | offset | correlation"
                    auto_entry = f"{clean_name} [{lang.upper()}] | {offset_str}s | {correlation_str}"
                    to_auto_accept.append((entry, auto_entry))
        except Exception:
            continue  # Skip malformed entries
    
    print_and_log(f"{sync_tag()} Checked {checked_count} manual entries for auto-accept eligibility")
    
    # Check auto-accepted entries: should any be moved to manual verify?
    for entry in auto_accepted_entries:
        if '|' not in entry:
            continue
        
        parts = entry.split('|')
        if len(parts) < 3:
            continue
        
        try:
            title_lang = parts[0].strip()
            offset_str = parts[1].strip().replace('s', '').strip()
            correlation_str = parts[2].strip()
            
            offset = float(offset_str)
            correlation = float(correlation_str)
            quality_score = calculate_quality_score(offset, correlation)
            
            # Auto-accepted entries always have: rejected=0, imdb_match=yes
            # So we only need to check quality score threshold
            if quality_score < AUTO_ACCEPT_SCORE:
                # This no longer meets criteria - needs manual verification
                print_and_log(f"{sync_tag()}   {title_lang}: score={quality_score:.0f} - Moving to manual verification (below threshold {AUTO_ACCEPT_SCORE})")
                
                # Extract movie name and language
                if '[' in title_lang and ']' in title_lang:
                    lang_start = title_lang.rfind('[')
                    lang_end = title_lang.rfind(']')
                    movie_name = title_lang[:lang_start].strip()
                    lang = title_lang[lang_start+1:lang_end].strip().lower()
                    
                    # Try to find the video file and get path + first_line
                    video_path, video_name = find_video_by_name(movie_name, videos)
                    
                    if video_path:
                        # Found the video - get path and first_line
                        try:
                            anchor_path_for_rel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            # Try relative path, but use absolute if on different drives
                            try:
                                rel_video_path = os.path.relpath(video_path, anchor_path_for_rel)
                                path_str = rel_video_path
                            except ValueError:
                                # Different drives - use absolute path
                                path_str = video_path
                            
                            # Find subtitle file
                            video_basename = os.path.splitext(video_path)[0]
                            subtitle_path = f"{video_basename}.{lang}.srt"
                            
                            if os.path.exists(subtitle_path):
                                try:
                                    first_time, first_line = get_first_line_and_time(subtitle_path)
                                    first_line_str = first_line if first_line else "N/A"
                                except:
                                    first_line_str = "N/A"
                            else:
                                first_line_str = "N/A"
                        except Exception as path_err:
                            # If path/first_line lookup fails, use placeholders but still create entry
                            print_and_log(f"{sync_tag()}   WARNING: Could not get path/first_line for {movie_name}: {path_err}")
                            path_str = "(from config change)"
                            first_line_str = "N/A"
                    else:
                        # Video not found - use placeholders
                        path_str = "(from config change)"
                        first_line_str = "N/A"
                    
                    # Create manual verification entry with quality score
                    quality_label = "Excellent" if quality_score >= 80 else "Good" if quality_score >= 65 else "Decent" if quality_score >= 50 else "Poor"
                    
                    manual_entry = f"Name: {movie_name}\n"
                    manual_entry += f"Path: {path_str}\n"
                    manual_entry += f"Offset: {offset_str}s\n"
                    manual_entry += f"Correlation: {correlation_str}\n"
                    manual_entry += f"Language: {lang}\n"
                    manual_entry += f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    manual_entry += f"First_line: {first_line_str}\n"
                    manual_entry += f"Rejected: 0\n"
                    manual_entry += f"IMDb_match: yes\n"
                    manual_entry += f"Quality: {quality_label} ({quality_score:.0f}/100)\n"
                    
                    to_manual_verify.append((entry, manual_entry))
        except Exception as e:
            print_and_log(f"{sync_tag()}   ERROR checking auto-accept entry: {e}")
            continue
    
    # Always clean up and sort auto-accepted entries (even if no new changes)
    # Update list with any new entries
    if to_auto_accept or to_manual_verify:
        new_auto_accepted = [e for e in auto_accepted_entries if not any(e == old for old, new in to_manual_verify)]
        new_auto_accepted.extend([new for old, new in to_auto_accept])
    else:
        new_auto_accepted = auto_accepted_entries
    
    # Clean up duplicate [LANG] tags in ALL entries
    cleaned_entries = []
    for entry in new_auto_accepted:
        if '|' not in entry:
            cleaned_entries.append(entry)
            continue
        
        parts = entry.split('|')
        if len(parts) < 3:
            cleaned_entries.append(entry)
            continue
        
        title_lang = parts[0].strip()
        offset_part = parts[1].strip()
        correlation_part = parts[2].strip()
        
        # Check for duplicate [LANG] tags like "Movie [EN] [EN]"
        if title_lang.count('[') > 1 and title_lang.count(']') > 1:
            # Extract language from last occurrence
            lang_start = title_lang.rfind('[')
            lang_end = title_lang.rfind(']')
            if lang_start >= 0 and lang_end > lang_start:
                lang = title_lang[lang_start+1:lang_end].strip()
                # Remove all [LANG] occurrences and rebuild
                clean_name = title_lang
                while '[' in clean_name and ']' in clean_name:
                    bracket_start = clean_name.rfind('[')
                    bracket_end = clean_name.rfind(']')
                    if bracket_start >= 0 and bracket_end > bracket_start:
                        potential_lang = clean_name[bracket_start+1:bracket_end].strip()
                        if len(potential_lang) <= 3:  # Language code
                            clean_name = clean_name[:bracket_start].strip()
                        else:
                            break
                title_lang = f"{clean_name} [{lang}]"
        
        cleaned_entries.append(f"{title_lang} | {offset_part} | {correlation_part}")
    
    # Sort by quality score (highest first)
    entries_with_scores = []
    for entry in cleaned_entries:
        if '|' not in entry:
            continue
        parts = entry.split('|')
        if len(parts) < 3:
            continue
        try:
            offset_str = parts[1].strip().replace('s', '').strip()
            correlation_str = parts[2].strip()
            offset = float(offset_str)
            correlation = float(correlation_str)
            quality_score = calculate_quality_score(offset, correlation)
            entries_with_scores.append((quality_score, entry))
        except:
            entries_with_scores.append((0, entry))
    
    # Sort by score descending
    entries_with_scores.sort(key=lambda x: x[0], reverse=True)
    sorted_entries = [entry for score, entry in entries_with_scores]
    
    # Always write the cleaned and sorted file
    with open(AUTO_ACCEPTED_FILE, 'w', encoding='utf-8') as f:
        f.write("Auto-accepted subtitles from Smart Sync\n")
        f.write("Format: Movie Name (Year) [LANG] | offset | correlation_score\n")
        f.write("=" * 80 + "\n\n")
        for entry in sorted_entries:
            f.write(entry + "\n")
    
    # Update movies_with_linear_offset.txt (only if changes)
    if to_auto_accept or to_manual_verify:
        # Remove entries that moved to auto-accept
        new_manual_entries = [e for e in manual_offset_entries if not any(e == old for old, new in to_auto_accept)]
        # Add entries from auto-accept that need manual verify (add at TOP)
        entries_from_auto = [new for old, new in to_manual_verify]
        
        # Rebuild offset file
        if os.path.exists(MOVIES_WITH_LINEAR_OFFSET_FILE):
            with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            # Extract header
            if '\n--\n' in content:
                header = content.split('\n--\n', 1)[0] + '\n--\n'
            else:
                header = "Linear offset tracking file for movies with subtitle sync corrections.\n"
                header += "Format: movie name, path, offset, timestamp, first line, rejected count\n--\n"
        else:
            header = "Linear offset tracking file for movies with subtitle sync corrections.\n"
            header += "Format: movie name, path, offset, timestamp, first line, rejected count\n--\n"
        
        with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'w', encoding='utf-8') as f:
            f.write(header)
            # Add entries from auto-accept first (at top)
            for entry in entries_from_auto:
                f.write(entry)
                f.write("\n--\n")
            # Then add remaining manual entries
            for entry in new_manual_entries:
                f.write(entry)
                f.write("\n--\n")
        
        # Log changes
        if to_auto_accept:
            print_and_log(f"{sync_tag()} {Fore.GREEN}Config sync: Moved {len(to_auto_accept)} subtitle(s) to auto-accepted (now meet threshold){Style.RESET_ALL}")
        if to_manual_verify:
            print_and_log(f"{sync_tag()} {Fore.YELLOW}Config sync: Moved {len(to_manual_verify)} subtitle(s) to manual verification (below threshold){Style.RESET_ALL}")
    else:
        print_and_log(f"{sync_tag()} No changes needed - all entries already in correct list")

def show_auto_accepted_summary():
    """Display summary screen of auto-accepted subtitles before manual verification."""
    if not os.path.exists(AUTO_ACCEPTED_FILE):
        return False
    
    # Loop until user chooses to continue (option 2)
    while True:
        with open(AUTO_ACCEPTED_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Filter out header lines and separator lines
        entries = [line.strip() for line in lines 
                   if line.strip() 
                   and not line.startswith('Auto-accepted') 
                   and not line.startswith('Format:') 
                   and not line.startswith('=')
                   and not line.startswith('--')]
        
        if not entries:
            return False
        
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"{Style.BRIGHT}{Fore.GREEN}Auto-Accepted Subtitles{Style.RESET_ALL}\n")
        print_and_log(f"The following subtitles were automatically accepted:")
        print_and_log(f"  • Quality score ≥ {AUTO_ACCEPT_SCORE:.0f}/100")
        if REQUIRE_IMDB_VALIDATION:
            print_and_log(f"  • IMDb match found")
        if COUNT_REJECTED:
            print_and_log(f"  • Not more than 50% of batch rejected\n")
        else:
            print_and_log("")
        
        # Display each entry with numbering (format: "Movie Name (Year) [LANG] | offset | score")
        entry_data = []  # Store parsed entry data for later use
        for idx, entry in enumerate(entries, 1):
            if '|' in entry:
                parts = entry.split('|')
                if len(parts) >= 3:
                    title = parts[0].strip()
                    offset_str = parts[1].strip()
                    correlation_score = parts[2].strip()
                    
                    # Parse offset to calculate quality score
                    try:
                        offset = float(offset_str.replace('s', '').strip())
                        score = float(correlation_score)
                        bonus = int(parts[4].strip()) if len(parts) >= 5 else 0
                        quality_score = calculate_quality_score(offset, score)
                        quality_tier, tier_color = get_quality_tier(quality_score)
                        score_display = f"{quality_score}+{bonus}" if bonus > 0 else f"{quality_score:.0f}"
                        
                        print_and_log(f"[{Fore.YELLOW}{idx}{Style.RESET_ALL}]  {Fore.CYAN}{title}{Style.RESET_ALL}  •  Quality: {tier_color}{score_display}/100 {quality_tier}{Style.RESET_ALL}  •  Confidence: {Fore.GREEN}{score:,.0f}{Style.RESET_ALL}  •  Offset: {offset_str}")
                        entry_data.append((title, offset_str, score))
                    except:
                        # Fallback if parsing fails
                        print_and_log(f"[{Fore.YELLOW}{idx}{Style.RESET_ALL}]  {Fore.CYAN}{title}{Style.RESET_ALL}  •  Offset: {offset_str}  •  Score: {correlation_score}")
                        entry_data.append((title, offset_str, None))
        
        print_and_log(f"\n{Fore.GREEN}Total: {len(entries)} subtitle(s) auto-accepted{Style.RESET_ALL}\n")
        
        # Prompt user for action
        print_and_log(f"{Fore.LIGHTGREEN_EX}1{Style.RESET_ALL} = Approve of all auto-accepted subtitles and continue")
        print_and_log(f"{Fore.LIGHTYELLOW_EX}2{Style.RESET_ALL} = Move specific subtitles to manual verification (enter numbers like 1,5,18)\n")
        
        choice = input_and_log(f"\n{Fore.LIGHTYELLOW_EX}Choose option (1 or 2){Style.RESET_ALL}, or press {Fore.LIGHTYELLOW_EX}enter{Style.RESET_ALL} to continue: ").strip()
        
        if choice == "2":
            # User wants to select specific entries for manual verification
            while True:
                selection = input_and_log(f"\n{Fore.LIGHTYELLOW_EX}Enter the number(s) to move to manual verification (e.g. 1,2,4){Style.RESET_ALL}, or press {Fore.LIGHTYELLOW_EX}enter{Style.RESET_ALL} to cancel: ").strip()
                
                if not selection:
                    print_and_log(f"{Fore.YELLOW}No entries selected. Returning to menu.{Style.RESET_ALL}")
                    break
                
                # Validate input format (only comma-separated numbers allowed)
                if not re.fullmatch(r"\d+(,\d+)*", selection):
                    print_and_log(f"{Fore.RED}Invalid input. Only comma-separated numbers are allowed (e.g. 1,2,4). Try again.{Style.RESET_ALL}")
                    continue
                
                # Parse and validate indices
                raw_indices = selection.split(',')
                indices = []
                for s in raw_indices:
                    idx_num = int(s)
                    if 1 <= idx_num <= len(entries):
                        if idx_num not in indices:
                            indices.append(idx_num)
                    else:
                        print_and_log(f"{Fore.RED}Invalid number: {idx_num}. Must be between 1 and {len(entries)}.{Style.RESET_ALL}")
                
                if not indices:
                    print_and_log(f"{Fore.RED}No valid entries selected. Try again.{Style.RESET_ALL}")
                    continue
                
                # Move selected entries to manual verification
                indices.sort()  # Process in order
                selected_entries = [entries[i-1] for i in indices]
                
                # Add selected entries to the TOP of the manual offset file
                move_entries_to_manual_verification(selected_entries)
                
                # Remove selected entries from auto-accepted file
                remaining_entries = [entry for idx, entry in enumerate(entries, 1) if idx not in indices]
                
                # Update AUTO_ACCEPTED_FILE
                with open(AUTO_ACCEPTED_FILE, 'w', encoding='utf-8') as f:
                    f.write("Auto-accepted subtitles from Smart Sync\n")
                    f.write("Format: Movie Name (Year) [LANG] | offset | correlation_score | video_basename\n")
                    f.write("=" * 80 + "\n\n")
                    for entry in remaining_entries:
                        f.write(entry + "\n")
                
                print_and_log(f"{Fore.YELLOW}Remaining auto-accepted: {len(remaining_entries)} subtitle(s){Style.RESET_ALL}\n")
                
                if len(remaining_entries) == 0:
                    print_and_log(f"{Fore.YELLOW}All entries have been moved to manual verification.{Style.RESET_ALL}")
                    print_and_log(f"Press any key to continue...")
                    input()
                    return False  # No more auto-accepted entries
                
                # Wait for user to read the message
                print_and_log(f"{Fore.WHITE}Press any key to continue...{Style.RESET_ALL}")
                input()
                
                # Clear screen and show refresh message
                os.system('cls' if os.name == 'nt' else 'clear')
                print_and_log(f"{Fore.CYAN}Refreshing list...{Style.RESET_ALL}")
                time.sleep(0.5)
                break
            
            # Continue outer loop to show refreshed list
            continue
        
        # Option 1 or just pressing enter - continue normally
        print_and_log(f"Press any key to continue...")
        input()
        return True

def remove_completed_entries_from_offset_file():
    """Remove entries from offset file where subtitles already exist (completed from previous runs)."""
    if not os.path.exists(MOVIES_WITH_LINEAR_OFFSET_FILE):
        return
    
    try:
        # Read offset file
        with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by entry delimiter
        entries = content.split('--\n')
        header = entries[0] if entries else ""
        
        # Filter entries: keep only those where subtitle doesn't exist
        filtered_entries = [header]
        removed_count = 0
        
        for entry in entries[1:]:
            if not entry.strip():
                continue
            
            lines = entry.strip().split('\n')
            if len(lines) >= 4:
                # Line 2 is folder path, line 3 is subtitle filename
                folder_path = lines[1].strip()
                subtitle_file = lines[3].strip()
                
                # Full subtitle path
                subtitle_path = os.path.join(folder_path, subtitle_file)
                
                # Check if subtitle exists
                if os.path.exists(subtitle_path):
                    removed_count += 1
                else:
                    filtered_entries.append(entry)
            else:
                # Malformed entry, keep it
                filtered_entries.append(entry)
        
        # Write back filtered content
        if removed_count > 0:
            with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'w', encoding='utf-8') as f:
                f.write('--\n'.join(filtered_entries))
            
            print_and_log(f"{sync_tag()} {Fore.GREEN}Removed {removed_count} completed entry/entries from offset file (subtitles already exist){Style.RESET_ALL}")
    
    except Exception as e:
        print_and_log(f"{sync_tag()} {Fore.YELLOW}Warning: Could not clean up offset file: {e}{Style.RESET_ALL}")

def remove_auto_accepted_from_offset_file():
    """Remove auto-accepted entries from movies_with_linear_offset.txt to avoid duplicate verification."""
    if not os.path.exists(AUTO_ACCEPTED_FILE) or not os.path.exists(MOVIES_WITH_LINEAR_OFFSET_FILE):
        return
    
    try:
        # Read auto-accepted entries (format: "Movie Name (Year) [LANG] | offset | score | video_basename")
        # Build a set of (title_with_lang, video_basename) tuples for precise matching
        auto_accepted_entries = set()  # (title_with_lang, video_basename or None)
        with open(AUTO_ACCEPTED_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('Auto-accepted') and not line.startswith('Format:') and not line.startswith('--'):
                    if '|' in line:
                        parts = [p.strip() for p in line.split('|')]
                        title_with_lang = parts[0].strip()
                        # New format includes video_basename as 4th field
                        video_basename = parts[3].strip() if len(parts) >= 4 else None
                        auto_accepted_entries.add((title_with_lang, video_basename))
        
        if not auto_accepted_entries:
            return
        
        # Read offset file and filter out auto-accepted entries
        with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by entry delimiter
        entries = content.split('--\n')
        header = entries[0] if entries else ""
        
        # Filter entries: keep only those NOT in auto_accepted_titles
        filtered_entries = [header]
        removed_count = 0
        
        for entry in entries[1:]:
            if not entry.strip():
                continue
            
            # First line is the title with [LANG], third line is the video filename
            lines = entry.strip().split('\n')
            if lines:
                title_line = lines[0].strip()
                # Line index 2 is the video filename in the offset file format
                offset_video = lines[2].strip() if len(lines) > 2 else None
                
                # Check if this entry matches an auto-accepted entry
                # Match on both title+lang AND video filename for precision (series)
                is_match = False
                for (auto_title, auto_video) in auto_accepted_entries:
                    if auto_video and offset_video:
                        # Exact match on video filename (most precise)
                        if offset_video == auto_video:
                            is_match = True
                            break
                    else:
                        # Fallback: match on title+lang only (movies, old format)
                        title_base = title_line.replace('.mkv', '').replace('.mp4', '').replace('.avi', '')
                        auto_base = auto_title.replace('.mkv', '').replace('.mp4', '').replace('.avi', '')
                        if title_base == auto_base:
                            is_match = True
                            break
                
                if not is_match:
                    filtered_entries.append(entry)
                else:
                    removed_count += 1
        
        # Write back filtered content
        if removed_count > 0:
            with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'w', encoding='utf-8') as f:
                f.write('--\n'.join(filtered_entries))
            
            print_and_log(f"{sync_tag()} {Fore.GREEN}Removed {removed_count} auto-accepted entry/entries from offset file{Style.RESET_ALL}")
    
    except Exception as e:
        print_and_log(f"{sync_tag()} {Fore.YELLOW}Warning: Could not remove auto-accepted entries from offset file: {e}{Style.RESET_ALL}")

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
            if len(lines) >= 6 and any(line.endswith(('.mkv', '.mp4', '.avi')) for line in lines):
                # Parse correlation score (line 5, added in newer format)
                correlation_score = "N/A"
                if len(lines) >= 7:
                    correlation_score = lines[5].strip()
                entries.append((entry, correlation_score))
    if not entries:
        return
    
    # Clear screen before showing offset verification menu
    clear_and_print_ascii(BANNER_LINE)
    print_and_log(f"{Style.BRIGHT}{Fore.CYAN}Offset Correction Verification Menu{Style.RESET_ALL}\n")

    print_and_log(f"{Fore.YELLOW}Detected {Style.BRIGHT}{len(entries)}{Style.NORMAL} subtitle file(s) requiring verification.{Style.RESET_ALL}\n")
    
    if SMART_SYNC:
        print_and_log(f"{Fore.CYAN}Smart Sync:{Style.RESET_ALL}")
        print_and_log(f"Subtitles are here for manual verification for one of the following reasons: ")
        print_and_log(f"  • {Fore.YELLOW}Quality score between {AUTO_REJECT_SCORE:.0f}-{AUTO_ACCEPT_SCORE:.0f}{Style.RESET_ALL} (Decent/Poor tier) - not confident enough to auto-accept")
        if COUNT_REJECTED:
            print_and_log(f"  • {Fore.LIGHTRED_EX}More than 50% of batch rejected{Style.RESET_ALL} - too many bad candidates lowers confidence in the winner")
        if REQUIRE_IMDB_VALIDATION:
            print_and_log(f"  • {Fore.LIGHTRED_EX}No IMDb match found{Style.RESET_ALL} - couldn't verify this is the correct movie/episode")
        print_and_log("")
    else:
        print_and_log(f"{Fore.CYAN}First-Match Mode:{Style.RESET_ALL} ALL syncs require manual verification (except excellent < {ACCEPT_OFFSET_THRESHOLD:.3f}s).")
        print_and_log(f"Offset alone doesn't guarantee quality - you must verify subtitle-audio alignment.\n")

    print_and_log(f"{Fore.LIGHTYELLOW_EX}What happens next?{Style.RESET_ALL}")
    print_and_log(f"Subservient goes through each video one by one. For every video, you open it")
    print_and_log(f"and confirm whether the subtitle is well synced, or apply manual corrections.\n")
    print_and_log(f"{Fore.LIGHTYELLOW_EX}Opening videos:{Style.RESET_ALL}")
    print_and_log(f"Videos are opened using {Fore.LIGHTYELLOW_EX}VLC Media Player{Style.RESET_ALL} with the correct subtitle pre-loaded.")
    print_and_log(f"No VLC? It's strongly recommended to download for Subservient. Get it free at {Fore.CYAN}https://www.videolan.org/vlc/{Style.RESET_ALL}\n")
    print_and_log(f"{Fore.LIGHTYELLOW_EX}What to check:{Style.RESET_ALL}")
    print_and_log(f"  • Are subtitles {Fore.GREEN}in sync{Style.RESET_ALL} with the audio? If not, use the correction tool.")
    print_and_log(f"  • Are foreign language lines (e.g. alien/elvish speech) correctly subtitled?")
    print_and_log(f"  • Is the subtitle completely wrong? Mark it as {Fore.YELLOW}Drift{Style.RESET_ALL} to download a new one.\n")
    print_and_log(f"{Fore.GREEN}Press any key to start going through the video files...{Style.RESET_ALL}")
    input()
    
    # Clear screen now, after user confirms
    clear_and_print_ascii(BANNER_LINE)
    show_offset_verification_details()

def open_video_with_default_app(path):
    """Open video file with system default media player."""
    try:
        if sys.platform.startswith('win'):
            # Try different approaches on Windows
            try:
                # First try the standard way
                os.startfile(path)
            except OSError as e:
                # If standard way fails, try with cmd /c start
                if "No application is associated" in str(e):
                    # Try to find and use a specific media player
                    import shutil
                    vlc_path = shutil.which("vlc")
                    if vlc_path:
                        subprocess.run([vlc_path, path], check=False)
                    else:
                        # Fallback to cmd start
                        subprocess.run(['cmd', '/c', 'start', '', path], check=False, shell=True)
                else:
                    raise
        elif sys.platform.startswith('darwin'):
            subprocess.call(['open', path])
        else:
            subprocess.call(['xdg-open', path])
    except Exception as e:
        # Re-raise with more detailed error info
        raise Exception(f"Failed to open video: {str(e)}")

def validate_and_update_offset_file_paths():
    """Validate paths in offset file and update if videos moved to new locations."""
    offset_file = os.path.join(script_dir, 'movies_with_linear_offset.txt')
    if not os.path.exists(offset_file):
        return
    
    with open(offset_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    entries = content.split('\n--\n')
    header = entries[0]
    valid_entries = []
    updates_made = False
    
    for entry_text in entries[1:]:
        if not entry_text.strip():
            continue
            
        lines = entry_text.strip().split('\n')
        if len(lines) < 4:
            continue
            
        title = lines[0]
        folder = lines[1] 
        video = lines[2]
        video_path = os.path.join(folder, video)
        
        # Check if video still exists at recorded location
        if os.path.exists(video_path):
            valid_entries.append(entry_text)
            continue
            
        # Video not found, try to find it in current folder structure
        print_and_log(f"{sync_tag()} {Fore.YELLOW}Video moved: searching for {video}{Style.RESET_ALL}")
        
        found = False
        for root, dirs, files in os.walk(anchor_path):
            if video in files:
                new_folder = root
                new_video_path = os.path.join(new_folder, video)
                
                # Update the entry with new path
                lines[1] = new_folder
                updated_entry = '\n'.join(lines)
                valid_entries.append(updated_entry)
                
                print_and_log(f"{sync_tag()} {Fore.GREEN}Found video at new location: {new_folder}{Style.RESET_ALL}")
                updates_made = True
                found = True
                break
        
        if not found:
            print_and_log(f"{sync_tag()} {Fore.RED}Video not found anywhere, removing from verification list: {video}{Style.RESET_ALL}")
            print_and_log(f"{sync_tag()} {Fore.LIGHTRED_EX}Video '{video}' could not be found. This entry may be a leftover from an old run (e.g. the video was deleted, renamed, or replaced) and has been removed from the verification list.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL}")
            input()
    
    # Rewrite file if updates were made or entries were removed
    if updates_made or len(valid_entries) != len(entries[1:]):
        if valid_entries:
            new_content = header + '\n--\n' + '\n--\n'.join(valid_entries) + '\n--\n'
            with open(offset_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print_and_log(f"{sync_tag()} {Fore.CYAN}Updated offset file with new video locations{Style.RESET_ALL}")
        else:
            # No valid entries left, remove the file
            os.remove(offset_file)
            # Also remove metadata and auto-accepted files
            metadata_file = os.path.join(script_dir, '.subtitle_metadata.txt')
            if os.path.exists(metadata_file):
                os.remove(metadata_file)
            if os.path.exists(AUTO_ACCEPTED_FILE):
                os.remove(AUTO_ACCEPTED_FILE)
            print_and_log(f"{sync_tag()} {Fore.YELLOW}No valid videos found, removed offset verification file{Style.RESET_ALL}")

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
                
                # Also remove from metadata file
                remove_metadata_entry(video, title)
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
            # Also remove metadata and auto-accepted files
            metadata_file = os.path.join(script_dir, '.subtitle_metadata.txt')
            if os.path.exists(metadata_file):
                os.remove(metadata_file)
            if os.path.exists(AUTO_ACCEPTED_FILE):
                os.remove(AUTO_ACCEPTED_FILE)
            print_and_log(f"{sync_tag()} {Fore.LIGHTYELLOW_EX}Offset tracking file deleted - no more entries to track{Style.RESET_ALL}")
            
    except Exception as e:
        print_and_log(f"{sync_tag()} {Fore.RED}Error removing entry from offset file: {str(e)}{Style.RESET_ALL}")

def show_offset_verification_details():
    """Process offset verification entries and prompt user for each video."""
    # First validate and update paths in case videos were moved
    validate_and_update_offset_file_paths()
    
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
        if len(lines) >= 3 and (lines[2].endswith('.mkv') or lines[2].endswith('.mp4') or lines[2].endswith('.avi')):
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
            if l.replace('.', '', 1).replace('-', '', 1).isdigit() or l.startswith('00:') or l.startswith('0:') or l.startswith('Rejected:') or l.startswith('IMDb_match:') or l.startswith('Quality:'):
                break
            subfiles.append(l)
        offset_line_idx = 3 + len(subfiles)
        offset = lines[offset_line_idx]
        correlation_score = lines[offset_line_idx+1] if len(lines) > offset_line_idx+1 else "N/A"
        timestamp = lines[offset_line_idx+2] if len(lines) > offset_line_idx+2 else ''
        
        # Parse rejected count, IMDb status, and quality score
        rejected_count = 0
        imdb_match = "unknown"
        quality_info = None
        for l in lines[offset_line_idx+3:]:
            if l.startswith('Rejected:'):
                try:
                    rejected_count = int(l.split(':')[1].strip())
                except:
                    pass
            elif l.startswith('IMDb_match:'):
                imdb_match = l.split(':')[1].strip()
            elif l.startswith('Quality:'):
                quality_info = l.split(':', 1)[1].strip()  # Keep everything after "Quality:"
        
        # Clear screen before showing verification menu
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"{Fore.LIGHTYELLOW_EX}[{idx}/{len(entries)}] {title}{Style.RESET_ALL}")
        print_and_log(f"{Fore.WHITE}Video folder: {Fore.GREEN}{folder}{Style.RESET_ALL}")
        print_and_log(f"{Fore.WHITE}Video file:   {Fore.GREEN}{video}{Style.RESET_ALL}")
        for sub in subfiles:
            print_and_log(f"{Fore.WHITE}Subtitle:    {Fore.GREEN}{sub}{Style.RESET_ALL}")
        
        # Display quality score with color
        if quality_info:
            # Parse quality tier from string like "Decent (52/100)"
            tier_match = re.match(r'(\w+)\s+\((\d+)/100\)', quality_info)
            if tier_match:
                tier_name = tier_match.group(1)
                score_value = int(tier_match.group(2))
                _, tier_color = get_quality_tier(score_value)
                
                # Format offset and correlation for display
                offset_display = f"{Fore.WHITE}Offset: {offset}{Style.RESET_ALL}" if offset else ""
                correlation_display = f"{Fore.WHITE}Confidence: {correlation_score}{Style.RESET_ALL}" if correlation_score != "N/A" else ""
                
                # Format rejected count and IMDb match
                rejected_color = Fore.RED if rejected_count > 0 else Fore.WHITE
                rejected_display = f"{rejected_color}{rejected_count} rejection{'s' if rejected_count != 1 else ''}{Style.RESET_ALL}"
                if imdb_match.lower() == "yes":
                    imdb_display = f"IMDb: {Fore.GREEN}yes{Style.RESET_ALL}"
                elif imdb_match.lower() == "no":
                    imdb_display = f"IMDb: {Fore.RED}no{Style.RESET_ALL}"
                else:
                    imdb_display = f"IMDb: {Fore.YELLOW}unknown{Style.RESET_ALL}"
                
                # Combine all info on one line
                extra_info = "  |  ".join(filter(None, [offset_display, correlation_display, rejected_display, imdb_display]))
                if extra_info:
                    print_and_log(f"{Fore.WHITE}Quality:     {tier_color}{quality_info}{Style.RESET_ALL}  |  {extra_info}")
                else:
                    print_and_log(f"{Fore.WHITE}Quality:     {tier_color}{quality_info}{Style.RESET_ALL}")
        
        print()
        docker_note = ""
        if is_running_in_docker():
            docker_note = f"Note: Your docker container does not have access to your video player, so you'll need to open the video manually.\n"
        
        vlc_text = (
            f"Choose option 1 to automatically open the video file using your default media player.\n"
            f"{docker_note}"
            f"If you prefer not to, then you can always open the video file manually."
        )
        print_and_log(f"{Fore.WHITE}{vlc_text}{Style.RESET_ALL}")
        
        # Show subtitle info if available
        if subfiles:
            print_and_log(f"\n{Fore.WHITE}Subtitle file(s):{Style.RESET_ALL}")
            for sub in subfiles:
                print_and_log(f"{Fore.CYAN}{folder}{os.sep}{sub}{Style.RESET_ALL}")

        print_and_log(f"{Fore.LIGHTYELLOW_EX}Note: VLC will attempt to auto-load the subtitle file automatically.{Style.RESET_ALL}")
        print()
        skip_entry = False
        while True:
            print_and_log(f"{Fore.LIGHTYELLOW_EX}How would you like to open the video?:{Style.RESET_ALL}")
            print_and_log(f"{Fore.CYAN}1{Style.RESET_ALL} = Automatically open the video using your default media player.")
            print_and_log(f"{Fore.YELLOW}2{Style.RESET_ALL} = I will open the video manually.")
            print_and_log(f"{Fore.GREEN}3{Style.RESET_ALL} = Skip this video, mark as done.")
            choice = input(f"\nChoose [{Fore.CYAN}1{Style.RESET_ALL}/{Fore.YELLOW}2{Style.RESET_ALL}/{Fore.GREEN}3{Style.RESET_ALL}]: ").strip()
            vlc_opened = False
            vlc_method = ""
            clear_and_print_ascii(BANNER_LINE)
            if choice == "3":
                remove_completed_entry_from_offset_file(title, folder, video)
                print_and_log(f"{Fore.GREEN}Marked as done. Moving to next video.{Style.RESET_ALL}")
                skip_entry = True
                break
            elif choice == "1":
                if subfiles:
                    video_path = os.path.join(folder, video)
                    # Find subtitle matching the target language; fall back to first
                    matching_sub = next((s for s in subfiles if f'.{lang.lower()}.' in s.lower()), None)
                    subtitle_path = os.path.join(folder, matching_sub if matching_sub else subfiles[0])
                    
                    # Try to open with VLC (with subtitle auto-loading)
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
                            subprocess.Popen([vlc_path, video_path, f':sub-file={subtitle_path}', '--no-sub-autodetect-file'], 
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            vlc_opened = True
                            vlc_method = "vlc"
                            print_and_log(f"{Fore.GREEN}Video opened in VLC with subtitle auto-loaded. The video should now have started with the subtitle loaded.{Style.RESET_ALL}")

                            print_and_log(f"\n{Fore.LIGHTYELLOW_EX}Did you know?{Style.RESET_ALL}\nIn VLC, press {Fore.CYAN}H{Style.RESET_ALL} or {Fore.CYAN}G{Style.RESET_ALL} to nudge subtitle timing forward or backward.")
                            print_and_log(f"Once perfectly in sync, note the offset, return to this menu and choose {Fore.RED}2{Style.RESET_ALL} below → then option 2 in the next menu to apply it.\n")
                        else:
                            # Fallback to default video player (Windows)
                            os.startfile(video_path)
                            vlc_method = "default"
                            print_and_log(f"{Fore.YELLOW}⚠ VLC not found - video opened in default player{Style.RESET_ALL}")
                            print_and_log(f"{Fore.YELLOW}  Subtitle NOT auto-loaded. Please load manually:{Style.RESET_ALL}")
                            print_and_log(f"{Fore.CYAN}  {subtitle_path}{Style.RESET_ALL}")
                    except Exception as e:
                        print_and_log(f"{Fore.LIGHTRED_EX}Could not automatically open the video..{Style.RESET_ALL}")
                        print_and_log(f"{Fore.YELLOW}Error details: {str(e)}{Style.RESET_ALL}")
                        print_and_log(f"{Fore.LIGHTYELLOW_EX}Please open the video file manually:{Style.RESET_ALL}")
                        print_and_log(f"{Fore.CYAN}Video: {video_path}{Style.RESET_ALL}")
                        print_and_log(f"{Fore.CYAN}Subtitle: {subtitle_path}{Style.RESET_ALL}")
                        print_and_log(f"\n{Fore.YELLOW}Tip: Load the subtitle in your media player manually{Style.RESET_ALL}")
                        
                        # Try to provide helpful suggestions
                        if "No application is associated" in str(e):
                            print_and_log(f"{Fore.YELLOW}Tip: Install a media player like VLC and set it as default for .mkv files{Style.RESET_ALL}")
                        elif "cannot find the file specified" in str(e).lower():
                            print_and_log(f"{Fore.YELLOW}Tip: Check if the file path contains special characters or is too long{Style.RESET_ALL}")
                else:
                    print_and_log(f"{Fore.LIGHTRED_EX}No subtitle file found for this entry!{Style.RESET_ALL}")
                break
            elif choice == "2":
                break
            else:
                print_and_log(f"{Fore.RED}Invalid choice. Please enter 1, 2 or 3.{Style.RESET_ALL}")
        if skip_entry:
            continue
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
        if not ('vlc_opened' in locals() and vlc_opened):
            print_and_log("Please open the video file manually at the blue path:")
            print_and_log(f"{Fore.CYAN}{folder}{os.sep}{video}{Style.RESET_ALL}\n")
        
            print_and_log(f"{Fore.LIGHTYELLOW_EX}Did you know?{Style.RESET_ALL}\nIn VLC, press {Fore.CYAN}H{Style.RESET_ALL} or {Fore.CYAN}G{Style.RESET_ALL} to nudge subtitle timing forward or backward.")
            print_and_log(f"Once perfectly in sync, note the offset, return to this menu and choose {Fore.RED}2{Style.RESET_ALL} below → then option 2 in the next menu to apply it.\n")

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
                show_manual_correction_menu(idx, len(entries), title, subtitle_name, offset_val, timestamp_val, folder, video, lang, correlation_score)
                clear_and_print_ascii(BANNER_LINE)
                break
            else:
                print_and_log(f"{Fore.RED}Invalid choice. Please enter 1 or 2.{Style.RESET_ALL}")

def test_drift_subtitles_in_menu(folder, video, lang, current_sub_path, idx, total, title):
    """Browse DRIFT subtitle candidates from within the manual verification menu.

    Returns:
        False      → user went back, no change
        'accept'   → DRIFT sub replaced current file, entry is done (caller should close menu)
        'swap'     → DRIFT sub replaced current file, caller should continue editing
    """
    video_path = os.path.join(folder, video)

    def extract_drift_number(p):
        m = re.search(r'\.number(\d+)\.', p.name)
        return int(m.group(1)) if m else 999999

    # In series mode, restrict to DRIFT/FAILED subtitles for this specific episode only
    if SERIES_MODE:
        sxxexx = extract_sxxexx_code(video)
        if sxxexx:
            drift_subs = sorted(
                list(Path(folder).glob(f"*.{lang}.number*.{sxxexx}.DRIFT.srt")) +
                list(Path(folder).glob(f"*.{lang}.number*.{sxxexx}.FAILED.srt")),
                key=extract_drift_number)
        else:
            drift_subs = sorted(
                list(Path(folder).glob(f"*.{lang}.number*.DRIFT.srt")) +
                list(Path(folder).glob(f"*.{lang}.number*.FAILED.srt")),
                key=extract_drift_number)
    else:
        drift_subs = sorted(
            list(Path(folder).glob(f"*.{lang}.number*.DRIFT.srt")) +
            list(Path(folder).glob(f"*.{lang}.number*.FAILED.srt")),
            key=extract_drift_number)

    if not drift_subs:
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"\n{Style.BRIGHT}{Fore.CYAN}[{idx}/{total}] {title}{Style.RESET_ALL}")
        print_and_log(f"{sync_tag()} {Fore.YELLOW}No DRIFT subtitles found for {lang.upper()}{Style.RESET_ALL}")
        input(f"{sync_tag()} Press Enter to return to correction menu... ")
        return False

    drift_meta = load_drift_subtitle_metadata(DRIFT_METADATA_FILE)
    tested_bad = set()

    while True:
        # Auto-exit when all candidates have been rejected
        if tested_bad and len(tested_bad) >= len(drift_subs):
            clear_and_print_ascii(BANNER_LINE)
            print_and_log(f"\n{Style.BRIGHT}{Fore.CYAN}[{idx}/{total}] {title}{Style.RESET_ALL}")
            print_and_log(f"\n{Fore.YELLOW}All available DRIFT subtitle candidates have been tested and rejected.{Style.RESET_ALL}")
            input(f"\nPress Enter to return to the correction menu... ")
            return False

        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"\n{Style.BRIGHT}{Fore.CYAN}[{idx}/{total}] {title}{Style.RESET_ALL}")
        print_and_log(f"{sync_tag()} {Fore.LIGHTYELLOW_EX}DRIFT subtitles for: {Style.BRIGHT}{os.path.basename(folder)}{Style.RESET_ALL}")
        print_and_log(f"File: {Fore.CYAN}{video}{Style.RESET_ALL}\n")

        for i, sub in enumerate(drift_subs, 1):
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
        print_and_log(f"\n  {Fore.CYAN}0{Style.RESET_ALL} = Back to editor")

        choice = input(f"\nChoose [1-{len(drift_subs)}/0]: ").strip()

        if choice == "0":
            return False

        try:
            sel_idx = int(choice)
            if 1 <= sel_idx <= len(drift_subs):
                selected_sub = drift_subs[sel_idx - 1]

                # Open VLC with drift subtitle
                vlc_method = ""
                try:
                    vlc_path = shutil.which("vlc")
                    if not vlc_path:
                        for _p in [r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                                   r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"]:
                            if Path(_p).exists():
                                vlc_path = _p
                                break
                    if vlc_path:
                        subprocess.Popen(
                            [vlc_path, video_path, f':sub-file={str(selected_sub)}', '--no-sub-autodetect-file'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                        vlc_method = "vlc"
                    else:
                        os.startfile(video_path)
                        vlc_method = "default"
                except FileNotFoundError:
                    clear_and_print_ascii(BANNER_LINE)
                    print_and_log(f"\n{Fore.RED}{Style.BRIGHT}╔═══════════════════════════════════════════════════════════════╗{Style.RESET_ALL}")
                    print_and_log(f"{Fore.RED}{Style.BRIGHT}║  VIDEO PLAYER ERROR - Could not open video automatically     ║{Style.RESET_ALL}")
                    print_and_log(f"{Fore.RED}{Style.BRIGHT}╚═══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}\n")
                    print_and_log(f"{Fore.CYAN}Video file:{Style.RESET_ALL}\n  {video_path}\n")
                    print_and_log(f"{Fore.CYAN}Subtitle file:{Style.RESET_ALL}\n  {selected_sub}\n")
                    print_and_log(f"{Fore.YELLOW}Possible causes:{Style.RESET_ALL}")
                    print_and_log(f"  {Fore.WHITE}•{Style.RESET_ALL} VLC Media Player is not installed or not in system PATH")
                    print_and_log(f"  {Fore.WHITE}•{Style.RESET_ALL} Video file is already open in another player\n")
                    print_and_log(f"{Fore.GREEN}Solutions:{Style.RESET_ALL}")
                    print_and_log(f"  {Fore.WHITE}1.{Style.RESET_ALL} Download and install VLC Media Player (recommended)")
                    print_and_log(f"  {Fore.WHITE}2.{Style.RESET_ALL} Manually open the video with the subtitle file above\n")
                    print_and_log(f"{Fore.CYAN}What would you like to do?{Style.RESET_ALL}")
                    print_and_log(f"  {Fore.LIGHTBLUE_EX}1{Style.RESET_ALL} = Return to subtitle selection")
                    print_and_log(f"  {Fore.LIGHTBLUE_EX}2{Style.RESET_ALL} = I will test the subtitle manually, please continue")
                    err = input(f"\nChoose [1/2]: ").strip()
                    if err != "2":
                        continue
                except Exception as e:
                    clear_and_print_ascii(BANNER_LINE)
                    print_and_log(f"\n{Fore.RED}{Style.BRIGHT}╔═══════════════════════════════════════════════════════════════╗{Style.RESET_ALL}")
                    print_and_log(f"{Fore.RED}{Style.BRIGHT}║  ERROR - Could not open video player                         ║{Style.RESET_ALL}")
                    print_and_log(f"{Fore.RED}{Style.BRIGHT}╚═══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}\n")
                    print_and_log(f"{Fore.CYAN}Video file:{Style.RESET_ALL} {video_path}")
                    print_and_log(f"{Fore.CYAN}Subtitle file:{Style.RESET_ALL} {selected_sub}")
                    print_and_log(f"{Fore.RED}Error:{Style.RESET_ALL} {str(e)}\n")
                    print_and_log(f"{Fore.CYAN}What would you like to do?{Style.RESET_ALL}")
                    print_and_log(f"  {Fore.LIGHTBLUE_EX}1{Style.RESET_ALL} = Return to subtitle selection")
                    print_and_log(f"  {Fore.LIGHTBLUE_EX}2{Style.RESET_ALL} = I will test the subtitle manually, please continue")
                    err = input(f"\nChoose [1/2]: ").strip()
                    if err != "2":
                        continue

                # Assessment menu
                clear_and_print_ascii(BANNER_LINE)
                print_and_log(f"\n{Style.BRIGHT}{Fore.CYAN}[{idx}/{total}] {title}{Style.RESET_ALL}")
                if vlc_method == "vlc":
                    print_and_log(f"{Fore.GREEN}✓ Video opened in VLC with subtitle auto-loaded{Style.RESET_ALL}")
                elif vlc_method == "default":
                    print_and_log(f"{Fore.YELLOW}⚠ VLC not found - video opened in default player{Style.RESET_ALL}")
                    print_and_log(f"{Fore.YELLOW}  Subtitle NOT auto-loaded. Please load manually:{Style.RESET_ALL}")
                    print_and_log(f"{Fore.CYAN}  {selected_sub.name}{Style.RESET_ALL}")

                print_and_log(f"\n{sync_tag()} {Fore.CYAN}Testing: {selected_sub.name}{Style.RESET_ALL}\n")
                print_and_log(f"{Fore.LIGHTYELLOW_EX}Check if the subtitle matches. Press {Fore.GREEN}1{Fore.LIGHTYELLOW_EX} if correct, {Fore.YELLOW}2{Fore.LIGHTYELLOW_EX} if you want to edit it, or {Fore.RED}3{Fore.LIGHTYELLOW_EX} if unusable.{Style.RESET_ALL}\n")
                print_and_log(f"  {Fore.GREEN}1{Style.RESET_ALL} = Subtitle is correct - Accept and continue")
                print_and_log(f"  {Fore.YELLOW}2{Style.RESET_ALL} = Load this subtitle in the editor {Fore.LIGHTBLACK_EX}(replaces current subtitle, opens for manual offset adjustment){Style.RESET_ALL}")
                print_and_log(f"  {Fore.RED}3{Style.RESET_ALL} = Subtitle is bad - Return to selection")

                assess = input(f"\nChoose [{Fore.GREEN}1{Style.RESET_ALL}/{Fore.YELLOW}2{Style.RESET_ALL}/{Fore.RED}3{Style.RESET_ALL}]: ").strip()

                if assess == "1":
                    try:
                        os.replace(str(selected_sub), current_sub_path)
                        print_and_log(f"{sync_tag()} {Fore.GREEN}✓ Drift subtitle accepted as {os.path.basename(current_sub_path)}{Style.RESET_ALL}")
                        time.sleep(1.0)
                        return "accept"
                    except Exception as e:
                        print_and_log(f"{sync_tag()} {Fore.RED}Error replacing subtitle: {e}{Style.RESET_ALL}")
                        input("Press Enter to continue... ")
                        continue

                elif assess == "2":
                    try:
                        os.replace(str(selected_sub), current_sub_path)
                        print_and_log(f"{sync_tag()} {Fore.GREEN}✓ Loaded into editor: {os.path.basename(current_sub_path)}{Style.RESET_ALL}")
                        time.sleep(0.8)
                        return "swap"
                    except Exception as e:
                        print_and_log(f"{sync_tag()} {Fore.RED}Error swapping subtitle: {e}{Style.RESET_ALL}")
                        input("Press Enter to continue... ")
                        continue

                elif assess == "3":
                    tested_bad.add(selected_sub)
                    continue
                else:
                    print_and_log(f"{sync_tag()} {Fore.RED}Invalid choice.{Style.RESET_ALL}")
                    input("Press Enter to continue... ")
                    continue
            else:
                print_and_log(f"{sync_tag()} {Fore.RED}Invalid number.{Style.RESET_ALL}")
                input("Press Enter to continue... ")
        except ValueError:
            print_and_log(f"{sync_tag()} {Fore.RED}Invalid input.{Style.RESET_ALL}")
            input("Press Enter to continue... ")


def show_manual_correction_menu(idx, total, title, subtitle_name, offset, timestamp, folder, video, lang, correlation_score="N/A"):
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
    
    # Determine correlation score quality
    score_display = ""
    if correlation_score != "N/A":
        try:
            score_val = float(correlation_score)
            if score_val >= 200000:
                score_quality = f"{Fore.GREEN}Excellent{Style.RESET_ALL}"
            elif score_val >= 100000:
                score_quality = f"{Fore.LIGHTGREEN_EX}Good{Style.RESET_ALL}"
            elif score_val >= 50000:
                score_quality = f"{Fore.YELLOW}Moderate{Style.RESET_ALL}"
            elif score_val > 0:
                score_quality = f"{Fore.LIGHTYELLOW_EX}Low{Style.RESET_ALL}"
            else:
                score_quality = f"{Fore.RED}Poor{Style.RESET_ALL}"
            score_display = f" | {Fore.WHITE}Correlation: {Fore.CYAN}{score_val:.0f}{Style.RESET_ALL} ({score_quality})"
        except (ValueError, TypeError):
            score_display = f" | {Fore.WHITE}Correlation: {Fore.YELLOW}{correlation_score}{Style.RESET_ALL}"
    else:
        score_display = ""
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
        
        # Display correlation score
        if correlation_score != "N/A":
            try:
                score_val = float(correlation_score)
                if score_val >= 200000:
                    score_quality = f"{Fore.GREEN}Excellent{Style.RESET_ALL}"
                elif score_val >= 100000:
                    score_quality = f"{Fore.GREEN}Good{Style.RESET_ALL}"
                elif score_val >= 50000:
                    score_quality = f"{Fore.YELLOW}Moderate{Style.RESET_ALL}"
                elif score_val < 0:
                    score_quality = f"{Fore.RED}Poor{Style.RESET_ALL}"
                else:
                    score_quality = f"{Fore.YELLOW}Low{Style.RESET_ALL}"
                print_and_log(f"{Fore.WHITE}Correlation score: {Fore.LIGHTYELLOW_EX}{score_val:.0f}{Style.RESET_ALL} ({score_quality})")
            except ValueError:
                print_and_log(f"{Fore.WHITE}Correlation score: {Fore.LIGHTBLACK_EX}{correlation_score}{Style.RESET_ALL}")
        else:
            print_and_log(f"{Fore.WHITE}Correlation score: {Fore.LIGHTBLACK_EX}N/A{Style.RESET_ALL}")
        
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
        print_and_log(f"{Fore.CYAN}6{Style.RESET_ALL} = Check other drifted files for {Fore.LIGHTYELLOW_EX}{lang.upper()}{Style.RESET_ALL}")
        print_and_log(f"{Fore.CYAN}7{Style.RESET_ALL} = Remove subtitle and skip this movie-language combination {Fore.LIGHTBLACK_EX}(adds to skipped_movies){Style.RESET_ALL}")
        print_and_log(f"{Fore.CYAN}8{Style.RESET_ALL} = Done")
        print()
        choice = input(f"Choose [{Fore.CYAN}1-8{Style.RESET_ALL}]: ").strip()
        if choice == "1":
            video_path = os.path.join(folder, video)
            try:
                vlc_path = shutil.which("vlc")
                if not vlc_path:
                    for _p in [r"C:\Program Files\VideoLAN\VLC\vlc.exe", r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"]:
                        if Path(_p).exists():
                            vlc_path = _p
                            break
                if vlc_path and os.path.exists(sub_path):
                    subprocess.Popen([vlc_path, video_path, f':sub-file={sub_path}', '--no-sub-autodetect-file'],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    logs.append(f"{sync_tag()} {Fore.CYAN}Video opened in VLC with subtitle: {os.path.basename(sub_path)}{Style.RESET_ALL}")
                else:
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
                        
                        # Update timestamp to reflect the change
                        new_time, first_line = get_first_line_and_time(sub_path)
                        if new_time:
                            timestamp = f"{new_time} <i>- {first_line}</i>"
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
                        
                        # Update timestamp to reflect the restoration
                        new_time, first_line = get_first_line_and_time(sub_path)
                        if new_time:
                            timestamp = f"{new_time} <i>- {first_line}</i>"
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
                                # Find the original numbered subtitle line (ignore metadata lines)
                                for l in lines:
                                    if (l.endswith(('.srt', '.ass', '.ssa')) and
                                            not l.startswith('Rejected:') and
                                            not l.startswith('IMDb_match:') and
                                            not l.startswith('Quality:')):
                                        orig_name = l
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
                    mark_subtitle_as_drift(sub_path, lang='', create_copies=not SMART_SYNC)
                    
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
            result = test_drift_subtitles_in_menu(folder, video, lang, sub_path, idx, total, title)
            if result == "accept":
                remove_completed_entry_from_offset_file(title, folder, video)
                return
            elif result == "swap":
                # Drift file replaced sub_path on disk — refresh timestamp for the editor
                new_time, first_line = get_first_line_and_time(sub_path)
                if new_time:
                    timestamp = f"{new_time} <i>- {first_line}</i>"
                logs.append(f"{sync_tag()} {Fore.GREEN}Drift subtitle loaded — now editing the selected file{Style.RESET_ALL}")
            # False → back to menu, nothing to do
        elif choice == "7":
            while True:
                confirm = input(f"{Fore.LIGHTYELLOW_EX}Are you sure you want to remove this subtitle and skip this movie-language combination? (y/n): {Style.RESET_ALL}").strip().lower()
                if confirm == "y":
                    # Remove the subtitle file
                    try:
                        if os.path.exists(sub_path):
                            os.remove(sub_path)
                            print_and_log(f"{sync_tag()} {Fore.YELLOW}Removed subtitle file: {subtitle_name}{Style.RESET_ALL}")
                        
                        # Clean up all DRIFT and FAILED files for this language/episode
                        # so they don't trigger acquisition on the next run
                        cleanup_drift_and_failed(folder, lang, keep_file=None, clean_drifts=True, video=video, silent=False)
                        
                        # Add to skipped_movies in config
                        video_full_path = Path(folder) / video
                        add_skipped_movie_language_to_config(video_full_path, lang)
                        print_and_log(f"{sync_tag()} {Fore.MAGENTA}Added {video} [{lang.upper()}] to skipped_movies in .config{Style.RESET_ALL}")
                        print_and_log(f"{sync_tag()} {Fore.MAGENTA}This movie-language combination will not be processed again.{Style.RESET_ALL}")
                        
                        # Remove from offset tracking file
                        remove_completed_entry_from_offset_file(title, folder, video)
                        print_and_log(f"{sync_tag()} {Fore.YELLOW}Removed offset entry from tracking file{Style.RESET_ALL}")
                        
                        print_and_log(f"{Fore.LIGHTGREEN_EX}Movie skipped successfully. Moving to next video.{Style.RESET_ALL}")
                        return
                    except Exception as e:
                        logs.append(f"{sync_tag()} {Fore.RED}Error skipping movie: {str(e)}{Style.RESET_ALL}")
                        break
                elif confirm == "n":
                    print_and_log(f"{Fore.YELLOW}Cancelled skip operation.{Style.RESET_ALL}")
                    break
                else:
                    print_and_log(f"{Fore.RED}Invalid choice. Please enter y or n.{Style.RESET_ALL}")
        elif choice == "8":
            remove_completed_entry_from_offset_file(title, folder, video)
            break
        else:
            logs.append(f"{sync_tag()} {Fore.RED}Invalid choice. Please enter 1-8.{Style.RESET_ALL}")

# Ensure all entries in offset file have Quality scores
ensure_quality_scores_in_offset_file()

# Sync auto-accept list with current config thresholds (in case user changed settings)
sync_auto_accept_with_config()

# Show auto-accepted summary first (if any)
has_auto_accepted = show_auto_accepted_summary()

# Remove auto-accepted entries from offset file to avoid duplicate verification
remove_auto_accepted_from_offset_file()

# Show manual verification menu if there are entries
def _has_pending_verification_entries():
    if not os.path.exists(MOVIES_WITH_LINEAR_OFFSET_FILE):
        return False
    with open(MOVIES_WITH_LINEAR_OFFSET_FILE, 'r', encoding='utf-8') as _f:
        _content = _f.read()
    for _entry in _content.split('--\n'):
        _entry = _entry.strip()
        if _entry and not _entry.startswith('Linear offset tracking') and not _entry.startswith('Format:'):
            _lines = _entry.splitlines()
            if len(_lines) >= 6 and any(_l.endswith(('.mkv', '.mp4', '.avi')) for _l in _lines):
                return True
    return False

if _has_pending_verification_entries():
    print_and_log(f"\n{Fore.YELLOW}Manual verification needed for subtitles{Style.RESET_ALL}")
    show_offset_verification_menu()
else:
    if has_auto_accepted:
        print_and_log(f"\n{sync_tag()} {Fore.GREEN}No subtitles require manual offset verification.{Style.RESET_ALL}")
    else:
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"{Style.BRIGHT}{Fore.GREEN}All subtitles synchronized successfully!{Style.RESET_ALL}\n")
        print_and_log(f"No manual verification needed.")
        time.sleep(2)
    print_and_log(f"{sync_tag()} {Fore.CYAN}Continuing to cleaning process...{Style.RESET_ALL}")

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

print_and_log(f"\n{sync_tag()} {Fore.CYAN}Performing comprehensive cleanup of extracted files...{Style.RESET_ALL}")
comprehensive_cleanup_extracted_files()

# Offer to remove SUBTITLES.S##.LANG folders if they were used (series mode only)
if SERIES_MODE:
    import shutil as _shutil
    _used_subtitle_folders = []
    for _vid in videos:
        _vdir = Path(os.path.dirname(_vid))
        for _item in _vdir.iterdir():
            if re.match(r'subtitles\.s\d{2}\.[a-z]+(\.zip)?$', _item.name, re.IGNORECASE) and _item not in _used_subtitle_folders:
                _used_subtitle_folders.append(_item)
    if _used_subtitle_folders:
        clear_and_print_ascii(BANNER_LINE)
        print_and_log(f"\n{sync_tag()} {Style.BRIGHT}{Fore.CYAN}Pre-downloaded Subtitle Folder Cleanup{Style.RESET_ALL}\n")
        print_and_log(f"The following subtitle folder(s) were used during this run:\n")
        for _sf in _used_subtitle_folders:
            print_and_log(f"   {Fore.YELLOW}{_sf.name}{Style.RESET_ALL}  {Fore.LIGHTBLACK_EX}({_sf.parent}){Style.RESET_ALL}")
        print_and_log(f"\n{Fore.LIGHTYELLOW_EX}All subtitles have been synchronised. These folders are no longer needed.{Style.RESET_ALL}\n")
        print_and_log(f"{Fore.CYAN}1{Style.RESET_ALL} = {Style.BRIGHT}Remove the subtitle folder(s) {Fore.LIGHTYELLOW_EX}(recommended){Style.RESET_ALL}")
        print_and_log(f"{Fore.CYAN}2{Style.RESET_ALL} = Keep the subtitle folder(s)\n")
        while True:
            _sf_choice = input_and_log(f"Make a choice [{Fore.CYAN}1{Style.RESET_ALL}/{Fore.CYAN}2{Style.RESET_ALL}]: ").strip()
            if _sf_choice in ('1', ''):
                _removed = 0
                for _sf in _used_subtitle_folders:
                    try:
                        if _sf.is_dir():
                            _shutil.rmtree(_sf)
                        else:
                            _sf.unlink()
                        _removed += 1
                        print_and_log(f"{sync_tag()} {Fore.GREEN}Removed: {_sf.name}{Style.RESET_ALL}")
                    except Exception as _e:
                        print_and_log(f"{sync_tag()} {Fore.RED}Could not remove {_sf.name}: {_e}{Style.RESET_ALL}")
                print_and_log(f"\n{sync_tag()} {Fore.GREEN}{_removed} folder(s) removed.{Style.RESET_ALL}")
                break
            elif _sf_choice == '2':
                print_and_log(f"{sync_tag()} {Fore.YELLOW}Subtitle folders kept.{Style.RESET_ALL}")
                break
            else:
                print_and_log(f"{Fore.RED}Invalid choice. Please enter 1 or 2.{Style.RESET_ALL}")

# Remove offset tracking and metadata files only if manual verification is complete
# (i.e., movies_with_linear_offset.txt no longer exists)
offset_file = os.path.join(script_dir, 'movies_with_linear_offset.txt')
metadata_file = os.path.join(script_dir, '.subtitle_metadata.txt')

if not _has_pending_verification_entries():
    # No pending entries means all verification is done - safe to cleanup
    if os.path.exists(offset_file):
        os.remove(offset_file)
    if os.path.exists(metadata_file):
        os.remove(metadata_file)
    if os.path.exists(AUTO_ACCEPTED_FILE):
        os.remove(AUTO_ACCEPTED_FILE)
    if os.path.exists(DRIFT_METADATA_FILE):
        os.remove(DRIFT_METADATA_FILE)

# Final DRIFT cleanup: all syncing and verification is fully done at this point.
# Remove any remaining numbered DRIFT files across all video folders.
print_and_log(f"\n{sync_tag()} {Fore.CYAN}Performing final DRIFT cleanup...{Style.RESET_ALL}")
drift_removed = 0
for video in videos:
    video_dir = os.path.dirname(video)
    for f in os.listdir(video_dir):
        is_drift = False
        for lang in LANGUAGES:
            if SERIES_MODE:
                sxxexx_code = extract_sxxexx_code(video)
                if sxxexx_code and re.match(rf".*\.{lang}\.number\d+\.{re.escape(sxxexx_code)}\.DRIFT\.srt$", f, re.IGNORECASE):
                    is_drift = True
                    break
            if re.match(rf".*\.{lang}\.number\d+\.DRIFT\.srt$", f, re.IGNORECASE):
                is_drift = True
                break
        if is_drift:
            try:
                os.remove(os.path.join(video_dir, f))
                print_and_log(f"{sync_tag()} {Fore.YELLOW}Final DRIFT cleanup: removed {f}{Style.RESET_ALL}")
                drift_removed += 1
            except Exception as e:
                print_and_log(f"{sync_tag()} {Fore.RED}Could not remove DRIFT {f}: {e}{Style.RESET_ALL}")
if drift_removed == 0:
    print_and_log(f"{sync_tag()} {Fore.GREEN}No remaining DRIFT files found.{Style.RESET_ALL}")

print_and_log(f"\n{sync_tag()} {Fore.CYAN}Performing final subtitle coverage scan...{Style.RESET_ALL}")
coverage_results = scan_subtitle_coverage(videos, LANGUAGES, SERIES_MODE, show_progress=True, logger_func=print_and_log, sync_tag_func=sync_tag)
display_coverage_results(coverage_results, LANGUAGES, banner_line=BANNER_LINE, return_to_menu=True, logger_func=print_and_log, sync_tag_func=sync_tag, series_mode=SERIES_MODE)

clear_and_print_ascii(BANNER_LINE)
print_and_log(f"\n{Style.BRIGHT}{Fore.GREEN}Subservient run COMPLETE!{Style.RESET_ALL}\n")

print_and_log(f"{Style.BRIGHT}All done. Smart Sync, quality scoring, internal subtitle extraction, series support,{Style.RESET_ALL}")
print_and_log(f"{Style.BRIGHT}and DRIFT recovery \u2014 all handled automatically.{Style.RESET_ALL}\n")
print_and_log(f"{Fore.YELLOW}If Subservient saved you time, consider supporting its development:{Style.RESET_ALL}")
print_and_log(f"{Fore.CYAN}https://buymeacoffee.com/nexigen{Style.RESET_ALL}")
print_and_log(f"\n{Fore.LIGHTWHITE_EX}Your support funds what's next: Bazarr integration, a web UI, and Jellyfin/Plex webhooks.")
print_and_log(f"Donors get early builds and priority support in my Discord. Even \u20ac3 helps.{Style.RESET_ALL}")
print_and_log(f"\n{Fore.LIGHTMAGENTA_EX}Thanks for using Subservient. \u2014 Nexigen{Style.RESET_ALL}")

print_and_log(f"\n{Fore.YELLOW}Press any key to exit...{Style.RESET_ALL}")
input()