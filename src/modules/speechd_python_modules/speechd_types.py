#
# speechd_types.py - types for Speech Dispatcher
#
# Copyright (C) 2001, 2002, 2003 Brailcom, o.p.s.
# Copyright (C) 2004 Brailcom, o.p.s.
# Copyright (C) 2019-2024 Samuel Thibault <samuel.thibault@ens-lyon.org>
#
# This is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1, or (at your option)
# any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

SPD_MSGTYPE_TEXT = 0
SPD_MSGTYPE_SOUND_ICON = 1
SPD_MSGTYPE_CHAR = 2
SPD_MSGTYPE_KEY = 3
SPD_MSGTYPE_SPELL = 99

SPD_AUDIO_LE = 0
SPD_AUDIO_BE = 1


class SPDVoice:
    def __init__(self, name=None, language=None, variant=None):
        self.name = name
        self.language = language
        self.variant = variant


class AudioTrack:
    def __init__(self, bits, num_channels, sample_rate, num_samples, samples):
        self.bits = bits
        self.num_channels = num_channels
        self.sample_rate = sample_rate
        self.num_samples = num_samples
        self.samples = samples
