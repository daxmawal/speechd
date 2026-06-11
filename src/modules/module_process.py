#
# module_process.py - Processing loop of output modules.
#
# Copyright (C) 2020-2023, 2025 Samuel Thibault <samuel.thibault@ens-lyon.org>
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

import os
import select
import sys

from speechd_types import (
    SPD_MSGTYPE_CHAR,
    SPD_MSGTYPE_KEY,
    SPD_MSGTYPE_SOUND_ICON,
    SPD_MSGTYPE_TEXT,
)

BAD_SYNTAX = "302 ERROR BAD SYNTAX"
BAD_PARAM = "303 ERROR INVALID PARAMETER OR VALUE"
BAD_MULTILINE = "305 DATA MORE THAN ONE LINE"

MAX_CHUNK = 10000

_audio_server = False
_current_module = None
_module_should_stop = False


def module_send(fmt, *args):
    if args:
        fmt = fmt % args
    sys.stdout.write(fmt)
    sys.stdout.flush()


def module_audio_set_server():
    global _audio_server
    _audio_server = True


def module_audio_set_through_server(cur_item, cur_value):
    if cur_item != "audio_output_method":
        return -1
    if cur_value != "server":
        return -1
    return 0


def module_tts_output_send_server(
    samples,
    sample_rate,
    num_channels=1,
    bits=16,
    big_endian=0,
):
    sample_size = num_channels * bits // 8

    module_send("705-bits=%d\n", bits)
    module_send("705-num_channels=%d\n", num_channels)
    module_send("705-sample_rate=%d\n", sample_rate)
    module_send("705-num_samples=%d\n", len(samples) // sample_size)
    module_send("705-big_endian=%d\n", big_endian)
    module_send("705-AUDIO")
    sys.stdout.buffer.write(b"\0")
    sys.stdout.buffer.write(_escape_audio(samples))
    sys.stdout.buffer.write(b"\n705 AUDIO\n")
    sys.stdout.buffer.flush()


def module_tts_output_server(
    samples,
    sample_rate,
    num_channels=1,
    bits=16,
    big_endian=0,
):
    sample_size = num_channels * bits // 8
    num_samples = len(samples) // sample_size
    samplepos = 0

    while samplepos < num_samples:
        if _module_should_stop:
            break

        chunk_samples = MAX_CHUNK // sample_size
        if chunk_samples > num_samples - samplepos:
            chunk_samples = num_samples - samplepos

        start = samplepos * sample_size
        end = start + chunk_samples * sample_size
        samplepos += chunk_samples

        module_tts_output_send_server(
            samples[start:end],
            sample_rate,
            num_channels,
            bits,
            big_endian,
        )

        if _current_module is not None:
            module_process(_current_module, block=False)


def cmd_speak(module, msgtype):
    global _module_should_stop

    _print("202 OK RECEIVING MESSAGE")
    text, nlines = _read_message()

    if not text:
        module_speak_error()
        return

    if msgtype != SPD_MSGTYPE_TEXT and nlines > 1:
        _print(BAD_MULTILINE)
        return

    if msgtype in {SPD_MSGTYPE_KEY, SPD_MSGTYPE_CHAR} and text == "space":
        text = " "

    _module_should_stop = False
    speak_sync = getattr(module, "speak_sync", None)
    if speak_sync is not None:
        speak_sync(text, len(text), msgtype)
        return

    result = module.speak(text, msgtype)
    if result is None:
        return
    if result:
        module_speak_ok()
    else:
        module_speak_error()


def cmd_speak_text(module):
    return cmd_speak(module, SPD_MSGTYPE_TEXT)


def cmd_speak_sound_icon(module):
    return cmd_speak(module, SPD_MSGTYPE_SOUND_ICON)


def cmd_speak_char(module):
    return cmd_speak(module, SPD_MSGTYPE_CHAR)


def cmd_speak_key(module):
    return cmd_speak(module, SPD_MSGTYPE_KEY)


def module_speak_ok():
    _print("200 OK SPEAKING")


def module_speak_error():
    _print("301 ERROR CANT SPEAK")


def cmd_stop(module):
    global _module_should_stop
    _module_should_stop = True
    _call_module(module, "stop")


def cmd_pause(module):
    global _module_should_stop
    _module_should_stop = True
    _call_module(module, "pause")


def cmd_list_voices(module, line):
    voices = module.list_voices()
    if not voices:
        _print("304 CANT LIST VOICES")
        return

    parts = line.split()
    requested_language = parts[2] if len(parts) >= 3 else None
    requested_variant = parts[3] if len(parts) >= 4 else None
    one = False

    for language, variant, name in voices:
        if not name:
            continue

        language = language or "none"
        variant = variant or "none"

        if requested_language:
            if requested_language.lower() != language.lower():
                language_prefix = language.split("-", 1)[0]
                if requested_language.lower() != language_prefix.lower():
                    continue
            if requested_variant and requested_variant.lower() != variant.lower():
                continue

        one = True
        module_send("200-%s\t%s\t%s\n", name, language, variant)

    _print("200 OK VOICE LIST SENT" if one else "304 CANT LIST VOICES")


def cmd_params(module, ack, type_name, set_func):
    _print("%u OK RECEIVING %sSETTINGS" % (ack, type_name))
    err = None

    while True:
        line = _readline(block=True)
        if line is None:
            return -1

        if line == ".\n":
            if err is None:
                return 0
            _print(err)
            return -1

        stripped = line.rstrip("\n")
        if "=" not in stripped:
            err = BAD_SYNTAX
            continue

        var, val = stripped.split("=", 1)
        if not var or val == "":
            err = BAD_SYNTAX
            continue

        if not _setter_succeeded(set_func(module, var, val)):
            err = BAD_PARAM


def cmd_set(module):
    if cmd_params(module, 203, "", _module_set) != 0:
        return
    _print("203 OK SETTINGS RECEIVED")


def cmd_audio(module):
    if _audio_server:
        ret = cmd_params(module, 207, "AUDIO ", _module_audio_set_through_server)
    else:
        ret = cmd_params(module, 207, "AUDIO ", _module_audio_set)
        if ret == 0:
            audio_init = getattr(module, "audio_init", None)
            if audio_init is not None:
                ret = 0 if _setter_succeeded(audio_init()) else -1

    if ret == 0:
        _print("203 OK AUDIO INITIALIZED")


def cmd_loglevel(module):
    if cmd_params(module, 207, "LOGLEVEL ", _module_loglevel_set) != 0:
        return
    _print("203 OK LOGLEVEL SET")


def cmd_debug(module, line):
    parts = line.split(maxsplit=2)
    if len(parts) < 2 or parts[0] != "DEBUG":
        _print(BAD_SYNTAX)
        return

    enable = False
    filename = None
    if parts[1] == "ON":
        enable = True
        if len(parts) != 3:
            _print(BAD_SYNTAX)
            return
        filename = parts[2]
    elif parts[1] != "OFF":
        _print(BAD_SYNTAX)
        return

    debug = getattr(module, "debug", None)
    if debug is not None and not _setter_succeeded(debug(enable, filename)):
        _print("303 CANT OPEN CUSTOM DEBUG FILE")
    else:
        _print("200 OK DEBUGGING %s" % parts[1])


def cmd_quit(module):
    _call_module(module, "close")
    _print("210 OK QUIT")


def module_process(module, fd=None, block=True, hard_exit=False):
    del fd

    global _current_module
    previous_module = _current_module
    _current_module = module

    try:
        while True:
            line = _readline(block)
            if line is None:
                return -1

            if line == "SPEAK\n":
                cmd_speak_text(module)
            elif line == "SOUND_ICON\n":
                cmd_speak_sound_icon(module)
            elif line == "CHAR\n":
                cmd_speak_char(module)
            elif line == "KEY\n":
                cmd_speak_key(module)
            elif line == "STOP\n":
                cmd_stop(module)
            elif line == "PAUSE\n":
                cmd_pause(module)
            elif line.startswith("LIST VOICES"):
                cmd_list_voices(module, line)
            elif line == "SET\n":
                cmd_set(module)
            elif line == "AUDIO\n":
                cmd_audio(module)
            elif line == "LOGLEVEL\n":
                cmd_loglevel(module)
            elif line.startswith("DEBUG"):
                cmd_debug(module, line.rstrip("\n"))
            elif line == "QUIT\n":
                cmd_quit(module)
                if hard_exit:
                    sys.stdout.flush()
                    sys.stderr.flush()
                    os._exit(0)
                return 0
            else:
                _print("300 ERR UNKNOWN COMMAND")
    finally:
        _current_module = previous_module


def module_report_index_mark(mark):
    if mark is None:
        return
    _print("700-%s\n700 INDEX MARK" % mark)


def module_report_event_begin():
    _print("701 BEGIN")


def module_report_event_end():
    _print("702 END")


def module_report_event_stop():
    _print("703 STOP")


def module_report_event_pause():
    _print("704 PAUSE")


def module_report_icon(icon):
    if icon is None:
        return
    _print("706-%s\n706 ICON" % icon)


def _print(line):
    module_send("%s\n", line)


def _readline(block):
    if not block:
        readable, _, _ = select.select([sys.stdin], [], [], 0)
        if not readable:
            return None
    line = sys.stdin.readline()
    return line if line else None


def _read_message():
    lines = []
    while True:
        line = _readline(block=True)
        if line is None:
            raise EOFError
        if line == ".\n":
            break
        if line.startswith("."):
            line = line[1:]
        lines.append(line)

    text = "".join(lines)
    return (text[:-1] if text.endswith("\n") else text), len(lines)


def _escape_audio(payload):
    escaped = bytearray()
    for byte in payload:
        if byte in (0x0A, 0x7D):
            escaped.append(0x7D)
            escaped.append(byte ^ 0x20)
        else:
            escaped.append(byte)
    return bytes(escaped)


def _setter_succeeded(result):
    if isinstance(result, bool):
        return result
    if isinstance(result, int):
        return result == 0
    return bool(result)


def _call_module(module, name, *args):
    handler = getattr(module, name, None)
    if handler is not None:
        return handler(*args)
    return None


def _module_set(module, var, val):
    return module.set_parameter(var, val)


def _module_audio_set_through_server(_module, var, val):
    return module_audio_set_through_server(var, val)


def _module_audio_set(module, var, val):
    audio_set = getattr(module, "audio_set", None)
    if audio_set is not None:
        return audio_set(var, val)
    return module_audio_set_through_server(var, val)


def _module_loglevel_set(module, var, val):
    loglevel_set = getattr(module, "loglevel_set", None)
    if loglevel_set is not None:
        return loglevel_set(var, val)
    if var != "log_level":
        return -1
    try:
        int(val)
    except ValueError:
        return -1
    return 0
