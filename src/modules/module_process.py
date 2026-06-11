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
import sys


MESSAGE_TEXT = "TEXT"
MESSAGE_CHAR = "CHAR"
MESSAGE_KEY = "KEY"
MESSAGE_SOUND_ICON = "SOUND_ICON"

BAD_SYNTAX = "302 ERROR BAD SYNTAX"
BAD_PARAM = "303 ERROR INVALID PARAMETER OR VALUE"
BAD_MULTILINE = "305 DATA MORE THAN ONE LINE"
CANT_SPEAK = "301 ERROR CANT SPEAK"

MAX_AUDIO_CHUNK = 10000


def reply(line):
    print(line, flush=True)


def speak_ok():
    reply("200 OK SPEAKING")


def speak_error():
    reply(CANT_SPEAK)


def event_begin():
    reply("701 BEGIN")


def event_end():
    reply("702 END")


def event_stop():
    reply("703 STOP")


def read_message():
    lines = []
    while True:
        line = sys.stdin.readline()
        if line == "":
            raise EOFError
        if line == ".\n":
            break
        if line.startswith(".."):
            line = line[1:]
        lines.append(line)

    text = "".join(lines)
    return text[:-1] if text.endswith("\n") else text, len(lines)


def receive_settings(status, label, setter):
    reply(f"{status} OK RECEIVING {label}SETTINGS")
    error = None
    while True:
        line = sys.stdin.readline()
        if line == "":
            raise EOFError
        if line == ".\n":
            break
        if "=" not in line:
            error = BAD_SYNTAX
            continue
        var, val = line.rstrip("\n").split("=", 1)
        if not setter(var, val):
            error = BAD_PARAM

    if error is not None:
        reply(error)
        return False
    return True


def write_audio_pcm(pcm, sample_rate, num_channels=1, bits=16, big_endian=0):
    sample_size = num_channels * bits // 8
    for offset in range(0, len(pcm), MAX_AUDIO_CHUNK):
        chunk = pcm[offset : offset + MAX_AUDIO_CHUNK]
        payload = escape_audio(chunk)

        sys.stdout.write(f"705-bits={bits}\n")
        sys.stdout.write(f"705-num_channels={num_channels}\n")
        sys.stdout.write(f"705-sample_rate={sample_rate}\n")
        sys.stdout.write(f"705-num_samples={len(chunk) // sample_size}\n")
        sys.stdout.write(f"705-big_endian={big_endian}\n")
        sys.stdout.write("705-AUDIO")
        sys.stdout.flush()
        sys.stdout.buffer.write(b"\0" + payload + b"\n705 AUDIO\n")
        sys.stdout.buffer.flush()


def escape_audio(payload):
    escaped = bytearray()
    for byte in payload:
        if byte in (0x0A, 0x7D):
            escaped.append(0x7D)
            escaped.append(byte ^ 0x20)
        else:
            escaped.append(byte)
    return bytes(escaped)


def send_voice_list(voices, command):
    parts = command.split()
    requested_language = parts[2] if len(parts) >= 3 else None
    requested_variant = parts[3] if len(parts) >= 4 else None
    sent_any = False

    for language, variant, name in voices:
        if requested_language is not None and not languages_match(requested_language, language):
            continue
        if requested_variant is not None and requested_variant.lower() != variant.lower():
            continue
        print(f"200-{name}\t{language}\t{variant}", flush=False)
        sent_any = True

    reply("200 OK VOICE LIST SENT" if sent_any else "304 CANT LIST VOICES")


def languages_match(requested, candidate):
    requested = requested.lower().replace("_", "-")
    candidate = candidate.lower().replace("_", "-")
    return requested == candidate or requested.split("-", 1)[0] == candidate.split("-", 1)[0]


def run(module, *, hard_exit=False):
    try:
        while True:
            command = sys.stdin.readline()
            if command == "":
                return 1
            command = command.rstrip("\n")

            if command in {"SPEAK", MESSAGE_CHAR, MESSAGE_KEY, MESSAGE_SOUND_ICON}:
                handle_speech_command(module, command)
            elif command == "STOP":
                call_optional(module, "stop")
            elif command == "PAUSE":
                call_optional(module, "pause")
            elif command.startswith("LIST VOICES"):
                send_voice_list(module.list_voices(), command)
            elif command == "SET":
                if receive_settings(203, "", module.set_parameter):
                    reply("203 OK SETTINGS RECEIVED")
            elif command == "AUDIO":
                if receive_settings(207, "AUDIO ", set_audio):
                    reply("203 OK AUDIO INITIALIZED")
            elif command == "LOGLEVEL":
                if receive_settings(207, "LOGLEVEL ", set_loglevel):
                    reply("203 OK LOGLEVEL SET")
            elif command.startswith("DEBUG"):
                handle_debug(module, command)
            elif command == "QUIT":
                call_optional(module, "close")
                reply("210 OK QUIT")
                if hard_exit:
                    sys.stdout.flush()
                    sys.stderr.flush()
                    os._exit(0)
                return 0
            else:
                reply("300 ERR UNKNOWN COMMAND")
    except EOFError:
        return 1


def handle_speech_command(module, command):
    reply("202 OK RECEIVING MESSAGE")
    text, lines = read_message()
    if command != "SPEAK" and lines > 1:
        reply(BAD_MULTILINE)
    elif command == MESSAGE_SOUND_ICON:
        call_optional(module, "sound_icon", text, default=speak_error)
    else:
        module.speak(text, MESSAGE_TEXT if command == "SPEAK" else command)


def set_audio(var, val):
    return var == "audio_output_method" and val == "server"


def set_loglevel(var, _val):
    return var == "log_level"


def handle_debug(module, command):
    parts = command.split(maxsplit=2)
    if len(parts) < 2 or parts[1] not in {"ON", "OFF"}:
        reply(BAD_SYNTAX)
        return
    if parts[1] == "ON" and len(parts) != 3:
        reply(BAD_SYNTAX)
        return

    handler = getattr(module, "debug", None)
    if handler is not None and not handler(parts[1] == "ON", parts[2] if len(parts) == 3 else None):
        reply("303 CANT OPEN CUSTOM DEBUG FILE")
    else:
        reply(f"200 OK DEBUGGING {parts[1]}")


def call_optional(module, name, *args, default=None):
    handler = getattr(module, name, None)
    if handler is None:
        if default is not None:
            default()
        return None
    return handler(*args)
