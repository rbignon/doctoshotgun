# -*- coding: utf-8 -*-

# Copyright(C) 2010-2016 Romain Bignon
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


from datetime import date, datetime
import re
from unidecode import unidecode

from woob.capabilities.base import (
    BaseObject, Field, StringField, DecimalField,
    UserError, Currency, EnumField, Enum,
    Capability, empty, find_object,
)
from woob.capabilities.date import DateField
from woob.exceptions import BrowserQuestion
from woob.tools.capabilities.bank.iban import is_iban_valid

from .base import ObjectNotFound, BaseAccount, CapBank, Account


__all__ = [
    'AddRecipientBankError', 'AddRecipientError', 'AddRecipientStep', 'AddRecipientTimeout',
    'BeneficiaryType',
    'CapBankTransfer', 'CapBankTransferAddRecipient',
    'CapTransfer', 'Emitter', 'EmitterNumberType', 'Recipient',
    'RecipientInvalidIban', 'RecipientInvalidLabel', 'RecipientInvalidOTP', 'RecipientNotFound',
    'Transfer',
    'TransferBankError', 'TransferCancelledByUser', 'TransferDateType', 'TransferError', 'TransferFrequency',
    'TransferInsufficientFunds', 'TransferInvalidAmount', 'TransferInvalidCurrency',
    'TransferInvalidDate', 'TransferInvalidEmitter', 'TransferInvalidLabel', 'TransferTimeout', 'TransferInvalidOTP',
    'TransferInvalidRecipient', 'TransferNotFound', 'TransferStatus', 'TransferStep',
]


class RecipientNotFound(ObjectNotFound):
    """
    Raised when a recipient is not found.
    """

    def __init__(self, msg='Recipient not found'):
        super(RecipientNotFound, self).__init__(msg)


class TransferNotFound(ObjectNotFound):
    def __init__(self, msg='Transfer not found'):
        super(TransferNotFound, self).__init__(msg)


class TransferError(UserError):
    """
    A transfer has failed.
    """

    code = 'transferError'

    def __init__(self, description=None, message=None):
        """
        :param message: error message from the bank, if any
        """

        super(TransferError, self).__init__(message or description)
        self.message = message
        self.description = description


class TransferBankError(TransferError):
    """The transfer was rejected by the bank with a message."""

    code = 'bankMessage'


class TransferTimeout(TransferError):
    """The transfer request timed out"""

    code = 'timeout'


class TransferInvalidLabel(TransferError):
    """The transfer label is invalid."""

    code = 'invalidLabel'


class TransferInvalidEmitter(TransferError):
    """The emitter account cannot be used for transfers."""

    code = 'invalidEmitter'


class TransferInvalidRecipient(TransferError):
    """The emitter cannot transfer to this recipient."""

    code = 'invalidRecipient'


class TransferInvalidAmount(TransferError):
    """This amount is not allowed."""

    code = 'invalidAmount'


class TransferInvalidCurrency(TransferInvalidAmount):
    """The transfer currency is invalid."""

    code = 'invalidCurrency'


class TransferInsufficientFunds(TransferInvalidAmount):
    """Not enough funds on emitter account."""

    code = 'insufficientFunds'


class TransferInvalidDate(TransferError):
    """This execution date cannot be used."""

    code = 'invalidDate'


class TransferInvalidOTP(TransferError):
    code = 'invalidOTP'


class TransferCancelledByUser(TransferError):
    """The transfer is cancelled by the emitter or an authorized user"""

    code = 'cancelledByUser'


class AddRecipientError(UserError):
    """
    Failed trying to add a recipient.
    """

    code = 'AddRecipientError'

    def __init__(self, description=None, message=None):
        """
        :param message: error message from the bank, if any
        """

        super(AddRecipientError, self).__init__(message or description)
        self.message = message
        self.description = description


class AddRecipientBankError(AddRecipientError):
    """The new recipient was rejected by the bank with a message."""

    code = 'bankMessage'


class AddRecipientTimeout(AddRecipientError):
    """Add new recipient request has timeout"""

    code = 'timeout'


class RecipientInvalidIban(AddRecipientError):
    code = 'invalidIban'


class RecipientInvalidLabel(AddRecipientError):
    code = 'invalidLabel'


class RecipientInvalidOTP(AddRecipientError):
    code = 'invalidOTP'


