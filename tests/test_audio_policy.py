"""Regression tests for original-audio preservation and remux validation (shared helpers in utils.py).

extraction.py cannot be imported (side effects), so its policy lives in utils.select_audio_tracks and is tested here.
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import utils  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG = {'jpn', 'eng', 'nld'}


def A(tid, lang, default=False, name=''):
    return {'id': str(tid), 'lang': lang, 'default': default, 'name': name}


def keep(tracks, config=CONFIG):
    ids, _ = utils.select_audio_tracks(tracks, lambda lang: lang in config)
    return [t['lang'] for t in tracks if t['id'] in ids]


class AudioPolicyTests(unittest.TestCase):
    def test_1_single_korean_track_is_kept_when_korean_is_not_configured(self):
        self.assertEqual(keep([A(1, 'kor', True)]), ['kor'])

    def test_2_norwegian_default_with_english_and_german(self):
        tracks = [A(1, 'nor', True), A(2, 'eng'), A(3, 'deu')]
        self.assertEqual(keep(tracks), ['nor', 'eng'])

    def test_3_english_dub_default_keeps_a_plausible_norwegian_original(self):
        self.assertEqual(keep([A(1, 'nor'), A(2, 'eng', True)]), ['nor', 'eng'])
        self.assertEqual(keep([A(1, 'eng', True), A(2, 'nor')]), ['eng', 'nor'])

    def test_4_single_undefined_track(self):
        self.assertEqual(keep([A(1, 'und')]), ['und'])

    def test_5_several_tracks_without_default_are_all_kept(self):
        self.assertEqual(keep([A(1, 'fra'), A(2, 'deu'), A(3, 'eng')]), ['fra', 'deu', 'eng'])

    def test_6_conflicting_defaults_are_all_kept(self):
        self.assertEqual(keep([A(1, 'fra', True), A(2, 'deu', True), A(3, 'spa')]), ['fra', 'deu', 'spa'])

    def test_french_default_with_english(self):
        self.assertEqual(keep([A(1, 'fra', True), A(2, 'eng')]), ['fra', 'eng'])

    def test_japanese_only_and_english_only(self):
        self.assertEqual(keep([A(1, 'jpn', True)]), ['jpn'])
        self.assertEqual(keep([A(1, 'eng', True)]), ['eng'])

    def test_commentary_in_other_language_can_be_removed(self):
        tracks = [A(1, 'kor', True), A(2, 'deu', name='Director Commentary'), A(3, 'eng')]
        self.assertEqual(keep(tracks), ['kor', 'eng'])

    def test_track_named_original_is_protected(self):
        tracks = [A(1, 'eng', True), A(2, 'kor', name='Original'), A(3, 'deu'), A(4, 'nld')]
        self.assertIn('kor', keep(tracks))

    def test_7_filename_is_never_an_input(self):
        # Root cause of the Hope (2026) bug: 'AC3' matched inside 'EAC3' in the filename.
        source = (ROOT / 'extraction.py').read_text(encoding='utf-8')
        self.assertNotIn('multi_lang_indicators', source)
        self.assertNotIn('is_multi_lang_release', source)
        self.assertEqual(keep([A(1, 'kor', True)]), ['kor'])  # same result whatever the file is called

    def test_8_priority_does_not_override_a_valid_original_default(self):
        self.assertEqual(utils.resolve_audio_default(['2', '1'], ['1'], '2'), '1')
        self.assertEqual(utils.resolve_audio_default(['2', '1'], [], '2'), '2')
        self.assertEqual(utils.resolve_audio_default(['2', '1'], ['1', '2'], '2'), '2')   # conflicting defaults
        self.assertEqual(utils.resolve_audio_default(['2'], ['1'], '2'), '2')             # default track was removed

    def test_9_never_results_in_zero_audio_tracks(self):
        for tracks in ([A(1, 'kor')], [A(1, 'kor', name='Commentary'), A(2, 'deu', name='Commentary')],
                       [A(1, 'und')], [A(1, 'kor', True), A(2, 'zho', True)]):
            self.assertTrue(keep(tracks), tracks)

    def test_all_tracks_commentary_still_keeps_first(self):
        self.assertEqual(keep([A(1, 'kor', name='Commentary'), A(2, 'deu', name='Commentary')]), ['kor'])


def _info(audio_langs=('kor',), subs=1, chapters=0, attachments=0, recognized=True):
    tracks = [{'id': 0, 'type': 'video', 'properties': {}}]
    tracks += [{'id': i + 1, 'type': 'audio', 'properties': {'language': lang}} for i, lang in enumerate(audio_langs)]
    base = 1 + len(audio_langs)
    tracks += [{'id': base + i, 'type': 'subtitles', 'properties': {'language': 'eng'}} for i in range(subs)]
    return {'container': {'recognized': recognized}, 'tracks': tracks,
            'chapters': [{'num_entries': chapters}] if chapters else [], 'attachments': [{}] * attachments}


class RemuxValidationTests(unittest.TestCase):
    def check(self, src, out, audio, subs):
        return utils.check_remux_result(src, out, audio, subs)

    def test_correct_output_is_accepted(self):
        src = _info(('kor', 'eng', 'deu'), subs=2, chapters=3, attachments=1)
        out = _info(('kor', 'eng'), subs=1, chapters=3, attachments=1)
        self.assertIsNone(self.check(src, out, ['1', '2'], ['4']))

    def test_10_output_that_lost_the_protected_audio_is_rejected(self):
        src = _info(('kor', 'eng'))
        self.assertIn('audio', self.check(src, _info(('eng',)), ['1', '2'], ['3']))
        self.assertIn('audio', self.check(src, _info(()), ['1', '2'], ['3']))

    def test_selection_without_any_audio_is_rejected_when_source_has_audio(self):
        self.assertIn('no audio', self.check(_info(('kor',)), _info(()), [], ['2']))

    def test_unreadable_output_chapter_and_attachment_loss_are_rejected(self):
        src = _info(('kor',), chapters=2, attachments=1)
        self.assertIsNotNone(self.check(src, _info(('kor',), recognized=False), ['1'], ['2']))
        self.assertIn('chapters', self.check(src, _info(('kor',), attachments=1), ['1'], ['2']))
        self.assertIn('attachments', self.check(src, _info(('kor',), chapters=2), ['1'], ['2']))

    def test_missing_video_or_subtitles_are_rejected(self):
        src = _info(('kor',), subs=1)
        out = _info(('kor',), subs=0)
        self.assertIn('subtitle', self.check(src, out, ['1'], ['2']))
        out['tracks'] = [t for t in out['tracks'] if t['type'] != 'video']
        self.assertIn('video', self.check(src, out, ['1'], []))


class CommitRemuxTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(self.dir, True))

    def test_same_name_replaces_original(self):
        original, temp = self.dir / 'a.mkv', self.dir / 'a.temp.mkv'
        original.write_text('old'), temp.write_text('new')
        utils.commit_remux(temp, original, original)
        self.assertEqual(original.read_text(), 'new')
        self.assertFalse(temp.exists())

    def test_conversion_to_mkv_removes_the_old_container_only_after_the_new_file_exists(self):
        original, temp, final = self.dir / 'a.avi', self.dir / 'a.temp.mkv', self.dir / 'a.mkv'
        original.write_text('old'), temp.write_text('new')
        utils.commit_remux(temp, original, final)
        self.assertEqual(final.read_text(), 'new')
        self.assertFalse(original.exists())

    def test_failed_replace_keeps_the_original(self):
        original = self.dir / 'a.mkv'
        original.write_text('old')
        with self.assertRaises(OSError):
            utils.commit_remux(self.dir / 'missing.temp.mkv', original, original)
        self.assertEqual(original.read_text(), 'old')


if __name__ == '__main__':
    unittest.main()
