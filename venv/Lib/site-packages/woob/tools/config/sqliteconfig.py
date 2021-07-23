# -*- coding: utf-8 -*-

# Copyright(C) 2019 Laurent Bachelier
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


import os
import sqlite3
import tempfile
from collections import Mapping, MutableMapping

import yaml

from woob.tools.compat import unicode

from .iconfig import ConfigError, IConfig
from .util import replace, time_buffer
from .yamlconfig import WoobDumper

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


__all__ = ['SQLiteConfig']


class VirtualRootDict(Mapping):
    def __init__(self, config):
        self.config = config

    def __getitem__(self, base):
        if base in self.config._tables:
            return VirtualDict(self.config, base)
        raise KeyError('%s table not found' % base)

    def __iter__(self):
        for base in self.config._tables:
            yield base

    def __len__(self):
        return len(self.config._tables)


class VirtualDict(MutableMapping):
    def __init__(self, config, base):
        self.config = config
        self.base = base

    def __getitem__(self, key):
        try:
            return self.config.get(self.base, key)
        except ConfigError:
            raise KeyError('%s key in %s table not found' % (key, self.base))

    def __contains__(self, key):
        return self.config.has(self.base, key)

    def __iter__(self):
        for key in self.config.keys(self.base):
            yield key

    def items(self):
        return self.config.items(self.base)

    def __len__(self):
        return self.config.count(self.base)

    def __delitem__(self, key):
        try:
            self.config.delete(self, self.base, key)
        except ConfigError:
            raise KeyError('%s key in %s table not found' % (key, self.base))

    def __setitem__(self, key, value):
        self.config.set(self.base, key, value)


class SQLiteConfig(IConfig):
    commit_since_seconds = 3600
    dump_since_seconds = 600

    def __init__(self, path, commit_since_seconds=None, dump_since_seconds=None, last_run=True, logger=None):
        self.path = path
        if commit_since_seconds:
            self.commit_since_seconds = commit_since_seconds
        if dump_since_seconds:
            self.dump_since_seconds = dump_since_seconds
        if self.commit_since_seconds:
            self.commit = time_buffer(since_seconds=self.commit_since_seconds, last_run=last_run, logger=logger)(self.commit)
        if self.dump_since_seconds:
            self.dump = time_buffer(since_seconds=self.dump_since_seconds, last_run=last_run, logger=logger)(self.dump)

    def load(self, default={}, optimize=True):
        self.storage = sqlite3.connect(self.path)
        self.storage.execute('PRAGMA page_size = 4096')
        if optimize:
            self.storage.execute('VACUUM')
            self.storage.execute('REINDEX')
        self._tables = set(self.tables())
        self.values = VirtualRootDict(self)

    def save(self, commit_since_seconds=None, dump_since_seconds=None):
        self.commit(since_seconds=commit_since_seconds)
        # No one would want immediate dumps, assume it means no dumps
        if self.dump_since_seconds:
            self.dump(since_seconds=dump_since_seconds)

    def force_save(self):
        self.save(commit_since_seconds=False, dump_since_seconds=False)

    def __exit__(self, t, v, tb):
        self.force_save()
        super(SQLiteConfig, self).__exit__(t, v, tb)

    def commit(self, **kwargs):
        kwargs.pop('since_seconds', None)
        self.storage.commit()

    def dump(self, **kwargs):
        kwargs.pop('since_seconds', None)
        target = os.path.splitext(self.path)[0] + '.sql'
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(self.path), delete=False) as f:
            for line in self.storage.iterdump():
                f.write(unicode(line).encode('utf-8'))
                f.write(b'\n')
        replace(f.name, target)

    def ensure_table(self, name):
        if name not in self._tables:
            self.storage.execute('''CREATE TABLE IF NOT EXISTS %s (
                key text PRIMARY KEY,
                value text
            );''' % name)
            self._tables.add(name)

    def tables(self):
        cur = self.storage.cursor()
        cur.execute('''SELECT name FROM sqlite_master
            WHERE type="table" AND name NOT LIKE "sqlite_%";''')
        return [k[0] for k in cur.fetchall()]

    def items(self, table, size=100):
        """
        Low memory way of listing all items.
        The size parameters alters how many items are fetched at a time.
        """
        cur = self.storage.cursor()
        cur.execute('SELECT key, value FROM %s;' % table)
        items = cur.fetchmany(size)
        while items:
            for key, strvalue in items:
                yield key, yaml.load(strvalue, Loader=Loader)
            items = cur.fetchmany(size)

    def keys(self, table, size=200):
        """
        Low memory way of listing all keys.
        The size parameters alters how many items are fetched at a time.
        """
        cur = self.storage.cursor()
        cur.execute('SELECT key FROM %s;' % table)
        items = cur.fetchmany(size)
        while items:
            for item in items:
                yield item[0]
            items = cur.fetchmany(size)

    def count(self, table):
        cur = self.storage.cursor()
        cur.execute('SELECT count(*) FROM %s;' % table)
        return cur.fetchone()[0]

    def get(self, *args, **kwargs):
        table = args[0]
        key = '.'.join(args[1:])
        self.ensure_table(table)
        if not key:
            return self.values[table]
        try:
            cur = self.storage.cursor()
            cur.execute('SELECT value FROM %s WHERE key=?;' % table, (key, ))
            row = cur.fetchone()
            if row is None:
                if 'default' in kwargs:
                    value = kwargs.get('default')
                else:
                    raise ConfigError()
            else:
                strvalue = row[0]
                value = yaml.load(strvalue, Loader=Loader)
        except TypeError:
            raise ConfigError()
        return value

    def set(self, *args):
        table = args[0]
        key = '.'.join(args[1:-1])
        if not key:
            raise ConfigError('A minimum of two levels are required.')
        value = args[-1]
        self.ensure_table(table)
        try:
            strvalue = yaml.dump(value, None, Dumper=WoobDumper, default_flow_style=False)
            cur = self.storage.cursor()
            cur.execute('''INSERT OR REPLACE INTO %s VALUES (?, ?)''' % table, (key, strvalue))
        except KeyError:
            raise ConfigError()
        except TypeError:
            raise ConfigError()

    def delete(self, *args):
        table = args[0]
        key = '.'.join(args[1:])
        if not key:
            if table in self._tables:
                cur = self.storage.cursor()
                cur.execute('DROP TABLE %s;' % table)
            else:
                raise ConfigError()
        else:
            self.ensure_table(table)
            cur = self.storage.cursor()
            cur.execute('DELETE FROM %s WHERE key=?;' % table, (key, ))
            if not cur.rowcount:
                raise ConfigError()

    def has(self, *args):
        table = args[0]
        key = '.'.join(args[1:])
        if not key:
            return table in self._tables
        cur = self.storage.cursor()
        cur.execute('SELECT count(*) FROM %s WHERE key=?;' % table, (key, ))
        return cur.fetchone()[0] > 0
