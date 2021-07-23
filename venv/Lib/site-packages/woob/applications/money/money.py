# -*- coding: utf-8 -*-

# Copyright(C) 2018-2021  Bruno Chabrier
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

# start with:
# set PYTHONPATH=D:\Dropbox\Projets\boomoney
# D:\Dropbox\Projets\boomoney\scripts\bin\woob.exe money -N

import signal
import sys

from threading import Thread, Lock
from io import StringIO
import os
import re
import subprocess
import datetime
from optparse import OptionGroup

import asyncio
from asyncio.subprocess import PIPE
from asyncio import create_subprocess_exec

import shutil
from colorama import init, Fore, Style

from woob.tools.compat import unicode
from woob.capabilities.bank import AccountType
from woob.applications.bank import Appbank
from woob.applications.bank.bank import OfxFormatter
from woob.tools.application.formatters.simple import SimpleFormatter


__all__ = ['AppMoney']


def handler(signum, frame):
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    print('Interrupted', file=sys.__stderr__)
    for t in HistoryThread.allthreads:
        t.terminate()
    sys.exit()


signal.signal(signal.SIGINT, handler)

printMutex = Lock()
numMutex = Lock()
backupMutex = Lock()


class MoneyOfxFormatter(OfxFormatter):

    MANDATORY_FIELDS = tuple(set(OfxFormatter.MANDATORY_FIELDS).union({"type"}) - {"id"})

    def start_format(self, **kwargs):
        self.seen = set()

        # MSMoney only supports CHECKING accounts
        self.original_type = kwargs['account'].type

        # we collect this formatter output because we will need to do some processing to restore the account type
        self.original_outfile = self.outfile
        self.outfile = StringIO()

        kwargs['account'].type = AccountType.CHECKING
        super(MoneyOfxFormatter, self).start_format(**kwargs)
        kwargs['account'].type = self.original_type

    def format_obj(self, obj, alias):
        cat = obj.category
        obj.category = obj.raw
        result = super(MoneyOfxFormatter, self).format_obj(obj, alias)
        obj.category = cat
        return result

    def output(self, formatted):
        if self.outfile != sys.stdout:
            self.outfile.write(formatted + os.linesep)
        else:
            super(MoneyOfxFormatter, self).output(formatted)

    def flush(self):
        super(MoneyOfxFormatter, self).flush()

        # we process the output by restoring the account type
        collected_output = self.outfile.getvalue()
        if hasattr(self, 'original_outfile'):
            # do the test because when killed, flush might be called before original_outfile is called
            self.outfile = self.original_outfile
            self.outfile.write(re.sub('<ACCTTYPE>[^\r]*\r', '<ACCTTYPE>' + str(self.original_type) + '\r', collected_output))


class ListFormatter(SimpleFormatter):
    def output(self, formatted):
        if self.outfile != sys.stdout:
            self.outfile.write(formatted + os.linesep)
        else:
            super(ListFormatter, self).output(formatted)


class HistoryThread(Thread):
    allthreads = []

    def __init__(self, money, accounts):
        Thread.__init__(self)
        self.daemon = True
        HistoryThread.allthreads.append(self)
        self.money = money
        self.accounts = accounts
        self.last_dates = {}
        for a in self.accounts:
            self.last_dates[a] = self.money.config.get(a, 'last_date', default='')

    def terminate(self):
        pass

    def retrieve_history(self, account):
        return self.money.retrieve_history(account)

    def run(self):
        for account in self.accounts:
            last_date = self.money.get_history_from_thread(account, self)
            if not self.money.options.no_import:
                self.last_dates[account] = last_date


