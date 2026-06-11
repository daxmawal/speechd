#
# module_main.py - Main startup structure for Python output modules.
#
# Copyright (C) 2020-2021 Samuel Thibault <samuel.thibault@ens-lyon.org>
# Copyright (C) 2026 Hypra
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

from module_process import module_process, module_send


def config_path(argv):
    for arg in argv[1:]:
        if not arg.startswith("--"):
            return arg
    return None


def init_error(error):
    for line in str(error).splitlines():
        module_send("399-%s\n", line)
    module_send("399 ERR CANT INIT MODULE\n")


def run_main(
    load_config,
    module_factory,
    *,
    argv=None,
    reexec=None,
    success_message="Unspecified initialization success",
    hard_exit=False,
):
    argv = sys.argv if argv is None else argv

    try:
        config = load_config(config_path(argv))
        if reexec is not None:
            reexec(config, argv)
    except Exception as error:
        config = None
        config_error = error
    else:
        config_error = None

    if sys.stdin.readline() != "INIT\n":
        init_error("Server did not start with INIT")
        return 1

    if config_error is not None:
        init_error(config_error)
        return 1

    module = None
    try:
        module = module_factory(config)
        status = module.initialize()
    except Exception:
        init_error(traceback.format_exc())
        call_module_close(module)
        return 1

    module_send("299-%s\n", status or success_message)
    module_send("299 OK LOADED SUCCESSFULLY\n")
    result = module_process(module, hard_exit=hard_exit)
    if result:
        module_send("399 ERR MODULE CLOSED\n")
        call_module_close(module)
    return result


def call_module_close(module):
    close = getattr(module, "close", None)
    if close is not None:
        close()
