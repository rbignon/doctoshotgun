# -*- coding: utf-8 -*-

# Copyright(C) 2013 Julien Veyssier
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

from woob.capabilities.lyrics import CapLyrics
from woob.capabilities.base import empty
from woob.tools.application.repl import ReplApplication, defaultcount
from woob.tools.application.formatters.iformatter import IFormatter, PrettyFormatter


__all__ = ['AppLyrics', 'LyricsGetFormatter', 'LyricsListFormatter']


class LyricsGetFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'title', 'artist', 'content')

    def format_obj(self, obj, alias):
        result = u'%s%s%s\n' % (self.BOLD, obj.title, self.NC)
        result += 'ID: %s\n' % obj.fullid
        result += 'Title: %s\n' % obj.title
        result += 'Artist: %s\n' % obj.artist
        result += '\n%sContent%s\n' % (self.BOLD, self.NC)
        result += '%s' % obj.content
        return result


class LyricsListFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'title', 'artist')

    def get_title(self, obj):
        return obj.title

    def get_description(self, obj):
        artist = u''
        if not empty(obj.artist):
            artist = obj.artist
        return '%s' % artist


class AppLyrics(ReplApplication):
    APPNAME = 'lyrics'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2013-YEAR Julien Veyssier'
    DESCRIPTION = "Console application allowing to search for song lyrics on various websites."
    SHORT_DESCRIPTION = "search and display song lyrics"
    CAPS = CapLyrics
    EXTRA_FORMATTERS = {'lyrics_list': LyricsListFormatter,
                        'lyrics_get': LyricsGetFormatter,
                        }
    COMMANDS_FORMATTERS = {'search':    'lyrics_list',
                           'get':      'lyrics_get',
                           }
    SEARCH_CRITERIAS = ['artist', 'song']

    def complete_get(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()

    def do_get(self, id):
        """
        get ID

        Display lyrics of the song.
        """

        songlyrics = self.get_object(id, 'get_lyrics')
        if not songlyrics:
            print('Song lyrics not found: %s' % id, file=self.stderr)
            return 3

        self.start_format()
        self.format(songlyrics)

    def complete_search(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self.SEARCH_CRITERIAS

    @defaultcount(10)
    def do_search(self, line):
        """
        search [artist | song] [PATTERN]

        Search lyrics by artist name or by song title.
        """
        criteria, pattern = self.parse_command_args(line, 2, 2)
        self.change_path([u'search'])
        if not pattern:
            pattern = None

        self.start_format(pattern=pattern)
        for songlyrics in self.do('iter_lyrics', criteria, pattern):
            self.cached_format(songlyrics)
