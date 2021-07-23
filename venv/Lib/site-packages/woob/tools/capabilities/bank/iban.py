# -*- coding: utf-8 -*-

# Copyright(C) 2016  Romain Bignon
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


import re

from woob.tools.compat import unicode

_country2length = dict(
    AL=28, AD=24, AT=20, AZ=28, BE=16, BH=22, BA=20, BR=29,
    BG=22, CR=21, HR=21, CY=28, CZ=24, DK=18, DO=28, EE=20,
    FO=18, FI=18, FR=27, GE=22, DE=22, GI=23, GR=27, GL=18,
    GT=28, HU=28, IS=26, IE=22, IL=23, IT=27, KZ=20, KW=30,
    LV=21, LB=28, LI=21, LT=20, LU=20, MK=19, MT=31, MR=27,
    MU=30, MC=27, MD=24, ME=22, NL=18, NO=15, PK=24, PS=29,
    PL=28, PT=25, RO=24, SM=27, SA=24, RS=22, SK=24, SI=19,
    ES=24, SE=24, CH=21, TN=24, TR=26, AE=23, GB=22, VG=24,
    MA=28, JO=30, TL=23, XK=20, QA=29,
)

def clean(iban):
    return iban.replace(' ','').replace('\t', '')

def is_iban_valid(iban):
    # Ensure upper alphanumeric input.
    iban = clean(iban)
    if not re.match(r'^[A-Z]{2}\d{2}[\dA-Z]+$', iban):
        return False

    # Validate country code against expected length.
    if iban[:2] in _country2length and len(iban) != _country2length[iban[:2]]:
        return False

    digits = iban2numeric(iban)
    return digits % 97 == 1

def iban2numeric(iban):
    # Shift and convert.
    iban = iban[4:] + iban[:4]
    # BASE 36: 0..9,A..Z -> 0..35
    digits = int(''.join(str(int(ch, 36)) for ch in iban))
    return digits

def find_iban_checksum(iban):
    iban = iban[:2] + '00' + iban[4:]
    digits = str(iban2numeric(iban))
    checksum = 0
    for char in digits:
        checksum *= 10
        checksum += int(char)
        checksum %= 97
    return 98-checksum

def rebuild_iban(iban):
    return unicode(iban[:2] + ('%02d' % find_iban_checksum(iban)) + iban[4:])

def rib2iban(rib):
    return rebuild_iban('FR00' + rib)

def find_rib_checksum(bank, counter, account):
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    digits = '12345678912345678923456789'
    account = ''.join([(char if char.isdigit() else digits[letters.find(char.upper())]) for char in account])
    rest = (89*int(bank) + 15*int(counter) + 3*int(account)) % 97
    return 97 - rest

def is_rib_valid(rib):
    if len(rib) != 23:
        return False

    return find_rib_checksum(rib[:5], rib[5:10], rib[10:21]) == int(rib[21:23])

def rebuild_rib(rib):
    rib = clean(rib)
    assert len(rib) >= 21
    key = find_rib_checksum(rib[:5], rib[5:10], rib[10:21])
    return unicode(rib[:21] + ('%02d' % key))


def test():
    assert rebuild_iban('FR0013048379405300290000355') == "FR7613048379405300290000355"
    assert rebuild_iban('GB87BARC20658244971655') == "GB87BARC20658244971655"
    assert rebuild_rib('30003021990005077567600') == "30003021990005077567667"
