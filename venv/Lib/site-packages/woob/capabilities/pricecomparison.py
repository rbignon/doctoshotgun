# -*- coding: utf-8 -*-

# Copyright(C) 2012 Romain Bignon
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


from .base import Capability, BaseObject, Field, DecimalField, \
                  StringField, UserError
from .date import DateField

__all__ = ['Shop', 'Price', 'Product', 'CapPriceComparison']


class PriceNotFound(UserError):
    """
    Raised when a price is not found
    """

    def __init__(self, msg='Price not found'):
        super(PriceNotFound, self).__init__(msg)


class Product(BaseObject):
    """
    A product.
    """
    name =      StringField('Name of product')


class Shop(BaseObject):
    """
    A shop where the price is.
    """
    name =      StringField('Name of shop')
    location =  StringField('Location of the shop')
    info =      StringField('Information about the shop')


class Price(BaseObject):
    """
    Price.
    """
    date =      DateField('Date when this price has been published')
    cost =      DecimalField('Cost of the product in this shop')
    currency =  StringField('Currency of the price')
    message =   StringField('Message related to this price')
    shop =      Field('Shop information', Shop)
    product =   Field('Product', Product)


class CapPriceComparison(Capability):
    """
    Capability for price comparison websites.
    """

    def search_products(self, pattern=None):
        """
        Search products from a pattern.

        :param pattern: pattern to search
        :type pattern: str
        :rtype: iter[:class:`Product`]
        """
        raise NotImplementedError()

    def iter_prices(self, products):
        """
        Iter prices for a product.

        :param product: product to search
        :type product: :class:`Product`
        :rtype: iter[:class:`Price`]
        """
        raise NotImplementedError()

    def get_price(self, id):
        """
        Get a price from an ID

        :param id: ID of price
        :type id: str
        :rtype: :class:`Price`
        """
        raise NotImplementedError()
