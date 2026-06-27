#
# module_main.py - Main loop entry point for Python output modules.
#
# Copyright (C) 2026 Jean-François David <jeanfrancoismanutea@gmail.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

import sys
import traceback

from .module_utils import module_loop


def config_path(argv):
    return argv[1] if len(argv) >= 2 else None


def print_init_error(message):
    if message is None:
        message = "Unspecified initialization error"
    message = " ".join(str(message).splitlines())
    if not message:
        message = "Unspecified initialization error"

    sys.stdout.write("399-%s\n" % message)
    sys.stdout.write("399 ERR CANT INIT MODULE\n")
    sys.stdout.flush()


def run_main(module_config, module_factory, argv=None, reexec=None):
    argv = sys.argv if argv is None else argv
    configfile = config_path(argv)

    try:
        config = module_config(configfile)
        if reexec is not None:
            reexec(config, argv)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        module_close(None)
        return 1

    line = sys.stdin.readline()
    if line != "INIT\n":
        sys.stderr.write("ERROR: Server did not start with INIT\n")
        sys.stderr.flush()
        module_close(None)
        return 3

    module = None
    try:
        module = module_factory(config)
        msg = module.module_init()
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        print_init_error(str(exc) or "initialization failed")
        module_close(module)
        return 1

    if msg is None:
        msg = "Unspecified initialization success\n"
    sys.stdout.write("299-%s\n" % msg)
    sys.stdout.write("299 OK LOADED SUCCESSFULLY\n")
    sys.stdout.flush()

    ret = module_loop(module)
    if ret:
        sys.stdout.write("399 ERR MODULE CLOSED\n")
        sys.stdout.flush()
        module_close(module)
    return ret


def module_close(module):
    if module is not None:
        module.module_close()
