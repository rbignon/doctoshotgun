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
    BaseObject, Field, StringField, DecimalField, IntField,
    EnumField, Enum,
)
from woob.capabilities.date import DateField

from .base import Account, CapBank

__all__ = [
    'PerVersion', 'PerProviderType', 'Per', 'Investment', 'Pocket',
    'MarketOrderType', 'MarketOrderDirection', 'MarketOrderPayment',
    'MarketOrder', 'CapBankWealth',
]



class PerVersion(Enum):
    PERIN = 'perin'  # "PER individuel", subscribed by the account holder
    PERCOL = 'percol'  # "PER collectif", subscribed by the employer for all employees
    PERCAT = 'percat'  # "PER catégoriel", subscribed by the employer for a category of employees (for example managers)


class PerProviderType(Enum):
    BANK = 'bank'
    INSURER = 'insurer'


class Per(Account):
    """
    Account type dedicated to PER retirement savings plans.
    """

    version = EnumField('Version of PER', PerVersion)
    provider_type = EnumField('Type of account provider', PerProviderType)


class Investment(BaseObject):
    """
    Investment in a financial market.
    """
    CODE_TYPE_ISIN =     u'ISIN'
    CODE_TYPE_AMF =      u'AMF'

    label = StringField('Label of stocks')
    code = StringField('Identifier of the stock')
    code_type = StringField('Type of stock code (ISIN or AMF)')
    description = StringField('Short description of the stock')
    quantity = DecimalField('Quantity of stocks')
    unitprice = DecimalField('Buy price of one stock')
    unitvalue = DecimalField('Current value of one stock')
    valuation = DecimalField('Total current valuation of the Investment')
    vdate = DateField('Value date of the valuation amount')
    diff = DecimalField('Difference between the buy cost and the current valuation')
    diff_ratio = DecimalField('Difference in ratio (1 meaning 100%) between the buy cost and the current valuation')
    portfolio_share = DecimalField('Ratio (1 meaning 100%) of the current amount relative to the total')
    performance_history = Field('History of the performances of the stock (key=years, value=diff_ratio)', dict)
    srri = IntField('Synthetic Risk and Reward Indicator of the stock (from 1 to 7)')
    asset_category = StringField('Category of the stock')
    recommended_period = StringField('Recommended investment period of the stock')

    # International
    original_currency = StringField('Currency of the original amount')
    original_valuation = DecimalField('Original valuation (in another currency)')
    original_unitvalue = DecimalField('Original unitvalue (in another currency)')
    original_unitprice = DecimalField('Original unitprice (in another currency)')
    original_diff = DecimalField('Original diff (in another currency)')

    def __repr__(self):
        return '<Investment label=%r code=%r valuation=%r>' % (self.label, self.code, self.valuation)

    # compatibility alias
    @property
    def diff_percent(self):
        return self.diff_ratio

    @diff_percent.setter
    def diff_percent(self, value):
        self.diff_ratio = value


class PocketCondition(Enum):
    UNKNOWN                    = 0
    DATE                       = 1
    AVAILABLE                  = 2
    RETIREMENT                 = 3
    WEDDING                    = 4
    DEATH                      = 5
    INDEBTEDNESS               = 6
    DIVORCE                    = 7
    DISABILITY                 = 8
    BUSINESS_CREATION          = 9
    BREACH_EMPLOYMENT_CONTRACT = 10
    UNLOCKING_EXCEPTIONAL      = 11
    THIRD_CHILD                = 12
    EXPIRATION_UNEMPLOYMENT    = 13
    PURCHASE_APARTMENT         = 14


