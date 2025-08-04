import os
import sys
import subprocess
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    class MockColor:
        def __getattr__(self, name):
            return ""
    Fore = Style = MockColor()

def ensure_core_requirements():
    """Install core Python packages required for Subservient to function.
    
    Checks if required packages are installed and offers to install missing ones.
    Exits the program after installation or if user declines installation.
    """
    REQUIRED_PACKAGES = [
        ("colorama", None),
        ("platformdirs", None),
        ("pycountry", None),
        ("requests", None),
        ("tqdm", None),
        ("ffsubsync", None),
        ("langdetect", None),
    ]
    missing = []
    for pkg, import_name in REQUIRED_PACKAGES:
        try:
            __import__(import_name or pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print("\n[Subservient] The following required packages are missing:")
        for pkg in missing:
            print(f"  - {pkg}")
        
        if os.name == 'nt':
            import shutil
            import glob
            cl_path = shutil.which('cl')
            
            if not cl_path:
                vs_patterns = [
                    r"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                    r"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio\*\BuildTools\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio\*\BuildTools\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\bin\cl.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio\2017\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio\2017\*\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe"
                ]
                found_cl = any(glob.glob(pattern) for pattern in vs_patterns)
                
                if not found_cl:
                    print(f"\n{Fore.YELLOW}ERROR: Build tools not installed. Python packages require Microsoft Visual C++ Build Tools to compile.{Style.RESET_ALL}")
                    print(f"{Fore.YELLOW}Please install Microsoft Visual C++ Build Tools first before installing Python packages.{Style.RESET_ALL}")
                    print(f"{Fore.WHITE}In the README, look for chapter: {Fore.CYAN}'1. Installing and Configuring Subservient', step 4{Style.RESET_ALL}")
                    print(f"{Fore.WHITE}In there, check the 'External Tools' section for installation instructions.{Style.RESET_ALL}")
                    input("\nPress Enter to exit...")
                    sys.exit(1)
        
        choice = input("\nWould you like to install ALL missing packages now? [y/n]: ").strip().lower()
        if choice in ('', 'y', 'yes'):
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', *missing])
                print("\nSuccessfully installed required packages.\n")
                if os.name == 'nt':
                    os.system('cls')
                else:
                    os.system('clear')
                print("[Subservient] All essential packages for Subservient are now installed.")
                print("[Subservient] It's strongly recommended to verify and test all packages")
                print("[Subservient] When opening subordinate.py, use option '4' to test the installed packages.")
                print("[Subservient] Please close this terminal and try restarting subordinate.py =)\n\n")
                input("Press Enter to exit...")
                sys.exit(0)
            except Exception as e:
                print(f"\n[ERROR] Failed to install packages: {e}\nPlease install them manually and restart the script.")
                input("\nPress Enter to exit...")
                sys.exit(1)
        else:
            print("\n[Subservient] Required packages are missing. Exiting.")
            input("\nPress Enter to exit...")
            sys.exit(1)

ensure_core_requirements()

print("[Subservient] Loading imports..")
import importlib.util
import time
from pathlib import Path
from platformdirs import user_config_dir
from datetime import datetime
import re
import pycountry
import requests

BANNER_LINE = f"                   {Fore.LIGHTRED_EX}[Phase 1/4]{Style.RESET_ALL} Subservient Set-up"

def write_anchor_to_pathfile():
    """Write current directory path to Subservient pathfiles config.
    
    Writes or updates the subservient anchor path in the pathfile and
    creates config directory and pathfile if they don't exist.
    """
    config_dir = Path(user_config_dir()) / "Subservient"
    config_dir.mkdir(parents=True, exist_ok=True)
    pathfile = config_dir / "Subservient_pathfiles"
    anchor_path = str(Path(__file__).resolve().parent)
    lines = []
    if pathfile.exists():
        with open(pathfile, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith("subservient_anchor="):
                lines[i] = f"subservient_anchor={anchor_path}"
                found = True
                break
        if not found:
            lines.append(f"subservient_anchor={anchor_path}")
    else:
        lines = [f"subservient_anchor={anchor_path}"]
    with open(pathfile, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def write_subordinate_path_to_pathfile():
    """Write current subordinate.py path to Subservient pathfiles config.
    
    Updates the subordinate_path entry in the pathfile to reflect the current
    location of subordinate.py, enabling other modules to find this script.
    """
    config_dir = Path(user_config_dir()) / "Subservient"
    config_dir.mkdir(parents=True, exist_ok=True)
    pathfile = config_dir / "Subservient_pathfiles"
    subordinate_path = str(Path(__file__).resolve())
    lines = []
    if pathfile.exists():
        with open(pathfile, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith("subordinate_path="):
                lines[i] = f"subordinate_path={subordinate_path}"
                found = True
                break
        if not found:
            lines.append(f"subordinate_path={subordinate_path}")
    else:
        lines = [f"subordinate_path={subordinate_path}"]
    with open(pathfile, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def print_subservient_checklist():
    """Display pre-flight checklist for Subservient setup and usage.
    
    Shows current configuration and video processing settings including mode,
    processing type, language settings, and other important parameters.
    """
    config_dir = Path(user_config_dir()) / "Subservient"
    pathfile = config_dir / "Subservient_pathfiles"
    anchor_path = None
    if pathfile.exists():
        with open(pathfile, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("utils_path="):
                    utils_path = Path(line.split("=", 1)[1].strip())
                    anchor_path = utils_path.parent
                    break
    if anchor_path is None:
        anchor_path = Path(__file__).parent.resolve()
    
    config_path = anchor_path / '.config'
    config = {}
    if config_path.exists():
        with open(config_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                m = re.match(r'^([a-zA-Z0-9_]+)\s*=\s*(.+)$', line)
                if m:
                    config[m.group(1).strip().lower()] = m.group(2).strip()
    
    series_mode = config.get('series_mode', None)
    top_downloads = config.get('top_downloads', None)
    delete_extra_videos = config.get('delete_extra_videos', None)
    
    local_path = Path(__file__).parent.resolve()
    video_exts = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
    direct_videos = [f for f in local_path.iterdir() if f.is_file() and f.suffix.lower() in video_exts]
    
    if direct_videos:
        processing_type = f"{Fore.CYAN}Single file processing{Style.RESET_ALL}"
        maps_found = f"{Fore.GREEN}1{Style.RESET_ALL}"
    else:
        subfolders = [f for f in local_path.iterdir() if f.is_dir()]
        count = sum(1 for folder in subfolders if [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in video_exts])
        processing_type = f"{Fore.CYAN}Batch processing{Style.RESET_ALL}"
        maps_found = f"{Fore.GREEN}{count}{Style.RESET_ALL}"
    
    mode = (f"{Fore.GREEN}Series mode{Style.RESET_ALL}" if series_mode and series_mode.strip().lower() == 'true' 
            else f"{Fore.GREEN}Movie mode{Style.RESET_ALL}" if series_mode 
            else f"{Fore.RED}N/A (series_mode missing in config){Style.RESET_ALL}")
    
    subtitle_downloads = f"{Fore.YELLOW}{top_downloads}{Style.RESET_ALL}" if top_downloads else f"{Fore.RED}N/A{Style.RESET_ALL}"
    
    if delete_extra_videos is not None:
        delete_status = (f"{Fore.RED}PERMANENTLY DELETE extra videos{Style.RESET_ALL}" 
                        if delete_extra_videos.strip().lower() == 'true' 
                        else f"{Fore.CYAN}Move extra videos to 'Extras' folder{Style.RESET_ALL}")
    else:
        delete_status = f"{Fore.RED}N/A (delete_extra_videos missing in config){Style.RESET_ALL}"
    
    folder_path = Path(__file__).parent.resolve()
    folder_name = folder_path.name
    short_path = str(folder_path.parent / (folder_name[:37] + '...' if len(folder_name) > 40 else folder_name))
    
    reject_offset_threshold = config.get('reject_offset_threshold', None)
    threshold_str = (f"{float(reject_offset_threshold):.1f}s" 
                    if reject_offset_threshold and reject_offset_threshold.replace('.', '').isdigit()
                    else f"{Fore.RED}N/A{Style.RESET_ALL}")
    
    print(f"{Style.BRIGHT}{Fore.BLUE}  [ Subservient Pre-Flight Checklist ]{Style.RESET_ALL}\n")
    print(f"  {Fore.WHITE}Location:{Style.RESET_ALL}         {Fore.LIGHTYELLOW_EX}{short_path}{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}Mode:{Style.RESET_ALL}             {mode}")
    print(f"  {Fore.WHITE}Processing type:{Style.RESET_ALL}  {processing_type}")
    print(f"  {Fore.WHITE}Maps found:{Style.RESET_ALL}       {maps_found}")
    
    subtitle_langs = config.get('languages', None)
    audio_langs = config.get('audio_track_languages', None)
    print(f"  {Fore.WHITE}Subtitle languages to find:{Style.RESET_ALL}   {Fore.LIGHTYELLOW_EX}{subtitle_langs if subtitle_langs else 'N/A'}{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}Audio track languages to keep:{Style.RESET_ALL} {Fore.LIGHTYELLOW_EX}{audio_langs if audio_langs else 'N/A'}{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}Subtitle downloads per batch:{Style.RESET_ALL} {subtitle_downloads}")
    print(f"  {Fore.WHITE}Extra video handling:{Style.RESET_ALL}   {delete_status}")
    print(f"  {Fore.WHITE}Subtitle delay threshold:{Style.RESET_ALL}   {Fore.LIGHTYELLOW_EX}{threshold_str}{Style.RESET_ALL}")
    print(f"\n{Fore.LIGHTYELLOW_EX}  Is everything set correctly?{Style.RESET_ALL}")
    print(f"{Fore.GREEN}  1{Style.RESET_ALL} = Looks good, start Subservient!")
    print(f"{Fore.RED}  2{Style.RESET_ALL} = This is incorrect. Exit so that I can fix it")
def print_main_menu():
    """Display main menu options for Subservient."""
    """Display the main menu options for the Subservient application."""
    print(f"\n{Style.BRIGHT}{Fore.YELLOW}What would you like to do?{Style.RESET_ALL}\n")
    print(f"  {Fore.GREEN}1{Style.RESET_ALL} = Start Subservient")
    print(f"  {Fore.GREEN}2{Style.RESET_ALL} = Scan subtitle coverage")
    print(f"  {Fore.GREEN}3{Style.RESET_ALL} = Show quick instructions")
    print(f"  {Fore.GREEN}4{Style.RESET_ALL} = Install & verify requirements")
    print(f"  {Fore.GREEN}5{Style.RESET_ALL} = Extra tools")
    print(f"  {Fore.GREEN}6{Style.RESET_ALL} = Recreate .config file")
    print(f"  {Fore.GREEN}7{Style.RESET_ALL} = Open README file")
    print(f"  {Fore.GREEN}8{Style.RESET_ALL} = Exit\n")

def print_subtitle_cleaner_intro():
    """Display subtitle cleaner introduction and options."""
    utils.clear_and_print_ascii(BANNER_LINE)
    print(f"{Style.BRIGHT}{Fore.BLUE}[Subservient]{Style.RESET_ALL} Subtitle Cleaner\n")
    
    print(f"{Style.BRIGHT}{Fore.CYAN}What is Subtitle Cleaner?{Style.RESET_ALL}")
    print(f"{Fore.WHITE}Subtitle Cleaner removes unwanted content from .srt subtitle files, such as:{Style.RESET_ALL}")
    print(f"  • {Fore.LIGHTYELLOW_EX}Advertisements and promotional text{Style.RESET_ALL}")
    print(f"  • {Fore.LIGHTYELLOW_EX}Website credits and watermarks{Style.RESET_ALL}")
    print(f"  • {Fore.LIGHTYELLOW_EX}Translator notes and metadata{Style.RESET_ALL}")
    print(f"  • {Fore.LIGHTYELLOW_EX}Other unwanted content that clutters subtitles{Style.RESET_ALL}")
    
    print(f"\n{Fore.WHITE}All original files are automatically backed up to:{Style.RESET_ALL}")
    print(f"  {Fore.LIGHTBLACK_EX}{utils.get_subservient_folder()}/data/subtitle_backups/{Style.RESET_ALL}")
    
    print(f"\n{Style.BRIGHT}{Fore.YELLOW}What would you like to do?{Style.RESET_ALL}\n")
    print(f"  {Fore.GREEN}1{Style.RESET_ALL} = Clean subtitle files (remove ads and unwanted content)")
    print(f"  {Fore.GREEN}2{Style.RESET_ALL} = Restore subtitle changes (undo previous cleaning)")
    print(f"  {Fore.RED}3{Style.RESET_ALL} = Return to extra tools menu\n")
    print(f"{Style.DIM}Note: Make sure you're in a directory with video files and .srt subtitle files.{Style.RESET_ALL}")

def print_extra_tools_menu():
    """Display extra tools menu with available tools."""
    utils.clear_and_print_ascii(BANNER_LINE)
    print(f"{Style.BRIGHT}{Fore.BLUE}[Subservient]{Style.RESET_ALL} Extra Tools\n")
    
    print(f"{Style.BRIGHT}{Fore.CYAN}Available Tools:{Style.RESET_ALL}")
    print(f"{Fore.WHITE}Select a tool to use:{Style.RESET_ALL}\n")
    
    print(f"  {Fore.GREEN}1{Style.RESET_ALL} = Subtitle Cleaner - Remove ads and unwanted content from subtitle files")
    print(f"  {Fore.RED}2{Style.RESET_ALL} = Return to main menu\n")
    
    print(f"{Style.DIM}More tools will be added in future updates.{Style.RESET_ALL}")

def show_extra_tools_menu():
    """Handle the Extra Tools menu interface."""
    while True:
        print_extra_tools_menu()
        choice = input(f"{Fore.LIGHTYELLOW_EX}Make a choice:{Style.RESET_ALL} ").strip()
        if choice == "1":
            show_subtitle_cleaner()
        elif choice == "2":
            break
        else:
            print(f"{Fore.RED}Invalid choice. Please select 1 or 2.{Style.RESET_ALL}")
            time.sleep(1)

def show_subtitle_cleaner():
    """Handle the Subtitle Cleaner main interface."""
    while True:
        print_subtitle_cleaner_intro()
        choice = input(f"{Fore.LIGHTYELLOW_EX}Make a choice:{Style.RESET_ALL} ").strip()
        if choice == "1":
            try:
                utils.run_subtitle_cleaning_interface()
            except Exception as e:
                utils.clear_and_print_ascii(BANNER_LINE)
                print(f"{Style.BRIGHT}{Fore.RED}[Error]{Style.RESET_ALL}")
                print(f"{Fore.RED}An error occurred while running subtitle cleaning: {str(e)}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Please make sure all required dependencies are installed.{Style.RESET_ALL}")
                input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")
        elif choice == "2":
            try:
                utils.run_subtitle_restore_interface()
            except Exception as e:
                utils.clear_and_print_ascii(BANNER_LINE)
                print(f"{Style.BRIGHT}{Fore.RED}[Error]{Style.RESET_ALL}")
                print(f"{Fore.RED}An error occurred while running subtitle restore: {str(e)}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Please make sure all required dependencies are installed.{Style.RESET_ALL}")
                input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")
        elif choice == "3":
            break
        else:
            print(f"{Fore.RED}Invalid choice. Please select 1, 2, or 3.{Style.RESET_ALL}")
            time.sleep(1)

def print_instructions_page(page):
    """Display specified page of usage instructions.
    
    Shows a specific page of the instruction manual (pages 1-5).
    """
    utils.clear_and_print_ascii(BANNER_LINE)
    if page == 1:
        print(f"{Style.BRIGHT}{Fore.CYAN}[1/5] Installing, configuring and running Subservient{Style.RESET_ALL}\n")
        print(f"{Fore.GREEN}1.{Style.RESET_ALL} Start by selecting option {Fore.YELLOW}'4'{Style.RESET_ALL} in the menu.")
        print(f"   This will check if all required packages are installed and working.")
        print(f"   If there are any issues, consult the README, ask ChatGPT, or open an issue on GitHub.")
        print(f"   All errors and test results are shown in the terminal and saved in the logs folder.\n")
    elif page == 2:
        print(f"{Style.BRIGHT}{Fore.CYAN}[2/5] Configuration: .config and OpenSubtitles{Style.RESET_ALL}\n")
        print(f"{Fore.GREEN}2.{Style.RESET_ALL} Open the {Fore.YELLOW}.config{Style.RESET_ALL} file in your Subservient folder.")
        print(f"   Fill in all required settings. The most important are:")
        print(f"   - {Fore.CYAN}OpenSubtitles API key{Style.RESET_ALL}")
        print(f"   - {Fore.CYAN}Username and password{Style.RESET_ALL}\n")
        print(f"   You need to create an OpenSubtitles account and then create a 'consumer' (API application).")
        print(f"   Detailed instructions for this are in the README.")
        print(f"   Adjust other settings as needed for your preferences.\n")
    elif page == 3:
        print(f"{Style.BRIGHT}{Fore.CYAN}[3/5] Placing subordinate.py and processing modes{Style.RESET_ALL}\n")
        print(f"{Fore.GREEN}3.{Style.RESET_ALL} Move {Fore.YELLOW}subordinate.py{Style.RESET_ALL} to the folder you want to process.")
        print(f"   There are two modes:")
        print(f"   - {Fore.CYAN}Single file processing:{Style.RESET_ALL} Place subordinate.py in a folder with one video file.")
        print(f"   - {Fore.CYAN}Batch processing:{Style.RESET_ALL} Place subordinate.py in a folder with multiple subfolders, each containing a video file.")
        print(f"   If there is a video file next to subordinate.py, single file mode is used. Otherwise, batch mode is used.\n")
        print(f"   {Fore.YELLOW}In your .config, the setting 'series_mode' is available.\n   It is 'false' by default, but set it to 'true' if you want to process TV series.{Style.RESET_ALL}")
        print(f"   {Fore.LIGHTRED_EX}Do not mix single movies and series in one run, as this WILL cause unwanted results!{Style.RESET_ALL}\n")
        print(f"   So make sure that your video files are correctly organized before starting.\n")
    elif page == 4:
        print(f"{Style.BRIGHT}{Fore.CYAN}[4/5] Running Subservient and pre-flight checklist{Style.RESET_ALL}\n")
        print(f"{Fore.GREEN}4.{Style.RESET_ALL} Once subordinate.py is in the right place, run it and choose {Fore.YELLOW}'1'{Style.RESET_ALL} to start.")
        print(f"   You will see a pre-flight checklist with all important variables and settings.")
        print(f"   Carefully check these before continuing.")
        print(f"   If everything looks correct, you can proceed.\n")
        print(f"   Subservient will now go through the Extraction, Acquisition and Synchronisation phase.")
        print(f"   If everything is configured correctly, this process is automatic for the most part.")
        print(f"   Only when something is not clear for Subservient, will it start asking you what to do.\n")
    elif page == 5:
        print(f"{Style.BRIGHT}{Fore.CYAN}[5/5] Tips & Troubleshooting{Style.RESET_ALL}\n")
        print(f"{Fore.GREEN}*{Style.RESET_ALL} If you move subordinate.py, run it again in the new folder to update the location.")
        print(f"{Fore.GREEN}*{Style.RESET_ALL} All logs and outputs are saved in the main Subservient folder.")
        print(f"{Fore.GREEN}*{Style.RESET_ALL} If you have issues, check your .config and requirements first.")
        print(f"{Fore.GREEN}*{Style.RESET_ALL} For advanced options, see the README or .config comments.")
        print(f"{Fore.GREEN}*{Style.RESET_ALL} Still stuck? Open an issue on GitHub or ask ChatGPT for help.\n")
        print(f"{Fore.LIGHTWHITE_EX}Subservient is free and open source.\nIf you appreciate the project, you can support future development via Buy Me a Coffee:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}https://buymeacoffee.com/nexigen{Style.RESET_ALL}\n")
        print(f"{Fore.LIGHTWHITE_EX}I can't always offer one-on-one support to everyone, but donors are welcome to join my Discord for extra help.\nDonors can also get my builds/patches earlier (or as soon as I commit them) as an extra 'thank you'.\nMany thanks for understanding, for donating, and heck.. even just for using Subservient.{Style.RESET_ALL}")
        print(f"{Fore.LIGHTMAGENTA_EX}-Nexigen")
def show_instructions():
    """Show paginated instructions for using Subservient.
    
    Interactive instruction manual with navigation between pages allowing
    users to go through 5 pages of setup and usage instructions.
    """
    page = 1
    total_pages = 5
    while True:
        print_instructions_page(page)
        if page < total_pages:
            nav = input(f"\n{Style.BRIGHT}{Fore.YELLOW}Press Enter for next page, or {Fore.CYAN}b{Style.RESET_ALL}{Style.BRIGHT}{Fore.YELLOW} to go back to the main menu:{Style.RESET_ALL} ").strip().lower()
            if nav == 'b':
                break
            page += 1
        else:
            input(f"\n{Style.BRIGHT}{Fore.YELLOW}Press Enter to return to the main menu.{Style.RESET_ALL} ")
            break
    utils.clear_and_print_ascii(BANNER_LINE)
    print(f"{Style.BRIGHT}{Fore.BLUE}[Subservient]{Style.RESET_ALL} This is the central script for Subservient subtitle automation.")
    print(f"{Style.BRIGHT}{Fore.BLUE}[Subservient]{Style.RESET_ALL} My anchor location is: {Fore.YELLOW}{Path(__file__).resolve().parent}{Style.RESET_ALL}\n")
    print(f"{Style.DIM}When unsure how to proceed, you can consult the README file or press option '3' for guidance.{Style.RESET_ALL}")
    print_main_menu()
def reconstruct_config():
    """Interactive configuration file reconstruction with user prompts.
    
    Creates a new .config file with default template and prompts user for 
    confirmation if existing config file is found.
    """
    utils.clear_and_print_ascii(BANNER_LINE)
    print(f"{Style.BRIGHT}{Fore.YELLOW}You can use this option to reconstruct the .config file if your current config is missing or not working properly.{Style.RESET_ALL}\n")
    print(f"{Fore.WHITE}A new .config file will be created in the same directory as this script ({Path(__file__).parent}).{Style.RESET_ALL}")
    print(f"{Fore.WHITE}To use it, you must move this .config file back to the main Subservient folder if it is not already there.{Style.RESET_ALL}")
    print(f"{Fore.LIGHTRED_EX}All settings in the new .config will need to be re-entered manually!{Style.RESET_ALL}\n")
    print(f"{Fore.GREEN}1{Style.RESET_ALL} = Create new .config file now")
    print(f"{Fore.RED}2{Style.RESET_ALL} = Return to main menu\n")
    choice = input(f"Make a choice [{Fore.GREEN}1{Style.RESET_ALL}/{Fore.RED}2{Style.RESET_ALL}]: ").strip()
    if choice != "1":
        print(f"{Fore.YELLOW}Config reconstruction cancelled. Returning to main menu.{Style.RESET_ALL}")
        input("Press Enter to continue...")
        print_full_main_menu()
        return
    
    config_path = Path(__file__).parent / '.config'
    if config_path.exists():
        print(f"{Fore.YELLOW}A .config file already exists at: {config_path}{Style.RESET_ALL}")
        confirm = input(f"{Fore.RED}Overwrite existing .config? (y/n): {Style.RESET_ALL}").strip().lower()
        if confirm != 'y':
            print(f"{Fore.GREEN}Config reconstruction cancelled.{Style.RESET_ALL}")
            input("Press Enter to return to the main menu...")
            print_full_main_menu()
            return
    
    ascii_lines = utils.ASCII_ART.splitlines()
    if ascii_lines:
        ascii_lines[0] = '  ' + ascii_lines[0].lstrip()
    ascii_block = '\n'.join(ascii_lines)
    config_template = f'''{ascii_block}
                             [.CONFIG FILE]

[SETUP]
# === Subtitle Acquisition Script Setup ===

# API_KEY: Your OpenSubtitles consumer API key
# USERNAME: Your OpenSubtitles username
# PASSWORD: Your OpenSubtitles password
# API_URL: OpenSubtitles API endpoint (only rename when OpenSubtitles changed their API URL)
api_key=
username=
password=
api_url= https://api.opensubtitles.com/api/v1

# - LANGUAGES: Comma-separated list of subtitle languages to download (e.g. nl,en).
#   These are the languages for which subtitles will be searched and downloaded.
#   This setting does NOT decide what happens to extracted languages not in this list, preserve_forced_subtitles and preserve_unwanted_subtitles do.
languages= en

# - AUDIO_TRACK_LANGUAGES: Comma-separated list of audio track languages to keep inside video files (e.g. nl,en,ja). ('undefined' tracks are always kept).
#   Tracks with a language not in the list are removed. Highly recommended to keep english in there, as 95% of all mainstream movies have english tracks only.
#   Set to 'ALL' to disable all audio track processing and keep all audio tracks unchanged (e.g. audio_track_languages = ALL)
audio_track_languages= en,ja

# - ACCEPT_OFFSET_THRESHOLD: If a subtitle synchronisation is below this threshold, then the subtitle will be accepted without needing further manual user verification.
#   Generally speaking: A higher setting saves time, but may result in poorer syncs being accepted unconditionally.
#   A lower setting leads to only very excellently synced subtittles getting through.
#   Try finding your ideal balance by testing it on videos. I personally find that somewhere between 0.05 and 0.1 strikes a good balance
accept_offset_threshold= 0.05

# - REJECT_OFFSET_THRESHOLD: If a subtitle synchronisation is above this threshold, then the subtitle will be rejected, meaning it will be marked as DRIFT and will be discarded later.
#   Generally speaking: Higher settings will lead to less rejections, but more manual checkups for you to go through.
#   Lower settings will lead to very fast rejections, making videos run out of subtitle candidates very quickly.
#   NOTE: Increasing the threshold is usually recommended when you notice that many movies can't find good subtitle candidates anymore.
#   I personally find that around 2 to 2.5 seconds strikes a good balance.
#   You could try up to 4 seconds if you want to be more lenient, but I would not recommend going any higher, unless some videos are consistently rejected.
reject_offset_threshold= 2.5

# - SERIES_MODE: If true, treat all videos in the same folder as episodes of a TV series.
#   If false, only the largest video file in each folder is processed (movie mode).
series_mode= false

# - DELETE_EXTRA_VIDEOS: If true, all extra video files in a folder will be permanently deleted.
#   If false, extra video files will be moved to a folder named by EXTRAS_FOLDER_NAME.
#   This setting is ignored if series_mode is true (in series mode, all videos are kept).
# - EXTRAS_FOLDER_NAME: Name of the folder where extra video files are moved if DELETE_EXTRA_VIDEOS is false.
delete_extra_videos= false
extras_folder_name= extras

# - PRESERVE_FORCED_SUBTITLES: If true, forced subtitle tracks will be preserved and not replaced by full subtitles.
#   Forced subtitles are typically used for foreign dialogue in otherwise native-language movies.
#   If false, forced subtitles will be treated like regular subtitles and may be replaced.
# - PRESERVE_UNWANTED_SUBTITLES: If true, all internal and external subtitle tracks will be kept, even those not in the wanted languages list.
#   If false, subtitle tracks not in the wanted languages will be removed during cleanup.
#   This only affects cleanup behavior - the languages list still controls which subtitles are downloaded and synchronized.
preserve_forced_subtitles= false
preserve_unwanted_subtitles= false

# - PAUSE_SECONDS: Number of seconds to pause between phases, breaks, and other script waits.
#   If you don't mind about reading what happens in the terminal, a lower value can be set. Example: 5 means a 5 second pause between phases and after summaries. Average speed = 5.
pause_seconds= 5

# - MAX_SEARCH_RESULTS: Maximum number of subtitle search results to consider per movie (e.g. 10).
#   Increasing MAX_SEARCH_RESULTS can help find more options, but may slow down processing.
#   When having a low download limit and many videos to sync, it's strongly recommended to not go higher than 12. As a VIP you can easily go for 20 or more.
max_search_results= 10

# - TOP_DOWNLOADS: Number of subtitles to download and test per batch.
#   Keeping TOP_DOWNLOADS low preserves your daily download limit by first testing one batch before downloading another batch.
#   If you need to sync many videos, take 2 to 4 as a maximum. When you have 1000 downloads a day, you could set this to, say, 5-10, for significantly faster processing.
top_downloads= 3

# - DOWNLOAD_RETRY_503: Number of retry attempts for HTTP 503 Service Unavailable errors during subtitle downloads.
#   503 errors typically indicate OpenSubtitles servers are temporarily overloaded. Higher values increase chance of success but slow down processing.
#   Recommended: 6 for good balance between success rate and speed. Set to 3 for faster processing, 10 for maximum persistence.
download_retry_503= 6

# - SKIP_DIRS: Comma-separated list of directory names to skip when scanning for videos (e.g. extras,trailers,samples).
#   These directories will be ignored during video discovery in both movie and series mode. Use lowercase names, matching is case-insensitive.
#   Common examples: extras, trailers, samples, bonus.
skip_dirs= new folder,nieuwe map,extra,extra's,extras,featurettes,bonus,bonusmaterial,bonus_material,behindthescenes,behind_the_scenes,deletedscenes,deleted_scenes,interviews,makingof,making_of,scenes,trailer,trailers,sample,samples,other,misc,specials,special_features,documentary,docs,docu,promo,promos,bloopers,outtakes

# - UNWANTED_TERMS: Comma-separated list of words/terms that should be filtered from subtitle search results.
#   For example, a search can be 'Lord of the Rings 2001 [h.265 HEVC 10 bit]'.
#   The whole latter part would then be removed, so that 'The lord of the Rings 2001' remains, giving a good search query.
#   Legal disclaimer: These filters clean technical metadata from filenames regardless of source.
#   Subservient is designed for use with content you legally own or have rights to process.
#   The inclusion of various format and distribution tags serves technical interoperability purposes only.
UNWANTED_TERMS= sample,cam,ts,workprint,unrated,uncut,720p,1080p,2160p,480p,4k,uhd,imax,eng,ita,jap,hindi,web,webrip,web-dl,bluray,brrip,bdrip,dvdrip,hdrip,hdtv,remux,x264,x265,h.264,h.265,hevc,avc,hdr,hdr10,hdr10+,dv,dolby.vision,sdr,10bit,8bit,ddp,dd+,dts,aac,ac3,eac3,truehd,atmos,flac,5.1,7.1,2.0,yts,yts.mx,yify,rarbg,fgt,galaxyrg,cm8,evo,sparks,drones,amiable,kingdom,tigole,chd,ddr,hdchina,cinefile,ettv,eztv,aXXo,maven,fitgirl,skidrow,reloaded,codex,cpy,conspir4cy,hoodlum,hive-cm8,extras,final.cut,open.matte,hybrid,version,v2,proper,limited,dubbed,subbed,multi,dual.audio,complete.series,complete.season,Licdom,ac,sub,nl,en,ita,eng,subs,rip,h265,xvid,mp3,mp4,avi,Anime Time,[Anime Time]

# - RUN_COUNTER: used to count how many full runs have been made. Also used to organize logfiles
#   Don't change if you don't need to, as it may result in overwriting existing logs
run_counter= 0

# === END OF SETUP ===
# ------------------------------------------------------------
# Everything below is managed automatically by the application.
# Only change this if you know what you are doing!

[RUNTIME]

'''
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(config_template)
    print(f"{Fore.GREEN}New .config file created at: {config_path}{Style.RESET_ALL}\n")
    input("Press Enter to return to the main menu...")
    print_full_main_menu()
def import_utils():
    """Import utils module and handle missing file error gracefully.
    
    Dynamically imports the utils module from the registered path and handles
    cases where utils.py cannot be found via pathfile. Also handles location mismatches.
    """
    config_dir = Path(user_config_dir()) / "Subservient"
    pathfile = config_dir / "Subservient_pathfiles"
    utils_path = None
    
    if pathfile.exists():
        try:
            with open(pathfile, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("utils_path="):
                        utils_path = line.strip().split("=", 1)[1]
                        break
        except Exception:
            pass
    
    if utils_path and Path(utils_path).exists():
        try:
            spec = importlib.util.spec_from_file_location("utils", utils_path)
            utils = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(utils)
            return utils
        except Exception:
            pass
    
    current_dir_utils = Path(__file__).parent / "utils.py"
    if current_dir_utils.exists():
        try:
            spec = importlib.util.spec_from_file_location("utils", str(current_dir_utils))
            utils = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(utils)
            return utils
        except Exception:
            pass
    
    print(f"{Fore.RED}{Style.BRIGHT}[SETUP ERROR]{Style.RESET_ALL} Cannot continue - required files are missing.\n")
    print(f"{Fore.YELLOW}Could not locate utils.py in the expected locations:{Style.RESET_ALL}")
    print(f"  - Pathfile location: {utils_path if utils_path else 'Not found in configuration'}")
    print(f"  - Current directory: {current_dir_utils}")
    print(f"\n{Fore.WHITE}This usually happens when:{Style.RESET_ALL}")
    print(f"  1. subordinate.py was moved without the other Subservient files")
    print(f"  2. The Subservient installation is incomplete or corrupted")
    print(f"\n{Fore.WHITE}To resolve this issue:{Style.RESET_ALL}")
    print(f"  1. Ensure subordinate.py is in the main Subservient folder")
    print(f"  2. Verify all required files are present and intact")
    print(f"  3. Run subordinate.py from the main folder to complete setup")
    print(f"\n{Fore.WHITE}If the problem persists, consider re-downloading Subservient from the official repository.{Style.RESET_ALL}")
    input("\nPress Enter to exit...")
    sys.exit(1)

def ensure_initial_setup():
    """Ensure initial Subservient setup is complete with pathfiles and config.
    
    Verifies that all required Subservient scripts are present and registers their paths.
    Creates pathfile with script locations for cross-module access and exits with error if required scripts are missing.
    Also detects if subordinate.py has been moved and requires re-setup.
    """
    required_keys = ["subservient_anchor", "subordinate_path", "extraction_path", "acquisition_path", "synchronisation_path", "utils_path"]
    required_scripts = ["subordinate.py", "extraction.py", "acquisition.py", "synchronisation.py", "utils.py"]
    
    config_dir = Path(user_config_dir()) / "Subservient"
    config_dir.mkdir(parents=True, exist_ok=True)
    pathfile = config_dir / "Subservient_pathfiles"
    
    current_subordinate_path = str(Path(__file__).resolve())

    def valid_pathfile():
        """Check if pathfile exists and contains all required keys."""
        if not pathfile.exists():
            return False
        lines = pathfile.read_text(encoding="utf-8").splitlines()
        kv = {k.strip(): v.strip() for l in lines if '=' in l for k, v in [l.split('=', 1)]}
        return all(k in kv and kv[k] for k in required_keys)
    
    def check_subservient_files_location():
        """Check if the other Subservient files are still in their expected locations."""
        if not pathfile.exists():
            return True
        
        try:
            lines = pathfile.read_text(encoding="utf-8").splitlines()
            essential_files = ["extraction_path", "acquisition_path", "synchronisation_path", "utils_path"]
            
            for line in lines:
                for file_key in essential_files:
                    if line.startswith(f"{file_key}="):
                        expected_path = Path(line.split("=", 1)[1].strip())
                        if not expected_path.exists():
                            return False
            return True
        except Exception:
            return False
    
    if pathfile.exists() and not check_subservient_files_location():
        print(f"{Fore.RED}{Style.BRIGHT}[SETUP ERROR]{Style.RESET_ALL} Subservient files location mismatch detected!\n")
        print(f"{Fore.YELLOW}It appears that the Subservient folder has been moved or some files are missing.{Style.RESET_ALL}")
        
        try:
            lines = pathfile.read_text(encoding="utf-8").splitlines()
            essential_files = ["extraction_path", "acquisition_path", "synchronisation_path", "utils_path"]
            missing_files = []
            
            for line in lines:
                for file_key in essential_files:
                    if line.startswith(f"{file_key}="):
                        expected_path = Path(line.split("=", 1)[1].strip())
                        if not expected_path.exists():
                            missing_files.append(f"{file_key.replace('_path', '.py')}: {expected_path}")
            
            if missing_files:
                print(f"{Fore.YELLOW}Missing files:{Style.RESET_ALL}")
                for missing in missing_files:
                    print(f"  - {Fore.WHITE}{missing}{Style.RESET_ALL}")
        except Exception:
            pass
        print(f"\n{Fore.WHITE}{Style.BRIGHT}SOLUTION:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}🔧 If you moved the entire Subservient folder:{Style.RESET_ALL}")
        print(f"  1. Put subordinate.py back in the main Subservient folder (where all other .py files are)")
        print(f"  2. Run subordinate.py once from that location to complete re-setup")
        print(f"  3. After setup completes, you can move subordinate.py anywhere again for video processing")
        print(f"\n{Fore.YELLOW}🔍 If individual files are missing or corrupted:{Style.RESET_ALL}")
        print(f"  1. Remove the current Subservient folder. If need be, you can make a backup of your .config file.")
        print(f"  2. Re-download Subservient from the official GitHub repository")
        print(f"  3. Ensure all required .py files are present in the main folder")
        print(f"\n{Fore.LIGHTBLUE_EX}📂 Current subordinate.py location: {Fore.WHITE}{Path(__file__).resolve().parent}{Style.RESET_ALL}")
        
        try:
            pathfile.unlink()
            print(f"\n{Fore.CYAN}✅ Old pathfile removed - fresh setup will run when you restart from main folder.{Style.RESET_ALL}")
        except Exception:
            pass
        
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    if valid_pathfile():
        return
    
    current_dir = Path(__file__).parent.resolve()
    missing = [s for s in required_scripts if not (current_dir / s).exists()]
    if missing:
        print(f"{Fore.RED}{Style.BRIGHT}[SETUP ERROR]{Style.RESET_ALL} Subservient failed to launch - required files are missing.\n")
        print(f"{Fore.YELLOW}The following required scripts are missing in the current directory:{Style.RESET_ALL}")
        for s in missing:
            print(f"  {Fore.RED}• {s}{Style.RESET_ALL}")
        print(f"\n{Fore.WHITE}To resolve this issue:{Style.RESET_ALL}")
        print(f"  1. Move subordinate.py back to the main Subservient folder")
        print(f"  2. Ensure all required files are present and intact")
        print(f"  3. Run subordinate.py from the main folder to complete setup")
        print(f"\n{Fore.WHITE}If files are genuinely missing, consider re-downloading Subservient from the official repository.{Style.RESET_ALL}")
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    print(f"\n{Fore.GREEN}{Style.BRIGHT}All required scripts found!{Style.RESET_ALL}\n")
    print(f"{Fore.CYAN}Registering script paths and setting up Subservient...{Style.RESET_ALL}\n")
    
    with open(pathfile, "w", encoding="utf-8") as f:
        f.write(f"subservient_anchor={current_dir}\n")
        f.write(f"subordinate_path={current_dir / 'subordinate.py'}\n")
        f.write(f"extraction_path={current_dir / 'extraction.py'}\n")
        f.write(f"acquisition_path={current_dir / 'acquisition.py'}\n")
        f.write(f"synchronisation_path={current_dir / 'synchronisation.py'}\n")
        f.write(f"utils_path={current_dir / 'utils.py'}\n")
    
    print(f"{Fore.GREEN}Initial setup complete! All script paths have been registered.{Style.RESET_ALL}\n")
    print(f"{Fore.YELLOW}You can now continue using Subservient.\n"
          f"You may move subordinate.py to any folder you want to process.\n"
          f"(You can use it for a single movie or a batch of folders.)\n"
          f"For more help, read the README file or the instructions inside subordinate.py.{Style.RESET_ALL}\n")
    input("Press Enter to continue...")
    if not valid_pathfile():
        print(f"{Fore.RED}{Style.BRIGHT}[ERROR]{Style.RESET_ALL} Pathfile is incomplete or invalid after setup. Please check your files and try again.")
        sys.exit(1)
ensure_initial_setup()
utils = import_utils()
write_anchor_to_pathfile()
write_subordinate_path_to_pathfile()
def get_log_path():
    """Get path for requirements log file based on run counter.
    
    Creates logs directory if needed and returns the log file path using
    the main Subservient folder for logs, not the local subordinate.py location.
    """
    config_dir = Path(user_config_dir()) / "Subservient"
    pathfile = config_dir / "Subservient_pathfiles"
    
    subservient_anchor = None
    if pathfile.exists():
        with open(pathfile, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("utils_path="):
                    utils_path = Path(line.split("=", 1)[1].strip())
                    subservient_anchor = utils_path.parent
                    break
    
    if not subservient_anchor:
        subservient_anchor = Path(__file__).parent.resolve()
    
    logs_dir = subservient_anchor / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return logs_dir / f"install_log_{log_timestamp}.txt"

def log_requirements_event(message):
    """Log requirements-related event to requirements log file.
    
    Logs a timestamped message to the requirements installation log file.
    """
    log_path = get_log_path()
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {message}\n")

def get_config_and_pause_seconds():
    """Load configuration settings and extract pause_seconds value.
    
    Returns:
        tuple: (config dict, pause_seconds float)
    """
    config_dir = Path(user_config_dir()) / "Subservient"
    pathfile = config_dir / "Subservient_pathfiles"
    anchor_path = Path(__file__).parent.resolve()
    
    if pathfile.exists():
        with open(pathfile, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("utils_path="):
                    utils_path = Path(line.split("=", 1)[1].strip())
                    anchor_path = utils_path.parent
                    break
    
    config_path = anchor_path / '.config'
    config = {}
    if config_path.exists():
        with open(config_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                m = re.match(r'^([a-zA-Z0-9_]+)\s*=\s*(.+)$', line)
                if m:
                    config[m.group(1).strip().lower()] = m.group(2).strip()
    
    pause_seconds = float(config.get('pause_seconds', 5))
    return config, pause_seconds

def check_requirements_status():
    """Comprehensive check and installation of all required packages and tools.
    
    This complex function tests all Python packages, external tools like ffmpeg and MKVToolNix,
    and Windows-specific build tools. It displays detailed status information, performs
    functional tests where possible, and logs all results to file for troubleshooting.
    """
    import importlib
    import time
    import pycountry
    import requests
    import re
    config, pause_seconds = get_config_and_pause_seconds()
    status_lines = []
    log_requirements_event("--- REQUIREMENTS VERIFICATION START ---")
    
    from platformdirs import user_config_dir
    config_dir = Path(user_config_dir()) / "Subservient"
    pathfile = Path(config_dir) / "Subservient_pathfiles"
    anchor_path = Path(__file__).parent
    
    if pathfile.exists():
        with open(pathfile, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("utils_path="):
                    utils_path = Path(line.split("=", 1)[1].strip())
                    anchor_path = utils_path.parent
                    break
    
    config_path = anchor_path / '.config'
    config = {}
    if config_path.exists():
        with open(config_path, encoding='utf-8') as f:
            for line in f:
                m = re.match(r'^([a-zA-Z0-9_]+)\s*=\s*(.+)$', line.strip())
                if m:
                    config[m.group(1).strip().lower()] = m.group(2).strip()
    
    required = [
        ("colorama", "Colorama"),
        ("platformdirs", "Platformdirs"),
        ("requests", "Requests"),
        ("tqdm", "Tqdm"),
        ("pycountry", "PyCountry"),
        ("ffsubsync", "ffsubsync"),
        ("langdetect", "langdetect"),
    ]
    
    total = len(required) + 3 
    for idx, (mod, display) in enumerate(required, 1):
        utils.clear_and_print_ascii(BANNER_LINE)
        print(f"{Fore.LIGHTYELLOW_EX}Subservient is currently testing {display}... {Fore.LIGHTBLUE_EX}[{idx}/{total}]{Style.RESET_ALL}")
        test_passed = False
        test_msg = ""
        
        try:
            m = importlib.import_module(mod)
            if mod == "colorama":
                _ = m.Fore.GREEN + m.Style.RESET_ALL
                test_passed = True
                test_msg = "colorama functional test passed"
            elif mod == "platformdirs":
                from platformdirs import user_config_dir
                _ = user_config_dir("SubservientTest")
                test_passed = True
                test_msg = "platformdirs functional test passed"
            elif mod == "requests":
                print(f"{Fore.LIGHTYELLOW_EX}Testing internet connectivity... {Fore.LIGHTBLUE_EX}[{idx}/{total}]{Style.RESET_ALL}")
                for i in range(5):
                    try:
                        r = requests.get("https://httpbin.org/get", timeout=3)
                        if r.status_code == 200:
                            test_passed = True
                            test_msg = "requests functional test passed"
                            break
                    except Exception as e:
                        log_requirements_event(f"Requests attempt {i+1}: {e}")
                    if i < 4:
                        time.sleep(pause_seconds)
                if not test_passed:
                    test_msg = "requests functional test failed"
            elif mod == "tqdm":
                from tqdm import tqdm
                for _ in tqdm(range(1), disable=True):
                    pass
                test_passed = True
                test_msg = "tqdm functional test passed"
            elif mod == "pycountry":
                lang = pycountry.languages.get(alpha_2="en")
                test_passed = lang is not None and hasattr(lang, "alpha_3")
                test_msg = "pycountry functional test passed" if test_passed else "pycountry lookup failed"
            elif mod == "ffsubsync":
                result = subprocess.run(["ffsubsync", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                output = result.stdout.decode(errors="ignore") + result.stderr.decode(errors="ignore")
                version_match = re.search(r"\d+\.\d+(\.\d+)?", output)
                test_passed = result.returncode == 0 and version_match is not None
                test_msg = "ffsubsync version check passed" if test_passed else f"ffsubsync version check failed"
            elif mod == "langdetect":
                from langdetect import detect
                detected = detect("This is an English sentence.")
                test_passed = detected == "en"
                test_msg = "langdetect functional test passed" if test_passed else f"langdetect returned '{detected}'"
            
            log_requirements_event(f"{display:<13} : {'working' if test_passed else 'installed, but not working'} | {test_msg}")
            status = f"{Fore.WHITE}[{Fore.GREEN}working{Fore.WHITE}]{Style.RESET_ALL}" if test_passed else f"{Fore.WHITE}[{Fore.YELLOW}installed, but not working{Fore.WHITE}]{Style.RESET_ALL}"
            
        except Exception as e:
            status = f"{Fore.WHITE}[{Fore.LIGHTRED_EX}not installed{Fore.WHITE}]{Style.RESET_ALL}"
            log_requirements_event(f"{display:<13} : not installed | import failed: {e}")
        
        status_lines.append(f"{Fore.YELLOW}{display:<13}{Style.RESET_ALL} : {status}")
    
    utils.clear_and_print_ascii(BANNER_LINE)
    print(f"{Fore.LIGHTYELLOW_EX}Testing ffmpeg... {Fore.LIGHTBLUE_EX}[{total-2}/{total}]{Style.RESET_ALL}")
    
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        ffmpeg_status = f"{Fore.WHITE}[{Fore.GREEN}working{Fore.WHITE}]{Style.RESET_ALL}"
        log_requirements_event("ffmpeg working")
    except Exception as e:
        ffmpeg_status = f"{Fore.WHITE}[{Fore.LIGHTRED_EX}not installed{Fore.WHITE}]{Style.RESET_ALL}"
        log_requirements_event(f"ffmpeg not installed: {e}")
    
    status_lines.append(f"{Fore.YELLOW}ffmpeg       {Style.RESET_ALL} : {ffmpeg_status}")
    
    utils.clear_and_print_ascii(BANNER_LINE)
    print(f"{Fore.LIGHTYELLOW_EX}Testing MKVToolNix (mkvmerge)... {Fore.LIGHTBLUE_EX}[{total-1}/{total}]{Style.RESET_ALL}")
    
    try:
        result = subprocess.run(["mkvmerge", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        mkvmerge_status = f"{Fore.WHITE}[{Fore.GREEN}working{Fore.WHITE}]{Style.RESET_ALL}"
        log_requirements_event("MKVToolNix (mkvmerge) working")
    except Exception as e:
        mkvmerge_status = f"{Fore.WHITE}[{Fore.LIGHTRED_EX}not installed{Fore.WHITE}]{Style.RESET_ALL}"
        log_requirements_event(f"MKVToolNix (mkvmerge) not installed: {e}")
    
    status_lines.append(f"{Fore.YELLOW}MKVToolNix    {Style.RESET_ALL} : {mkvmerge_status}")
    
    utils.clear_and_print_ascii(BANNER_LINE)
    print(f"{Fore.LIGHTYELLOW_EX}Testing Microsoft Visual C++ Build Tools... {Fore.LIGHTBLUE_EX}[{total}/{total}]{Style.RESET_ALL}")
    
    if os.name == 'nt':
        try:
            import shutil
            cl_path = shutil.which('cl')
            
            if cl_path:
                try:
                    result = subprocess.run(['cl'], capture_output=True, text=True, timeout=5)
                    version_info = result.stderr
                    
                    if 'Microsoft' in version_info:
                        if any(v in version_info for v in ['19.', '18.', '17.', '16.', '15.', '14.']):
                            msvc_status = f"{Fore.WHITE}[{Fore.GREEN}working{Fore.WHITE}]{Style.RESET_ALL}"
                            log_requirements_event("Microsoft Visual C++ Build Tools working")
                        else:
                            msvc_status = f"{Fore.WHITE}[{Fore.YELLOW}old version{Fore.WHITE}]{Style.RESET_ALL}"
                            log_requirements_event("Microsoft Visual C++ Build Tools - old version detected")
                    else:
                        msvc_status = f"{Fore.WHITE}[{Fore.LIGHTRED_EX}not working{Fore.WHITE}]{Style.RESET_ALL}"
                        log_requirements_event("Microsoft Visual C++ Build Tools - cl.exe found but not working")
                except Exception as e:
                    msvc_status = f"{Fore.WHITE}[{Fore.YELLOW}found but error{Fore.WHITE}]{Style.RESET_ALL}"
                    log_requirements_event(f"Microsoft Visual C++ Build Tools - found but error: {e}")
            else:
                import glob
                vs_patterns = [
                    r"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                    r"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio\*\BuildTools\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio\*\BuildTools\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\bin\cl.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio\2017\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio\2017\*\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe"
                ]
                
                found_cl = False
                for pattern in vs_patterns:
                    matches = glob.glob(pattern)
                    if matches:
                        found_cl = True
                        break
                
                if found_cl:
                    msvc_status = f"{Fore.WHITE}[{Fore.YELLOW}found but not in PATH{Fore.WHITE}]{Style.RESET_ALL}"
                    log_requirements_event("Microsoft Visual C++ Build Tools - found but not in PATH")
                else:
                    msvc_status = f"{Fore.WHITE}[{Fore.LIGHTRED_EX}not installed{Fore.WHITE}]{Style.RESET_ALL}"
                    log_requirements_event("Microsoft Visual C++ Build Tools not found")
        except Exception as e:
            msvc_status = f"{Fore.WHITE}[{Fore.LIGHTRED_EX}check failed{Fore.WHITE}]{Style.RESET_ALL}"
            log_requirements_event(f"Microsoft Visual C++ Build Tools check failed: {e}")
    else:
        msvc_status = f"{Fore.WHITE}[{Fore.CYAN}not needed (non-Windows){Fore.WHITE}]{Style.RESET_ALL}"
        log_requirements_event("Microsoft Visual C++ Build Tools - not needed on non-Windows system")
    
    status_lines.append(f"{Fore.YELLOW}MSVC Build Tools{Style.RESET_ALL} : {msvc_status}")
    
    utils.clear_and_print_ascii(BANNER_LINE)
    print(f"{Style.BRIGHT}{Fore.CYAN}Subservient Requirements Status{Style.RESET_ALL}\n")
    for line in status_lines:
        print(line)
    
    print(f"\n{Fore.WHITE}If any are not working or installed, please check the README for installation instructions.{Style.RESET_ALL}")
    
    missing_external_tools = []
    if ffmpeg_status == f"{Fore.WHITE}[{Fore.LIGHTRED_EX}not installed{Fore.WHITE}]{Style.RESET_ALL}":
        missing_external_tools.append("ffmpeg")
    if mkvmerge_status == f"{Fore.WHITE}[{Fore.LIGHTRED_EX}not installed{Fore.WHITE}]{Style.RESET_ALL}":
        missing_external_tools.append("MKVToolNix")
    if os.name == 'nt' and any(status in str(msvc_status) for status in ['not installed', 'check failed']):
        missing_external_tools.append("Microsoft Visual C++ Build Tools")
    
    if missing_external_tools:
        print(f"{Fore.WHITE}Look for section: {Fore.CYAN}'1. Installing and Configuring Subservient', step 4{Style.RESET_ALL}")
        print(f"{Fore.WHITE}You can open the README from the main menu (option 6) or simply double click the readme in the main folder.{Style.RESET_ALL}")
    
    print(f"{Fore.LIGHTBLUE_EX}A timestamped install_log is saved in the logs folder inside Subservient.{Style.RESET_ALL}")
    log_requirements_event("--- REQUIREMENTS VERIFICATION END ---")
    input(f"{Fore.LIGHTYELLOW_EX}Press Enter to return to the main menu...{Style.RESET_ALL}")
    print_full_main_menu()

def quick_requirements_check():
    """Perform a quick check of essential requirements before launching extraction.
    
    Returns True if all essential tools are available, False otherwise.
    """
    import shutil
    import glob
    
    essential_tools = {
        'ffmpeg': 'ffmpeg',
        'mkvmerge': 'MKVToolNix',
        'ffsubsync': 'ffsubsync'
    }
    
    missing_tools = []
    tool_status = []
    
    for tool, display_name in essential_tools.items():
        if not shutil.which(tool):
            missing_tools.append(display_name)
        else:
            tool_status.append(f"{Fore.GREEN}{display_name} found!{Style.RESET_ALL}")
    
    if os.name == 'nt':
        cl_path = shutil.which('cl')
        if cl_path:
            tool_status.append(f"{Fore.GREEN}Microsoft Visual C++ Build Tools found!{Style.RESET_ALL}")
        else:
            vs_patterns = [
                r"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                r"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                r"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe",
                r"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe",
                r"C:\Program Files (x86)\Microsoft Visual Studio\*\BuildTools\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                r"C:\Program Files (x86)\Microsoft Visual Studio\*\BuildTools\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe",
                r"C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\bin\cl.exe",
                r"C:\Program Files (x86)\Microsoft Visual Studio\2017\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                r"C:\Program Files (x86)\Microsoft Visual Studio\2017\*\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe"
            ]
            found_cl = any(glob.glob(pattern) for pattern in vs_patterns)
            
            if found_cl:
                tool_status.append(f"{Fore.GREEN}Microsoft Visual C++ Build Tools found!{Style.RESET_ALL} {Fore.WHITE}(not in PATH){Style.RESET_ALL}")
            else:
                missing_tools.append("Microsoft Visual C++ Build Tools")
    
    if tool_status:
        print(f"{Fore.LIGHTYELLOW_EX}Checking for external tools...{Style.RESET_ALL}")
        for status in tool_status:
            print(status)
    
    if missing_tools:
        utils.clear_and_print_ascii(BANNER_LINE)
        print(f"{Fore.RED}{Style.BRIGHT}[PRE-FLIGHT CHECK FAILED]{Style.RESET_ALL}\n")
        print(f"{Fore.YELLOW}The following essential tools are missing:{Style.RESET_ALL}")
        for tool in missing_tools:
            print(f"  - {Fore.RED}{tool}{Style.RESET_ALL}")
        print(f"\n{Fore.LIGHTRED_EX}Subservient cannot start without these tools!{Style.RESET_ALL}")
        print(f"{Fore.WHITE}For detailed installation instructions, please see the README file.{Style.RESET_ALL}")
        print(f"{Fore.WHITE}Look for section: {Fore.CYAN}'1. Installing and Configuring Subservient', step 4{Style.RESET_ALL}")
        print(f"{Fore.WHITE}You can open the README from the main menu (option 6) or simply double click the readme in the main folder.{Style.RESET_ALL}")
        input(f"\n{Fore.YELLOW}Press Enter to exit Subservient...{Style.RESET_ALL} ")
        sys.exit(1)
        return False
    
    return True

def print_full_main_menu():
    """Display complete main menu with all available options."""
    """Display the banner and full main menu with location information."""
    utils.clear_and_print_ascii(BANNER_LINE)
    print(f"{Style.BRIGHT}{Fore.BLUE}[Subservient]{Style.RESET_ALL} This is the central script for Subservient subtitle automation.")
    print(f"{Style.BRIGHT}{Fore.BLUE}[Subservient]{Style.RESET_ALL} My anchor location is: {Fore.YELLOW}{Path(__file__).resolve().parent}{Style.RESET_ALL}\n")
    print(f"{Style.DIM}When unsure how to proceed, you can consult the README file or press option '3' for guidance.{Style.RESET_ALL}")
    print_main_menu()

def main():
    """Main application loop handling user menu choices and navigation.
    
    Processes user input and calls appropriate functions for each menu option.
    """
    print_full_main_menu()
    while True:
        choice = input(f"{Fore.LIGHTYELLOW_EX}Make a choice:{Style.RESET_ALL} ").strip()
        if choice == "1":
            while True:
                utils.clear_and_print_ascii(BANNER_LINE)
                print_subservient_checklist()
                config, pause_seconds = get_config_and_pause_seconds()
                start_choice = input(f"\nMake a choice [{Fore.GREEN}1{Style.RESET_ALL}/{Fore.RED}2{Style.RESET_ALL}]: ").strip()
                if start_choice == "1":
                    if not quick_requirements_check():
                        print_full_main_menu()
                        continue
                    
                    from platformdirs import user_config_dir
                    config_dir = Path(user_config_dir()) / "Subservient"
                    pathfile = config_dir / "Subservient_pathfiles"
                    extraction_path = None
                    if pathfile.exists():
                        lines = pathfile.read_text(encoding="utf-8").splitlines()
                        for l in lines:
                            if l.startswith("extraction_path="):
                                extraction_path = l.split("=", 1)[1].strip()
                                break
                    if extraction_path and Path(extraction_path).exists():
                        utils.clear_and_print_ascii(BANNER_LINE)
                        print(f"{Style.BRIGHT}{Fore.GREEN}[PRE-FLIGHT CHECK PASSED]{Style.RESET_ALL}")
                        print(f"{Style.BRIGHT}{Fore.BLUE}[Subordinate]{Style.RESET_ALL} Launching extraction.py at: {Fore.YELLOW}{extraction_path}{Style.RESET_ALL}")
                        print(f"\n{Style.BRIGHT}{Fore.GREEN}Extraction will start in {int(pause_seconds)} seconds...{Style.RESET_ALL}")
                        time.sleep(pause_seconds)
                        subprocess.run([sys.executable, extraction_path])
                        sys.exit(0)
                    else:
                        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Could not find extraction.py path in the universal pathfile or the file does not exist.")
                    return
                elif start_choice == "2":
                    print(f"{Style.BRIGHT}{Fore.BLUE}[Subservient]{Style.RESET_ALL} Exiting. Please complete your setup and try again.")
                    return
        elif choice == "2":
            run_subtitle_coverage_scan()
            print_full_main_menu()
            continue
        elif choice == "3":
            show_instructions()
        elif choice == "4":
            utils.clear_and_print_ascii(BANNER_LINE)
            print(f"{Style.BRIGHT}{Fore.BLUE}[Subordinate]{Style.RESET_ALL}{Fore.LIGHTYELLOW_EX} Gathering requirements...{Style.RESET_ALL}")
            ensure_core_requirements()
            req_path = Path(__file__).parent / 'requirements.txt'
            utils.clear_and_print_ascii(BANNER_LINE)
            print(f"{Fore.LIGHTYELLOW_EX}This option will (re)install and test the required packages.{Style.RESET_ALL}\n")
            print(f"{Fore.LIGHTYELLOW_EX}Checking for external tools...{Style.RESET_ALL}")
            import shutil
            ffmpeg_path = shutil.which("ffmpeg")
            mkvmerge_path = shutil.which("mkvmerge")
            
            if ffmpeg_path:
                try:
                    result = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True)
                    print(f"{Fore.GREEN}ffmpeg found!{Style.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.RED}Error running ffmpeg: {e}{Style.RESET_ALL}")
            else:
                print(f"\n{Fore.LIGHTRED_EX}ffmpeg is not installed or not found in your PATH.{Style.RESET_ALL}")
                print(f"ffmpeg is a crucial tool for Subservient to work properly.")
            
            if mkvmerge_path:
                try:
                    result = subprocess.run([mkvmerge_path, "--version"], capture_output=True, text=True)
                    print(f"{Fore.GREEN}MKVToolNix (mkvmerge) found!{Style.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.RED}Error running mkvmerge: {e}{Style.RESET_ALL}")
            else:
                print(f"\n{Fore.LIGHTRED_EX}MKVToolNix (mkvmerge) is not installed or not found in your PATH.{Style.RESET_ALL}")
                print(f"MKVToolNix is required for extracting subtitles from MKV files.")
            
            if not ffmpeg_path or not mkvmerge_path:
                print(f"\n{Fore.WHITE}For detailed installation instructions, please see the README file.{Style.RESET_ALL}")
                print(f"{Fore.WHITE}Look for section: {Fore.CYAN}'1. Installing and Configuring Subservient', step 4{Style.RESET_ALL}")
                print(f"{Fore.WHITE}You can also use option '7' from the main menu to open the README directly.{Style.RESET_ALL}")
            
            if os.name == 'nt':
                import glob
                cl_path = shutil.which('cl')
                
                if cl_path:
                    print(f"{Fore.GREEN}Microsoft Visual C++ Build Tools found!{Style.RESET_ALL}")
                else:
                    vs_patterns = [
                        r"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                        r"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                        r"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe",
                        r"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe",
                        r"C:\Program Files (x86)\Microsoft Visual Studio\*\BuildTools\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                        r"C:\Program Files (x86)\Microsoft Visual Studio\*\BuildTools\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe",
                        r"C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\bin\cl.exe",
                        r"C:\Program Files (x86)\Microsoft Visual Studio\2017\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
                        r"C:\Program Files (x86)\Microsoft Visual Studio\2017\*\VC\Tools\MSVC\*\bin\Hostx86\x86\cl.exe"
                    ]
                    found_cl = any(glob.glob(pattern) for pattern in vs_patterns)
                    
                    if found_cl:
                        print(f"{Fore.GREEN}Microsoft Visual C++ Build Tools found!{Style.RESET_ALL} {Fore.WHITE}(not in PATH){Style.RESET_ALL}")
                    else:
                        print(f"\n{Fore.LIGHTRED_EX}Microsoft Visual C++ Build Tools are not installed.{Style.RESET_ALL}")
                        print(f"Some Python packages require these tools to compile properly.")
                        print(f"{Fore.WHITE}In the README, look for chapter: {Fore.CYAN}'1. Installing and Configuring Subservient', step 4{Style.RESET_ALL}")
                        print(f"{Fore.WHITE}In there, check the 'External Tools' section for installation instructions.{Style.RESET_ALL}")
            
            print(f"{Fore.LIGHTYELLOW_EX}\nDo you want to proceed with (re)installing and testing?{Style.RESET_ALL}")
            print(f"  {Fore.GREEN}1{Style.RESET_ALL} = Yes, install and test everything")
            print(f"  {Fore.RED}2{Style.RESET_ALL} = No, return to main menu\n")
            sub_choice = input(f"Make a choice [{Fore.GREEN}1{Style.RESET_ALL}/{Fore.RED}2{Style.RESET_ALL}]: ").strip()
            if sub_choice != "1":
                print_full_main_menu()
                continue
            utils.clear_and_print_ascii(BANNER_LINE)
            print(f"{Fore.LIGHTYELLOW_EX}Installing requirements from requirements.txt...{Style.RESET_ALL}\n")
            log_requirements_event("--- REQUIREMENTS INSTALLATION START ---")
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', str(req_path)])
                print(f"{Fore.GREEN}Requirements installed successfully!{Style.RESET_ALL}\n")
                log_requirements_event("requirements.txt install: success")
            except Exception as e:
                print(f"{Fore.RED}Failed to install requirements: {e}{Style.RESET_ALL}\n")
                log_requirements_event(f"requirements.txt install: failed: {e}")
            log_requirements_event("--- REQUIREMENTS INSTALLATION END ---")
            check_requirements_status()
            continue
        elif choice == "5":
            show_extra_tools_menu()
            print_full_main_menu()
            continue
        elif choice == "6":
            reconstruct_config()
        elif choice == "7":
            utils.clear_and_print_ascii(BANNER_LINE)
            github_readme_url = "https://github.com/N3xigen/Subservient/blob/main/README.md"
            print(f"{Fore.YELLOW}Opening README on GitHub...{Style.RESET_ALL}\n")
            print(f"{Fore.LIGHTWHITE_EX}URL: {github_readme_url}{Style.RESET_ALL}")
            try:
                import webbrowser
                webbrowser.open(github_readme_url)
                print(f"{Fore.GREEN}README opened in your default browser!{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.LIGHTRED_EX}Could not open browser automatically.{Style.RESET_ALL}")
                print(f"{Fore.LIGHTWHITE_EX}In Docker environments, please copy the URL above and paste it in your browser.{Style.RESET_ALL}")
            input("Press Enter to return to the main menu...")
            print_full_main_menu()
            continue
        elif choice == "8":
            print(f"{Style.BRIGHT}{Fore.BLUE}[Subservient]{Style.RESET_ALL} Exiting.")
            return

def run_subtitle_coverage_scan():
    """Perform a subtitle coverage scan on videos in the current directory.
    
    Shows which videos have subtitles for configured languages.
    Handles errors gracefully and provides user feedback.
    """
    try:
        scan_banner = f"                   {Fore.YELLOW}Subtitle Coverage Scan{Style.RESET_ALL}"
        current_dir = Path(__file__).parent.resolve()
        config_dir = Path(user_config_dir()) / "Subservient"
        pathfile = config_dir / "Subservient_pathfiles"
        anchor_path = current_dir
        
        if pathfile.exists():
            with open(pathfile, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("subservient_anchor="):
                        anchor_path = Path(line.split("=", 1)[1].strip())
                        break
        
        languages = ['en']
        config_path1 = anchor_path / '.config'
        if config_path1.exists():
            languages = utils.get_languages_from_config(config_path1)
        else:
            try:
                subservient_folder = utils.get_subservient_folder()
                config_path2 = subservient_folder / '.config'
                if config_path2.exists():
                    languages = utils.get_languages_from_config(config_path2)
                else:
                    languages = utils.get_languages_from_config(None)
            except Exception:
                languages = ['en']
        
        videos = utils.find_videos_in_directory(current_dir)
        if not videos:
            utils.clear_and_print_ascii(scan_banner)
            print(f"{Fore.YELLOW}No videos found to scan in current directory.{Style.RESET_ALL}")
            input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")
            return
        
        coverage_results = utils.scan_subtitle_coverage(videos, languages, show_progress=True)
        utils.display_coverage_results(coverage_results, languages, scan_banner, return_to_menu=True)
        
    except Exception as e:
        utils.clear_and_print_ascii(BANNER_LINE)
        print(f"{Fore.RED}Error during subtitle coverage scan: {str(e)}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Make sure you have ffprobe installed and videos in the current directory.{Style.RESET_ALL}")
        input(f"\n{Fore.YELLOW}Press Enter to continue...{Style.RESET_ALL} ")

ensure_initial_setup()
utils = import_utils()
write_anchor_to_pathfile()
write_subordinate_path_to_pathfile()

if __name__ == "__main__":
    main()
