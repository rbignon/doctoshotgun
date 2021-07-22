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


from .base import Capability, BaseObject, BoolField, StringField
from .date import DateField


__all__ = ['Content', 'Revision', 'CapContent']


class Content(BaseObject):
    """
    Content object.
    """
    title =         StringField('Title of content')
    author =        StringField('Original author of content')
    content =       StringField('Body')
    revision =      StringField('ID of revision')


class Revision(BaseObject):
    """
    Revision of a change on a content.
    """
    author =        StringField('Author of revision')
    comment =       StringField('Comment log about revision')
    timestamp =     DateField('Date of revision')
    minor =         BoolField('Is this change minor?')


class CapContent(Capability):
    def get_content(self, id, revision=None):
        """
        Get a content from an ID.

        :param id: ID of content
        :type id: str
        :param revision: if given, get the content at this revision
        :type revision: :class:`Revision`
        :rtype: :class:`Content`
        """
        raise NotImplementedError()

    def iter_revisions(self, id):
        """
        Iter revisions of a content.

        :param id: id of content
        :type id: str
        :rtype: iter[:class:`Revision`]
        """
        raise NotImplementedError()

    def push_content(self, content, message=None, minor=False):
        """
        Push a new revision of a content.

        :param content: object to push
        :type content: :class:`Content`
        :param message: log message to associate to new revision
        :type message: str
        :param minor: this is a minor revision
        :type minor: bool
        """
        raise NotImplementedError()

    def get_content_preview(self, content):
        """
        Get a HTML preview of a content.

        :param content: content object
        :type content: :class:`Content`
        :rtype: str
        """
        raise NotImplementedError()
