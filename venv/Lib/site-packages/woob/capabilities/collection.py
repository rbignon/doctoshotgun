# -*- coding: utf-8 -*-

# Copyright(C) 2010-2012  Nicolas Duhamel, Laurent Bachelier
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

from collections import OrderedDict

from .base import Capability, BaseObject, UserError, StringField, Field


__all__ = ['CapCollection', 'BaseCollection', 'Collection', 'CollectionNotFound']


class CollectionNotFound(UserError):
    def __init__(self, split_path=None):
        if split_path is not None:
            msg = 'Collection not found: %s' % '/'.join(split_path)
        else:
            msg = 'Collection not found'
        super(CollectionNotFound, self).__init__(msg)


class BaseCollection(BaseObject):
    """
    Inherit from this if you want to create an object that is *also* a Collection.
    However, this probably will not work properly for now.
    """

    def __init__(self, split_path, id=None, url=None):
        super(BaseCollection, self).__init__(id, url)
        self.split_path = split_path

    @property
    def basename(self):
        return self.split_path[-1] if self.path_level else None

    @property
    def parent_path(self):
        return self.split_path[0:-1] if self.path_level else None

    @property
    def path_level(self):
        return len(self.split_path)

    def to_dict(self):
        def iter_decorate(d):
            for key, value in d:
                if key == 'id' and self.backend is not None:
                    value = u'%s@%s' % (self.basename, self.backend)
                yield key, value

                if key == 'split_path':
                    yield key, '/'.join(value)

        fields_iterator = self.iter_fields()
        return OrderedDict(iter_decorate(fields_iterator))


class Collection(BaseCollection):
    """
    A Collection is a "fake" object returned in results, which shows you can get
    more results if you go into its path.

    It is a dumb object, it must not contain callbacks to a backend.

    Do not inherit from this class if you want to make a regular BaseObject
    a Collection, use BaseCollection instead.
    """
    title = StringField('Collection title')
    split_path = Field('Full collection path', list)

    def __init__(self, split_path=None, title=None, id=None, url=None):
        self.title = title
        super(Collection, self).__init__(split_path, id, url)

    def __unicode__(self):
        if self.title and self.basename:
            return u'%s (%s)' % (self.basename, self.title)
        elif self.basename:
            return u'%s' % self.basename
        else:
            return u'Unknown collection'


class CapCollection(Capability):
    def iter_resources_flat(self, objs, split_path, clean_only=False):
        """
        Call iter_resources() to fetch all resources in the tree.
        If clean_only is True, do not explore paths, only remove them.
        split_path is used to set the starting path.
        """
        for resource in self.iter_resources(objs, split_path):
            if isinstance(resource, Collection):
                if not clean_only:
                    for res in self.iter_resources_flat(objs, resource.split_path):
                        yield res
            else:
                yield resource

    def iter_resources(self, objs, split_path):
        """
        split_path is a list, either empty (root path) or with one or many
        components.
        """
        raise NotImplementedError()

    def get_collection(self, objs, split_path):
        """
        Get a collection for a given split path.
        If the path is invalid (i.e. can't be handled by this module),
        it should return None.
        """
        collection = Collection(split_path, None)
        return self.validate_collection(objs, collection) or collection

    def validate_collection(self, objs, collection):
        """
        Tests if a collection is valid.
        For compatibility reasons, and to provide a default way, it checks if
        the collection has at least one object in it. However, it is not very
        efficient or exact, and you are encouraged to override this method.
        You can replace the collection object entirely by returning a new one.
        """
        # Root
        if collection.path_level == 0:
            return
        try:
            i = self.iter_resources(objs, collection.split_path)
            next(i)
        except StopIteration:
            raise CollectionNotFound(collection.split_path)

    def _restrict_level(self, split_path, lmax=0):
        if len(split_path) > lmax:
            raise CollectionNotFound(split_path)


def test():
    c = Collection([])
    assert c.basename is None
    assert c.parent_path is None
    assert c.path_level == 0

    c = Collection([u'lol'])
    assert c.basename == u'lol'
    assert c.parent_path == []
    assert c.path_level == 1

    c = Collection([u'lol', u'cat'])
    assert c.basename == u'cat'
    assert c.parent_path == [u'lol']
    assert c.path_level == 2

    c = Collection([u'w', u'e', u'e', u'b', u'o', u'o', u'b'])
    assert c.basename == u'b'
    assert c.parent_path == [u'w', u'e', u'e', u'b', u'o', u'o']
    assert c.path_level == 7
