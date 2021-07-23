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


import os
from copy import copy
from threading import RLock

from woob.capabilities.base import BaseObject, Capability, FieldNotFound, NotAvailable, NotLoaded
from woob.exceptions import ModuleInstallError
from woob.tools.compat import basestring, getproxies
from woob.tools.log import getLogger
from woob.tools.json import json
from woob.tools.misc import iter_fields
from woob.tools.value import ValuesDict

__all__ = ['BackendStorage', 'BackendConfig', 'Module']


class BackendStorage(object):
    """
    This is an abstract layer to store data in storages (:mod:`woob.tools.storage`)
    easily.

    It is instancied automatically in constructor of :class:`Module`, in the
    :attr:`Module.storage` attribute.

    :param name: name of backend
    :param storage: storage object
    :type storage: :class:`woob.tools.storage.IStorage`
    """

    def __init__(self, name, storage):
        self.name = name
        self.storage = storage

    def set(self, *args):
        """
        Set value in the storage.

        Example:

        >>> from woob.tools.storage import StandardStorage
        >>> backend = BackendStorage('blah', StandardStorage('/tmp/cfg'))
        >>> backend.storage.set('config', 'nb_of_threads', 10)  # doctest: +SKIP
        >>>

        :param args: the path where to store value
        """
        if self.storage:
            return self.storage.set('backends', self.name, *args)

    def delete(self, *args):
        """
        Delete a value from the storage.

        :param args: path to delete.
        """
        if self.storage:
            return self.storage.delete('backends', self.name, *args)

    def get(self, *args, **kwargs):
        """
        Get a value or a dict of values in storage.

        Example:

        >>> from woob.tools.storage import StandardStorage
        >>> backend = BackendStorage('blah', StandardStorage('/tmp/cfg'))
        >>> backend.storage.get('config', 'nb_of_threads')  # doctest: +SKIP
        10
        >>> backend.storage.get('config', 'unexistant', 'path', default='lol')  # doctest: +SKIP
        'lol'
        >>> backend.storage.get('config')  # doctest: +SKIP
        {'nb_of_threads': 10, 'other_things': 'blah'}

        :param args: path to get
        :param default: if specified, default value when path is not found
        """
        if self.storage:
            return self.storage.get('backends', self.name, *args, **kwargs)
        else:
            return kwargs.get('default', None)

    def load(self, default):
        """
        Load storage.

        It is made automatically when your backend is created, and use the
        ``STORAGE`` class attribute as default.

        :param default: this is the default tree if storage is empty
        :type default: :class:`dict`
        """
        if self.storage:
            return self.storage.load('backends', self.name, default)

    def save(self):
        """
        Save storage.
        """
        if self.storage:
            return self.storage.save('backends', self.name)


