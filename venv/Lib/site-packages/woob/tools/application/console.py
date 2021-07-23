# -*- coding: utf-8 -*-

# Copyright(C) 2010-2012  Christophe Benz, Romain Bignon
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


from __future__ import print_function

from collections import OrderedDict
from copy import copy
import getpass
import logging
import shlex
import subprocess
from subprocess import check_output
import sys
import os

from woob.capabilities import UserError
from woob.capabilities.account import CapAccount, Account, AccountRegisterError
from woob.core.backendscfg import BackendAlreadyExists
from woob.core.repositories import IProgress
from woob.exceptions import BrowserUnavailable, BrowserIncorrectPassword, BrowserForbidden, \
                              BrowserSSLError, BrowserQuestion, BrowserHTTPSDowngrade, \
                              ModuleInstallError, ModuleLoadError, NoAccountsException, \
                              ActionNeeded, CaptchaQuestion, NeedInteractiveFor2FA
from woob.tools.value import Value, ValueBool, ValueFloat, ValueInt, ValueBackendPassword
from woob.tools.misc import to_unicode
from woob.tools.compat import unicode, long

from .base import Application, MoreResultsAvailable


__all__ = ['ConsoleApplication', 'BackendNotGiven']


class BackendNotGiven(Exception):
    def __init__(self, id, backends):
        self.id = id
        self.backends = sorted(backends)
        super(BackendNotGiven, self).__init__('Please specify a backend to use for this argument (%s@backend_name). '
                'Availables: %s.' % (id, ', '.join(name for name, backend in backends)))


class BackendNotFound(Exception):
    pass


class ConsoleProgress(IProgress):
    def __init__(self, app):
        self.app = app

    def progress(self, percent, message):
        try:
            quiet = self.app.options.quiet
        except AttributeError:
            quiet = False
        if not quiet:
            self.app.stdout.write('=== [%3.0f%%] %s\n' % (percent*100, message))

    def error(self, message):
        self.app.stderr.write('ERROR: %s\n' % message)

    def prompt(self, message):
        return self.app.ask(message, default=True)


