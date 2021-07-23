# -*- coding: utf-8 -*-

# Copyright(C) 2011 Laurent Bachelier
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

from woob.tools.compat import unicode

from .base import Capability, BaseObject, NotLoaded, StringField, BoolField, UserError


__all__ = ['PasteNotFound', 'BasePaste', 'CapPaste']


class PasteNotFound(UserError):
    """
    Raised when a paste is not found.
    """

    def __init__(self):
        return super(PasteNotFound, self).__init__("Paste not found")


class BasePaste(BaseObject):
    """
    Represents a pasted text.
    """
    title =         StringField('Title of paste')
    language =      StringField('Language of the paste')
    contents =      StringField('Content of the paste')
    public =        BoolField('Is this paste public?')

    def __init__(self, _id, title=NotLoaded, language=NotLoaded, contents=NotLoaded,
            public=NotLoaded, url=None):
        super(BasePaste, self).__init__(unicode(_id), url)

        self.title = title
        self.language = language
        self.contents = contents
        self.public = public

    @classmethod
    def id2url(cls, _id):
        """Overloaded in child classes provided by backends."""
        raise NotImplementedError()

    @property
    def page_url(self):
        """
        Get URL to page of this paste.
        """
        return self.id2url(self.id)


class CapPaste(Capability):
    """
    This capability represents the ability for a website backend to store plain text.
    """

    def new_paste(self, *args, **kwargs):
        """
        Get a new paste object for posting it with the backend.
        The parameters should be passed to the object init.

        :rtype: :class:`BasePaste`
        """
        raise NotImplementedError()

    def can_post(self, contents, title=None, public=None, max_age=None):
        """
        Checks if the paste can be pasted by this backend.
        Some properties are considered required (public/private, max_age) while others
        are just bonuses (language).

        contents: Can be used to check encodability, maximum length, etc.
        title: Can be used to check length, allowed characters. Should not be required.
        public: True must be public, False must be private, None do not care.
        max_age: Maximum time to live in seconds.

        A score of 0 means the backend is not suitable.
        A score of 1 means the backend is suitable.
        Higher scores means it is more suitable than others with a lower score.

        :rtype: int
        :returns: score
        """
        raise NotImplementedError()

    def get_paste(self, url):
        """
        Get a Paste from an ID or URL.

        :param _id: the paste id. It can be an ID or a page URL.
        :type _id: str
        :rtype: :class:`BasePaste`
        :raises: :class:`PasteNotFound`
        """
        raise NotImplementedError()

    def post_paste(self, paste, max_age=None):
        """
        Post a paste.

        :param paste: a Paste object
        :type paste: :class:`BasePaste`
        """
        raise NotImplementedError()
