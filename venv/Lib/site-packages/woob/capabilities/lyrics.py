# -*- coding: utf-8 -*-

# Copyright(C) 2013
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


from .base import BaseObject, Capability, StringField

__all__ = ['SongLyrics', 'CapLyrics']


class SongLyrics(BaseObject):
    """
    Song lyrics object.
    """
    title = StringField('Title of the song')
    artist = StringField('Artist of the song')
    content = StringField('Lyrics of the song')


class CapLyrics(Capability):
    """
    Lyrics websites.
    """

    def iter_lyrics(self, criteria, pattern):
        """
        Search lyrics by artist or by song
        and iterate on results.

        :param criteria: 'artist' or 'song'
        :type criteria: str
        :param pattern: pattern to search
        :type pattern: str
        :rtype: iter[:class:`SongLyrics`]
        """
        raise NotImplementedError()

    def get_lyrics(self, _id):
        """
        Get a lyrics object from an ID.

        :param _id: ID of lyrics
        :type _id: str
        :rtype: :class:`SongLyrics`
        """
        raise NotImplementedError()
