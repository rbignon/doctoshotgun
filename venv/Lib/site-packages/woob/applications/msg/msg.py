# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011  Christophe Benz
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
import datetime
import hashlib

from tempfile import NamedTemporaryFile
from lxml import etree

from woob.core import CallErrors
from woob.capabilities.base import empty
from woob.capabilities.messages import CapMessages, Message, Thread
from woob.capabilities.account import CapAccount
from woob.capabilities.contact import CapContact
from woob.tools.application.repl import ReplApplication, defaultcount
from woob.tools.application.formatters.iformatter import IFormatter
from woob.tools.html import html2text


__all__ = ['AppMsg']


class AtomFormatter(IFormatter):
    MANDATORY_FIELDS = ('title', 'date', 'sender', 'content')

    def start_format(self, **kwargs):
        self.output(u'<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"')
        self.output(u'xmlns:dc="http://purl.org/dc/elements/1.1/">\n')
        self.output(u'<title type="text">Atom feed by Woob</title>')  # TODO : get backend name
        self.output(u'<updated>%s</updated>' % datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"))
        m = hashlib.md5()
        m.update(datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"))
        self.output(u'<id>urn:md5:%s</id>' % m.hexdigest())

    def format_obj(self, obj, alias):
        elem = etree.Element('entry')

        title = etree.Element('title')
        title.text = obj.title
        elem.append(title)

        id = etree.Element('id')
        m = hashlib.md5()
        m.update(obj.content.encode('utf8', 'ascii'))
        id.text = "urn:md5:%s" % m.hexdigest()
        elem.append(id)

        link = etree.Element('link')
        link.attrib["href"] = obj.thread.id
        link.attrib["title"] = obj.title
        link.attrib["type"] = "text/html"
        elem.append(link)

        author = etree.Element('author')
        name = etree.Element('name')
        if obj.sender:
            name.text = obj.sender
        else:
            name.text = obj.backend
        author.append(name)
        elem.append(author)

        date = etree.Element('updated')
        date.text = obj.date.strftime("%Y-%m-%dT%H:%M:%SZ")
        elem.append(date)

        content = etree.Element('content')
        content.text = obj.content
        content.attrib["type"] = "html"
        elem.append(content)

        return etree.tostring(elem, pretty_print=True)

    def flush(self):
        self.output(u'</feed>')


class XHtmlFormatter(IFormatter):
    MANDATORY_FIELDS = ('title', 'date', 'sender', 'signature', 'content')

    def format_obj(self, obj, alias):
        result  = "<div>\n"
        result += "<h1>%s</h1>" % (obj.title)
        result += "<dl>"
        result += "<dt>Date</dt><dd>%s</dd>" % (obj.date.strftime('%Y-%m-%d %H:%M'))
        result += "<dt>Sender</dt><dd>%s</dd>" % (obj.sender)
        result += "<dt>Signature</dt><dd>%s</dd>" % (obj.signature)
        result += "</dl>"
        result += "<div>%s</div>" % (obj.content)
        result += "</div>\n"
        return result


class MessageFormatter(IFormatter):
    MANDATORY_FIELDS = ('title', 'date', 'sender', 'signature', 'content')

    def format_obj(self, obj, alias):
        result = u'%sTitle:%s %s\n' % (self.BOLD,
                                       self.NC, obj.title)
        result += u'%sDate:%s %s\n' % (self.BOLD,
                                       self.NC, obj.date.strftime('%Y-%m-%d %H:%M'))
        result += u'%sFrom:%s %s\n' % (self.BOLD,
                                       self.NC, obj.sender)
        if hasattr(obj, 'receivers') and obj.receivers:
            result += u'%sTo:%s %s\n' % (self.BOLD,
                                         self.NC,
                                         ', '.join(obj.receivers))

        if obj.flags & Message.IS_HTML:
            content = html2text(obj.content)
        else:
            content = obj.content

        result += '\n%s' % content

        if obj.signature:
            if obj.flags & Message.IS_HTML:
                signature = html2text(obj.signature)
            else:
                signature = obj.signature

            result += '\n-- \n%s' % signature
        return result


class MessagesListFormatter(IFormatter):
    MANDATORY_FIELDS = ()
    count = 0
    _list_messages = False

    def flush(self):
        self.count = 0

    def format_obj(self, obj, alias):
        if not self._list_messages:
            return self.format_dict_thread(obj, alias)
        else:
            return self.format_dict_messages(obj, alias)

    def format_dict_thread(self, obj, alias):
        self.count += 1
        if self.interactive:
            result = u'%s* (%d) %s (%s)%s' % (self.BOLD,
                                              self.count,
                                              obj.title, obj.backend,
                                              self.NC)
        else:
            result = u'%s* (%s) %s%s' % (self.BOLD, obj.id,
                                         obj.title,
                                         self.NC)
        if obj.date:
            result += u'\n             %s' % obj.date
        return result

    def format_dict_messages(self, obj, alias):
        if obj.flags == Thread.IS_THREADS:
            depth = 0
        else:
            depth = -1

        result = self.format_message(obj.backend, obj.root, depth)
        return result

    def format_message(self, backend, message, depth=0):
        if not message:
            return u''
        self.count += 1

        flags = '['
        if message.flags & message.IS_UNREAD:
            flags += 'N'
        else:
            flags += '-'
        if message.flags & message.IS_NOT_RECEIVED:
            flags += 'U'
        elif message.flags & message.IS_RECEIVED:
            flags += 'R'
        else:
            flags += '-'
        flags += ']'

        if self.interactive:
            result = u'%s%s* (%d)%s %s <%s> %s (%s)\n' % (depth * '  ',
                                                          self.BOLD,
                                                          self.count,
                                                          self.NC,
                                                          flags,
                                                          message.sender,
                                                          message.title,
                                                          backend)
        else:
            result = u'%s%s* (%s.%s@%s)%s %s <%s> %s\n' % (depth * '  ',
                                                           self.BOLD,
                                                           message.thread.id,
                                                           message.id,
                                                           backend,
                                                           self.NC,
                                                           flags,
                                                           message.sender,
                                                           message.title)
        if message.children:
            if depth >= 0:
                depth += 1
            for m in message.children:
                result += self.format_message(backend, m, depth)
        return result


class ProfileFormatter(IFormatter):
    def flush(self):
        pass

    def format_obj(self, obj, alias=None):
        return obj.get_text()


class AppMsg(ReplApplication):
    APPNAME = 'msg'
    OLD_APPNAME = 'boobmsg'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2010-YEAR Christophe Benz'
    DESCRIPTION = "Console application allowing to send messages on various websites and " \
                  "to display message threads and contents."
    SHORT_DESCRIPTION = "send and receive message threads"
    CAPS = CapMessages
    EXTRA_FORMATTERS = {'msglist':  MessagesListFormatter,
                        'msg':      MessageFormatter,
                        'xhtml':    XHtmlFormatter,
                        'atom':     AtomFormatter,
                        'profile' : ProfileFormatter,
                       }
    COMMANDS_FORMATTERS = {'list':          'msglist',
                           'show':          'msg',
                           'export_thread': 'msg',
                           'export_all':    'msg',
                           'ls':            'msglist',
                           'profile':       'profile',
                          }

    def add_application_options(self, group):
        group.add_option('-E', '--accept-empty',  action='store_true',
                         help='Send messages with an empty body.')
        group.add_option('-t', '--title', action='store',
                         help='For the "post" command, set a title to message',
                         type='string', dest='title')

    def load_default_backends(self):
        self.load_backends(CapMessages, storage=self.create_storage())

    def main(self, argv):
        self.load_config()
        return ReplApplication.main(self, argv)

    def do_status(self, line):
        """
        status

        Display status information about a backend.
        """
        if len(line) > 0:
            backend_name = line
        else:
            backend_name = None

        results = {}
        for field in self.do('get_account_status',
                             backends=backend_name,
                             caps=CapAccount):
            if field.backend in results:
                results[field.backend].append(field)
            else:
                results[field.backend] = [field]

        for name, fields in results.items():
            print(':: %s ::' % name)
            for f in fields:
                if f.flags & f.FIELD_HTML:
                    value = html2text(f.value)
                else:
                    value = f.value
                print('%s: %s' % (f.label, value))
            print('')

    def do_post(self, line):
        """
        post RECEIVER@BACKEND[,RECEIVER@BACKEND[...]] [TEXT]

        Post a message to the specified receivers.
        Multiple receivers are separated by a comma.

        If no text is supplied on command line, the content of message is read on stdin.
        """
        receivers, text = self.parse_command_args(line, 2, 1)
        if text is None:
            text = self.acquire_input()

        if not self.options.accept_empty and not text.strip():
            self.logger.warning(u'The message body is empty, use option --accept_empty to send empty messages')
            return

        for receiver in receivers.strip().split(','):
            receiver, backend_name = self.parse_id(receiver.strip(),
                                                   unique_backend=True)
            if not backend_name and len(self.enabled_backends) > 1:
                self.logger.warning(u'No backend specified for receiver "%s": message will be sent with all the '
                    'enabled backends (%s)' % (receiver,
                    ','.join(backend.name for backend in self.enabled_backends)))

            if '.' in receiver:
                # It's a reply
                thread_id, parent_id = receiver.rsplit('.', 1)
            else:
                # It's an original message
                thread_id = receiver
                parent_id = None
                try:
                    thread_id = self.threads[int(thread_id) - 1].id
                except (IndexError,ValueError):
                    pass

            thread = Thread(thread_id)
            message = Message(thread,
                              0,
                              title=self.options.title,
                              parent=Message(thread, parent_id) if parent_id else None,
                              content=text)

            try:
                self.do('post_message', message, backends=backend_name).wait()
            except CallErrors as errors:
                self.bcall_errors_handler(errors)
            else:
                if self.interactive:
                    print('Message sent sucessfully to %s' % receiver)

    threads = []
    messages = []

    @defaultcount(10)
    def do_list(self, arg):
        """
        list

        Display all threads.
        """
        if len(arg) > 0:
            try:
                thread = self.threads[int(arg) - 1]
            except (IndexError, ValueError):
                id, backend_name = self.parse_id(arg)
            else:
                id = thread.id
                backend_name = thread.backend

            self.messages = []
            cmd = self.do('get_thread', id, backends=backend_name)
            self.formatter._list_messages = True
        else:
            self.threads = []
            cmd = self.do('iter_threads')
            self.formatter._list_messages = False

        self.start_format()
        for thread in cmd:
            if not thread:
                continue
            if len(arg) > 0:
                for m in thread.iter_all_messages():
                    if not m.backend:
                        m.backend = thread.backend
                    self.messages.append(m)
            else:
                self.threads.append(thread)
            self.format(thread)

    def do_export_all(self, arg):
        """
        export_all

        Export All threads
        """

        def func(backend):
            for thread in backend.iter_threads():
                if not thread:
                    continue
                t = backend.fillobj(thread, None)
                for msg in t.iter_all_messages():
                    yield msg

        self.start_format()
        for msg in self.do(func):
            self.format(msg)

    def do_export_thread(self, arg):
        """
        export_thread ID

        Export the thread identified by ID
        """
        try:
            thread = self.threads[int(arg) - 1]
        except (IndexError, ValueError):
            _id, backend_name = self.parse_id(arg)
        else:
            _id = thread.id
            backend_name = thread.backend

        cmd = self.do('get_thread', _id, backends=backend_name)
        self.start_format()
        for thread in cmd:
            if thread is not None:
                thread, = self.do('fillobj', thread, None, backends=thread.backend)
                for msg in thread.iter_all_messages():
                    msg, = self.do('fillobj', msg, None, backends=thread.backend)
                    self.format(msg)

    def do_show(self, arg):
        """
        show MESSAGE

        Read a message
        """
        message = None
        if len(arg) == 0:
            print('Please give a message ID.', file=self.stderr)
            return 2

        try:
            message = self.messages[int(arg) - 1]
        except (IndexError, ValueError):
            # The message is not is the cache, we have now two cases:
            # 1) the user uses a number to get a thread in the cache
            # 2) the user gives a thread id
            try:
                thread = self.threads[int(arg) - 1]
                if not empty(thread.root):
                    message = thread.root
                else:
                    for thread in self.do('get_thread', thread.id, backends=thread.backend):
                        if thread is not None:
                            if not thread.root:
                                thread, = self.do('fillobj', thread, ('root',), backends=thread.backend)
                            message = thread.root
            except (IndexError, ValueError):
                _id, backend_name = self.parse_id(arg)
                for thread in self.do('get_thread', _id, backends=backend_name):
                    if thread is not None:
                        if not thread.root:
                            thread, = self.do('fillobj', thread, ('root',), backends=thread.backend)
                        message = thread.root
        if not empty(message):
            self.start_format()
            self.format(message)
            self.woob.do('set_message_read', message, backends=message.backend)
            return
        else:
            print('Message not found', file=self.stderr)
            return 3

    def do_profile(self, id):
        """
        profile ID

        Display a profile
        """
        _id, backend_name = self.parse_id(id, unique_backend=True)

        found = 0
        for contact in self.do('get_contact', _id, backends=backend_name, caps=CapContact):
            if contact:
                self.format(contact)
                found = 1

        if not found:
            self.logger.error(u'Profile not found')

    def do_photos(self, id):
        """
        photos ID

        Display photos of a profile
        """
        photo_cmd = self.config.get('photo_viewer')
        if photo_cmd is None:
            print("Configuration error: photo_viewer is undefined", file=self.stderr)
            return

        _id, backend_name = self.parse_id(id, unique_backend=True)

        found = 0
        for contact in self.do('get_contact', _id, backends=backend_name):
            if contact:
                # Write photo to temporary files
                tmp_files = []
                for photo in contact.photos.values():
                    suffix = '.jpg'
                    if '.' in photo.url.split('/')[-1]:
                        suffix = '.%s' % photo.url.split('/')[-1].split('.')[-1]
                    f = NamedTemporaryFile(suffix=suffix)

                    photo = self.woob[contact.backend].fillobj(photo, 'data')
                    f.write(photo.data)
                    tmp_files.append(f)
                os.system(photo_cmd % ' '.join([file.name for file in tmp_files]))
                found = 1

        if not found:
            self.logger.error(u'Profile not found')