class BackendConfig(ValuesDict):
    """
    Configuration of a backend.

    This class is firstly instanced as a :class:`woob.tools.value.ValuesDict`,
    containing some :class:`woob.tools.value.Value` (and derivated) objects.

    Then, using the :func:`load` method will load configuration from file and
    create a copy of the :class:`BackendConfig` object with the loaded values.
    """
    modname = None
    instname = None
    woob = None

    def load(self, woob, modname, instname, config, nofail=False):
        """
        Load configuration from dict to create an instance.

        :param woob: woob object
        :type woob: :class:`woob.core.woob.Woob`
        :param modname: name of the module
        :type modname: :class:`str`
        :param instname: name of this backend
        :type instname: :class:`str`
        :param params: parameters to load
        :type params: :class:`dict`
        :param nofail: if true, this call can't fail
        :type nofail: :class:`bool`
        :rtype: :class:`BackendConfig`
        """
        cfg = BackendConfig()
        cfg.modname = modname
        cfg.instname = instname
        cfg.woob = woob
        for name, field in self.items():
            value = config.get(name, None)

            if value is None:
                if not nofail and field.required:
                    raise Module.ConfigError('Backend(%s): Configuration error: Missing parameter "%s" (%s)'
                                                  % (cfg.instname, name, field.description))
                value = field.default

            field = copy(field)
            try:
                field.load(cfg.instname, value, cfg.woob.requests)
            except ValueError as v:
                if not nofail:
                    raise Module.ConfigError(
                        'Backend(%s): Configuration error for field "%s": %s' % (cfg.instname, name, v))

            cfg[name] = field
        return cfg

    def dump(self):
        """
        Dump config in a dictionary.

        :rtype: :class:`dict`
        """
        settings = {}
        for name, value in self.items():
            if not value.transient:
                settings[name] = value.dump()
        return settings

    def save(self, edit=True, params=None):
        """
        Save backend config.

        :param edit: if true, it changes config of an existing backend
        :type edit: :class:`bool`
        :param params: if specified, params to merge with the ones of the current object
        :type params: :class:`dict`
        """
        assert self.modname is not None
        assert self.instname is not None
        assert self.woob is not None

        dump = self.dump()
        if params is not None:
            dump.update(params)

        if edit:
            self.woob.backends_config.edit_backend(self.instname, dump)
        else:
            self.woob.backends_config.add_backend(self.instname, self.modname, dump)


