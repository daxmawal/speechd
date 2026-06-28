#
# test_module_process.py - Python module_process protocol tests
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
import os
import sys
import unittest

from speechd_python_modules import module_main, module_process, module_utils, speechd_types
from speechd_python_modules.module_process import (
    module_audio_set_server,
    module_report_event_begin,
    module_report_event_end,
    module_speak_ok,
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


class ScriptedStdin:
    def __init__(self, data):
        self.read_fd, write_fd = os.pipe()
        os.write(write_fd, data.encode("utf-8"))
        os.close(write_fd)

    def fileno(self):
        return self.read_fd

    def close(self):
        os.close(self.read_fd)


class ModuleProcessTest(unittest.TestCase):
    def setUp(self):
        self.old_stdin = sys.stdin
        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr
        module_process._audio_server = False
        module_utils.log_level = 0

    def tearDown(self):
        sys.stdin = self.old_stdin
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr
        module_process._audio_server = False
        module_utils.log_level = 0

    def run_main(self, module, script, stdout=None):
        stdout = io.StringIO() if stdout is None else stdout
        stderr = io.StringIO()
        sys.stdin = io.StringIO(script)
        sys.stdout = stdout
        sys.stderr = stderr

        ret = module_main.run_main(lambda _path: {}, lambda _config: module, ["fake-module"])
        return ret, stdout, stderr

    def test_speak_sync_error_protocol(self):
        class FailingSpeakModule:
            def __init__(self):
                self.closed = False
                self.spoken = []

            def module_init(self):
                return "fake initialized"

            def module_speak_sync(self, text, text_len, msgtype):
                self.spoken.append((text, text_len, msgtype))
                raise RuntimeError("speak failed")

            def module_close(self):
                self.closed = True

        module = FailingSpeakModule()

        ret, stdout, stderr = self.run_main(
            module,
            "INIT\nSPEAK\nHello\n.\nQUIT\n",
        )

        output = stdout.getvalue()
        for needle in (
            "299-fake initialized\n",
            "299 OK LOADED SUCCESSFULLY\n",
            "202 OK RECEIVING MESSAGE\n",
            "301 ERROR CANT SPEAK\n",
            "210 OK QUIT\n",
        ):
            self.assertIn(needle, output)
        self.assertNotIn("Traceback", output)
        self.assertNotIn("399 ERR MODULE CLOSED", output)
        self.assertEqual(ret, 0)
        self.assertTrue(module.closed)
        self.assertEqual(module.spoken, [("Hello", 5, speechd_types.SPD_MSGTYPE_TEXT)])
        self.assertIn("Traceback", stderr.getvalue())
        self.assertIn("RuntimeError: speak failed", stderr.getvalue())

    def test_speak_async_error_protocol(self):
        class FailingAsyncSpeakModule:
            def __init__(self):
                self.closed = False
                self.spoken = []

            def module_init(self):
                return "fake initialized"

            def module_speak(self, text, text_len, msgtype):
                self.spoken.append((text, text_len, msgtype))
                raise RuntimeError("async speak failed")

            def module_close(self):
                self.closed = True

        module = FailingAsyncSpeakModule()

        ret, stdout, stderr = self.run_main(
            module,
            "INIT\nSPEAK\nHello\n.\nQUIT\n",
        )

        output = stdout.getvalue()
        for needle in (
            "299-fake initialized\n",
            "299 OK LOADED SUCCESSFULLY\n",
            "202 OK RECEIVING MESSAGE\n",
            "301 ERROR CANT SPEAK\n",
            "210 OK QUIT\n",
        ):
            self.assertIn(needle, output)
        self.assertNotIn("Traceback", output)
        self.assertNotIn("399 ERR MODULE CLOSED", output)
        self.assertEqual(ret, 0)
        self.assertTrue(module.closed)
        self.assertEqual(module.spoken, [("Hello", 5, speechd_types.SPD_MSGTYPE_TEXT)])
        self.assertIn("Traceback", stderr.getvalue())
        self.assertIn("RuntimeError: async speak failed", stderr.getvalue())

    def test_missing_set_callback_protocol(self):
        class MinimalModule:
            def __init__(self):
                self.closed = False

            def module_init(self):
                return "fake initialized"

            def module_close(self):
                self.closed = True

        module = MinimalModule()

        ret, stdout, stderr = self.run_main(
            module,
            "INIT\n"
            "SET\n"
            "voice=fake\n"
            ".\n"
            "QUIT\n",
        )

        self.assertEqual(
            stdout.getvalue(),
            "299-fake initialized\n"
            "299 OK LOADED SUCCESSFULLY\n"
            "203 OK RECEIVING SETTINGS\n"
            "303 ERROR INVALID PARAMETER OR VALUE\n"
            "210 OK QUIT\n",
        )
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(ret, 0)
        self.assertTrue(module.closed)

    def test_backend_callback_error_protocol(self):
        class FailingCallbackModule:
            def __init__(self):
                self.closed = False
                self.settings = []

            def module_init(self):
                return "fake initialized"

            def module_list_voices(self):
                raise RuntimeError("list voices failed")

            def module_set(self, var, val):
                self.settings.append((var, val))
                raise RuntimeError("set failed")

            def module_close(self):
                self.closed = True
                raise RuntimeError("close failed")

        module = FailingCallbackModule()

        ret, stdout, stderr = self.run_main(
            module,
            "INIT\n"
            "LIST VOICES\n"
            "SET\n"
            "voice=fake\n"
            ".\n"
            "QUIT\n",
        )

        self.assertEqual(
            stdout.getvalue(),
            "299-fake initialized\n"
            "299 OK LOADED SUCCESSFULLY\n"
            "304 CANT LIST VOICES\n"
            "203 OK RECEIVING SETTINGS\n"
            "303 ERROR INVALID PARAMETER OR VALUE\n"
            "210 OK QUIT\n",
        )
        self.assertNotIn("Traceback", stdout.getvalue())
        self.assertNotIn("399 ERR MODULE CLOSED", stdout.getvalue())
        self.assertEqual(ret, 0)
        self.assertTrue(module.closed)
        self.assertEqual(module.settings, [("voice", "fake")])
        for needle in (
            "RuntimeError: list voices failed",
            "RuntimeError: set failed",
            "RuntimeError: close failed",
        ):
            self.assertIn(needle, stderr.getvalue())

    def test_speak_reports_byte_length(self):
        class RecordingModule:
            def __init__(self):
                self.closed = False
                self.spoken = []

            def module_init(self):
                return "fake initialized"

            def module_speak_sync(self, text, text_len, msgtype):
                self.spoken.append((text, text_len, msgtype))
                module_speak_ok()

            def module_close(self):
                self.closed = True

        text = "caf\u00e9"
        expected_len = len(text.encode("utf-8"))
        self.assertNotEqual(len(text), expected_len)
        module = RecordingModule()

        ret, stdout, _stderr = self.run_main(
            module,
            "INIT\nSPEAK\n" + text + "\n.\nQUIT\n",
        )

        self.assertEqual(ret, 0)
        self.assertTrue(module.closed)
        self.assertEqual(
            module.spoken,
            [(text, expected_len, speechd_types.SPD_MSGTYPE_TEXT)],
        )
        self.assertIn("200 OK SPEAKING\n", stdout.getvalue())

    def test_module_process_reads_supplied_fd(self):
        class RecordingModule:
            def __init__(self):
                self.closed = False
                self.spoken = []

            def module_speak_sync(self, text, text_len, msgtype):
                self.spoken.append((text, text_len, msgtype))
                module_speak_ok()

            def module_close(self):
                self.closed = True

        module = RecordingModule()
        stdout = io.StringIO()
        sys.stdin = io.StringIO("QUIT\n")
        sys.stdout = stdout

        read_fd, write_fd = os.pipe()
        try:
            ret = module_process.module_process(module, fd=read_fd, block=False)
        finally:
            os.close(read_fd)
            os.close(write_fd)

        self.assertEqual(ret, -1)
        self.assertFalse(module.closed)
        self.assertEqual(stdout.getvalue(), "")

        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, "SPEAK\ncaf\u00e9\n.\nQUIT\n".encode("utf-8"))
            os.close(write_fd)
            write_fd = None
            ret = module_process.module_process(module, fd=read_fd, block=True)
        finally:
            os.close(read_fd)
            if write_fd is not None:
                os.close(write_fd)

        self.assertEqual(ret, 0)
        self.assertTrue(module.closed)
        self.assertEqual(module.spoken, [("caf\u00e9", 5, speechd_types.SPD_MSGTYPE_TEXT)])
        self.assertEqual(
            stdout.getvalue(),
            "202 OK RECEIVING MESSAGE\n"
            "200 OK SPEAKING\n"
            "210 OK QUIT\n",
        )

    def test_fake_module_protocol(self):
        class FakeModule:
            def __init__(self):
                self.settings = {}
                self.spoken = []
                self.closed = False

            def module_init(self):
                module_audio_set_server()
                return "fake initialized"

            def module_list_voices(self):
                return [
                    speechd_types.SPDVoice("fake-fr", "fr", "FEMALE1"),
                    speechd_types.SPDVoice("fake-en", "en-US", "MALE1"),
                ]

            def module_set(self, var, val):
                self.settings[var] = val
                return 0

            def module_speak_sync(self, text, text_len, msgtype):
                self.spoken.append((text, text_len, msgtype))
                module_speak_ok()
                module_report_event_begin()
                module_tts_output_server(
                    speechd_types.AudioTrack(
                        bits=16,
                        num_channels=1,
                        sample_rate=24000,
                        num_samples=4,
                        samples=b"\x00\x00\x0a\x00\x7d\x00\x01\x00",
                    ),
                    speechd_types.SPD_AUDIO_LE,
                )
                module_report_event_end()

            def module_close(self):
                self.closed = True
                return 0

        script = (
            "INIT\n"
            "LIST VOICES\n"
            "SET\n"
            "voice=fake-fr\n"
            "rate=10\n"
            ".\n"
            "AUDIO\n"
            "audio_output_method=server\n"
            ".\n"
            "LOGLEVEL\n"
            "log_level=4\n"
            ".\n"
            "SPEAK\n"
            "Hello\n"
            ".\n"
            "CHAR\n"
            "space\n"
            ".\n"
            "KEY\n"
            "Enter\n"
            ".\n"
            "QUIT\n"
        )
        fake = FakeModule()
        stdin = ScriptedStdin(script)
        stdout = FakeStdout()
        sys.stdin = stdin
        sys.stdout = stdout
        try:
            ret = module_main.run_main(
                lambda _path: {},
                lambda _config: fake,
                ["fake-module"],
            )
        finally:
            stdin.close()

        self.assertEqual(ret, 0)
        self.assertTrue(fake.closed)
        self.assertEqual(fake.settings, {"voice": "fake-fr", "rate": "10"})
        self.assertEqual(module_utils.log_level, 4)
        self.assertEqual(
            fake.spoken,
            [
                ("Hello", 5, speechd_types.SPD_MSGTYPE_TEXT),
                (" ", 1, speechd_types.SPD_MSGTYPE_CHAR),
                ("Enter", 5, speechd_types.SPD_MSGTYPE_KEY),
            ],
        )

        output = stdout.value()
        for needle in (
            b"299-fake initialized\n",
            b"299 OK LOADED SUCCESSFULLY\n",
            b"200-fake-fr\tfr\tFEMALE1\n",
            b"200-fake-en\ten-US\tMALE1\n",
            b"200 OK VOICE LIST SENT\n",
            b"203 OK SETTINGS RECEIVED\n",
            b"203 OK AUDIO INITIALIZED\n",
            b"203 OK LOGLEVEL SET\n",
            b"210 OK QUIT\n",
        ):
            self.assertIn(needle, output)

        audio_event = (
            b"705-bits=16\n"
            b"705-num_channels=1\n"
            b"705-sample_rate=24000\n"
            b"705-num_samples=4\n"
            b"705-big_endian=0\n"
            b"705-AUDIO\0"
            b"\x00\x00\x7d\x2a\x00\x7d\x5d\x00\x01\x00"
            b"\n705 AUDIO\n"
        )
        speech_event = b"200 OK SPEAKING\n701 BEGIN\n" + audio_event + b"702 END\n"
        self.assertEqual(output.count(speech_event), 3)
        self.assertEqual(output.count(b"705-AUDIO\0"), 3)

    def test_protocol_edge_cases(self):
        class EdgeModule:
            def __init__(self):
                self.closed = False
                self.spoken = []

            def module_init(self):
                return "edge initialized"

            def module_list_voices(self):
                return [speechd_types.SPDVoice("fake-en", "en-US", "MALE1")]

            def module_speak_sync(self, text, text_len, msgtype):
                self.spoken.append((text, text_len, msgtype))
                module_speak_ok()

            def module_close(self):
                self.closed = True

        module = EdgeModule()

        ret, stdout, _stderr = self.run_main(
            module,
            "INIT\n"
            "SPEAK\n"
            ".\n"
            "CHAR\n"
            "a\n"
            "b\n"
            ".\n"
            "SPEAK\n"
            ".First\n"
            ".\n"
            "LIST VOICES de\n"
            "QUIT\n",
        )

        self.assertEqual(
            stdout.getvalue(),
            "299-edge initialized\n"
            "299 OK LOADED SUCCESSFULLY\n"
            "202 OK RECEIVING MESSAGE\n"
            "301 ERROR CANT SPEAK\n"
            "202 OK RECEIVING MESSAGE\n"
            "305 DATA MORE THAN ONE LINE\n"
            "202 OK RECEIVING MESSAGE\n"
            "200 OK SPEAKING\n"
            "304 CANT LIST VOICES\n"
            "210 OK QUIT\n",
        )
        self.assertEqual(ret, 0)
        self.assertTrue(module.closed)
        self.assertEqual(module.spoken, [("First", 5, speechd_types.SPD_MSGTYPE_TEXT)])


if __name__ == "__main__":
    unittest.main()
