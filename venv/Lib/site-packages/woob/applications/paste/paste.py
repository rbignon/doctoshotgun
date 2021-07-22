# -*- coding: utf-8 -*-

# Copyright(C) 2011-2014 Laurent Bachelier
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

from base64 import b64decode, b64encode
import os
import codecs
import re
from random import choice
import sys

from woob.capabilities.paste import CapPaste, PasteNotFound
from woob.tools.application.repl import ReplApplication


__all__ = ['AppPaste']


class AppPaste(ReplApplication):
    APPNAME = 'paste'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2011-YEAR Laurent Bachelier'
    DESCRIPTION = "Console application allowing to post and get pastes from pastebins."
    SHORT_DESCRIPTION = "post and get pastes from pastebins"
    CAPS = CapPaste

    def main(self, argv):
        self.load_config()
        return ReplApplication.main(self, argv)

    def do_info(self, line):
        """
        info ID [ID2 [...]]

        Get information about pastes.
        """
        if not line:
            print('This command takes an argument: %s' % self.get_command_help('info', short=True), file=self.stderr)
            return 2

        self.start_format()
        for _id in line.split(' '):
            paste = self.get_object(_id, 'get_paste', ['id', 'title', 'language', 'public', 'contents'])
            if not paste:
                print('Paste not found: %s' % _id, file=self.stderr)

            self.format(paste)


    def do_get(self, line):
        """
        get ID

        Get a paste contents.
        """
        return self._get_op(line, binary=False, command='get')

    def do_get_bin(self, line):
        """
        get_bin ID

        Get a paste contents.
        File will be downloaded from binary services.
        """
        return self._get_op(line, binary=True, command='get_bin')

    def _get_op(self, _id, binary, command='get'):
        if not _id:
            print('This command takes an argument: %s' % self.get_command_help(command, short=True), file=self.stderr)
            return 2

        try:
            paste = self.get_object(_id, 'get_paste', ['contents'])
        except PasteNotFound:
            print('Paste not found: %s' % _id, file=self.stderr)
            return 3
        if not paste:
            print('Unable to handle paste: %s' % _id, file=self.stderr)
            return 1

        if binary:
            if self.interactive:
                if not self.ask('The console may become messed up. Are you sure you want to show a binary file on your terminal?', default=False):
                    print('Aborting.', file=self.stderr)
                    return 1
            if sys.version_info.major >= 3:
                output = self.stdout.buffer
            else:
                output = self.stdout.stream
            output.write(b64decode(paste.contents))
        else:
            if sys.version_info.major < 3:
                output = codecs.getwriter(self.encoding)(self.stdout)
            else:
                output = self.stdout
            output.write(paste.contents)
            # add a newline unless we are writing
            # in a file or in a pipe
            if output.isatty():
                output.write('\n')

    def do_post(self, line):
        """
        post [FILENAME]

        Submit a new paste.
        The filename can be '-' for reading standard input (pipe).
        If 'bin' is passed, file will be uploaded to binary services.
        """
        return self._post(line, binary=False)

    def do_post_bin(self, line):
        """
        post_bin [FILENAME]

        Submit a new paste.
        The filename can be '-' for reading standard input (pipe).
        File will be uploaded to binary services.
        """
        return self._post(line, binary=True)

    def _post(self, filename, binary):
        use_stdin = (not filename or filename == '-')
        if use_stdin:
            if binary:
                if sys.version_info.major >= 3:
                    contents = self.stdin.buffer.read()
                else:
                    contents = self.stdin.read()
            else:
                contents = self.acquire_input()
            if not len(contents):
                print('Empty paste, aborting.', file=self.stderr)
                return 1

        else:
            try:
                if binary:
                    m = open(filename, 'rb')
                else:
                    m = codecs.open(filename, encoding=self.options.encoding or self.encoding)
                with m as fp:
                    contents = fp.read()
            except IOError as e:
                print('Unable to open file "%s": %s' % (filename, e.strerror), file=self.stderr)
                return 1

        if binary:
            contents = b64encode(contents).decode('ascii')

        # get and sort the backends able to satisfy our requirements
        params = self.get_params()
        backends = {}
        for backend in self.woob.iter_backends():
            score = backend.can_post(contents, **params)
            if score:
                backends.setdefault(score, []).append(backend)
        # select a random backend from the best scores
        if len(backends):
            backend = choice(backends[max(list(backends.keys()))])
        else:
            print('No suitable backend found.', file=self.stderr)
            return 1

        p = backend.new_paste(_id=None)
        p.public = params['public']
        if self.options.title is not None:
            p.title = self.options.title
        else:
            p.title = os.path.basename(filename)
        p.contents = contents
        backend.post_paste(p, max_age=params['max_age'])
        print('Successfuly posted paste: %s' % p.page_url)

    def get_params(self):
        return {'public': self.options.public,
                'max_age': self.str_to_duration(self.options.max_age),
                'title': self.options.title}

    def str_to_duration(self, s):
        if s.strip().lower() == 'never':
            return False

        parts = re.findall(r'(\d*(?:\.\d+)?)\s*([A-z]+)', s)
        argsmap = {'Y|y|year|years|yr|yrs': 365.25 * 24 * 3600,
                   'M|o|month|months': 30.5 * 24 * 3600,
                   'W|w|week|weeks': 7 * 24 * 3600,
                   'D|d|day|days': 24 * 3600,
                   'H|h|hours|hour|hr|hrs': 3600,
                   'm|i|minute|minutes|min|mins': 60,
                   'S|s|second|seconds|sec|secs': 1}

        seconds = 0
        for number, unit in parts:
            for rx, secs in argsmap.items():
                if re.match('^(%s)$' % rx, unit):
                    seconds += float(number) * float(secs)

        return int(seconds)

    def add_application_options(self, group):
        group.add_option('-p', '--public',  action='store_true',
                         help='Make paste public.')
        group.add_option('-t', '--title', action='store',
                         help='Paste title',
                         type='string')
        group.add_option('-m', '--max-age', action='store',
                         help='Maximum age (duration), default "1 month", "never" for infinite',
                         type='string', default='1 month')
        group.add_option('-E', '--encoding', action='store',
                         help='Input encoding',
                         type='string')
