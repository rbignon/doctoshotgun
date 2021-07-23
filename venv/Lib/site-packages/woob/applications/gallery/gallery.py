# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011  Noé Rubinstein
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

import os
from re import search, sub

from woob.tools.application.repl import ReplApplication, defaultcount
from woob.capabilities.base import empty
from woob.capabilities.gallery import CapGallery, BaseGallery, BaseImage
from woob.tools.application.formatters.iformatter import PrettyFormatter


__all__ = ['AppGallery']


class GalleryListFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'title')

    def get_title(self, obj):
        s = obj.title
        if hasattr(obj, 'cardinality') and not empty(obj.cardinality):
            s += u' (%d pages)' % obj.cardinality
        return s

    def get_description(self, obj):
        if hasattr(obj, 'description') and obj.description:
            return obj.description


class AppGallery(ReplApplication):
    APPNAME = 'gallery'
    VERSION = '3.0'
    COPYRIGHT = u'Copyright(C) 2011-2014 Noé Rubinstein'
    DESCRIPTION = 'gallery browses and downloads web image galleries'
    SHORT_DESCRIPTION = 'browse and download web image galleries'
    CAPS = CapGallery
    EXTRA_FORMATTERS = {'gallery_list': GalleryListFormatter}
    COMMANDS_FORMATTERS = {'search': 'gallery_list', 'ls': 'gallery_list'}
    COLLECTION_OBJECTS = (BaseGallery, BaseImage, )

    def __init__(self, *args, **kwargs):
        super(AppGallery, self).__init__(*args, **kwargs)

    @defaultcount(10)
    def do_search(self, pattern):
        """
        search PATTERN

        List galleries matching a PATTERN.
        """
        if not pattern:
            print('This command takes an argument: %s' % self.get_command_help('search', short=True), file=self.stderr)
            return 2

        self.start_format(pattern=pattern)
        for gallery in self.do('search_galleries', pattern=pattern):
            self.cached_format(gallery)

    def do_download(self, line):
        """
        download ID [FIRST [FOLDER]]

        Download a gallery.

        Begins at page FIRST (default: 0) and saves to FOLDER (default: title)
        """
        _id, first, dest = self.parse_command_args(line, 3, 1)

        if first is None:
            first = 0
        else:
            first = int(first)

        gallery = None
        _id, backend = self.parse_id(_id)
        for result in self.do('get_gallery', _id, backends=backend):
            if result:
                gallery = result

        if not gallery:
            print('Gallery not found: %s' % _id, file=self.stderr)
            return 3

        self.woob[backend].fillobj(gallery, ('title',))
        if dest is None:
            dest = sub('/', ' ', gallery.title)

        print("Downloading to %s" % dest)

        try:
            os.mkdir(dest)
        except OSError:
            pass  # ignore error on existing directory
        os.chdir(dest)  # fail here if dest couldn't be created

        i = 0
        for img in self.woob[backend].iter_gallery_images(gallery):
            i += 1
            if i < first:
                continue

            self.woob[backend].fillobj(img, ('url', 'data'))
            if img.data is None:
                self.woob[backend].fillobj(img, ('url', 'data'))
                if img.data is None:
                    print("Couldn't get page %d, exiting" % i, file=self.stderr)
                    break

            ext = search(r"\.([^\.]{1,5})$", img.url)
            if ext:
                ext = ext.group(1)
            else:
                ext = "jpg"

            name = '%03d.%s' % (i, ext)
            print('Writing file %s' % name)

            with open(name, 'wb') as f:
                f.write(img.data)

        os.chdir(os.path.pardir)

    def do_info(self, line):
        """
        info ID

        Get information about a gallery.
        """
        _id, = self.parse_command_args(line, 1, 1)

        gallery = self.get_object(_id, 'get_gallery')
        if not gallery:
            print('Gallery not found: %s' % _id, file=self.stderr)
            return 3

        self.start_format()
        self.format(gallery)