class HistoryThreadAsAProcess(HistoryThread):

    def __init__(self, money, accounts):
        super(HistoryThreadAsAProcess, self).__init__(money, accounts)
        self.ofxcontent = ""
        self.stderr = ""
        self.loop = asyncio.new_event_loop()

    def terminate(self):
        self.process.terminate()
        return super(HistoryThreadAsAProcess, self).terminate()

    def retrieve_history(self, account):
        self.ofxcontent[account] = re.sub(r'\r\r\n', r'\n', self.ofxcontent[account])
        return self.ofxcontent[account], self.stderrcontent[account]

    async def _read_stream(self, stream, callback):
        while True:
            line = await stream.readline()
            if line:
                callback(line)
            else:
                break

    async def run_process(self):
        id, backend = self.accounts[0].split("@")

        propagated_options = []
        for o in vars(self.money.options):
            switcher = {
                'backends': False,
                'exclude_backends': False,
                'insecure': True,
                'nss': True,
                'debug': True,
                'quiet': False,
                'verbose': True,
                'logging_file': False,
                'save_responses': False,
                'export_session': False,
                'shell_completion': False,
                'auto_update': False,
                'condition': False,
                'count': True,
                'select': False,
                'formatter': False,
                'no_header': False,
                'no_keys': False,
                'outfile': False,
                'list': False,
                'force': True,
                'accounts': False,
                'until_date': True,
                'no_import': False,
                'display': False
            }
            propagate = switcher.get(o, None)
            if propagate is None:
                self.money.logger.warning("Unhandled option %s." % o)
                propagate = False
            if propagate:
                value = getattr(self.money.options, o)
                o = o.replace("_", "-")
                if value is not None:
                    if value == 0:
                        pass
                    elif value == 1:
                        propagated_options += ["--" + o]
                    else:
                        propagated_options += ["--" + o + "=" + str(value)]

        self.cmd = [
            sys.executable,  # D:\...\woob.exe
            sys.path[0],
            'money',
            '--no-import',
            '--display',
            '--backends=' + backend,
            '--accounts=' + ",".join(self.accounts)
        ] + propagated_options
        self.money.logger.info(" ".join(self.cmd))

        self.process = await create_subprocess_exec(*self.cmd, stdout=PIPE, stderr=PIPE)

        def handle_stdout_line(line):
            line = line.decode("CP1252")
            if not re.search(r"^\([0-9]+/[0-9]+\) ", line) is None:
                account = re.split(r"\s", line)[1]
                self.ofxcontent[account] = self.stdout
                self.stderrcontent[account] = self.stderr
                last_date = self.money.get_history_from_thread(account, self)

                if not self.money.options.no_import:
                    self.last_dates[account] = last_date

                self.stdout = ""
                self.stderr = ""
                self.stdouterr = ""
                self.intransaction = False
                return

            if line.startswith("Hint: There are more results available"):
                self.stderr += line
                self.stdouterr += line
                return

            if line.startswith("OFXHEADER:"):
                self.intransaction = True

            if self.intransaction:
                self.stdout += line
            else:
                self.stderr += line
            self.stdouterr += line

            # print("STDOUT: {}".format(line))

        def handle_stderr_line(line):
            line = line.decode("CP1252")
            self.stderr += line
            self.stdouterr += line
            # print("STDERR: {}".format(line))

        self.stdout = ""
        self.stderr = ""
        self.stdouterr = ""
        self.ofxcontent = dict()
        self.stderrcontent = dict()
        self.intransaction = False

        await asyncio.wait(
                [
                    self._read_stream(self.process.stdout, handle_stdout_line),
                    self._read_stream(self.process.stderr, handle_stderr_line)
                ]
            )

        await self.process.wait()

    def run(self):
        self.loop.run_until_complete(self.run_process())
        if self.stdouterr != "":
            self.money.print(" ".join(self.cmd) + "\n" + self.stdouterr)