class Module(object):
    """
    Base class for modules.

    You may derivate it, and also all capabilities you want to implement.

    :param woob: woob instance
    :type woob: :class:`woob.core.woob.Woob`
    :param name: name of backend
    :type name: :class:`str`
    :param config: configuration of backend
    :type config: :class:`dict`
    :param storage: storage object
    :type storage: :class:`woob.tools.storage.IStorage`
    :param logger: logger
    :type logger: :class:`logging.Logger`
    """
    # Module name.
    NAME = None
    """Name of the maintainer of this module."""

    MAINTAINER = u'<unspecified>'

    EMAIL = '<unspecified>'
    """Email address of the maintainer."""

    VERSION = '<unspecified>'
    """Version of module (for information only)."""

    DESCRIPTION = '<unspecified>'
    """Description"""

    # License of this module.
    LICENSE = '<unspecified>'

    CONFIG = BackendConfig()
    """Configuration required for backends.

    Values must be woob.tools.value.Value objects.
    """

    STORAGE = {}
    """Storage"""

    BROWSER = None
    """Browser class"""

    ICON = None
    """URL to an optional icon.

    If you want to create your own icon, create a 'favicon.png' icon in
    the module's directory, and keep the ICON value to None.
    """

    OBJECTS = {}
    """Supported objects to fill

    The key is the class and the value the method to call to fill
    Method prototype: method(object, fields)
    When the method is called, fields are only the one which are
    NOT yet filled.
    """

    class ConfigError(Exception):
        """
        Raised when the config can't be loaded.
        """

    def __enter__(self):
        self.lock.acquire()

    def __exit__(self, t, v, tb):
        self.lock.release()

    def __repr__(self):
        return "<Backend %r>" % self.name

    def __new__(cls, *args, **kwargs):
        """ Accept any arguments, necessary for AbstractModule __new__ override.

        AbstractModule, in its overridden __new__, removes itself from class hierarchy
        so its __new__ is called only once. In python 3, default (object) __new__ is
        then used for next instantiations but it's a slot/"fixed" version supporting
        only one argument (type to instanciate).
        """
        return object.__new__(cls)

    def __init__(self, woob, name, config=None, storage=None, logger=None, nofail=False):
        self.logger = getLogger(name, parent=logger)
        self.woob = woob
        self.name = name
        self.lock = RLock()
        if config is None:
            config = {}

        # Private fields (which start with '_')
        self._private_config = dict((key, value) for key, value in config.items() if key.startswith('_'))

        # Load configuration of backend.
        self.config = self.CONFIG.load(woob, self.NAME, self.name, config, nofail)

        self.storage = BackendStorage(self.name, storage)
        self.storage.load(self.STORAGE)

    def dump_state(self):
        if hasattr(self.browser, 'dump_state'):
            self.storage.set('browser_state', self.browser.dump_state())
            self.storage.save()

    def deinit(self):
        """
        This abstract method is called when the backend is unloaded.
        """
        if self._browser is None:
            return

        try:
            self.dump_state()
        finally:
            if hasattr(self.browser, 'deinit'):
                self.browser.deinit()

    @property
    def weboob(self):
        # compatibility property for modules that still use this name
        # TODO remove when not needed any longer
        return self.woob

    _browser = None

    @property
    def browser(self):
        """
        Attribute 'browser'. The browser is created at the first call
        of this attribute, to avoid useless pages access.

        Note that the :func:`create_default_browser` method is called to create it.
        """
        if self._browser is None:
            self._browser = self.create_default_browser()
        return self._browser

    def create_default_browser(self):
        """
        Method to overload to build the default browser in
        attribute 'browser'.
        """
        return self.create_browser()

    def create_browser(self, *args, **kwargs):
        """
        Build a browser from the BROWSER class attribute and the
        given arguments.

        :param klass: optional parameter to give another browser class to instanciate
        :type klass: :class:`woob.browser.browsers.Browser`
        """

        klass = kwargs.pop('klass', self.BROWSER)

        if not klass:
            return None

        kwargs['proxy'] = self.get_proxy()
        if '_proxy_headers' in self._private_config:
            kwargs['proxy_headers'] = self._private_config['_proxy_headers']
            if isinstance(kwargs['proxy_headers'], basestring):
                kwargs['proxy_headers'] = json.loads(kwargs['proxy_headers'])

        kwargs['logger'] = self.logger

        if self.logger.settings['responses_dirname']:
            kwargs.setdefault('responses_dirname', os.path.join(self.logger.settings['responses_dirname'],
                                                                self._private_config.get('_debug_dir', self.name)))
        elif os.path.isabs(self._private_config.get('_debug_dir', '')):
            kwargs.setdefault('responses_dirname', self._private_config['_debug_dir'])
        if self._private_config.get('_highlight_el', ''):
            kwargs.setdefault('highlight_el', bool(int(self._private_config['_highlight_el'])))

        browser = klass(*args, **kwargs)

        if hasattr(browser, 'load_state'):
            browser.load_state(self.storage.get('browser_state', default={}))

        return browser

    def get_proxy(self):
        # Get proxies from environment variables
        proxies = getproxies()
        # Override them with backend-specific config
        if '_proxy' in self._private_config:
            proxies['http'] = self._private_config['_proxy']
        if '_proxy_ssl' in self._private_config:
            proxies['https'] = self._private_config['_proxy_ssl']
        # Remove empty values
        for key in list(proxies.keys()):
            if not proxies[key]:
                del proxies[key]
        return proxies

    @classmethod
    def iter_caps(klass):
        """
        Iter capabilities implemented by this backend.

        :rtype: iter[:class:`woob.capabilities.base.Capability`]
        """
        for base in klass.mro():
            if issubclass(base, Capability) and base != Capability and base != klass and not issubclass(base, Module):
                yield base

    def has_caps(self, *caps):
        """
        Check if this backend implements at least one of these capabilities.
        """
        for c in caps:
            if (isinstance(c, basestring) and c in [cap.__name__ for cap in self.iter_caps()]) or \
               isinstance(self, c):
                return True
        return False

    def fillobj(self, obj, fields=None):
        """
        Fill an object with the wanted fields.

        :param fields: what fields to fill; if None, all fields are filled
        :type fields: :class:`list`
        """
        if obj is None:
            return obj

        def not_loaded_or_incomplete(v):
            return (v is NotLoaded or isinstance(v, BaseObject) and not v.__iscomplete__())

        def not_loaded(v):
            return v is NotLoaded

        def filter_missing_fields(obj, fields, check_cb):
            missing_fields = []
            if fields is None:
                # Select all fields
                if isinstance(obj, BaseObject):
                    fields = [item[0] for item in obj.iter_fields()]
                else:
                    fields = [item[0] for item in iter_fields(obj)]

            for field in fields:
                if not hasattr(obj, field):
                    raise FieldNotFound(obj, field)
                value = getattr(obj, field)

                missing = False
                if hasattr(value, '__iter__'):
                    for v in (value.values() if isinstance(value, dict) else value):
                        if check_cb(v):
                            missing = True
                            break
                elif check_cb(value):
                    missing = True

                if missing:
                    missing_fields.append(field)

            return missing_fields

        if isinstance(fields, basestring):
            fields = (fields,)

        missing_fields = filter_missing_fields(obj, fields, not_loaded_or_incomplete)

        if not missing_fields:
            return obj

        for key, value in self.OBJECTS.items():
            if isinstance(obj, key):
                self.logger.debug(u'Fill %r with fields: %s' % (obj, missing_fields))
                obj = value(self, obj, missing_fields) or obj
                break

        missing_fields = filter_missing_fields(obj, fields, not_loaded)

        # Object is not supported by backend. Do not notice it to avoid flooding user.
        # That's not so bad.
        for field in missing_fields:
            setattr(obj, field, NotAvailable)

        return obj


