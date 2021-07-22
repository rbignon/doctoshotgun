# -*- coding: utf-8 -*-

# Copyright(C) 2013 Pierre Mazière
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

import re

from woob.tools.compat import unicode

from .image import Thumbnail
from .base import Field, StringField, IntField, BaseObject
from .date import DeltaField
from .file import CapFile, BaseFile


__all__ = ['BaseAudio', 'CapAudio']


def decode_id(decode_id):
    def wrapper(func):
        def inner(self, *args, **kwargs):
            arg = unicode(args[0])
            _id = decode_id(arg)
            if _id is None:
                return None

            new_args = [_id]
            new_args.extend(args[1:])
            return func(self, *new_args, **kwargs)
        return inner
    return wrapper


class Album(BaseObject):
    """
    Represent an album
    """
    title = StringField('album name')
    author = StringField('artist name')
    year = IntField('release year')
    thumbnail = Field('Image associated to the album', Thumbnail)
    tracks_list = Field('list of tracks', list)

    @classmethod
    def decode_id(cls, _id):
        if _id:
            m = re.match('^(album)\.(.*)', _id)
            if m:
                return m.group(2)
            return _id


class Playlist(BaseObject):
    """
    Represent a playlist
    """
    title = StringField('playlist name')
    tracks_list = Field('list of tracks', list)

    @classmethod
    def decode_id(cls, _id):
        if _id:
            m = re.match('^(playlist)\.(.*)', _id)
            if m:
                return m.group(2)
            return _id


class BaseAudio(BaseFile):
    """
    Represent an audio file
    """
    duration =  DeltaField('file duration')
    bitrate =   IntField('file bit rate in Kbps')
    format =    StringField('file format')
    thumbnail = Field('Image associated to the file', Thumbnail)

    @classmethod
    def decode_id(cls, _id):
        if _id:
            m = re.match('^(audio)\.(.*)', _id)
            if m:
                return m.group(2)
            return _id


class CapAudio(CapFile):
    """
    Audio file provider
    """

    @classmethod
    def get_object_method(cls, _id):
        m = re.match('^(\w+)\.(.*)', _id)
        if m:
            if m.group(1) == 'album':
                return 'get_album'

            elif m.group(1) == 'playlist':
                return 'get_playlist'

            else:
                return 'get_audio'

    def search_audio(self, pattern, sortby=CapFile.SEARCH_RELEVANCE):
        """
        search for a audio file

        :param pattern: pattern to search on
        :type pattern: str
        :param sortby: sort by ...(use SEARCH_* constants)
        :rtype: iter[:class:`BaseAudio`]
        """
        return self.search_file(pattern, sortby)

    def search_album(self, pattern, sortby=CapFile.SEARCH_RELEVANCE):
        """
        search for an album
        :param pattern: pattern to search on
        :type pattern: str
        :rtype: iter[:class:`Album`]
        """
        raise NotImplementedError()

    def search_playlist(self, pattern, sortby=CapFile.SEARCH_RELEVANCE):
        """
        search for an album
        :param pattern: pattern to search on
        :type pattern: str
        :rtype: iter[:class:`Playlist`]
        """
        raise NotImplementedError()

    @decode_id(BaseAudio.decode_id)
    def get_audio(self, _id):
        """
        Get an audio file from an ID.

        :param id: audio file ID
        :type id: str
        :rtype: :class:`BaseAudio`]
        """
        return self.get_file(_id)

    @decode_id(Playlist.decode_id)
    def get_playlist(self, _id):
        """
        Get a playlist from an ID.

        :param id: playlist ID
        :type id: str
        :rtype: :class:`Playlist`]
        """
        raise NotImplementedError()

    @decode_id(Album.decode_id)
    def get_album(self, _id):
        """
        Get an album from an ID.

        :param id: album ID
        :type id: str
        :rtype: :class:`Album`]
        """
        raise NotImplementedError()
