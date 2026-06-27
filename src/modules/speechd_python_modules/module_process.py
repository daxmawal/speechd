#
# module_process.py - Processing loop for Python output modules.
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

import select
import sys
import threading
import traceback

from . import speechd_types
from .module_utils import module_debug, module_loglevel_set


module_stdout_mutex = threading.Lock()

BAD_SYNTAX = "302 ERROR BAD SYNTAX"
BAD_PARAM = "303 ERROR INVALID PARAMETER OR VALUE"
BAD_MULTILINE = "305 DATA MORE THAN ONE LINE"
MAX_CHUNK = 10000


def module_send(format_string, *args):
    if args:
        format_string = format_string % args
    with module_stdout_mutex:
        sys.stdout.write(format_string)
        sys.stdout.flush()


def module_audio_set_server():
    pass


def module_audio_set_through_server(cur_item, cur_value):
    if cur_item != "audio_output_method":
        return -1
    if cur_value != "server":
        return -1
    return 0


def _sample_size(track):
    if track.bits <= 0 or track.bits % 8 != 0:
        raise ValueError("track.bits must be a positive multiple of 8")
    if track.num_channels <= 0:
        raise ValueError("track.num_channels must be positive")
    if track.num_samples < 0:
        raise ValueError("track.num_samples must not be negative")

    sample_size = track.num_channels * track.bits // 8
    if sample_size <= 0:
        raise ValueError("invalid sample size")
    if sample_size > MAX_CHUNK:
        raise ValueError("sample size is larger than MAX_CHUNK")
    return sample_size


def _track_payload_size(track):
    sample_size = _sample_size(track)
    expected_size = track.num_samples * sample_size

    if len(track.samples) != expected_size:
        raise ValueError(
            "invalid AudioTrack payload size: got %d bytes, expected %d"
            % (len(track.samples), expected_size)
        )
    return sample_size, expected_size


def module_tts_output_send_server(track, audio_format):
    if audio_format not in (speechd_types.SPD_AUDIO_LE, speechd_types.SPD_AUDIO_BE):
        raise ValueError("invalid audio format")
    _track_payload_size(track)
    header = (
        "705-bits=%d\n"
        "705-num_channels=%d\n"
        "705-sample_rate=%d\n"
        "705-num_samples=%d\n"
        "705-big_endian=%d\n"
        "705-AUDIO"
    ) % (
        track.bits,
        track.num_channels,
        track.sample_rate,
        track.num_samples,
        audio_format,
    )

    with module_stdout_mutex:
        sys.stdout.buffer.write(header.encode())
        sys.stdout.buffer.write(b"\0")
        payload = track.samples
        escape = 0x7D
        invert = 1 << 5
        for byte in payload:
            if byte in (0x0A, escape):
                sys.stdout.buffer.write(bytes((escape, byte ^ invert)))
            else:
                sys.stdout.buffer.write(bytes((byte,)))
        sys.stdout.buffer.write(b"\n705 AUDIO\n")
        sys.stdout.buffer.flush()


def module_tts_output_server(track, audio_format):
    sample_size, _ = _track_payload_size(track)
    samplepos = 0

    while samplepos < track.num_samples:
        num_samples = MAX_CHUNK // sample_size
        if num_samples > track.num_samples - samplepos:
            num_samples = track.num_samples - samplepos

        start = samplepos * sample_size
        end = start + num_samples * sample_size
        samplepos += num_samples

        mytrack = speechd_types.AudioTrack(
            bits=track.bits,
            num_channels=track.num_channels,
            sample_rate=track.sample_rate,
            num_samples=num_samples,
            samples=track.samples[start:end],
        )
        module_tts_output_send_server(mytrack, audio_format)


def cmd_speak(module, msgtype):
    module_send("202 OK RECEIVING MESSAGE\n")

    lines = []
    nlines = 0
    while True:
        line = _readline(block=True)
        if line is None:
            return
        if line == ".\n":
            break
        if line.startswith("."):
            line = line[1:]
        nlines += 1
        lines.append(line)

    text = "".join(lines)
    if text.endswith("\n"):
        text = text[:-1]
    text_len = len(text)

    if not text_len:
        module_speak_error()
        return

    if msgtype != speechd_types.SPD_MSGTYPE_TEXT and nlines > 1:
        module_send("%s\n", BAD_MULTILINE)
        return

    if msgtype in (speechd_types.SPD_MSGTYPE_KEY, speechd_types.SPD_MSGTYPE_CHAR):
        if text == "space":
            text = " "
            text_len = 1

    speak_sync = getattr(module, "module_speak_sync", None)
    if speak_sync is not None:
        try:
            speak_sync(text, text_len, msgtype)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            module_speak_error()
        return

    try:
        with module_stdout_mutex:
            ret = module.module_speak(text, text_len, msgtype)
            if ret is not None and ret > 0:
                sys.stdout.write("200 OK SPEAKING\n")
            else:
                sys.stdout.write("301 ERROR CANT SPEAK\n")
            sys.stdout.flush()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        module_speak_error()


