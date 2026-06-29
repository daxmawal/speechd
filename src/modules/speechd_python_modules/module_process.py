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

import sys
import threading
import traceback

from . import speechd_types
from .module_readline import module_readline
from .module_utils import module_debug, module_loglevel_set


module_stdout_mutex = threading.Lock()

BAD_SYNTAX = "302 ERROR BAD SYNTAX"
BAD_PARAM = "303 ERROR INVALID PARAMETER OR VALUE"
BAD_MULTILINE = "305 DATA MORE THAN ONE LINE"

# Arbitrary chunk size in bytes, large enough to get efficient transfer
# but small enough to be reactive.
MAX_CHUNK = 10000

# Whether we will send the audio to the server
_audio_server = False

#TODO module_should_stop = 0


# This sends some text to the server, taking the mutex to avoid intermixing
# between multi-line answers and asynchronous sends.
def module_send(format_string, *args):
    if args:
        format_string = format_string % args
    with module_stdout_mutex:
        sys.stdout.write(format_string)
        sys.stdout.flush()


def module_audio_set_server():
    global _audio_server

    _audio_server = True


def module_audio_set_through_server(cur_item, cur_value):
    # We only support the audio output method parameter
    if cur_item != "audio_output_method":
        return -1
    # We only support server audio output method
    if cur_value != "server":
        return -1
    return 0


def module_tts_output_send_server(track, format):
    size = track.num_channels * track.num_samples * track.bits // 8
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
        format,
    )

    with module_stdout_mutex:
        payload = track.samples[:size]
        # HDLC escaping: prefix NL and escapes with escape, and invert their bit 5.
        escape = 0x7D
        invert = 1 << 5
        escaped_payload = bytearray()
        for byte in payload:
            # Escape NL or escape.
            if byte in (0x0A, escape):
                escaped_payload.append(escape)
                escaped_payload.append(byte ^ invert)
            else:
                escaped_payload.append(byte)
        sys.stdout.buffer.write(
            header.encode() + b"\0" + bytes(escaped_payload) + b"\n705 AUDIO\n"
        )
        sys.stdout.buffer.flush()


def module_tts_output_server(track, format):
    sample_size = track.num_channels * track.bits // 8
    samplepos = 0

    while samplepos < track.num_samples:
        #TODO add the module stop condition here
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
        module_tts_output_send_server(mytrack, format)


def cmd_speak(module, msgtype, source=None):
    module_send("202 OK RECEIVING MESSAGE\n")

    lines = []
    nlines = 0
    while True:
        line = module_readline(source, block=True)
        if line is None:
            # EOF
            return
        if line == ".\n":
            # Replace \n at the end with a \0
            break
        if line.startswith("."):
            line = line[1:]
        nlines += 1
        lines.append(line)

    text = "".join(lines)
    if text.endswith("\n"):
        text = text[:-1]
    text_len = len(text.encode("utf-8", "surrogateescape"))

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

    #TODO module_should_stop = 0

    module_speak_sync = getattr(module, "module_speak_sync", None)
    if module_speak_sync is not None:
        try:
            module_speak_sync(text, text_len, msgtype)
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


def cmd_speak_text(module, source=None):
    return cmd_speak(module, speechd_types.SPD_MSGTYPE_TEXT, source)


#TODO implement def cmd_speak_sound_icon(module, source=None)


def cmd_speak_char(module, source=None):
    return cmd_speak(module, speechd_types.SPD_MSGTYPE_CHAR, source)


def cmd_speak_key(module, source=None):
    return cmd_speak(module, speechd_types.SPD_MSGTYPE_KEY, source)


def module_speak_ok():
    module_send("200 OK SPEAKING\n")


def module_speak_error():
    module_send("301 ERROR CANT SPEAK\n")


#TODO implement def cmd_stop(module)


#TODO implement def cmd_pause(module)


