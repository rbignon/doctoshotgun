# -*- coding: utf-8 -*-

# Copyright(C) 2010-2013 Christophe Benz, Romain Bignon, Julien Hebert
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

from collections import OrderedDict
import warnings
import re
from decimal import Decimal
from copy import deepcopy, copy
import sys

from woob.tools.compat import unicode, long, with_metaclass, StrConv
from woob.tools.misc import to_unicode


__all__ = ['UserError', 'FieldNotFound', 'NotAvailable', 'FetchError',
           'NotLoaded', 'Capability', 'Field', 'IntField', 'DecimalField',
           'FloatField', 'StringField', 'BytesField', 'BoolField',
           'Enum', 'EnumField',
           'empty', 'BaseObject']


class EnumMeta(type):
    @classmethod
    def __prepare__(mcs, name, bases, **kwargs):
        # in python3.6, default namespace keeps declaration order
        # in python>=3 but <3.6, force ordered namespace
        # doesn't work in python2
        return OrderedDict()

    def __init__(cls, name, bases, attrs, *args, **kwargs):
        super(EnumMeta, cls).__init__(name, bases, attrs, *args, **kwargs)
        attrs = [(k, v) for k, v in attrs.items() if not callable(v) and not k.startswith('__')]
        if sys.version_info.major < 3:
            # can't have original declaration order, at least sort by value
            attrs.sort(key=lambda kv: kv[1])
        cls.__members__ = OrderedDict(attrs)

    def __setattr__(cls, name, value):
        super(EnumMeta, cls).__setattr__(name, value)
        if not callable(value) and not name.startswith('__'):
            cls.__members__[name] = value

    def __call__(cls, *args, **kwargs):
        raise ValueError("Enum type can't be instanciated")

    @property
    def _items(cls):
        return cls.__members__.items()

    @property
    def _keys(cls):
        return cls.__members__.keys()

    @property
    def _values(cls):
        return cls.__members__.values()

    @property
    def _types(cls):
        return set(map(type, cls._values))

    def __iter__(cls):
        return iter(cls.__members__.values())

    def __len__(cls):
        return len(cls.__members__)

    def __contains__(cls, value):
        return value in cls.__members__.values()

    def __getitem__(cls, k):
        return cls.__members__[k]


class Enum(with_metaclass(EnumMeta, object)):
    pass


def empty(value):
    """
    Checks if a value is empty (None, NotLoaded or NotAvailable).

    :rtype: :class:`bool`
    """
    return value is None or isinstance(value, EmptyType)


def find_object(mylist, error=None, **kwargs):
    """
    Very simple tools to return an object with the matching parameters in
    kwargs.
    """
    for a in mylist:
        for key, value in kwargs.items():
            if getattr(a, key) != value:
                break
        else:
            return a

    if error is not None:
        raise error()
    return None


def strict_find_object(mylist, error=None, **kwargs):
    """
    Tools to return an object with the matching parameters in kwargs.
    Parameters with empty value are skipped
    """
    kwargs = {k: v for k, v in kwargs.items() if not empty(v)}
    if kwargs:
        return find_object(mylist, error=error, **kwargs)

    if error is not None:
        raise error()


class UserError(Exception):
    """
    Exception containing an error message for user.
    """


class FieldNotFound(Exception):
    """
    A field isn't found.

    :param obj: object
    :type obj: :class:`BaseObject`
    :param field: field not found
    :type field: :class:`Field`
    """

    def __init__(self, obj, field):
        super(FieldNotFound, self).__init__(u'Field "%s" not found for object %s' % (field, obj))


class ConversionWarning(UserWarning):
    """
    A field's type was changed when setting it.
    Ideally, the module should use the right type before setting it.
    """
    pass


class AttributeCreationWarning(UserWarning):
    """
    A non-field attribute has been created with a name not
    prefixed with a _.
    """


class EmptyType(object):
    """
    Parent class for NotAvailableType, NotLoadedType and FetchErrorType.
    """

    def __str__(self):
        return repr(self)

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

    def __nonzero__(self):
        return False

    __bool__ = __nonzero__


class NotAvailableType(EmptyType):
    """
    NotAvailable is a constant to use on non available fields.
    """

    def __repr__(self):
        return 'NotAvailable'

    def __unicode__(self):
        return u'Not available'


NotAvailable = NotAvailableType()