class ConsoleApplication(Application):
    """
    Base application class for CLI applications.
    """

    CAPS = None

    # shell escape strings
    if sys.platform == 'win32' \
            or not sys.stdout.isatty() \
            or os.getenv('ANSI_COLORS_DISABLED') is not None:
        #workaround to disable bold
        BOLD   = ''
        NC     = ''          # no color
    else:
        BOLD   = '[1m'
        NC     = '[0m'    # no color

    def __init__(self, option_parser=None):
        super(ConsoleApplication, self).__init__(option_parser)
        self.woob.requests.register('login', self.login_cb)
        self.enabled_backends = set()
        self._parser.add_option('--auto-update', action='store_true',
                                help='Automatically check for updates when a bug in a module is encountered')

    def login_cb(self, backend_name, value):
        return self.ask('[%s] %s' % (backend_name,
                        value.label),
                        masked=True,
                        default='',
                        regexp=value.regexp)

    def unload_backends(self, *args, **kwargs):
        unloaded = self.woob.unload_backends(*args, **kwargs)
        for backend in unloaded.values():
            try:
                self.enabled_backends.remove(backend)
            except KeyError:
                pass
        return unloaded

    def is_module_loadable(self, info):
        return self.CAPS is None or info.has_caps(self.CAPS)

    def load_backends(self, *args, **kwargs):
        if 'errors' in kwargs:
            errors = kwargs['errors']
        else:
            kwargs['errors'] = errors = []
        ret = super(ConsoleApplication, self).load_backends(*args, **kwargs)

        for err in errors:
            print(u'Error(%s): %s' % (err.backend_name, err), file=self.stderr)
            if self.ask('Do you want to reconfigure this backend?', default=True):
                self.edit_backend(err.backend_name)
                self.load_backends(names=[err.backend_name])

        for name, backend in ret.items():
            self.enabled_backends.add(backend)

        self.check_loaded_backends()

        return ret

    def check_loaded_backends(self, default_config=None):
        while len(self.enabled_backends) == 0:
            print('Warning: there is currently no configured backend for %s' % self.APPNAME)
            if not self.stdout.isatty() or not self.ask('Do you want to configure backends?', default=True):
                return False

            self.prompt_create_backends(default_config)

        return True

    def prompt_create_backends(self, default_config=None):
        r = ''
        while r != 'q':
            modules = []
            print('\nAvailable modules:')
            for name, info in sorted(self.woob.repositories.get_all_modules_info().items()):
                if not self.is_module_loadable(info):
                    continue
                modules.append(name)
                loaded = ' '
                for bi in self.woob.iter_backends():
                    if bi.NAME == name:
                        if loaded == ' ':
                            loaded = 'X'
                        elif loaded == 'X':
                            loaded = 2
                        else:
                            loaded += 1
                print('%s%d)%s [%s] %s%-15s%s   %s' % (self.BOLD, len(modules), self.NC, loaded,
                                                       self.BOLD, name, self.NC,
                                                       info.description))
            print('%sa) --all--%s               install all backends' % (self.BOLD, self.NC))
            print('%sq)%s --stop--\n' % (self.BOLD, self.NC))
            r = self.ask('Select a backend to create (q to stop)', regexp='^(\d+|q|a)$')

            if str(r).isdigit():
                i = int(r) - 1
                if i < 0 or i >= len(modules):
                    print('Error: %s is not a valid choice' % r, file=self.stderr)
                    continue
                name = modules[i]
                try:
                    inst = self.add_backend(name, name, default_config)
                    if inst:
                        self.load_backends(names=[inst])
                except (KeyboardInterrupt, EOFError):
                    print('\nAborted.')
            elif r == 'a':
                try:
                    for name in modules:
                        if name in [b.NAME for b in self.woob.iter_backends()]:
                            continue
                        inst = self.add_backend(name, name, default_config)
                        if inst:
                            self.load_backends(names=[inst])
                except (KeyboardInterrupt, EOFError):
                    print('\nAborted.')
                else:
                    break

        print('Right right!')

    def _handle_options(self):
        self.load_default_backends()

    def load_default_backends(self):
        """
        By default loads all backends.

        Applications can overload this method to restrict backends loaded.
        """
        if len(self.STORAGE) > 0:
            self.load_backends(self.CAPS, storage=self.create_storage())
        else:
            self.load_backends(self.CAPS)

    @classmethod
    def run(klass, args=None):
        try:
            super(ConsoleApplication, klass).run(args)
        except BackendNotFound as e:
            print('Error: Backend "%s" not found.' % e)
            sys.exit(1)

    def do(self, function, *args, **kwargs):
        if 'backends' not in kwargs:
            kwargs['backends'] = self.enabled_backends
        return self.woob.do(function, *args, **kwargs)

    def parse_id(self, _id, unique_backend=False):
        try:
            _id, backend_name = _id.rsplit('@', 1)
        except ValueError:
            backend_name = None
        backends = [(b.name, b) for b in self.enabled_backends]
        if unique_backend and not backend_name:
            if len(backends) == 1:
                backend_name = backends[0][0]
            else:
                raise BackendNotGiven(_id, backends)
        if backend_name is not None and backend_name not in dict(backends):
            # Is the backend a short version of a real one?
            found = False
            for key in dict(backends):
                if backend_name in key:
                    # two choices, ambiguous command
                    if found:
                        raise BackendNotFound(backend_name)
                    else:
                        found = True
                        _back = key
            if found:
                return _id, _back
            raise BackendNotFound(backend_name)
        return _id, backend_name

    # user interaction related methods

    def register_backend(self, name, ask_add=True):
        try:
            backend = self.woob.modules_loader.get_or_load_module(name)
        except ModuleLoadError:
            backend = None

        if not backend:
            print('Backend "%s" does not exist.' % name, file=self.stderr)
            return 1

        if not backend.has_caps(CapAccount) or backend.klass.ACCOUNT_REGISTER_PROPERTIES is None:
            print('You can\'t register a new account with %s' % name, file=self.stderr)
            return 1

        account = Account()
        account.properties = {}
        if backend.website:
            website = 'on website %s' % backend.website
        else:
            website = 'with backend %s' % backend.name
        while True:
            asked_config = False
            for key, prop in backend.klass.ACCOUNT_REGISTER_PROPERTIES.items():
                if not asked_config:
                    asked_config = True
                    print('Configuration of new account %s' % website)
                    print('-----------------------------%s' % ('-' * len(website)))
                p = copy(prop)
                p.set(self.ask(prop, default=account.properties[key].get() if (key in account.properties) else prop.default))
                account.properties[key] = p
            if asked_config:
                print('-----------------------------%s' % ('-' * len(website)))
            try:
                backend.klass.register_account(account)
            except AccountRegisterError as e:
                print(u'%s' % e)
                if self.ask('Do you want to try again?', default=True):
                    continue
                else:
                    return None
            else:
                break
        backend_config = {}
        for key, value in account.properties.items():
            if key in backend.config:
                backend_config[key] = value.get()

        if ask_add and self.ask('Do you want to add the new register account?', default=True):
            return self.add_backend(name, name, backend_config, ask_register=False)

        return backend_config

    def install_module(self, name):
        try:
            self.woob.repositories.install(name, ConsoleProgress(self))
        except ModuleInstallError as e:
            print('Unable to install module "%s": %s' % (name, e), file=self.stderr)
            return False

        print('')
        return True

    def edit_backend(self, name, params=None):
        return self.add_backend(name, name, params, True)

    def add_backend(self, module_name, backend_name, params=None, edit=False, ask_register=True):
        if params is None:
            params = {}

        module = None
        config = None
        try:
            if not edit:
                minfo = self.woob.repositories.get_module_info(module_name)
                if minfo is None:
                    raise ModuleLoadError(module_name, 'Module does not exist')
                if not minfo.is_installed():
                    print('Module "%s" is available but not installed.' % minfo.name)
                    self.install_module(minfo)
                module = self.woob.modules_loader.get_or_load_module(module_name)
                config = module.config
            else:
                module_name, items = self.woob.backends_config.get_backend(backend_name)
                module = self.woob.modules_loader.get_or_load_module(module_name)
                items.update(params)
                params = items
                config = module.config.load(self.woob, module_name, backend_name, params, nofail=True)
        except ModuleLoadError as e:
            print('Unable to load module "%s": %s' % (module_name, e), file=self.stderr)
            return 1

        # ask for params non-specified on command-line arguments
        asked_config = False
        for key, value in config.items():
            if value.transient:
                continue

            if not asked_config:
                asked_config = True
                print('')
                print('Configuration of backend %s' % module.name)
                print('-------------------------%s' % ('-' * len(module.name)))
            if key not in params or edit:
                params[key] = self.ask(value, default=params[key] if (key in params) else value.default)
            else:
                print(u'[%s] %s: %s' % (key, value.description, '(masked)' if value.masked else to_unicode(params[key])))
        if asked_config:
            print('-------------------------%s' % ('-' * len(module.name)))

        i = 2
        while not edit and self.woob.backends_config.backend_exists(backend_name):
            if not self.ask('Backend "%s" already exists. Add a new one for module %s?' % (backend_name, module.name), default=False):
                return 1

            backend_name = backend_name.rstrip('0123456789')
            while self.woob.backends_config.backend_exists('%s%s' % (backend_name, i)):
                i += 1
            backend_name = self.ask('Please give new instance name', default='%s%s' % (backend_name, i), regexp=r'^[\w\-_]+$')

        try:
            config = config.load(self.woob, module.name, backend_name, params, nofail=True)
            for key, value in params.items():
                if key not in config:
                    continue
                config[key].set(value)

            config.save(edit=edit)
            print('Backend "%s" successfully %s.' % (backend_name, 'edited' if edit else 'added'))
            return backend_name
        except BackendAlreadyExists:
            print('Backend "%s" already exists.' % backend_name, file=self.stderr)
            return 1

    def ask(self, question, default=None, masked=None, regexp=None, choices=None, tiny=None):
        """
        Ask a question to user.

        @param question  text displayed (str)
        @param default  optional default value (str)
        @param masked  if True, do not show typed text (bool)
        @param regexp  text must match this regexp (str)
        @param choices  choices to do (list)
        @param tiny  ask for the (small) value of the choice (bool)
        @return  entered text by user (str)
        """

        if isinstance(question, Value):
            v = copy(question)
            if default is not None:
                v.default = to_unicode(default) if isinstance(default, str) else default
            if masked is not None:
                v.masked = masked
            if regexp is not None:
                v.regexp = regexp
            if choices is not None:
                v.choices = choices
            if tiny is not None:
                v.tiny = tiny
        else:
            if isinstance(default, bool):
                klass = ValueBool
            elif isinstance(default, float):
                klass = ValueFloat
            elif isinstance(default, (int,long)):
                klass = ValueInt
            else:
                klass = Value

            v = klass(label=question, default=default, masked=masked, regexp=regexp, choices=choices, tiny=tiny)

        question = v.label
        if v.description and v.description != v.label:
            question = u'%s: %s' % (question, v.description)
        if v.id:
            question = u'[%s] %s' % (v.id, question)

        if isinstance(v, ValueBackendPassword):
            print(question + ':')
            question = v.label
            choices = OrderedDict()
            choices['c'] = 'Run an external tool during backend load'
            if not v.noprompt:
                choices['p'] = 'Prompt value when needed (do not store it)'
            choices['s'] = 'Store value in config'

            if v.default == '' and not v.noprompt:
                default = 'p'
            else:
                default = 's'

            r = self.ask('*** How do you want to store it?', choices=choices, tiny=True, default=default)
            if r == 'p':
                return ''
            if r == 'c':
                print('Enter the shell command that will print the required value on the standard output')
                while True:
                    cmd = self.ask('')
                    try:
                        check_output(cmd, shell=True)
                    except subprocess.CalledProcessError as e:
                        print('%s' % e)
                    else:
                        return '`%s`' % cmd

        aliases = {}
        if isinstance(v, ValueBool):
            question = u'%s (%s/%s)' % (question, 'Y' if v.default else 'y', 'n' if v.default else 'N')
        elif v.choices:
            if v.tiny is None:
                v.tiny = True
                for key in v.choices:
                    if len(key) > 5 or ' ' in key:
                        v.tiny = False
                        break

            if v.tiny:
                question = u'%s (%s)' % (question, '/'.join((s.upper() if s == v.default else s)
                                                            for s in v.choices))
                for s in v.choices:
                    if s == v.default:
                        aliases[s.upper()] = s
                for key, value in v.choices.items():
                    print('     %s%s%s: %s' % (self.BOLD, key, self.NC, value))
            else:
                for n, (key, value) in enumerate(v.choices.items()):
                    print('     %s%2d)%s %s' % (self.BOLD, n + 1, self.NC, value))
                    aliases[str(n + 1)] = key
                question = u'%s (choose in list)' % question
        if v.masked:
            question = u'%s (hidden input)' % question

        if not isinstance(v, ValueBool) and not v.tiny and v.default not in (None, ''):
            question = u'%s [%s]' % (question, '*******' if v.masked else v.default)

        question += ': '

        while True:
            if v.masked:
                if sys.version_info.major < 3 and isinstance(question, unicode):
                    question = question.encode(self.encoding)

                line = getpass.getpass(question)
                if sys.platform != 'win32':
                    if isinstance(line, bytes): # only for python2
                        line = line.decode(self.encoding)
            else:
                self.stdout.write(question)
                self.stdout.flush()
                line = self._readline()
                if len(line) == 0:
                    raise EOFError()
                else:
                    line = line.rstrip('\r\n')

            if not line and v.default is not None:
                line = v.default

            if line in aliases:
                line = aliases[line]

            try:
                v.set(line)
            except ValueError as e:
                print(u'Error: %s' % e, file=self.stderr)
            else:
                break

        v.noprompt = True
        return v.get()

    def print(self, txt):
        print(txt)

    def _readall(self):
        if sys.version_info.major == 2:
            return self.stdin.read().decode(self.encoding)
        else:
            return self.stdin.read()

    def _readline(self):
        if sys.version_info.major == 2:
            return self.stdin.readline().decode(self.encoding)
        else:
            return self.stdin.readline()

    def acquire_input(self, content=None, editor_params=None):
        editor = os.getenv('EDITOR', 'vi')
        if self.stdin.isatty() and editor:
            from tempfile import NamedTemporaryFile
            with NamedTemporaryFile() as f:
                filename = f.name
                if content is not None:
                    if isinstance(content, unicode):
                        content = content
                    f.write(content)
                    f.flush()
                try:
                    params = editor_params[os.path.basename(editor)]
                except (KeyError,TypeError):
                    params = ''
                cmd = shlex.split(editor) + shlex.split(params) + [filename]
                subprocess.call(cmd)
                f.seek(0)
                text = f.read()
        else:
            if self.stdin.isatty():
                print('Reading content from stdin... Type ctrl-D '
                          'from an empty line to stop.')
            text = self._readall()
        return to_unicode(text)

    def bcall_error_handler(self, backend, error, backtrace):
        """
        Handler for an exception inside the CallErrors exception.

        This method can be overridden to support more exceptions types.
        """
        if isinstance(error, BrowserQuestion):
            for field in error.fields:
                v = self.ask(field)
                if v:
                    backend.config[field.id].set(v)
        elif isinstance(error, CaptchaQuestion):
            print(u'Warning(%s): Captcha has been found on login page' % backend.name, file=self.stderr)
        elif isinstance(error, BrowserIncorrectPassword):
            msg = unicode(error)
            if not msg:
                msg = 'invalid login/password.'
            print('Error(%s): %s' % (backend.name, msg), file=self.stderr)
            if self.ask('Do you want to reconfigure this backend?', default=True):
                self.unload_backends(names=[backend.name])
                self.edit_backend(backend.name)
                self.load_backends(names=[backend.name])
        elif isinstance(error, BrowserSSLError):
            print(u'FATAL(%s): ' % backend.name + self.BOLD + '/!\ SERVER CERTIFICATE IS INVALID /!\\' + self.NC, file=self.stderr)
        elif isinstance(error, BrowserHTTPSDowngrade):
            print(u'FATAL(%s): ' % backend.name + 'Downgrade from HTTPS to HTTP')
        elif isinstance(error, BrowserForbidden):
            msg = unicode(error)
            print(u'Error(%s): %s' % (backend.name, msg or 'Forbidden'), file=self.stderr)
        elif isinstance(error, BrowserUnavailable):
            msg = unicode(error)
            print(u'Error(%s): %s' % (backend.name, msg or 'Website is unavailable.'), file=self.stderr)
        elif isinstance(error, ActionNeeded):
            msg = unicode(error)
            print(u'Error(%s): Action needed on website: %s' % (backend.name, msg), file=self.stderr)
        elif isinstance(error, NotImplementedError):
            print(u'Error(%s): this feature is not supported yet by this backend.' % backend.name, file=self.stderr)
            print(u'      %s   To help the maintainer of this backend implement this feature,' % (' ' * len(backend.name)), file=self.stderr)
            print(u'      %s   please contact us on the project mailing list' % (' ' * len(backend.name)), file=self.stderr)
        elif isinstance(error, NeedInteractiveFor2FA):
            print(u'Error(%s): You have to run %s in interactive mode to perform a two-factor authentication' % (backend.name, self.APPNAME), file=self.stderr)
        elif isinstance(error, UserError):
            print(u'Error(%s): %s' % (backend.name, to_unicode(error)), file=self.stderr)
        elif isinstance(error, MoreResultsAvailable):
            print(u'Hint: There are more results for backend %s' % (backend.name), file=self.stderr)
        elif isinstance(error, NoAccountsException):
            print(u'Error(%s): %s' % (backend.name, to_unicode(error) or 'No account on this backend'), file=self.stderr)
        else:
            print(u'Bug(%s): %s' % (backend.name, to_unicode(error)), file=self.stderr)

            minfo = self.woob.repositories.get_module_info(backend.NAME)
            if minfo and not minfo.is_local():
                if self.options.auto_update:
                    self.woob.repositories.update_repositories(ConsoleProgress(self))

                    # minfo of the new available module
                    minfo = self.woob.repositories.get_module_info(backend.NAME)
                    if minfo and minfo.version > self.woob.repositories.versions.get(minfo.name) and \
                       self.ask('A new version of %s is available. Do you want to install it?' % minfo.name, default=True) and \
                       self.install_module(minfo):
                        print('New version of module %s has been installed. Retry to call the command.' % minfo.name)
                        return
                else:
                    print('(If --auto-update is passed on the command-line, new versions of the module will be checked automatically)')

            if logging.root.level <= logging.DEBUG:
                print(backtrace, file=self.stderr)
            else:
                return True

    def bcall_errors_handler(self, errors, debugmsg='Use --debug option to print backtraces', ignore=()):
        """
        Handler for the CallErrors exception.
        """
        ask_debug_mode = False
        more_results = set()
        err = 0

        for backend, error, backtrace in errors.errors:
            if isinstance(error, MoreResultsAvailable):
                more_results.add(backend.name)
            elif isinstance(error, ignore):
                continue
            else:
                err = 1
                if self.bcall_error_handler(backend, error, backtrace):
                    ask_debug_mode = True

        if ask_debug_mode:
            print(debugmsg, file=self.stderr)
        elif len(more_results) > 0:
            print('Hint: There are more results available for %s (use option -n or count command)' % (', '.join(more_results)), file=self.stderr)

        return err
