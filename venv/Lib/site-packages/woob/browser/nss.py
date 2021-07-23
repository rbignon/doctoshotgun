# -*- coding: utf-8 -*-

# Copyright(C) 2016      Vincent A
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

"""Module to use NSS instead of OpenSSL in urllib3/requests."""

# create db:
#   mkdir pki
#   certutil -N -d pki

# import certificate:
#   find -L /etc/ssl/certs -name "*.pem" | while read f; do certutil -A -d pki -i $f -n $f -t TCu,Cu,Tu; done

from __future__ import absolute_import

from functools import wraps
from io import RawIOBase, BufferedRWPair
import hashlib
import os
import re
import socket
import ssl as basessl
import subprocess
from tempfile import NamedTemporaryFile
from threading import Lock

try:
    import nss.ssl
    import nss.error
    import nss.nss
except ImportError:
    raise ImportError('Please install python3-nss')
from requests.packages.urllib3.util.ssl_ import ssl_wrap_socket as old_ssl_wrap_socket
import requests  # for AIA
from woob.tools.log import getLogger


__all__ = ['init_nss', 'inject_in_urllib3', 'certificate_db_filename']


CTX = None
INIT_PID = None
INIT_ARGS = None
LOGGER = getLogger('woob.browser.nss')


def nss_version():
    version_str = nss.nss.nss_get_version()
    version_str = re.match(r'\d+\.\d+', version_str).group(0) # can be "3.21.3 Extended ECC"
    return tuple(int(x) for x in version_str.split('.'))
    # see https://developer.mozilla.org/en-US/docs/Mozilla/Projects/NSS/NSS_3.35_release_notes


def certificate_db_filename():
    version = nss_version()
    if version < (3, 35):
        return 'cert8.db'
    return 'cert9.db'


def path_for_version(path):
    # despite what certutil(1) and the NSS 3.35 releases notes say
    # some nss builds >=3.35 will use either sql or dbm by default
    # also, some builds <3.35 will fail to enforce sql format when using "sql:"
    if nss_version() < (3, 35):
        return path
    return 'sql:%s' % path


def cert_to_dict(cert):
    # see https://docs.python.org/2/library/ssl.html#ssl.SSLSocket.getpeercert
    # and https://github.com/kennethreitz/requests/blob/master/requests/packages/urllib3/contrib/pyopenssl.py

    mappings = {
        nss.nss.certDNSName: 'DNS',
        nss.nss.certIPAddress: 'IP Address',
        # TODO support more types
    }

    altnames = []
    try:
        ext = cert.get_extension(nss.nss.SEC_OID_X509_SUBJECT_ALT_NAME)
    except KeyError:
        pass
    else:
        for entry in nss.nss.x509_alt_name(ext.value, nss.nss.AsObject):
            key = mappings[entry.type_enum]
            altnames.append((key, entry.name))

    ret = {
        'subject': [
            [('commonName', cert.subject.common_name)],
            [('localityName', cert.subject.locality_name)],
            [('organizationName', cert.subject.org_name)],
            [('organizationalUnitName', cert.subject.org_unit_name)],
            [('emailAddress', cert.subject.email_address)],
        ],
        'subjectAltName': altnames,
        'issuer': [
            [('countryName', cert.issuer.country_name)],
            [('organizationName', cert.issuer.org_name)],
            [('organizationalUnitName', cert.issuer.org_unit_name)],
            [('commonName', cert.issuer.common_name)],
        ],
        # TODO serialNumber, notBefore, notAfter
        'version': cert.version,
    }

    return ret


ERROR_MAP = {
    nss.error.PR_CONNECT_TIMEOUT_ERROR: (socket.timeout,),
    nss.error.PR_IO_TIMEOUT_ERROR: (socket.timeout,),
    nss.error.PR_CONNECT_RESET_ERROR: (socket.error,),
}


