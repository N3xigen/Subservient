"""Tests for Intelligent Track Repair. Run with: python -m unittest discover -s tests -v

MKVToolNix is mocked by FakeMkv, which keeps each "MKV" as a JSON state inside a real file so that
remux, in-place edits and os.replace behave like the real tools. RealToolsTest uses actual MKVToolNix/ffmpeg when installed.
"""
import itertools
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import track_repair as tr  # noqa: E402

_uid = itertools.count(1000)


def T(kind, lang, name='', default=False, forced=False, size=None, ietf=None):
    return {'type': kind, 'codec': {'audio': 'AAC', 'subtitles': 'SubRip/SRT', 'video': 'AVC'}[kind], 'lang': lang,
            'ietf': ietf if ietf is not None else lang, 'name': name, 'default': default, 'forced': forced,
            'uid': next(_uid), 'size': size}


VIDEO = lambda: T('video', 'und')  # noqa: E731


class FakeMkv:
    """Emulates mkvmerge -J, mkvmerge remux and mkvpropedit against JSON-in-file media."""

    def __init__(self):
        self.calls = []
        self.fail_remux = False
        self.fail_propedit = False

    @staticmethod
    def make(path, tracks):
        Path(path).write_text(json.dumps({'tracks': tracks}), encoding='utf-8')

    @staticmethod
    def state(path):
        return json.loads(Path(path).read_text(encoding='utf-8'))['tracks']

    def __call__(self, cmd):
        self.calls.append(cmd)
        if cmd[0] == 'mkvmerge' and cmd[1] == '-J':
            return self._identify(cmd[2])
        if cmd[0] == 'mkvpropedit':
            return self._propedit(cmd)
        return self._remux(cmd)

    def _identify(self, path):
        tracks = []
        for i, t in enumerate(self.state(path)):
            props = {'language': t['lang'], 'language_ietf': t['ietf'], 'track_name': t['name'],
                     'default_track': t['default'], 'forced_track': t['forced'], 'uid': t['uid']}
            if t['size'] is not None:
                props['tag_number_of_bytes'] = str(t['size'])
            tracks.append({'id': i, 'type': t['type'], 'codec': t['codec'], 'properties': props})
        return CompletedProcess([], 0, json.dumps({'tracks': tracks}), '')

    def _propedit(self, cmd):
        if self.fail_propedit:
            return CompletedProcess(cmd, 2, 'Error: edit failed', '')
        tracks, current = self.state(cmd[1]), None
        it = iter(cmd[2:])
        for arg in it:
            if arg == '--edit':
                selector = next(it).split(':', 1)[1]
                if selector.startswith('='):
                    current = next(t for t in tracks if t['uid'] == int(selector[1:]))
                else:
                    kind = {'a': 'audio', 's': 'subtitles'}[selector[0]]
                    current = [t for t in tracks if t['type'] == kind][int(selector[1:]) - 1]
            elif arg == '--set':
                key, value = next(it).split('=', 1)
                field = {'language': 'lang', 'language-ietf': 'ietf', 'name': 'name',
                         'flag-default': 'default', 'flag-forced': 'forced'}[key]
                current[field] = bool(int(value)) if key.startswith('flag') else value
            elif arg == '--delete':
                current[next(it)] = ''
        self.make(cmd[1], tracks)
        return CompletedProcess(cmd, 0, '', '')

    def _remux(self, cmd):
        if self.fail_remux:
            return CompletedProcess(cmd, 2, 'Error: remux failed', '')
        out, src = cmd[cmd.index('-o') + 1], cmd[-1]
        tracks = self.state(src)

        def ids(option):
            return [int(x) for x in cmd[cmd.index(option) + 1].split(',')] if option in cmd else []

        keep = set(ids('--audio-tracks')) | set(ids('--subtitle-tracks'))
        order = [int(x.split(':')[1]) for x in cmd[cmd.index('--track-order') + 1].split(',')]
        new = []
        flags = {int(a.split(':')[0]): bool(int(a.split(':')[1]))
                 for prev, a in zip(cmd, cmd[1:]) if prev == '--default-track-flag'}
        for tid in order:
            if tracks[tid]['type'] == 'video' or tid in keep:
                new.append(dict(tracks[tid], uid=next(_uid), **({'default': flags[tid]} if tid in flags else {})))
        self.make(out, new)
        return CompletedProcess(cmd, 0, '', '')


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.fake = FakeMkv()
        self.answers = []
        for target, value in (('_run', self.fake), ('_open_media', lambda p: None),
                              ('_screen', lambda *a: None), ('_pause', lambda *a: None), ('_close_players', lambda: []),
                              ('_log_path', lambda: self.tmp / 'log.jsonl')):
            patcher = mock.patch.object(tr, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch('builtins.input', side_effect=self._next_answer)
        patcher.start()
        self.addCleanup(patcher.stop)
        printer = mock.patch('builtins.print')
        printer.start()
        self.addCleanup(printer.stop)

    def _next_answer(self, prompt=''):
        self.assertTrue(self.answers, f"unexpected prompt: {prompt}")
        return self.answers.pop(0)

    def media(self, name, tracks, folder=None):
        directory = self.tmp / folder if folder else self.tmp
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        self.fake.make(path, [VIDEO()] + tracks)
        return path

    def pattern_for(self, *paths):
        patterns = tr.group_patterns([tr.scan_file(p) for p in paths])
        self.assertEqual(len(patterns), 1)
        return patterns[0]

    def verify(self, pattern, *answers):
        self.answers = list(answers)
        tr._verify_menu([pattern], {})
        self.assertEqual(self.answers, [], 'unused scripted answers')
        return pattern.plan

    def subs(self, path):
        return [t for t in self.fake.state(path) if t['type'] == 'subtitles']

    def audio(self, path):
        return [t for t in self.fake.state(path) if t['type'] == 'audio']


class AudioTests(Base):
    def test_1_wrong_default_audio_is_corrected(self):
        path = self.media('a.mkv', [T('audio', 'jpn', 'Japanese'), T('audio', 'eng', 'English', default=True)])
        p = self.pattern_for(path)
        # pattern, scope=none(default), no removal, default=1 (Japanese), order=keep
        self.verify(p, '', '', '', '1', '')
        self.assertEqual(tr.apply_plan(path, p)[0], 'changed')
        self.assertEqual([t['default'] for t in self.audio(path)], [True, False])
        self.assertNotIn('mkvmerge', [c[0] for c in self.fake.calls if '-o' in c])


class SubtitleTests(Base):
    def full_and_signs(self):
        return [T('subtitles', 'eng', 'Signs & Songs (Shio)', default=True, size=100),
                T('subtitles', 'jpn', 'Full Subtitles (Shio)', size=900)]

    def test_2_full_english_mislabelled_japanese_is_fixed_and_reordered(self):
        path = self.media('a.mkv', self.full_and_signs())
        p = self.pattern_for(path)
        # pattern, scope=all, track1: signs + lang as labeled, track2: full + English, names: accept,
        # removal none, default=2, order=default first (recommended)
        self.verify(p, '', '1', '2', '', '1', '2', '', '', '2', '')
        self.assertEqual(tr.apply_plan(path, p)[0], 'changed')
        first, second = self.subs(path)
        self.assertEqual((first['name'], first['lang'], first['ietf'], first['default']),
                         ('English - Full Subtitles (Shio)', 'eng', 'en', True))
        self.assertEqual((second['name'], second['lang'], second['default']), ('Signs & Songs (Shio)', 'eng', False))

    def test_3_same_language_tracks_with_different_purposes(self):
        tracks = [T('subtitles', 'eng', size=900), T('subtitles', 'eng', size=100)]
        notes = tr.suspicions(tr.parse_mkvmerge_json('x', self._ident(tracks)).tracks)
        self.assertTrue(all(any('share language' in n for n in track_notes) for track_notes in notes))

    def test_4_smaller_track_is_only_a_hypothesis_that_needs_confirmation(self):
        tracks = [T('subtitles', 'eng', size=900), T('subtitles', 'eng', size=100)]
        notes = tr.suspicions(tr.parse_mkvmerge_json('x', self._ident(tracks)).tracks)
        self.assertFalse(any('Signs' in n for n in notes[0]))
        self.assertTrue(any('Signs & Songs (needs verification)' in n for n in notes[1]))
        path = self.media('a.mkv', tracks)
        p = self.pattern_for(path)
        # scope=flagged, track1: full/as labeled, track2: "no visible subtitles" -> another scene -> signs/as labeled,
        # names accept, no removal, default none, order keep
        plan = self.verify(p, '', '1', '1', '', '5', '1', '2', '', '', '', '', '')
        self.assertEqual([d.purpose for d in plan.decisions], ['full', 'signs'])
        self.assertEqual([d.name for d in plan.decisions], ['English - Full Subtitles', 'English - Signs & Songs'])

    def test_4b_unable_to_determine_keeps_metadata(self):
        tracks = [T('subtitles', 'eng', 'English', size=900), T('subtitles', 'eng', 'English 2', size=100)]
        p = self.pattern_for(self.media('a.mkv', tracks))
        plan = self.verify(p, '', '1', '6', '6', '', '', '')
        self.assertEqual([d.status for d in plan.decisions], ['inconclusive', 'inconclusive'])
        self.assertEqual([d.name for d in plan.decisions], [None, None])

    def test_5_user_may_prefer_partial_subtitles_and_forced_stays_untouched(self):
        tracks = [T('subtitles', 'eng', 'Full Subtitles', default=True, size=900),
                  T('subtitles', 'eng', 'Signs & Songs', forced=True, size=100)]
        path = self.media('a.mkv', tracks)
        p = self.pattern_for(path)
        # scope=none (3rd option, as the pair looks suspicious), no removal, default=2 (Signs & Songs),
        # order: default first, forced prompt: leave unchanged
        self.verify(p, '', '3', '', '2', '', '')
        tr.apply_plan(path, p)
        first, second = self.subs(path)
        self.assertEqual((first['name'], first['default'], first['forced']), ('Signs & Songs', True, True))
        self.assertEqual((second['name'], second['default']), ('Full Subtitles', False))

    def test_no_default_subtitle_can_be_chosen(self):
        path = self.media('a.mkv', [T('subtitles', 'eng', 'Full', default=True), T('subtitles', 'jpn', 'Signs')])
        p = self.pattern_for(path)
        self.verify(p, '', '2', '', '3', '2')
        tr.apply_plan(path, p)
        self.assertEqual([t['default'] for t in self.subs(path)], [False, False])

    def test_10_user_selected_track_is_removed(self):
        path = self.media('a.mkv', [T('audio', 'jpn', 'Japanese', default=True), T('subtitles', 'eng', 'Full', default=True),
                                    T('subtitles', 'jpn', 'Other')])
        p = self.pattern_for(path)
        # scope none, audio: no removal/default keep, subs: remove 2, default keep
        self.verify(p, '', '2', '', '1', '2', '1')
        self.assertEqual(tr.apply_plan(path, p)[0], 'changed')
        self.assertEqual([t['name'] for t in self.subs(path)], ['Full'])
        self.assertEqual(len(self.audio(path)), 1)

    def test_last_audio_track_cannot_be_removed(self):
        p = self.pattern_for(self.media('a.mkv', [T('audio', 'jpn', 'Japanese', default=True)]))
        self.verify(p, '', '2', '1', '', '1')

    @staticmethod
    def _ident(tracks):
        return {'tracks': [{'id': i, 'type': t['type'], 'codec': t['codec'], 'properties': {
            'language': t['lang'], 'language_ietf': t['ietf'], 'track_name': t['name'], 'default_track': t['default'],
            'forced_track': t['forced'], 'uid': t['uid'],
            **({'tag_number_of_bytes': str(t['size'])} if t['size'] else {})}} for i, t in enumerate(tracks)]}


class PatternTests(Base):
    STANDARD = lambda self: [T('audio', 'jpn', 'Japanese'), T('audio', 'eng', 'English'),  # noqa: E731
                             T('subtitles', 'eng', 'Full')]

    def test_6_identical_structure_groups_across_seasons(self):
        paths = [self.media(f'S0{s}E0{e}.mkv', self.STANDARD(), f'Season {s}') for s in (1, 2, 3) for e in (1, 2, 3)]
        patterns = tr.group_patterns([tr.scan_file(p) for p in paths])
        self.assertEqual(len(patterns), 1)
        self.assertEqual(len(patterns[0].files), 9)
        self.assertEqual(len({m.path.parent for m in patterns[0].files}), 3)

    def test_7_and_8_anomaly_in_the_middle_and_return_to_original(self):
        odd = [T('audio', 'jpn', 'Japanese'), T('audio', 'eng', 'English'), T('subtitles', 'eng', 'Full'),
               T('subtitles', 'eng', 'Extra')]
        paths = [self.media(f'E{e:02d}.mkv', odd if e in (9, 10) else self.STANDARD(), 'Season 3') for e in range(1, 25)]
        a, b = tr.group_patterns([tr.scan_file(p) for p in paths])
        self.assertEqual((len(a.files), len(b.files)), (22, 2))
        self.assertEqual({m.path.stem for m in b.files}, {'E09', 'E10'})
        self.assertIn('E11', {m.path.stem for m in a.files})

    def test_9_same_names_different_order_are_different_patterns(self):
        one = self.media('a.mkv', [T('subtitles', 'eng', 'English', size=1), T('subtitles', 'eng', 'English [CC]')])
        two = self.media('b.mkv', [T('subtitles', 'eng', 'English [CC]'), T('subtitles', 'eng', 'English', size=1)])
        self.assertEqual(len(tr.group_patterns([tr.scan_file(one), tr.scan_file(two)])), 2)

    def test_filenames_and_flags_matter_only_through_tracks(self):
        one = self.media('anything.mkv', [T('audio', 'jpn', 'Japanese', default=True)], 'x')
        two = self.media('else.mkv', [T('audio', 'jpn', 'Japanese', default=False)], 'y')
        self.assertEqual(len(tr.group_patterns([tr.scan_file(one), tr.scan_file(two)])), 2)

    def test_verified_pattern_is_applied_to_all_matches_and_deviation_is_left_alone(self):
        good = [self.media(f'E{e}.mkv', [T('audio', 'jpn', 'Japanese'), T('audio', 'eng', 'English', default=True)], f'S{e % 2}')
                for e in range(4)]
        odd = self.media('odd.mkv', [T('audio', 'eng', 'English', default=True), T('audio', 'jpn', 'Japanese')])
        a, b = tr.group_patterns([tr.scan_file(p) for p in good + [odd]])
        self.verify_single(a)
        self.assertEqual({tr.apply_plan(p, a)[0] for p in good}, {'changed'})
        self.assertEqual(self.audio(odd)[0]['default'], True)
        self.assertEqual(tr.pattern_status(b, [a, b]), 'not verified')

    def verify_single(self, pattern):
        self.answers = ['1', '', '', '1', '']  # pattern A, scope none, no removal, default Japanese, keep order
        tr._verify_menu([pattern], {})


class SafetyAndIdempotencyTests(Base):
    def setUp(self):
        super().setUp()
        self.path = self.media('a.mkv', [T('audio', 'jpn', 'Japanese'), T('audio', 'eng', 'English', default=True),
                                         T('subtitles', 'eng', 'Signs', default=True), T('subtitles', 'jpn', 'Full')])
        self.pattern = self.pattern_for(self.path)

    def plan_move_second_sub_first(self):
        # scope none, audio: no removal, default Japanese, order keep; subs: no removal, default 2 (default first)
        self.verify(self.pattern, '', '', '', '1', '', '', '2', '')

    def test_11_rerun_on_repaired_files_changes_nothing(self):
        self.plan_move_second_sub_first()
        self.assertEqual(tr.apply_plan(self.path, self.pattern)[0], 'changed')
        calls = len(self.fake.calls)
        self.assertEqual(tr.apply_plan(self.path, self.pattern)[0], 'unchanged')
        self.assertEqual([c[0] for c in self.fake.calls[calls:]], ['mkvmerge'])  # identify only
        repaired = tr.group_patterns([tr.scan_file(self.path)])[0]
        self.assertEqual(tr.pattern_status(repaired, [self.pattern, repaired]).split(' of ')[0], 'already matches the result')

    def test_12a_failed_remux_leaves_original_untouched(self):
        self.plan_move_second_sub_first()
        before = self.path.read_text(encoding='utf-8')
        self.fake.fail_remux = True
        self.assertEqual(tr.apply_plan(self.path, self.pattern)[0], 'failed')
        self.assertEqual(self.path.read_text(encoding='utf-8'), before)
        self.assertEqual(list(self.tmp.glob('*.tmp.mkv')), [])

    def test_12b_failed_edit_after_remux_keeps_original_and_removes_temp(self):
        self.plan_move_second_sub_first()
        before = self.path.read_text(encoding='utf-8')
        self.fake.fail_propedit = True
        self.assertEqual(tr.apply_plan(self.path, self.pattern)[0], 'failed')
        self.assertEqual(self.path.read_text(encoding='utf-8'), before)
        self.assertEqual(list(self.tmp.glob('*.tmp.mkv')), [])

    def test_12c_structure_changed_since_scan_is_skipped(self):
        self.plan_move_second_sub_first()
        self.fake.make(self.path, self.fake.state(self.path)[:-1])
        self.assertEqual(tr.apply_plan(self.path, self.pattern)[0], 'skipped')

    def test_unreadable_file_is_reported_not_raised(self):
        self.plan_move_second_sub_first()
        self.assertEqual(tr.apply_plan(self.tmp / 'missing.mkv', self.pattern)[0], 'failed')

    def test_changes_are_logged_with_original_values(self):
        self.plan_move_second_sub_first()
        tr.apply_plan(self.path, self.pattern)
        entry = json.loads((self.tmp / 'log.jsonl').read_text(encoding='utf-8').splitlines()[0])
        self.assertEqual(entry['before'][0]['lang'], 'jpn')
        self.assertTrue(entry['remux'])


class QuickRemovalTests(Base):
    def quick_file(self, name='q.mkv', folder=None):
        return self.media(name, [T('audio', 'jpn', 'Japanese', default=True), T('audio', 'eng', 'English'),
                                 T('subtitles', 'eng', 'Full Subtitles', default=True),
                                 T('subtitles', 'jpn', 'Full Subtitles')], folder)

    def layout(self, path):
        return [(t['type'], t['lang'], t['name'], t['default']) for t in self.fake.state(path) if t['type'] != 'video']

    def run_quick(self, *answers, root=None):
        self.answers = list(answers)
        tr.quick_removal(root or self.tmp)
        self.assertEqual(self.answers, [], 'unused scripted answers')

    def remux_calls(self):
        return [c for c in self.fake.calls if '-o' in c]

    def test_1_single_audio_track(self):
        path = self.quick_file()
        self.run_quick('2', '1', '2')
        self.assertEqual([t[1] for t in self.layout(path) if t[0] == 'audio'], ['jpn'])
        self.assertEqual(len([t for t in self.layout(path) if t[0] == 'subtitles']), 2)

    def test_2_single_subtitle_track(self):
        path = self.quick_file()
        self.run_quick('4', '1', '2')
        self.assertEqual([t[1] for t in self.layout(path) if t[0] == 'subtitles'], ['eng'])
        self.assertEqual(len([t for t in self.layout(path) if t[0] == 'audio']), 2)

    def test_3_multiple_tracks_in_one_operation(self):
        path = self.quick_file()
        self.run_quick('2,4', '1', '2')
        self.assertEqual([(t[0], t[1]) for t in self.layout(path)], [('audio', 'jpn'), ('subtitles', 'eng')])
        self.assertEqual(len(self.remux_calls()), 1)

    def test_4_all_subtitles_can_be_removed(self):
        path = self.quick_file()
        self.run_quick('3,4', '1', '2')
        self.assertEqual([t[0] for t in self.layout(path)], ['audio', 'audio'])

    def test_5_last_audio_track_cannot_be_removed(self):
        path = self.media('one.mkv', [T('audio', 'kor', 'Korean', default=True), T('subtitles', 'eng', 'Full')])
        before = self.layout(path)
        self.run_quick('1', '')  # rejected, then Enter at the new selection prompt cancels
        self.assertEqual(self.layout(path), before)
        self.assertEqual(self.remux_calls(), [])

    def test_5b_removing_every_audio_track_of_several_is_rejected(self):
        path = self.quick_file()
        before = self.layout(path)
        self.run_quick('1,2', '', root=self.tmp)
        self.assertEqual(self.layout(path), before)

    def test_6_cancel_leaves_the_file_unchanged(self):
        path = self.quick_file()
        before = self.layout(path)
        self.run_quick('')
        self.run_quick('2', '2')  # confirmation answered with Cancel
        self.assertEqual(self.layout(path), before)
        self.assertEqual(self.remux_calls(), [])

    def test_7_unselected_tracks_and_metadata_are_preserved(self):
        path = self.media('meta.mkv', [T('audio', 'jpn', 'Japanese', default=True), T('audio', 'eng', 'English'),
                                       T('subtitles', 'eng', 'Signs', forced=True),
                                       T('subtitles', 'eng', 'Full Subtitles'), T('subtitles', 'nld', 'Dutch')])
        self.run_quick('2', '1', '2')
        self.assertEqual([(t['type'], t['lang'], t['name'], t['default'], t['forced']) for t in self.fake.state(path)[1:]],
                         [('audio', 'jpn', 'Japanese', True, False), ('subtitles', 'eng', 'Signs', False, True),
                          ('subtitles', 'eng', 'Full Subtitles', False, False), ('subtitles', 'nld', 'Dutch', False, False)])
        self.assertEqual(self.fake.state(path)[0]['type'], 'video')

    def test_8_removed_default_audio_promotes_the_next_and_subtitles_get_no_default(self):
        path = self.quick_file()
        self.run_quick('1,3', '1', '2')
        self.assertEqual(self.layout(path), [('audio', 'eng', 'English', True), ('subtitles', 'jpn', 'Full Subtitles', False)])

    def test_8b_removing_a_non_default_track_changes_no_flags(self):
        path = self.quick_file()
        self.run_quick('4', '1', '2')
        self.assertEqual([t[3] for t in self.layout(path)], [True, False, True])

    def test_9_failed_remux_keeps_the_original_and_removes_temp(self):
        path = self.quick_file()
        before = self.layout(path)
        self.fake.fail_remux = True
        self.run_quick('2', '1')
        self.assertEqual(self.layout(path), before)
        self.assertEqual(list(self.tmp.glob('*.tmp.mkv')), [])

    def test_9b_output_failing_validation_keeps_the_original(self):
        path = self.quick_file()
        before = self.layout(path)
        with mock.patch.object(tr.utils, 'check_remux_result', return_value='audio tracks do not match the expected selection'):
            self.run_quick('2', '1')
        self.assertEqual(self.layout(path), before)
        self.assertEqual(list(self.tmp.glob('*.tmp.mkv')), [])

    def test_changed_source_is_rejected(self):
        path = self.quick_file()
        uids = [t.uid for t in tr.scan_file(path).tracks]
        self.fake.make(path, self.fake.state(path)[:-1])
        self.assertEqual(tr.remove_tracks(path, uids, {uids[0]})[0], 'failed')

    def test_multiple_files_show_a_list_and_can_process_another(self):
        a, b = self.quick_file('a.mkv'), self.quick_file('b.mkv')
        self.run_quick('2', '2', '1', '1', '3')  # file b, track 2, yes, process another, Back
        self.assertEqual(len([t for t in self.layout(b) if t[0] == 'audio']), 1)
        self.assertEqual(len([t for t in self.layout(a) if t[0] == 'audio']), 2)

    def test_10_menu_returns_and_dispatches(self):
        path = self.quick_file()
        self.answers = ['2', '2', '1', '2', '4']  # Quick Removal, remove track 2, yes, return to menu, return to Extra Tools
        tr._main_menu(self.tmp)
        self.assertEqual(self.answers, [])
        self.assertEqual(len([t for t in self.layout(path) if t[0] == 'audio']), 1)
        with mock.patch.object(tr, '_session') as session:
            self.answers = ['1', '4']
            tr._main_menu(self.tmp)
        session.assert_called_once()
        self.answers = ['4']
        tr._main_menu(self.tmp)
        self.assertEqual(self.answers, [])


class DefaultAudioTests(Base):
    def audio_file(self, name='d.mkv', defaults=(True, False)):
        return self.media(name, [T('audio', 'jpn', 'Japanese', default=defaults[0]), T('audio', 'eng', 'English', default=defaults[1]),
                                 T('subtitles', 'eng', 'Full Subtitles', default=True)])

    def flags(self, path):
        return [(t['type'], t['lang'], t['default']) for t in self.fake.state(path) if t['type'] != 'video']

    def run_default(self, *answers):
        self.answers = list(answers)
        tr.change_default_audio(self.tmp)
        self.assertEqual(self.answers, [], 'unused scripted answers')

    def test_default_moves_to_the_chosen_audio_track_without_a_remux(self):
        path = self.audio_file()
        self.run_default('2', '1', '2')
        self.assertEqual(self.flags(path), [('audio', 'jpn', False), ('audio', 'eng', True), ('subtitles', 'eng', True)])
        self.assertEqual([c for c in self.fake.calls if '-o' in c], [])

    def test_conflicting_defaults_are_resolved_to_one(self):
        path = self.audio_file(defaults=(True, True))
        self.run_default('1', '1', '2')
        self.assertEqual([t[2] for t in self.flags(path) if t[0] == 'audio'], [True, False])

    def test_cancel_and_already_default_leave_the_file_unchanged(self):
        path = self.audio_file()
        before = self.flags(path)
        self.run_default('')
        self.run_default('2', '2')
        self.run_default('1', '')  # already default, then cancel
        self.assertEqual(self.flags(path), before)

    def test_single_audio_track_has_nothing_to_choose(self):
        path = self.media('one.mkv', [T('audio', 'jpn', 'Japanese', default=True)])
        self.run_default()
        self.assertEqual(self.flags(path), [('audio', 'jpn', True)])

    def test_failed_edit_is_reported_and_changed_source_rejected(self):
        path = self.audio_file()
        before = self.flags(path)
        self.fake.fail_propedit = True
        self.run_default('2', '1')
        self.assertEqual(self.flags(path), before)
        self.fake.fail_propedit = False
        uids = [t.uid for t in tr.scan_file(path).tracks]
        self.fake.make(path, self.fake.state(path)[:-1])
        self.assertEqual(tr.set_default_audio(path, uids, uids[2])[0], 'failed')

    def test_menu_option_3_opens_the_default_audio_flow(self):
        path = self.audio_file()
        self.answers = ['3', '2', '1', '2', '4']
        tr._main_menu(self.tmp)
        self.assertEqual(self.answers, [])
        self.assertTrue(self.flags(path)[1][2])


@unittest.skipUnless(shutil.which('mkvmerge') and shutil.which('mkvpropedit') and shutil.which('ffmpeg'),
                     'MKVToolNix and ffmpeg are required')
class RealToolsTest(unittest.TestCase):
    def test_real_quick_removal_with_default_handling(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        for n, text in (('s1', 'Hello'), ('s2', 'Sign')):
            (tmp / f'{n}.srt').write_text(f"1\n00:00:00,000 --> 00:00:00,500\n{text}\n", encoding='utf-8')
        path = tmp / 'quick.mkv'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=64x64:d=1:r=10',
                        '-f', 'lavfi', '-i', 'sine=d=1', '-f', 'lavfi', '-i', 'sine=f=880:d=1',
                        '-i', str(tmp / 's1.srt'), '-i', str(tmp / 's2.srt'),
                        '-map', '0', '-map', '1', '-map', '2', '-map', '3', '-map', '4', '-c:v', 'mpeg4', '-c:a', 'aac',
                        '-c:s', 'srt', '-metadata:s:a:0', 'language=jpn', '-metadata:s:a:1', 'language=eng',
                        '-metadata:s:s:0', 'language=eng', '-metadata:s:s:0', 'title=Signs & Songs',
                        '-metadata:s:s:1', 'language=jpn', '-metadata:s:s:1', 'title=Full Subtitles',
                        '-disposition:a:0', '0', '-disposition:a:1', 'default', '-disposition:s:0', 'default',
                        '-disposition:s:1', '0', str(path)], check=True)
        media = tr.scan_file(path)
        removed = {t.uid for t in media.tracks if (t.type, t.lang) in (('audio', 'eng'), ('subtitles', 'eng'))}
        self.assertEqual(len(removed), 2)
        status, message, n_removed, n_kept = tr.remove_tracks(path, [t.uid for t in media.tracks], removed)
        self.assertEqual((status, n_removed, n_kept), ('removed', 2, 2), message)
        self.assertEqual([(t.type, t.lang, t.name, t.default) for t in tr.scan_file(path).tracks],
                         [('audio', 'jpn', '', True), ('subtitles', 'jpn', 'Full Subtitles', False)])
        self.assertEqual(list(tmp.glob('*.tmp.mkv')), [])


