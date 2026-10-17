"""Intelligent Track Repair: verify, label, prioritize, reorder and remove audio/subtitle tracks in MKV files.

Standalone Extra Tools utility. User-confirmed observations and preferences always win over metadata and heuristics.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path

from colorama import Fore, Style

import utils

TAG = f"{Style.BRIGHT}{Fore.BLUE}[Track Repair]{Style.RESET_ALL}"
KINDS = ('audio', 'subtitles')
PURPOSE_LABEL = {'full': 'Full Subtitles', 'signs': 'Signs & Songs', 'sdh': 'SDH', 'commentary': 'Commentary'}
_PURPOSE_PATTERNS = (
    ('commentary', r'commentary'),
    ('sdh', r'\bsdh\b|hearing|caption'),
    ('signs', r'sign|song'),
    ('full', r'full|dialog'),
)
SMALL_TRACK_RATIO = 0.5
MAX_LISTED_FOLDERS = 15


# ---------------------------------------------------------------------------
# Language helpers
# ---------------------------------------------------------------------------

def _lang3(code):
    """Canonical 3-letter code; 'und' for missing/undetermined."""
    code = (code or '').strip().lower().split('-')[0]
    if code in ('', 'und', 'zxx', 'mis', 'mul'):
        return 'und'
    if len(code) == 2:
        return utils.LANG_2TO3_PREFERRED.get(code, code)
    return utils.LANG_2TO3_PREFERRED.get(utils.LANG_3TO2_MAP.get(code, ''), code)


def _lang_ietf(code3):
    return utils.LANG_3TO2_MAP.get(code3, code3)


_LANG_NAMES = {}
for _name, _c2 in utils.LANG_FULLNAME_TO_2.items():
    _LANG_NAMES.setdefault(_lang3(_c2), _name.capitalize())


def _lang_name(code3):
    return 'Undetermined' if code3 == 'und' else _LANG_NAMES.get(code3, code3.upper())


def _parse_lang(text):
    """Language code from a full name or 2/3-letter code; None if unrecognized."""
    text = text.strip().lower()
    if text in utils.LANG_FULLNAME_TO_2:
        return _lang3(utils.LANG_FULLNAME_TO_2[text])
    if re.fullmatch(r'[a-z]{2,3}', text):
        return _lang3(text)
    return None


def _name_language_hint(name):
    for token in re.split(r'[^a-z]+', (name or '').lower()):
        if token in utils.LANG_FULLNAME_TO_2:
            return _lang3(utils.LANG_FULLNAME_TO_2[token])
    return None


def _norm_name(name):
    return re.sub(r'\s+', ' ', (name or '').strip()).casefold()


def _purpose_hint(name):
    for purpose, pattern in _PURPOSE_PATTERNS:
        if re.search(pattern, name or '', re.IGNORECASE):
            return purpose
    return None


# ---------------------------------------------------------------------------
# Track discovery and inspection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Track:
    tid: int
    type: str
    idx: int          # 1-based position within its own type
    codec: str
    lang: str
    name: str
    default: bool
    forced: bool
    uid: int = None
    size: int = None  # optional; only comparable between tracks with the same size_unit
    size_unit: str = ''
    lang_ok: bool = True
    channels: int = 0


@dataclass
class MediaFile:
    path: Path
    tracks: list = field(default_factory=list)   # audio + subtitles in physical order
    fixed_tids: list = field(default_factory=list)  # video and any other track kept untouched
    raw: dict = field(default_factory=dict, repr=False)  # full `mkvmerge -J` result


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')


def _open_media(path):
    try:
        if os.name == 'nt':
            os.startfile(str(path))
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', str(path)])
        else:
            subprocess.Popen(['xdg-open', str(path)])
    except Exception as e:
        print(f"{TAG} {Fore.RED}Could not open {path}: {e}{Style.RESET_ALL}")


_PLAYERS = ('vlc.exe', 'mpc-hc64.exe', 'mpc-hc.exe', 'mpc-be64.exe', 'mpc-be.exe',
            'potplayermini64.exe', 'potplayermini.exe', 'mpv.exe')


def _close_players():
    """Close known media players (opened for verification) so they cannot lock files about to be replaced."""
    if os.name != 'nt':
        return []
    closed = [exe for exe in _PLAYERS if _run(['taskkill', '/IM', exe, '/F']).returncode == 0]
    if closed:
        time.sleep(1)
    return closed


def parse_mkvmerge_json(path, data):
    media = MediaFile(Path(path), raw=data)
    counters = Counter()
    for tr in data.get('tracks', []):
        props = tr.get('properties', {})
        kind = tr.get('type')
        if kind not in KINDS:
            media.fixed_tids.append(tr['id'])
            continue
        counters[kind] += 1
        lang = _lang3(props.get('language_ietf') or props.get('language'))
        lang_ok = not (props.get('language') and props.get('language_ietf')) \
            or _lang3(props['language']) == _lang3(props['language_ietf'])
        size, unit = None, ''
        for key, u in (('tag_number_of_bytes', 'bytes'), ('tag_number_of_frames', 'events')):
            try:
                size, unit = int(props[key]), u
                break
            except (KeyError, TypeError, ValueError):
                continue
        media.tracks.append(Track(
            tid=tr['id'], type=kind, idx=counters[kind], codec=tr.get('codec', ''), lang=lang,
            name=props.get('track_name', '') or '', default=bool(props.get('default_track')),
            forced=bool(props.get('forced_track')), uid=props.get('uid'), size=size, size_unit=unit,
            lang_ok=lang_ok, channels=int(props.get('audio_channels') or 0)))
    return media


def scan_file(path):
    result = _run(['mkvmerge', '-J', str(path)])
    if result.returncode >= 2:
        raise RuntimeError(((result.stdout or result.stderr).strip().splitlines() or ['mkvmerge failed'])[0])
    return parse_mkvmerge_json(path, json.loads(result.stdout))


def track_label(t, name=None):
    name = t.name if name is None else name
    return f"{name or '(no name)'} [{t.lang}]"


def print_inventory(media, root=None):
    rel = os.path.relpath(media.path, root) if root else media.path.name
    print(f"\n{TAG} {Fore.CYAN}{rel}{Style.RESET_ALL}")
    for kind, title in (('audio', 'Audio'), ('subtitles', 'Subtitles')):
        group = [t for t in media.tracks if t.type == kind]
        if not group:
            continue
        print(f"\n{Style.BRIGHT}{Fore.CYAN}{title}:{Style.RESET_ALL}")
        for t in group:
            flags = ''.join(f" {c}({f}){Style.RESET_ALL}" for f, c, on in
                            (('default', Fore.GREEN, t.default), ('forced', Fore.LIGHTYELLOW_EX, t.forced)) if on)
            print(f"{Fore.WHITE}{t.idx}. {track_label(t)}{Style.RESET_ALL}{flags}")


# ---------------------------------------------------------------------------
# Structural signatures and global pattern grouping
# ---------------------------------------------------------------------------

def track_key(t):
    return (t.type, t.codec, t.lang, _norm_name(t.name), t.default, t.forced)


def signature(tracks):
    """Ordered structural signature of audio/subtitle tracks; independent of file, episode or season names."""
    return tuple(track_key(t) for t in tracks)


@dataclass
class Pattern:
    label: str
    signature: tuple
    files: list
    plan: 'Plan' = None
    applied: bool = False

    @property
    def tracks(self):
        return self.files[0].tracks


def group_patterns(files):
    groups = {}
    for media in files:
        groups.setdefault(signature(media.tracks), []).append(media)
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), str(kv[1][0].path)))
    return [Pattern(_pattern_label(i), sig, sorted(fs, key=lambda m: str(m.path))) for i, (sig, fs) in enumerate(ordered)]


def _pattern_label(i):
    return chr(65 + i) if i < 26 else f"P{i + 1}"


# ---------------------------------------------------------------------------
# Heuristics: used only to decide which questions to ask
# ---------------------------------------------------------------------------

def suspicions(tracks):
    """Per-track list of reasons the metadata may be unreliable (hypotheses, never conclusions)."""
    notes = [[] for _ in tracks]
    for i, t in enumerate(tracks):
        siblings = [(j, o) for j, o in enumerate(tracks) if o.type == t.type and o.lang == t.lang]
        if t.lang == 'und':
            notes[i].append('language is undefined')
        if not t.lang_ok:
            notes[i].append('language fields disagree (ISO 639-2 vs IETF)')
        if len(siblings) > 1:
            notes[i].append(f"{len(siblings)} {t.type} tracks share language {_lang_name(t.lang)}")
        hint = _name_language_hint(t.name)
        if hint and hint != t.lang:
            notes[i].append(f"name mentions {_lang_name(hint)} but language is {_lang_name(t.lang)}")
        if t.type == 'subtitles' and t.size is not None:
            peers = [o for _, o in siblings if o is not t and o.size is not None and o.size_unit == t.size_unit]
            if peers and t.size < SMALL_TRACK_RATIO * max(o.size for o in peers):
                notes[i].append('contains much less data than its sibling - possibly Signs & Songs (needs verification)')
    return notes


# ---------------------------------------------------------------------------
# Decisions and plans
# ---------------------------------------------------------------------------

@dataclass
class Decision:
    lang: str
    purpose: str = None
    name: str = None      # None keeps each file's own track name
    default: bool = False
    forced: bool = False
    status: str = 'assumed'   # assumed | confirmed | inconclusive


@dataclass
class Plan:
    decisions: list
    order: list           # kept slots in final order: audio first, then subtitles


def final_tracks(plan, tracks):
    out = []
    for slot in plan.order:
        t, d = tracks[slot], plan.decisions[slot]
        out.append(replace(t, lang=d.lang, name=t.name if d.name is None else d.name,
                           default=d.default, forced=d.forced, lang_ok=True))
    return out


def target_signature(plan, tracks):
    return signature(final_tracks(plan, tracks))


def proposed_name(t, d):
    """New descriptive name only when the confirmed language/purpose contradict the current one."""
    purpose_changed = d.purpose in PURPOSE_LABEL and d.purpose != _purpose_hint(t.name)
    if d.lang == t.lang and not purpose_changed:
        return None
    label = PURPOSE_LABEL.get(d.purpose) if (t.type == 'subtitles' or d.purpose == 'commentary') else None
    group = re.search(r'\([^)]*\)\s*$', t.name or '')
    suffix = f" {group.group(0).strip()}" if group else ''
    return f"{_lang_name(d.lang)} - {label}{suffix}" if label else f"{_lang_name(d.lang)}{suffix}"


def diff_tracks(current, desired):
    """(track, properties) pairs for tracks whose metadata differs from the desired state."""
    edits = []
    for cur, des in zip(current, desired):
        props = {}
        if cur.lang != des.lang or not cur.lang_ok:
            props['language'] = des.lang
        if cur.name != des.name:
            props['name'] = des.name
        if cur.default != des.default:
            props['flag-default'] = des.default
        if cur.forced != des.forced:
            props['flag-forced'] = des.forced
        if props:
            edits.append((cur, props))
    return edits


def describe_changes(tracks, plan):
    final = final_tracks(plan, tracks)
    lines = []
    for kind, title in (('audio', 'Audio'), ('subtitles', 'Subtitles')):
        slots = [s for s in plan.order if tracks[s].type == kind]
        if not slots:
            continue
        lines.append(f"{Style.BRIGHT}{Fore.CYAN}{title}:{Style.RESET_ALL}")
        for pos, slot in enumerate(slots, 1):
            old, new = tracks[slot], final[plan.order.index(slot)]
            changes = []
            if old.lang != new.lang:
                changes.append(f"language {old.lang} -> {new.lang}")
            if old.name != new.name:
                changes.append(f"name '{old.name}' -> '{new.name}'")
            if old.default != new.default:
                changes.append("becomes default" if new.default else "default cleared")
            if old.forced != new.forced:
                changes.append("forced flag cleared" if old.forced else "forced flag set")
            state = f" {Fore.GREEN}[DEFAULT]{Style.RESET_ALL}" if new.default else ''
            change_text = f"  {Fore.LIGHTYELLOW_EX}<- {'; '.join(changes)}{Style.RESET_ALL}" if changes else ''
            lines.append(f"  {pos}. {track_label(new)}{state}{change_text}")
    removed = [tracks[s] for s in range(len(tracks)) if s not in plan.order]
    lines.append("Removal: " + (f"{Fore.RED}{'; '.join(f'{t.type} {track_label(t)}' for t in removed)}{Style.RESET_ALL}"
                               if removed else f"{Fore.LIGHTBLACK_EX}none{Style.RESET_ALL}"))
    if plan.order != list(range(len(tracks))):
        lines.append(f"{Fore.LIGHTBLACK_EX}Physical track order will change (remux without re-encoding){Style.RESET_ALL}")
    return lines


# ---------------------------------------------------------------------------
# Console input helpers
# ---------------------------------------------------------------------------

_banner = f"                   {Fore.YELLOW}Intelligent Track Repair{Style.RESET_ALL}"


def _screen(title, *lines):
    """Clear the screen (keeping the ASCII art) and show a step title with plain-language guidance."""
    utils.clear_and_print_ascii(_banner)
    print(f"{TAG} {Style.BRIGHT}{Fore.CYAN}{title}{Style.RESET_ALL}")
    for line in lines:
        print(f"{Fore.WHITE}{line}{Style.RESET_ALL}")
    print()


def _pause(message='Press Enter to continue...'):
    input(f"\n{Fore.YELLOW}{message}{Style.RESET_ALL} ")


def _ask(prompt, valid, default=None):
    while True:
        raw = input(f"{Fore.LIGHTYELLOW_EX}{prompt}{Style.RESET_ALL} ").strip().lower()
        if not raw and default is not None:
            return default
        if raw in valid:
            return raw
        print(f"{Fore.RED}Invalid choice.{Style.RESET_ALL}")


def _choose(options, prompt='Make a choice:', default=None):
    for i, option in enumerate(options, 1):
        print(f"  {Fore.GREEN}{i}{Style.RESET_ALL} = {option}")
    valid = {str(i) for i in range(1, len(options) + 1)}
    return int(_ask(prompt, valid, None if default is None else str(default)))


def _ask_numbers(prompt, count, must_be_permutation=False):
    """List of 1-based numbers; empty list when the user just presses Enter."""
    while True:
        raw = input(f"{Fore.LIGHTYELLOW_EX}{prompt}{Style.RESET_ALL} ").strip()
        if not raw:
            return []
        try:
            nums = [int(x) for x in re.split(r'[,\s]+', raw) if x]
        except ValueError:
            nums = []
        ok = bool(nums) and all(1 <= n <= count for n in nums) and len(set(nums)) == len(nums)
        if ok and (not must_be_permutation or len(nums) == count):
            return nums
        print(f"{Fore.RED}Invalid input.{Style.RESET_ALL}")


def _ask_language(prompt, current):
    """Language options start with the metadata language; returns a 3-letter code or None (unable to determine)."""
    codes = [c for c in (current, 'jpn', 'eng') if c != 'und']
    codes = list(dict.fromkeys(codes))
    options = [f"{_lang_name(c)}{' (as labeled)' if c == current else ''}" for c in codes]
    options += ['Another language', 'Unable to determine']
    print(f"\n{prompt}")
    pick = _choose(options, default=1 if current != 'und' else None)
    if pick <= len(codes):
        return codes[pick - 1]
    if pick == len(codes) + 2:
        return None
    while True:
        raw = input(f"{Fore.LIGHTYELLOW_EX}Language name or code (Enter = unable to determine):{Style.RESET_ALL} ")
        if not raw.strip():
            return None
        parsed = _parse_lang(raw)
        if parsed:
            return parsed
        print(f"{Fore.RED}Language not recognized.{Style.RESET_ALL}")


# ---------------------------------------------------------------------------
# Interactive verification
# ---------------------------------------------------------------------------

_OBSERVATIONS = (
    ('full', 'Full dialogue subtitles'),
    ('signs', 'Only signs, songs or occasional text'),
    ('sdh', 'SDH / hearing-impaired captions'),
    ('commentary', 'Commentary'),
    ('empty', 'No visible subtitles at the tested scene'),
    ('unknown', 'Unable to determine'),
)


def _memory_key(t):
    return (t.type, t.codec, t.lang, _norm_name(t.name))


def _verify_audio(pattern, slot, t, d, note_lines):
    _screen(f"Pattern {pattern.label} - Step 1 of 3: audio track {t.idx}",
            "The example video was opened in your player. Switch it to this audio track and listen for a moment.")
    print(f"{Fore.CYAN}Audio track {t.idx}{Style.RESET_ALL}: {track_label(t)}")
    for note in note_lines:
        print(f"  Note: {note}")
    print()
    lang = _ask_language("What language is actually spoken?", t.lang)
    if lang is None:
        d.status = 'inconclusive'
        return
    d.lang, d.status = lang, 'confirmed'
    if _purpose_hint(t.name) == 'commentary':
        d.purpose = 'commentary'


def _verify_subtitle(pattern, slot, t, d, note_lines):
    attempt = 0
    while True:
        _screen(f"Pattern {pattern.label} - Step 1 of 3: subtitle track {t.idx}",
                "The example video was opened in your player. Switch it to this subtitle track and watch a few lines of dialogue.")
        print(f"{Fore.CYAN}Subtitle track {t.idx}{Style.RESET_ALL}: {track_label(t)}")
        for note in note_lines:
            print(f"  Note: {note}")
        print(f"\n{Style.BRIGHT}{Fore.YELLOW}What do you actually see on screen?{Style.RESET_ALL}")
        pick = _OBSERVATIONS[_choose([label for _, label in _OBSERVATIONS]) - 1][0]
        if pick == 'unknown':
            d.status = 'inconclusive'
            return
        if pick == 'empty':
            print("An empty scene is not proof that the track is empty.")
            if _choose(['Try another scene in another file of this pattern' if len(pattern.files) > 1 else 'Try another scene',
                        'Mark as inconclusive'], default=1) == 1:
                attempt += 1
                _open_media(pattern.files[attempt % len(pattern.files)].path)
                continue
            d.status = 'inconclusive'
            return
        lang = _ask_language("In which language is the text actually written?", t.lang)
        if lang is None:
            d.status = 'inconclusive'
            return
        d.lang, d.purpose, d.status = lang, pick, 'confirmed'
        return


def verify_pattern(pattern, memory):
    """Ask targeted questions about a representative file; returns one Decision per track slot."""
    tracks = pattern.tracks
    decisions = [Decision(t.lang, _purpose_hint(t.name), None, t.default, t.forced) for t in tracks]
    notes = suspicions(tracks)
    flagged = [i for i, n in enumerate(notes) if n]
    key_counts = Counter(_memory_key(t) for t in tracks)

    _screen(f"Pattern {pattern.label} - Step 1 of 3: check what the tracks contain",
            f"{len(pattern.files)} file(s) have exactly these tracks, so you only need to check ONE of them (shown below).",
            "Your answers are applied to every file in this pattern. Nothing is changed until you approve it at the end.")
    print_inventory(pattern.files[0])
    if flagged:
        print(f"\n{Fore.YELLOW}{len(flagged)} track(s) look suspicious. Metadata may not be reliable:{Style.RESET_ALL}")
        for i in flagged:
            print(f"  {tracks[i].type} {tracks[i].idx}: {'; '.join(notes[i])}")
    print(f"\n{Style.BRIGHT}{Fore.YELLOW}How thorough should the check be?{Style.RESET_ALL}")

    scopes = ([('flagged', f"Verify only the {len(flagged)} suspicious track(s)")] if flagged else []) \
        + [('all', 'Verify every track'), ('none', 'Metadata is correct - skip verification')]
    scope = scopes[_choose([label for _, label in scopes], 'Verification scope:',
                           default=len(scopes) if not flagged else 1) - 1][0]
    todo = {'flagged': flagged, 'all': list(range(len(tracks))), 'none': []}[scope]
    if scope == 'none':
        for d in decisions:
            d.status = 'confirmed'

    if todo:
        _open_media(pattern.files[0].path)
    for slot in todo:
        t, d = tracks[slot], decisions[slot]
        remembered = memory.get(_memory_key(t))
        if remembered and key_counts[_memory_key(t)] == 1:
            lang, purpose = remembered
            print(f"\n{track_label(t)} matches a track you verified earlier: {_lang_name(lang)}"
                  f"{' - ' + PURPOSE_LABEL[purpose] if purpose in PURPOSE_LABEL else ''}")
            if _ask('Reuse that result? [Y/n]', {'y', 'n'}, 'y') == 'y':
                d.lang, d.purpose, d.status = lang, purpose, 'confirmed'
                continue
        (_verify_audio if t.type == 'audio' else _verify_subtitle)(pattern, slot, t, d, notes[slot])

    for t, d in zip(tracks, decisions):
        if d.status == 'confirmed' and key_counts[_memory_key(t)] == 1:
            memory[_memory_key(t)] = (d.lang, d.purpose)
        d.name = proposed_name(t, d)
    return decisions


def _slot_label(tracks, decisions, slot):
    t, d = tracks[slot], decisions[slot]
    label = track_label(t, t.name if d.name is None else d.name)
    return label + (' (inconclusive)' if d.status == 'inconclusive' else '')


def review_names(tracks, decisions):
    renamed = [i for i, (t, d) in enumerate(zip(tracks, decisions)) if d.name is not None and d.name != t.name]
    if not renamed:
        return
    while True:
        _screen("Track names",
                "Names are the labels shown in your player's track menu. Because you corrected a language or purpose,",
                "these names are proposed so they stay consistent with it.")
        print("Proposed track names:")
        for n, slot in enumerate(renamed, 1):
            print(f"  {n}. {tracks[slot].type}: '{tracks[slot].name}' -> '{decisions[slot].name}'")
        picked = _ask_numbers("Number to edit its name (Enter = accept):", len(renamed))
        if not picked:
            return
        decisions[renamed[picked[0] - 1]].name = input(f"{Fore.LIGHTYELLOW_EX}New name:{Style.RESET_ALL} ").strip()


def collect_preferences(tracks, decisions):
    """Ask removal, default and order per track type; flags and order follow the user's choices only."""
    order = []
    for kind in KINDS:
        slots = [i for i, t in enumerate(tracks) if t.type == kind]
        if not slots:
            continue
        slots = _choose_removals(kind, slots, tracks, decisions)
        order += _choose_default_and_order(kind, slots, tracks, decisions)
    _confirm_forced(order, tracks, decisions)
    return Plan(decisions, order)


