#
# module_main.c - Main file of output modules.
#
# Copyright (C) 2020-2021 Samuel Thibault <samuel.thibault@ens-lyon.org>
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
# THIS SOFTWARE IS PROVIDED BY Samuel Thibault AND CONTRIBUTORS ``AS IS'' AND
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
from collections.abc import Callable
from typing import Any

from module_process import module_process
from spd_module_main import SPDModule


def config_path(argv):
    return argv[1] if len(argv) >= 2 else None


def print_init_error(message):
    if message is None:
        message = "Unspecified initialization error\n"
    sys.stdout.write("399-%s\n" % message)
    sys.stdout.write("399 ERR CANT INIT MODULE\n")
    sys.stdout.flush()


def run_main(
    module_config: Callable[[str | None], Any],
    module_factory: Callable[[Any], SPDModule],
    *,
    argv=None,
    reexec=None,
    hard_exit=False,
):
    argv = sys.argv if argv is None else argv

    # Read configuration
    try:
        config = module_config(config_path(argv))
        if reexec is not None:
            reexec(config, argv)
    except Exception:
        module_close(None)
        return 1

    # Wait for server init
    if sys.stdin.readline() != "INIT\n":
        sys.stderr.write("ERROR: Server did not start with INIT\n")
        sys.stderr.flush()
        module_close(None)
        return 3

    # Initialize module */
    module = None
    try:
        module = module_factory(config)
        status = module.module_init()
    except Exception:
        print_init_error(traceback.format_exc())
        module_close(module)
        return 1

    if status is None:
        status = "Unspecified initialization success\n"
    sys.stdout.write("299-%s\n" % status)
    sys.stdout.write("299 OK LOADED SUCCESSFULLY\n")
    sys.stdout.flush()

    # Run module
    result = module_process(module, hard_exit=hard_exit)
    if result:
        sys.stdout.write("399 ERR MODULE CLOSED\n")
        sys.stdout.flush()
        module_close(module)
    return result


def module_close(module):
    if module is not None:
        module.module_close()
