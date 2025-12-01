# 🎬 Subservient - The AI Subtitle Synchronizer

<div align="center">

[![Version](https://img.shields.io/badge/version-v0.88-brightgreen.svg)](https://github.com/N3xigen/Subservient)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-supported-orange.svg)](https://docker.com)
[![License](https://img.shields.io/badge/license-GPL--3.0-red.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue.svg)](https://github.com/N3xigen/Subservient)

[![Plex](https://img.shields.io/badge/Plex-compatible-orange.svg?logo=plex&logoColor=white)](https://plex.tv)
[![Jellyfin](https://img.shields.io/badge/Jellyfin-compatible-purple.svg?logo=jellyfin&logoColor=white)](https://jellyfin.org)
[![Emby](https://img.shields.io/badge/Emby-compatible-green.svg?logo=emby&logoColor=white)](https://emby.media)
[![Unraid](https://img.shields.io/badge/Unraid-compatible-red.svg?logo=unraid&logoColor=white)](https://unraid.net)

</div>


<br>

## 🔍 What Subservient Does

> **🎯 Automated subtitle synchronization for your video collection**
> 
> Transform your viewing experience with perfectly synchronized subtitles in multiple languages.
>Subservient automatically extracts, downloads, and syncs subtitle files using advanced audio analysis, eliminating the frustration of out-of-sync dialogue.
> Unlike comprehensive media management systems like Bazarr or Sonarr, Subservient is a focused, standalone application dedicated specifically to subtitle synchronization.<br>Simply point it at your video files, and it handles the technical complexity while giving you control over the results.

### 🔄 Core Workflow
**Extract** → **Download** → **Synchronize** → **Verify**

1. **📤 Subtitle Extraction**: Automatically extracts embedded subtitles from video files
2. **🌐 Intelligent Download**: Searches OpenSubtitles for missing languages based on your preferences  
3. **🎵 Audio-Based Synchronization**: Uses FFSubSync's advanced audio analysis to achieve frame-perfect timing
4. **✅ Quality Verification**: Presents sync results for manual verification when automatic quality thresholds aren't met

> **🧹 Optional**: Content cleaning tool available separately to remove promotional text and translator notes

### Processing Modes

| Mode | Description | Best For |
|------|-------------|----------|
| **🎭 Movie Mode** | Processes the largest video file in each folder | Film collections with extras and multiple versions |
| **📺 Series Mode** | Processes all videos with SxxExx pattern detection | TV shows with consistent episode naming |

### ⚡ Synchronization Strategies  

| Strategy | Approach | Performance |
|----------|----------|-------------|
| **🚀 First Match** | Uses first successful sync | Quick processing, good results |
| **🎯 Smart Sync** | Tests all candidates, picks best | Slower but highest quality sync |

### 💡 Built for Real-World Use

>Whether you're managing a personal movie collection,
>processing TV series with hundreds of episodes,
>or handling multilingual content for family viewing,
>Subservient adapts to your workflow while maintaining professional-grade subtitle quality.

<br>

## 📋 Table of Contents
1. [🔧 Installing and Configuring Subservient](#-installing-and-configuring-subservient)
2. [🎯 Using Subservient](#-using-subservient)
3. [⚙️ How Subservient Works: The Four-Phase Automation Process](#️-how-subservient-works-four-phase-automation)
4. [🔍 Troubleshooting Common Issues](#-troubleshooting-common-issues)
5. [❓ Frequently Asked Questions (FAQ)](#-frequently-asked-questions-faq)
6. [📚 Changelog](#-changelog)
7. [🚀 Future Updates & Roadmap](#-future-updates--roadmap)
8. [💝🎉 Support & Donations](#-support--donations)
9. [📄 License](#-license)

<br>

## 🔧 INSTALLING AND CONFIGURING SUBSERVIENT

Subservient offers two installation methods, each with distinct advantages:

### 🖥️ **Native Python Installation** (Recommended for Performance)
> **Best for:** Windows, macOS, and Linux users who want maximum performance
- **✅ Advantages:** Uses 100% of your system resources, faster processing, native OS integration
- **⚠️ Complexity:** Requires Python setup and dependency management

### 🐳 **Docker Container Installation** 
> **Best for:** Unraid, Linux servers, and users who prefer containerized applications
- **✅ Advantages:** Easy setup, isolated environment, consistent across platforms
- **⚠️ Performance:** May be slower, especially with limited RAM/CPU allocation

---

### 📺 **Video Installation Guide (Native Python)**
The video below provides a comprehensive walkthrough for the native Python installation, covering Python setup, required dependencies, setting up an OpenSubtitles consumer, and external tools like ffmpeg and mkvtoolnix.

> **📝 Note:** Although this video was created for an older Subservient version, the installation procedure remains exactly the same.

  <a href="https://www.youtube.com/watch?v=33lcr6dCtRw">
    <img src="https://i.ibb.co/6JBG73qP/Screenshot-2025-07-28-112319.png" alt="Subservient Installation Video Guide" width="480"/>
  </a>

---

**Choose your installation method:**

<details>
<summary><strong>🐍 Install Subservient with Python (Native Installation)</strong></summary>

<br>

> **Best for:** Users who want direct Python access, development, or full customization control

After downloading the Subservient folder from the GitHub repository, ensure that **all required files** are present in the same folder.

### 📁 Required Files

| File | Purpose |
|------|---------|
| `subordinate.py` | Main menu and setup |
| `extraction.py` | Extract internal subtitles |
| `acquisition.py` | Download from OpenSubtitles |
| `synchronisation.py` | AI sync and cleanup |
| `utils.py` | Shared utilities |
| `.config` | Configuration file |
| `requirements.txt` | Python dependencies |

> ⚠️ **Keep all files together in the `Subservient` folder. Don't move or edit anything until setup is complete.**

<br>

<details>
<summary><strong>🐍 Step 1: Install Python</strong></summary>

Subservient requires **Python 3.8+**. If you don't have Python:

1. Download from [python.org](https://www.python.org/downloads/)
2. Install (Windows: **recommended** to install directly to `C:\Python[version]\` for easier path management)
3. During installation, **check "Add Python to PATH"**
4. Test with: open a terminal and test by typing `python --version`. This should show the current version.

> 💡 **Windows Installation Tip**: Installing to a simple path like `C:\Python[version]\` (you can shorten the folder name) makes troubleshooting much easier than the default AppData location.

> 🚨 If `python --version` doesn't work, Python wasn't added to PATH correctly during install.
> 
> **Manual PATH Fix (Windows):**
> Add these two folders to your system PATH (adjust path if you chose a different location):
> - **If installed to C-drive:** `C:\Python[version]\` and `C:\Python[version]\Scripts\`
> - **If default location:** `C:\Users\[YourUsername]\AppData\Local\Programs\Python\Python[version]\` and `C:\Users\[YourUsername]\AppData\Local\Programs\Python\Python[version]\Scripts\`

</details>

<details>
<summary><strong>🏗️ Step 2: Initial Setup</strong></summary>

> **Position the `Subservient` folder where you want to keep it permanently, then:**

**🚀 START:** Run `subordinate.py` (double-click or `python subordinate.py`)

During initial setup:

| Step | Description | Status |
|------|-------------|--------|
| 📦 | Check for essential Python packages | Auto-install if missing |
| ⚓ | Create anchor point and pathfiles | Saves to system config |
| ✅ | Verify installation | Shows confirmation |

> ⚠️ **Windows Users:** Microsoft Visual C++ Build Tools are **required** for Python package installation. If you don't have them installed, Subservient will notice this, direct you to install them first and then exit. See [Step 4](#step-4-install--verify-requirements) for installation instructions.

<br>
<details>
<summary><strong>🔧 Technical Setup Details</strong> ( click to expand)</summary>

- If you miss essential Python packages, it will attempt to install them using 'pip install'.
  Once you have the packages installed, it will either continue or quit depending on your system. 
  If it quits, restart `subordinate.py` and it should continue to the initial setup. 
- When it proceeds to the initial setup, it will create a Subservient_pathfiles textfile, where it     
  will store all pathfiles. These paths will then be used throughout all Subservient scripts.
  This textfile is in your local appdata folder. The directory of this folder depends on your OS.
- When finished, you will see a confirmation that everything is set up correctly.

</details>
<br>

> 📝 **NOTE:** If you ever decide to move the Subservient folder after installation, Subservient will automatically detect when essential files are missing or moved and will provide clear instructions. The old pathfile will be automatically cleaned up and you can simply follow the on-screen instructions to complete the re-setup. The `subordinate.py` file itself can be moved freely without issues.

<br>
<details>
<summary><strong>📍 Where are the locations stored?</strong> ( click to expand)</summary>

Subservient stores the anchor and file locations in a user-specific config file:

| Operating System | Path |
|------------------|------|
| 🪟 **Windows** | `%APPDATA%/Subservient/Subservient_pathfiles` |
| 🍎 **macOS/Linux** | `~/.config/Subservient/Subservient_pathfiles` |

- As long as this file exists and is reachable, Subservient will function normally.
- If the folder is deleted or becomes inaccessible, you will need to redo the setup by running `subordinate.py` again, inside of the Subservient folder. `subordinate.py` should be informing you if it has any issues with Subservient_pathfiles, in theory.. 

</details>

<br>

✅ **After completing the initial setup, you are now able to access the `subordinate.py` main menu.**

</details>

<details>
<summary><strong>🎮 Step 3: Access the Main Menu</strong></summary>

- Press Enter (if you haven't already) to proceed from the initial setup to the main menu.
- The menu options are:

| Option | Description | Icon |
|--------|-------------|------|
| **1** | Start Subservient | 🚀 Begin the subtitle automation process |
| **2** | Scan subtitle coverage | 📊 Analyze existing subtitle files in current directory |
| **3** | Show quick instructions | 📋 View a concise guide to using Subservient |
| **4** | Install & verify requirements | 🔧 Install and verify all Python packages |
| **5** | Extra tools | 🛠️ Access Subtitle Cleaner and additional subtitle utilities |
| **6** | Recreate .config file | ⚙️ Generate a new configuration file if needed |
| **7** | Open README file | 📖 Open this documentation |
| **8** | Exit | 🚪 Close the program |

<br>
<details>
<summary><strong>📊 About Subtitle Coverage Scanning (Option 2)</strong></summary>

Works together with your preferred language setting in your `.config` file.
E.g. if you have `NL` and `EN` specified as languages that you need, then it will check per video file if those languages are present.

It will scan your library and provide you with the following markers per video file when finished:
- ✅ Complete coverage (all languages present)
- ⚠️ Partial coverage (some languages missing)
- ❌ No coverage (no subtitles found)

Use before processing to see what's available, or after to verify results.

</details>

<br>
<details>
<summary><strong>🛠️ About Extra Tools (Option 5)</strong></summary>

Access additional subtitle utilities and cleaning tools that complement the main Subservient workflow:

#### **🧹 Subtitle Cleaner**
Remove advertisements, promotional content, and unwanted text from .srt files using the built-in Subtitle Cleaner:

- **Smart Detection**: Automatically identifies and removes ads, website credits, translator notes, and promotional text
- **Safe Operation**: All original files are automatically backed up before cleaning
- **Restore Functionality**: Easily undo any changes if needed with the built-in restore option
- **Batch Processing**: Clean multiple subtitle files at once for efficient processing
- **Regex Profiles**: Uses advanced pattern matching to identify unwanted content

**How to use:**
1. Navigate to a folder containing video files and their .srt subtitle files
2. Select "Extra tools" from the main menu (Option 5)
3. Choose "Subtitle Cleaner" (Option 1)
4. Select either "Clean subtitle files" or "Restore subtitle changes"

</details>

</details>

<details>
<summary><strong>📦 Step 4: Install & Verify Requirements</strong></summary>

Select menu option (4) to install Python packages:

| Package | Purpose |
|---------|---------|
| `colorama` | Colored terminal output |
| `requests` | HTTP requests |
| `langdetect` | Language detection |
| `ffsubsync` | AI subtitle synchronization |
| `platformdirs` | Cross-platform directories |
| `pycountry` | Language code conversion |
| `tqdm` | Progress bars |

#### 🛠️ External Tools Required

Subservient requires three external tools to function properly:

**🎬 FFmpeg** 
- **Purpose:** Audio/video processing and subtitle extraction
- **Download:** [ffmpeg.org](https://ffmpeg.org/download.html)
- **Installation:** Extract and add the `bin` folder to your system PATH
- **Test:** Open Command Prompt and run: `ffmpeg -version`
- **Expected:** Should show FFmpeg version and configuration info

**📁 MKVToolNix**
- **Purpose:** Extract subtitles from MKV video files  
- **Download:** [mkvtoolnix.download](https://mkvtoolnix.download/downloads.html) (Look for your OS at the top and go for the non-portable version to be safe)
- **Installation:** Install normally - **remember the installation folder location**
- **Test:** Open Command Prompt and run: `mkvmerge --version`
- **Expected:** Should show MKVToolNix version info

- **PATH issue:** If `mkvmerge --version` fails on Windows:
  - Find your MKVToolNix installation folder (usually `C:\Program Files\MKVToolNix` or `C:\Program Files (x86)\MKVToolNix`)
  - Add this folder to your system PATH environment variable
  - **Windows:** Search "Environment Variables" → Edit System Environment Variables → Environment Variables → Select "Path" under System Variables → Edit → New → Add your MKVToolNix folder path → OK
  - **Alternative:** Reinstall MKVToolNix and choose "Add to PATH" if the option appears during installation

**🔧 Microsoft Visual C++ Build Tools** (Windows only) - Linux and macOS can run this natively
- **Purpose:** Required for compiling Python packages with native code
- **Download:** [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (click on 'Download Build Tools')
- During installation, you will only need to select `C++ Build Tools` and then start installing

If you encountered package installation failures during [Step 2](#step-2-initial-setup), retry the setup after installing Build Tools.
If it still gives errors, then add `cl.exe` to PATH (see below)

- **CL issue:** If `cl` command fails:
  - Find `cl.exe`, which is usually located in `C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\[version]\bin\Hostx64\x64\`
  - Add this path to your system PATH environment variable
- **Test:** Open Command Prompt and run: `cl`
- **Expected:** Should show Microsoft compiler version info

> 🚨 **If packages are not working**
> 
> If any package is not working or not installed, that most likely means something went wrong during the pip install phase. Check the install_log inside the logs folder for more information. Also make sure that Subservient has the required privileges to install and run scripts. You can also try installing the requirements again to see if that works. AI assistants like ChatGPT are also excellent at solving Python package issues.

You can always try running Subservient anyway to see if it works, but it's about as likely as a cactus winning a wet T-shirt contest in Alaska. Please check the GitHub page for known issues or create a new issue when applicable. 

**💝 Support Note:**
Limited support is available via GitHub issues. For faster, more personalized Discord support, consider [supporting via Buy Me a Coffee](https://buymeacoffee.com/nexigen).

</details>

<br>

</details>


<details>
<summary><strong>🐳 Install Subservient with Docker (Containerized)</strong></summary>

<br> 

> **Best for:**<br>Users who want easy deployment, Unraid compatibility, or isolated environments.<br>
Docker provides a completely self-contained Subservient environment with all dependencies pre-installed.<br>Perfect for NAS systems like Unraid, or users who prefer containerized applications.

### 📋 Prerequisites

1. **Docker Desktop** (Windows/macOS) or **Docker Engine** (Linux)
   - Download from [docker.com](https://www.docker.com/products/docker-desktop/)
   - Ensure Docker is running before proceeding

2. **Git** (optional - for cloning repository)
   - Or download ZIP from GitHub and extract

### 🚀 Quick Start

1. **Get Subservient:**
   ```bash
   git clone https://github.com/N3xigen/Subservient.git
   cd Subservient/docker
   ```

2. **Prepare your content:**

<br>

Place your video files in the `movies` folder and configure OpenSubtitles credentials in the main `.config` file.
   ```
   docker/
   ├── movies/          # ← Place your video files here
   ├── logs/            # ← Subservient logs (auto-generated)
   └── data/            # ← Subtitle backups (auto-generated)
   ```

3. **Start Subservient:**
   ```bash
   docker-compose up -d
   ```

4. **Access Subservient:**
   ```bash
   docker exec -it subservient bash
   python subordinate.py
   ```

### � Folder Structure
All your data is automatically preserved between container restarts:

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `docker/movies/` | `/app/movies` | Your video files |
| `Subservient/.config` | `/app/.config` | Configuration file (shared with native version) |
| `docker/logs/` | `/app/logs` | Subservient processing logs |
| `docker/data/` | `/app/data` | Subtitle backups & data |

### 🎮 Usage Examples

#### **Interactive Mode (Recommended)**
```bash
# Start container
docker-compose up -d

# Enter interactive session
docker exec -it subservient bash

# Run Subservient (inside container)
python subordinate.py
```

#### **One-time Processing**
```bash
# Start container and run directly
docker-compose up -d
docker exec subservient python subordinate.py
```

#### **Unraid Template**
For Unraid users, use these container settings:
- **Repository:** `ghcr.io/n3xigen/subservient:latest`
- **Network Type:** `bridge`
- **Console Shell Command:** `bash`
- **Host Paths:**
  - `/mnt/user/Movies/` → `/app/movies`
  - `/mnt/user/appdata/subservient/logs/` → `/app/logs`
  - `/mnt/user/appdata/subservient/data/` → `/app/data`
  - `/mnt/user/appdata/subservient/.config` → `/app/.config`

> 💡 **Alternative (Local Build):** If you prefer to build locally or the image isn't available yet:
> ```bash
> git clone https://github.com/N3xigen/Subservient.git
> cd Subservient/docker
> docker-compose build
> ```
> Then use `subservient:latest` as repository name instead.

### ⚙️ Docker Commands

| Action | Command |
|--------|---------|
| **Start container** | `docker-compose up -d` |
| **Stop container** | `docker-compose down` |
| **View logs** | `docker-compose logs -f` |
| **Rebuild** | `docker-compose up --build -d` |
| **Enter container** | `docker exec -it subservient bash` |

### 🚀 Performance Optimization

Docker containers have resource limits that can slow down intensive operations like subtitle synchronization. For better performance:

#### **Docker Desktop Users:**
1. Open **Docker Desktop** → **Settings** → **Resources**
2. **Recommended settings:**
   - **CPUs**: 4-6 cores (or 75% of your available cores)
   - **Memory**: 6-8GB (or 50% of your total RAM)
   - **Swap**: 2GB

#### **Docker Compose Users:**
Add resource limits to your `docker-compose.yml`:
```yaml
services:
  subservient:
    deploy:
      resources:
        limits:
          cpus: '4.0'    # Adjust based on your system
          memory: 6G     # Adjust based on your RAM
```

#### **Performance Tips:**
- **ffsubsync** (audio sync) is CPU-intensive - more cores = faster sync
- **Large video files** benefit from more RAM allocation
- **SSD storage** improves file I/O performance significantly
- **Close other applications** during processing for maximum resources

> 💡 **Note:** Subtitle synchronization can be 2-3x slower in Docker compared to native Python due to virtualization overhead.

<br> 

</details>

---

## ⚙️ Configuration

> **🔧 Unified Configuration System**
> 
> Both installation methods use the same `.config` file for all settings. Configure your OpenSubtitles credentials, processing preferences, and subtitle languages in one place that works for both native Python and Docker versions.<br>
>
>  **💡 Take time to review the configuration settings below.** While Subservient works with sensible defaults out of the box, understanding these settings determines how powerfully you can utilize and customize Subservient to match your specific needs.

<details>
<summary><strong>📝 All Configuration settings explained (.config file)</strong></summary>

### 📋 Configuration Overview

- **🌐 OpenSubtitles Setup**: Create account and configure API credentials (required)
- **🔑 API Settings**: OpenSubtitles credentials configuration
- **🎯 Processing**: Series/Movie mode, Smart Sync, languages  
- **⚙️ Quality**: Sync thresholds, performance tuning
- **📁 File Management**: Video handling, subtitle preservation

---

### 🌐 OpenSubtitles Setup

1. Create account at [opensubtitles.com](https://www.opensubtitles.com/)
2. Go to **API Consumers** and create a new consumer
3. Copy your API key, username, and password to `.config`

| Account Type | Daily Limit | Cost |
|--------------|-------------|------|
| 🆓 **Free (Dev Mode)** | ~100 downloads | Free |
| 👑 **VIP** | 1000 downloads | $10-15/year |

> 💡 **VIP Recommendation**
> 
> **VIP membership** is a paid upgrade that increases your daily download limit to 1000.<br>This is recommended if you plan to use Subservient substantially. You can purchase VIP membership here: [https://www.opensubtitles.com/en/vip](https://www.opensubtitles.com/en/vip).

<br>

---

### 🔑 Required Settings (OpenSubtitles API)

| Setting | Description | Default | Required |
|---------|-------------|---------|----------|
| **api_key** | OpenSubtitles consumer API key from API Consumers section | `your_api_key_here` | ✅ |
| **username** | Your OpenSubtitles account username | `your_username` | ✅ |
| **password** | Your OpenSubtitles account password | `your_password` | ✅ |
| **api_url** | OpenSubtitles API endpoint (only change if API URL changes) | `https://api.opensubtitles.com/api/v1` | - |

<br>

### 🎯 Processing & Synchronization Settings

| Setting | Description | Default | Options |
|---------|-------------|---------|---------|
| **series_mode** | Processing mode selection | `false` | `true` = TV Series (all videos), `false` = Movies (largest per folder) |
| **smart_sync** | Subtitle selection strategy | `true` | `true` = Test all candidates, pick best; `false` = Use first successful sync |
| **languages** | Subtitle languages to download and sync | `en` | Comma-separated codes (e.g. `en,nl,fr,de`) |
| **audio_track_languages** | Audio track languages to keep in video files | `en,ja` | Language codes or `ALL` to keep all tracks |

> **📺 series_mode**: When `true`, processes ALL videos with SxxExx pattern detection. When `false`, only processes the largest video file per folder (movie mode).
> 
> **🎯 smart_sync**: When `true`, tests all subtitle candidates and picks the best quality sync. When `false`, uses first acceptable match (faster but potentially lower quality).
> 
> **🌐 languages**: Controls which subtitle languages are downloaded from OpenSubtitles. Does not affect preservation of existing subtitles.
> 
> **🔊 audio_track_languages**: Removes audio tracks not in this list to reduce file size. Set to `ALL` to keep all audio tracks unchanged.

**Series Mode Details:**
- `false`: **Movie Mode** - Processes only the largest video file per folder
- `true`: **TV Series Mode** - Processes ALL videos with SxxExx pattern detection and integrity checking

**Smart Sync Details:**
- `false`: **First Match** - Uses first subtitle that syncs acceptably (faster)  
- `true`: **Smart Sync** - Tests ALL candidates, compares results, picks best quality (slower but higher quality)

<br>

### ⚙️ Quality & Performance Settings

| Setting | Description | Default | Notes |
|---------|-------------|---------|-------|
| **accept_offset_threshold** | Auto-accept sync threshold (seconds) | `0.05` | Lower = stricter quality, higher = more auto-accepts |
| **reject_offset_threshold** | Auto-reject sync threshold (seconds) | `2.5` | Higher = more lenient, lower = stricter rejections |
| **max_search_results** | Maximum subtitle search results per video | `10` | Free: ≤12, VIP: 20+ |
| **top_downloads** | Subtitles to test per batch | `3` | Free: 2-4, VIP: 5-10 |
| **download_retry_503** | Retry attempts for server errors | `6` | Recommended: 6 for busy periods |
| **pause_seconds** | Pause between processing phases | `5` | Prevents API rate limiting |

> **✅ accept_offset_threshold**: Subtitles with sync quality below this threshold are automatically accepted without manual verification. Lower values ensure higher quality but require more manual checks.
> 
> **❌ reject_offset_threshold**: Subtitles with sync quality above this threshold are automatically rejected. Higher values give more subtitle candidates a chance but may require more manual verification.
> 
> **🔍 max_search_results**: More results increase chances of finding good subtitles but use more API quota. Free users should stay ≤12, VIP users can go higher.
> 
> **⬇️ top_downloads**: Number of subtitles tested simultaneously. Lower preserves download quota, higher speeds up processing if you have sufficient quota.
> 
> **🔄 download_retry_503**: OpenSubtitles servers can be busy. More retries increase success rate but slow processing during peak times.
> 
> **⏸️ pause_seconds**: Prevents API rate limiting and gives you time to read processing information between phases.

<br>

### 📁 File Management Settings

| Setting | Description | Default | Warning |
|---------|-------------|---------|---------|
| **delete_extra_videos** | Handle extra videos in folders | `false` | ⚠️ `true` = **PERMANENT DELETION** |
| **extras_folder_name** | Folder name for moved extras | `extras` | Used when `delete_extra_videos=false` |
| **preserve_forced_subtitles** | Keep FORCED subtitle tracks | `false` | For foreign dialogue scenes |
| **preserve_unwanted_subtitles** | Keep all subtitle languages | `false` | Override language filtering |
| **skip_dirs** | Folder names to ignore | `extras,trailers,samples...` | Comma-separated list |
| **unwanted_terms** | Terms to filter from searches | `720p,BluRay,x264...` | Technical metadata removal |

> **🗑️ delete_extra_videos**: When `false` (safe), moves extra videos to specified folder. When `true` (dangerous), permanently deletes all but the largest video file per folder. Ignored in series mode.
> 
> **📁 extras_folder_name**: Name of the folder where extra videos are moved when `delete_extra_videos=false`.
> 
> **🔤 preserve_forced_subtitles**: Preserves FORCED subtitle tracks (typically used for foreign dialogue in otherwise native-language movies) when `true`.
> 
> **🌐 preserve_unwanted_subtitles**: When `true`, keeps ALL subtitle tracks regardless of language settings. When `false`, removes tracks not in the languages list.
> 
> **🚫 skip_dirs**: Ignores these folder names during video discovery (case-insensitive matching).
> 
> **🏷️ unwanted_terms**: Removes technical terms from filenames before searching OpenSubtitles for cleaner, more accurate search queries.

> ⚠️ **Warning:** `delete_extra_videos=true` **PERMANENTLY DELETES** all video files except the largest in each folder.

<br>

</details>

## ⚙️ Mode Details & Advanced Configuration

> **🔧 Processing Mode Explanations & Advanced Settings**
> 
> Detailed explanations of how TV Series Mode and Smart Sync work, plus advanced configuration patterns like subtitle preservation logic. These help you understand and optimize your `.config` settings.

<details>
<summary><strong>⚙️ Mode Details & Advanced Configuration</strong></summary>

<br>

<details>
<summary><strong>📺 TV Series Mode</strong> - Complete episode processing with SxxExx detection</summary>

### 🚀 What Series Mode Does

**Series Mode** (`series_mode=true`) transforms Subservient to handle TV shows with advanced episode detection and processing:

#### 🔍 **SxxExx Pattern Detection**
- **Automatic Recognition**: Detects `S01E01`, `S02E15`, `S10E23` patterns in filenames
- **Integrity Checking**: Validates consistent naming across episodes
- **Auto-Normalization**: Converts `S1E01` → `S01E01` for consistency
- **Flexible Matching**: Works with various naming conventions

#### 📁 **Processing Behavior**
| Mode | File Selection | Use Case |
|------|----------------|----------|
| **Movie Mode** (`false`) | Largest file per folder | Movies, single videos |
| **Series Mode** (`true`) | ALL video files | TV shows, episode collections |

#### 🛡️ **Built-in Safeguards**
- **Movie Detection**: Warns when movie files detected in series mode
- **Pattern Validation**: Ensures episodes follow consistent SxxExx format  
- **Missing Episode Detection**: Identifies gaps in season/episode numbering
- **Duplicate Prevention**: Handles multiple versions of same episode

#### 🎯 **Example Usage**
```
/TV Shows/Breaking Bad Season 1/
├── Breaking.Bad.S01E01.720p.mkv    ← Processed ✅
├── Breaking.Bad.S01E02.720p.mkv    ← Processed ✅  
├── Breaking.Bad.S01E03.720p.mkv    ← Processed ✅
└── extras/                         ← Ignored ✅
```

</details>

<details>
<summary><strong>🎯 Smart Sync Mode</strong> - Advanced subtitle selection for optimal quality</summary>

### 🚀 How Smart Sync Works

**Smart Sync** (`smart_sync=true`) revolutionizes subtitle selection by testing ALL candidates before choosing the best result:

#### 🔄 **Sync Strategies**

| Mode | Strategy | Speed | Quality | Best For |
|------|----------|-------|---------|----------|
| **First Match** (`false`) | Use first acceptable sync | ⚡ Fast | 🟡 Good | Quick processing, decent results |
| **Smart Sync** (`true`) | Test all, pick best | 🐌 Slower | 🟢 Excellent | Maximum quality, worth the wait |

#### 🎯 **Smart Sync Process**
1. **Batch Download**: Gets all available subtitle candidates
2. **Parallel Sync**: Tests synchronization for each candidate  
3. **Quality Comparison**: Measures offset precision for all results
4. **Best Selection**: Automatically picks the highest-quality sync
5. **Results Display**: Shows comparison of all tested candidates

#### 📊 **Quality Comparison Example**
```
[Synchronisation] [Smart Sync] Smart Sync Results:
• subtitle1.srt: ✓ 0.025s ← BEST
• subtitle2.srt: ✓ 0.087s  
• subtitle3.srt: ✗ 3.2s (rejected)
• subtitle4.srt: ✗ Failed
```

#### ⚙️ **Performance Impact**
- **Processing Time**: ~2-5x longer per video
- **API Usage**: Tests more subtitle downloads  
- **Quality Gain**: Significantly better sync accuracy
- **Recommendation**: Enable for movies/important content

</details>

<details>
<summary>🎯 <strong>Subtitle Preservation Logic</strong> - Advanced track management settings</summary>

**🎮 Smart Preservation System**: Control exactly what subtitle content gets preserved during processing:

| Setting Combination | FORCED Subtitles | Regular Subtitles | Use Case |
|---------------------|------------------|-------------------|----------|
| **preserve_forced_subtitles=true**<br>**preserve_unwanted_subtitles=true** | ✅ ALL languages | ✅ ALL languages | **Maximum preservation** - Keep everything |
| **preserve_forced_subtitles=true**<br>**preserve_unwanted_subtitles=false** | ✅ Wanted languages only | ❌ Unwanted languages removed | **FORCED-priority** - Keep FORCED for wanted langs |
| **preserve_forced_subtitles=false**<br>**preserve_unwanted_subtitles=true** | ❌ Treated as regular | ✅ ALL languages | **Language-priority** - Keep all but no FORCED special treatment |
| **preserve_forced_subtitles=false**<br>**preserve_unwanted_subtitles=false** | ❌ Treated as regular | ❌ Unwanted languages removed | **Minimal** - Only wanted languages |

**🔧 What are FORCED subtitles?**
- **Separate subtitle tracks** that ONLY translate foreign dialogue segments
- **NOT full movie subtitles** - they complement the main spoken language
- Example: Japanese dialogue in an English movie gets FORCED subtitles, while English dialogue remains unsubditled
- Often essential for understanding key plot points when foreign languages are spoken
- **Important**: FORCED subtitles are completely independent from regular full-movie subtitles

**💡 Recommended Settings:**
- **Keep everything**: `preserve_forced_subtitles=true, preserve_unwanted_subtitles=true`
- **Perserve languages in language setting only, including forced subtitles**: `preserve_forced_subtitles=true, preserve_unwanted_subtitles=false`
- **Perserve subtitles for all encountered languages, but remove forced subtitles**: `preserve_forced_subtitles=false, preserve_unwanted_subtitles=true`
- **Only preferred languages, nothing else**: `preserve_forced_subtitles=false, preserve_unwanted_subtitles=false`

</details>

<details>
<summary><strong> 🌐 Language Codes </strong> - All supported languages and how to use them </summary>

Use ISO 639-1 codes in `.config` (e.g., `en`, `nl`, `fr`):

| Language | Code | Language | Code | Language | Code |
|----------|------|----------|------|----------|------|
| 🇺🇸 English | `en` | 🇳🇱 Dutch | `nl` | 🇫🇷 French | `fr` |
| 🇩🇪 German | `de` | 🇪🇸 Spanish | `es` | 🇮🇹 Italian | `it` |
| 🇵🇹 Portuguese | `pt` | 🇷🇺 Russian | `ru` | 🇯🇵 Japanese | `ja` |
| 🇨🇳 Chinese | `zh` | 🇰🇷 Korean | `ko` | 🇸🇦 Arabic | `ar` |

> 🌍 **Need more?** See [ISO 639-1 Wikipedia](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) for complete list.

</details>

</details>

<br>

## 🎯 USING SUBSERVIENT

Choose your preferred method for using Subservient:


<details>
<summary><strong>🐍 Using Subservient with the native python installation</strong></summary>

### 🎮 How to use subordinate.py

Move `subordinate.py` to where you want to process videos, then run it:

| Scenario | Action | Result |
|----------|--------|--------|
| **Single Movie** | Move into folder with movie | Processes one movie |
| **Batch Movies** | Move next to movie folders | Processes all folders |
| **TV Series** | Move into series folder + `series_mode=true` | All episodes in that series |
| **Batch TV Series** | Move next to series folders + `series_mode=true` | All episodes in all series folders |

Please note that, in movie mode, you cannot have multiple movie files in the same folder.
Doing so will cause Subservient to look for the largest movie file, process that one, and either move or delete all the other movies in there.
Only in TV Series mode can you have multiple movie files in the same folder.<br>

**📺 Series Processing Options:**
- **Single Series**: Place `subordinate.py` inside a series folder (e.g., `/Breaking Bad/`) to process all episodes in that series
- **Batch Series**: Place `subordinate.py` next to multiple series folders (e.g., `/TV Shows/`) to process all episodes in all series automatically

**🎬 Movie Processing Options:**  
- **Single Movie**: Place `subordinate.py` in the folder containing the movie file
- **Batch Movies**: Place `subordinate.py` next to multiple movie folders - each folder must contain only one movie file

> ⚠️ **Movement Rules:** Use cut+paste (Ctrl+X+V), NOT copy+paste. Multiple copies will confuse Subservient.

### 🎯 Running the Process

1. Run `subordinate.py` → Choose option 1 → Read pre-flight checklist → Confirm
2. Subservient processes automatically based on `.config` settings
3. Manual input only needed for edge cases (bad configs, series detection, etc.)

</details>

<details>
<summary><strong>🐳 Using Subservient with a docker container</strong></summary>

### 🎮 Using Docker Container

#### Using Docker Compose (Recommended)

Navigate to the `docker` folder and start the container:

```bash
cd docker
docker-compose up
```

The container will start with an interactive terminal showing the Subservient main menu.

#### Using Docker Run Command

```bash
docker run -it --rm \
  -v /path/to/your/movies:/movies \
  -v /path/to/config:/config \
  -v /path/to/persistent/logs:/app/logs \
  -v /path/to/persistent/data:/app/data \
  -v /path/to/persistent/home:/root \
  subservient:latest
```

### 🎯 Container Usage

1. **Interactive Mode**: Container starts directly in Subservient's main menu
2. **Volume Access**: All your movie files are accessible via `/movies` mount
3. **Persistent Data**: Configuration, logs, and download backups persist between container runs
4. **File Operations**: Process movies directly from mounted volumes

#### File Placement Strategy

Since you can't move the script file in a container environment:

| Scenario | Docker Approach |
|----------|-----------------|
| **Single Movie** | Place movie in dedicated folder under `/movies` |
| **Batch Movies** | Organize movies in separate folders under `/movies` |
| **TV Series** | Use series folder structure under `/movies` + `series_mode=true` |
| **Batch TV Series** | Organize multiple series folders under `/movies` + `series_mode=true` |

### 📁 Volume Organization

Structure your mounted directories for optimal workflow:

```
/your/movies/
├── Movie1_Folder/
│   └── movie1.mkv
├── Movie2_Folder/
│   └── movie2.mp4
├── Breaking_Bad/
│   ├── Breaking.Bad.S01E01.mkv
│   ├── Breaking.Bad.S01E02.mkv
│   └── Breaking.Bad.S01E03.mkv
└── Better_Call_Saul/
    ├── Better.Call.Saul.S01E01.mkv
    └── Better.Call.Saul.S01E02.mkv

/your/config/
└── .config

/your/logs/
└── (Subservient logs)

/your/data/
└── (Subtitle backups)
```

</details>

<br>

### 💬 When is a 'human touch' required?

Four main situations require your input:
<br>

<details>
<summary>1. 🔤 <strong>No Valid 'languages' Entry in .config </strong> (`extraction.py`)</summary>

<br>

**Trigger:** If the extraction script does not find a valid 'languages' entry in your `.config` file

**Prompt Options:**
- Type `c` to continue with English only (default)
- Type any other key to exit and fix your config

**Purpose:** Ensures you are aware that only English subtitles will be processed unless you update your configuration (because apparently configuring languages is optional until it's not).

</details>


<details>
<summary>2. 🔍 <strong>No Subtitles Found for a Video </strong>(`acquisition.py`)</summary>

**Trigger:** If Subservient cannot find any search results when searching on OpenSubtitles

**Prompt Options:**
- **Option 1:** 🔵 Type in a manual search term to try a different subtitle search
- **Option 2:** 🔴 Delete the video file permanently
- **Option 3:** 🟡 Increase global subtitle download limit (will allow more subtitle candidates to be downloaded when available)
- **Option 4:** 🟡 Skip this video for now (can be processed again in future runs)
- **Option 5:** 🟣 Skip this language and do not show again (adds language to permanent skip list in config)

**Purpose:** Gives you complete control over what happens to videos for which no subtitles could be found, with both temporary and permanent solutions. Because sometimes we need to admit defeat gracefully ;) 

</details>

<details>
<summary>3. 🧹 <strong>Prompt for Cleaning Internal Subtitles </strong>(`synchronisation.py`)</summary>

<br>


**Trigger:** If not all required external subtitles in your preferred languages are present for a video

**Prompt:** "Not all external subtitles present for [video]. Do you want to clean internal subtitles anyway?"

**Options:**
- `1` = Clean internal subtitles anyway (removes all internal subtitles for compatibility)
- `2` = Do NOT clean internal subtitles (leaves internal subtitles untouched)

**Purpose:** Ensures you have control over internal subtitle removal, especially when some external subtitles are missing.

</details>

<details>
<summary>4. 🎯 <strong>Manual Offset Verification and Correction </strong>(`synchronisation.py`)</summary>

<br>


**Trigger:** If any subtitles had timing offset corrections applied during synchronisation

**Process:**
- **Initial Verification:** For each corrected subtitle, verify if timing matches audio well enough
- **Video Opening Options:** Automatically open video or show path for manual opening
- **Correction Submenu:** Apply additional timing adjustments, restore original offsets, or mark as drifted
- **Automatic Handling:** If marked as DRIFT, `acquisition.py` restarts automatically to download new candidates

**Purpose:** Ensures perfect synchronisation quality through manual verification when needed.

</details>

<br>


> 🛡️ **Safety Philosophy**
> 
> Interactive prompts protect your files and provide fallbacks when automation fails, while maintaining maximum automation.

<br>

## ⚙️ HOW SUBSERVIENT WORKS: FOUR-PHASE AUTOMATION

Subservient runs through four automated phases:

| Phase | Script | Purpose |
|-------|--------|---------|
| 🎮 **1** | `subordinate.py` | Setup and preparation |
| 📤 **2** | `extraction.py` | Extract internal subtitles |
| 🌐 **3** | `acquisition.py` | Download from OpenSubtitles |
| 🎯 **4** | `synchronisation.py` | AI sync and cleanup |

Each phase calls the next automatically. User input only for edge cases.

<details>
<summary><strong>🎮 PHASE 1: SETUP & ANCHORING (`subordinate.py`)</strong></summary>

<br>

**Role of subordinate.py:**
`subordinate.py` serves as the **central reference point** for all other scripts in the native Python version. <br>
You place `subordinate.py` directly in the folder containing your video files, <br>
and all other scripts use its location to discover and process videos in that directory and subdirectories. <br>

**Key Functions:**
- **🎯 Process Launcher**: Initiates the complete 4-phase automation (Option 1) with pre-flight checklist verification
- **🏠 Central Hub**: Provides main menu access to all tools, configuration, and documentation
- **📍 Anchor Point**: Other scripts locate videos relative to subordinate.py's position
- **🔧 Tool Collection**: Subtitle coverage scans, subtitle cleaning (ads/credits removal), configuration management

**Technical Operations:**
- **Package Management**: Installs core dependencies (colorama, langdetect, requests, tqdm, platformdirs) if missing
- **Pathfile Creation**: Writes anchor directory path to persistent pathfile for cross-session access
- **Configuration Management**: Creates and validates configuration files with video/audio processing settings
- **Initial Setup**: Ensures directory structure and required files exist before processing begins
- **Menu Interface**: Provides interactive navigation between all four phases

**Files Modified**: `pathfile.txt`, `config` files, dependency installations  
**Manual Input**: [Manual Input 1] - Configuration validation and directory selection

</details>

<details>
<summary><strong>📤 PHASE 2: EXTRACTION (`extraction.py`)</strong></summary>

<br>

**Role of extraction.py:**
The **subtitle discovery engine** that intelligently harvests internal subtitles already embedded within your video files. <br> Since internal subtitles are perfectly synchronized and don't count against OpenSubtitles download quotas, <br> extraction prioritizes using existing content before searching online.

**Key Functions:**
- **🔍 Container Scanning**: Systematically analyzes video files for embedded subtitle streams
- **🌍 Smart Language Detection**: Uses AI to identify subtitle languages with high accuracy
- **🎯 FORCED Subtitle Preservation**: Protects essential foreign dialogue subtitles from removal
- **🧹 Intelligent Track Management**: Handles multiple subtitle/audio tracks based on user preferences

**Technical Operations:**
- **Container Analysis**: Uses `ffprobe` to scan video files for embedded subtitle streams
- **Language Detection**: Analyzes subtitle content using langdetect library for automatic language identification
- **Subtitle Extraction**: Executes `mkvmerge` operations to extract internal subtitles to `.srt` files
- **Track Management**: Preserves forced subtitle flags and handles multiple language tracks per video
- **Format Conversion**: Converts various subtitle formats (VobSub, ASS, etc.) to standardized SRT format

**Files Created**: `{video_basename}.{lang}.srt` files extracted from video containers  
**Manual Input**: [Manual Input 2] - Language confirmation and forced subtitle handling

</details>

<details>
<summary><strong>🌐 PHASE 3: ACQUISITION (`acquisition.py`)</strong></summary>

<br>

**Role of acquisition.py:**
The **subtitle hunting specialist** that searches the OpenSubtitles database when internal subtitles are missing or incomplete. <br> Uses sophisticated search strategies and automatic retry logic to find the best available subtitles for your videos.

**Key Functions:**
- **🔍 Multi-Strategy Search**: Employs hash-based, filename-based, and manual query approaches
- **🌐 OpenSubtitles Integration**: Handles JWT authentication and API communication seamlessly
- **📥 Smart Download Logic**: Selects top-rated subtitles with automatic 503 error retry handling
- **🤔 Interactive Fallbacks**: Provides manual search options when automatic matching fails

**Technical Operations:**
- **API Integration**: Authenticates with OpenSubtitles API using JWT tokens for subtitle database access
- **Search Strategy**: Implements multiple search algorithms (hash-based, filename-based, manual query)
- **Download Logic**: Downloads top-rated subtitles with automatic retry for 503 server responses
- **File Management**: Saves subtitles with numbered naming convention (`{video}.{lang}.number{N}.srt`)
- **Fallback Handling**: Provides manual search interface when automatic matching fails

**Files Created**: `{video_basename}.{lang}.number{N}.srt` files from OpenSubtitles database  
**Manual Input**: [Manual Input 3] - Search term specification and subtitle selection

</details>

<details>
<summary><strong>🎯 PHASE 4: SYNCHRONIZATION (`synchronisation.py`)</strong></summary>

<br>

**Role of synchronisation.py:**
The **precision timing expert** that uses AI-powered ffsubsync technology to achieve perfect subtitle synchronization. <br> Employs intelligent quality control and provides manual verification tools for edge cases requiring human judgment.

**Key Functions:**
- **🤖 AI Synchronization**: Leverages ffsubsync's audio analysis for automatic timing alignment
- **📊 Quality Assessment**: Uses configurable thresholds to classify sync quality automatically
- **🎛️ Manual Verification**: Provides interactive tools for fine-tuning problematic subtitles
- **🧹 Final Cleanup**: Removes temporary files and organizes results for optimal user experience

**Technical Operations:**
- **AI Synchronization**: Executes `ffsubsync` to align subtitle timestamps with video audio tracks
- **Offset Calculation**: Compares original vs synchronized timestamps to measure correction accuracy
- **Quality Thresholds**: Applies configurable accept/reject thresholds (default: 0.05s/0.3s) for automatic processing
- **Manual Verification**: Creates offset tracking file for subtitles requiring human review
- **File Cleanup**: Removes `.DRIFT`, `.FAILED`, and redundant numbered subtitle files

**Files Created**: Final synchronized `.srt` files, `movies_with_linear_offset.txt` tracking file  
**Manual Input**: [Manual Input 4] - Offset verification and timing correction interface

</details>

<br>

## 🔍 TROUBLESHOOTING COMMON ISSUES

Here are some common issues and solutions to help you get Subservient up and running:

<details>
<summary>0. <strong>File Rename Errors During Extraction</strong></summary>

**💥 Symptom:** Error about "Cannot rename subtitle file - target already exists" during extraction.

**✅ Solution:** 
- This happens when Subservient was interrupted previously and left incomplete files
- **Remove incomplete subtitle files**: Look for files like `*.und0.srt`, `*.temp.srt`, or duplicate `.forced.srt` files
- **Clean restart**: Delete any partial/temporary subtitle files and run Subservient again
- Subservient will show you exactly which files are causing conflicts

</details>

### 🐍 Python Issues

<details>
<summary>1. <strong>Python Not Found / Incorrect Version</strong></summary>

**💥 Symptom:** Running `python --version` shows an error or an older version (<3.8).

**✅ Solution:** 
- Reinstall Python from the [official Python website](https://www.python.org/downloads/)
- ⚠️ Ensure you check "Add Python to PATH" during installation
- Verify with `python --version` again

</details>

### 📁 File Structure Issues

<details>
<summary>2. <strong>Missing Files or Incorrect Folder Structure</strong></summary>

**💥 Symptom:** Errors about missing files or modules when running Subservient.

**✅ Solution:** 
- Ensure all required files are in the same folder as `subordinate.py`
- Required files: `extraction.py`, `acquisition.py`, `synchronisation.py`, `.config`, `requirements.txt`, `README.md`
- Do not move or delete any files until `subordinate.py` shows the main menu

</details>

<details>
<summary>3. <strong>Permission Errors</strong></summary>

**💥 Symptom:** Errors about not being able to access or modify files/folders.

**✅ Solution:** 
- Ensure you have read, write, and execute permissions
- On Windows: Run as administrator if needed
- Check folder permissions for video files location

</details>

### 📦 Dependency Issues

<details>
<summary>4. <strong>Package Installation Issues</strong></summary>

**💥 Symptom:** Errors when Subservient tries to install Python packages

**✅ Solution:** 
- Install packages manually: `pip install <package>` (e.g., `pip install requests`)

</details>

<details>
<summary>5. <strong>FFmpeg Not Found or Not Working</strong></summary>

**💥 Symptom:** Errors about `ffmpeg` command not found or FFmpeg-related failures.

**✅ Solution:** 
- FFmpeg is required for audio/video processing
- See [Step 4: Install & Verify Requirements](#-step-4-install--verify-requirements) for detailed installation instructions

</details>

<details>
<summary>6. <strong>MKVToolNix Not Found</strong></summary>

**💥 Symptom:** Errors about `mkvmerge` command not found or MKV extraction failures.

**✅ Solution:** 
- MKVToolNix is required for extracting subtitles from MKV files
- See [Step 4: Install & Verify Requirements](#-step-4-install--verify-requirements) for detailed installation instructions
- **If still not found after installation:** MKVToolNix may not have been added to PATH automatically
  - Find your installation folder (usually `C:\Program Files\MKVToolNix`)
  - Add this folder to your system PATH environment variable
  - **Windows PATH Guide:** Search "Environment Variables" → Edit System Environment Variables → Environment Variables → Select "Path" under System Variables → Edit → New → Add your MKVToolNix folder path → OK
  - Restart Command Prompt and test with `mkvmerge --version`

</details>

<details>
<summary>7. <strong>Microsoft Visual C++ Runtime Error</strong></summary>

**💥 Symptom:** Error messages about missing Microsoft Visual C++ Redistributable or version 14.0 or higher required.

**✅ Solution:** 
- Microsoft Visual C++ Build Tools are required for compiling Python packages
- See [Step 4: Install & Verify Requirements](#-step-4-install--verify-requirements) for detailed installation instructions

</details>

### 🌐 API Issues

<details>
<summary>8. <strong>OpenSubtitles API Errors</strong></summary>

**💥 Symptom:** Errors related to API key, username, or password.

**✅ Solution:** 
- ✔️ Double-check credentials in `.config` file
- ✔️ Verify API consumer exists on OpenSubtitles website
- ✔️ Check account status (not banned/suspended)
- ✔️ Verify API status on OpenSubtitles website
- ✔️ **New**: Check for 503 errors in logs - these are temporary server overload issues that Subservient handles automatically

</details>

<details>
<summary>8b. <strong>503 Service Unavailable Errors</strong></summary>

**💥 Symptom:** Repeated 503 errors when downloading subtitles, even with valid credentials.

**✅ Solution:** 
- **This is normal!** 503 errors indicate OpenSubtitles servers are temporarily overloaded
- **Subservient handles this automatically** with intelligent retry logic
- **If persistent**: Increase `download_retry_503` setting in `.config` (default: 6)
- **Check logs**: Subservient shows retry attempts and automatically backs off when needed

</details>

<details>
<summary>9. <strong>Network Issues</strong></summary>

**💥 Symptom:** Unable to connect to internet or OpenSubtitles API.

**✅ Solution:** 
- Check internet connection
- Configure proxy/VPN settings if needed
- Ensure firewall allows Python/Subservient internet access

</details>

### 🚀 Runtime Issues

<details>
<summary>10. <strong>File Not Found / Incorrect File Paths</strong></summary>

**💥 Symptom:** Errors about files not being found during processing.

**✅ Solution:** 
- Place `subordinate.py` in correct folder with video files
- Avoid network drives or removable media
- Run `subordinate.py` once after moving to re-anchor

**🔧 If Issues Persist:**
1. **Re-anchor Setup:** Simply run `subordinate.py` and it will automatically detect and resolve file location issues  
2. **Manual Reset:** If problems continue, manually delete the `Subservient_pathfiles` directory (typically in your user config folder) and rerun `subordinate.py` in the Subservient folder
3. **Fresh Start:** Backup the .config and re-download Subservient from GitHub and replace your .config file. Then meticulously follow the installation setup at the top of this README.

</details>

<details>
<summary>11. <strong>Subservient Crashes or Disappears Suddenly</strong></summary>

**💥 Symptom:** Program closes unexpectedly without showing error messages, or freezes during execution.

**✅ Solution:** 
1. **Run from Terminal/Command Prompt** to see error messages:
   - **Windows:** Open `cmd.exe`, drag `subordinate.py` into the window, press Enter
   - **Linux/macOS:** Open terminal, drag `subordinate.py` into the window, press Enter
   - This prevents Subservient from closing automatically and shows error details

2. **Basic Troubleshooting:**
   - Ensure sufficient free memory (at least 2GB RAM available)
   - Close unnecessary programs
   - Check if antivirus software is interfering

3. **Get Help:**
   - If you can't solve the error: create an issue on [GitHub Issues](https://github.com/N3xigen/Subservient/issues) with the error message
   - BMAC supporters can contact me directly on Discord for faster support

</details>

### 🎯 User Error Issues

<details>
<summary>12. <strong>"Package Requirements Error" when running Subservient for the first time</strong></summary>

**💥 Symptom:** Missing packages error when running `extraction.py`, `acquisition.py`, or `synchronisation.py` directly.

**✅ Solution:** 
- ✅ **This is normal behavior!** Always start with `subordinate.py`
- Individual scripts are designed to be run through `subordinate.py`
- `subordinate.py` handles package installation and setup

</details>

<details>
<summary>13. <strong>Initial Setup Not Complete Errors</strong></summary>

**💥 Symptom:** Scripts report incomplete setup, even after running `subordinate.py`.

**✅ Solution:** 
- Run `subordinate.py` from main Subservient folder (not movie folder), so that initial setup triggers
- Setup creates anchor points that all scripts need and should prevent the incomplete setup message from coming up again

</details>

<br>

> 🆘 **Need More Help?**
> 
> If you encounter issues not covered here:
> - 📚 Check the [Subservient GitHub repository](https://github.com/N3xigen/Subservient)
> - 🐛 Open a new issue with detailed information
> - 💬 Direct support available through Discord for supporters

<br>

## ❓ FREQUENTLY ASKED QUESTIONS (FAQ)

### 🔧 Installation & Setup

<details>
<summary>1. <strong>Do I need to install Python and dependencies every time?</strong></summary>

**Answer:** No, you only need to install Python and the required dependencies (packages and ffmpeg) once. Subservient will remember these settings and use them for future runs on the device used for installing.

</details>

<details>
<summary>2. <strong>Can I use Subservient on macOS/Linux?</strong></summary>

**Answer:** Yes, Subservient is cross-platform and works on Windows, macOS, and Linux. The installation and setup process is similar on all platforms

**⚠️ Disclaimer:** Subservient is built and tested on Windows. While programmed with cross-platform compatibility in mind, there could be lingering issues. Please consult the GitHub repository for known issues and please report an issue yourself if you encounter a problem.

</details>

### 🔐 Credentials & API

<details>
<summary>3. <strong>Why do I need OpenSubtitles credentials?</strong></summary>

**Answer:** Subservient uses your OpenSubtitles credentials to access the OpenSubtitles API, required for searching and downloading subtitles. Your credentials are stored locally and are securely handled by OpenSubtitles.

</details>

<details>
<summary>4. <strong>What if I don't have an OpenSubtitles account?</strong></summary>

**Answer:** You can create a free OpenSubtitles account on their website. Free accounts have limitations (download limits), but are sufficient for testing and light usage. For heavier usage, consider upgrading to VIP.

</details>

### ⚙️ Configuration & Usage

<details>
<summary>5. <strong>Can I customize subtitle languages and settings?</strong></summary>

**Answer:** Yes, you can customize subtitle languages, file handling options, and other settings in the `.config` file. Subservient also provides interactive prompts to guide you through configuration.

</details>

<details>
<summary>6. <strong>How does Subservient handle TV series?</strong></summary>

**Answer:** Subservient can automatically detect and process TV series with multiple episodes, as long as they follow consistent naming (e.g., S01E01, S01E02). Set `series_mode=true` in your config for series processing.

</details>

### 🛠️ Troubleshooting

<details>
<summary>7. <strong>What if Subservient fails to find subtitles?</strong></summary>

**Answer:** Subservient handles errors and missing subtitles gracefully. It will log issues and prompt for input when necessary. Subservient prompts you to manually search for subtitles or adjust settings in the `.config` file (it's surprisingly polite about failure).

</details>

<details>
<summary>8. <strong>Is there a download limit for subtitles?</strong></summary>

**Answer:** Subservient has no hard limit, but OpenSubtitles accounts do:
- 🆓 Free (Dev Mode): ~100 downloads/day
- 👑 VIP: 1000 downloads/day  
- 🆓 Free (Non-Dev): 5-10 downloads/day

</details>

### 📜 Legal & Support

<details>
<summary>9. <strong>Can I download subtitles for copyrighted content?</strong></summary>

**Answer:** Subservient can download subtitles for all content available on OpenSubtitles, which is generally a huge number of videos. However, you should only use it for content you own or have rights to use subtitles for. Please refer to the legal disclaimer near the bottom of the Readme file.

</details>

<details>
<summary>10. <strong>Where can I get help and support?</strong></summary>

**Answer:** 
- 📚 Check the [Subservient GitHub repository](https://github.com/N3xigen/Subservient) for documentation and issues
- 🐛 Open new issues for specific problems
- 💝 Direct support via Discord for supporters ([Buy Me a Coffee](https://buymeacoffee.com/nexigen))

**Note:** Support is provided when possible, but time is limited. Direct Discord support is available for those who support the project financially.

</details>


## 📚 CHANGELOG

### 🚀 Recent Major Updates

| Date | Version | Feature | Description |
|------|---------|---------|-------------|
| 🚀 **2025-11-30** | v0.88 | Smart Sync & Series Enhancement | Smart Sync mode for optimal subtitle selection and enhanced TV-Series functionality |
| 🌐 **2025-11-23** | v0.87 | Early TV-Series Support | TV-Series mode with basic SxxExx detection and episode processing |
| 🐳 **2025-08-04** | v0.85 | Docker Support | Full Docker containerization with docker-compose support and Unraid compatibility! |
| 🧹 **2025-08-03** | v0.83 | Subtitle Cleaner | Full subtitle cleaning tool with ad removal, backup/restore, and batch processing! |
| 💬 **2025-08-01** | v0.81 | 7 bugs fixed! | More in-depth (forced)subtitle preservation, language code mismatch fix and more! |
| 🔥 **2025-07-28** | v0.80 | ALPHA release | Video synchronisation is fully operational, repo is public! |
| 🐛 **2025-07-20** | v0.79 | Single/batch video syncs now work! | Public alpha release |
| 🔧 **2025-07-05** | v0.78 | Manual Verification | Added manual offset verification menu and editor |

> 🎉 **Current Version: v0.88** - New features: Smart Sync mode for better subtitle quality and enhanced TV-Series support!

<br>

## 🚀 Future Updates & Roadmap

Subservient is actively developed with exciting new features planned! Here's what's coming next:

### 📅 Updates that I should be doing

| Priority | Feature | Target | Description |
|----------|---------|--------|-------------|
| 🤝 **Planned** | 📺 TV-Series Support | v0.9 BETA | Complete automation for TV shows with episode detection |
| 📋 **High** | 📚 Containerization for easy use | v0.95 | Packaging everything in a container/executable to make it easy to install |
| 🔥 **High** | 🛠️ 'Tools' option in Subservient menu & complete LINUX bugfixing  | v1.00 RELEASE | manual syncing, batch-renaming, muxing/de-muxing, manual subtitle offset tools, you name it! |
| ⚡ **Medium** | 📊 Smarter subtitle search queries | v1.06 | More fallbacks for more comprehensive searches |
| ⚡ **Medium** | 🔄 Asynchronous synchronisation (whaat?) | v1.08 | Synchronizing multiple videos simultaneously

### 💬 Community Suggestions Welcome!

**Have an idea for Subservient?** Feel free to post your ideas in the Subservient GitHub repo! 

| How to Suggest | Method | Response Time |
|----------------|--------|---------------|
| 🐛 **Bug Reports** | [GitHub Issues](https://github.com/N3xigen/Subservient/issues) | In my spare time (varies a lot) |
| 💡 **Feature Requests** | [GitHub Discussions](https://github.com/N3xigen/Subservient/discussions) | In my spare time (varies a lot) |
| ☕ **VIP Suggestions** | Discord (for supporters) | Same day, possibly within minutes after your message |

> 🎉 **Get Involved!**
> 
> Subservient thrives on community feedback. Whether you're a casual user or a power user, your suggestions help shape the future of the project. Don't hesitate to share your ideas, no matter how big or small!

<br>

## 💝🎉 Support & Donations

> 🎯 **Subservient Will Always Be Free**
> 
> Subservient is and will always remain completely free for personal use. This project was created out of passion for automation and the belief that useful tools should be accessible to everyone. No features are locked behind paywalls, no subscriptions are required, and you'll never be pressured to pay for anything.

> ❤️ **But Your Support Is Warmly Welcome**
> 
> While financial support is never required or expected, it is incredibly meaningful when offered. This project is developed and maintained entirely in my free time, and every contribution (whether code, feedback, or financial), helps me dedicate more time to improving Subservient and assisting users.

### 🎯 Ways to Support (All Optional!)

| Method | Description | Impact |
|--------|-------------|--------|
| ⭐ **GitHub Star** | Star the repository | Helps others discover Subservient |
| 🐛 **Bug Reports** | Report issues you encounter | Makes Subservient better for everyone |
| 💡 **Feature Requests** | Suggest improvements | Shapes future development |
| 🗣️ **Word of Mouth** | Tell others about Subservient | Grows our community |
| ☕ **Buy Me a Coffee** | [BMAC donation page](https://buymeacoffee.com/nexigen) | Helps me dedicate more time to improving Subservient, while keeping it free for everyone ❤️ |

### ☕ About My Buy Me a Coffee Page

Beyond being a platform for optional financial support, my [Buy Me a Coffee page](https://buymeacoffee.com/nexigen) serves as the central hub for project updates and development insights. Here's what you'll find:

- **📢 Regular Updates**: Detailed posts about Subservient development progress, new features, and behind-the-scenes insights
- **🚀 Project Announcements**: First looks at new projects I'm working on, from early concepts to beta releases
- **💬 Community Interaction**: Direct communication with supporters and the broader community
- **🎯 Development Roadmap**: Insights into what's coming next and how community feedback shapes development priorities

Whether you choose to support financially or just follow along, it's a great way to stay connected with the ongoing development of Subservient and discover other automation tools I'm building!

> 🙏 **A Heartfelt Thank You**
> 
> Whether you use Subservient daily or just tried it once, whether you've contributed code or simply starred the repo, whether you've supported financially or spread the word, thank you! Every interaction, no matter how small, means the world to me and keeps this project alive 💝
<br> -- <strong>Nexigen</strong>

<br>

## 📄 License

This project is licensed under the **GPL-3.0 License**. 

### 🆓 Open Source License
This software is free and open source, licensed under the GNU General Public License v3.0. You are free to:

- ✅ **Use** the software for any purpose
- ✅ **Study** how the software works and modify it
- ✅ **Distribute** copies of the software
- ✅ **Distribute** modified versions of the software

### 📋 GPL-3.0 Requirements
If you distribute this software or create derivative works, you must:

- 📝 **Provide source code** when distributing binaries
- 🏷️ **Include copyright notices** and license information  
- 📋 **License derivatives** under GPL-3.0 as well
- 📢 **Document changes** made to the original code

### 📖 Full License Text
For the complete license terms, see the [LICENSE](LICENSE) file in this repository or visit: [https://www.gnu.org/licenses/gpl-3.0.html](https://www.gnu.org/licenses/gpl-3.0.html)

> 💡 **In Simple Terms**: This is free software that will always remain free. You can use, modify, and share it, but if you distribute modified versions, they must also be open source under GPL-3.0.

<br>

## ⚖️ Legal Disclaimer

**Subservient is designed for use with content you legally own or have rights to process.** This software provides technical functionality for subtitle management and synchronization, similar to media players, converters, and other multimedia tools.

The inclusion of various technical format filters and metadata cleaning capabilities serves **interoperability purposes only** and enables the software to work with diverse file naming conventions found in multimedia content, regardless of source.

**Users are responsible for ensuring their use of this software complies with applicable copyright laws and terms of service of subtitle providers.** The developers do not endorse or encourage any illegal activity.
<br><br>
## 🙏 Acknowledgments

- Thanks to all the contributors and open-source projects that made this software possible
- Special thanks to the OpenSubtitles team for providing an excellent API and subtitle database
- Special thanks to [KBlixt/subcleaner](https://github.com/KBlixt/subcleaner) for the powerful subtitle cleaning engine integrated into Subservient
- Very special thanks to all of my current and future supporters! You are simply the best and the biggest reason why I will release most of my projects free and largely open-source.

<br><br><br><br>
---
<div align="center">
**🎬 Made with ❤️ for the subtitle automation community**

[![Version](https://img.shields.io/badge/version-v0.88-brightgreen.svg)](https://github.com/N3xigen/Subservient)
[![GitHub](https://img.shields.io/badge/GitHub-Subservient-blue?logo=github)](https://github.com/N3xigen/Subservient)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg)](https://docker.com)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)

[![Plex](https://img.shields.io/badge/Plex-compatible-orange.svg?logo=plex&logoColor=white)](https://plex.tv)
[![Jellyfin](https://img.shields.io/badge/Jellyfin-compatible-purple.svg?logo=jellyfin&logoColor=white)](https://jellyfin.org)
[![Emby](https://img.shields.io/badge/Emby-compatible-green.svg?logo=emby&logoColor=white)](https://emby.media)
[![Unraid](https://img.shields.io/badge/Unraid-compatible-red.svg?logo=unraid&logoColor=white)](https://unraid.net)

*Happy subtitle processing! 🎯*

</div>

---





