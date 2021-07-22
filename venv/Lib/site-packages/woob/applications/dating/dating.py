# -*- coding: utf-8 -*-

# Copyright(C) 2010-2012 Romain Bignon
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

from copy import copy

from woob.core import CallErrors
from woob.tools.application.repl import ReplApplication
from woob.applications.msg import AppMsg
from woob.capabilities.dating import CapDating, OptimizationNotFound
from woob.tools.application.formatters.iformatter import PrettyFormatter


__all__ = ['AppDating']


class EventListFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('date', 'type')

    def get_title(self, event):
        s = u'(%s) %s' % (event.date, event.type)
        if hasattr(event, 'contact') and event.contact:
            s += u' — %s (%s)' % (event.contact.name, event.contact.id)

        return s

    def get_description(self, event):
        if hasattr(event, 'message'):
            return event.message


class AppDating(AppMsg):
    APPNAME = 'dating'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2010-YEAR Romain Bignon'
    DESCRIPTION = "Console application allowing to interact with various dating websites " \
                  "and to optimize seduction algorithmically."
    SHORT_DESCRIPTION = "interact with dating websites"
    STORAGE_FILENAME = 'dating.storage'
    STORAGE = {'optims': {}}
    CAPS = CapDating
    EXTRA_FORMATTERS = copy(AppMsg.EXTRA_FORMATTERS)
    EXTRA_FORMATTERS['events'] = EventListFormatter
    COMMANDS_FORMATTERS = copy(AppMsg.COMMANDS_FORMATTERS)
    COMMANDS_FORMATTERS['optim'] = 'table'
    COMMANDS_FORMATTERS['events'] = 'events'

    def load_default_backends(self):
        self.load_backends(CapDating, storage=self.create_storage(self.STORAGE_FILENAME))

    def main(self, argv):
        self.load_config()

        try:
            self.do('init_optimizations').wait()
        except CallErrors as e:
            self.bcall_errors_handler(e)

        optimizations = self.storage.get('optims')
        for optim, backends in optimizations.items():
            self.optims('start', backends, optim, store=False)

        return ReplApplication.main(self, argv)

    def do_query(self, id):
        """
        query ID

        Send a query to someone.
        """
        _id, backend_name = self.parse_id(id, unique_backend=True)

        for query in self.do('send_query', _id, backends=backend_name):
            print('%s' % query.message)

    def edit_optims(self, backend_names, optims_names, stop=False):
        if optims_names is None:
            print('Error: missing parameters.', file=self.stderr)
            return 2

        for optim_name in optims_names.split():
            backends_optims = {}
            for optim in self.do('get_optimization', optim_name, backends=backend_names):
                if optim:
                    backends_optims[optim.backend] = optim
            for backend_name, optim in backends_optims.items():
                if len(optim.CONFIG) == 0:
                    print('%s.%s does not require configuration.' % (backend_name, optim_name))
                    continue

                was_running = optim.is_running()
                if stop and was_running:
                    print('Stopping %s: %s' % (optim_name, backend_name))
                    optim.stop()
                params = optim.get_config()
                if params is None:
                    params = {}
                print('Configuration of %s.%s' % (backend_name, optim_name))
                print('-----------------%s-%s' % ('-' * len(backend_name), '-' * len(optim_name)))
                for key, value in optim.CONFIG.items():
                    params[key] = self.ask(value, default=params[key] if (key in params) else value.default)

                optim.set_config(params)
                if stop and was_running:
                    print('Starting %s: %s' % (optim_name, backend_name))
                    optim.start()

    def optims(self, function, backend_names, optims, store=True):
        if optims is None:
            print('Error: missing parameters.', file=self.stderr)
            return 2

        for optim_name in optims.split():
            try:
                if store:
                    storage_optim = set(self.storage.get('optims', optim_name, default=[]))
                self.stdout.write('%sing %s:' % (function.capitalize(), optim_name))
                for optim in self.do('get_optimization', optim_name, backends=backend_names):
                    if optim:
                        # It's useless to start a started optim, or to stop a stopped one.
                        if (function == 'start' and optim.is_running()) or \
                           (function == 'stop' and not optim.is_running()):
                            continue

                        # Optim is not configured and would be, ask user to do it.
                        if function == 'start' and len(optim.CONFIG) > 0 and optim.get_config() is None:
                            self.edit_optims(optim.backend, optim_name)

                        ret = getattr(optim, function)()
                        self.stdout.write(' ' + optim.backend)
                        if not ret:
                            self.stdout.write('(failed)')
                        self.stdout.flush()
                        if store:
                            if function == 'start' and ret:
                                storage_optim.add(optim.backend)
                            elif function == 'stop':
                                try:
                                    storage_optim.remove(optim.backend)
                                except KeyError:
                                    pass
                self.stdout.write('.\n')
            except CallErrors as errors:
                for backend, error, backtrace in errors:
                    if isinstance(error, OptimizationNotFound):
                        self.logger.error(u'Error(%s): Optimization "%s" not found' % (backend.name, optim_name))
                    else:
                        self.bcall_error_handler(backend, error, backtrace)
            if store:
                if len(storage_optim) > 0:
                    self.storage.set('optims', optim_name, list(storage_optim))
                else:
                    self.storage.delete('optims', optim_name)
        if store:
            self.storage.save()

    def complete_optim(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return ['list', 'start', 'stop', 'edit']
        elif len(args) == 3:
            return [backend.name for backend in self.enabled_backends]
        elif len(args) >= 4:
            if args[2] == '*':
                backend = None
            else:
                backend = args[2]
            optims = set()
            for optim in self.do('iter_optimizations', backends=backend):
                optims.add(optim.id)
            return sorted(optims - set(args[3:]))

    def do_optim(self, line):
        """
        optim [list | start | edit | stop] BACKEND [OPTIM1 [OPTIM2 ...]]

        All dating backends offer optimization services. This command can be
        manage them.
        Use * us BACKEND value to apply command to all backends.

        Commands:
        * list       list all available optimizations of a backend
        * start      start optimization services on a backend
        * edit       configure an optimization service for a backend
        * stop       stop optimization services on a backend
        """
        cmd, backend_name, optims_names = self.parse_command_args(line, 3)

        if backend_name == '*':
            backend_name = None
        elif backend_name is not None and backend_name not in [b.name for b in self.enabled_backends]:
            print('Error: No such backend "%s"' % backend_name, file=self.stderr)
            return 1

        if cmd == 'start':
            return self.optims('start', backend_name, optims_names)
        if cmd == 'stop':
            return self.optims('stop', backend_name, optims_names)
        if cmd == 'edit':
            self.edit_optims(backend_name, optims_names, stop=True)
            return
        if cmd == 'list' or cmd is None:
            if optims_names is not None:
                optims_names = optims_names.split()

            optims = {}
            backends = set()
            for optim in self.do('iter_optimizations', backends=backend_name):
                if optims_names is not None and optim.id not in optims_names:
                    continue
                if optim.is_running():
                    status = 'RUNNING'
                else:
                    status = '-------'
                if optim.id not in optims:
                    optims[optim.id] = {optim.backend: status}
                else:
                    optims[optim.id][optim.backend] = status
                backends.add(optim.backend)

            backends = sorted(backends)
            for name, backends_status in optims.items():
                line = [('name', name)]
                for b in backends:
                    try:
                        status = backends_status[b]
                    except KeyError:
                        status = ''
                    line.append((b, status))
                self.format(tuple(line))
            return
        print("No such command '%s'" % cmd, file=self.stderr)
        return 1

    def do_events(self, line):
        """
        events

        Display dating events.
        """
        self.change_path([u'events'])
        self.start_format()
        for event in self.do('iter_events'):
            self.cached_format(event)
