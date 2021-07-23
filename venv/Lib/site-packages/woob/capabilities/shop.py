# -*- coding: utf-8 -*-

# Copyright(C) 2014 Oleg Plakhotniuk
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


from .base import BaseObject, StringField, DecimalField, UserError
from .date import DateField
from .collection import CapCollection


__all__ = ['OrderNotFound', 'Order', 'Payment', 'Item', 'CapShop']


class OrderNotFound(UserError):
    """
    Raised when an order is not found.
    """

    def __init__(self, msg='Order not found'):
        super(OrderNotFound, self).__init__(msg)


class Order(BaseObject):
    """
    Purchase order.
    """
    date     = DateField('Date when the order was placed')
    shipping = DecimalField('Shipping price')
    discount = DecimalField('Discounts')
    tax      = DecimalField('Tax')
    total    = DecimalField('Total')

    def __repr__(self):
        return "<Order id=%r date=%r>" % (self.id, self.date)


class Payment(BaseObject):
    """
    Payment for an order.
    """
    date   = DateField('The date when payment was applied')
    method = StringField('Payment method; e.g. "VISA 1234"')
    amount = DecimalField('Payment amount')

    def __repr__(self):
        return "<Payment date=%r method=%r amount=%r>" % \
            (self.date, self.method, self.amount)


class Item(BaseObject):
    """
    Purchased item within an order.
    """
    label = StringField('Item label')
    price = DecimalField('Item price')

    def __repr__(self):
        return "<Item label=%r price=%r>" % (self.label, self.price)


class CapShop(CapCollection):
    """
    Capability of online shops to see orders history.
    """

    def iter_resources(self, objs, split_path):
        """
        Iter resources.

        Default implementation of this method is to return on top-level
        all orders (by calling :func:`iter_accounts`).

        :param objs: type of objects to get
        :type objs: tuple[:class:`BaseObject`]
        :param split_path: path to discover
        :type split_path: :class:`list`
        :rtype: iter[:class:`BaseObject`]
        """
        if Order in objs:
            self._restrict_level(split_path)
            return self.iter_orders()

    def get_currency(self):
        """
        Get the currency this shop uses.

        :rtype: :class:`str`
        """
        raise NotImplementedError()

    def iter_orders(self):
        """
        Iter history of orders.

        :rtype: iter[:class:`Order`]
        """
        raise NotImplementedError()

    def get_order(self, id):
        """
        Get an order from its ID.

        :param id: ID of the order
        :type id: :class:`str`
        :rtype: :class:`Order`
        :raises: :class:`OrderNotFound`
        """
        raise NotImplementedError()

    def iter_payments(self, order):
        """
        Iter payments of a specific order.

        :param order: order to get payments
        :type order: :class:`Order`
        :rtype: iter[:class:`Payment`]
        :raises: :class:`OrderNotFound`
        """
        raise NotImplementedError()

    def iter_items(self, order):
        """
        Iter items of a specific order.

        :param order: order to get items
        :type order: :class:`Order`
        :rtype: iter[:class:`Item`]
        :raises: :class:`OrderNotFound`
        """
        raise NotImplementedError()
