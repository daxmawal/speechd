#
# module_readline.py - Input buffering for Python output modules.
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

import os
import select
import sys


READ_CHUNK = 4096

_fd_buffers = {}


def module_readline(source=None, block=True):
    if source is None:
        source = sys.stdin
    if isinstance(source, int):
        return _readline_fd(source, block)

    if not block:
        if _can_select(source):
            readable, _, _ = select.select([source], [], [], 0)
            if not readable:
                return None
        else:
            return None

    line = source.readline()
    return _decode_line(line)


def _readline_fd(fd, block):
    buffer = _fd_buffers.setdefault(fd, bytearray())

    while True:
        newline = buffer.find(b"\n")
        if newline != -1:
            line = bytes(buffer[: newline + 1])
            del buffer[: newline + 1]
            if not buffer:
                _fd_buffers.pop(fd, None)
            return _decode_bytes(line)

        timeout = None if block else 0
        readable, _, _ = select.select([fd], [], [], timeout)
        if not readable:
            return None

        try:
            chunk = os.read(fd, READ_CHUNK)
        except (InterruptedError, BlockingIOError):
            if not block:
                return None
            continue

        if not chunk:
            _fd_buffers.pop(fd, None)
            return None

        buffer.extend(chunk)


def _can_select(source):
    try:
        source.fileno()
    except (AttributeError, OSError, ValueError):
        return False
    return True


def _decode_line(line):
    if not line:
        return None
    if isinstance(line, bytes):
        return _decode_bytes(line)
    return line


def _decode_bytes(data):
    return data.decode("utf-8", "surrogateescape")
