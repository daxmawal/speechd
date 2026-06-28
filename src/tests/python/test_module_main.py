#
# test_module_main.py - Python module_main unit tests
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

from speechd_python_modules import module_main


class ModuleMainTest(unittest.TestCase):
    def setUp(self):
        self.old_stdin = sys.stdin
        self.old_stdout = sys.stdout
        self.old_stderr = sys.stderr
        self.stdin = io.StringIO()
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        sys.stdin = self.stdin
        sys.stdout = self.stdout
        sys.stderr = self.stderr

    def tearDown(self):
        sys.stdin = self.old_stdin
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr

    def test_config_error_is_reported_before_init_without_stdout(self):
        def fail_config(_path):
            raise RuntimeError("bad config")

        ret = module_main.run_main(fail_config, lambda _config: object(), ["fake-module"])

        self.assertEqual(ret, 1)
        self.assertEqual(self.stdout.getvalue(), "")
        self.assertIn("Traceback", self.stderr.getvalue())
        self.assertIn("RuntimeError: bad config", self.stderr.getvalue())

    def test_init_error_protocol(self):
        class FailingModule:
            def __init__(self):
                self.closed = False

            def module_init(self):
                raise RuntimeError("first line\nsecond line")

            def module_close(self):
                self.closed = True

        module = FailingModule()
        self.stdin = io.StringIO("INIT\n")
        sys.stdin = self.stdin

        ret = module_main.run_main(
            lambda _path: {},
            lambda _config: module,
            ["fake-module"],
        )

        self.assertEqual(ret, 1)
        self.assertTrue(module.closed)
        self.assertEqual(
            self.stdout.getvalue(),
            "399-first line second line\n399 ERR CANT INIT MODULE\n",
        )
        self.assertNotIn("Traceback", self.stdout.getvalue())
        self.assertIn("Traceback", self.stderr.getvalue())
        self.assertIn("RuntimeError: first line", self.stderr.getvalue())

    def test_init_success_protocol(self):
        class InitModule:
            def __init__(self, message):
                self.closed = False
                self.message = message

            def module_init(self):
                return self.message

            def module_close(self):
                self.closed = True

        def run_case(message):
            module = InitModule(message)
            self.stdin = io.StringIO("INIT\nQUIT\n")
            self.stdout = io.StringIO()
            sys.stdin = self.stdin
            sys.stdout = self.stdout

            ret = module_main.run_main(
                lambda _path: {},
                lambda _config: module,
                ["fake-module"],
            )

            self.assertEqual(ret, 0)
            self.assertTrue(module.closed)
            return self.stdout.getvalue()

        self.assertEqual(
            run_case(None),
            "299-Unspecified initialization success\n"
            "299 OK LOADED SUCCESSFULLY\n"
            "210 OK QUIT\n",
        )
        self.assertEqual(
            run_case("first line\nsecond line"),
            "299-first line second line\n"
            "299 OK LOADED SUCCESSFULLY\n"
            "210 OK QUIT\n",
        )


if __name__ == "__main__":
    unittest.main()
