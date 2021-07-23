# -*- coding: utf-8 -*-

# Copyright(C) 2010-2012  Christophe Benz, Romain Bignon, Laurent Bachelier
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

import atexit
import logging
import os
import re
import shlex
import signal
import sys
from cmd import Cmd
from collections import OrderedDict
from datetime import datetime
from optparse import IndentedHelpFormatter, OptionGroup, OptionParser

from woob.capabilities.base import BaseObject, FieldNotFound, UserError, empty
from woob.capabilities.collection import BaseCollection, CapCollection, Collection, CollectionNotFound
from woob.core import CallErrors
from woob.exceptions import BrowserQuestion, BrowserRedirect, DecoupledValidation
from woob.tools.application.formatters.iformatter import MandatoryFieldsNotFound
from woob.tools.compat import basestring, range, unicode
from woob.tools.misc import to_unicode
from woob.tools.path import WorkingPath

from .console import BackendNotGiven, ConsoleApplication
from .formatters.load import FormatterLoadError, FormattersLoader
from .results import ResultsCondition, ResultsConditionError

__all__ = ['NotEnoughArguments', 'TooManyArguments', 'ArgSyntaxError',
           'ReplApplication']


class NotEnoughArguments(Exception):
    pass


class TooManyArguments(Exception):
    pass


class ArgSyntaxError(Exception):
    pass


class ReplOptionParser(OptionParser):
    def format_option_help(self, formatter=None):
        if not formatter:
            formatter = self.formatter

        return '%s\n%s' % (formatter.format_commands(self.commands),
                           OptionParser.format_option_help(self, formatter))


class ReplOptionFormatter(IndentedHelpFormatter):
    def format_commands(self, commands):
        s = u''
        for section, cmds in commands.items():
            if len(cmds) == 0:
                continue
            if len(s) > 0:
                s += '\n'
            s += '%s Commands:\n' % section
            for c in cmds:
                c = c.split('\n')[0]
                s += '    %s\n' % c
        return s


def defaultcount(default_count=10):
    def deco(f):
        def inner(self, *args, **kwargs):
            oldvalue = self.options.count
            if self._is_default_count:
                self.options.count = default_count

            try:
                return f(self, *args, **kwargs)
            finally:
                self.options.count = oldvalue

        inner.__doc__ = f.__doc__
        assert inner.__doc__ is not None, "A command must have a docstring"
        inner.__doc__ += '\nDefault is limited to %s results.' % default_count

        return inner
    return deco


class MyCmd(Cmd, object):
    # Hack for Python 2, because Cmd doesn't inherit object, so its __init__ was not called when using super only
    pass


