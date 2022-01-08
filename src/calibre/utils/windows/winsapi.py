#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from calibre_extensions.winsapi import ISpVoice


def develop():
    spv = ISpVoice()
    spv.create_recording_wav('test.wav', 'Hello, world!')


def find_tests():
    import unittest
    import os
    is_ci = os.environ.get('CI', '').lower() == 'true'

    class TestSAPI(unittest.TestCase):

        def setUp(self):
            self.sapi = ISpVoice()

        def tearDown(self):
            self.sapi = None

        def test_enumeration_of_voices(self):
            default_voice = self.sapi.get_current_voice()
            self.assertTrue(default_voice)
            all_voices = self.sapi.get_all_voices()
            self.assertTrue(all_voices)
            self.assertIn(default_voice, {x['id'] for x in all_voices})
            for voice in all_voices:
                for key in ('name', 'gender', 'age', 'language', 'description'):
                    self.assertIn(key, voice)
                self.sapi.set_current_voice(voice['id'])
                self.assertEqual(self.sapi.get_current_voice(), voice['id'])
            self.sapi.set_current_voice()
            self.assertEqual(self.sapi.get_current_voice(), default_voice)

        @unittest.skipIf(is_ci, 'No sound output on CI')
        def test_enumeration_of_sound_outputs(self):
            default_output = self.sapi.get_current_sound_output()
            self.assertTrue(default_output)
            all_outputs = self.sapi.get_all_sound_outputs()
            self.assertTrue(all_outputs)
            self.assertIn(default_output, {x['id'] for x in all_outputs})
            for output in all_outputs:
                for key in ('id', 'description',):
                    self.assertIn(key, output)
                self.sapi.set_current_voice(output['id'])
                self.assertEqual(self.sapi.get_current_sound_output(), output['id'])
            self.sapi.set_current_sound_output()
            self.assertEqual(self.sapi.get_current_sound_output(), default_output)

        def test_volume_and_rate(self):
            dr = self.sapi.get_current_rate()
            new_rate = dr // 2 + 1
            self.sapi.set_current_rate(new_rate)
            self.assertEqual(self.sapi.get_current_rate(), new_rate)
            self.sapi.set_current_rate(dr)

            dv = self.sapi.get_current_volume()
            new_vol = dv // 2 + 3
            self.sapi.set_current_volume(new_vol)
            self.assertEqual(self.sapi.get_current_volume(), new_vol)
            self.sapi.set_current_volume(dv)

        def test_record_as_audio_file(self):
            import tempfile
            with tempfile.TemporaryDirectory() as tdir:
                wav_path = os.path.join(tdir, 'test.wav')
                self.sapi.create_recording_wav(wav_path, 'testing microsoft voices')
                self.assertGreater(os.path.getsize(wav_path), 256)

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestSAPI)


def run_tests():
    from calibre.utils.run_tests import run_tests
    run_tests(find_tests)
