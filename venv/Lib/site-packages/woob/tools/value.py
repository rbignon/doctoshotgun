# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Romain Bignon
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
import datetime
from collections import OrderedDict

from woob.tools.compat import unicode, basestring

from .misc import to_unicode


__all__ = ['ValuesDict', 'Value', 'ValueBackendPassword', 'ValueInt', 'ValueFloat', 'ValueBool']


class ValuesDict(OrderedDict):
    """
    Ordered dictionarry which can take values in constructor.

    >>> ValuesDict(Value('a', label='Test'), ValueInt('b', label='Test2'))
    """

    def __init__(self, *values):
        super(ValuesDict, self).__init__()
        for v in values:
            self[v.id] = v


class Value(object):
    """
    Value.

    :param label: human readable description of a value
    :type label: str
    :param required: if ``True``, the backend can't load if the key isn't found in its configuration
    :type required: bool
    :param default: an optional default value, used when the key is not in config. If there is no default value and the key
                    is not found in configuration, the **required** parameter is implicitly set
    :param masked: if ``True``, the value is masked. It is useful for applications to know if this key is a password
    :type masked: bool
    :param regexp: if specified, on load the specified value is checked against this regexp, and an error is raised if it doesn't match
    :type regexp: str
    :param choices: if this parameter is set, the value must be in the list
    :type choices: (list,dict)
    :param aliases: mapping of old choices values that should be accepted but not presented
    :type aliases: dict
    :param tiny: the value of choices can be entered by an user (as they are small)
    :type tiny: bool
    :param transient: this value is not persistent (asked only if needed)
    :type transient: bool
    """

    def __init__(self, *args, **kwargs):
        if len(args) > 0:
            self.id = args[0]
        else:
            self.id = ''
        self.label = kwargs.get('label', kwargs.get('description', None))
        self.description = kwargs.get('description', kwargs.get('label', None))
        self.default = kwargs.get('default', None)
        if isinstance(self.default, str):
            self.default = to_unicode(self.default)
        self.regexp = self.get_normalized_regexp(kwargs.get('regexp', None))
        self.choices = kwargs.get('choices', None)
        self.aliases = kwargs.get('aliases')
        if isinstance(self.choices, (list, tuple)):
            self.choices = OrderedDict(((v, v) for v in self.choices))
        self.tiny = kwargs.get('tiny', None)
        self.transient = kwargs.get('transient', None)
        self.masked = kwargs.get('masked', False)
        self.required = kwargs.get('required', self.default is None)
        self._value = kwargs.get('value', None)

    @staticmethod
    def get_normalized_regexp(regexp):
        """ Return normalized regexp adding missing anchors """

        if not regexp:
            return regexp
        if not regexp.startswith('^'):
            regexp = '^' + regexp
        if not regexp.endswith('$'):
            regexp += '$'
        return regexp

    def show_value(self, v):
        if self.masked:
            return u''
        else:
            return v

    def check_valid(self, v):
        """
        Check if the given value is valid.

        :raises: ValueError
        """
        if self.required and v is None:
            raise ValueError('Value is required and thus must be set')
        if v == self.default:
            return
        if v == '' and self.default != '' and (self.choices is None or v not in self.choices):
            raise ValueError('Value can\'t be empty')
        if self.regexp is not None and not re.match(self.regexp, unicode(v) if v is not None else ''):
            raise ValueError('Value "%s" does not match regexp "%s"' % (self.show_value(v), self.regexp))
        if self.choices is not None and v not in self.choices:
            if not self.aliases or v not in self.aliases:
                raise ValueError('Value "%s" is not in list: %s' % (
                    self.show_value(v), ', '.join(unicode(s) for s in self.choices)))

    def load(self, domain, v, requests):
        """
        Load value.

        :param domain: what is the domain of this value
        :type domain: str
        :param v: value to load
        :param requests: list of woob requests
        :type requests: woob.core.requests.Requests
        """
        return self.set(v)

    def set(self, v):
        """
        Set a value.
        """
        if isinstance(v, str):
            v = to_unicode(v)
        self.check_valid(v)
        if self.aliases and v in self.aliases:
            v = self.aliases[v]
        self._value = v

    def dump(self):
        """
        Dump value to be stored.
        """
        return self.get()

    def get(self):
        """
        Get the value.
        """
        return self._value


class ValueTransient(Value):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('transient', True)
        kwargs.setdefault('default', None)
        kwargs.setdefault('required', False)
        super(ValueTransient, self).__init__(*args, **kwargs)

    def dump(self):
        return ''


