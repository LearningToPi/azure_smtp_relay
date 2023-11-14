"""
Module Description: This module contains the implementation of the AddressLust class.

The Address list can be used to create a email address list using the Azure format of
    {'address': [email], 'displayName': [friendlyName]}
Addresses can be added individually using the add(...) which can be any of the following:
    - a string with a single email address ('Test <test@none.com>' or 'test@none.com')
    - a list of emails (['test@none.com', 'Test2 <test2@none.com>'])
    - a comma separated list of emails ('test@none.com,Test2 <test2@none.com>')

If a display name is not found, then it is left blank.

Usage:
    Example usage of the SmtpHandler class:
    >>> handler = SmtpHandler(logger=your_logger, config=your_smtp_config, queue=your_queue_manager)
    >>> await handler.handle_RCPT(server, session, envelope, address, rcpt_options)
    >>> await handler.handle_DATA(server, session, envelope)

License:
    MIT License

    Copyright (c) 2023 LearningToPi

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
"""

import re


def email_address_valid(email:str) -> bool:
    """
    Check if the email address is properly formatted.

    Parameters:
        email (str): Email address in string format.

    Returns:
        bool: True if the email address is valid, False otherwise.

    Example:
        Example of checking the validity of an email address:
        >>> is_valid = email_address_valid('user@example.com')
        >>> print(f"Is the email address valid? {is_valid}")
    """
    re_check = re.search(r"[ -~^@]+@[A-Za-z0-9\-]+.[a-zA-Z0-9\-]+", email)
    return re_check is not None

def email_domain_valid(domain:str) -> bool:
    """
    Check if the email domain is properly formatted.

    Parameters:
        domain (str): Email domain in string format.

    Returns:
        bool: True if the email domain is valid, False otherwise.

    Example:
        Example of checking the validity of an email domain:
        >>> is_valid_domain = email_domain_valid('example.com')
        >>> print(f"Is the email domain valid? {is_valid_domain}")
    """
    re_check = re.search(r"[A-Za-z0-9\-]+.[a-zA-Z0-9\-]+", domain)
    return re_check is not None


class AddressList:
    """
    Object to represent a list of email addresses.

    Attributes:
        addresses (list): List of dictionaries representing email addresses.

    Methods:
        add(*args): Add one or more addresses to the list.
        first_address(): Return the first email address.
        __str__(): Return the list as a printable string.
    """
    def __init__(self, *args):
        self.addresses = []
        self.add(*args)

    @property
    def first_address(self) -> str:
        """
        Return only the first email address, use for From or ReplyTo lists that should only contain 1 entry.

        Returns:
            str: The first email address.

        Raises:
            ValueError: If the address list is empty.

        Example:
            Example of getting the first email address:
            >>> first_email = address_list.first_address
            >>> print(f"The first email address is: {first_email}")
        """
        if len(self.addresses) == 0:
            raise ValueError('Address list is empty!')
        return self.addresses[0].get('address')

    def add(self, *args):
        """
        Add one or more addresses to the list.

        Parameters:
            *args: Variable number of arguments representing addresses.
                Each arg can be any of the following:
                    - a string with a single email address ('Test <test@none.com>' or 'test@none.com')
                    - a list of emails (['test@none.com', 'Test2 <test2@none.com>'])
                    - a comma separated list of emails ('test@none.com,Test2 <test2@none.com>')
        Raises:
            ValueError: If the argument is of an unsupported type.

        Example:
            Example of adding addresses to the list:
            >>> address_list.add('user@example.com', {'address': 'admin@example.com', 'displayName': 'Admin'})
        """
        # process positional args
        for arg in args:
            if isinstance(arg, str) and (',' in arg or ';' in arg):
                # we have a list from a header, split it and recursively call
                self.add(arg.split(';'))
            elif isinstance(arg, str) and '<' in arg and '>' in arg:
                # we have an address string formated with "Display Name <email@none.com>"
                address_re = re.search(r"(?P<displayName>[^< ]*)\s*<\s*(?P<address>[^>]*)\s*>", arg)
                if address_re:
                    if address_re.groupdict()['address'] in [str(x.get('address')).lower() for x in self.addresses]:
                        # if already present, jump to next arg
                        continue
                    # add address
                    self.addresses.append(address_re.groupdict())
            elif isinstance(arg, str) and email_address_valid(arg):
                if arg.lower() in [str(x.get('address')).lower() for x in self.addresses]:
                    # if already present, jump to next arg
                    continue
                # add address
                self.addresses.append({'address': arg})
            elif isinstance(arg, dict) and 'address' in arg and email_address_valid(str(arg.get('address'))):
                if str(arg.get('address')).lower() in [str(x.get('address')).lower() for x in self.addresses]:
                    # if already present, jump to next arg
                    continue
                # add address
                self.addresses.append({'address': arg.get('address'), 'displayName': arg.get('displayName')})
            elif isinstance(arg, list):
                # if a list was passed, recursively call and process individually
                self.add(*arg)
            else:
                raise ValueError(f"{arg} is of type {type(arg)} and is not supported.")

    def __str__(self):
        """
        Return the list as a printable string.

        Returns:
            str: String representation of the address list.

        Example:
            Example of getting the string representation of the address list:
            >>> print(address_list)
        """
        return str(self.addresses)