class NotLoadedType(EmptyType):
    """
    NotLoaded is a constant to use on not loaded fields.

    When you use :func:`woob.tools.backend.Module.fillobj` on a object based on :class:`BaseObject`,
    it will request all fields with this value.
    """

    def __repr__(self):
        return 'NotLoaded'

    def __unicode__(self):
        return u'Not loaded'


NotLoaded = NotLoadedType()


class FetchErrorType(EmptyType):
    """
    FetchError is a constant to use when parsing a non-mandatory field raises an exception.
    """

    def __repr__(self):
        return 'FetchError'

    def __unicode__(self):
        return u'Not mandatory'


FetchError = FetchErrorType()


class Capability(object):
    """
    This is the base class for all capabilities.

    A capability may define abstract methods (which raise :class:`NotImplementedError`)
    with an explicit docstring to tell backends how to implement them.

    Also, it may define some *objects*, using :class:`BaseObject`.
    """


class Field(object):
    """
    Field of a :class:`BaseObject` class.

    :param doc: docstring of the field
    :type doc: :class:`str`
    :param args: list of types accepted
    :param default: default value of this field. If not specified, :class:`NotLoaded` is used.
    """
    _creation_counter = 0

    def __init__(self, doc, *args, **kwargs):
        self.types = ()
        self.value = kwargs.get('default', NotLoaded)
        self.doc = doc
        self.mandatory = kwargs.get('mandatory', True)

        for arg in args:
            if isinstance(arg, type) or isinstance(arg, str):
                self.types += (arg,)
            else:
                raise TypeError('Arguments must be types or strings of type name')

        self._creation_counter = Field._creation_counter
        Field._creation_counter += 1

    def convert(self, value):
        """
        Convert value to the wanted one.
        """
        return value


class IntField(Field):
    """
    A field which accepts only :class:`int` and :class:`long` types.
    """

    def __init__(self, doc, **kwargs):
        super(IntField, self).__init__(doc, int, long, **kwargs)

    def convert(self, value):
        return int(value)


class BoolField(Field):
    """
    A field which accepts only :class:`bool` type.
    """

    def __init__(self, doc, **kwargs):
        super(BoolField, self).__init__(doc, bool, **kwargs)

    def convert(self, value):
        return bool(value)


class DecimalField(Field):
    """
    A field which accepts only :class:`decimal` type.
    """

    def __init__(self, doc, **kwargs):
        super(DecimalField, self).__init__(doc, Decimal, **kwargs)

    def convert(self, value):
        if isinstance(value, Decimal):
            return value
        return Decimal(value)


class FloatField(Field):
    """
    A field which accepts only :class:`float` type.
    """

    def __init__(self, doc, **kwargs):
        super(FloatField, self).__init__(doc, float, **kwargs)

    def convert(self, value):
        return float(value)


class StringField(Field):
    """
    A field which accepts only :class:`unicode` strings.
    """

    def __init__(self, doc, **kwargs):
        super(StringField, self).__init__(doc, unicode, **kwargs)

    def convert(self, value):
        return to_unicode(value)


class BytesField(Field):
    """
    A field which accepts only :class:`bytes` strings.
    """

    def __init__(self, doc, **kwargs):
        super(BytesField, self).__init__(doc, bytes, **kwargs)

    def convert(self, value):
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        return bytes(value)


class EnumField(Field):
    def __init__(self, doc, enum, **kwargs):
        if not issubclass(enum, Enum):
            raise TypeError('invalid enum type: %r' % enum)
        super(EnumField, self).__init__(doc, *enum._types, **kwargs)
        self.enum = enum

    def convert(self, value):
        if value not in self.enum._values:
            raise ValueError('value %r does not belong to enum %s' % (value, self.enum))
        return value


class _BaseObjectMeta(type):
    def __new__(cls, name, bases, attrs):
        fields = [(field_name, attrs.pop(field_name)) for field_name, obj in list(attrs.items()) if isinstance(obj, Field)]
        fields.sort(key=lambda x: x[1]._creation_counter)

        new_class = super(_BaseObjectMeta, cls).__new__(cls, name, bases, attrs)
        if new_class._fields is None:
            new_class._fields = OrderedDict()
        else:
            new_class._fields = deepcopy(new_class._fields)
        new_class._fields.update(fields)

        if new_class.__doc__ is None:
            new_class.__doc__ = ''
        for name, field in fields:
            doc = '(%s) %s' % (', '.join([':class:`%s`' % v.__name__ if isinstance(v, type) else v for v in field.types]), field.doc)
            if field.value is not NotLoaded:
                doc += ' (default: %s)' % field.value
            new_class.__doc__ += '\n:var %s: %s' % (name, doc)
        return new_class


