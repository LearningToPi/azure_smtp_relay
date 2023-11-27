"""
Module Description: This module contains the implementation of the SmtpConfig class.

The SmtpConfig class represents the configuration for the SMTP service.

Usage:
    Example usage of the SmtpConfig class:
    >>> config = SmtpConfig(address='smtp.example.com', port=587, from_address='sender@example.com', allowed_dest_domains=['example.com'], allowed_subnets=['192.168.1.0/24'])
    >>> print(config.address)

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
KEEPALIVE_INTERVAL = 1
AZURE_SEND_TIMEOUT = 30
AZURE_SEND_QUEUE_MAX_AGE = 43200 # 12 hours
AZURE_MESSAGE_RETRY = 3
AZURE_MESSAGE_RETRY_DELAY = 3600 # 1 hour
RETAIN_LOG_DAYS = 72
RELAY_QUEUE_LIMIT = 100


class SmtpConfig:
    """
    Class Description: The SmtpConfig class represents the configuration for the SMTP service.

    Attributes:
        address (str): The address of the SMTP server.
        port (int): The port number for the SMTP server.
        from_address (str): The default sender address for outgoing emails.
        allowed_dest_domains (list): A list of allowed destination domains.
        allowed_subnets (list): A list of allowed subnets.
        move_from_replyto (bool): Whether to override the 'From' address with the 'Reply-To' address.
        message_retry (int): The number of retry attempts for failed messages.
        message_retry_delay (int): The delay (in seconds) between message retry attempts.
        retain_log_days (int): The number of days to retain log entries.
        send_timeout (int): The timeout (in seconds) for sending messages.

    Methods:
        __init__: Initialize the SmtpConfig instance.

    Example:
        Example of using the SmtpConfig class:
        >>> config = SmtpConfig(address='smtp.example.com', port=587, from_address='sender@example.com', allowed_dest_domains=['example.com'], allowed_subnets=['192.168.1.0/24'])
        >>> print(config.address)

    """
    def __init__(self, address:str, port:int|str, from_address:str, allowed_dest_domains:list, allowed_subnets:list, 
                 move_from_replyto=True, message_retry:int=AZURE_MESSAGE_RETRY, message_retry_delay:int=AZURE_MESSAGE_RETRY_DELAY,
                 retain_log_days:int=RETAIN_LOG_DAYS, send_timeout:int=AZURE_SEND_TIMEOUT):
        """
        Initialize the SmtpConfig instance.

        Args:
            address (str): The address of the SMTP server.
            port (int|str): The port number for the SMTP server.
            from_address (str): The default sender address for outgoing emails.
            allowed_dest_domains (list): A list of allowed destination domains.
            allowed_subnets (list): A list of allowed subnets.
            move_from_replyto (bool): Whether to override the 'From' address with the 'Reply-To' address.
            message_retry (int): The number of retry attempts for failed messages.
            message_retry_delay (int): The delay (in seconds) between message retry attempts.
            retain_log_days (int): The number of days to retain log entries.
            send_timeout (int): The timeout (in seconds) for sending messages.

        Returns:
            None

        Notes:
            This constructor initializes the SmtpConfig instance with the provided configuration parameters.

        Example:
            Example of creating an instance of SmtpConfig:
            >>> config = SmtpConfig(address='smtp.example.com', port=587, from_address='sender@example.com', allowed_dest_domains=['example.com'], allowed_subnets=['192.168.1.0/24'])
            >>> print(config.address)

        """
        self.address = address
        self.port = int(port)
        self.from_address = from_address
        self.allowed_dest_domains = allowed_dest_domains
        self.allowed_subnets = allowed_subnets
        self.move_from_replyto = move_from_replyto
        self.message_retry = message_retry
        self.message_retry_delay = message_retry_delay
        self.retain_log_days = retain_log_days
        self.send_timeout = send_timeout