class ValueBackendPassword(Value):
    _domain = None
    _requests = None
    _stored = True

    def __init__(self, *args, **kwargs):
        kwargs['masked'] = kwargs.pop('masked', True)
        self.noprompt = kwargs.pop('noprompt', False)
        super(ValueBackendPassword, self).__init__(*args, **kwargs)
        self.default = kwargs.get('default', '')

    def load(self, domain, password, requests):
        self.check_valid(password)
        self._domain = domain
        self._value = to_unicode(password)
        self._requests = requests

    def check_valid(self, passwd):
        if passwd == '':
            # always allow empty passwords
            return True
        return super(ValueBackendPassword, self).check_valid(passwd)

    def set(self, passwd):
        self.check_valid(passwd)
        if passwd is None:
            # no change
            return
        self._value = ''
        if passwd == '':
            return
        if self._domain is None:
            self._value = to_unicode(passwd)
            return

        self._value = to_unicode(passwd)

    def dump(self):
        if self._stored:
            return self._value
        else:
            return ''

    def get(self):
        if self._value != '' or self._domain is None:
            return self._value

        passwd = None

        if passwd is not None:
            # Password has been read in the keyring.
            return to_unicode(passwd)

        # Prompt user to enter password by hand.
        if not self.noprompt and self._requests:
            self._value = self._requests.request('login', self._domain, self)
            if self._value is None:
                self._value = ''
            else:
                self._value = to_unicode(self._value)
                self._stored = False
        return self._value


class ValueInt(Value):
    def __init__(self, *args, **kwargs):
        kwargs['regexp'] = '^\d+$'
        super(ValueInt, self).__init__(*args, **kwargs)
        self.default = kwargs.get('default', 0)

    def get(self):
        return int(self._value)


class ValueFloat(Value):
    def __init__(self, *args, **kwargs):
        kwargs['regexp'] = '^[\d\.]+$'
        super(ValueFloat, self).__init__(*args, **kwargs)
        self.default = kwargs.get('default', 0.0)

    def check_valid(self, v):
        try:
            float(v)
        except ValueError:
            raise ValueError('Value "%s" is not a float value' % self.show_value(v))

    def get(self):
        return float(self._value)


class ValueBool(Value):
    def __init__(self, *args, **kwargs):
        kwargs['choices'] = {'y': 'True', 'n': 'False'}
        super(ValueBool, self).__init__(*args, **kwargs)
        self.default = kwargs.get('default', False)

    def check_valid(self, v):
        if not isinstance(v, bool) and \
            unicode(v).lower() not in ('y', 'yes', '1', 'true',  'on',
                                       'n', 'no',  '0', 'false', 'off'):
            raise ValueError('Value "%s" is not a boolean (y/n)' % self.show_value(v))

    def get(self):
        return (isinstance(self._value, bool) and self._value) or \
                unicode(self._value).lower() in ('y', 'yes', '1', 'true', 'on')


class ValueDate(Value):
    DEFAULT_FORMAT = '%Y-%m-%d'

    def __init__(self, *args, **kwargs):
        formats = tuple(kwargs.pop('formats', ()))
        super(ValueDate, self).__init__(*args, **kwargs)

        if formats:
            self.preferred_format = formats[0]
        else:
            self.preferred_format = self.DEFAULT_FORMAT
        self.accepted_formats = (self.DEFAULT_FORMAT,) + formats

    def _parse(self, v):
        for format in self.accepted_formats:
            try:
                dateval = datetime.datetime.strptime(v, format).date()
            except ValueError:
                continue
            return dateval

        raise ValueError('Value "%s" does not match format in %s' % (self.show_value(v), self.accepted_formats))

    def check_valid(self, v):
        if self.required and not v:
            raise ValueError('Value is required and thus must be set')

    def load(self, domain, v, requests):
        self.check_valid(v)
        if not v:
            self._value = None
            return
        if isinstance(v, basestring):
            v = self._parse(v)
        if isinstance(v, datetime.date):
            self._value = v
        else:
            raise ValueError('Value %r is not of the proper type' % self.show_value(v))

    def dump(self):
        if self._value:
            return self._value.strftime(self.DEFAULT_FORMAT)

    def set(self, v):
        self.load(None, v, None)

    def get_as_string(self):
        if not self._value:
            return self._value

        return self._value.strftime(self.preferred_format)
