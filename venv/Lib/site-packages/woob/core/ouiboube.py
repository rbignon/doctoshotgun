# -*- coding: utf-8 -*-

# Copyright(C) 2010-2014 Romain Bignon
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
from pathlib import Path

from woob.core.bcall import BackendsCall
from woob.core.modules import ModulesLoader, RepositoryModulesLoader
from woob.core.backendscfg import BackendsConfig
from woob.core.requests import RequestsManager
from woob.core.repositories import Repositories, PrintProgress
from woob.core.scheduler import Scheduler
from woob.tools.backend import Module
from woob.tools.compat import basestring, unicode
from woob.tools.config.iconfig import ConfigError
from woob.tools.log import getLogger
from woob.exceptions import ModuleLoadError


__all__ = ['WebNip', 'Weboob']


class VersionsMismatchError(ConfigError):
    pass


class WebNip(object):
    """
    Woob in Non Integrated Programs

    It provides methods to build backends or call methods on all loaded
    backends.

    You should use this class when you want to build an application
    using Woob as a library, without using the standard modules nor
    the automatic module download and update machanism. When using
    WebNip, you have to explicitely provide module paths and deal
    yourself with backend configuration.

    :param modules_path: path to directory containing modules.
    :type modules_path: :class:`basestring`
    :param storage: provide a storage where backends can save data
    :type storage: :class:`woob.tools.storage.IStorage`
    :param scheduler: what scheduler to use; default is :class:`woob.core.scheduler.Scheduler`
    :type scheduler: :class:`woob.core.scheduler.IScheduler`
    """
    VERSION = '3.0'

    def __init__(self, modules_path=None, storage=None, scheduler=None):
        self.logger = getLogger('woob')
        self.backend_instances = {}
        self.requests = RequestsManager()

        if modules_path is None:
            import pkg_resources
            # Package woob_modules is provided by
            # https://gitlab.com/woob/modules
            # and should be pip-installed separately.
            # Note that Weboob users should rather install Weboob modules
            # through https://updates.woob.tech/.
            modules_path = pkg_resources.resource_filename('woob_modules', '')

        if modules_path:
            self.modules_loader = ModulesLoader(modules_path, self.VERSION)

        if scheduler is None:
            scheduler = Scheduler()
        self.scheduler = scheduler

        self.storage = storage

    def __deinit__(self):
        self.deinit()

    def deinit(self):
        """
        Call this method when you stop using Woob, to
        properly unload all correctly.
        """
        self.unload_backends()

    def build_backend(self, module_name, params=None, storage=None, name=None, nofail=False, logger=None):
        """
        Create a backend.

        It does not load it into the Woob object, so you are responsible for
        deinitialization and calls.

        :param module_name: name of module
        :param params: parameters to give to backend
        :type params: :class:`dict`
        :param storage: storage to use
        :type storage: :class:`woob.tools.storage.IStorage`
        :param name: name of backend
        :type name: :class:`basestring`
        :rtype: :class:`woob.tools.backend.Module`
        :param nofail: if true, this call can't fail
        :type nofail: :class:`bool`
        """
        module = self.modules_loader.get_or_load_module(module_name)

        backend_instance = module.create_instance(self, name or module_name, params or {}, storage, nofail, logger=logger or self.logger)
        return backend_instance

    class LoadError(Exception):
        """
        Raised when a backend is unabled to load.

        :param backend_name: name of backend we can't load
        :param exception: exception object
        """

        def __init__(self, backend_name, exception):
            super(WebNip.LoadError, self).__init__(unicode(exception))
            self.backend_name = backend_name

    def load_backend(self, module_name, name, params=None, storage=None):
        """
        Load a backend.

        :param module_name: name of module to load
        :type module_name: :class:`basestring`:
        :param name: name of instance
        :type name: :class:`basestring`
        :param params: parameters to give to backend
        :type params: :class:`dict`
        :param storage: storage to use
        :type storage: :class:`woob.tools.storage.IStorage`
        :rtype: :class:`woob.tools.backend.Module`
        """
        if name is None:
            name = module_name

        if name in self.backend_instances:
            raise self.LoadError(name, 'A loaded backend already named "%s"' % name)

        backend = self.build_backend(module_name, params, storage, name)
        self.backend_instances[name] = backend
        return backend

    def unload_backends(self, names=None):
        """
        Unload backends.

        :param names: if specified, only unload that backends
        :type names: :class:`list`
        """
        unloaded = {}
        if isinstance(names, basestring):
            names = [names]
        elif names is None:
            names = list(self.backend_instances.keys())

        for name in names:
            backend = self.backend_instances.pop(name)
            with backend:
                backend.deinit()
            unloaded[backend.name] = backend

        return unloaded

    def __getitem__(self, name):
        """
        Alias for :func:`WebNip.get_backend`.
        """
        return self.get_backend(name)

    def get_backend(self, name, **kwargs):
        """
        Get a backend from its name.

        :param name: name of backend to get
        :type name: str
        :param default: if specified, get this value when the backend is not found
        :type default: whatever you want
        :raises: :class:`KeyError` if not found.
        """
        try:
            return self.backend_instances[name]
        except KeyError:
            if 'default' in kwargs:
                return kwargs['default']
            else:
                raise

    def count_backends(self):
        """
        Get number of loaded backends.
        """
        return len(self.backend_instances)

    def iter_backends(self, caps=None, module=None):
        """
        Iter on each backends.

        Note: each backend is locked when it is returned.

        :param caps: optional list of capabilities to select backends
        :type caps: tuple[:class:`woob.capabilities.base.Capability`]
        :param module: optional name of module
        :type module: :class:`basestring`
        :rtype: iter[:class:`woob.tools.backend.Module`]
        """
        for _, backend in sorted(self.backend_instances.items()):
            if (caps is None or backend.has_caps(caps)) and \
               (module is None or backend.NAME == module):
                with backend:
                    yield backend

    def __getattr__(self, name):
        def caller(*args, **kwargs):
            return self.do(name, *args, **kwargs)
        return caller

    def do(self, function, *args, **kwargs):
        r"""
        Do calls on loaded backends with specified arguments, in separated
        threads.

        This function has two modes:

        - If *function* is a string, it calls the method with this name on
          each backends with the specified arguments;
        - If *function* is a callable, it calls it in a separated thread with
          the locked backend instance at first arguments, and \*args and
          \*\*kwargs.

        :param function: backend's method name, or a callable object
        :type function: :class:`str`
        :param backends: list of backends to iterate on
        :type backends: list[:class:`str`]
        :param caps: iterate on backends which implement this caps
        :type caps: list[:class:`woob.capabilities.base.Capability`]
        :rtype: A :class:`woob.core.bcall.BackendsCall` object (iterable)
        """
        backends = list(self.backend_instances.values())
        _backends = kwargs.pop('backends', None)
        if _backends is not None:
            if isinstance(_backends, Module):
                backends = [_backends]
            elif isinstance(_backends, basestring):
                if len(_backends) > 0:
                    try:
                        backends = [self.backend_instances[_backends]]
                    except (ValueError, KeyError):
                        backends = []
            elif isinstance(_backends, (list, tuple, set)):
                backends = []
                for backend in _backends:
                    if isinstance(backend, basestring):
                        try:
                            backends.append(self.backend_instances[backend])
                        except (ValueError, KeyError):
                            pass
                    else:
                        backends.append(backend)
            else:
                self.logger.warning(u'The "backends" value isn\'t supported: %r', _backends)

        if 'caps' in kwargs:
            caps = kwargs.pop('caps')
            backends = [backend for backend in backends if backend.has_caps(caps)]

        # The return value MUST BE the BackendsCall instance. Please never iterate
        # here on this object, because caller might want to use other methods, like
        # wait() on callback_thread().
        # Thanks a lot.
        return BackendsCall(backends, function, *args, **kwargs)

    def schedule(self, interval, function, *args):
        """
        Schedule an event.

        :param interval: delay before calling the function
        :type interval: int
        :param function: function to call
        :type function: callabale
        :param args: arguments to give to function
        :returns: an event identificator
        """
        return self.scheduler.schedule(interval, function, *args)

    def repeat(self, interval, function, *args):
        """
        Repeat a call to a function

        :param interval: interval between two calls
        :type interval: int
        :param function: function to call
        :type function: callable
        :param args: arguments to give to function
        :returns: an event identificator
        """
        return self.scheduler.repeat(interval, function, *args)

    def cancel(self, ev):
        """
        Cancel an event

        :param ev: the event identificator
        """
        return self.scheduler.cancel(ev)

    def want_stop(self):
        """
        Plan to stop the scheduler.
        """
        return self.scheduler.want_stop()

    def loop(self):
        """
        Run the scheduler loop
        """
        return self.scheduler.run()

    def load_or_install_module(self, module_name):
        """ Load a backend, but can't install it """
        return self.modules_loader.get_or_load_module(module_name)


