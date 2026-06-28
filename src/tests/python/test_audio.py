#
# test_audio.py - Python module audio protocol tests
#
# Copyright (C) 2026 Jean-François David
#
# This is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import io
import sys
import unittest

from speechd_python_modules import speechd_types
from speechd_python_modules import module_process
from speechd_python_modules.module_process import (
    cmd_audio,
    module_tts_output_send_server,
    module_tts_output_server,
)


class FakeStdout:
    def __init__(self):
        self.chunks = []
        self.buffer = self

    def write(self, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.chunks.append(data)
        return len(data)

    def flush(self):
        pass

    def value(self):
        return b"".join(self.chunks)


class AudioTest(unittest.TestCase):
    def setUp(self):
        self.old_stdin = sys.stdin
        self.old_stdout = sys.stdout
        module_process._audio_server = False

    def tearDown(self):
        sys.stdin = self.old_stdin
        sys.stdout = self.old_stdout
        module_process._audio_server = False

    def run_audio_command(self, module, script):
        stdout = io.StringIO()
        sys.stdin = io.StringIO(script)
        sys.stdout = stdout
        cmd_audio(module)
        return stdout.getvalue()

    def test_audio_command_requires_explicit_server_mode(self):
        self.assertEqual(
            self.run_audio_command(object(), "audio_output_method=server\n.\n"),
            "207 OK RECEIVING AUDIO SETTINGS\n"
            "303 ERROR INVALID PARAMETER OR VALUE\n",
        )

    def test_audio_command_uses_local_callbacks(self):
        class LocalAudioModule:
            def __init__(self):
                self.initialized = False
                self.settings = []

            def module_audio_set(self, var, val):
                self.settings.append((var, val))
                if var == "audio_output_method" and val == "pulse":
                    return 0
                if var == "audio_pulse_device":
                    return 0
                return -1

            def module_audio_init(self):
                self.initialized = True
                return 0

        module = LocalAudioModule()

        output = self.run_audio_command(
            module,
            "audio_output_method=pulse\n"
            "audio_pulse_device=default\n"
            ".\n",
        )

        self.assertEqual(
            output,
            "207 OK RECEIVING AUDIO SETTINGS\n"
            "203 OK AUDIO INITIALIZED\n",
        )
        self.assertEqual(
            module.settings,
            [
                ("audio_output_method", "pulse"),
                ("audio_pulse_device", "default"),
            ],
        )
        self.assertTrue(module.initialized)

    def test_audio_command_rejects_local_output(self):
        output = self.run_audio_command(object(), "audio_output_method=pulse\n.\n")

        self.assertEqual(
            output,
            "207 OK RECEIVING AUDIO SETTINGS\n"
            "303 ERROR INVALID PARAMETER OR VALUE\n",
        )
        self.assertNotIn("203 OK AUDIO INITIALIZED", output)

    def track(self, bits=16, num_channels=1, num_samples=1, samples=b"\0\0"):
        return speechd_types.AudioTrack(
            bits=bits,
            num_channels=num_channels,
            sample_rate=24000,
            num_samples=num_samples,
            samples=samples,
        )

    def test_audio_output_send_server_uses_computed_payload_size(self):
        audio_track = self.track(
            num_samples=1,
            samples=b"\x01\x00extra",
        )
        stdout = FakeStdout()
        sys.stdout = stdout

        module_tts_output_send_server(audio_track, speechd_types.SPD_AUDIO_LE)

        output = stdout.value()
        self.assertIn(b"705-num_samples=1\n", output)
        self.assertIn(b"705-AUDIO\0\x01\x00\n705 AUDIO\n", output)
        self.assertNotIn(b"extra", output)

    def test_audio_output_send_server_prints_format_value(self):
        audio_track = self.track()
        stdout = FakeStdout()
        sys.stdout = stdout

        module_tts_output_send_server(audio_track, 99)

        self.assertIn(b"705-big_endian=99\n", stdout.value())

    def test_audio_track_chunking(self):
        samples = b"\x01\x00" * 6001
        audio_track = speechd_types.AudioTrack(
            bits=16,
            num_channels=1,
            sample_rate=24000,
            num_samples=6001,
            samples=samples,
        )
        stdout = FakeStdout()
        sys.stdout = stdout

        module_tts_output_server(audio_track, speechd_types.SPD_AUDIO_LE)

        output = stdout.value()
        self.assertEqual(len(stdout.chunks), 2)
        self.assertEqual(output.count(b"705-AUDIO\0"), 2)
        self.assertEqual(output.count(b"\n705 AUDIO\n"), 2)
        self.assertIn(b"705-num_samples=5000\n", output)
        self.assertIn(b"705-num_samples=1001\n", output)

        first = output.find(b"705-num_samples=5000\n")
        second = output.find(b"705-num_samples=1001\n")
        self.assertLess(first, second)


if __name__ == "__main__":
    unittest.main()
