"""
Module Description: This module provides functionality for an Azure SMTP Relay using Azure Communication Services
    using aiosmtpd as the SMTP server.  Messages received by the SMTP server will be queued and sent serially
    to the Azure Communication Service.  For information on setup of the Azure Communication Service, see the
    Azure_Setup.md doc in the docs folder.

    This module was written to allow relaying of messages from a home lab network out through Azure.  Most ISP
    networks block outbound port 25 (due to spam), and now Azure blocks outbound port 25 unless you have a
    specific enterprise agreement.  Since a VM running in Azure can no longer relay messages, this module was
    written to fill the gap and replace the internal postfix relay that can no longer forward alerts.

    NOTE: This is NOT intended to be internet facting.  This is intended to run on an internal network to allow
    relaying of messages through Azure.

    NOTE: To prevent unintended relaying or spam, a specific list of destination email domains is REQUIRED!  In
    addition, a list of permitted networks that should be allowed to relay is REQUIRED!  Networks should be
    listed in CIDR notation ('10.0.0.0/24', '192.168.100.0/24', etc).  Subnets will be verified using "ipcalc".

    The package is also available as a docker container (...)

Args:
    address (str): The address for the SMTPD service.
    port (int|str): The port for the SMTPD service.
    from_address (str): The sender's email address.
    allowed_dest_domains (list): List of allowed destination email domains.
    allowed_subnets (list): List of allowed subnets.
    azure_auth (ClientSecretCredential|AzureKeyCredential): Azure authentication credentials.
    endpoint (str): The Azure endpoint for sending emails.
    log_level (int): The logging level for the logger.
    max_queue (int): Maximum number of messages to queue.
    enable_send_log (bool): Flag to enable message sending logs.
    send_queue_max_age (int): Maximum age (in seconds) for messages in the queue.
    queue_timeout (int): Timeout (in seconds) for the message queue.
    move_from_replyto (bool): Flag to move 'From' to 'ReplyTo' in the processed message.
    message_retry (int): Number of retry attempts for sending a message to Azure.
    message_retry_delay (int): Delay (in seconds) between message retry attempts.
    retain_log_hours (int): Number of hours to retain log entries.
    send_timeout (int): Timeout (in seconds) for sending messages to Azure.

Usage:
    Example usage of this module:
    >>> from azure_smtp_relay import AzureSmtpRelay, ClientSecretCredential, AzureKeyCredential
    >>> relay = AzureSmtpRelay(
    ...     address='smtp.example.com',
    ...     port=587,
    ...     from_address='sender@example.com',
    ...     allowed_dest_domains=['example.com'],
    ...     allowed_subnets=['192.168.1.0/24'],
    ...     azure_auth=ClientSecretCredential(
    ...         tenant_id='your_tenant_id',
    ...         client_id='your_client_id',
    ...         client_secret='your_client_secret'
    ...     ),
    ...     endpoint='https://your-communication-service-endpoint',
    ...     log_level=logging.INFO,
    ...     max_queue=100,
    ...     enable_send_log=True,
    ...     send_queue_max_age=43200,  # 12 hours
    ...     queue_timeout=60,  # 2 minutes
    ...     move_from_replyto=True,
    ...     message_retry=3,
    ...     message_retry_delay=3600,  # 1 hour
    ...     retain_log_hours=72,
    ...     send_timeout=30
    ... )
    >>> relay.start()

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

from azure.identity import ClientSecretCredential
from azure.core.credentials import AzureKeyCredential
from .relay import AzureSmtpRelay

VERSION = (1, 0, 1)    # updated 2023-11-26 22:23:02.656013 from : (1, 0, 0)