def wrap_callable(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return exc_wrap(func, *args, **kwargs)
    return wrapper


def exc_wrap(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except nss.error.NSPRError as e:
        if e.error_desc.startswith('(SEC_ERROR_') or e.error_desc.startswith('(SSL_ERROR_'):
            raise basessl.SSLError(0, e.error_message or e.error_desc, e)

        for k in ERROR_MAP:
            if k == e.error_code:
                raise ERROR_MAP[k][0]

        raise


class NSSFile(RawIOBase):
    def __init__(self, obj):
        self.obj = obj
        self.open = True

    def close(self):
        super(NSSFile, self).close()
        if self.open:
            self.obj.close()
            self.open = False

    def read(self, amount):
        return self.obj.recv(amount)

    def readinto(self, buf):
        amount = len(buf)
        chunk = self.obj.recv(amount)
        # TODO handle timeout by returning None?
        buf[:len(chunk)] = chunk
        return len(chunk)

    def write(self, buf):
        self.obj.send(buf)
        return len(buf)

    def readable(self):
        return self.open

    writable = readable


class Wrapper(object):
    def __init__(self, obj):
        self.__obj = obj
        self.__timeout = nss.io.PR_INTERVAL_NO_TIMEOUT

    def settimeout(self, t):
        if t is None:
            self.__timeout = nss.io.PR_INTERVAL_NO_TIMEOUT
        else:
            self.__timeout = nss.io.milliseconds_to_interval(int(t * 1000))

    def __getattr__(self, attr):
        ret = getattr(self.__obj, attr)
        if callable(ret):
            ret = wrap_callable(ret)
        return ret

    def getpeercert(self, binary_form=False):
        # TODO return none or exception in case no cert yet?

        cert = self.__obj.get_peer_certificate()
        if binary_form:
            return cert.der_data
        else:
            return cert_to_dict(cert)

    def makefile(self, *args, **kwargs):
        made = self.__obj.makefile(*args, **kwargs)
        # NSS.io.Socket returns the same object, but increments its internal ref counter
        # close() decreases the counter, and closes if there are no more refs
        # see python NSS source
        assert made is self.__obj

        rw_wrapper = NSSFile(self)
        return BufferedRWPair(rw_wrapper, rw_wrapper)

    def recv(self, amount):
        return exc_wrap(self.__obj.recv, amount, self.__timeout)

    def send(self, s):
        return exc_wrap(self.__obj.send, s, self.__timeout)


def auth_cert_pinning(sock, check_sig, is_server, path):
    cert = sock.get_peer_certificate()

    expected = nss.nss.Certificate(nss.nss.read_der_from_file(path, True))
    return (expected.signed_data.data == cert.signed_data.data)


AIA_CACHE = {}
AIA_LOCK = Lock()


def auth_cert_basic(sock, check_sig, is_server):
    cert = sock.get_certificate()
    db = nss.nss.get_default_certdb()

    # simple case: full cert chain
    try:
        valid = cert.verify_hostname(sock.get_hostname())
    except nss.error.NSPRError:
        return False
    if not valid:
        return False

    required = nss.nss.certificateUsageSSLServer
    try:
        usages = cert.verify_now(db, check_sig, required) & required
    except nss.error.NSPRError:
        return False
    return bool(usages)


def auth_cert_aia_only(sock, check_sig, is_server):
    cert = sock.get_certificate()
    db = nss.nss.get_default_certdb()

    # harder case: the server presents an incomplete cert chain and only has the leaf cert
    # the parent is indicated in the TLS extension called "AIA"

    for ext in cert.extensions:
        if ext.name == 'Authority Information Access':
            aia_text = ext.format()
            aia_text = re.sub(r'\s+', ' ', aia_text)
            break
    else:
        return False
    # yes, the parent TLS cert is behind an HTTP URL
    parent_url = re.search(r'Method: PKIX CA issuers access method Location: URI: (http:\S+)', aia_text).group(1)

    with AIA_LOCK:
        parent_der = AIA_CACHE.get(parent_url)

    if parent_der is None:
        parent_der = requests.get(parent_url).content
        with AIA_LOCK:
            AIA_CACHE[parent_url] = parent_der

    # verify parent cert is a CA in our db
    parent = nss.nss.Certificate(parent_der, perm=False)
    required = nss.nss.certificateUsageAnyCA
    try:
        usages = parent.verify_now(db, check_sig, required) & required
    except nss.error.NSPRError:
        return False
    if not usages:
        return False

    # verify leaf certificate
    try:
        valid = cert.verify_hostname(sock.get_hostname())
    except nss.error.NSPRError:
        return False
    if not valid:
        return False

    required = nss.nss.certificateUsageSSLServer
    try:
        usages = cert.verify_now(db, check_sig, required) & required
    except nss.error.NSPRError:
        return False
    return bool(usages)


def auth_cert_with_aia(sock, check_sig, is_server):
    assert not is_server

    cert = sock.get_certificate()

    if len(cert.get_cert_chain()) > 1:
        return auth_cert_basic(sock, check_sig, is_server)
    else:
        return auth_cert_aia_only(sock, check_sig, is_server)


DEFAULT_CA_CERTIFICATES = (
    '/etc/ssl/certs/ca-certificates.crt',
    '/etc/pki/tls/certs/ca-bundle.crt',
)

try:
    import certifi
except ImportError:
    pass
else:
    DEFAULT_CA_CERTIFICATES = DEFAULT_CA_CERTIFICATES + (certifi.where(),)


def ssl_wrap_socket(sock, *args, **kwargs):
    if kwargs.get('certfile'):
        LOGGER.debug('a client certificate is used, falling back to OpenSSL')
        # TODO implement NSS client certificate support
        return old_ssl_wrap_socket(sock, *args, **kwargs)

    reinit_if_needed()

    # TODO handle more options?
    hostname = kwargs.get('server_hostname')
    ossl_ctx = kwargs.get('ssl_context')

    # the python Socket and the NSS SSLSocket are agnostic of each other's state
    # so the Socket could close the fd, then a file could be opened,
    # obtaining the same file descriptor, then NSS would use the file, thinking
    # it's a network file descriptor... dup the fd to make it independant
    fileno = sock.fileno()
    if hasattr(sock, 'detach'):
        # socket.detach only exists in py3.
        sock.detach()
    else:
        fileno = os.dup(fileno)

    nsssock = nss.ssl.SSLSocket.import_tcp_socket(fileno)
    wrapper = Wrapper(nsssock)

    nsssock.set_certificate_db(nss.nss.get_default_certdb())
    if hostname:
        nsssock.set_hostname(hostname)
    if ossl_ctx and not ossl_ctx.verify_mode:
        nsssock.set_auth_certificate_callback(lambda *args: True)
    elif kwargs.get('ca_certs') and kwargs['ca_certs'] not in DEFAULT_CA_CERTIFICATES:
        nsssock.set_auth_certificate_callback(auth_cert_pinning, kwargs['ca_certs'])
    else:
        nsssock.set_auth_certificate_callback(auth_cert_with_aia)

    nsssock.reset_handshake(False) # marks handshake as not-done
    try:
        wrapper.send(b'') # performs handshake
    except nss.error.NSPRError as e:
        if e.error_code == nss.error.PR_END_OF_FILE_ERROR:
            # the corresponding openssl error isn't exactly socket.timeout()
            # but rather something SyscallError.
            # i don't know how to generate it exactly and the end result is
            # similar so let's use this.
            raise socket.timeout()

        # see below why closing
        wrapper.close()
        raise
    except:
        # If there is an exception during the handshake, correctly close the
        # duplicated/detached socket as it isn't known by the caller.
        wrapper.close()
        raise

    return wrapper


def inject_in_urllib3():
    import urllib3.util.ssl_
    import urllib3.connection
    # on some distros, requests comes with its own urllib3 version
    import requests.packages.urllib3.util.ssl_
    import requests.packages.urllib3.connection

    for pkg in (urllib3, requests.packages.urllib3):
        pkg.util.ssl_.ssl_wrap_socket = ssl_wrap_socket
        pkg.util.ssl_wrap_socket = ssl_wrap_socket
        pkg.connection.ssl_wrap_socket = ssl_wrap_socket


def init_nss(path, rw=False):
    global CTX, INIT_PID, INIT_ARGS

    if CTX is not None and INIT_PID == os.getpid():
        return

    INIT_ARGS = (path, rw)

    if rw:
        flags = 0
    else:
        flags = nss.nss.NSS_INIT_READONLY

    path = path_for_version(path)
    INIT_PID = os.getpid()
    CTX = nss.nss.nss_init_context(path, flags=flags)


def add_nss_cert(dbpath, certpath, nickname):
    # Even if you use a different nickname, NSS will not add a cert that is
    # already in db, without signaling it.
    subprocess.check_call(['certutil', '-A', '-d', dbpath, '-i', certpath, '-n', nickname, '-t', 'TC,C,T'])


def del_nss_cert(dbpath, nickname):
    subprocess.check_call(['certutil', '-D', '-d', dbpath, '-n', nickname])


def create_cert_db(path):
    # continue to provide this function for braindead customers who believe a development version
    # is an api-stable version
    update_cert_db(path)


def iter_db_certs(path):
    # TODO check existing db
    output = subprocess.check_output(['certutil', '-L', '-d', path]).decode('utf-8').rstrip()
    for line in output.split('\n'):
        if line.startswith(' ') or ',' not in line:
            # NSS prints a useless header.
            # The lines we want have format:
            #   {cert nickname}{space based alignment}{nss trust flags}
            # NSS trust flags contain "," so we're guaranteed these are the desired lines
            continue

        yield line.split()[0]


def create_empty_db(path):
    path = path_for_version(path)

    try:
        subprocess.check_call(['certutil', '-N', '--empty-password', '-d', path])
    except OSError:
        raise ImportError('Please install libnss3-tools')


def update_cert_db(dbpath):
    """Imports certificates from system dir into NSS database."""

    # Tries to keep unchanged certificates.
    # Each certificate has a "nickname" in NSS db, which is defined by us, not
    # by cert content.
    # Previously, we used the certificate file path as nickname.
    # To be able to track those which changed and those removed, we use the
    # hash of the PEM data as nickname. This is useful for ensuring unicity as
    # system certificate dirs contain duplicate certificates.

    realdbpath = dbpath
    dbpath = path_for_version(dbpath)

    if not os.path.exists(os.path.join(realdbpath, certificate_db_filename())):
        create_empty_db(realdbpath)

    db_certs = set(iter_db_certs(dbpath))
    obsolete_certs = set(db_certs)

    # Do a first pass by removing certs that use file nicknames.
    # NSS won't add duplicate certs, so existing file nicknames will prevent
    # hash nicknames from being inserted into the db.
    # Then, the purging loop at function end will remove file nicknames, which
    # will make the db effectively empty, because we couldn't insert any hash
    # nicknames...
    # If we clean them before, we aren't blocked from adding hash nicknames.
    for nick in db_certs:
        if '/' in nick:
            del_nss_cert(dbpath, nick)
            obsolete_certs.discard(nick)

    cert_dir = '/etc/ssl/certs'
    for cert_file in os.listdir(cert_dir):
        cert_file = os.path.join(cert_dir, cert_file)
        if os.path.isdir(cert_file) or '.' not in cert_file:
            continue

        with open(cert_file) as fd:
            content = fd.read()

        separators = [
            '-----END CERTIFICATE-----',
            '-----END TRUSTED CERTIFICATE-----',
        ]
        for sep in separators:
            if sep in content:
                separator = sep
                break
        else:
            continue

        nb_certs = content.count(separator)
        try:
            if nb_certs == 1:
                nick = hashlib.sha1(content.strip().encode('utf-8')).hexdigest()
                if nick in db_certs:  # no need to import it
                    obsolete_certs.discard(nick)  # don't remove it at the end
                    continue

                add_nss_cert(dbpath, cert_file, nick)
                db_certs.add(nick)
            elif nb_certs > 1:
                # nss can't import bundles, split them
                for subcert in content.split(separator)[:-1]:
                    subcert += separator

                    nick = hashlib.sha1(subcert.strip().encode('utf-8')).hexdigest()
                    if nick in db_certs:
                        obsolete_certs.discard(nick)
                        continue

                    with NamedTemporaryFile('w') as fd:
                        fd.write(subcert)
                        fd.flush()
                        add_nss_cert(dbpath, fd.name, nick)
                        db_certs.add(nick)

        except subprocess.CalledProcessError:
            LOGGER.warning('Unable to handle ca file {}'.format(cert_file))

    for nick in obsolete_certs:
        # Those certs were imported in a previous session, but they don't seem
        # to be on the system anymore.
        del_nss_cert(dbpath, nick)


def reinit_if_needed():
    # if we forked since NSS was initialized, we might get an exception
    # (SEC_ERROR_PKCS11_DEVICE_ERROR) A PKCS #11 module returned CKR_DEVICE_ERROR, indicating that a problem has occurred with the token or slot.
    # so we should reinit NSS

    if INIT_PID and INIT_PID != os.getpid():
        LOGGER.debug('nss inited in %s but now in %s', INIT_PID, os.getpid())
        assert INIT_ARGS
        init_nss(*INIT_ARGS)