def _print_slots(slots, tracks, decisions):
    for n, slot in enumerate(slots, 1):
        print(f"  {n}. {_slot_label(tracks, decisions, slot)}")


def _choose_removals(kind, slots, tracks, decisions):
    _screen(f"Step 2 of 3: remove {kind} tracks (optional)",
            "Unwanted tracks, such as a duplicate or wrong-language one, can be removed from the file (no re-encoding).",
            "Nothing is removed unless you type its number. Press Enter to keep everything.")
    _print_slots(slots, tracks, decisions)
    while True:
        picked = _ask_numbers("Numbers to remove (Enter = keep all):", len(slots))
        if kind == 'audio' and len(picked) == len(slots):
            print(f"{Fore.RED}At least one audio track must remain.{Style.RESET_ALL}")
            continue
        return [s for n, s in enumerate(slots, 1) if n not in picked]


def _choose_default_and_order(kind, slots, tracks, decisions):
    _screen(f"Step 3 of 3: preferred {kind}",
            f"The default {kind[:-1] if kind == 'subtitles' else kind} track is the one your player selects automatically.",
            "The order decides how the tracks are listed in the player's menu.")
    current = next((s for s in slots if tracks[s].default), None)
    options = [_slot_label(tracks, decisions, s) for s in slots]
    if kind == 'subtitles':
        options.append('No default subtitle track')
    default_pos = slots.index(current) + 1 if current is not None else (len(slots) + 1 if kind == 'subtitles' else 1)
    pick = _choose(options, f"Choose default {kind}:", default=default_pos)
    chosen = slots[pick - 1] if pick <= len(slots) else None
    for s in slots:
        decisions[s].default = s == chosen
    if len(slots) < 2:
        return slots
    recommended = 1 if chosen is not None and chosen != current and slots[0] != chosen else 2
    print(f"\n{kind.capitalize()} order:")
    how = _choose(['Move the default track first, keep the rest in place', 'Keep the current order',
                   'Enter a custom priority order'], default=recommended)
    if how == 1 and chosen is not None:
        return [chosen] + [s for s in slots if s != chosen]
    if how == 3:
        print("Current tracks:")
        _print_slots(slots, tracks, decisions)
        nums = _ask_numbers(f"All {len(slots)} numbers in priority order (Enter = keep current):", len(slots), True)
        return [slots[n - 1] for n in nums] if nums else slots
    return slots