class AbstractModuleMissingParentError(Exception):
    pass


class AbstractModule(Module):
    """ Abstract module allow inheritance between modules.

    Sometimes, several websites are based on the same website engine. This module
    allow to simplify code with a fake inheritance: woob will install (if needed) and
    load a PARENT module and build our AbstractModule on top of this class.

    PARENT is a mandatory attribute of any AbstractModule.

    By default an AbstractModule inherits its parent backends CONFIG.
    To add backend values, use ADDITIONAL_CONFIG.
    To remove backend values, you must override CONFIG definition.

    Note that you must pass a valid woob instance as first argument of the constructor.
    """
    PARENT = None

    ADDITIONAL_CONFIG = BackendConfig()
    """Optional additional Values for backends, appended to parent CONFIG

    Values must be woob.tools.value.Value objects.
    """

    @classmethod
    def _resolve_abstract(cls, woob, name):
        """ Replace AbstractModule parent with the real base class """
        if cls.PARENT is None:
            raise AbstractModuleMissingParentError("PARENT is not defined for module %s" % cls.__name__)

        try:
            parent = woob.load_or_install_module(cls.PARENT).klass
        except ModuleInstallError as err:
            raise ModuleInstallError('The module %s depends on %s module but %s\'s installation failed with: %s' % (name, cls.PARENT, cls.PARENT, err))

        # Parent may be an AbstractModule as well
        if hasattr(parent, '_resolve_abstract'):
            parent._resolve_abstract(woob, name)

        parent_caps = parent.iter_caps()
        cls.__bases__ = tuple([parent] + [cap for cap in cls.iter_caps() if cap not in parent_caps])

        # As soon as __bases__ is overwritten, the attributes and behavior of
        # cls can change as the new "parents" will be taken into account immediately

        # Cls may have defined an ADDITIONAL_CONFIG
        # In that case, create a virtual CONFIG for this class that will
        # contains the additional_config elements.
        if getattr(cls, 'ADDITIONAL_CONFIG', None):
            cls.CONFIG = BackendConfig(*(list(parent.CONFIG.values()) + list(cls.ADDITIONAL_CONFIG.values())))

        return parent

    def __new__(cls, woob, name, config=None, storage=None, logger=None, nofail=False):
        # fake backend config inheritance, override existing Values
        # do not use CONFIG to allow the children to overwrite completely the parent CONFIG.
        cls._resolve_abstract(woob=woob, name=name)

        return Module.__new__(cls, woob, name, config, storage, logger, nofail)