class Recipient(BaseAccount):
    """
    Recipient of a transfer.
    """
    enabled_at =     DateField('Date of availability')
    category =       StringField('Recipient category')
    iban =           StringField('International Bank Account Number')

    # Needed for multispaces case
    origin_account_id = StringField('Account id which recipient belong to')
    origin_account_iban = StringField('Account iban which recipient belong to')

    def __repr__(self):
        return "<%s id=%r label=%r>" % (type(self).__name__, self.id, self.label)


class TransferStep(BrowserQuestion):
    def __init__(self, transfer, *values):
        super(TransferStep, self).__init__(*values)
        self.transfer = transfer


class AddRecipientStep(BrowserQuestion):
    def __init__(self, recipient, *values):
        super(AddRecipientStep, self).__init__(*values)
        self.recipient = recipient


class BeneficiaryType(object):
    RECIPIENT =          'recipient'
    IBAN =               'iban'
    PHONE_NUMBER =       'phone_number'


class TransferStatus(Enum):
    UNKNOWN = 'unknown'

    INTERMEDIATE = 'intermediate'
    """Transfer is not validated yet"""

    SCHEDULED = 'scheduled'
    """Transfer to be executed later"""

    DONE = 'done'
    """Transfer was executed"""

    CANCELLED = 'cancelled'
    """Transfer was cancelled by the bank or by the user"""


class TransferFrequency(Enum):
    UNKNOWN = 'unknown'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    BIMONTHLY = 'bimonthly'
    QUARTERLY = 'quarterly'
    BIANNUAL = 'biannual'
    YEARLY = 'yearly'


class TransferDateType(Enum):
    FIRST_OPEN_DAY = 'first_open_day'
    """Transfer to execute when possible (accounting opening days)"""

    INSTANT = 'instant'
    """Transfer to execute immediately (not accounting opening days)"""

    DEFERRED = 'deferred'
    """Transfer to execute on a chosen date"""

    PERIODIC = 'periodic'
    """Transfer to execute periodically"""


class Transfer(BaseObject, Currency):
    """
    Transfer from an account to a recipient.
    """
    amount =          DecimalField('Amount to transfer')
    currency =        StringField('Currency', default=None)
    fees =            DecimalField('Fees', default=None)

    exec_date =       Field('Date of transfer', date, datetime)
    label =           StringField('Reason')

    account_id =      StringField('ID of origin account')
    account_iban =    StringField('International Bank Account Number')
    account_label =   StringField('Label of origin account')
    account_balance = DecimalField('Balance of origin account before transfer')

    # Information for beneficiary in recipient list
    recipient_id =      StringField('ID of recipient account')
    recipient_iban =    StringField('International Bank Account Number')
    recipient_label =   StringField('Label of recipient account')

    # Information for beneficiary not only in recipient list
    # Like transfer to iban beneficiary
    beneficiary_type =    StringField('Transfer creditor number type', default=BeneficiaryType.RECIPIENT)
    beneficiary_number =  StringField('Transfer creditor number')
    beneficiary_label =  StringField('Transfer creditor label')
    beneficiary_bic = StringField('Transfer creditor BIC')

    date_type = EnumField('Transfer execution date type', TransferDateType)

    frequency = EnumField('Frequency of periodic transfer', TransferFrequency)
    first_due_date = DateField('Date of first transfer of periodic transfer')
    last_due_date = DateField('Date of last transfer of periodic transfer')

    creation_date = DateField('Creation date of transfer')
    status = EnumField('Transfer status', TransferStatus)

    cancelled_exception = Field('Transfer cancelled reason', TransferError)


class EmitterNumberType(Enum):
    UNKNOWN = 'unknown'
    IBAN = 'iban'
    BBAN = 'bban'


class Emitter(BaseAccount):
    """
    Transfer emitter account.
    """
    number_type = EnumField('Account number type', EmitterNumberType, default=EmitterNumberType.UNKNOWN)
    number = StringField('Account number value')
    balance = DecimalField('Balance of emitter account')