class AppMoney(Appbank):
    APPNAME = 'money'
    OLD_APPNAME = 'boomoney'
    VERSION = '3.0'
    COPYRIGHT = 'Copyright(C) 2018-YEAR Bruno Chabrier'
    DESCRIPTION = "Console application that imports bank accounts into Microsoft Money"
    SHORT_DESCRIPTION = "import bank accounts into Microsoft Money"

    EXTRA_FORMATTERS = {'list': ListFormatter, 'ops_list': MoneyOfxFormatter}
    COMMANDS_FORMATTERS = {'list': 'list', 'history': 'ops_list', 'coming': 'ops_list'}

    def __init__(self):
        super(AppMoney, self).__init__()
        self.importIndex = 0
        application_options = OptionGroup(self._parser, 'Money Options')
        application_options.add_option('-l', '--list', action='store_true', help='list the accounts and balance, without generating any import to MSMoney')
        application_options.add_option('-F', '--force', action='store_true', help='forces the retrieval of transactions (10 maximum), otherwise retrieves only the transactions newer than the previous retrieval date')
        application_options.add_option('-U', '--until-date', help='retrieves until date YYYY-MM-DD max')
        application_options.add_option('-A', '--accounts', help='retrieves only the specified accounts. By default, all accounts are retrieved')
        application_options.add_option('-N', '--no-import', action='store_true', help='no import. Generates the files, but they are not imported in MSMoney. Last import dates are not modified')
        application_options.add_option('-D', '--display', action='store_true', help='displays the generated OFX file')
        self._parser.add_option_group(application_options)
        self.labels = dict()
        self.commands_formatters["select"] = "simple"
        self._backupDone = False

    def str2bool(self, str):
        if str is True:
            return True
        if str is False:
            return False
        if str.upper() == "True".upper():
            return True
        if str.upper() == "False".upper():
            return False
        self.logger.error("Cannot convert '%s' to boolean." % str)
        raise ValueError

    def print(self, *args, **kwargs):
        with printMutex:
            print(*args, **kwargs)

    def write(self, *args):
        with printMutex:
            sys.stdout.write(*args)

    def get_downloads_path(self):
        if not hasattr(self, '_downloadsPath'):
            s = subprocess.check_output('reg query "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\User Shell Folders" /v "{374DE290-123F-4565-9164-39C4925E467B}"', encoding='CP850')
            t = re.sub(r'^(.|\r|\n)+REG_EXPAND_SZ\s+([^\n\r]+)(.|\r|\n)*$', r'\2', s)
            self._downloadsPath = os.path.expandvars(t)
        return self._downloadsPath

    def get_money_path(self):
        if not hasattr(self, '_moneyPath'):
            s = subprocess.check_output('reg query HKEY_CLASSES_ROOT\\money\\Shell\\Open\\Command /ve', encoding='CP850')
            t = re.sub(r'^(.|\r|\n)+REG_SZ\s+([^\n\r]+)(.|\r|\n)*$', r'\2', s)
            self._moneyPath = os.path.expandvars(os.path.dirname(t))
        return self._moneyPath

    def get_money_file(self):
        if not hasattr(self, '_moneyFile'):
            s = subprocess.check_output('reg query HKEY_CURRENT_USER\\Software\\Microsoft\\Money\\14.0 /v CurrentFile', encoding='CP850')
            t = re.sub(r'^(.|\r|\n)+REG_SZ\s+([^\n\r]+)(.|\r|\n)*$', r'\2', s)
            self._moneyFile = os.path.expandvars(t)
        return self._moneyFile

    def backup_if_needed(self):
        if not self._backupDone:
            with backupMutex:
                # redo the test in mutual exclusion
                if not (hasattr(self, '_backupDone') and self._backupDone):
                    file = self.get_money_file()
                    filename = os.path.splitext(os.path.basename(file))[0]
                    dir = os.path.dirname(file)
                    self.logger.info(Fore.YELLOW + Style.BRIGHT + "Creating backup of %s..." % file + Style.RESET_ALL)
                    target = os.path.join(dir, filename + datetime.datetime.now().strftime("_%Y_%m_%d_%H%M%S.mny"))
                    shutil.copy2(file, target)
                    self._backupDone = True

    def save_config(self):
        for t in self.threads:
            for a in t.accounts:
                self.config.set(a, 'label', self.config.get(a, 'label', default=''))
                self.config.set(a, 'disabled', self.str2bool(self.config.get(a, 'disabled', default=False)))
                self.config.set(a, 'date_min', self.config.get(a, 'date_min', default=''))
                self.config.set(a, 'last_date', t.last_dates[a])

        self.config.save()

    def get_list(self):
        self.onecmd("select id label number balance")
        self.options.outfile = StringIO()
        self.onecmd("list")
        listContent = self.options.outfile.getvalue()
        self.options.outfile.close()
        self.options.outfile = None

        # find max columns width
        id_maxlength = 0
        label_maxlength = 0
        number_maxlength = 0
        balance_maxlength = 0
        self.ids = []
        labels = []
        balances = []
        self.numbers = []
        for line in listContent.split(os.linesep):
            if not line == "":
                idspec, labelspec, numberspec, balancespec = line.split("\t")
                notusedid, id = idspec.split("=")
                self.ids.append(id)
                id_maxlength = max(id_maxlength, len(id))
                notusedlabel, label = labelspec.split("=")
                bmnlabel = self.config.get(id, 'label', default='')
                if bmnlabel != '' and bmnlabel != label:
                    label = bmnlabel + ' (' + label + ')'
                labels.append(label)
                label_maxlength = max(label_maxlength, len(label))
                notusednumber, number = numberspec.split("=")
                self.numbers.append(number)
                number_maxlength = max(number_maxlength, len(number))
                notusedbalance, balance = balancespec.split("=")
                balances.append(balance)
                balance_maxlength = max(balance_maxlength, len(balance))

                # use the label if not already set
                if self.config.get(id, 'label', default='') == '':
                    self.config.set(id, 'label', label)

        # print columns
        self.print(Style.BRIGHT + "%d accounts:" % len(self.ids))
        sepline = "-".ljust(id_maxlength, "-") + "-" + "-".ljust(number_maxlength, "-") + "-" + "-".ljust(balance_maxlength, "-") + "-" + "-".ljust(label_maxlength, "-") + "-" + "--------"
        self.print(sepline)
        for i in range(len(self.ids)):
            disabled = self.str2bool(self.config.get(self.ids[i], "disabled", default=False))
            self.print(
                self.ids[i].ljust(id_maxlength),
                self.numbers[i].ljust(number_maxlength),
                balances[i].ljust(balance_maxlength),
                labels[i].ljust(label_maxlength),
                "Disabled" if disabled else "")
        self.print(sepline + Style.RESET_ALL)
        self.print()

    def get_history_from_thread(self, account, thread):
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        last_date = self.config.get(account, 'last_date', default='')
        label = self.config.get(account, 'label', default='')

        ofxcontent, stderrcontent = thread.retrieve_history(account)

        if ofxcontent == '':
            self.write(stderrcontent)
            self.importIndex += 1
            self.print(Style.BRIGHT + Fore.RED + "(%i/%i) %s (%s): Got error!" % (
                self.importIndex, self.nb_accounts, account, label) + Style.RESET_ALL)
            return last_date
        else:
            self.handle_ofx_content(account, ofxcontent, stderrcontent)
            return now

    def retrieve_history(self, account):

        date_min = self.config.get(account, 'date_min', default='')
        last_date = self.config.get(account, 'last_date', default='')
        label = self.config.get(account, 'label', default='')

        if self.options.force:
            from_date = date_min
        else:
            if last_date != '':
                from_date = datetime.date.fromisoformat(last_date).isoformat()
            else:
                from_date = ''

        if self.options.count:
            from_date = ''
        if self.options.until_date:
            from_date = self.options.until_date

        self.stderr = StringIO()
        self.stdout = self.stderr
        id, backend = account.split("@")
        module_name, foo = self.woob.backends_config.get_backend(backend)
        moduleHandler = "%s.bat" % os.path.join(os.path.dirname(self.get_money_file()), module_name)
        self.logger.info("Starting history of %s (%s)..." % (account, label))

        MAX_RETRIES = 3
        count = 0
        found = False
        content = ''
        self.error = False
        while count <= MAX_RETRIES and not (found and not self.error):
            self.options.outfile = StringIO()
            self.error = False

            # executing history command
            self.logger.info("select " + " ".join(MoneyOfxFormatter.MANDATORY_FIELDS))
            self.onecmd("select " + " ".join(MoneyOfxFormatter.MANDATORY_FIELDS))
            self.logger.info("history " + account + " " + from_date)
            self.onecmd("history " + account + " " + from_date)
            expected_outputs = 1

            # For CARD accounts, let's also get coming transactions
            # We check number and string until MR!300 is merged. Can take a loooong time...
            regexp = re.compile('\r\n<ACCTTYPE>(' + str(AccountType.CARD) + '|' + list(AccountType._keys)[int(AccountType.CARD)] + ')\r\n')
            if regexp.search(self.options.outfile.getvalue()):
                self.logger.info("coming " + account + " " + from_date)
                self.onecmd("coming " + account + " " + from_date)
                expected_outputs += 1

            historyContent = self.options.outfile.getvalue()
            self.options.outfile.close()
            self.options.outfile = None

            if count > 0:
                self.logger.info("Retrying %s (%s)... %i/%i" % (account, label, count, MAX_RETRIES))
            found = re.findall(r'OFXHEADER:100', historyContent)
            nb_output = len(found)
            if found and nb_output == expected_outputs and not self.error:
                content = historyContent
            count = count + 1

        if content == '':
            # error occurred
            with numMutex:
                self.importIndex = self.importIndex + 1
            self.logger.error("%s (%s): %saborting after %i retries.%s" % (
                account,
                label,
                Fore.RED + Style.BRIGHT,
                MAX_RETRIES,
                Style.RESET_ALL))
            return '', self.stderr.getvalue()

        # postprocessing of the ofx content to match MSMoney expectations
        content = re.sub(r'<BALAMT>Not loaded', r'<BALAMT></BALAMT>', content)
        input = StringIO(content)
        output = StringIO()
        field = {}
        fields = ' '
        transaction = ''
        output_id = 1  # used because we have 2 commands, history and coming
        for line in input:
            if output_id != nb_output:
                # skip trailer of first commands
                if line.startswith('</BANKTRANLIST>'):
                    continue
                if line.startswith('<LEDGERBAL><BALAMT>'):
                    continue
                if line.startswith('<DTASOF>'):
                    continue
                if line.startswith('</LEDGERBAL>'):
                    continue
                if line.startswith('<AVAILBAL><BALAMT>'):
                    continue
                if line.startswith('<DTASOF>20200526</AVAILBAL>'):
                    continue
                if line.startswith('</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>'):
                    output_id += 1
                    continue
            if output_id != 1:
                # skip header of last commands
                if line.startswith('OFXHEADER:100'):
                    continue
                if line.startswith('DATA:OFXSGML'):
                    continue
                if line.startswith('VERSION:'):
                    continue
                if line.startswith('SECURITY:NONE'):
                    continue
                if line.startswith('ENCODING:'):
                    continue
                if line.startswith('CHARSET:'):
                    continue
                if line.startswith('COMPRESSION:'):
                    continue
                if line.startswith('OLDFILEUID:'):
                    continue
                if line.startswith('NEWFILEUID:'):
                    continue
                if line.startswith('\r'):
                    continue
                if line.startswith('<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS>'):
                    continue
                if line.startswith('<DTSERVER>'):
                    continue
                if line.startswith('<BANKMSGSRSV1><STMTTRNRS><TRNUID>'):
                    continue
                if line.startswith('<STATUS><CODE>0<SEVERITY>INFO</STATUS><CLTCOOKIE>null<STMTRS>'):
                    continue
                if line.startswith('<CURDEF>'):
                    continue
                if line.startswith('<BANKID>'):
                    continue
                if line.startswith('<BRANCHID>'):
                    continue
                if line.startswith('<ACCTID>'):
                    continue
                if line.startswith('<ACCTTYPE>'):
                    continue
                if line.startswith('<ACCTKEY>'):
                    continue
                if line.startswith('</BANKACCTFROM>'):
                    continue
                if line.startswith('<BANKTRANLIST>'):
                    continue
                if line.startswith('<DTSTART>'):
                    continue
                if line.startswith('<DTEND>'):
                    continue

            if re.match(r'^OFXHEADER:100', line):
                inTransaction = False
            if re.match(r'^<STMTTRN>', line):
                inTransaction = True
            # MSMoney only supports CHECKING accounts
            if re.match(r'^<ACCTTYPE>', line):
                line = '<ACCTTYPE>CHECKING\r\n'

            if not inTransaction:
                output.write(line)
            else:
                transaction = transaction + line
            if re.match(r'^</STMTTRN>', line):
                # debug: display transaction:
                # print(transaction, file=sys.stderr)
                # if output_id == 2: print(transaction, file=sys.stderr)

                # MSMoney expects CHECKNUM instead of NAME for CHECK transactions
                if "TRNTYPE" in field and field["TRNTYPE"] == "CHECK":
                    if "NAME" in field and unicode(field["NAME"]).isnumeric():
                        field["CHECKNUM"] = field["NAME"]
                        del field["NAME"]
                        fields = fields.replace(' NAME ', ' CHECKNUM ')

                # go through specific backend process if any
                IGNORE = False
                NEW = None
                origfields = fields
                origfield = field.copy()
                if os.path.exists(moduleHandler):
                    # apply the transformations, in the form
                    # field_NAME=...
                    # field_MEMO=...
                    # field=...

                    cmd = 'cmd /C '
                    for f in field:
                        value = field[f]
                        cmd = cmd + 'set field_%s=%s& ' % (f, value)
                    cmd = cmd + '"' + moduleHandler + '"'

                    self.logger.info(cmd)
                    result = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    (stdout, stderr) = result.communicate()
                    if result.returncode != 0:
                        print(stderr.decode('CP850'), file=sys.stderr)
                        raise subprocess.CalledProcessError(result.returncode, cmd)
                    if stderr != b'' or self.options.verbose is True:
                        if stderr != b'':
                            self.logger.warning(cmd)
                        for f in field:
                            self.print('field_%s=%s' % (f, field[f]))
                        self.print('Output:')
                        self.print(stdout.decode('CP850'), end='')
                        self.print(stderr.decode('CP850'), end='')

                    result = stdout.decode('CP850')

                    for line in re.split(r'[\r\n]+', result):
                        if not line == "":
                            f, value = line.split("=", 1)

                            if f == "IGNORE":
                                IGNORE = True
                            elif f == "NEW":
                                NEW = value
                            elif f.startswith('field_'):
                                f = re.sub(r'^field_', '', f)
                                if value == "":
                                    if f in field:
                                        del field[f]
                                    fields = re.sub(" " + f + " ", " ", fields)
                                else:
                                    field[f] = value
                                    if f not in fields.strip().split(" "):
                                        # MSMoney does not like when CHECKNUM is after MEMO
                                        if f == "CHECKNUM":
                                            fields = fields.replace("MEMO", "CHECKNUM MEMO")
                                        else:
                                            fields = fields + f + " "

                if "DTUSER" in field and "DTPOSTED" in field and not field["DTUSER"] == field["DTPOSTED"]:
                    # the payment date is a deferred payment
                    # MSMoney takes DTPOSTED, which is the payment date
                    # I prefer to have the date of the operation, so I set DTPOSTED
                    # as DTUSER
                    field["DTPOSTED"] = field["DTUSER"]

                if not IGNORE and (from_date == '' or field["DTPOSTED"] >= from_date[0:4] + from_date[5:7] + from_date[8:10]):
                    # dump transaction if not ignored and date matches
                    # (still needed because 'coming "date"' still returns older transactions - bug?
                    #  and anyway, because for CARDs all transactions are listed by 'history "date"' as registered at the payment date)
                    # Also, we keep the transactions listed by 'coming' (output_id == 2)
                    self.dump_transaction(output, fields, field)

                    if NEW is not None:
                        for n in NEW.strip().split(" "):
                            fields = origfields
                            field = origfield.copy()
                            field["FITID"] = origfield["FITID"] + "_" + n
                            for line in re.split(r'[\r\n]+', result):
                                if not line == "":
                                    f, value = line.split("=", 1)

                                    if f.startswith(n + '_field_'):
                                        f = re.sub(r'^.*_field_', '', f)
                                        field[f] = value
                                        if f not in fields.strip().split(" "):
                                            fields = fields + f + " "
                            # dump secondary transaction
                            self.dump_transaction(output, fields, field)

                inTransaction = False
            if inTransaction:
                if re.match(r'^<STMTTRN>', line):
                    field = {}
                    fields = ' '
                    transaction = ''
                else:
                    t = line.split(">", 1)
                    v = re.split(r'[\r\n]', t[1])
                    field[t[0][1:]] = v[0]
                    fields = fields + t[0][1:] + ' '

        ofxcontent = output.getvalue()
        stderrcontent = self.stderr.getvalue()
        input.close()
        output.close()
        self.stderr.close()

        return ofxcontent, stderrcontent

    def dump_transaction(self, output, fields, field):
        output.write("<STMTTRN>\n")
        for f in fields.strip().split(" "):
            value = field[f]
            if f == "NAME":
                if value == "":
                    # MSMoney does not support empty NAME field
                    value = "</NAME>"
                else:
                    # MSMoney does not support NAME field longer than 64
                    value = value[:64]
            output.write("<%s>%s\n" % (f, value))
        output.write("</STMTTRN>\n")

    def handle_ofx_content(self, account, ofxcontent, stderrcontent):

        label = self.config.get(account, 'label', default='')

        if self.options.display:
            self.print(Style.BRIGHT + ofxcontent + Style.RESET_ALL)

        nbTransactions = ofxcontent.count('<STMTTRN>')

        # create ofx file
        fname = re.sub(r'[^\w@\. ]', '_', account + " " + label)
        ofxfile = os.path.join(self.get_downloads_path(), fname + datetime.datetime.now().strftime("_%Y_%m_%d_%H%M%S") + ".ofx")
        with open(ofxfile, "w") as ofx_file:
            ofx_file.write(re.sub(r'\r\n', r'\n', ofxcontent))

        with numMutex:
            self.importIndex = self.importIndex + 1
            index = self.importIndex

        self.write(stderrcontent)

        if not (self.options.no_import or nbTransactions == 0):
            self.backup_if_needed()
        with printMutex:
            if self.options.no_import or nbTransactions == 0:
                if nbTransactions == 0:
                    print(Style.BRIGHT + '(%i/%i) %s (%s) (no transaction).' % (
                        index, self.nb_accounts,
                        account,
                        label
                    ) + Style.RESET_ALL)
                else:
                    print(Fore.GREEN + Style.BRIGHT + '(%i/%i) %s (%s) (%i transaction(s)).' % (
                        index, self.nb_accounts,
                        account,
                        label,
                        nbTransactions
                    ) + Style.RESET_ALL)
            else:
                # import into money
                print(Fore.GREEN + Style.BRIGHT + '(%i/%i) Importing "%s" into MSMoney (%i transaction(s))...' % (
                    index, self.nb_accounts,
                    ofxfile,
                    nbTransactions
                ) + Style.RESET_ALL)
        if not self.options.no_import:
            if nbTransactions > 0:
                subprocess.check_call('"%s" %s' % (
                    os.path.join(self.get_money_path(), "mnyimprt.exe"),
                    ofxfile))

    def main(self, argv):

        init()

        self.load_config()

        self._interactive = False

        if self.options.list:
            self.get_list()
            return

        self.threads = set()

        accounts = []
        if not self.options.accounts:
            self.get_list()
            accounts = self.ids
        else:
            accounts = self.options.accounts.split(",")

        # take only enabled accounts
        accounts = list(filter(
            lambda account: self.str2bool(self.config.get(account, "disabled", default=False)) is False,
            accounts))
        self.nb_accounts = len(accounts)

        # accounts.sort(key = lambda x: x.split("@")[1])

        # make a unique list
        backends = list(set(map(lambda x: x.split("@")[1], accounts)))

        # order backends by number of accounts
        backends.sort(key=lambda b: len(list(filter(
                lambda x: x.split("@")[1] == b,
                accounts))), reverse=True)

        self.main_thread = None
        for backend in backends:
            backend_accounts = list(filter(
                lambda x: x.split("@")[1] == backend,
                accounts))

            if backend == backends[0]:
                self.main_thread = HistoryThread(self, backend_accounts)
                self.threads.add(self.main_thread)
            else:
                self.threads.add(HistoryThreadAsAProcess(self, backend_accounts))

        if self.main_thread is not None:
            for t in self.threads:
                if t != self.main_thread:
                    t.start()
            self.main_thread.run()

            for t in self.threads:
                if t != self.main_thread:
                    t.join()

        self.save_config()
        return
