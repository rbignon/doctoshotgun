# -*- coding: utf-8 -*-

# Copyright(C) 2020      Quentin Defenouillere
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

# Temporary imports before moving these classes in this file
from woob.capabilities.bank.wealth import (
    PerVersion, PerProviderType, Per, Investment, Pocket,
    MarketOrderType, MarketOrderDirection, MarketOrderPayment,
    MarketOrder, CapBankWealth,
)

__all__ = [
    'PerVersion', 'PerProviderType', 'Per', 'Investment', 'Pocket',
    'MarketOrderType', 'MarketOrderDirection', 'MarketOrderPayment',
    'MarketOrder', 'CapBankWealth',
]