def cmd_list_voices(module, line):
    try:
        voices = module.module_list_voices()
        if voices:
            voices = list(voices)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        module_send("304 CANT LIST VOICES\n")
        return

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
                # Ok, skip this
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
                        # Not the requested language
                        continue
                if requested_variant and requested_variant.lower() != variant.lower():
                    # Not the requested variant, skip
                    continue

            one = True
            sys.stdout.write("200-%s\t%s\t%s\n" % (name, language, variant))

        if one:
            sys.stdout.write("200 OK VOICE LIST SENT\n")
        else:
            sys.stdout.write("304 CANT LIST VOICES\n")
        sys.stdout.flush()


def cmd_params(ack, param_type, set_param, source=None):
    module_send("%u OK RECEIVING %sSETTINGS\n", ack, param_type)
    err = None

    while True:
        line = module_readline(source, block=True)
        if line is None:
            # EOF
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

        try:
            ret = set_param(var, val)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            ret = -1

        if ret != 0:
            err = BAD_PARAM


#TODO add a Python equivalent of module_utils.c:module_set for standard settings
def _module_set_missing(_var, _val):
    return -1


def cmd_set(module, source=None):
    module_set = getattr(module, "module_set", _module_set_missing)
    if cmd_params(203, "", module_set, source) != 0:
        return
    module_send("203 OK SETTINGS RECEIVED\n")


#TODO add Python equivalents of module_utils.c:module_audio_set
def _module_audio_set_missing(_cur_item, _cur_value):
    return -1


#TODO add Python equivalents of module_audio_init and move this in module_utils.py
def _module_audio_init(module):
    audio_init = getattr(module, "module_audio_init", None)
    if audio_init is None:
        return 0, None

    try:
        result = audio_init()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return -1, "audio initialization failed."

    if isinstance(result, tuple):
        ret = result[0] if result else 0
        status = result[1] if len(result) >= 2 else None
    else:
        ret = 0 if result is None else result
        status = None

    try:
        ret = int(ret)
    except (TypeError, ValueError):
        return -1, str(result)

    return ret, status


def cmd_audio(module, source=None):
    if _audio_server:
        audio_set = module_audio_set_through_server
    else:
        audio_set = getattr(module, "module_audio_set", _module_audio_set_missing)

    if cmd_params(207, "AUDIO ", audio_set, source) != 0:
        return

    if _audio_server:
        ret, status = 0, None
    else:
        ret, status = _module_audio_init(module)

    if ret == 0:
        module_send("203 OK AUDIO INITIALIZED\n")
    else:
        status = status or "audio initialization failed."
        module_send("300-%s\n300 MODULE ERROR\n", status)


def cmd_loglevel(module, source=None):
    if cmd_params(207, "LOGLEVEL ", module_loglevel_set, source) != 0:
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
    try:
        module.module_close()
    except Exception:
        traceback.print_exc(file=sys.stderr)

    module_send("210 OK QUIT\n")


def module_process(module, fd=None, block=True):
    source = sys.stdin if fd is None else fd

    while True:
        line = module_readline(source, block)
        if line is None:
            return -1

        if line == "SPEAK\n":
            cmd_speak_text(module, source)
        #TODO dispatch SOUND_ICON to cmd_speak_sound_icon(module, source)
        elif line == "CHAR\n":
            cmd_speak_char(module, source)
        elif line == "KEY\n":
            cmd_speak_key(module, source)
        #TODO dispatch STOP to cmd_stop(module)
        #TODO dispatch PAUSE to cmd_pause(module)
        elif line.startswith("LIST VOICES"):
            cmd_list_voices(module, line)
        elif line == "SET\n":
            cmd_set(module, source)
        elif line == "AUDIO\n":
            cmd_audio(module, source)
        elif line == "LOGLEVEL\n":
            cmd_loglevel(module, source)
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


#TODO implement def module_report_event_stop()


#TODO implement def module_report_event_pause()


#TODO implement def module_report_icon(icon)