class Weboob(WebNip):
    """
    The main class of Woob, used to manage backends, modules repositories and
    call methods on all loaded backends.

    :param workdir: optional parameter to set path of the working directory
    :type workdir: str
    :param datadir: optional parameter to set path of the data directory
    :type datadir: str
    :param backends_filename: name of the *backends* file, where configuration of
                              backends is stored
    :type backends_filename: str
    :param storage: provide a storage where backends can save data
    :type storage: :class:`woob.tools.storage.IStorage`
    """
    BACKENDS_FILENAME = 'backends'

    def __init__(self, workdir=None, datadir=None, backends_filename=None, scheduler=None, storage=None):
        super(Weboob, self).__init__(modules_path=False, scheduler=scheduler, storage=storage)

        # Create WORKDIR
        xdg_config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")

        workdir_paths = [
            workdir,
            os.environ.get("WOOB_WORKDIR"),
            os.environ.get("WEBOOB_WORKDIR"),
        ]
        workdir = self._get_working_dir(workdir_paths, xdg_config / "woob", xdg_config / "weboob")
        self.workdir = os.path.realpath(workdir)
        self._create_dir(self.workdir)

        # Create DATADIR
        xdg_data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
        datadir_paths = [
            datadir,
            os.environ.get("WOOB_DATADIR"),
            os.environ.get("WOOB_WORKDIR"),
            os.environ.get("WEBOOB_DATADIR"),
            os.environ.get("WEBOOB_WORKDIR"),
        ]
        datadir = self._get_working_dir(datadir_paths, xdg_data / "woob", xdg_data / "weboob")
        datadir = os.path.realpath(datadir)
        self._create_dir(datadir)

        # Modules management
        self.repositories = Repositories(workdir, datadir, self.VERSION)
        self.modules_loader = RepositoryModulesLoader(self.repositories)

        # Backend instances config
        if not backends_filename:
            backends_filename = (
                os.environ.get('WOOB_BACKENDS')
                or os.environ.get('WEBOOB_BACKENDS')
                or os.path.join(self.workdir, self.BACKENDS_FILENAME)
            )
        elif not backends_filename.startswith('/'):
            backends_filename = os.path.join(self.workdir, backends_filename)
        self.backends_config = BackendsConfig(backends_filename)

    def _get_working_dir(self, priority_dirs, user_dir, user_dir_legacy):
        for dir in priority_dirs:
            if dir:
                return dir

        # if it's a broken link, exists() will return False
        # but we don't want to overwrite even that
        try:
            user_dir.lstat()
        except FileNotFoundError:
            pass
        else:
            return user_dir

        if user_dir_legacy.is_dir():
            self.logger.debug("legacy dir %r can be renamed", user_dir_legacy)
            try:
                user_dir_legacy.rename(user_dir)
            except IOError as exc:
                self.logger.warning("can't rename legacy dir %r: %s", user_dir_legacy, exc)
                return user_dir_legacy

        return user_dir

    def _create_dir(self, name):
        if not os.path.exists(name):
            os.makedirs(name)
        elif not os.path.isdir(name):
            self.logger.error(u'"%s" is not a directory', name)

    def update(self, progress=PrintProgress()):
        """
        Update modules from repositories.
        """
        self.repositories.update(progress)

        modules_to_check = set([module_name for _, module_name, _ in self.backends_config.iter_backends()])
        for module_name in modules_to_check:
            minfo = self.repositories.get_module_info(module_name)
            if minfo and not minfo.is_installed():
                self.repositories.install(minfo, progress)

    def build_backend(self, module_name, params=None, storage=None, name=None, nofail=False):
        """
        Create a single backend which is not listed in configuration.

        :param module_name: name of module
        :param params: parameters to give to backend
        :type params: :class:`dict`
        :param storage: storage to use
        :type storage: :class:`woob.tools.storage.IStorage`
        :param name: name of backend
        :type name: :class:`basestring`
        :rtype: :class:`woob.tools.backend.Module`
        :param nofail: if true, this call can't fail
        :type nofail: :class:`bool`
        """
        minfo = self.repositories.get_module_info(module_name)
        if minfo is None:
            raise ModuleLoadError(module_name, 'Module does not exist.')

        if not minfo.is_installed():
            self.repositories.install(minfo)

        return super(Weboob, self).build_backend(module_name, params, storage, name, nofail)

    def load_backends(self, caps=None, names=None, modules=None, exclude=None, storage=None, errors=None):
        """
        Load backends listed in config file.

        :param caps: load backends which implement all of specified caps
        :type caps: tuple[:class:`woob.capabilities.base.Capability`]
        :param names: load backends in list
        :type names: tuple[:class:`str`]
        :param modules: load backends which module is in list
        :type modules: tuple[:class:`str`]
        :param exclude: do not load backends in list
        :type exclude: tuple[:class:`str`]
        :param storage: use this storage if specified
        :type storage: :class:`woob.tools.storage.IStorage`
        :param errors: if specified, store every errors in this list
        :type errors: list[:class:`LoadError`]
        :returns: loaded backends
        :rtype: dict[:class:`str`, :class:`woob.tools.backend.Module`]
        """
        loaded = {}
        if storage is None:
            storage = self.storage

        if not self.repositories.check_repositories():
            self.logger.error(u'Repositories are not consistent with the sources.list')
            raise VersionsMismatchError(u'Versions mismatch, please run "woob config update"')

        for backend_name, module_name, params in self.backends_config.iter_backends():
            if '_enabled' in params and not params['_enabled'].lower() in ('1', 'y', 'true', 'on', 'yes') or \
               names is not None and backend_name not in names or \
               modules is not None and module_name not in modules or \
               exclude is not None and backend_name in exclude:
                continue

            minfo = self.repositories.get_module_info(module_name)
            if minfo is None:
                self.logger.warning(u'Backend "%s" is referenced in %s but was not found. '
                                    u'Perhaps a missing repository or a removed module?', module_name, self.backends_config.confpath)
                continue

            if caps is not None and not minfo.has_caps(caps):
                continue

            if not minfo.is_installed():
                self.repositories.install(minfo)

            module = None
            try:
                module = self.modules_loader.get_or_load_module(module_name)
            except ModuleLoadError as e:
                self.logger.error(u'Unable to load module "%s": %s', module_name, e)
                continue

            if backend_name in self.backend_instances:
                self.logger.warning(u'Oops, the backend "%s" is already loaded. Unload it before reloading...', backend_name)
                self.unload_backends(backend_name)

            try:
                backend_instance = module.create_instance(self, backend_name, params, storage)
            except Module.ConfigError as e:
                if errors is not None:
                    errors.append(self.LoadError(backend_name, e))
            else:
                self.backend_instances[backend_name] = loaded[backend_name] = backend_instance
        return loaded

    def load_or_install_module(self, module_name):
        """ Load a backend, and install it if not done before """
        try:
            return self.modules_loader.get_or_load_module(module_name)
        except ModuleLoadError:
            self.repositories.install(module_name)
            return self.modules_loader.get_or_load_module(module_name)
