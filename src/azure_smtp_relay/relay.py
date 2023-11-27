"""
Module Description: This module contains the implementation of the AzureSmtpRelay class.

The AzureSmtpRelay class provides functionality for handling both the async smtpd service and the Azure relay.

Usage:
    Example usage of the AzureSmtpRelay class:
    >>> relay_instance = AzureSmtpRelay(address='127.0.0.1', port=25, from_address='sender@example.com', 
                                       allowed_dest_domains=['example.com'], allowed_subnets=['192.168.0.0/24'],
                                       azure_auth=your_azure_auth, endpoint='your_azure_endpoint')
    >>> relay_instance.start()
    >>> relay_instance.send_message(message=your_message)
    >>> log_entries = relay_instance.log
    >>> relay_instance.close()

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

from time import sleep, time
from threading import Thread, Lock
from datetime import datetime
import ipaddress
from logging_handler import create_logger, INFO
from azure.communication.email import EmailClient
from azure.identity import ClientSecretCredential
from azure.core.credentials import AzureKeyCredential
from aiosmtpd.controller import Controller
from queue_processor import QueueManager
from .address_list import email_address_valid, email_domain_valid

from .config import KEEPALIVE_INTERVAL, AZURE_SEND_TIMEOUT, AZURE_SEND_QUEUE_MAX_AGE, AZURE_MESSAGE_RETRY, AZURE_MESSAGE_RETRY_DELAY, RETAIN_LOG_DAYS, RELAY_QUEUE_LIMIT, SmtpConfig
from .handler import SmtpHandler


class AzureSmtpRelay:
    """
    Class Description: AzureSmtpRelay provides functionality for handling both the async smtpd service and the Azure relay.

    Attributes:
        enable_send_log (bool): Flag to enable message sending logs.

    Methods:
        __init__: Initialize the AzureSmtpRelay instance.
        __del__: Destructor to clean up resources.
        close: Close all open objects.
        start: Initialize and start the SMTPD service.
        smtp_ok: Check if the SMTP service is up and running.
        log: Return a copy of the log list.
        clear_log: Clear the message log.
        message_queue_length: Return the number of messages waiting to be sent.

    Example:
        Example of using the AzureSmtpRelay class:
        >>> relay_instance = AzureSmtpRelay(address='127.0.0.1', port=25, from_address='sender@example.com', 
                                            allowed_dest_domains=['example.com'], allowed_subnets=['192.168.0.0/24'],
                                            azure_auth=your_azure_auth, endpoint='your_azure_endpoint')
        >>> relay_instance.start()
        >>> relay_instance.send_message(message=your_message)
        >>> log_entries = relay_instance.log
        >>> relay_instance.close()

    """
    def __init__(self, address:str, port:int|str, from_address:str, domains:list, subnets:list,
                 azure_auth:ClientSecretCredential|AzureKeyCredential, endpoint:str, log_level=INFO, max_queue_length=RELAY_QUEUE_LIMIT,
                 enable_send_log=True, retain_log_days:int=RETAIN_LOG_DAYS,
                 send_queue_max_age=AZURE_SEND_QUEUE_MAX_AGE, move_from_replyto=True,
                 message_retry:int=AZURE_MESSAGE_RETRY, message_retry_delay:int=AZURE_MESSAGE_RETRY_DELAY,
                 send_timeout=AZURE_SEND_TIMEOUT, name:str|None=None):
        """
        Initialize the AzureSmtpRelay instance.

        Args:
            address (str): The address for the SMTPD service.
            name(str|None): A friendly name for the STMPD service (used in log messages).
            port (int|str): The port for the SMTPD service.
            from_address (str): The sender's email address.
            domains (list): List of allowed destination email domains.
            subnets (list): List of allowed subnets.
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
            retain_log_days (int): Number of days to retain log entries.
            send_timeout (int): Timeout (in seconds) for sending messages to Azure.

        Returns:
            None

        Notes:
            This constructor initializes the AzureSmtpRelay instance with the provided configuration.

        Example:
            Example of creating an instance of AzureSmtpRelay:
            >>> relay_instance = AzureSmtpRelay(address='127.0.0.1', port=25, from_address='sender@example.com', 
                                                allowed_dest_domains=['example.com'], allowed_subnets=['192.168.0.0/24'],
                                                azure_auth=your_azure_auth, endpoint='your_azure_endpoint')

        """
        self._config = SmtpConfig(address=address, port=int(port), from_address=from_address, allowed_dest_domains=domains,
                                  allowed_subnets=subnets, move_from_replyto=bool(move_from_replyto), message_retry=int(message_retry),
                                  message_retry_delay=int(message_retry_delay), retain_log_days=int(retain_log_days), send_timeout=int(send_timeout))
        self._logger = create_logger(log_level, name=f"smtpd {self._config.address}:{self._config.port}" + (f"({name})" if name is not None else ''))
        self._smtpd = None
        self.name = name
        self._smtpd_check_thread = None
        self._smtpd_check_thread_stop = False
        self._smtpd_restart_counter = 0
        self.enable_send_log = enable_send_log
        self._log = []
        self._message_queue = QueueManager(name='AzureSMTP', depth=int(max_queue_length), command_func=self._send_message, delay_ms=0,
                                           max_age=int(send_queue_max_age), timeout=int(send_timeout)*2, raise_queue_full=True)
        self._lock = Lock()
        if isinstance(azure_auth, ClientSecretCredential) and isinstance(endpoint, str):
            self._azure_client = EmailClient(endpoint=endpoint, credential=azure_auth)
        elif isinstance(azure_auth, AzureKeyCredential) and isinstance(endpoint, str):
            self._azure_client = EmailClient(endpoint=endpoint, credential=azure_auth)

        # run some checks to ensure valid data
        if not email_address_valid(from_address):
            raise ValueError(f"{from_address} is not a valid email!")
        for domain in domains:
            if not email_domain_valid(domain):
                raise ValueError(f"Domain {domain} is not a valid email domain!")
        try:
            ipaddress.ip_address(self._config.address)
        except ValueError as e:
            raise ValueError(f"Address {address} is not valid! {e}") from e
        if not isinstance(port, int) and not 0 < self._config.port < 65535:
            raise ValueError(f"Port {port} not valid! TCP port must be an integer between 0 and 65535")

        # start the SMTPD thread
        self._handler = None
        self.start()

    def __del__(self):
        """
        Destructor to clean up resources.

        Returns:
            None

        Notes:
            This method is automatically called when an instance of AzureSmtpRelay is deleted.
            It ensures that the SMTPD service is stopped and resources are released.

        Example:
            Example of cleaning up resources when an instance is deleted:
            >>> del relay_instance

        """
        self.close()

    def close(self):
        """
        Returns:
            None

        Notes:
            This method terminates the keepalive thread, stops the SMTPD service, clears the message log, and resets internal variables.

        Example:
            Example of closing open objects:
            >>> self.close()

        """
        if isinstance(self._smtpd_check_thread, Thread):
            self._logger.info('Termating keepalive thread...')
            self._smtpd_check_thread_stop = True
            self._smtpd_check_thread.join(timeout=KEEPALIVE_INTERVAL * 3)
            self._smtpd_check_thread = None
        if self._smtpd is not None:
            self._logger.info('Stopping SMTPD service...')
            self._smtpd.stop()
            self._smtpd = None
        self.clear_log()
        self._smtpd_check_thread_stop = False

    def start(self):
        """
        Returns:
            None

        Notes:
            This method initializes the SMTPD service, creates a handler, and starts the SMTPD server.
            It also starts a background thread to periodically check the status of the SMTP service.

        Example:
            Example of starting the SMTPD service:
            >>> self.start()

        """
        if self._smtpd is not None or self._smtpd_check_thread is not None:
            self.close()
        self._logger.info("Starting SMTPD service...")
        self._handler = SmtpHandler(logger=self._logger, config=self._config, queue=self._message_queue)
        self._smtpd = Controller(self._handler, hostname=self._config.address, port=self._config.port, ready_timeout=10)
        self._smtpd.start()
        sleep(.5)
        if self._smtpd.server is None or not self._smtpd.server.is_serving():
            self._logger.error("Error starting SMTPD service.  Check configuration.")
        else:
            self._logger.info("SMTPD service running.")
            # sstart keepalive thread
            self._smtpd_check_thread = Thread(target=self._background_thread, daemon=True)
            self._smtpd_check_thread.start()

    @property
    def smtp_ok(self) -> bool:
        """
        Returns:
            bool: True if the SMTP service is running, False otherwise.

        Notes:
            This property checks the status of the SMTP service and returns True if it is up and running.

        Returns Description:
            - bool: True if the SMTP service is running, False otherwise.

        Example:
            Example of checking the SMTP service status:
            >>> is_smtp_running = self.smtp_ok
            >>> print(f"SMTP service is running: {is_smtp_running}")

        """
        if self._smtpd is not None and self._smtpd.server is not None and self._smtpd.server.is_serving():
            return True
        return False

    def _background_thread(self):
        """
        Returns:
            None

        Notes:
            This method runs as a background thread to periodically check the status of the SMTP service.
            If the service has stopped unexpectedly, it attempts to restart it.

        Example:
            This method is designed to run continuously in the background and does not require explicit invocation.

        """
        while not self._smtpd_check_thread_stop:
            if self._smtpd is None or self._smtpd.server is None or not self._smtpd.server.is_serving():
                self._smtpd_restart_counter += 1
                self._logger.error(f"SMTPD service has stopped unexpectedly. This has happened {self._smtpd_restart_counter} times. Attempting restart...")
                Thread(target=self.start, daemon=True).start()
                return
            sleep(KEEPALIVE_INTERVAL)

    def _send_message(self, message:dict, retry:int):
        """
        Send a message to Azure.

        Args:
            message (dict): A dictionary representing the message to be sent. 
                (See https://learn.microsoft.com/en-us/azure/communication-services/quickstarts/email/send-email?tabs=linux%2Cconnection-string&pivots=programming-language-python
                 for details on the Azure email object model)
            retry (int): The number of retry attempts in case of failure.

        Raises:
            Any exception raised during the message sending process.

        Returns:
            None

        Notes:
            This method sends a message to Azure using the Azure client. It logs the process and handles retries if needed.

        Args Description:
            - message (dict): The message to be sent, formatted as a dictionary.
            - retry (int): The number of retry attempts in case of failure.

        Log Format:
            The log entry format includes the following fields:
            - time: The timestamp of the log entry.
            - date: The date and time when the log entry was created.
            - from: The sender of the message (extracted from the 'replyTo' field in the message).
            - to: The recipients of the message (extracted from the 'recipients' field in the message).
            - subject: The subject of the message (extracted from the 'content' field in the message).
            - azure_result: The result of the Azure operation.
            - status: The status of the message (OK, FAILED, REQUEUE).
            - retry: The remaining retry attempts.
            - exception: Any exception raised during the process.

        Examples:
            Example of sending a message:
            >>> self._send_message({'replyTo': 'sender@example.com', 'recipients': ['recipient@example.com'], 'content': {'subject': 'Hello, Azure!'}}, retry=3)

        """
        # Start the log entry
        log_index = len(self._log)
        if self.enable_send_log:
            with self._lock:
                self._log.append({'time': time(), 'date': datetime.now(), 'from': message.get('replyTo'), 'to': message.get('recipients'), 'subject': message['content'].get('subject'),
                    'azure_result': None, 'status': None, 'retry': retry, 'exception': None})
        try:
            self._logger.info(f"Sending queued message from {message.get('replyTo')} to {message.get('recipients')} subject {message['content'].get('subject')}")

            poller = self._azure_client.begin_send(message=message, connection_timeout=float(self._config.send_timeout))
            poller.wait(self._config.send_timeout)
            if str(poller.result().get('status')).lower() != 'succeeded':
                # if Azure poller did not come back as scceeded, requeue until we hit the max
                if retry > 0:
                    if self.enable_send_log:
                        with self._lock:
                            self._log[log_index].update(azure_result=poller.result(), status='REQUEUE')
                    self._logger.warning(f"FAILED, requeing ({self._config.message_retry - retry}/{self._config.message_retry}) message from {message.get('replyTo')} to {message.get('recipients')}" \
                                            f" subject {message['content'].get('subject')}: {poller.result()}, retry: {retry}")
                    self._message_queue.add(kwargs={'message': message, 'retry': retry - 1}, run_after=time() + self._config.message_retry_delay)
                else:
                    if self.enable_send_log:
                        with self._lock:
                            self._log[log_index].update(azure_result=poller.result(), status='FAILED')
                    self._logger.error(f"FAILED, DISCARDING MESSAGE from {message.get('replyTo')} to {message.get('recipients')} subject {message['content'].get('subject')}: {poller.result()}")
            else:
                # success!  log it and move on
                if self.enable_send_log:
                    with self._lock:
                        self._log[log_index].update(azure_result=poller.result(), status='OK')
                self._logger.debug(f"Success sending message from {message.get('replyTo')} to {message.get('recipients')} subject {message['content'].get('subject')}: {poller.result()}")
        except Exception as e:
           # An exception was raised, ie TCP timeout or DNS resolve failure. Requeue until we hit the max
            if retry > 0:
                if self.enable_send_log:
                    with self._lock:
                        self._log[log_index].update(azure_result=None, status='REQUEUE', exception=e)
                self._logger.error(f"EXCEPTION RAISED, REQUEUING MESSAGE from {message.get('replyTo')} to {message.get('recipients')} subject {message['content'].get('subject')}: " \
                                   f"{e}, retry: {retry}")
                self._message_queue.add(kwargs={'message': message, 'retry': retry - 1}, run_after=time() + self._config.message_retry_delay)
            else:
                if self.enable_send_log:
                    with self._lock:
                        self._log[log_index].update(azure_result=None, status='FAILED', exception=e)
                self._logger.error(f"EXCEPTION RAISED, DISCARDING MESSAGE from {message.get('replyTo')} to {message.get('recipients')} subject {message['content'].get('subject')}: " \
                                   f"{e}, retry: {retry}")

        # cleanup the log
        with self._lock:
            while len(self._log) > 0 and self._log[0]['time'] + (self._config.retain_log_days * 86400) < time():
                del self._log[0]

    @property
    def log(self) -> list:
        """
        Return a copy of the log list.

        NOTE: This is a COPY, not a reference to the log, to prevent locking issues.

        Returns:
            list: A copy of the log entries.

        Notes:
            This property returns a copy of the log list to ensure thread safety by preventing direct access to the log.
            The log contains entries with information about sent messages, including timestamps, sender, recipients, subject,
            Azure result, status, retry attempts, and exceptions.

        Returns Description:
            - list: A list containing log entries.

        Example:
            Example of retrieving a copy of the log:
            >>> log_copy = self.log
            >>> print(log_copy)

        """
        with self._lock:
            return self._log.copy()

    def clear_log(self):
        """
        Clear the message log.

        Returns:
            None

        Notes:
            This method clears the message log, removing all entries.

        Example:
            Example of clearing the message log:
            >>> self.clear_log()

        """
        with self._lock:
            self._logger.info("Clearing message log...")
            del self._log
            self._log = []

    @property
    def message_queue_length(self) -> int:
        """
        Return the number of messages waiting to be sent.

        Returns:
            int: The number of messages in the queue.

        Notes:
            This property provides the current length of the message queue, indicating the number of messages waiting to be sent.

        Returns Description:
            - int: The number of messages in the queue.

        Example:
            Example of retrieving the message queue length:
            >>> queue_length = self.message_queue_length
            >>> print(f"Number of messages in the queue: {queue_length}")

        """
        return self._message_queue.length