class BaseObject(with_metaclass(_BaseObjectMeta, StrConv, object)):
    """
    This is the base class for a capability object.

    A capability interface may specify to return several kind of objects, to formalise
    retrieved information from websites.

    As python is a flexible language where variables are not typed, we use a system to
    force backends to set wanted values on all fields. To do that, we use the :class:`Field`
    class and all derived ones.

    For example::

        class Transfer(BaseObject):
            " Transfer from an account to a recipient.  "

            amount =    DecimalField('Amount to transfer')
            date =      Field('Date of transfer', basestring, date, datetime)
            origin =    Field('Origin of transfer', int, long, basestring)
            recipient = Field('Recipient', int, long, basestring)

    The docstring is mandatory.
    """

    id = None
    backend = None
    url = StringField('url')
    _fields = None

    def __init__(self, id=u'', url=NotLoaded, backend=None):
        self.id = to_unicode(id) if id is not None else u''
        self.backend = backend
        self._fields = deepcopy(self._fields)
        self.__setattr__('url', url)

    @property
    def fullid(self):
        """
        Full ID of the object, in form '**ID@backend**'.
        """
        return '%s@%s' % (self.id, self.backend)

    def __iscomplete__(self):
        """
        Return True if the object is completed.

        It is useful when the object is a field of an other object which is
        going to be filled.

        The default behavior is to iter on fields (with iter_fields) and if
        a field is NotLoaded, return False.
        """
        for key, value in self.iter_fields():
            if value is NotLoaded:
                return False
        return True

    def copy(self):
        obj = copy(self)
        obj._fields = copy(self._fields)
        for k in obj._fields:
            obj._fields[k] = copy(obj._fields[k])
        return obj

    def __deepcopy__(self, memo):
        return self.copy()

    def set_empty_fields(self, value, excepts=()):
        """
        Set the same value on all empty fields.

        :param value: value to set on all empty fields
        :param excepts: if specified, do not change fields listed
        """
        for key, old_value in self.iter_fields():
            if empty(old_value) and key not in excepts:
                setattr(self, key, value)

    def iter_fields(self):
        """
        Iterate on the fields keys and values.

        Can be overloaded to iterate on other things.

        :rtype: iter[(key, value)]
        """

        if hasattr(self, 'id') and self.id is not None:
            yield 'id', self.id
        for name, field in self._fields.items():
            yield name, field.value

    def __eq__(self, obj):
        if isinstance(obj, BaseObject):
            return self.backend == obj.backend and self.id == obj.id
        else:
            return False

    def __getattr__(self, name):
        if self._fields is not None and name in self._fields:
            return self._fields[name].value
        else:
            raise AttributeError("'%s' object has no attribute '%s'" % (
                self.__class__.__name__, name))

    def __setattr__(self, name, value):
        try:
            attr = (self._fields or {})[name]
        except KeyError:
            if name not in dir(self) and not name.startswith('_'):
                warnings.warn('Creating a non-field attribute %s. Please prefix it with _' % name,
                              AttributeCreationWarning, stacklevel=2)
            object.__setattr__(self, name, value)
        else:
            if not empty(value):
                try:
                    # Try to convert value to the wanted one.
                    nvalue = attr.convert(value)
                    # If the value was converted
                    if nvalue is not value:
                        warnings.warn('Value %s was converted from %s to %s' %
                                      (name, type(value), type(nvalue)),
                                      ConversionWarning, stacklevel=2)
                    value = nvalue
                except Exception:
                    # error during conversion, it will probably not
                    # match the wanted following types, so we'll
                    # raise ValueError.
                    pass
            from collections import deque
            actual_types = ()
            for v in attr.types:
                if isinstance(v, str):
                    # the following is a (almost) copy/paste from
                    # https://stackoverflow.com/questions/11775460/lexical-cast-from-string-to-type
                    q = deque([object])
                    while q:
                        t = q.popleft()
                        if t.__name__ == v:
                            actual_types += (t,)
                        else:
                            try:
                                # keep looking!
                                q.extend(t.__subclasses__())
                            except TypeError:
                                # type.__subclasses__ needs an argument for
                                # whatever reason.
                                if t is type:
                                    continue
                                else:
                                    raise
                else:
                    actual_types += (v,)

            if not isinstance(value, actual_types) and not empty(value):
                raise ValueError(
                    'Value for "%s" needs to be of type %r, not %r' % (
                        name, actual_types, type(value)))
            attr.value = value

    def __delattr__(self, name):
        try:
            self._fields.pop(name)
        except KeyError:
            object.__delattr__(self, name)

    def to_dict(self):
        def iter_decorate(d):
            for key, value in d:
                if key == 'id' and self.backend is not None:
                    value = self.fullid
                yield key, value

        fields_iterator = self.iter_fields()
        return OrderedDict(iter_decorate(fields_iterator))

    def __getstate__(self):
        d = self.to_dict()
        d.update((k, v) for k, v in self.__dict__.items() if k != '_fields')
        return d

    @classmethod
    def from_dict(cls, values, backend=None):
        self = cls()

        for attr in values:
            setattr(self, attr, values[attr])

        return self

    def __setstate__(self, state):
        self._fields = deepcopy(self._fields)  # because yaml does not call __init__
        for k in state:
            setattr(self, k, state[k])

    if sys.version_info.major >= 3:
        def __dir__(self):
            return list(super(BaseObject, self).__dir__()) + list(self._fields.keys())


