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


from .base import Capability, BaseObject, StringField, IntField, UserError


__all__ = ['Subtitle', 'CapSubtitle']


class LanguageNotSupported(UserError):
    """
    Raised when the language is not supported
    """

    def __init__(self, msg='language is not supported'):
        super(LanguageNotSupported, self).__init__(msg)


class Subtitle(BaseObject):
    """
    Subtitle object.
    """
    name =      StringField('Name of subtitle')
    ext =       StringField('Extension of file')
    nb_cd =     IntField('Number of cd or files')
    language =  StringField('Language of the subtitle')
    description=StringField('Description of corresponding video')

    def __init__(self, id='', name='', url=None):
        super(Subtitle, self).__init__(id, url)
        self.name = name


class CapSubtitle(Capability):
    """
    Subtitle providers.
    """

    def iter_subtitles(self, pattern):
        """
        Search subtitles and iterate on results.

        :param pattern: pattern to search
        :type pattern: str
        :rtype: iter[:class:`Subtitle`]
        """
        raise NotImplementedError()

    def get_subtitle(self, _id):
        """
        Get a subtitle object from an ID.

        :param _id: ID of subtitle
        :type _id: str
        :rtype: :class:`Subtitle`
        """
        raise NotImplementedError()

    def get_subtitle_file(self, _id):
        """
        Get the content of the subtitle file.

        :param _id: ID of subtitle
        :type _id: str
        :rtype: str
        """
        raise NotImplementedError()
