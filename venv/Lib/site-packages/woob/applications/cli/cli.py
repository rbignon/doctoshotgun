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

from __future__ import print_function

from woob.tools.application.repl import ReplApplication


__all__ = ['AppCli']


class AppCli(ReplApplication):
    APPNAME = 'cli'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2010-YEAR Romain Bignon'
    SYNOPSIS =  'Usage: %prog [-dqv] [-b backends] [-cnfs] capability method [arguments..]\n'
    SYNOPSIS += '       %prog [--help] [--version]'
    DESCRIPTION = "Console application to call a specific method on backends " \
                  "which implement the given capability."
    SHORT_DESCRIPTION = "call a method on backends"
    DISABLE_REPL = True

    def load_default_backends(self):
        pass

    def main(self, argv):
        if len(argv) < 3:
            print("Syntax: %s capability method [args ..]" % argv[0], file=self.stderr)
            return 2

        cap_s = argv[1]
        cmd = argv[2]
        args = argv[3:]

        self.load_backends(cap_s)

        for obj in self.do(cmd, *args):
            self.format(obj)

        self.flush()

        return 0
