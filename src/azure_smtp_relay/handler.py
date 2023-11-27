"""
Module Description: This module contains the implementation of the SmtpHandler class.

The SmtpHandler class provides functionality for handling SMTP commands and processing messages received by the smtpd service.

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

import asyncio
import re
import base64
from aiosmtpd.smtp import Session, Envelope
import ipcalc
from queue_processor import QueueManager, QueueCommandError
from .address_list import AddressList
from .config import SmtpConfig

class SmtpHandler:
    """
    Class Description: The SmtpHandler class provides functionality for handling SMTP commands and processing messages received by the
        aiosmtpd service.  The handler must be initaited using the SmtpConfig class and also must be provided a reference to the QueueManager
        that will hold the queued messages that are received.

    Methods:
        handle_RCPT: Process recipient list after RCPT command.
        handle_DATA: Function to handle messages received by the smtpd service.

    Example:
        Example of using the SmtpHandler class:
        >>> handler = SmtpHandler(logger=your_logger, config=your_smtp_config, queue=your_queue_manager)
        >>> smtpd = Controller(handler, hostname='0.0.0.0', port=10025, ready_timeout=10)
        >>> smtpd.start()

    """
    def __init__(self, logger, config:SmtpConfig, queue:QueueManager):
        """
        Initialize the SmtpHandler instance.

        Args:
            logger (Logger): Logger instance for logging messages.
            config (SmtpConfig): Configuration object for the SMTP service.
            queue (QueueManager): Queue manager for storing messages to be sent.

        Returns:
            None

        Notes:
            This constructor initializes the SmtpHandler instance with the provided logger, configuration, and queue manager.

        Args Description:
            - logger (Logger): Logger instance for logging messages.
            - config (SmtpConfig): Configuration object for the SMTP service.
            - queue (QueueManager): Queue manager for storing messages to be sent.

        Example:
            Example of creating an instance of SmtpHandler:
            >>> handler = SmtpHandler(logger=your_logger, config=your_smtp_config, queue=your_queue_manager)

        """
        self._logger = logger
        self._config = config
        self._queue = queue

    async def handle_RCPT(self, server, session, envelope, address:str, rcpt_options):
        """
        Process recipient list after RCPT command.

        Args:
            server: The SMTP server instance.
            session: The SMTP session instance.
            envelope: The SMTP envelope instance.
            address (str): The recipient address.
            rcpt_options: Options associated with the recipient.

        Returns:
            str: The response message.

        Notes:
            This method processes the recipient list after the RCPT command and checks against allowed destination domains and subnets.

        Args Description:
            - server: The SMTP server instance.
            - session: The SMTP session instance.
            - envelope: The SMTP envelope instance.
            - address (str): The recipient address.
            - rcpt_options: Options associated with the recipient.

        Returns Description:
            - str: The response message.

        Example:
            Example of handling RCPT command:
            >>> response = await handler.handle_RCPT(server, session, envelope, address, rcpt_options)
            >>> print(response)

        """
        # check recipient against allowed destination domains
        domain_ok = False
        ip_ok = False
        for domain in self._config.allowed_dest_domains:
            if address.endswith(f"@{domain}"):
                envelope.rcpt_tos.append(address)
                domain_ok = True
                break

        for allowed_subnet in self._config.allowed_subnets:
            if isinstance(session, Session) and session.peer is not None and str(ipcalc.IP(session.peer[0])) in allowed_subnet:
                ip_ok = True

        if not ip_ok:
            self._logger.warning(f"Rejected mail relay from {session.peer[0] if session.peer is not None else None}:{session.peer[1] if session.peer is not None else None}")
            return f'550 {session.peer[0] if session.peer is not None else None} not permitted'

        if not domain_ok:
            self._logger.warning(f"Rejected mail relay from {session.peer[0] if session.peer is not None else None}:{session.peer[1] if session.peer is not None else None} to {address}")
            return "550 not relaying to that domain"

        return "250 OK"

    async def handle_DATA(self, server, session:Session, envelope:Envelope):
        """
        Function to handle messages received by the smtpd service.

        Args:
            server: The SMTP server instance.
            session (Session): The SMTP session instance.
            envelope (Envelope): The SMTP envelope instance.

        Returns:
            str: The response message.

        Notes:
            This method handles messages received by the smtpd service, parses the message, logs details, and adds the message to the queue.

        Args Description:
            - server: The SMTP server instance.
            - session (Session): The SMTP session instance.
            - envelope (Envelope): The SMTP envelope instance.

        Returns Description:
            - str: The response message.

        Example:
            Example of handling DATA command:
            >>> response = await handler.handle_DATA(server, session, envelope)
            >>> print(response)

        """
        # try parsing the incoming message
        try:
            peer = session.peer
            mail_from = AddressList(envelope.mail_from)
            rcpt_tos = AddressList(envelope.rcpt_tos)
            rcpt_cc = AddressList()
            rcpt_bcc = AddressList()
            reply_to = AddressList()
            data = envelope.content if isinstance(envelope.content, bytes) else str(envelope).encode()

            # log incoming message
            self._logger.info(f"Message received from {peer[0] if peer is not None else None}:{peer[1] if peer is not None else None}, from: {mail_from.first_address}, to: {rcpt_tos.first_address}")

            # setup the message header
            message = {
                "content": {
                },
                "recipients": {
                },
                'senderAddress': '',
                "headers": {
                    "X-azure-smtp-relay": "Sent by Python azure_smtp_relay"
                }
            }

            # parse the message header
            message_lines = data.decode('utf-8').split('\r\n')
            # loop through the envelope
            mime_data = False
            pos = 0
            for line in message_lines:
                if line == '':
                    # we reached the end of the envelope
                    pos+=1 #skip the blank!
                    break
                if line.startswith('Subject:'):
                    message['content']['subject'] = line.split(':')[1].lstrip()
                elif line.startswith('To:'):
                    rcpt_tos.add(line.split(':')[1].lstrip())
                elif line.startswith('Cc:'):
                    rcpt_cc.add(line.split(':')[1].lstrip())
                elif line.startswith('Bcc:'):
                    rcpt_bcc.add(line.split(':')[1].lstrip())
                elif line.startswith('From:'):
                    mail_from.add(line.split(':')[1].lstrip())
                elif line.startswith('Reply-To:'):
                    reply_to.add(line.split(':')[1].lstrip())
                elif line.startswith('Mime-Version:'):
                    mime_data = True
                # maintain the position so we can capture the message data
                pos +=1

            # override from address and original from to reply-to
            if self._config.move_from_replyto:
                reply_to = mail_from
            mail_from = AddressList(self._config.from_address)

            # If we are at the end of the message after the envelope, then we have no content!
            if pos >= len(message_lines) - 1:
                raise ValueError("No message body found after envelope!")

            # get the message body
            if mime_data:
                # loop through and capture the MIME header
                mime_data = {}
                while message_lines[pos] != '':
                    if message_lines[pos].startswith('Content-Type:'):
                        mime_re = re.search(r"Content-Type:\s*(?P<type>[ -~^/]+/[ -~^/;]+);\s*charset=(?P<charset>[ -~]+)", message_lines[pos])
                        if mime_re:
                            mime_data['type'] = mime_re.groupdict().get('type', None)
                            mime_data['charset'] = mime_re.groupdict().get('charset', None)
                    elif message_lines[pos].startswith('Content-Transfer-Encoding:'):
                        mime_re = re.search(r"Content-Transfer-Encoding:\s*(?P<encoding>[ -~^/]+)", message_lines[pos])
                        if mime_re:
                            mime_data['encoding'] = mime_re.groupdict().get('encoding', None)
                    elif message_lines[pos].startswith('Content-Disposition:'):
                        mime_re = re.search(r"Content-Disposition:\s*(?P<disposition>[ -~^/]+)", message_lines[pos])
                        if mime_re:
                            mime_data['disposition'] = mime_re.groupdict().get('disposition', None)
                    elif 'MIME_boundary' in message_lines[pos]:
                        mime_re = re.search(r"[-]*(?P<boundary>MIME_boundary_[a-zA-Z0-9]+)", message_lines[pos])
                        if mime_re:
                            mime_data['boundary'] = mime_re.groupdict().get('boundary', None)
                    pos += 1
                # get find the line where the MIME data ends
                pos2 = pos + 1
                while pos2 < len(message_lines):
                    if mime_data.get('boundary', None) in message_lines[pos2]:
                        break
                    pos2 += 1
                try:
                    message['content']['html'] = base64.b64decode(''.join(message_lines[pos:pos2])).decode(mime_data.get('charset', 'utf-8'))
                except Exception as e:
                    raise ValueError(f"Unable to decode message MIME data: {mime_data}, error: {e}") from e
            else:
                message['content']['plainText'] = '\r\n'.join(message_lines[pos:])

            # fill in address lists
            message['senderAddress'] = mail_from.first_address
            message['replyTo'] = reply_to.addresses
            message['recipients'] = {
                "to": rcpt_tos.addresses,
                "bcc": rcpt_bcc.addresses,
                "cc": rcpt_cc.addresses
            }

            # run some basic checks to make sure we have an actual message to send
            if message['content'].get('subject', None) is None:
                raise ValueError("No message subject!")
            if message['content'].get('html', None) is None and message['content'].get('plainText', None) is None:
                raise ValueError("No message body!")
            if len(message['recipients'].get('to', [])) == 0:
                raise ValueError("No message recipients!")
            if message.get('senderAddress', '') == '':
                raise ValueError("No from address!")

        except ValueError as e:
            self._logger.error(f"Unable to process message {session.peer[0] if session.peer is not None else None}:{session.peer[1] if session.peer is not None else None}" \
                               f", from: {envelope.mail_from}, to: {envelope.rcpt_tos}, Error: {e}")
            return '500 Unable to process'

        # Add the message to the queue
        try:
            self._queue.add(kwargs={'message': message, 'retry': self._config.message_retry})
            # return ok
            return '250 Message accepted for delivery'
        except QueueCommandError as e:
            self._logger.error(f"Unable to process message {session.peer[0] if session.peer is not None else None}:{session.peer[1] if session.peer is not None else None}" \
                               f", from: {mail_from}, to: {rcpt_tos}, Message Queue Error: {e}")
            return '500 Queue error'