class Pocket(BaseObject):
    """
    Pocket
    """
    CONDITION_UNKNOWN                    = PocketCondition.UNKNOWN
    CONDITION_DATE                       = PocketCondition.DATE
    CONDITION_AVAILABLE                  = PocketCondition.AVAILABLE
    CONDITION_RETIREMENT                 = PocketCondition.RETIREMENT
    CONDITION_WEDDING                    = PocketCondition.WEDDING
    CONDITION_DEATH                      = PocketCondition.DEATH
    CONDITION_INDEBTEDNESS               = PocketCondition.INDEBTEDNESS
    CONDITION_DIVORCE                    = PocketCondition.DIVORCE
    CONDITION_DISABILITY                 = PocketCondition.DISABILITY
    CONDITION_BUSINESS_CREATION          = PocketCondition.BUSINESS_CREATION
    CONDITION_BREACH_EMPLOYMENT_CONTRACT = PocketCondition.BREACH_EMPLOYMENT_CONTRACT
    CONDITION_UNLOCKING_EXCEPTIONAL      = PocketCondition.UNLOCKING_EXCEPTIONAL
    CONDITION_THIRD_CHILD                = PocketCondition.THIRD_CHILD
    CONDITION_EXPIRATION_UNEMPLOYMENT    = PocketCondition.EXPIRATION_UNEMPLOYMENT
    CONDITION_PURCHASE_APARTMENT         = PocketCondition.PURCHASE_APARTMENT

    label =             StringField('Label of pocket')
    amount =            DecimalField('Amount of the pocket')
    quantity =          DecimalField('Quantity of stocks')
    availability_date = DateField('Availability date of the pocket')
    condition =         EnumField('Withdrawal condition of the pocket', PocketCondition, default=CONDITION_UNKNOWN)
    investment =        Field('Reference to the investment of the pocket', Investment)


class CapBankWealth(CapBank):
    """
    Capability of bank websites to see investments and pockets.
    """

    def iter_investment(self, account):
        """
        Iter investment of a market account

        :param account: account to get investments
        :type account: :class:`Account`
        :rtype: iter[:class:`Investment`]
        :raises: :class:`AccountNotFound`
        """
        raise NotImplementedError()

    def iter_pocket(self, account):
        """
        Iter pocket

        :param account: account to get pockets
        :type account: :class:`Account`
        :rtype: iter[:class:`Pocket`]
        :raises: :class:`AccountNotFound`
        """
        raise NotImplementedError()

    def iter_market_orders(self, account):
        """
        Iter market orders

        :param account: account to get market orders
        :type account: :class:`Account`
        :rtype: iter[:class:`MarketOrder`]
        :raises: :class:`AccountNotFound`
        """
        raise NotImplementedError()


class MarketOrderType(Enum):
    UNKNOWN = 0
    MARKET = 1
    """Order executed at the current market price"""
    LIMIT = 2
    """Order executed with a maximum or minimum price limit"""
    TRIGGER = 3
    """Order executed when the price reaches a specific value"""


class MarketOrderDirection(Enum):
    UNKNOWN = 0
    BUY = 1
    SALE = 2


class MarketOrderPayment(Enum):
    UNKNOWN = 0
    CASH = 1
    DEFERRED = 2


class MarketOrder(BaseObject):
    """
    Market order
    """

    # Important: a Market Order always corresponds to one (and only one) investment
    label = StringField('Label of the market order')

    # MarketOrder values
    unitprice = DecimalField('Value of the stock at the moment of the market order')
    unitvalue = DecimalField('Current value of the stock associated with the market order')
    ordervalue = DecimalField('Limit value or trigger value, only relevant if the order type is LIMIT or TRIGGER')
    currency = StringField('Currency of the market order - not always the same as account currency')
    quantity = DecimalField('Quantity of stocks in the market order')
    amount = DecimalField('Total amount that has been bought or sold')

    # MarketOrder additional information
    order_type = EnumField('Type of market order', MarketOrderType, default=MarketOrderType.UNKNOWN)
    direction = EnumField('Direction of the market order (buy or sale)', MarketOrderDirection, default=MarketOrderDirection.UNKNOWN)
    payment_method = EnumField('Payment method of the market order', MarketOrderPayment, default=MarketOrderPayment.UNKNOWN)
    date = DateField('Creation date of the market order')
    validity_date = DateField('Validity date of the market order')
    execution_date = DateField('Execution date of the market order (only for market orders that are completed)')
    state = StringField('Current state of the market order (e.g. executed)')
    code = StringField('Identifier of the stock related to the order')
    stock_market = StringField('Stock market on which the order was executed')