def _confirm_forced(order, tracks, decisions):
    forced = [s for s in order if tracks[s].type == 'subtitles' and decisions[s].forced]
    if not forced:
        return
    _screen("Forced subtitles",
            "Forced tracks only show translations of foreign speech and are normally left as they are.",
            "Forced flags are never changed unless you choose so here. Currently forced:")
    _print_slots(forced, tracks, decisions)
    for n in _ask_numbers("Number(s) whose forced flag should be cleared (Enter = leave unchanged):", len(forced)):
        slot = forced[n - 1]
        if _ask(f"Really clear the forced flag of {_slot_label(tracks, decisions, slot)}? [y/N]", {'y', 'n'}, 'n') == 'y':
            decisions[slot].forced = False


# ---------------------------------------------------------------------------
# Applying a plan to a file
# ---------------------------------------------------------------------------

def _log_path():
    return utils.get_subservient_folder() / 'track_repair_log.jsonl'


def _write_log(path, before, after, remux):
    entry = {'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'file': str(path), 'remux': remux,
             'before': [t.__dict__ for t in before], 'after': [t.__dict__ for t in after]}
    try:
        with open(_log_path(), 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except OSError:
        pass


def _edit_args(track, props, with_ietf=True):
    selector = f"track:={track.uid}" if track.uid else f"track:{'a' if track.type == 'audio' else 's'}{track.idx}"
    args = ['--edit', selector]
    for key, value in props.items():
        if key == 'language':
            args += ['--set', f'language={value}']
            if with_ietf:
                args += ['--set', f'language-ietf={_lang_ietf(value)}']
        elif key == 'name':
            args += ['--set', f'name={value}'] if value else ['--delete', 'name']
        else:
            args += ['--set', f'{key}={int(value)}']
    return args


def _propedit(path, edits):
    for with_ietf in (True, False):  # older mkvpropedit versions lack language-ietf
        cmd = ['mkvpropedit', str(path)]
        for track, props in edits:
            cmd += _edit_args(track, props, with_ietf)
        result = _run(cmd)
        if result.returncode < 2:
            return
    raise RuntimeError((result.stdout or result.stderr).strip() or 'mkvpropedit failed')


def _remux(path, temp, media, plan):
    kept = [media.tracks[s] for s in plan.order]
    audio = [str(t.tid) for t in kept if t.type == 'audio']
    subs = [str(t.tid) for t in kept if t.type == 'subtitles']
    cmd = ['mkvmerge', '-o', str(temp)]
    cmd += ['--audio-tracks', ','.join(audio)] if audio else ['--no-audio']
    cmd += ['--subtitle-tracks', ','.join(subs)] if subs else ['--no-subtitles']
    order = [str(t) for t in media.fixed_tids] + audio + subs
    cmd += ['--track-order', ','.join(f'0:{t}' for t in order), str(path)]
    result = _run(cmd)
    if result.returncode >= 2 or not temp.exists() or temp.stat().st_size == 0:
        raise RuntimeError((result.stdout or result.stderr).strip() or 'mkvmerge failed')


def apply_plan(path, pattern):
    """Returns (status, message); status is changed | unchanged | skipped | failed. Never leaves a half-written original."""
    plan = pattern.plan
    temp = Path(path).with_name(Path(path).stem + '.trackrepair.tmp.mkv')
    try:
        media = scan_file(path)
        current_sig = signature(media.tracks)
        if current_sig == target_signature(plan, pattern.tracks):
            return 'unchanged', 'already matches the verified result'
        if current_sig != pattern.signature:
            return 'skipped', 'track structure changed since the scan'
        desired = final_tracks(plan, media.tracks)
        remux = plan.order != list(range(len(media.tracks)))
        _write_log(path, media.tracks, desired, remux)
        target, current = Path(path), media.tracks
        if remux:
            _remux(path, temp, media, plan)
            remuxed = scan_file(temp)
            if len(remuxed.tracks) != len(desired) or len(remuxed.fixed_tids) != len(media.fixed_tids):
                raise RuntimeError('remuxed file has an unexpected track layout')
            target, current = temp, remuxed.tracks
        edits = diff_tracks(current, desired)
        if edits:
            _propedit(target, edits)
        if signature(scan_file(target).tracks) != signature(desired):
            raise RuntimeError('verification after the change failed')
        if remux:
            os.replace(temp, path)
        return 'changed', 'remuxed and updated' if remux else 'metadata updated'
    except Exception as e:
        return 'failed', str(e)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Quick Track Removal: remove explicitly chosen tracks from one file
# ---------------------------------------------------------------------------

def _channel_text(n):
    return {1: '1.0', 2: '2.0', 6: '5.1', 8: '7.1'}.get(n, f"{n}ch") if n else ''


def _quick_line(t):
    parts = [_lang_name(t.lang), ' '.join(p for p in (t.codec, _channel_text(t.channels)) if p)]
    if t.name:
        parts.append(t.name)
    if t.default:
        parts.append(f"{Fore.GREEN}Default{Style.RESET_ALL}")
    if t.forced:
        parts.append(f"{Fore.LIGHTYELLOW_EX}Forced{Style.RESET_ALL}")
    return ' | '.join(p for p in parts if p)


def _removal_defaults(kept_all, removed):
    """Explicit default flags {tid: bool}: an audio default is promoted when its track is removed; subtitles never get one."""
    flags = {}
    for kind in KINDS:
        kept = [t for t in kept_all if t.type == kind]
        if any(t.default for t in removed if t.type == kind) and kept and not any(t.default for t in kept):
            for i, t in enumerate(kept):
                flags[t.tid] = kind == 'audio' and i == 0
    return flags


def remove_tracks(path, expected_uids, remove_uids):
    """Remux without the selected tracks. Returns (status, message, removed_count, kept_count); the original survives any failure."""
    path = Path(path)
    temp = path.with_name(path.stem + '.trackremoval.tmp.mkv')
    try:
        media = scan_file(path)
        if [t.uid for t in media.tracks] != expected_uids:
            return 'failed', 'the file changed since it was listed; please select again', 0, 0
        removed = [t for t in media.tracks if t.uid in remove_uids]
        kept = [t for t in media.tracks if t.uid not in remove_uids]
        if any(t.type == 'audio' for t in media.tracks) and not any(t.type == 'audio' for t in kept):
            return 'failed', 'at least one audio track must remain', 0, 0
        if not utils.has_free_space(path.parent, path.stat().st_size):
            return 'failed', 'not enough free disk space for the temporary file', 0, 0
        audio = [str(t.tid) for t in kept if t.type == 'audio']
        subs = [str(t.tid) for t in kept if t.type == 'subtitles']
        flags = _removal_defaults(kept, removed)
        cmd = ['mkvmerge', '-o', str(temp)]
        cmd += ['--audio-tracks', ','.join(audio)] if audio else ['--no-audio']
        cmd += ['--subtitle-tracks', ','.join(subs)] if subs else ['--no-subtitles']
        order = [str(t) for t in media.fixed_tids] + [str(t.tid) for t in kept]
        for tid, on in flags.items():
            cmd += ['--default-track-flag', f"{tid}:{int(on)}"]
        cmd += ['--track-order', ','.join(f'0:{t}' for t in order), str(path)]
        result = _run(cmd)
        if result.returncode >= 2 or not temp.exists() or temp.stat().st_size == 0:
            raise RuntimeError(((result.stdout or result.stderr).strip().splitlines() or ['mkvmerge failed'])[0])
        out = scan_file(temp)
        problem = utils.check_remux_result(media.raw, out.raw, audio, subs)
        want = [(t.type, t.lang, t.name, t.forced, flags.get(t.tid, t.default)) for t in kept]
        got = [(t.type, t.lang, t.name, t.forced, t.default) for t in out.tracks]
        if problem or want != got:
            raise RuntimeError(problem or 'retained tracks differ from the source')
        _write_log(path, media.tracks, kept, True)
        os.replace(temp, path)
        return 'removed', 'done', len(removed), len(kept)
    except Exception as e:
        return 'failed', str(e), 0, 0
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def _pick_file(paths, root, title="Quick Track Removal", text="Choose the file to remove tracks from."):
    _screen(title, text)
    options = [os.path.relpath(p, root) for p in paths] + [f"{Fore.RED}Back{Style.RESET_ALL}"]
    pick = _choose(options, 'Which file?')
    return None if pick == len(options) else paths[pick - 1]


def _quick_remove_file(path, root):
    """Select, confirm and remove tracks from one file. Returns 'removed', 'cancelled' or 'failed'."""
    try:
        media = scan_file(path)
    except Exception as e:
        _screen("Quick Track Removal")
        print(f"{Fore.RED}Could not read {Path(path).name}: {e}{Style.RESET_ALL}")
        _pause()
        return 'failed'
    numbered = [t for kind in KINDS for t in media.tracks if t.type == kind]
    if not numbered:
        _screen("Quick Track Removal")
        print(f"{Fore.YELLOW}This file has no audio or subtitle tracks.{Style.RESET_ALL}")
        _pause()
        return 'failed'
    number_of = {t.uid: n for n, t in enumerate(numbered, 1)}
    has_audio = any(t.type == 'audio' for t in numbered)
    while True:
        _screen("Quick Track Removal", f"File: {Path(path).name}",
                "Only the tracks you select and confirm are removed. Nothing is re-encoded and nothing else is changed.")
        for kind, title in (('audio', 'Audio Tracks'), ('subtitles', 'Subtitle Tracks')):
            group = [t for t in numbered if t.type == kind]
            if group:
                print(f"{Style.BRIGHT}{Fore.CYAN}{title}:{Style.RESET_ALL}")
                for t in group:
                    print(f"{Fore.WHITE}{number_of[t.uid]}.{Style.RESET_ALL} {_quick_line(t)}")
                print()
        picked = _ask_numbers("Select track(s) to remove, e.g. 3,5 (Enter = cancel):", len(numbered))
        if not picked:
            return 'cancelled'
        removed = [numbered[n - 1] for n in picked]
        kept = [t for t in numbered if t not in removed]
        if has_audio and not any(t.type == 'audio' for t in kept):
            print(f"\n{Fore.RED}Every audio track would be removed and the video would be silent. Keep at least one audio track.{Style.RESET_ALL}")
            _pause()
            continue
        _screen("Quick Track Removal - confirm")
        print(f"{Style.BRIGHT}{Fore.YELLOW}Selected for removal:{Style.RESET_ALL}")
        for kind, title in (('audio', 'Audio'), ('subtitles', 'Subtitles')):
            group = [t for t in removed if t.type == kind]
            if group:
                print(f"\n{Style.BRIGHT}{Fore.CYAN}{title}:{Style.RESET_ALL}")
                for t in group:
                    print(f"{Fore.RED}- {Style.RESET_ALL}{_quick_line(t)}")
        print(f"\n{Style.BRIGHT}{Fore.CYAN}Tracks retained:{Style.RESET_ALL}")
        for t in kept:
            print(f"{Fore.GREEN}- {Style.RESET_ALL}{_lang_name(t.lang)} {t.type[:-1] if t.type == 'subtitles' else t.type}")
        promoted = [t for t in kept if _removal_defaults(kept, removed).get(t.tid) and t.type == 'audio']
        if promoted:
            print(f"\n{Fore.LIGHTBLACK_EX}The removed audio track was the default; {_lang_name(promoted[0].lang)} becomes the default audio.{Style.RESET_ALL}")
        print()
        if _choose(['Yes', 'Cancel'], 'Proceed with removal?', default=2) == 2:
            return 'cancelled'
        break
    _screen("Quick Track Removal", "Removing the selected tracks. Please wait and do not open the file in a player.")
    status, message, n_removed, n_kept = remove_tracks(path, [t.uid for t in media.tracks], {t.uid for t in removed})
    if status != 'removed':
        print(f"{TAG} {Fore.RED}Removal failed: {message}{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}The original file was not changed.{Style.RESET_ALL}")
        _pause()
        return 'failed'
    _screen("Removal Complete")
    print(f"{Fore.WHITE}Removed: {Fore.RED}{n_removed}{Fore.WHITE} track(s){Style.RESET_ALL}")
    print(f"{Fore.WHITE}Retained: {Fore.GREEN}{n_kept}{Fore.WHITE} track(s){Style.RESET_ALL}\n")
    return 'removed'


def quick_removal(root):
    paths = discover_mkv_files(root)
    if not paths:
        _screen("Quick Track Removal")
        print(f"{Fore.YELLOW}No MKV files found in {root}{Style.RESET_ALL}")
        _pause('Press Enter to return to the menu...')
        return
    while True:
        path = paths[0] if len(paths) == 1 else _pick_file(paths, root)
        if path is None:
            return
        status = _quick_remove_file(path, root)
        if status == 'removed':
            if _choose(['Process another file', 'Return to Track Repair menu'], default=2) == 2:
                return
        elif len(paths) == 1:
            return


# ---------------------------------------------------------------------------
# Change Default Audio Track: flag-only change, no remux
# ---------------------------------------------------------------------------

def set_default_audio(path, expected_uids, target_uid):
    """Make one audio track the only default via mkvpropedit. Returns (status, message)."""
    try:
        media = scan_file(path)
        if [t.uid for t in media.tracks] != expected_uids:
            return 'failed', 'the file changed since it was listed; please select again'
        audio = [t for t in media.tracks if t.type == 'audio']
        if not any(t.uid == target_uid for t in audio):
            return 'failed', 'the selected audio track no longer exists'
        edits = [(t, {'flag-default': t.uid == target_uid}) for t in audio if t.default != (t.uid == target_uid)]
        if edits:
            _write_log(path, media.tracks, media.tracks, False)
            _propedit(path, edits)
        after = [t for t in scan_file(path).tracks if t.type == 'audio']
        if [t.uid for t in after if t.default] != [target_uid]:
            return 'failed', 'verification after the change failed'
        return 'changed', 'done'
    except Exception as e:
        return 'failed', str(e)


def _default_audio_file(path):
    """Choose and apply a new default audio track for one file. Returns 'changed', 'cancelled' or 'failed'."""
    try:
        media = scan_file(path)
    except Exception as e:
        _screen("Change Default Audio Track")
        print(f"{Fore.RED}Could not read {Path(path).name}: {e}{Style.RESET_ALL}")
        _pause()
        return 'failed'
    audio = [t for t in media.tracks if t.type == 'audio']
    if len(audio) < 2:
        _screen("Change Default Audio Track")
        print(f"{Fore.YELLOW}{Path(path).name} has fewer than two audio tracks; there is nothing to choose.{Style.RESET_ALL}")
        _pause()
        return 'failed'
    while True:
        _screen("Change Default Audio Track", f"File: {Path(path).name}",
                "Only the default flag changes. Nothing is re-encoded, remuxed or reordered.")
        print(f"{Style.BRIGHT}{Fore.CYAN}Audio Tracks:{Style.RESET_ALL}")
        for n, t in enumerate(audio, 1):
            print(f"{Fore.WHITE}{n}.{Style.RESET_ALL} {_quick_line(t)}")
        print()
        picked = _ask_numbers("Select the audio track to make default (Enter = cancel):", len(audio))
        if not picked:
            return 'cancelled'
        if len(picked) != 1:
            print(f"{Fore.RED}Select exactly one track.{Style.RESET_ALL}")
            _pause()
            continue
        target = audio[picked[0] - 1]
        if [t.uid for t in audio if t.default] == [target.uid]:
            print(f"\n{Fore.YELLOW}That track is already the default audio track.{Style.RESET_ALL}")
            _pause()
            continue
        _screen("Change Default Audio Track - confirm")
        current = [t for t in audio if t.default]
        print(f"{Style.BRIGHT}{Fore.YELLOW}Current default:{Style.RESET_ALL}")
        for t in current or []:
            print(f"{Fore.RED}- {Style.RESET_ALL}{_quick_line(t)}")
        if not current:
            print(f"{Fore.LIGHTBLACK_EX}none{Style.RESET_ALL}")
        print(f"\n{Style.BRIGHT}{Fore.CYAN}New default:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}- {Style.RESET_ALL}{_quick_line(target)}\n")
        if _choose(['Yes', 'Cancel'], 'Proceed with change?', default=2) == 2:
            return 'cancelled'
        break
    _screen("Change Default Audio Track", "Updating the default flag. Please do not open the file in a player.")
    status, message = set_default_audio(path, [t.uid for t in media.tracks], target.uid)
    if status != 'changed':
        print(f"{TAG} {Fore.RED}Change failed: {message}{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}The file was not changed.{Style.RESET_ALL}")
        _pause()
        return 'failed'
    _screen("Default Audio Updated")
    print(f"{Fore.WHITE}Default audio: {Fore.GREEN}{_lang_name(target.lang)}{Fore.WHITE} {target.name}{Style.RESET_ALL}\n")
    return 'changed'


def change_default_audio(root):
    paths = discover_mkv_files(root)
    if not paths:
        _screen("Change Default Audio Track")
        print(f"{Fore.YELLOW}No MKV files found in {root}{Style.RESET_ALL}")
        _pause('Press Enter to return to the menu...')
        return
    while True:
        path = paths[0] if len(paths) == 1 else _pick_file(
            paths, root, "Change Default Audio Track", "Choose the file to change the default audio track of.")
        if path is None:
            return
        status = _default_audio_file(path)
        if status == 'changed':
            if _choose(['Process another file', 'Return to Track Repair menu'], default=2) == 2:
                return
        elif len(paths) == 1:
            return


# ---------------------------------------------------------------------------
# Session: scanning, pattern overview, approval and execution
# ---------------------------------------------------------------------------

def discover_mkv_files(root):
    return sorted(p for p in map(Path, utils.find_videos_in_directory(root)) if p.suffix.lower() == '.mkv')


def _folder_label(media, root):
    rel = os.path.relpath(media.path.parent, root)
    return Path(root).name if rel == '.' else rel


def pattern_status(pattern, patterns):
    if pattern.plan is None:
        for other in patterns:
            if other is not pattern and other.plan and target_signature(other.plan, other.tracks) == pattern.signature:
                return f"already matches the result of Pattern {other.label}"
        return 'not verified'
    if target_signature(pattern.plan, pattern.tracks) == pattern.signature:
        return 'verified - no changes needed'
    return 'applied' if pattern.applied else 'verified - changes pending'


def _status_color(status):
    if status.startswith(('verified - no', 'applied', 'already')):
        return Fore.GREEN
    return Fore.LIGHTYELLOW_EX if 'pending' in status else Fore.LIGHTBLACK_EX


def print_analysis(patterns, root, total):
    print(f"{Style.BRIGHT}{Fore.CYAN}Pattern analysis{Style.RESET_ALL} - {Fore.WHITE}{total} file(s) scanned{Style.RESET_ALL}")
    for p in patterns:
        status = pattern_status(p, patterns)
        print(f"\n{Style.BRIGHT}{Fore.CYAN}Pattern {p.label}{Style.RESET_ALL} - {Fore.WHITE}{len(p.files)} file(s){Style.RESET_ALL}"
              f" - {_status_color(status)}{status}{Style.RESET_ALL}")
        folders = Counter(_folder_label(m, root) for m in p.files)
        for folder, count in list(folders.items())[:MAX_LISTED_FOLDERS]:
            print(f"  {Fore.LIGHTBLACK_EX}- {folder}: {count}{Style.RESET_ALL}")
        if len(folders) > MAX_LISTED_FOLDERS:
            print(f"  {Fore.LIGHTBLACK_EX}... and {len(folders) - MAX_LISTED_FOLDERS} more folder(s){Style.RESET_ALL}")
        if len(p.files) <= 5:
            print(f"  {Fore.LIGHTBLACK_EX}Files: {', '.join(m.path.stem for m in p.files)}{Style.RESET_ALL}")


def print_preview(pattern, patterns):
    print(f"{Style.BRIGHT}{Fore.CYAN}Proposed changes - Pattern {pattern.label}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}Matching files: {len(pattern.files)}{Style.RESET_ALL}")
    for line in describe_changes(pattern.tracks, pattern.plan):
        print(line)
    already = [o for o in patterns if o is not pattern and pattern_status(o, patterns).endswith(f"Pattern {pattern.label}")]
    if already:
        print(f"{Fore.GREEN}Already repaired ({sum(len(o.files) for o in already)} file(s)): no modification needed{Style.RESET_ALL}")


def _split_folders(pattern, patterns, root, folders):
    moved = [m for m in pattern.files if _folder_label(m, root) in folders]
    pattern.files = [m for m in pattern.files if m not in moved]
    patterns.append(Pattern(_pattern_label(len(patterns)), pattern.signature, moved))
    print(f"{TAG} {len(moved)} file(s) moved to Pattern {patterns[-1].label} for separate verification.")


def _folder_scope_menu(pattern, patterns, root):
    folders = list(dict.fromkeys(_folder_label(m, root) for m in pattern.files))
    counts = Counter(_folder_label(m, root) for m in pattern.files)
    _screen(f"Pattern {pattern.label} - exclude or spot-check folders",
            "Exclude folders whose files differ from what you verified; they become a separate pattern to verify on their own.",
            "Or spot-check: open one file from a folder and confirm it matches your verified choices.")
    for n, f in enumerate(folders, 1):
        print(f"  {n}. {f} ({counts[f]})")
    raw = input(f"{Fore.LIGHTYELLOW_EX}Folder numbers to exclude, 's<number>' to spot-check one, Enter = back:{Style.RESET_ALL} ").strip().lower()
    spot = raw.startswith('s')
    try:
        nums = [int(x) for x in re.split(r'[,\s]+', raw[1:] if spot else raw) if x]
    except ValueError:
        nums = []
    nums = [n for n in nums if 1 <= n <= len(folders)]
    if not nums:
        return
    if not spot:
        _split_folders(pattern, patterns, root, {folders[n - 1] for n in nums})
        return
    folder = folders[nums[0] - 1]
    sample = next(m for m in pattern.files if _folder_label(m, root) == folder)
    _open_media(sample.path)
    _screen(f"Spot-check: {folder}", "A file from this folder was opened in your player. Compare it with the verified contents below.")
    print_inventory(sample, root)
    print("\nVerified contents of these tracks:")
    for slot, t in enumerate(sample.tracks):
        print(f"  {t.type} {t.idx}: {_slot_label(sample.tracks, pattern.plan.decisions, slot)}")
    if _choose(['Matches what I see/hear', 'Does not match - exclude this folder'], default=1) == 2:
        _split_folders(pattern, patterns, root, {folder})


def approve_and_apply(pattern, patterns, root):
    """Show the change plan, let the user adjust scope, then apply. Returns list of (path, status, message)."""
    while pattern.files:
        _screen(f"Pattern {pattern.label} - apply changes",
                "Below is what would change in every file of this pattern. Tracks are never re-encoded, and original",
                "values are logged. Nothing happens until you choose 'Apply'.")
        print_preview(pattern, patterns)
        folders = {_folder_label(m, root) for m in pattern.files}
        options = ['Apply', 'Review individual files']
        options += ['Exclude or spot-check folders'] if len(folders) > 1 else []
        options += ['Skip this pattern']
        pick = options[_choose(options, f"Apply these changes to all {len(pattern.files)} file(s)?") - 1]
        if pick == 'Review individual files':
            for m in pattern.files:
                print(f"  {os.path.relpath(m.path, root)}")
            _pause()
        elif pick == 'Exclude or spot-check folders':
            _folder_scope_menu(pattern, patterns, root)
        elif pick == 'Skip this pattern':
            return []
        else:
            break
    results = []
    _screen(f"Pattern {pattern.label} - applying changes", "Please wait and do not close this window or open these files in a player.")
    closed = _close_players()
    if closed:
        print(f"{Fore.LIGHTBLACK_EX}Closed media player(s) so they cannot lock the files: {', '.join(closed)}{Style.RESET_ALL}\n")
    try:
        for i, media in enumerate(pattern.files, 1):
            status, message = apply_plan(media.path, pattern)
            color = {'changed': Fore.GREEN, 'unchanged': Fore.YELLOW}.get(status, Fore.RED)
            print(f"{TAG} [{i}/{len(pattern.files)}] {color}{status}{Style.RESET_ALL}: {media.path.name} - {message}")
            results.append((media.path, status, message))
    except KeyboardInterrupt:
        print(f"\n{TAG} {Fore.YELLOW}Cancelled. Remaining files were not touched.{Style.RESET_ALL}")
    pattern.applied = bool(results) and all(s in ('changed', 'unchanged') for _, s, _ in results) \
        and len(results) == len(pattern.files)
    if results:
        print_summary(results)
        _pause()
    return results


def print_summary(results):
    counts = Counter(status for _, status, _ in results)
    print(f"\n{TAG} {Style.BRIGHT}Summary{Style.RESET_ALL}: " + ', '.join(f"{n} {s}" for s, n in sorted(counts.items())))
    for path, status, message in results:
        if status in ('failed', 'skipped'):
            print(f"  {Fore.RED}{status}{Style.RESET_ALL}: {path} - {message}")


def run_track_repair(root, banner_line=''):
    """Entry point from the Extra Tools menu."""
    global _banner
    if banner_line:
        _banner = banner_line
    if not (shutil.which('mkvmerge') and shutil.which('mkvpropedit')):
        _screen("MKVToolNix not found")
        print(f"{TAG} {Fore.RED}MKVToolNix (mkvmerge and mkvpropedit) was not found in your PATH.{Style.RESET_ALL}")
        input(f"\n{Fore.YELLOW}Press Enter to return...{Style.RESET_ALL} ")
        return
    _main_menu(Path(root))


def _main_menu(root):
    while True:
        _screen("Intelligent Track Repair", "Choose how you want to work on your MKV files.")
        print(f"  {Fore.GREEN}1{Style.RESET_ALL} = Intelligent Track Analysis & Repair "
              f"{Fore.LIGHTBLACK_EX}(verify, correct, order and remove tracks for whole series){Style.RESET_ALL}")
        print(f"  {Fore.GREEN}2{Style.RESET_ALL} = Quick Track Removal "
              f"{Fore.LIGHTBLACK_EX}(remove chosen tracks from a single file){Style.RESET_ALL}")
        print(f"  {Fore.GREEN}3{Style.RESET_ALL} = Change Default Audio Track "
              f"{Fore.LIGHTBLACK_EX}(choose which audio track plays by default in a single file){Style.RESET_ALL}")
        print(f"  {Fore.RED}4{Style.RESET_ALL} = Return to Extra Tools\n")
        pick = _ask('Make a choice:', {'1', '2', '3', '4'})
        if pick == '4':
            return
        try:
            if pick == '1':
                _session(root)
                _pause('Press Enter to return to the menu...')
            elif pick == '2':
                quick_removal(root)
            else:
                change_default_audio(root)
        except (KeyboardInterrupt, EOFError):
            print(f"\n{TAG} {Fore.YELLOW}Cancelled.{Style.RESET_ALL}")
            _pause('Press Enter to return to the menu...')


def _session(root):
    paths = discover_mkv_files(root)
    _screen("Scanning", "Reading the audio and subtitle tracks of your MKV files. This only reads; nothing is changed.")
    if not paths:
        print(f"{TAG} {Fore.YELLOW}No MKV files found in {root}{Style.RESET_ALL}")
        return
    files, failed = [], []
    for i, path in enumerate(paths, 1):
        print(f"\r{TAG} Scanning {i}/{len(paths)}", end='', flush=True)
        try:
            files.append(scan_file(path))
        except Exception as e:
            failed.append((path, str(e)))
    print()
    for path, err in failed:
        print(f"{TAG} {Fore.RED}Could not scan {path.name}: {err}{Style.RESET_ALL}")
    if failed:
        _pause()
    files = [m for m in files if m.tracks]
    if not files:
        print(f"{TAG} {Fore.YELLOW}No audio or subtitle tracks found.{Style.RESET_ALL}")
        return

    patterns, memory, results = group_patterns(files), {}, []
    while True:
        _screen("Overview",
                "Files with exactly the same audio and subtitle tracks are grouped into a 'pattern'.",
                "Suggested steps: 1) verify each pattern (check one example file), 2) apply the approved corrections.")
        print_analysis(patterns, root, len(files))
        pending = [p for p in patterns if p.plan and not p.applied and pattern_status(p, patterns) == 'verified - changes pending']
        options = ['Verify / inspect a pattern', 'Review all proposed changes']
        options += [f"Apply approved corrections ({len(pending)} pattern(s) pending)"] if pending else []
        options += ['Finish']
        unverified = any(p.plan is None and pattern_status(p, patterns) == 'not verified' for p in patterns)
        default = 3 if pending else (1 if unverified else len(options))
        pick = options[_choose(options, 'What do you want to do?', default=default) - 1]
        if pick == 'Finish':
            break
        if pick == 'Verify / inspect a pattern':
            _verify_menu(patterns, memory)
        elif pick == 'Review all proposed changes':
            _screen("All proposed changes")
            shown = [p for p in patterns if p.plan]
            for p in shown:
                print_preview(p, patterns)
            if not shown:
                print("Nothing verified yet, so there are no proposed changes.")
            _pause()
        else:
            for p in pending:
                results += approve_and_apply(p, patterns, root)


def _verify_menu(patterns, memory):
    unverified = [p for p in patterns if p.plan is None]
    labels = [f"Pattern {p.label} ({len(p.files)} file(s)) - {pattern_status(p, patterns)}" for p in patterns]
    default = patterns.index(unverified[0]) + 1 if unverified else 1
    _screen("Choose a pattern", "Pick the pattern you want to check. One example file of it will be opened in your player.")
    pattern = patterns[_choose(labels, 'Which pattern?', default=default) - 1]
    if pattern.plan and _ask('This pattern is already verified. Redo it? [y/N]', {'y', 'n'}, 'n') != 'y':
        return
    decisions = verify_pattern(pattern, memory)
    review_names(pattern.tracks, decisions)
    pattern.plan, pattern.applied = collect_preferences(pattern.tracks, decisions), False
    _screen(f"Pattern {pattern.label} - your choices")
    print_preview(pattern, patterns)
    print("\nNothing has been changed yet. Choose 'Apply approved corrections' in the overview to continue.")
    _pause()