class ReplApplication(ConsoleApplication, MyCmd):
    """
    Base application class for Repl applications.
    """

    SYNOPSIS =  'Usage: %prog [-dqv] [-b backends] [-cnfs] [command [arguments..]]\n'
    SYNOPSIS += '       %prog [--help] [--version]'
    DISABLE_REPL = False

    EXTRA_FORMATTERS = {}
    DEFAULT_FORMATTER = 'multiline'
    COMMANDS_FORMATTERS = {}

    COLLECTION_OBJECTS = tuple()
    """Objects to allow in do_ls / do_cd"""

    woob_commands = set(['backends', 'condition', 'count', 'formatter', 'logging', 'select', 'quit', 'ls', 'cd'])
    hidden_commands = set(['EOF'])

    def __init__(self):
        super(ReplApplication, self).__init__(ReplOptionParser(self.SYNOPSIS, version=self._get_optparse_version()))

        copyright = self.COPYRIGHT.replace('YEAR', '%d' % datetime.today().year)
        self.intro = '\n'.join(('Welcome to %s%s%s v%s' % (self.BOLD, self.APPNAME, self.NC, self.VERSION),
                                '',
                                copyright,
                                'This program is free software: you can redistribute it and/or modify',
                                'it under the terms of the GNU Lesser General Public License as published by',
                                'the Free Software Foundation, either version 3 of the License, or',
                                '(at your option) any later version.',
                                '',
                                'Type "help" to display available commands.',
                                '',
                               ))
        self.formatters_loader = FormattersLoader()
        for key, klass in self.EXTRA_FORMATTERS.items():
            self.formatters_loader.register_formatter(key, klass)
        self.formatter = None
        self.commands_formatters = self.COMMANDS_FORMATTERS.copy()

        commands_help = self.get_commands_doc()
        self._parser.commands = commands_help
        self._parser.formatter = ReplOptionFormatter()

        results_options = OptionGroup(self._parser, 'Results Options')
        results_options.add_option('-c', '--condition', help='filter result items to display given a boolean expression. See CONDITION section for the syntax')
        results_options.add_option('-n', '--count', type='int',
                                   help='limit number of results (from each backends)')
        results_options.add_option('-s', '--select', help='select result item keys to display (comma separated)')
        self._parser.add_option_group(results_options)

        formatting_options = OptionGroup(self._parser, 'Formatting Options')
        available_formatters = self.formatters_loader.get_available_formatters()
        formatting_options.add_option('-f', '--formatter', choices=available_formatters,
                                      help='select output formatter (%s)' % u', '.join(available_formatters))
        formatting_options.add_option('--no-header', dest='no_header', action='store_true', help='do not display header')
        formatting_options.add_option('--no-keys', dest='no_keys', action='store_true', help='do not display item keys')
        formatting_options.add_option('-O', '--outfile', dest='outfile', help='file to export result')
        self._parser.add_option_group(formatting_options)

        self._interactive = False
        self.working_path = WorkingPath()
        self._change_prompt()

    @property
    def interactive(self):
        return self._interactive

    def _change_prompt(self):
        self.objects = []
        self.collections = []
        # XXX can't use bold prompt because:
        # 1. it causes problems when trying to get history (lines don't start
        #    at the right place).
        # 2. when typing a line longer than term width, cursor goes at start
        #    of the same line instead of new line.
        #self.prompt = self.BOLD + '%s> ' % self.APPNAME + self.NC
        if len(self.working_path.get()):
            wp_enc = unicode(self.working_path)
            self.prompt = '%s:%s> ' % (self.APPNAME, wp_enc)
        else:
            self.prompt = '%s> ' % (self.APPNAME)

    def change_path(self, split_path):
        self.working_path.location(split_path)
        self._change_prompt()

    def add_object(self, obj):
        self.objects.append(obj)

    def _complete_object(self):
        return [obj.fullid for obj in self.objects]

    def parse_id(self, id, unique_backend=False):
        if self.interactive:
            try:
                obj = self.objects[int(id) - 1]
            except (IndexError, ValueError):
                # Try to find a shortcut in the cache
                for obj in self.objects:
                    if id in obj.id:
                        id = obj.fullid
                        break
            else:
                if isinstance(obj, BaseObject):
                    id = obj.fullid
        try:
            return ConsoleApplication.parse_id(self, id, unique_backend)
        except BackendNotGiven as e:
            backend_name = None
            while not backend_name:
                print('This command works with an unique backend. Availables:')
                for index, (name, backend) in enumerate(e.backends):
                    print('%s%d)%s %s%-15s%s   %s' % (self.BOLD, index + 1, self.NC, self.BOLD, name, self.NC,
                          backend.DESCRIPTION))
                i = self.ask('Select a backend to proceed with "%s"' % id)
                if not i.isdigit():
                    if i not in dict(e.backends):
                        print('Error: %s is not a valid backend' % i, file=self.stderr)
                        continue
                    backend_name = i
                else:
                    i = int(i)
                    if i < 0 or i > len(e.backends):
                        print('Error: %s is not a valid choice' % i, file=self.stderr)
                        continue
                    backend_name = e.backends[i-1][0]

            return id, backend_name

    def get_object(self, _id, method, fields=None, caps=None):
        if self.interactive:
            try:
                obj = self.objects[int(_id) - 1]
            except (IndexError, ValueError):
                pass
            else:
                try:
                    backend = self.woob.get_backend(obj.backend)
                    actual_method = getattr(backend, method, None)
                    if actual_method is None:
                        return None
                    else:
                        if callable(actual_method):
                            obj, = self.do('fillobj', obj, fields, backends=backend)
                            return obj
                        else:
                            return None
                except UserError as e:
                    self.bcall_error_handler(backend, e, '')

        _id, backend_name = self.parse_id(_id)
        kargs = {}
        if caps is not None:
            kargs = {'caps': caps}
        backend_names = (backend_name,) if backend_name is not None else self.enabled_backends

        # if backend's service returns several objects, try to find the one
        # with wanted ID. If not found, get the last not None object.
        obj = None

        # remove backends that do not have the required method
        new_backend_names = []
        for backend in backend_names:
            if isinstance(backend, (str, unicode)):
                actual_backend = self.woob.get_backend(backend)
            else:
                actual_backend = backend
            if getattr(actual_backend, method, None) is not None:
                new_backend_names.append(backend)
        backend_names = tuple(new_backend_names)
        try:
            for objiter in self.do(method, _id, backends=backend_names, fields=fields, **kargs):
                if objiter:
                    obj = objiter
                    if objiter.id == _id:
                        return obj
        except CallErrors as e:
            if obj is not None:
                self.bcall_errors_handler(e)
            else:
                raise

        return obj

    def get_object_list(self, method=None, *args, **kwargs):
        # return cache if not empty
        if len(self.objects) > 0:
            return self.objects
        elif method is not None:
            kwargs['backends'] = self.enabled_backends
            for _object in self.do(method, *args, **kwargs):
                self.add_object(_object)
            return self.objects
        # XXX: what can we do without method?
        return tuple()

    def unload_backends(self, *args, **kwargs):
        self.objects = []
        self.collections = []
        return ConsoleApplication.unload_backends(self, *args, **kwargs)

    def load_backends(self, *args, **kwargs):
        self.objects = []
        self.collections = []
        return ConsoleApplication.load_backends(self, *args, **kwargs)

    def main(self, argv):
        cmd_args = argv[1:]
        if cmd_args:
            cmd_line = u' '.join(cmd_args)
            cmds = cmd_line.split(';')
            for cmd in cmds:
                ret = self.onecmd(cmd)
                if ret:
                    return ret
        elif self.DISABLE_REPL:
            self._parser.print_help()
            self._parser.exit()
        else:
            try:
                import readline
            except ImportError:
                pass
            else:
                # Remove '-' from delims
                readline.set_completer_delims(readline.get_completer_delims().replace('-', ''))

                history_filepath = os.path.join(self.woob.workdir, '%s_history' % self.APPNAME)
                if self.OLD_APPNAME:
                    # compatibility for old, non-woob names
                    history_filepath = self._get_preferred_path(
                        history_filepath, os.path.join(self.woob.workdir, '%s_history' % self.OLD_APPNAME)
                    )
                try:
                    readline.read_history_file(history_filepath)
                except IOError:
                    pass

                def savehist():
                    readline.write_history_file(history_filepath)
                atexit.register(savehist)

            self.intro += '\nLoaded backends: %s\n' % ', '.join(sorted(backend.name for backend in self.woob.iter_backends()))
            self._interactive = True
            self.cmdloop()

    def do(self, function, *args, **kwargs):
        """
        Call Woob.do(), passing count and selected fields given by user.
        """
        backends = kwargs.pop('backends', None)
        if backends is None:
            kwargs['backends'] = []
            for backend in self.enabled_backends:
                actual_function = getattr(backend, function, None) if isinstance(function, basestring) else function

                if callable(actual_function):
                    kwargs['backends'].append(backend)
        else:
            kwargs['backends'] = backends
        fields = kwargs.pop('fields', self.selected_fields)
        if not fields and fields != []:
            fields = self.selected_fields

        fields = self.parse_fields(fields)

        if fields and self.formatter.MANDATORY_FIELDS is not None:
            missing_fields = set(self.formatter.MANDATORY_FIELDS) - set(fields)
            # If a mandatory field is not selected, do not use the customized formatter
            if missing_fields:
                print('Warning: you do not select enough mandatory fields for the formatter. Fallback to another. Hint: use option -f', file=self.stderr)
                self.formatter = self.formatters_loader.build_formatter(ReplApplication.DEFAULT_FORMATTER)

        if self.formatter.DISPLAYED_FIELDS is not None:
            if fields is None:
                missing_fields = True
            else:
                missing_fields = set(fields) - set(self.formatter.DISPLAYED_FIELDS + self.formatter.MANDATORY_FIELDS)
            # If a selected field is not displayed, do not use the customized formatter
            if missing_fields:
                print('Warning: some selected fields will not be displayed by the formatter. Fallback to another. Hint: use option -f', file=self.stderr)
                self.formatter = self.formatters_loader.build_formatter(ReplApplication.DEFAULT_FORMATTER)

        return self.woob.do(self._do_complete, self.options.count, fields, function, *args, **kwargs)

    def _do_and_retry(self, *args, **kwargs):
        """
        This method is a wrapper around Woob.do(), and handle interactive
        errors which allow to retry.

        List of handled errors:
        - BrowserQuestion
        - BrowserRedirect
        - DecoupledValidation
        """

        if self.stdout.isatty():
            # Set a non-None value to all backends's request_information
            #
            # - None indicates non-interactive: do not trigger 2FA challenges,
            #   raise NeedInteractive* exceptions before doing so
            # - non-None indicates interactive: ok to trigger 2FA challenges,
            #   raise BrowserQuestion/AppValidation when facing one
            # It should be a dict because when non-empty, it will contain HTTP
            # headers for legal PSD2 AIS/PIS authentication.
            for backend in self.enabled_backends:
                key = 'request_information'
                if key in backend.config and backend.config[key].get() is None:
                    backend.config[key].set({})

        try:
            for obj in self.do(*args, **kwargs):
                yield obj
        except CallErrors as errors:
            # Errors which are not handled here and which will be re-raised.
            remaining_errors = []
            # Backends on which we will retry.
            backends = set()

            for backend, error, backtrace in errors.errors:
                if isinstance(error, BrowserQuestion):
                    for field in error.fields:
                        v = self.ask(field)
                        backend.config[field.id].set(v)
                elif isinstance(error, BrowserRedirect):
                    print(u'Open this URL in a browser:')
                    print(error.url)
                    print()
                    value = self.ask('Please enter the final URL')
                    backend.config['auth_uri'].set(value)
                elif isinstance(error, DecoupledValidation):
                    print(error.message)
                    # FIXME we should reset this value, in case another DecoupledValidation occurs
                    key = 'resume'
                    if key in backend.config:
                        backend.config[key].set(True)
                else:
                    # Not handled error.
                    remaining_errors.append((backend, error, backtrace))
                    continue

                backends.add(backend)

            if backends:
                # There is at least one backend on which we can retry, do it
                # only on this ones.
                kwargs['backends'] = backends
                try:
                    for obj in self._do_and_retry(*args, **kwargs):
                        yield obj
                except CallErrors as sub_errors:
                    # As we called _do_and_retry, these sub errors are not
                    # interactive ones, so we can add them to the remaining
                    # errors.
                    remaining_errors += sub_errors.errors

            errors.errors = remaining_errors
            if errors.errors:
                # If there are remaining errors, raise them.
                raise errors

    # -- command tools ------------
    def parse_command_args(self, line, nb, req_n=None):
        try:
            if sys.version_info.major >= 3:
                args = shlex.split(line)
            else:
                args = [arg.decode('utf-8') for arg in shlex.split(line.encode('utf-8'))]
        except ValueError as e:
            raise ArgSyntaxError(str(e))

        if nb < len(args):
            raise TooManyArguments('Command takes at most %d arguments' % nb)
        if req_n is not None and (len(args) < req_n):
            raise NotEnoughArguments('Command needs %d arguments' % req_n)

        if len(args) < nb:
            args += tuple(None for i in range(nb - len(args)))
        return args

    # -- cmd.Cmd methods ---------
    def postcmd(self, stop, line):
        """
        This REPL method is overridden to return None instead of integers
        to prevent stopping cmdloop().
        """
        if not isinstance(stop, bool):
            stop = None
        return stop

    def parseline(self, line):
        """
        This REPL method is overridden to search "short" alias of commands
        """
        cmd, arg, ignored = Cmd.parseline(self, line)

        if cmd is not None:
            names = set(name for name in self.get_names() if name.startswith('do_'))

            if 'do_' + cmd not in names:
                long = set(name for name in names if name.startswith('do_' + cmd))
                # if more than one result, ambiguous command, do nothing (error will display suggestions)
                if len(long) == 1:
                    cmd = long.pop()[3:]

        return cmd, arg, ignored

    def onecmd(self, line):
        """
        This REPL method is overridden to catch some particular exceptions.
        """
        line = to_unicode(line)
        cmd, arg, ignored = self.parseline(line)

        # Set the right formatter for the command.
        try:
            formatter_name = self.commands_formatters[cmd]
        except KeyError:
            formatter_name = self.DEFAULT_FORMATTER
        self.set_formatter(formatter_name)

        try:
            try:
                return super(ReplApplication, self).onecmd(line)
            except CallErrors as e:
                return self.bcall_errors_handler(e)
            except BackendNotGiven as e:
                print('Error: %s' % str(e), file=self.stderr)
                return os.EX_DATAERR
            except NotEnoughArguments as e:
                print('Error: not enough arguments. %s' % str(e), file=self.stderr)
                return os.EX_USAGE
            except TooManyArguments as e:
                print('Error: too many arguments. %s' % str(e), file=self.stderr)
                return os.EX_USAGE
            except ArgSyntaxError as e:
                print('Error: invalid arguments. %s' % str(e), file=self.stderr)
                return os.EX_USAGE
            except (KeyboardInterrupt, EOFError):
                # ^C during a command process doesn't exit application.
                print('\nAborted.')
                return signal.SIGINT + 128
        finally:
            self.flush()

    def emptyline(self):
        """
        By default, an emptyline repeats the previous command.
        Overriding this function disables this behaviour.
        """
        pass

    def default(self, line):
        print('Unknown command: "%s"' % line, file=self.stderr)
        cmd, arg, ignore = Cmd.parseline(self, line)
        if cmd is not None:
            names = set(name[3:] for name in self.get_names() if name.startswith('do_' + cmd))
            if len(names) > 0:
                print('Do you mean: %s?' % ', '.join(names), file=self.stderr)
        return os.EX_USAGE

    def completenames(self, text, *ignored):
        return [name for name in Cmd.completenames(self, text, *ignored) if name not in self.hidden_commands]

    def _shell_completion_items(self):
        items = super(ReplApplication, self)._shell_completion_items()
        items.update(
            set(self.completenames('')) -
            set(('debug', 'condition', 'count', 'formatter', 'logging', 'select', 'quit')))
        return items

    def path_completer(self, arg):
        dirname = os.path.dirname(arg)
        try:
            children = os.listdir(dirname or '.')
        except OSError:
            return ()
        l = []
        for child in children:
            path = os.path.join(dirname, child)
            if os.path.isdir(path):
                child += '/'
            l.append(child)
        return l

    def complete(self, text, state):
        """
        Override of the Cmd.complete() method to:

          * add a space at end of proposals
          * display only proposals for words which match the
            text already written by user.
        """
        super(ReplApplication, self).complete(text, state)

        # When state = 0, Cmd.complete() set the 'completion_matches' attribute by
        # calling the completion function. Then, for other states, it only tries to
        # get the right item in list.
        # So that's the good place to rework the choices.
        if state == 0:
            self.completion_matches = [choice for choice in self.completion_matches if choice.startswith(text)]

        try:
            match = self.completion_matches[state]
        except IndexError:
            return None
        else:
            if match[-1] != '/':
                return '%s ' % match
            return match

    # -- errors management -------------
    def bcall_error_handler(self, backend, error, backtrace):
        """
        Handler for an exception inside the CallErrors exception.

        This method can be overridden to support more exceptions types.
        """
        return super(ReplApplication, self).bcall_error_handler(backend, error, backtrace)

    def bcall_errors_handler(self, errors, ignore=()):
        if self.interactive:
            return super(ReplApplication, self).bcall_errors_handler(errors, 'Use "logging debug" option to print backtraces.', ignore)
        else:
            return super(ReplApplication, self).bcall_errors_handler(errors, ignore=ignore)

    # -- options related methods -------------
    def _handle_options(self):
        if self.options.formatter:
            self.commands_formatters = {}
            self.DEFAULT_FORMATTER = self.options.formatter
        self.set_formatter(self.DEFAULT_FORMATTER)

        if self.options.select:
            self.selected_fields = self.options.select.split(',')
        else:
            self.selected_fields = ['$direct']


        if self.options.count is not None:
            self._is_default_count = False
            if self.options.count <= 0:
                # infinite search
                self.options.count = None

        if self.options.condition:
            self.condition = ResultsCondition(self.options.condition)
        else:
            self.condition = None

        return super(ReplApplication, self)._handle_options()

    def get_command_help(self, command, short=False):
        try:
            func = getattr(self, 'do_' + command)
        except AttributeError:
            return None

        doc = func.__doc__
        assert doc is not None, "A command must have a docstring"

        lines = [line.strip() for line in doc.strip().split('\n')]
        if not lines[0].startswith(command):
            lines = [command, ''] + lines

        if short:
            return lines[0]

        return '\n'.join(lines)

    def get_commands_doc(self):
        names = set(name for name in self.get_names() if name.startswith('do_'))
        appname = self.APPNAME.capitalize()
        d = OrderedDict(((appname, []), ('Woob', [])))

        for name in sorted(names):
            cmd = name[3:]
            if cmd in self.hidden_commands.union(self.woob_commands).union(['help']):
                continue

            d[appname].append(self.get_command_help(cmd))
        if not self.DISABLE_REPL:
            for cmd in self.woob_commands:
                d['Woob'].append(self.get_command_help(cmd))

        return d

    # -- default REPL commands ---------
    def do_quit(self, arg):
        """
        Quit the application.
        """
        return True

    def do_EOF(self, arg):
        """
        Quit the command line interpreter when ^D is pressed.
        """
        # print empty line for the next shell prompt to appear on the first column of the terminal
        print()
        return self.do_quit(arg)

    def do_help(self, arg=None):
        """
        help [COMMAND]

        List commands, or get information about a command.
        """
        if arg:
            cmd_names = set(name[3:] for name in self.get_names() if name.startswith('do_'))
            if arg in cmd_names:
                command_help = self.get_command_help(arg)
                if command_help is None:
                    logging.warning(u'Command "%s" is undocumented' % arg)
                else:
                    lines = command_help.split('\n')
                    lines[0] = '%s%s%s' % (self.BOLD, lines[0], self.NC)
                    self.stdout.write('%s\n' % '\n'.join(lines))
            else:
                print('Unknown command: "%s"' % arg, file=self.stderr)
        else:
            cmds = self._parser.formatter.format_commands(self._parser.commands)
            self.stdout.write('%s\n' % cmds)
            self.stdout.write('Type "help <command>" for more info about a command.\n')
        return 2

    def complete_backends(self, text, line, begidx, endidx):
        choices = []
        commands = ['enable', 'disable', 'only', 'list', 'add', 'register', 'edit', 'remove', 'list-modules']
        available_backends_names = set(backend.name for backend in self.woob.iter_backends())
        enabled_backends_names = set(backend.name for backend in self.enabled_backends)

        args = line.split(' ')
        if len(args) == 2:
            choices = commands
        elif len(args) >= 3:
            if args[1] == 'enable':
                choices = sorted(available_backends_names - enabled_backends_names)
            elif args[1] == 'only':
                choices = sorted(available_backends_names)
            elif args[1] == 'disable':
                choices = sorted(enabled_backends_names)
            elif args[1] in ('add', 'register') and len(args) == 3:
                for name, module in sorted(self.woob.repositories.get_all_modules_info(self.CAPS).items()):
                    choices.append(name)
            elif args[1] == 'edit':
                choices = sorted(available_backends_names)
            elif args[1] == 'remove':
                choices = sorted(available_backends_names)

        return choices

    def do_backends(self, line):
        """
        backends [ACTION] [BACKEND_NAME]...

        Select used backends.

        ACTION is one of the following (default: list):
            * enable         enable given backends
            * disable        disable given backends
            * only           enable given backends and disable the others
            * list           list backends
            * add            add a backend
            * register       register a new account on a website
            * edit           edit a backend
            * remove         remove a backend
            * list-modules   list modules
        """
        line = line.strip()
        if line:
            args = line.split()
        else:
            args = ['list']

        action = args[0]
        given_backend_names = args[1:]

        for backend_name in given_backend_names:
            if action in ('add', 'register'):
                minfo = self.woob.repositories.get_module_info(backend_name)
                if minfo is None:
                    print('Module "%s" does not exist.' % backend_name, file=self.stderr)
                    return 1
                else:
                    if not minfo.has_caps(self.CAPS):
                        print('Module "%s" is not supported by this application => skipping.' % backend_name, file=self.stderr)
                        return 1
            else:
                if backend_name not in [backend.name for backend in self.woob.iter_backends()]:
                    print('Backend "%s" does not exist => skipping.' % backend_name, file=self.stderr)
                    return 1

        if action in ('enable', 'disable', 'only', 'add', 'register', 'edit', 'remove'):
            if not given_backend_names:
                print('Please give at least a backend name.', file=self.stderr)
                return 2

        given_backends = set(backend for backend in self.woob.iter_backends() if backend.name in given_backend_names)

        if action == 'enable':
            for backend in given_backends:
                self.enabled_backends.add(backend)
        elif action == 'disable':
            for backend in given_backends:
                try:
                    self.enabled_backends.remove(backend)
                except KeyError:
                    print('%s is not enabled' % backend.name, file=self.stderr)
        elif action == 'only':
            self.enabled_backends = set()
            for backend in given_backends:
                self.enabled_backends.add(backend)
        elif action == 'list':
            enabled_backends_names = set(backend.name for backend in self.enabled_backends)
            disabled_backends_names = set(backend.name for backend in self.woob.iter_backends()) - enabled_backends_names
            print('Enabled: %s' % ', '.join(enabled_backends_names))
            if len(disabled_backends_names) > 0:
                print('Disabled: %s' % ', '.join(disabled_backends_names))
        elif action == 'add':
            for name in given_backend_names:
                instname = self.add_backend(name, name)
                if instname:
                    self.load_backends(names=[instname])
        elif action == 'register':
            for name in given_backend_names:
                instname = self.register_backend(name)
                if isinstance(instname, basestring):
                    self.load_backends(names=[instname])
        elif action == 'edit':
            for backend in given_backends:
                enabled = backend in self.enabled_backends
                self.unload_backends(names=[backend.name])
                self.edit_backend(backend.name)
                for newb in self.load_backends(names=[backend.name]).values():
                    if not enabled:
                        self.enabled_backends.remove(newb)
        elif action == 'remove':
            for backend in given_backends:
                self.woob.backends_config.remove_backend(backend.name)
                self.unload_backends(backend.name)
        elif action == 'list-modules':
            modules = []
            print('Modules list:')
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
                print('[%s] %s%-15s%s   %s' % (loaded, self.BOLD, name, self.NC, info.description))

        else:
            print('Unknown action: "%s"' % action, file=self.stderr)
            return 1

        if len(self.enabled_backends) == 0:
            print('Warning: no more backends are loaded. %s is probably unusable.' % self.APPNAME.capitalize(), file=self.stderr)

    def complete_logging(self, text, line, begidx, endidx):
        levels = ('debug', 'info', 'warning', 'error', 'quiet', 'default')
        args = line.split(' ')
        if len(args) == 2:
            return levels
        return ()

    def do_logging(self, line):
        """
        logging [LEVEL]

        Set logging level.

        Availables: debug, info, warning, error.
        * quiet is an alias for error
        * default is an alias for warning
        """
        args = self.parse_command_args(line, 1, 0)
        levels = (('debug',   logging.DEBUG),
                  ('info',    logging.INFO),
                  ('warning', logging.WARNING),
                  ('error',   logging.ERROR),
                  ('quiet',   logging.ERROR),
                  ('default', logging.WARNING)
                 )

        if not args[0]:
            current = None
            for label, level in levels:
                if logging.root.level == level:
                    current = label
                    break
            print('Current level: %s' % current)
            return

        levels = dict(levels)
        try:
            level = levels[args[0]]
        except KeyError:
            print('Level "%s" does not exist.' % args[0], file=self.stderr)
            print('Availables: %s' % ' '.join(levels), file=self.stderr)
            return 2
        else:
            logging.root.setLevel(level)
            for handler in logging.root.handlers:
                handler.setLevel(level)

    def do_condition(self, line):
        """
        condition [EXPRESSION | off]

        If an argument is given, set the condition expression used to filter the results. See CONDITION section for more details and the expression.
        If the "off" value is given, conditional filtering is disabled.

        If no argument is given, print the current condition expression.
        """
        line = line.strip()
        if line:
            if line == 'off':
                self.condition = None
            else:
                try:
                    self.condition = ResultsCondition(line)
                except ResultsConditionError as e:
                    print('%s' % e, file=self.stderr)
                    return 2
        else:
            if self.condition is None:
                print('No condition is set.')
            else:
                print(str(self.condition))

    def do_count(self, line):
        """
        count [NUMBER | off]

        If an argument is given, set the maximum number of results fetched.
        NUMBER must be at least 1.
        "off" value disables counting, and allows infinite searches.

        If no argument is given, print the current count value.
        """
        line = line.strip()
        if line:
            if line == 'off':
                self.options.count = None
                self._is_default_count = False
            else:
                try:
                    count = int(line)
                except ValueError:
                    print('Could not interpret "%s" as a number.' % line, file=self.stderr)
                    return 2
                else:
                    if count > 0:
                        self.options.count = count
                        self._is_default_count = False
                    else:
                        self.options.count = None
                        self._is_default_count = False
        else:
            if self.options.count is None:
                print('Counting disabled.')
            else:
                print(self.options.count)

    def complete_formatter(self, text, line, *ignored):
        formatters = self.formatters_loader.get_available_formatters()
        commands = ['list', 'option'] + formatters
        options = ['header', 'keys']
        option_values = ['on', 'off']

        args = line.split(' ')
        if len(args) == 2:
            return commands
        if args[1] == 'option':
            if len(args) == 3:
                return options
            if len(args) == 4:
                return option_values
        elif args[1] in formatters:
            return list(set(name[3:] for name in self.get_names() if name.startswith('do_')))

    def do_formatter(self, line):
        """
        formatter [list | FORMATTER [COMMAND] | option OPTION_NAME [on | off]]

        If a FORMATTER is given, set the formatter to use.
        You can add a COMMAND to apply the formatter change only to
        a given command.

        If the argument is "list", print the available formatters.

        If the argument is "option", set the formatter options.
        Valid options are: header, keys.
        If on/off value is given, set the value of the option.
        If not, print the current value for the option.

        If no argument is given, print the current formatter.
        """
        args = line.strip().split()
        if args:
            if args[0] == 'list':
                print(', '.join(self.formatters_loader.get_available_formatters()))
            elif args[0] == 'option':
                if len(args) > 1:
                    if len(args) == 2:
                        if args[1] == 'header':
                            print('off' if self.options.no_header else 'on')
                        elif args[1] == 'keys':
                            print('off' if self.options.no_keys else 'on')
                    else:
                        if args[2] not in ('on', 'off'):
                            print('Invalid value "%s". Please use "on" or "off" values.' % args[2], file=self.stderr)
                            return 2
                        else:
                            if args[1] == 'header':
                                self.options.no_header = True if args[2] == 'off' else False
                            elif args[1] == 'keys':
                                self.options.no_keys = True if args[2] == 'off' else False
                else:
                    print('Don\'t know which option to set. Available options: header, keys.', file=self.stderr)
                    return 2
            else:
                if args[0] in self.formatters_loader.get_available_formatters():
                    if len(args) > 1:
                        self.commands_formatters[args[1]] = self.set_formatter(args[0])
                    else:
                        self.commands_formatters = {}
                        self.DEFAULT_FORMATTER = self.set_formatter(args[0])
                else:
                    print('Formatter "%s" is not available.\n'
                          'Available formatters: %s.' % (args[0], ', '.join(self.formatters_loader.get_available_formatters())), file=self.stderr)
                    return 1
        else:
            print('Default formatter: %s' % self.DEFAULT_FORMATTER)
            for key, klass in self.commands_formatters.items():
                print('Command "%s": %s' % (key, klass))

    def do_select(self, line):
        """
        select [FIELD_NAME]... | "$direct" | "$full"

        If an argument is given, set the selected fields.
        $direct selects all fields loaded in one http request.
        $full selects all fields using as much http requests as necessary.

        If no argument is given, print the currently selected fields.
        """
        line = line.strip()
        if line:
            split = line.split()
            self.selected_fields = split
        else:
            print(' '.join(self.selected_fields))

    # First sort in alphabetical of backend
    # Second, sort with ID
    def comp_key(self, obj):
        return (obj.backend, obj.id)

    @defaultcount(40)
    def do_ls(self, line):
        """
        ls [-d] [-U] [PATH]

        List objects in current path.
        If an argument is given, list the specified path.
        Use -U option to not sort results. It allows you to use a "fast path" to
        return results as soon as possible.
        Use -d option to display information about a collection (and to not
        display the content of it). It has the same behavior than the well
        known UNIX "ls" command.
        """
        # TODO: real parsing of options
        path = line.strip()
        only = False
        sort = True

        if '-U' in line.strip().partition(' '):
            path = line.strip().partition(' ')[-1]
            sort = False

        if '-d' in line.strip().partition(' '):
            path = None
            only = line.strip().partition(' ')[-1]

        if path:
            for _path in path.split('/'):
                # We have an argument, let's ch to the directory before the ls
                self.working_path.cd1(_path)

        objects = []
        collections = []
        self.objects = []

        self.start_format()

        for res in self._fetch_objects(objs=self.COLLECTION_OBJECTS):
            if isinstance(res, Collection):
                collections.append(res)
                if sort is False:
                    self.formatter.format_collection(res, only)
            else:
                if sort:
                    objects.append(res)
                else:
                    self._format_obj(res, only)

        if sort:
            objects.sort(key=self.comp_key)
            collections = self._merge_collections_with_same_path(collections)
            collections.sort(key=self.comp_key)
            for collection in collections:
                self.formatter.format_collection(collection, only)
            for obj in objects:
                self._format_obj(obj, only)

        if path:
            for _path in path.split('/'):
                # Let's go back to the parent directory
                self.working_path.up()
        else:
            # Save collections only if we listed the current path.
            self.collections = collections

    def _find_collection(self, collection, collections):
        for col in collections:
            if col.split_path == collection.split_path:
                return col
        return None

    def _merge_collections_with_same_path(self, collections):
        to_return = []
        for collection in collections:
            col = self._find_collection(collection, to_return)
            if col:
                col.backend += " %s" % collection.backend
            else:
                to_return.append(collection)
        return to_return

    def _format_obj(self, obj, only):
        if only is False or not hasattr(obj, 'id') or obj.id in only:
            self.cached_format(obj)


    def do_cd(self, line):
        """
        cd [PATH]

        Follow a path.
        ".." is a special case and goes up one directory.
        "" is a special case and goes home.
        """
        if not len(line.strip()):
            self.working_path.home()
        elif line.strip() == '..':
            self.working_path.up()
        else:
            self.working_path.cd1(line)

            collections = []
            try:
                for res in self.do('get_collection', objs=self.COLLECTION_OBJECTS,
                                   split_path=self.working_path.get(),
                                   caps=CapCollection):
                    if res:
                        collections.append(res)
            except CallErrors as errors:
                self.bcall_errors_handler(errors, CollectionNotFound)

            if len(collections):
                # update the path from the collection if possible
                if len(collections) == 1:
                    self.working_path.split_path = collections[0].split_path
            else:
                print(u"Path: %s not found" % unicode(self.working_path), file=self.stderr)
                self.working_path.restore()
                return 1

        self._change_prompt()

    def _fetch_objects(self, objs):
        split_path = self.working_path.get()

        try:
            for res in self._do_and_retry(
                'iter_resources',
                objs=objs,
                split_path=split_path,
                caps=CapCollection
            ):
                yield res
        except CallErrors as errors:
            self.bcall_errors_handler(errors, CollectionNotFound)


    def all_collections(self):
        """
        Get all objects that are collections: regular objects and fake dumb objects.
        """
        obj_collections = [obj for obj in self.objects if isinstance(obj, BaseCollection)]
        return obj_collections + self.collections

    def obj_to_filename(self, obj, dest=None, default=None):
        """
        This method can be used to get a filename from an object, using a mask
        filled by information of this object.

        All patterns are braces-enclosed, and are name of available fields in
        the object.

        :param obj: object
        :type obj: BaseObject
        :param dest: dest given by user (default None)
        :type dest: str
        :param default: default file mask (if not given, this is '{id}-{title}.{ext}')
        :type default: str
        :rtype: str
        """
        if default is None:
            default = '{id}-{title}.{ext}'
        if dest is None:
            dest = '.'
        if os.path.isdir(dest):
            dest = os.path.join(dest, default)

        def repl(m):
            field = m.group(1)
            if hasattr(obj, field):
                value = getattr(obj, field)
                if empty(value):
                    value = 'unknown'
                return re.sub('[?:/]', '-', '%s' % value)
            else:
                return m.group(0)
        return re.sub(r'\{(.+?)\}', repl, dest)

    # for cd & ls
    def complete_path(self, text, line, begidx, endidx):
        directories = set()
        if len(self.working_path.get()):
            directories.add('..')
        mline = line.partition(' ')[2]
        offs = len(mline) - len(text)

        # refresh only if needed
        if len(self.objects) == 0 and len(self.collections) == 0:
            try:
                self.objects, self.collections = self._fetch_objects(objs=self.COLLECTION_OBJECTS)
            except CallErrors as errors:
                self.bcall_errors_handler(errors, CollectionNotFound)

        collections = self.all_collections()
        for collection in collections:
            directories.add(collection.basename)

        return [s[offs:] for s in directories if s.startswith(mline)]

    def complete_ls(self, text, line, begidx, endidx):
        return self.complete_path(text, line, begidx, endidx)

    def complete_cd(self, text, line, begidx, endidx):
        return self.complete_path(text, line, begidx, endidx)

    # -- formatting related methods -------------
    def set_formatter(self, name):
        """
        Set the current formatter from name.

        It returns the name of the formatter which has been really set.
        """
        try:
            self.formatter = self.formatters_loader.build_formatter(name)
        except FormatterLoadError as e:
            print('%s' % e, file=self.stderr)
            if self.DEFAULT_FORMATTER == name:
                self.DEFAULT_FORMATTER = ReplApplication.DEFAULT_FORMATTER
            print('Falling back to "%s".' % (self.DEFAULT_FORMATTER), file=self.stderr)
            self.formatter = self.formatters_loader.build_formatter(self.DEFAULT_FORMATTER)
            name = self.DEFAULT_FORMATTER
        if self.options.no_header:
            self.formatter.display_header = False
        if self.options.no_keys:
            self.formatter.display_keys = False
        if self.options.outfile:
            self.formatter.outfile = self.options.outfile
        if self.interactive:
            self.formatter.interactive = True
        return name

    def set_formatter_header(self, string):
        pass

    def start_format(self, **kwargs):
        self.formatter.start_format(**kwargs)

    def cached_format(self, obj):
        self.add_object(obj)
        alias = None
        if self.interactive:
            alias = '%s' % len(self.objects)
        self.format(obj, alias=alias)

    def parse_fields(self, fields):
        if '$direct' in fields:
            return []
        if '$full' in fields:
            return None
        return fields

    def format(self, result, alias=None):
        fields = self.parse_fields(self.selected_fields)
        try:
            self.formatter.format(obj=result, selected_fields=fields, alias=alias)
        except FieldNotFound as e:
            print(e, file=self.stderr)
        except MandatoryFieldsNotFound as e:
            print('%s Hint: select missing fields or use another formatter (ex: multiline).' % e, file=self.stderr)

    def flush(self):
        self.formatter.flush()

    def do_debug(self, line):
        """
        debug

        Launch a debug Python shell
        """

        from woob.applications.debug import AppDebug

        app = AppDebug()
        locs = dict(application=self, woob=self.woob)
        if len(self.woob.backend_instances):
            locs['backend'] = next(iter(self.woob.backend_instances.values()))
            locs['browser'] = locs['backend'].browser

        banner = ('Woob debug shell\n\nAvailable variables:\n'
         + '\n'.join(['  %s: %s' % (k, v) for k, v in locs.items()]))

        funcs = [app.ipython, app.bpython, app.python]
        app.launch(funcs, locs, banner)
