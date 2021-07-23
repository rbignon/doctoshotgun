# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Christophe Benz
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

from optparse import OptionGroup

from woob.tools.application.base import Application
from woob.browser.elements import generate_table_element


class AppDebug(Application):
    APPNAME = 'debug'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2010-YEAR Christophe Benz'
    DESCRIPTION = "Console application to debug backends."
    SHORT_DESCRIPTION = "debug backends"

    def __init__(self, option_parser=None):
        super(AppDebug, self).__init__(option_parser)
        options = OptionGroup(self._parser, 'Debug options')
        options.add_option('-B', '--bpython', action='store_true', help='Prefer bpython over ipython')
        self._parser.add_option_group(options)

    def load_default_backends(self):
        pass

    def main(self, argv):
        """
        BACKEND

        Debug BACKEND.
        """
        try:
            backend_name = argv[1]
        except IndexError:
            print('Usage: %s BACKEND' % argv[0], file=self.stderr)
            return 1
        try:
            backend = self.woob.load_backends(names=[backend_name])[backend_name]
        except KeyError:
            print(u'Unable to load backend "%s"' % backend_name, file=self.stderr)
            return 1

        locs = dict(backend=backend, browser=backend.browser,
                    application=self, woob=self.woob,
                    generate_table_element=generate_table_element)
        banner = 'Woob debug shell\nBackend "%s" loaded.\nAvailable variables:\n' % backend_name \
                 + '\n'.join(['  %s: %s' % (k, v) for k, v in locs.items()])

        if self.options.bpython:
            funcs = [self.bpython, self.ipython, self.python]
        else:
            funcs = [self.ipython, self.bpython, self.python]
        self.launch(funcs, locs, banner)

    def launch(self, funcs, locs, banner):
        for func in funcs:
            try:
                func(locs, banner)
            except ImportError:
                continue
            else:
                break

    def ipython(self, locs, banner):
        try:
            from IPython import embed
            embed(user_ns=locs, banner2=banner)
        except ImportError:
            from IPython.Shell import IPShellEmbed
            shell = IPShellEmbed(argv=[])
            shell.set_banner(shell.IP.BANNER + '\n\n' + banner)
            shell(local_ns=locs, global_ns={})

    def bpython(self, locs, banner):
        from bpython import embed
        embed(locs, banner=banner)

    def python(self, locs, banner):
        import code
        try:
            import readline
            import rlcompleter
            readline.set_completer(rlcompleter.Completer(locs).complete)
            readline.parse_and_bind("tab:complete")
        except ImportError:
            pass
        code.interact(banner=banner, local=locs)
