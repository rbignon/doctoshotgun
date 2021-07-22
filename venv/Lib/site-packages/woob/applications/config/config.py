# -*- coding: utf-8 -*-

# Copyright(C) 2010-2012 Romain Bignon, Christophe Benz
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

import os
from collections import OrderedDict

from woob.capabilities.account import CapAccount
from woob.exceptions import ModuleLoadError
from woob.tools.application.repl import ReplApplication
from woob.tools.application.console import ConsoleProgress
from woob.tools.application.formatters.iformatter import IFormatter

__all__ = ['AppConfig']


class ModuleInfoFormatter(IFormatter):
    def format_dict(self, minfo):
        result = '.------------------------------------------------------------------------------.\n'
        result += '| Module %-69s |\n' % minfo['name']
        result += "+-----------------.------------------------------------------------------------'\n"
        result += '| Version         | %s\n' % minfo['version']
        result += '| Maintainer      | %s\n' % minfo['maintainer']
        result += '| License         | %s\n' % minfo['license']
        result += '| Description     | %s\n' % minfo['description']
        result += '| Capabilities    | %s\n' % ', '.join(minfo['capabilities'])
        result += '| Installed       | %s\n' % minfo['installed']
        result += '| Location        | %s\n' % minfo['location']
        if 'config' in minfo:
            first = True
            for key, field in minfo['config'].items():
                label = field['label']
                if field['default'] is not None:
                    label += ' (default: %s)' % field['default']

                if first:
                    result += '|                 | \n'
                    result += '| Configuration   | %s: %s\n' % (key, label)
                    first = False
                else:
                    result += '|                 | %s: %s\n' % (key, label)
        result += "'-----------------'\n"
        return result


