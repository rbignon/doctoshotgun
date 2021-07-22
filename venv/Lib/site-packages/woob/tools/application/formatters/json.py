# -*- coding: utf-8 -*-

# Copyright(C) 2013-2014 Julien Hebert, Laurent Bachelier
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


from woob.tools.json import json, WoobEncoder

from .iformatter import IFormatter

__all__ = ['JsonFormatter', 'JsonLineFormatter']


class JsonFormatter(IFormatter):
    """
    Formats the whole list as a single JSON list object.
    """

    def __init__(self):
        super(JsonFormatter, self).__init__()
        self.queue = []

    def flush(self):
        self.output(json.dumps(self.queue, cls=WoobEncoder))

    def format_dict(self, item):
        self.queue.append(item)

    def format_collection(self, collection, only):
        self.queue.append(collection.to_dict())


class JsonLineFormatter(IFormatter):
    """
    Formats the list as received, with a JSON object per line.
    The advantage is that it can be streamed.
    """

    def format_dict(self, item):
        self.output(json.dumps(item, cls=WoobEncoder))


def test():
    from .iformatter import formatter_test_output as fmt
    assert fmt(JsonFormatter, {'foo': 'bar'}) == '[{"foo": "bar"}]\n'
    assert fmt(JsonLineFormatter, {'foo': 'bar'}) == '{"foo": "bar"}\n'
