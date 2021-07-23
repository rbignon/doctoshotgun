# -*- coding: utf-8 -*-

# Copyright(C) 2009-2015  Bezleputh
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

from woob.browser.filters.standard import _Filter, Field, debug
from woob.capabilities.base import empty
from decimal import Decimal


class PricePerMeterFilter(_Filter):
    """
    Filter that help to fill PricePerMeter field
    """
    def __init__(self):
        super(PricePerMeterFilter, self).__init__()

    @debug()
    def __call__(self, item):
        cost = Field('cost')(item)
        area = Field('area')(item)
        if not (empty(cost) or empty(area)):
            return Decimal(cost or 0) / Decimal(area or 1)
        return Decimal(0)