class AppConfig(ReplApplication):
    APPNAME = 'config'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2010-YEAR Christophe Benz, Romain Bignon'
    DESCRIPTION = "Console application to add/edit/remove backends, " \
                  "and to register new website accounts."
    SHORT_DESCRIPTION = "manage backends or register new accounts"
    EXTRA_FORMATTERS = {'info_formatter': ModuleInfoFormatter}
    COMMANDS_FORMATTERS = {'modules':     'table',
                           'list':        'table',
                           'info':        'info_formatter',
                           }
    DISABLE_REPL = True

    def load_default_backends(self):
        pass

    def do_add(self, line):
        """
        add MODULE_NAME [BACKEND_NAME] [PARAMETERS ...]

        Create a backend from a module. By default, if BACKEND_NAME is omitted,
        that's the module name which is used.

        You can specify parameters from command line in form "key=value".
        """
        if not line:
            print('You must specify a module name. Hint: use the "modules" command.', file=self.stderr)
            return 2

        module_name, options = self.parse_command_args(line, 2, 1)
        if options:
            options = options.split(' ')
        else:
            options = ()

        backend_name = None

        params = {}
        # set backend params from command-line arguments
        for option in options:
            try:
                key, value = option.split('=', 1)
            except ValueError:
                if backend_name is None:
                    backend_name = option
                else:
                    print('Parameters have to be formatted "key=value"', file=self.stderr)
                    return 2
            else:
                params[key] = value

        self.add_backend(module_name, backend_name or module_name, params)

    def do_register(self, line):
        """
        register MODULE

        Register a new account on a module.
        """
        self.register_backend(line)

    def do_confirm(self, backend_name):
        """
        confirm BACKEND

        For a backend which support CapAccount, parse a confirmation mail
        after using the 'register' command to automatically confirm the
        subscribe.

        It takes mail from stdin. Use it with postfix for example.
        """
        # Do not use the ReplApplication.load_backends() method because we
        # don't want to prompt user to create backend.
        self.woob.load_backends(names=[backend_name])
        try:
            backend = self.woob.get_backend(backend_name)
        except KeyError:
            print('Error: backend "%s" not found.' % backend_name, file=self.stderr)
            return 1

        if not backend.has_caps(CapAccount):
            print('Error: backend "%s" does not support accounts management' % backend_name, file=self.stderr)
            return 1

        mail = self.acquire_input()
        if not backend.confirm_account(mail):
            print('Error: Unable to confirm account creation', file=self.stderr)
            return 1
        return 0

    def do_list(self, line):
        """
        list [CAPS ..]

        Show backends.
        """
        caps = line.split()
        for backend_name, module_name, params in sorted(self.woob.backends_config.iter_backends()):
            try:
                module = self.woob.modules_loader.get_or_load_module(module_name)
            except ModuleLoadError as e:
                self.logger.warning('Unable to load module %r: %s' % (module_name, e))
                continue

            if caps and not module.has_caps(*caps):
                continue
            row = OrderedDict([('Name', backend_name),
                               ('Module', module_name),
                               ('Configuration', ', '.join(
                                   '%s=%s' % (key, ('*****' if key in module.config and module.config[key].masked
                                                    else value))
                                   for key, value in params.items())),
                               ])
            self.format(row)

    def do_enable(self, backend_name):
        """
        enable NAME

        Enable a backend.
        """
        try:
            self.woob.backends_config.edit_backend(backend_name, {'_enabled': '1'})
        except KeyError:
            print('Backend instance "%s" does not exist' % backend_name, file=self.stderr)
            return 1

    def do_disable(self, backend_name):
        """
        disable NAME

        Disable a backend.
        """
        try:
            self.woob.backends_config.edit_backend(backend_name, {'_enabled': '0'})
        except KeyError:
            print('Backend instance "%s" does not exist' % backend_name, file=self.stderr)
            return 1

    def do_remove(self, backend_name):
        """
        remove NAME

        Remove a backend.
        """
        if not self.woob.backends_config.remove_backend(backend_name):
            print('Backend instance "%s" does not exist' % backend_name, file=self.stderr)
            return 1

    def do_edit(self, line):
        """
        edit BACKEND

        Edit a backend
        """
        try:
            self.edit_backend(line)
        except KeyError:
            print('Error: backend "%s" not found' % line, file=self.stderr)
            return 1

    def do_modules(self, line):
        """
        modules [CAPS ...]

        Show available modules.
        """
        caps = line.split()
        for name, info in sorted(self.woob.repositories.get_all_modules_info(caps).items()):
            row = OrderedDict([('Name', name),
                               ('Capabilities', info.capabilities),
                               ('Description', info.description),
                               ('Installed', info.is_installed()),
                               ])
            self.format(row)

    def do_info(self, line):
        """
        info NAME

        Display information about a module.
        """
        if not line:
            print('You must specify a module name. Hint: use the "modules" command.', file=self.stderr)
            return 2

        minfo = self.woob.repositories.get_module_info(line)
        if not minfo:
            print('Module "%s" does not exist.' % line, file=self.stderr)
            return 1

        try:
            module = self.woob.modules_loader.get_or_load_module(line)
        except ModuleLoadError:
            module = None

        self.start_format()
        self.format(self.create_minfo_dict(minfo, module))


    def create_minfo_dict(self, minfo, module):
        module_info = {}
        module_info['name'] = minfo.name
        module_info['version'] = minfo.version
        module_info['maintainer'] = minfo.maintainer
        module_info['license'] = minfo.license
        module_info['description'] = minfo.description
        module_info['capabilities'] = minfo.capabilities
        repo_ver = self.woob.repositories.versions.get(minfo.name)
        module_info['installed'] = '%s%s' % (
            'yes' if module else 'no',
            ' (new version available)' if repo_ver and repo_ver > minfo.version else ''
        )
        module_info['location'] = '%s' % (minfo.url or os.path.join(minfo.path, minfo.name))
        if module:
            module_info['config'] = {}
            for key, field in module.config.items():
                module_info['config'][key] = {'label': field.label,
                                              'default': field.default,
                                              'description': field.description,
                                              'regexp': field.regexp,
                                              'choices': field.choices,
                                              'masked': field.masked,
                                              'required': field.required}
        return module_info

    def do_update(self, line):
        """
        update

        Update woob.
        """
        self.woob.update(ConsoleProgress(self))
        if self.woob.repositories.errors:
            print('Errors building modules: %s' % ', '.join(self.woob.repositories.errors.keys()), file=self.stderr)
            if not self.options.debug:
                print('Use --debug to get more information.', file=self.stderr)
            return 1