class CapTransfer(Capability):
    can_do_transfer_to_untrusted_beneficiary = False
    """
    The module can do transfer to untrusted beneficiary, for example:
    when module can't add new beneficiary without doing a transfer like n26
    or when module can do transfer to a beneficiary not listed
    in `iter_transfer_recipients` like for PSD2 modules
    """

    can_do_transfer_without_emitter = False
    """
    The module can do transfer without giving the emitter, for example:
    when there is only, and will be only, one account like wallet
    or when the module can initiate transfer without emitter
    and the emitter is chosen afterwards like for PSD2 modules
    """

    accepted_beneficiary_types = (BeneficiaryType.RECIPIENT, )
    accepted_execution_date_types = (TransferDateType.FIRST_OPEN_DAY, TransferDateType.DEFERRED)

    def iter_transfer_recipients(self, account):
        """
        Iter recipients availables for a transfer from a specific account.

        :param account: account which initiate the transfer
        :type account: :class:`Account`
        :rtype: iter[:class:`Recipient`]
        :raises: :class:`AccountNotFound`
        """
        raise NotImplementedError()

    def init_transfer(self, transfer, **params):
        """
        Initiate a transfer.

        :param :class:`Transfer`
        :rtype: :class:`Transfer`
        :raises: :class:`TransferError`
        """
        raise NotImplementedError()

    def execute_transfer(self, transfer, **params):
        """
        Execute a transfer.

        :param :class:`Transfer`
        :rtype: :class:`Transfer`
        :raises: :class:`TransferError`
        """
        raise NotImplementedError()

    def confirm_transfer(self, transfer, **params):
        """
        Transfer confirmation after multiple SCA from the Emitter.
        This method is only used for PSD2 purpose.
        Return the transfer with the new status.

        :param :class:`Transfer`
        :rtype: :class:`Transfer`
        :raises: :class:`TransferError`
        """
        return self.get_transfer(transfer.id)

    def transfer(self, transfer, **params):
        """
        Do a transfer from an account to a recipient.

        :param :class:`Transfer`
        :rtype: :class:`Transfer`
        :raises: :class:`TransferError`
        """

        transfer_not_check_fields = {
            BeneficiaryType.RECIPIENT: ('id', 'beneficiary_number', 'beneficiary_label',),
            BeneficiaryType.IBAN: ('id', 'recipient_id', 'recipient_iban', 'recipient_label',),
            BeneficiaryType.PHONE_NUMBER: ('id', 'recipient_id', 'recipient_iban', 'recipient_label',),
        }

        if not transfer.amount or transfer.amount <= 0:
            raise TransferInvalidAmount('amount must be strictly positive')

        t = self.init_transfer(transfer, **params)
        for key, value in t.iter_fields():
            if hasattr(transfer, key) and (key not in transfer_not_check_fields[transfer.beneficiary_type]):
                transfer_val = getattr(transfer, key)
                if hasattr(self, 'transfer_check_%s' % key):
                    assert getattr(self, 'transfer_check_%s' % key)(transfer_val, value), '%s changed during transfer processing (from "%s" to "%s")' % (key, transfer_val, value)
                else:
                    assert transfer_val == value or empty(transfer_val), '%s changed during transfer processing (from "%s" to "%s")' % (key, transfer_val, value)
        return self.execute_transfer(t, **params)

    def transfer_check_label(self, old, new):
        old = re.sub(r'\s+', ' ', old).strip()
        new = re.sub(r'\s+', ' ', new).strip()
        return unidecode(old) == unidecode(new)

    def iter_transfers(self, account=None):
        """
        Iter transfer transactions.

        :param account: account to get transfer history (or None for all accounts)
        :type account: :class:`Account`
        :rtype: iter[:class:`Transfer`]
        :raises: :class:`AccountNotFound`
        """
        raise NotImplementedError()

    def get_transfer(self, id):
        """
        Get a transfer from its id.

        :param id: ID of the Transfer
        :type id: :class:`str`
        :rtype: :class:`Transfer`
        """
        return find_object(self.iter_transfers(), id=id, error=TransferNotFound)

    def iter_emitters(self):
        """
        Iter transfer emitter accounts.

        :rtype: iter[:class:`Emitter`]
        """
        raise NotImplementedError()


class CapBankTransfer(CapBank, CapTransfer):
    def account_to_emitter(self, account):
        if isinstance(account, Account):
            account = account.id

        return find_object(self.iter_emitters, id=account, error=ObjectNotFound)


class CapBankTransferAddRecipient(CapBankTransfer):
    def new_recipient(self, recipient, **params):
        raise NotImplementedError()

    def add_recipient(self, recipient, **params):
        """
        Add a recipient to the connection.

        :param iban: iban of the new recipient.
        :type iban: :class:`str`
        :param label: label of the new recipient.
        :type label: :class`str`
        :raises: :class:`BrowserQuestion`
        :raises: :class:`AddRecipientError`
        :rtype: :class:`Recipient`
        """
        if not is_iban_valid(recipient.iban):
            raise RecipientInvalidIban('Iban is not valid.')
        if not recipient.label:
            raise RecipientInvalidLabel('Recipient label is mandatory.')
        return self.new_recipient(recipient, **params)
