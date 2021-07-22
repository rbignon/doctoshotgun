# -*- coding: utf-8 -*-

# Copyright(C) 2011 Laurent Bachelier
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

from base64 import b64decode, b64encode
import binascii

from woob.capabilities.paste import CapPaste


class BasePasteModule(CapPaste):
    EXPIRATIONS = {}
    """
    List of expirations and their corresponding remote codes (any type can be used).
    The expirations, i.e. the keys, are integers representing the duration
    in seconds. There also can be one False key, for the "forever" expiration.
    """

    def get_closest_expiration(self, max_age):
        """
        Get the expiration closest (and less or equal to) max_age (int, in seconds).
        max_age set to False means we want it to never expire.

        @return int or False if found, else None
        """
        # "forever"
        if max_age is False and False in self.EXPIRATIONS:
            return max_age
        # get timed expirations, longest first
        expirations = sorted([e for e in self.EXPIRATIONS if e is not False], reverse=True)
        # find the first expiration that is below or equal to the maximum wanted age
        for e in expirations:
            if max_age is False or max_age >= e:
                return e


def image_mime(data_base64, supported_formats=('gif', 'jpeg', 'png')):
    """
    Return the MIME type of an image or None.

    :param data_base64: data to detect, base64 encoded
    :type data_base64: str
    :param supported_formats: restrict list of formats to test
    """
    try:
        beginning = b64decode(data_base64[:24])
    except binascii.Error:
        return None

    if 'gif' in supported_formats and b'GIF8' in beginning:
        return 'image/gif'
    elif 'jpeg' in supported_formats and b'JFIF' in beginning:
        return 'image/jpeg'
    elif 'png' in supported_formats and b'\x89PNG' in beginning:
        return 'image/png'
    elif 'xcf' in supported_formats and b'gimp xcf' in beginning:
        return 'image/x-xcf'
    elif 'pdf' in supported_formats and b'%PDF' in beginning:
        return 'application/pdf'
    elif 'tiff' in supported_formats and (b'II\x00\x2a' in beginning or
          b'MM\x2a\x00' in beginning):
        return 'image/tiff'


def bin_to_b64(b):
    return b64encode(b).decode('ascii')


def test():
    class MockPasteModule(BasePasteModule):
        def __init__(self, expirations):
            self.EXPIRATIONS = expirations

    # all expirations are too high
    assert MockPasteModule({1337: '', 42: '', False: ''}).get_closest_expiration(1) is None
    # we found a suitable lower or equal expiration
    assert MockPasteModule({1337: '', 42: '', False: ''}).get_closest_expiration(84) == 42
    assert MockPasteModule({1337: '', 42: '', False: ''}).get_closest_expiration(False) is False
    assert MockPasteModule({1337: '', 42: ''}).get_closest_expiration(False) == 1337
    assert MockPasteModule({1337: '', 42: '', False: ''}).get_closest_expiration(1336) == 42
    assert MockPasteModule({1337: '', 42: '', False: ''}).get_closest_expiration(1337) == 1337
    assert MockPasteModule({1337: '', 42: '', False: ''}).get_closest_expiration(1338) == 1337
    # this format should work, though of doubtful usage
    assert MockPasteModule([1337, 42, False]).get_closest_expiration(84) == 42
