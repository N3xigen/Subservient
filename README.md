# 🎬 Subservient Subtitle Automation Suite

![Version](https://img.shields.io/badge/version-v0.79-brightgreen.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)
![FFmpeg](https://img.shields.io/badge/requires-FFmpeg-red.svg)
![Dependencies](https://img.shields.io/badge/dependencies-8%20packages-green.svg)

```
  _________    ___.                             .__               __   
 /   _____/__ _\_ |__   ______ ______________  _|__| ____   _____/  |_ 
 \_____  \|  |  \ __ \ /  ___// __ \_  __ \  \/ /  |/ __ \ /    \   __\
 /        \  |  / \_\ \\___ \\  ___/|  | \/\   /|  \  ___/|   |  \  |  
/_______  /____/|___  /____  >\___  >__|    \_/ |__|\___  >___|  /__|  
        \/          \/     \/     \/                    \/     \/      
```
<br>

> 🚀 **Automated subtitle extraction, download, and synchronisation suite for your video collection**
> 
> Transform your video library with perfectly synchronized subtitles in multiple languages. Achieves optimal results through a complex interplay of automated processing and strategic manual control when needed.

### 🎯 What Subservient Does For You

**🔥 One-Click Processing**: Drop `subordinate.py` into any folder with videos and watch Subservient automatically:
- 📤 **Extract** internal subtitles from video files that are ready to be used
- 🌐 **Download** missing subtitle languages from OpenSubtitles  
- 🤖 **AI-Sync** all subtitles using advanced audio analysis
- 🧹 **Clean up** your video files by removing unwanted subtitle tracks

**✅ Simple & Straightforward**:
- No confusing menus or overwhelming configuration options
- Works out-of-the-box with sensible defaults
- Just drop the script, run it, and let it do its job
- Uses interactive and articulate prompts when Subservient has a question for you during runtime
- Perfect for users who want results, not complexity

**⚡ Smart & Efficient**: 
- Uses existing internal subs first (saves download quota)
- Handles both single movies and entire video collections
- Works with 50+ languages using simple language codes (`en`, `nl`, `fr`, etc.)
- Processes TV series automatically with episode detection (Scheduled for v0.9)

**🛡️ Safe & Reliable**:
- Never overwrites originals - creates new synchronized `.srt` files
- Interactive prompts when manual input is needed
- Automatic quality control with three-tier sync verification
- Comprehensive error handling and recovery options

**�🎮 Perfect For**: Movie collectors, TV series enthusiasts, multilingual households, content creators, or anyone tired of out-of-sync subtitles ruining their viewing experience!

<br>

## 📋 Table of Contents
1. [🔧 Installing and Configuring Subservient](#-installing-and-configuring-subservient)
2. [🎯 Using Subservient](#-using-subservient)
3. [⚙️ How Subservient Works: The Four-Phase Automation Process](#️-how-subservient-works-the-four-phase-automation-process)
4. [🔍 Troubleshooting Common Issues](#-troubleshooting-common-issues)
5. [❓ Frequently Asked Questions (FAQ)](#-frequently-asked-questions-faq)
6. [📚 Changelog](#-changelog)
7. [� Future Updates & Roadmap](#-future-updates--roadmap)
8. [💝🎉 Support & Donations](#-support--donations)
9. [📄 License](#-license)

<br>

## 🔧 INSTALLING AND CONFIGURING SUBSERVIENT

After downloading the Subservient folder from the Github repository, ensure that **all required files** are present in the same folder. 

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

### 🐍 Step 1: Install Python

Subservient requires **Python 3.8+**. If you don't have Python:

1. Download from [python.org](https://www.python.org/downloads/)
2. Install (Windows: check "Add Python to PATH")
3. Test with: `python --version`

> 🚨 If `python --version` doesn't work, Python wasn't added to PATH correctly.

<br>

### 🏗️ Step 2: Initial Setup

> **Position the `Subservient` folder where you want to keep it permanently, then:**

**🚀 START:** Run `subordinate.py` (double-click or `python subordinate.py`)

During initial setup:

| Step | Description | Status |
|------|-------------|--------|
| 📦 | Check for essential Python packages | Auto-install if missing |
| ⚓ | Create anchor point and pathfiles | Saves to system config |
| ✅ | Verify installation | Shows confirmation |

<br>
<details>
<summary><strong>🔧 Technical Setup Details</strong> (✚ click to expand)</summary>

- If you miss essential Python packages, it will attempt to install them using 'pip install'.
  Once you have the packages installed, it will either continue or quit depending on your system. 
  If it quits, restart `subordinate.py` and it should continue to the initial setup. 
- When it proceeds to the initial setup, it will create a Subservient_pathfiles textfile, where it     
  will store all pathfiles. These paths will then be used throughout all Subservient scripts.
  This textfile is in your local appdata folder. The directory of this folder depends on your OS.
- When finished, you will see a confirmation that everything is set up correctly.

</details>
<br>

> 📝 **NOTE:** If you ever decide to move the Subservient folder after installation, then move `subordinate.py` back into the Subservient folder and run it again in order to redo the initial setup. This will update Subservient_pathfiles. If you don't do this, then you will encounter (possibly unrelated) errors during runtime.

<br>
<details>
<summary><strong>📍 Where are the locations stored?</strong> (✚ click to expand)</summary>

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

<br>

### 🎮 Step 3: Access the Main Menu
---
- Press Enter (if you haven't already) to proceed from the initial setup to the main menu.
- The menu options are:

| Option | Description | Icon |
|--------|-------------|------|
| **1** | Start Subservient | 🚀 Begin the subtitle automation process |
| **2** | Scan subtitle coverage | 📊 Analyze existing subtitle files in current directory |
| **3** | Show quick instructions | 📋 View a concise guide to using Subservient |
| **4** | Install & verify requirements | 🔧 Install and verify all Python packages |
| **5** | Recreate .config file | ⚙️ Generate a new configuration file if needed |
| **6** | Open README file | 📖 Open this documentation |
| **7** | Exit | 🚪 Close the program |

<br>
<details>
<summary><strong>📊 About Subtitle Coverage Scanning (Option 2)</strong></summary>

Shows detailed analysis of existing subtitles in your directory:
- ✅ Complete coverage (all languages present)
- ⚠️ Partial coverage (some languages missing)
- ❌ No coverage (no subtitles found)

Use before processing to see what's available, or after to verify results.

</details>
<br>

### 📦 Step 4: Install & Verify Requirements

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

**🎬 FFmpeg is Required:** Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

> 🚨 **If packages are not working**
> 
> If any package is not working or not installed, then that most likely means something went wrong during the Pip install phase. Check the install_log inside of the logs folder for more information. Also make sure that Subservient has the required privilege to install and run scripts. You can also try installing the requirements again to see if that works. ChatGPT is also excellent at solving Python package issues.

You can always try running Subservient anyway to see if it works, but it's about as likely as a cactus winning a wet T-shirt contest in Alaska. Please check my GitHub page for known issues or post an issue when applicable. 

**💝 Support Note:**
Limited support available via GitHub issues. For faster Discord support, consider [supporting via Buy Me a Coffee](https://buymeacoffee.com/nexigen).

### ⚙️ Step 5: Configuration

Edit the `.config` file to set your OpenSubtitles credentials and preferences.

#### 🌐 OpenSubtitles Setup

1. Create account at [opensubtitles.com](https://www.opensubtitles.com/)
2. Go to **API Consumers** and create a new consumer
3. Copy your API key, username, and password to `.config`

| Account Type | Daily Limit | Cost |
|--------------|-------------|------|
| 🆓 **Free (Dev Mode)** | ~100 downloads | Free |
| 👑 **VIP** | 1000 downloads | $10-15/year |

> 💡 **VIP Recommendation**
> 
> **VIP membership** is a paid upgrade that increases your daily download limit to 1000. This is highly recommended if you plan to use Subservient substantially. You can purchase VIP membership here: [https://www.opensubtitles.com/en/vip](https://www.opensubtitles.com/en/vip).

#### 🔧 Essential Configuration Settings

Open `.config` and configure the required settings:

| Setting | Description | Example | Required |
|---------|-------------|---------|----------|
| **username** | OpenSubtitles username | `myuser` | ✅ |
| **password** | OpenSubtitles password | `mypass` | ✅ |
| **api_key** | OpenSubtitles API key | `abc123` | ✅ |
| **languages** | Languages to download | `en,nl,fr` | ✅ |
| **series_mode** | TV series vs movies | `false` | - |

<details>
<summary>🔧 <strong>All Configuration Options</strong></summary>

| Setting | Description | Default |
|---------|-------------|---------|
| **max_search_results** | Max search results per video | `12` |
| **top_downloads** | Subtitles to test per batch | `3` |
| **accept_offset_threshold** | Auto-accept sync threshold | `0.05` |
| **reject_offset_threshold** | Auto-reject (DRIFT) threshold | `1.2` |
| **audio_track_languages** | Audio tracks to keep | `en,nl,ja` |
| **skip_dirs** | Folders to ignore | `extras,trailers` |
| **unwanted_terms** | Filter from search | `720p,BluRay` |
| **delete_extra_videos** | Delete extra videos | `false` |
| **pause_seconds** | Pause between phases | `3` |

> ⚠️ **Warning:** `delete_extra_videos=true` **PERMANENTLY DELETES** all video files except the largest in each folder.

<br>
<details>
<summary>🔧 <strong>Advanced Setting Details</strong> - Click here for detailed explanation of every .config setting ✚</summary>

**🎯 Sync Quality:**
- **accept_offset_threshold** (0.05s): Lower = stricter, more manual checks
- **reject_offset_threshold** (1.2s): Higher = more tolerance for poor syncs

**🔍 Search & Performance:**
- **max_search_results**: More options but slower (Free: 6, VIP: 12+)
- **top_downloads**: Lower preserves download quota (Free: 1-2, VIP: 3-5)

**📁 Content Management:**
- **skip_dirs**: Folders to ignore (`extras,trailers,samples`)
- **unwanted_terms**: Remove from search (`720p,BluRay,x264`)

</details>

</details>

#### 🎬 Mode Settings:

| Mode | Behavior | Use For |
|------|----------|---------|
| **series_mode = false** | Only largest file per folder | Movies |
| **series_mode = true** | All S##E## files | TV Shows |
| **delete_extra_videos = false** | Move extras to folder | ✅ Safe |
| **delete_extra_videos = true** | **PERMANENTLY DELETE** | ⚠️ Risky |

## 🌍 Language Codes

Use ISO 639-1 codes in `.config` (e.g., `en`, `nl`, `fr`):

| Language | Code | Language | Code | Language | Code |
|----------|------|----------|------|----------|------|
| 🇺🇸 English | en | 🇳🇱 Dutch | nl | 🇫🇷 French | fr |
| 🇩🇪 German | de | 🇪🇸 Spanish | es | 🇮🇹 Italian | it |
| 🇵🇹 Portuguese | pt | 🇷🇺 Russian | ru | 🇯🇵 Japanese | ja |
| 🇨🇳 Chinese | zh | 🇰🇷 Korean | ko | 🇸🇦 Arabic | ar |

> 🔍 **Need more?** See [ISO 639-1 Wikipedia](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) for complete list.

<br>

## 🎯 USING SUBSERVIENT

### 🎮 How to use subordinate.py

Move `subordinate.py` to where you want to process videos, then run it:

| Scenario | Action | Result |
|----------|--------|--------|
| **Single Movie** | Move into folder with movie | Processes one movie |
| **Batch Movies** | Move next to movie folders | Processes all folders |
| **TV Series** | Move into series folder + `series_mode=true` | All episodes |

> ⚠️ **Movement Rules:** Use cut+paste (Ctrl+X+V), NOT copy+paste. Multiple copies will confuse Subservient.

### � Running the Process

1. Run `subordinate.py` → Choose option 1 → Read checklist → Confirm
2. Subservient processes automatically based on `.config` settings
3. Manual input only needed for edge cases (bad configs, series detection, etc.)

### 💬 When You'll Be Prompted

Four main situations require your input:
<br>

<details>
<summary>1. 🔤 <strong>No Valid 'languages' Entry in .config </strong> (`extraction.py`)</summary>

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
- **Option 3:** 🟡 Increase global subtitle download limit (affects all languages/movies)
- **Option 4:** 🟡 Skip this video for now (can be processed again in future runs)
- **Option 5:** 🟣 Skip this language and do not show again (adds language to permanent skip list in config)

**Additional Features:**
- Manual search allows you to test different query terms until you find working subtitles
- Download limit increase updates .config file and restarts acquisition process
- Language-specific skipping lets you avoid certain languages for specific videos
- All choices include confirmation prompts to prevent accidental actions

**Purpose:** Gives you complete control over what happens to videos for which no subtitles could be found, with both temporary and permanent solutions. Because sometimes we need to admit defeat gracefully ;) 

</details>

<details>
<summary>3. 🧹 <strong>Prompt for Cleaning Internal Subtitles </strong>(`synchronisation.py`)</summary>

**Trigger:** If not all required external subtitles in your preferred languages are present for a video

**Prompt:** "Not all external subtitles present for [video]. Do you want to clean internal subtitles anyway?"

**Options:**
- `1` = Clean internal subtitles anyway (removes all internal subtitles for compatibility)
- `2` = Do NOT clean internal subtitles (leaves internal subtitles untouched)

**Purpose:** Ensures you have control over internal subtitle removal, especially when some external subtitles are missing.

</details>

<details>
<summary>4. 🎯 <strong>Manual Offset Verification and Correction </strong>(`synchronisation.py`)</summary>

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

### 🎮 Phase 1: Setup (`subordinate.py`)
Initialize environment, verify dependencies, present main menu.

### 📤 Phase 2: Extraction (`extraction.py`)  
Extract internal subtitles, auto-detect languages, clean unwanted tracks.

**Why extract first?** Internal subtitles are already perfectly synchronized and don't count against your OpenSubtitles download quota. Using what's already available is faster than searching online.

> ✅ **Phase 2 Summary**
> 
> Uses existing internal subtitles before searching online, saves download quota, ensures perfect sync, and cleans video files by removing unwanted tracks.

### 🌐 PHASE 3: SUBTITLE ACQUISITION (`acquisition.py`)

**Goal:** Download best subtitles for missing languages using OpenSubtitles API.

<details>
<summary><strong>🌐 Process Details</strong></summary>

| Step | Action |
|------|--------|
| 🔍 **Analysis** | Scan for missing subtitle languages |
| 🌐 **Search** | Query OpenSubtitles API with smart strategies |
| 📥 **Download** | Get best candidates based on ratings and downloads |
| 🤔 **Fallback** | Interactive handling when subtitles can't be found |

**Search strategies:** 
- **Primary**: Uses video/folder name, strips to core title and year
- **Fallback**: Tries variations without year or with different formatting
- **Manual**: Allows custom search terms for difficult titles
- **Language-specific**: Tailored queries per target language

**Options for missing subtitles:**
1. Manual search with custom terms
2. Delete problematic videos
3. Increase download limits  
4. Skip temporarily or permanently

</details>

> ✅ **Phase 3 Summary**  
> Intelligently searches and downloads subtitles using multiple strategies, with interactive fallbacks when automated searches fail.

### 🎯 PHASE 4: SUBTITLE SYNCHRONISATION (`synchronisation.py`)

**Goal:** AI sync, quality control, language detection, optional cleanup.

<details>
<summary><strong>🎯 Process Details</strong></summary>

| Step | Action |
|------|--------|
| 🤖 **AI Sync** | ffsubsync analyzes audio and aligns timing |
| 📊 **Quality Analysis** | Auto-classify sync quality using offset thresholds |
| 🏷️ **Language Detection** | Auto-detect and rename by actual language |
| 🧹 **Internal Cleanup** | Optional removal of internal subtitle tracks |

**Three-tier quality system:**
- 🟢 **Auto-Accept** (≤0.05s offset): Excellent sync, processed immediately
- 🟡 **Manual Review** (0.05s-1.2s): Requires user verification at end of run
- 🔴 **Auto-Reject** (>1.2s offset): Poor sync, marked as DRIFT for retry

**Status system handles problems:**
- **DRIFT**: Timing gradually worsens throughout video - triggers automatic retry with new subtitles
- **FAILED**: No suitable subtitles found after all attempts - logged for manual review

**Manual verification options:**
- Open video automatically or show path for manual checking
- Fine-tune timing with millisecond precision
- Mark as DRIFT to trigger new download attempts

</details>

> ✅ **Phase 4 Summary**  
> AI synchronization with intelligent quality control, manual verification when needed, and comprehensive final analysis.

<br>

## 🔍 TROUBLESHOOTING COMMON ISSUES

Here are some common issues and solutions to help you get Subservient up and running:

### 🐍 Python Issues

<details>
<summary>1. <strong>🚫 Python Not Found / Incorrect Version</strong></summary>

**💥 Symptom:** Running `python --version` shows an error or an older version (<3.8).

**✅ Solution:** 
- Reinstall Python from the [official Python website](https://www.python.org/downloads/)
- ⚠️ Ensure you check "Add Python to PATH" during installation
- Verify with `python --version` again

</details>

### 📁 File Structure Issues

<details>
<summary>2. <strong>📂 Missing Files or Incorrect Folder Structure</strong></summary>

**💥 Symptom:** Errors about missing files or modules when running Subservient.

**✅ Solution:** 
- Ensure all required files are in the same folder as `subordinate.py`
- Required files: `extraction.py`, `acquisition.py`, `synchronisation.py`, `.config`, `requirements.txt`, `README.md`
- Do not move or delete any files until `subordinate.py` shows the main menu

</details>

<details>
<summary>3. <strong>🔒 Permission Errors</strong></summary>

**💥 Symptom:** Errors about not being able to access or modify files/folders.

**✅ Solution:** 
- Ensure you have read, write, and execute permissions
- On Windows: Run as administrator if needed
- Check folder permissions for video files location

</details>

### 📦 Dependency Issues

<details>
<summary>4. <strong>🔧 Dependency Installation Issues</strong></summary>

**💥 Symptom:** Errors when Subservient tries to install Python packages or ffmpeg.

**✅ Solution:** 
- Install packages manually: `pip install <package>` (e.g., `pip install requests`)
- For ffmpeg: Download from [ffmpeg.org](https://ffmpeg.org/download.html) (the multimedia Swiss Army knife)
- Ensure ffmpeg's `bin` folder is in your system PATH

</details>

### 🌐 API Issues

<details>
<summary>5. <strong>🔑 OpenSubtitles API Errors</strong></summary>

**💥 Symptom:** Errors related to API key, username, or password.

**✅ Solution:** 
- ✔️ Double-check credentials in `.config` file
- ✔️ Verify API consumer exists on OpenSubtitles website
- ✔️ Check account status (not banned/suspended)
- ✔️ Verify API status on OpenSubtitles website

</details>

<details>
<summary>6. <strong>🌐 Network Issues</strong></summary>

**💥 Symptom:** Unable to connect to internet or OpenSubtitles API.

**✅ Solution:** 
- Check internet connection
- Configure proxy/VPN settings if needed
- Ensure firewall allows Python/Subservient internet access

</details>

### 🚀 Runtime Issues

<details>
<summary>7. <strong>📍 File Not Found / Incorrect File Paths</strong></summary>

**💥 Symptom:** Errors about files not being found during processing.

**✅ Solution:** 
- Place `subordinate.py` in correct folder with video files
- Avoid network drives or removable media
- Run `subordinate.py` once after moving to re-anchor

**🔧 If Issues Persist:**
1. **Re-anchor Setup:** Move `subordinate.py` back to the main Subservient folder and run it once to trigger initial setup
2. **Manual Reset:** If problems continue, manually delete the `Subservient_pathfiles` directory and rerun `subordinate.py` in the Subservient folder
3. **Fresh Start:** Backup the .config and re-download Subservient from Github and replace your .config file. Then meticulously follow the installation setup at the top of this Readme.

</details>

<details>
<summary>8. <strong>💻 Subservient Crashes or Freezes</strong></summary>

**💥 Symptom:** Program stops responding or crashes during execution.

**✅ Solution:** 
- Ensure sufficient free memory
- Close unnecessary programs
- Run in terminal/command prompt to see error messages
- Please create an issue in the Github repository so that I can review it when I'm working on Subservient

</details>

### 🎯 User Error Issues

<details>
<summary>9. <strong>📦 "Package Requirements Error" when running Subservient for the first time</strong></summary>

**💥 Symptom:** Missing packages error when running `extraction.py`, `acquisition.py`, or `synchronisation.py` directly.

**✅ Solution:** 
- ✅ **This is normal behavior!** Always start with `subordinate.py`
- Individual scripts are designed to be run through `subordinate.py`
- `subordinate.py` handles package installation and setup

</details>

<details>
<summary>10. <strong>⚙️ Initial Setup Not Complete Errors</strong></summary>

**💥 Symptom:** Scripts report incomplete setup, even after running `subordinate.py`.

**✅ Solution:** 
- Run `subordinate.py` from main Subservient folder (not movie folder), so that initial setup triggers
- Setup creates anchor points that all scripts need and should prevent the incomplete setup message from coming up again

</details>

<br>

> 🆘 **Need More Help?**
> 
> If you encounter issues not covered here:
> - 📚 Check the [Subservient GitHub repository](https://github.com/yourusername/Subservient)
> - 🐛 Open a new issue with detailed information
> - 💬 Direct support available through Discord for supporters

<br>

## ❓ FREQUENTLY ASKED QUESTIONS (FAQ)

### 🔧 Installation & Setup

<details>
<summary>1. <strong>🔄 Do I need to install Python and dependencies every time?</strong></summary>

**Answer:** No, you only need to install Python and the required dependencies (packages and ffmpeg) once. Subservient will remember these settings and use them for future runs on the device used for installing.

</details>

<details>
<summary>2. <strong>🍎 Can I use Subservient on macOS/Linux?</strong></summary>

**Answer:** Yes, Subservient is cross-platform and works on Windows, macOS, and Linux. The installation and setup process is similar on all platforms

**⚠️ Disclaimer:** Subservient is built and tested on Windows. While programmed with cross-platform compatibility in mind, there could be lingering issues. Please consult the GitHub repository for known issues and please report an issue yourself if you encounter a problem.

</details>

### 🔐 Credentials & API

<details>
<summary>3. <strong>🔑 Why do I need OpenSubtitles credentials?</strong></summary>

**Answer:** Subservient uses your OpenSubtitles credentials to access the OpenSubtitles API, required for searching and downloading subtitles. Your credentials are stored locally and are securely handled by OpenSubtitles.

</details>

<details>
<summary>4. <strong>🆓 What if I don't have an OpenSubtitles account?</strong></summary>

**Answer:** You can create a free OpenSubtitles account on their website. Free accounts have limitations (download limits), but are sufficient for testing and light usage. For heavier usage, consider upgrading to VIP.

</details>

### ⚙️ Configuration & Usage

<details>
<summary>5. <strong>🎨 Can I customize subtitle languages and settings?</strong></summary>

**Answer:** Yes, you can customize subtitle languages, file handling options, and other settings in the `.config` file. Subservient also provides interactive prompts to guide you through configuration.

</details>

<details>
<summary>6. <strong>📺 How does Subservient handle TV series?</strong></summary>

**Answer:** Subservient can automatically detect and process TV series with multiple episodes, as long as they follow consistent naming (e.g., S01E01, S01E02). Set `series_mode=true` in your config for series processing.

</details>

### 🛠️ Troubleshooting

<details>
<summary>7. <strong>❌ What if Subservient fails to find subtitles?</strong></summary>

**Answer:** Subservient handles errors and missing subtitles gracefully. It will log issues and prompt for input when necessary. Subservient prompts you to manually search for subtitles or adjust settings in the `.config` file (it's surprisingly polite about failure).

</details>

<details>
<summary>8. <strong>📊 Is there a download limit for subtitles?</strong></summary>

**Answer:** Subservient has no hard limit, but OpenSubtitles accounts do:
- 🆓 Free (Dev Mode): ~100 downloads/day
- 👑 VIP: 1000 downloads/day  
- 🆓 Free (Non-Dev): 5-10 downloads/day

</details>

### 📜 Legal & Support

<details>
<summary>9. <strong>⚖️ Can I download subtitles for copyrighted content?</strong></summary>

**Answer:** Subservient can download subtitles for all content available on OpenSubtitles, which is generally a huge number of videos. However, you should only use it for content you own or have rights to use subtitles for. Please refer to the legal disclaimer near the bottom of the Readme file.

</details>

<details>
<summary>10. <strong>🆘 Where can I get help and support?</strong></summary>

**Answer:** 
- 📚 Check the [Subservient GitHub repository](https://github.com/yourusername/Subservient) for documentation and issues
- 🐛 Open new issues for specific problems
- 💝 Direct support via Discord for supporters ([Buy Me a Coffee](https://buymeacoffee.com/nexigen))

**Note:** Support is provided when possible, but time is limited. Direct Discord support is available for those who support the project financially.

</details>


## 📚 CHANGELOG

### 🚀 Recent Major Updates

| Date | Version | Feature | Description |
|------|---------|---------|-------------|
| 🐛 **2025-07-20** | v0.79 | 🔥 Single/batch video syncs now work! | Launch day coming soon |
| 🔧 **2025-07-05** | v0.78 | 🎛️ Manual Verification | Added manual offset verification menu and editor |
| 🧪 **2025-06-25** | v0.75 | 🔍 Testing Phase | Extensive testing with 200+ personal video collection |

> 🎉 **Current Version: v0.79** - After a whole bunch of testing with several video libraries, we're now at a point where single/batch video processing fully works. The next step will be an instructional video and then we're good to go for an alpha launch.

<br>

## � Future Updates & Roadmap

Subservient is actively developed with exciting new features planned! Here's what's coming next:

### 📅 Updates that I should be doing

| Priority | Feature | Target | Description |
|----------|---------|--------|-------------|
| 🤝 **Planned** | 📺 TV-Series Support | v0.9 BETA | Complete automation for TV shows with episode detection |
| 🔥 **High** | 🛠️ 'Tools' option in Subservient menu & complete LINUX bugfixing  | v1.00 RELEASE | manual syncing, batch-renaming, muxing/de-muxing, manual subtitle offset tools, you name it! |
| ⚡ **Medium** | 📊 Smarter subtitle search queries | v1.06 | More fallbacks for more comprehensive searches |
| ⚡ **Medium** | � Asynchronous synchronisation (huh..what?) | v1.08 | Synchronizing multiple videos simultaneously

### 🎯 Long-term potential ideas that I might be doing (2025-2027)

- **🌐 Web Interface**: Browser-based control panel for remote management
- **📱 Mobile App**: iOS/Android companion for monitoring progress
- **🔌 Plugin System**: Third-party extensions and intricate customizability 

### 💬 Community Suggestions Welcome!

**Have an idea for Subservient?** Feel free to post your ideas in the Subservient Github repo! 

| How to Suggest | Method | Response Time |
|----------------|--------|---------------|
| 🐛 **Bug Reports** | [GitHub Issues](https://github.com/yourusername/Subservient/issues) | In my sparetime (varies a lot) |
| 💡 **Feature Requests** | [GitHub Discussions](https://github.com/yourusername/Subservient/discussions) | In my sparetime (varies a lot) |
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

### 🔧 Support & Response

| Support Level | What You Get | Method | Notes |
|---------------|-------------|--------|-------|
| 🆓 **Community Support** | GitHub issues, community help, feel free to post | GitHub Repo | Available to everyone |
| 💬 **BMAC Follower** | Access to supporter-only updates, posts, and the BMAC community | BMAC | $1+/month supporters |
| ☕ **Coffee Supporter** | Priority responses, shoutout credits | Shoutout in the Credits in my applications | $2+/month supporters |
| 🎯 **VIP Support** | Discord support access | VIP Discord Channel | $4/month+ supporters |
| 🚀 **Early Access** | Pre-release builds, 2-month early access | Early Access Repository | $8/month+ supporters |
| 🔥 **Live Development** | Real-time repo access, video shoutouts | Live Development Repository | $16/month+ supporters |

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

> � **In Simple Terms**: This is free software that will always remain free. You can use, modify, and share it, but if you distribute modified versions, they must also be open source under GPL-3.0.

> 📝 **Note:** Replace `yourusername` with your actual GitHub username when publishing this repository.

<br>

## ⚖️ Legal Disclaimer

**Subservient is designed for use with content you legally own or have rights to process.** This software provides technical functionality for subtitle management and synchronization, similar to media players, converters, and other multimedia tools.

The inclusion of various technical format filters and metadata cleaning capabilities serves **interoperability purposes only** and enables the software to work with diverse file naming conventions found in multimedia content, regardless of source.

**Users are responsible for ensuring their use of this software complies with applicable copyright laws and terms of service of subtitle providers.** The developers do not endorse or encourage any illegal activity.
<br><br>
## 🙏 Acknowledgments

- Thanks to all the contributors and open-source projects that made this software possible
- Special thanks to the OpenSubtitles team for providing an excellent API and subtitle database.
- Very special thanks to all of my current and future supporters! You are simply the best and the biggest reason why I will release most of my projects free and largely open-source.

<br><br><br><br>
---
<div align="center">
**🎬 Made with ❤️ for the subtitle automation community**

[![Version](https://img.shields.io/badge/version-v0.79-brightgreen.svg)](https://github.com/yourusername/Subservient)
[![GitHub](https://img.shields.io/badge/GitHub-Subservient-blue?logo=github)](https://github.com/yourusername/Subservient)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)

> 📝 **Note:** Remember to update GitHub URLs with your actual repository information when publishing.

*Happy subtitle processing! 🎯*

</div>

---

