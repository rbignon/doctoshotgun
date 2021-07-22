# -*- coding: utf-8 -*-

# Copyright(C) 2011  Romain Bignon
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

from datetime import timedelta
from email import message_from_string, message_from_file
from email.header import decode_header
from email.mime.text import MIMEText
from smtplib import SMTP
import os
import re
import unicodedata

from woob.capabilities.base import empty, BaseObject
from woob.capabilities.bugtracker import CapBugTracker, Query, Update, Project, Issue, IssueError
from woob.tools.application.repl import ReplApplication, defaultcount
from woob.tools.application.formatters.iformatter import IFormatter, PrettyFormatter
from woob.tools.compat import basestring, unicode
from woob.tools.html import html2text
from woob.tools.date import parse_french_date


__all__ = ['AppBugTracker']


try:
    input = raw_input
except NameError:
    pass


class IssueFormatter(IFormatter):
    MANDATORY_FIELDS = ('id', 'project', 'title', 'body', 'author')

    def format_attr(self, obj, attr):
        if not hasattr(obj, attr) or empty(getattr(obj, attr)):
            return u''

        value = getattr(obj, attr)
        if isinstance(value, BaseObject):
            value = value.name

        return self.format_key(attr.capitalize(), value)

    def format_key(self, key, value):
        return '%s %s\n' % (self.colored('%s:' % key, 'green'),
                            value)

    def format_obj(self, obj, alias):
        result = u'%s %s %s %s %s\n' % (self.colored(obj.project.name, 'blue', 'bold'),
                                        self.colored(u'—', 'cyan', 'bold'),
                                        self.colored(obj.fullid, 'red', 'bold'),
                                        self.colored(u'—', 'cyan', 'bold'),
                                        self.colored(obj.title, 'yellow', 'bold'))
        result += '\n%s\n\n' % obj.body
        result += self.format_key('Author', '%s (%s)' % (obj.author.name, obj.creation))
        result += self.format_attr(obj, 'status')
        result += self.format_attr(obj, 'priority')
        result += self.format_attr(obj, 'version')
        result += self.format_attr(obj, 'tracker')
        result += self.format_attr(obj, 'category')
        result += self.format_attr(obj, 'assignee')
        if hasattr(obj, 'fields') and not empty(obj.fields):
            for key, value in obj.fields.items():
                result += self.format_key(key.capitalize(), value)
        if hasattr(obj, 'attachments') and obj.attachments:
            result += '\n%s\n' % self.colored('Attachments:', 'green')
            for a in obj.attachments:
                result += '* %s%s%s <%s>\n' % (self.BOLD, a.filename, self.NC, a.url)
        if hasattr(obj, 'history') and obj.history:
            result += '\n%s\n' % self.colored('History:', 'green')
            for u in obj.history:
                result += '%s %s %s %s\n' % (self.colored('*', 'red', 'bold'),
                                             self.colored(u.date, 'yellow', 'bold'),
                                             self.colored(u'—', 'cyan', 'bold'),
                                             self.colored(u.author.name, 'blue', 'bold'))
                for change in u.changes:
                    result += '  - %s %s %s %s\n' % (self.colored(change.field, 'green'),
                                                     change.last,
                                                     self.colored('->', 'magenta'), change.new)
                if u.message:
                    result += '    %s\n' % html2text(u.message).strip().replace('\n', '\n    ')
        return result


class IssuesListFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ('id', 'project', 'status', 'title', 'category')

    def get_title(self, obj):
        return '%s - [%s] %s' % (obj.project.name, obj.status.name, obj.title)

    def get_description(self, obj):
        return obj.category


