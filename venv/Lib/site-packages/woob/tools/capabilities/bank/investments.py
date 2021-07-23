# -*- coding: utf-8 -*-

# Copyright(C) 2017 Jonathan Schmidt
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

from __future__ import unicode_literals

import re

from woob.tools.compat import basestring
from woob.capabilities.base import NotAvailable
from woob.capabilities.wealth import Investment
from woob.browser.filters.base import Filter, FilterError, debug

def is_isin_valid(isin):
    """
    Méthode générale
    Table de conversion des lettres en chiffres
    A=10    B=11    C=12    D=13    E=14    F=15    G=16    H=17    I=18
    J=19    K=20    L=21    M=22    N=23    O=24    P=25    Q=26    R=27
    S=28    T=29    U=30    V=31    W=32    X=33    Y=34    Z=35

    1 - Mettre de côté la clé, qui servira de référence à la fin de la vérification.
    2 - Convertir toutes les lettres en nombres via la table de conversion ci-contre. Si le nombre obtenu est supérieur ou égal à 10, prendre les deux chiffres du nombre séparément (exemple : 27 devient 2 et 7).
    3 - Pour chaque chiffre, multiplier sa valeur par deux si sa position est impaire en partant de la droite. Si le nombre obtenu est supérieur ou égal à 10, garder les deux chiffres du nombre séparément (exemple : 14 devient 1 et 4).
    4 - Faire la somme de tous les chiffres.
    5 - Soustraire cette somme de la dizaine supérieure ou égale la plus proche (exemples : si la somme vaut 22, la dizaine « supérieure ou égale » est 30, et la clé vaut donc 8 ; si la somme vaut 30, la dizaine « supérieure ou égale » est 30, et la clé vaut 0 ; si la somme vaut 31, la dizaine « supérieure ou égale » est 40, et la clé vaut 9).
    6 - Comparer la valeur obtenue à la clé mise initialement de côté.

    Étapes 1 et 2 :
    F R 0 0 0 3 5 0 0 0 0 (+ 8 : clé)
    15 27 0 0 0 3 5 0 0 0 0

    Étape 3 : le traitement se fait sur des chiffres
    1 5 2 7 0 0 0 3 5 0 0 0 0
    I P I P I P I P I P I P I : position en partant de la droite (P = Pair, I = Impair)
    2 1 2 1 2 1 2 1 2 1 2 1 2 : coefficient multiplicateur

    2 5 4 7 0 0 0 3 10 0 0 0 0 : résultat

    Étape 4 :
    2 + 5 + 4 + 7 + 0 + 0 + 0 + 3 + (1 + 0)+ 0 + 0 + 0 + 0 = 22

    Étapes 5 et 6 : 30 - 22 = 8 (valeur de la clé)
    """

    if not isinstance(isin, basestring):
        return False
    if not re.match(r'^[A-Z]{2}[A-Z0-9]{9}\d$', isin):
        return False

    isin_in_digits = ''.join(str(ord(x) - ord('A') + 10) if not x.isdigit() else x for x in isin[:-1])
    key = isin[-1:]
    result = ''
    for k, val in enumerate(isin_in_digits[::-1], start=1):
        if k % 2 == 0:
            result = ''.join((result, val))
        else:
            result = ''.join((result, str(int(val)*2)))
    return str(sum(int(x) for x in result) + int(key))[-1] == '0'


def create_french_liquidity(valuation):
    """
    Automatically fills a liquidity investment with label, code and code_type.
    """
    liquidity = Investment()
    liquidity.label = "Liquidités"
    liquidity.code = "XX-liquidity"
    liquidity.code_type = NotAvailable
    liquidity.valuation = valuation
    return liquidity


# These filters can be used to set Investment.code
# and Investment.code_type without having to declare
# obj_code() and obj_code_type() methods in each module

class FormatError(FilterError):
    pass


class IsinCode(Filter):
    """
    Returns the input only if it is a valid ISIN code.
    """
    @debug()
    def filter(self, code):
        if is_isin_valid(code):
            return code
        return self.default_or_raise(FormatError('%r is not a valid ISIN code, no default value was set.' % code))


class IsinType(Filter):
    """
    Returns Investment.CODE_TYPE_ISIN if the input is a valid ISIN code.
    """
    @debug()
    def filter(self, code):
        if is_isin_valid(code):
            return Investment.CODE_TYPE_ISIN
        return NotAvailable