def cmd_speak_text(module):
    return cmd_speak(module, speechd_types.SPD_MSGTYPE_TEXT)


def cmd_speak_char(module):
    return cmd_speak(module, speechd_types.SPD_MSGTYPE_CHAR)


def cmd_speak_key(module):
    return cmd_speak(module, speechd_types.SPD_MSGTYPE_KEY)


def module_speak_ok():
    module_send("200 OK SPEAKING\n")


def module_speak_error():
    module_send("301 ERROR CANT SPEAK\n")


def cmd_list_voices(module, line):
    voices = module.module_list_voices()
    if not voices:
        module_send("304 CANT LIST VOICES\n")
        return

    parts = line.split()
    requested_language = parts[2] if len(parts) >= 3 else None
    requested_variant = parts[3] if len(parts) >= 4 else None
    one = False

    with module_stdout_mutex:
        for voice in voices:
            name = voice.name
            language = voice.language
            variant = voice.variant
            if not name:
                continue

            language = language or "none"
            variant = variant or "none"

            if requested_language:
                if requested_language.lower() != language.lower():
                    dash = language.find("-")
                    langlen = dash if dash != -1 else len(language)
                    if (
                        len(requested_language) != langlen
                        or requested_language.lower() != language[:langlen].lower()
                    ):
                        continue
                if requested_variant and requested_variant.lower() != variant.lower():
                    continue

            one = True
            sys.stdout.write("200-%s\t%s\t%s\n" % (name, language, variant))

        if one:
            sys.stdout.write("200 OK VOICE LIST SENT\n")
        else:
            sys.stdout.write("304 CANT LIST VOICES\n")
        sys.stdout.flush()


def cmd_params(ack, param_type, set_param):
    module_send("%u OK RECEIVING %sSETTINGS\n", ack, param_type)
    err = None

    while True:
        line = _readline(block=True)
        if line is None:
            return -1

        if line == ".\n":
            if err is None:
                return 0
            module_send("%s\n", err)
            return -1

        line = line.rstrip("\n")
        if "=" not in line:
            err = BAD_SYNTAX
            continue

        var, val = line.split("=", 1)
        if not var or val == "":
            err = BAD_SYNTAX
            continue

        if set_param(var, val) != 0:
            err = BAD_PARAM


def cmd_set(module):
    if cmd_params(203, "", module.module_set) != 0:
        return
    module_send("203 OK SETTINGS RECEIVED\n")


def cmd_audio(module):
    del module

    if cmd_params(207, "AUDIO ", module_audio_set_through_server) != 0:
        return
    module_send("203 OK AUDIO INITIALIZED\n")


def cmd_loglevel(module):
    if cmd_params(207, "LOGLEVEL ", module_loglevel_set) != 0:
        return
    module_send("203 OK LOGLEVEL SET\n")


def cmd_debug(module, line):
    del module

    parts = line.split()
    if len(parts) < 2:
        module_send("%s\n", BAD_SYNTAX)
        return

    debug = parts[0]
    if debug != "DEBUG":
        module_send("%s\n", BAD_SYNTAX)
        return

    on = parts[1]
    enable = False
    filename = None
    if on == "ON":
        enable = True
        if len(parts) < 3:
            module_send("%s\n", BAD_SYNTAX)
            return
        filename = parts[2]
    elif on != "OFF":
        module_send("%s\n", BAD_SYNTAX)
        return

    if module_debug(enable, filename) != 0:
        module_send("303 CANT OPEN CUSTOM DEBUG FILE\n")
    else:
        module_send("200 OK DEBUGGING %s\n", on)


def cmd_quit(module):
    _call_module(module, "module_close")
    module_send("210 OK QUIT\n")


def module_process(module, fd=None, block=True):
    del fd

    while True:
        line = _readline(block)
        if line is None:
            return -1

        if line == "SPEAK\n":
            cmd_speak_text(module)
        elif line == "CHAR\n":
            cmd_speak_char(module)
        elif line == "KEY\n":
            cmd_speak_key(module)
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
            return 0
        else:
            module_send("300 ERR UNKNOWN COMMAND\n")


def module_report_event_begin():
    module_send("701 BEGIN\n")


def module_report_event_end():
    module_send("702 END\n")


def _readline(block):
    if not block:
        readable, _, _ = select.select([sys.stdin], [], [], 0)
        if not readable:
            return None
    line = sys.stdin.readline()
    return line if line else None


def _call_module(module, name, *args):
    handler = getattr(module, name, None)
    if handler is not None:
        return handler(*args)
    return None