class AppBugTracker(ReplApplication):
    APPNAME = 'bugtracker'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2011-YEAR Romain Bignon'
    DESCRIPTION = "Console application allowing to create, edit, view bug tracking issues."
    SHORT_DESCRIPTION = "manage bug tracking issues"
    CAPS = CapBugTracker
    EXTRA_FORMATTERS = {'issue_info': IssueFormatter,
                        'issues_list': IssuesListFormatter,
                       }
    COMMANDS_FORMATTERS = {'get':     'issue_info',
                           'post':    'issue_info',
                           'edit':    'issue_info',
                           'search':  'issues_list',
                           'ls':      'issues_list',
                          }
    COLLECTION_OBJECTS = (Project, Issue, )

    def add_application_options(self, group):
        group.add_option('--author')
        group.add_option('--title')
        group.add_option('--assignee')
        group.add_option('--target-version', dest='version')
        group.add_option('--tracker')
        group.add_option('--category')
        group.add_option('--status')
        group.add_option('--priority')
        group.add_option('--start')
        group.add_option('--due')

    @defaultcount(10)
    def do_search(self, line):
        """
        search PROJECT

        List issues for a project.

        You can use these filters from command line:
           --author AUTHOR
           --title TITLE_PATTERN
           --assignee ASSIGNEE
           --target-version VERSION
           --category CATEGORY
           --status STATUS
        """
        query = Query()

        path = self.working_path.get()
        backends = []
        if line.strip():
            query.project, backends = self.parse_id(line, unique_backend=True)
        elif len(path) > 0:
            query.project = path[0]
        else:
            print('Please enter a project name', file=self.stderr)
            return 1

        query.author = self.options.author
        query.title = self.options.title
        query.assignee = self.options.assignee
        query.version = self.options.version
        query.category = self.options.category
        query.status = self.options.status

        self.change_path([query.project, u'search'])
        for issue in self.do('iter_issues', query, backends=backends):
            self.add_object(issue)
            self.format(issue)

    def complete_get(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()

    def do_get(self, line):
        """
        get ISSUE

        Get an issue and display it.
        """
        if not line:
            print('This command takes an argument: %s' % self.get_command_help('get', short=True), file=self.stderr)
            return 2

        issue = self.get_object(line, 'get_issue')
        if not issue:
            print('Issue not found: %s' % line, file=self.stderr)
            return 3
        self.format(issue)

    def complete_comment(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()

    def do_comment(self, line):
        """
        comment ISSUE [TEXT]

        Comment an issue. If no text is given, enter it in standard input.
        """
        id, text = self.parse_command_args(line, 2, 1)
        if text is None:
            text = self.acquire_input()

        id, backend_name = self.parse_id(id, unique_backend=True)
        update = Update(0)
        update.message = text

        self.do('update_issue', id, update, backends=backend_name).wait()

    def do_logtime(self, line):
        """
        logtime ISSUE HOURS [TEXT]

        Log spent time on an issue.
        """
        id, hours, text = self.parse_command_args(line, 3, 2)
        if text is None:
            text = self.acquire_input()

        try:
            hours = float(hours)
        except ValueError:
            print('Error: HOURS parameter may be a float', file=self.stderr)
            return 1

        id, backend_name = self.parse_id(id, unique_backend=True)
        update = Update(0)
        update.message = text
        update.hours = timedelta(hours=hours)

        self.do('update_issue', id, update, backends=backend_name).wait()

    def complete_remove(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()

    def do_remove(self, line):
        """
        remove ISSUE

        Remove an issue.
        """
        id, backend_name = self.parse_id(line, unique_backend=True)
        self.do('remove_issue', id, backends=backend_name).wait()

    ISSUE_FIELDS = (('title',    (None,       False)),
                    ('assignee', ('members',  True)),
                    ('version',  ('versions', True)),
                    ('tracker',  (None,       False)),#XXX
                    ('category', ('categories', False)),
                    ('status',   ('statuses', True)),
                    ('priority', (None,       False)),#XXX
                    ('start',    (None,       False)),
                    ('due',      (None,       False)),
                   )

    def get_list_item(self, objects_list, name):
        if name is None:
            return None

        for obj in objects_list:
            if obj.name.lower() == name.lower():
                return obj

        if not name:
            return None

        raise ValueError('"%s" is not found' % name)

    def sanitize_key(self, key):
        if isinstance(key, str):
            key = unicode(key, "utf8")
        key = unicodedata.normalize('NFKD', key).encode("ascii", "ignore")
        return key.replace(' ', '-').capitalize()

    def issue2text(self, issue, backend=None):
        if backend is not None and 'username' in backend.config:
            sender = backend.config['username'].get()
        else:
            sender = os.environ.get('USERNAME', 'bugtracker')
        output = u'From: %s\n' % sender
        for key, (list_name, is_list_object) in self.ISSUE_FIELDS:
            value = None
            if not self.interactive:
                value = getattr(self.options, key)
            if not value:
                value = getattr(issue, key)
            if not value:
                value = ''
            elif hasattr(value, 'name'):
                value = value.name

            if list_name is not None:
                objects_list = getattr(issue.project, list_name)
                if len(objects_list) == 0:
                    continue

            output += '%s: %s\n' % (self.sanitize_key(key), value)
            if list_name is not None:
                availables = ', '.join(['<%s>' % (o if isinstance(o, basestring) else o.name)
                                        for o in objects_list])
                output += 'X-Available-%s: %s\n' % (self.sanitize_key(key), availables)

        for key, value in issue.fields.items():
            output += '%s: %s\n' % (self.sanitize_key(key), value or '')
            # TODO: Add X-Available-* for lists

        output += '\n%s' % (issue.body or 'Please write your bug report here.')
        return output

    def text2issue(self, issue, m):
        # XXX HACK to support real incoming emails
        if 'Subject' in m:
            m['Title'] = m['Subject']

        for key, (list_name, is_list_object) in self.ISSUE_FIELDS:
            value = m.get(key)
            if value is None:
                continue

            new_value = u''
            for part in decode_header(value):
                if part[1]:
                    new_value += unicode(part[0], part[1])
                else:
                    new_value += part[0].decode('utf-8')
            value = new_value

            if is_list_object:
                objects_list = getattr(issue.project, list_name)
                value = self.get_list_item(objects_list, value)

            # FIXME: autodetect
            if key in ['start', 'due']:
                if len(value) > 0:
                    #value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                    value = parse_french_date(value)
                else:
                    value = None

            setattr(issue, key, value)

        for key in issue.fields.keys():
            value = m.get(self.sanitize_key(key))
            if value is not None:
                issue.fields[key] = value.decode('utf-8')

        content = u''
        for part in m.walk():
            if part.get_content_type() == 'text/plain':
                s = part.get_payload(decode=True)
                charsets = part.get_charsets() + m.get_charsets()
                for charset in charsets:
                    try:
                        if charset is not None:
                            content += unicode(s, charset)
                        else:
                            content += unicode(s, encoding='utf-8')
                    except UnicodeError as e:
                        self.logger.warning('Unicode error: %s' % e)
                        continue
                    except Exception as e:
                        self.logger.exception(e)
                        continue
                    else:
                        break

        issue.body = content

        m = re.search('([^< ]+@[^ >]+)', m['From'] or '')
        if m:
            return m.group(1)

    def edit_issue(self, issue, edit=True):
        backend = self.woob.get_backend(issue.backend)
        content = self.issue2text(issue, backend)
        while True:
            if self.stdin.isatty():
                content = self.acquire_input(content, {'vim': "-c 'set ft=mail'"})
                m = message_from_string(content.encode('utf-8'))
            else:
                m = message_from_file(self.stdin)

            try:
                email_to = self.text2issue(issue, m)
            except ValueError as e:
                if not self.stdin.isatty():
                    raise
                input("%s -- Press Enter to continue..." % unicode(e).encode("utf-8"))
                continue

            try:
                issue = backend.post_issue(issue)
                print('Issue %s %s' % (self.formatter.colored(issue.fullid, 'red', 'bold'),
                                       'updated' if edit else 'created'))
                if edit:
                    self.format(issue)
                elif email_to:
                    self.send_notification(email_to, issue)
                return 0
            except IssueError as e:
                if not self.stdin.isatty():
                    raise
                input("%s -- Press Enter to continue..." % unicode(e).encode("utf-8"))

    def send_notification(self, email_to, issue):
        text = """Hi,

You have successfuly created this ticket on the Woob tracker:

%s

You can follow your bug report on this page:

https://symlink.me/issues/%s

Regards,

Woob Team
""" % (issue.title, issue.id)
        msg = MIMEText(text, 'plain', 'utf-8')
        msg['Subject'] = 'Issue #%s reported' % issue.id
        msg['From'] = 'Woob <woob@woob.tech>'
        msg['To'] = email_to
        s = SMTP('localhost')
        s.sendmail('woob@woob.tech', [email_to], msg.as_string())
        s.quit()

    def do_post(self, line):
        """
        post PROJECT

        Post a new issue.

        If you are not in interactive mode, you can use these parameters:
           --title TITLE
           --assignee ASSIGNEE
           --target-version VERSION
           --category CATEGORY
           --status STATUS
        """
        if not line.strip():
            print('Please give the project name')
            return 1

        project, backend_name = self.parse_id(line, unique_backend=True)

        backend = self.woob.get_backend(backend_name)

        issue = backend.create_issue(project)
        issue.backend = backend.name

        return self.edit_issue(issue, edit=False)

    def complete_edit(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()
        if len(args) == 3:
            return list(dict(self.ISSUE_FIELDS).keys())

    def do_edit(self, line):
        """
        edit ISSUE [KEY [VALUE]]

        Edit an issue.
        If you are not in interactive mode, you can use these parameters:
           --title TITLE
           --assignee ASSIGNEE
           --target-version VERSION
           --category CATEGORY
           --status STATUS
        """
        _id, key, value = self.parse_command_args(line, 3, 1)
        issue = self.get_object(_id, 'get_issue')
        if not issue:
            print('Issue not found: %s' % _id, file=self.stderr)
            return 3

        return self.edit_issue(issue, edit=True)

    def complete_attach(self, text, line, *ignored):
        args = line.split(' ')
        if len(args) == 2:
            return self._complete_object()
        elif len(args) >= 3:
            return self.path_completer(args[2])

    def do_attach(self, line):
        """
        attach ISSUE FILENAME

        Attach a file to an issue (Not implemented yet).
        """
        print('Not implemented yet.', file=self.stderr)