class Currency(object):
    CURRENCIES = OrderedDict([
        (u'EUR', (u'€', u'EURO', u'EUROS')),
        (u'CHF', (u'CHF',)),
        (u'USD', (u'$', u'$US')),
        (u'GBP', (u'£',)),
        (u'LBP', (u'ل.ل',)),
        (u'AED', (u'AED',)),
        (u'XOF', (u'XOF',)),
        (u'RUB', (u'руб',)),
        (u'SGD', (u'SGD',)),
        (u'BRL', (u'R$',)),
        (u'MXN', (u'$',)),
        (u'JPY', (u'¥',)),
        (u'TRY', (u'₺', u'TRY')),
        (u'RON', (u'lei',)),
        (u'COP', (u'$',)),
        (u'NOK', (u'kr',)),
        (u'CNY', (u'¥',)),
        (u'RSD', (u'din',)),
        (u'ZAR', (u'rand',)),
        (u'MYR', (u'RM',)),
        (u'HUF', (u'Ft',)),
        (u'HKD', (u'HK$',)),
        (u'TWD', (u'NT$',)),
        (u'QAR', (u'QR',)),
        (u'MAD', (u'MAD',)),
        (u'ARS', (u'ARS',)),
        (u'AUD', (u'AUD',)),
        (u'CAD', (u'CAD',)),
        (u'NZD', (u'NZD',)),
        (u'BHD', (u'BHD',)),
        (u'SEK', (u'SEK',)),
        (u'DKK', (u'DKK',)),
        (u'LUF', (u'LUF',)),
        (u'KZT', (u'KZT',)),
        (u'PLN', (u'PLN',)),
        (u'ILS', (u'ILS',)),
        (u'THB', (u'THB',)),
        (u'INR', (u'₹', u'INR')),
        (u'PEN', (u'S/',)),
        (u'IDR', (u'Rp',)),
        (u'KWD', (u'KD',)),
        (u'KRW', (u'₩',)),
        (u'CZK', (u'Kč',)),
        (u'EGP', (u'E£',)),
        (u'ISK', (u'Íkr', u'kr')),
        (u'XPF', (u'XPF',)),
        (u'SAR', (u'SAR',)),
    ])

    EXTRACTOR = re.compile(r'[()\d\s,\.\-]', re.UNICODE)

    @classmethod
    def get_currency(klass, text):
        u"""
        >>> Currency.get_currency(u'42')
        None
        >>> Currency.get_currency(u'42 €')
        u'EUR'
        >>> Currency.get_currency(u'$42')
        u'USD'
        >>> Currency.get_currency(u'42.000,00€')
        u'EUR'
        >>> Currency.get_currency(u'$42 USD')
        u'USD'
        >>> Currency.get_currency(u'%42 USD')
        u'USD'
        >>> Currency.get_currency(u'US1D')
        None
        """
        curtexts = klass.EXTRACTOR.sub(' ', text.upper()).split()

        for currency, symbols in klass.CURRENCIES.items():
            for curtext in curtexts:
                if curtext == currency:
                    return currency
                for symbol in symbols:
                    if curtext == symbol:
                        return currency
        return None

    @classmethod
    def currency2txt(klass, currency):
        _currency = klass.CURRENCIES.get(currency, (u'',))
        return _currency[0]


def capability_to_string(capability_klass):
    return re.match(r'^Cap(\w+)', capability_klass.__name__).group(1).lower()


class DeprecatedFieldWarning(UserWarning):
    pass