@unittest.skipUnless(shutil.which('mkvmerge') and shutil.which('mkvpropedit') and shutil.which('ffmpeg'),
                     'MKVToolNix and ffmpeg are required')
class RealToolsRepairTest(unittest.TestCase):
    def test_real_remux_reorder_remove_and_metadata(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        for n, text in (('s1', 'Hello'), ('s2', 'Sign')):
            (tmp / f'{n}.srt').write_text(f"1\n00:00:00,000 --> 00:00:00,500\n{text}\n", encoding='utf-8')
        path = tmp / 'sample.mkv'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=64x64:d=1:r=10',
                        '-f', 'lavfi', '-i', 'sine=d=1', '-f', 'lavfi', '-i', 'sine=f=880:d=1',
                        '-i', str(tmp / 's1.srt'), '-i', str(tmp / 's2.srt'),
                        '-map', '0', '-map', '1', '-map', '2', '-map', '3', '-map', '4', '-c:v', 'mpeg4', '-c:a', 'aac',
                        '-c:s', 'srt', '-metadata:s:a:0', 'language=jpn', '-metadata:s:a:1', 'language=eng',
                        '-metadata:s:s:0', 'language=eng', '-metadata:s:s:0', 'title=Signs & Songs',
                        '-metadata:s:s:1', 'language=jpn', '-metadata:s:s:1', 'title=Full Subtitles',
                        '-disposition:a:1', 'default', '-disposition:s:0', 'default', str(path)], check=True)
        media = tr.scan_file(path)
        audio_jpn = next(t for t in media.tracks if t.type == 'audio' and t.lang == 'jpn')
        self.assertTrue(audio_jpn.lang_ok)
        pattern = tr.group_patterns([media])[0]
        decisions = [tr.Decision(t.lang, tr._purpose_hint(t.name), None, t.default, t.forced) for t in media.tracks]
        a_jpn, a_eng, s_signs, s_full = range(4)
        decisions[a_jpn].default, decisions[a_eng].default = True, False
        decisions[s_full].lang, decisions[s_full].purpose = 'eng', 'full'
        decisions[s_full].name = 'English - Full Subtitles'
        decisions[s_full].default, decisions[s_signs].default = True, False
        pattern.plan = tr.Plan(decisions, [a_jpn, s_full])  # reorder + remove English audio and Signs & Songs
        self.assertEqual(tr.apply_plan(path, pattern)[0], 'changed')
        result = tr.scan_file(path)
        self.assertEqual([(t.type, t.lang, t.name, t.default) for t in result.tracks],
                         [('audio', 'jpn', '', True), ('subtitles', 'eng', 'English - Full Subtitles', True)])
        self.assertEqual(tr.apply_plan(path, pattern)[0], 'unchanged')
        self.assertEqual(list(tmp.glob('*.tmp.mkv')), [])


if __name__ == '__main__':
    unittest.main()

