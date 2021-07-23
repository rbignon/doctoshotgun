# -*- coding: utf-8 -*-

# Copyright(C) 2010-2016 Romain Bignon
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

from woob.capabilities.base import (
    BaseObject, StringField, DecimalField, Currency,
    Capability,
)
from woob.capabilities.date import DateField


__all__ = [
    'Rate', 'CapCurrencyRate',
]


class Rate(BaseObject, Currency):
    """
    Currency exchange rate.
    """

    currency_from = StringField('The currency to which exchange rates are relative to. When converting 1 EUR to X HUF, currency_fom is EUR.)', default=None)
    currency_to =   StringField('The currency is converted to. When converting 1 EUR to X HUF, currency_to is HUF.)', default=None)
    value =          DecimalField('Exchange rate')
    datetime =      DateField('Collection date and time')


class CapCurrencyRate(Capability):
    """
    Capability of bank websites to get currency exchange rates.
    """

    def iter_currencies(self):
        """
        Iter available currencies.

        :rtype: iter[:class:`Currency`]
        """
        raise NotImplementedError()

    def get_rate(self, currency_from, currency_to):
        """
        Get exchange rate.

        :param currency_from: currency to which exchange rate is relative to
        :type currency_from: :class:`Currency`
        :param currency_to: currency is converted to
        :type currency_to: :class`Currency`
        :rtype: :class:`Rate`
        """
        raise NotImplementedError()
