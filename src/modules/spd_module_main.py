#
# spd_module_main.py - Interface for main loop of Python output modules.
#
# Copyright (C) 2020-2021, 2025 Samuel Thibault <samuel.thibault@ens-lyon.org>
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

from collections.abc import Sequence
from typing import Protocol

from speechd_types import SPDVoice


class SPDModule(Protocol):
    def module_init(self) -> str | None:
        ...

    def module_list_voices(self) -> Sequence[SPDVoice]:
        ...

    def module_speak_sync(self, data: str, bytes: int, msgtype: int) -> None:
        ...

    def module_pause(self) -> int:
        ...

    def module_stop(self) -> int:
        ...

    def module_close(self) -> int:
        ...

    def module_set(self, var: str, val: str) -> int:
        ...
