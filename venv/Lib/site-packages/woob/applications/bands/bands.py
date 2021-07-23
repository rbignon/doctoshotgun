# -*- coding: utf-8 -*-

# Copyright(C) 2018 Quentin Defenouillere
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


from woob.capabilities.base import empty
from woob.capabilities.bands import CapBands
from woob.tools.application.repl import ReplApplication, defaultcount
from woob.tools.application.formatters.iformatter import PrettyFormatter


__all__ = ['Appbands', 'BandInfoFormatter', 'BandListFormatter', 'FavoritesFormatter']


class BandInfoFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'name', 'genre', 'year', 'country', 'description')
    def format_obj(self, obj, alias):
        result = u'\n%s%s%s\n' % (self.BOLD, obj.name, self.NC)
        if not empty(obj.genre):
            result += 'Genre: %s\n' % obj.genre
        if not empty(obj.country):
            result += 'Country: %s\n' % obj.country
        if not empty(obj.year):
            result += 'Formed in: %s\n' % obj.year
        if not empty(obj.description):
            result += '%sDescription:%s\n' % (self.BOLD, self.NC)
            result += '%s\n' % obj.description
        return result.strip()


class BandListFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'name', 'short_description')

    def get_title(self, obj):
        return obj.name

    def get_description(self, obj):
        result = u''
        if not empty(obj.short_description):
            result += '%s\n' % obj.short_description
        result+='---------------------------------------------------------------------------'
        return result.strip()


class FavoritesFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'name', 'band_url', 'short_description')

    def get_title(self, obj):
        return obj.name

    def get_description(self, obj):
        result = u''
        if not empty(obj.short_description):
            result += '%s\n' % obj.short_description
        if not empty(obj.band_url):
            result += '\t%s\n' % obj.band_url
        result+='---------------------------------------------------------------------------'
        return result.strip()


class AlbumsFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'name', 'album_type', 'year', 'reviews')

    def format_obj(self, obj, alias):
        result = u'\n%s%s%s\n' % (self.BOLD, obj.name, self.NC)
        if not empty(obj.album_type):
            result += 'Album type: %s\n' % obj.album_type
        if not empty(obj.id):
            result += 'Link to album: %s\n' % obj.id
        if not empty(obj.year):
            result += 'Year of release: %s\n' % obj.year
        if not empty(obj.reviews):
            result += 'Reviews: %s\n' % obj.reviews
        result+='---------------------------------------------------------------------------'
        return result.strip()


class SuggestionsFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'name', 'description', 'url')

    def get_title(self, obj):
        return obj.name

    def get_description(self, obj):
        result = u''
        if not empty(obj.description):
            result += '%s\n' % obj.description
        if not empty(obj.url):
            result += '\tLink to band: %s\n' % obj.url
        result+='---------------------------------------------------------------------------'
        return result.strip()



class Appbands(ReplApplication):
    APPNAME = 'bands'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2018-YEAR Quentin Defenouillere'
    DESCRIPTION = "Console application allowing to display music bands and offer music suggestions."
    SHORT_DESCRIPTION = "display bands and suggestions"
    CAPS = CapBands
    DEFAULT_FORMATTER = 'table'
    EXTRA_FORMATTERS = {
        'band_search': BandListFormatter,
        'band_info': BandInfoFormatter,
        'get_favorites': FavoritesFormatter,
        'get_albums': AlbumsFormatter,
        'suggestion': SuggestionsFormatter
    }

    COMMANDS_FORMATTERS = {
        'search': 'band_search',
        'info': 'band_info',
        'favorites': 'get_favorites',
        'albums': 'get_albums',
        'suggestions': 'suggestion'
    }

    def main(self, argv):
        self.load_config()
        return ReplApplication.main(self, argv)

    @defaultcount(20)
    def do_search(self, pattern):
        """
        band PATTERN
        Search bands.
        """
        self.change_path(['search'])
        self.start_format()
        for band in self.do('iter_band_search', pattern, caps=CapBands):
            self.cached_format(band)

    def do_info(self, line):
        """
        info BAND_ID
        Get detailed info for specified band. Use the 'search' command to find bands.
        """
        band, = self.parse_command_args(line, 1, 1)
        _id, backend_name = self.parse_id(band)

        self.start_format()
        for info in self.do('get_info', _id, backends=backend_name, caps=CapBands):
            if info:
                self.format(info)

    @defaultcount(40)
    def do_albums(self, line):
        """
        albums BAND_ID
        Get the discography of a band.
        """
        albums, = self.parse_command_args(line, 1, 1)
        _id, backend_name = self.parse_id(albums)

        self.start_format()
        for album in self.do('get_albums', _id, backends=backend_name, caps=CapBands):
            self.cached_format(album)

    @defaultcount(100)
    def do_favorites(self, *ignored):
        """
        favorites
        Displays your favorite bands.
        """
        self.change_path(['favorites'])
        self.start_format()
        for favorite in self.do('get_favorites', caps=CapBands):
            self.cached_format(favorite)

    @defaultcount(100)
    def do_suggestions(self, *ignored):
        """
        suggestions
        Suggests bands depending on your favorite bands.
        """
        self.change_path(['suggestions'])
        self.start_format()
        for suggestion in self.do('suggestions', caps=CapBands):
            self.cached_format(suggestion)
