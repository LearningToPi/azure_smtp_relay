import unittest
import json
import os
from time import time, sleep
from time import sleep
from smtplib import SMTP, SMTPRecipientsRefused
from azure_smtp_relay import AzureSmtpRelay, ClientSecretCredential, AzureKeyCredential
from azure_smtp_relay.config import AZURE_SEND_TIMEOUT
from threading import Lock

PORT_LOCK = Lock()
LAST_PORT = 0

def get_port(port_range:list) -> int:
    ''' Issue a port from the specified port range, save the port issued to start the next time '''
    print(port_range)
    global LAST_PORT
    with PORT_LOCK:
        if port_range[0] <= LAST_PORT <= port_range[1]:
            if LAST_PORT + 1 <= port_range[1]:
                LAST_PORT += LAST_PORT
                print('1--issued port', LAST_PORT)
                return LAST_PORT
            else:
                raise ValueError(f'Port {LAST_PORT} out of range! {port_range}')
        else:
            LAST_PORT = port_range[0]
            print('2--issued port', LAST_PORT)
            return LAST_PORT

CONFIG_FILE_PATHS = [os.path.join('local', 'test_settings.json'), os.path.join('azure_smtp_relay', 'local', 'test_settings.json')]
TEST_MESSAGE = "To: {to}\r\n" \
               "From: {msg_from}\r\n" \
               "Cc: {cc}\r\n" \
               "Subject: {subject}\r\n" \
               "\r\n" \
               "{test}\r\n" \
               "{body}\r\n"

for config_file in CONFIG_FILE_PATHS:
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as input_file:
            config = json.load(input_file)
            break

class azure_relay_test(unittest.TestCase):
    ''' Run a sseries of tests '''
    def test_1_test_relay(self):
        ''' Startup a relay server and test sending messages '''
        test_num = 1
        for azure_cred in config['azure_test_creds']:
            if azure_cred['type'] == 'key':
                cred = AzureKeyCredential(**azure_cred['values'])
            elif azure_cred['type'] == 'service_principal_secret':
                cred = ClientSecretCredential(**azure_cred['values'])
            else:
                raise ValueError(f"Unknown credential type: {azure_cred['type']}")
            updated_config = config.copy()
            updated_config['azure_relay']['send_timeout'] = 30
            updated_config['azure_relay']['message_retry_delay'] = 30
            updated_config['azure_relay']['message_retry'] = 3
            test_name = f"1/{azure_cred['type']}"
            server = AzureSmtpRelay(azure_auth=cred, name=test_name, port=config['test_port_range']+ test_num, **updated_config['azure_relay'])
            self.assertTrue(server.smtp_ok)
            # send the test messages
            # NOTE: This will only confirm that Azure accepted the message for the recipient, you will need to verify that you received!
            client = SMTP(host="127.0.0.1", port=config['test_port_range'] + test_num)
            for message in config['test_emails']:
                client.sendmail(from_addr=message['from'],
                                to_addrs=message['to'],
                                msg=TEST_MESSAGE.format(to=message['to'], msg_from=message['from'], cc=message['cc'], subject=message['subject'], body=message['body'], test=test_name))
                # NOTE: sendmail will raise an error if the message is not accepted
            client.close()

            # wait up to the AZURE_SEND_TIMEOUT * number of messages
            start_time = time()
            while time() < start_time + (AZURE_SEND_TIMEOUT * len(config['test_emails']) * updated_config['azure_relay']['message_retry']) or server.message_queue_length > 0:
                sleep(1)

            # verify that all messages were sent successfully
            self.assertTrue(len([x for x in server.log if x['status'] == 'OK']) == len(config['test_emails']))
            server.close()

    def test_2_test_dns_failure(self):
        ''' Startup a relay server and test timeout due to a DNS lookup failure '''
        # test DNS lookup failure
        test_num = 2
        for azure_cred in config['azure_test_creds']:
            if azure_cred['type'] == 'key':
                cred = AzureKeyCredential(**azure_cred['values'])
            elif azure_cred['type'] == 'service_principal_secret':
                cred = ClientSecretCredential(**azure_cred['values'])
            else:
                raise ValueError(f"Unknown credential type: {azure_cred['type']}")
            updated_config = config.copy()
            updated_config['azure_relay']['endpoint'] = 'nothere.learningtopi.com' # will result in DNS lookup failure
            updated_config['azure_relay']['send_timeout'] = 2
            updated_config['azure_relay']['message_retry_delay'] = 30
            updated_config['azure_relay']['message_retry'] = 3
            test_name = f"2/{azure_cred['type']}"
            server = AzureSmtpRelay(azure_auth=cred, name=test_name, port=config['test_port_range'] + test_num, **updated_config['azure_relay'])
            self.assertTrue(server.smtp_ok)

            # send the test messages
            # NOTE: This will only confirm that Azure accepted the message for the recipient, you will need to verify that you received!
            client = SMTP(host="127.0.0.1", port=config['test_port_range'] + test_num)
            for message in config['test_emails']:
                client.sendmail(from_addr=message['from'],
                                to_addrs=message['to'],
                                msg=TEST_MESSAGE.format(to=message['to'], msg_from=message['from'], cc=message['cc'], subject=message['subject'], body=message['body'], test=test_name))
                # NOTE: sendmail will raise an error if the message is not accepted
            client.close()

            # wait to ensure all messages have timed out and been requeued
            all_message_timeout = len(config['test_emails']) * updated_config['azure_relay']['send_timeout'] + 1
            sleep(all_message_timeout)
            self.assertTrue(len([x for x in server.log if x['status'] == 'REQUEUE']) == len(config['test_emails']))

            for x in range(1, updated_config['azure_relay']['message_retry']):
                # wait for all messages to have been attempted a second time
                sleep(updated_config['azure_relay']['message_retry_delay'] + 1 + all_message_timeout)
                self.assertTrue(len([x for x in server.log if x['status'] == 'REQUEUE']) == (x+1) * len(config['test_emails']))

            # wait one last round or the last retrans and verify that we are now failed
            sleep(updated_config['azure_relay']['message_retry_delay'] + 1 + all_message_timeout)
            self.assertTrue(len([x for x in server.log if x['status'] == 'FAILED']) == len(config['test_emails']))

            server.close()

    def test_3_test_tcp_timeout(self):
        ''' Startup a relay server and test timeout due to a TCP or SSL failure '''
        # test timeout to a resolved address
        test_num = 3
        for azure_cred in config['azure_test_creds']:
            if azure_cred['type'] == 'key':
                cred = AzureKeyCredential(**azure_cred['values'])
            elif azure_cred['type'] == 'service_principal_secret':
                cred = ClientSecretCredential(**azure_cred['values'])
            else:
                raise ValueError(f"Unknown credential type: {azure_cred['type']}")
            updated_config = config.copy()
            updated_config['azure_relay']['endpoint'] = '1.1.1.1:1' # will result in DNS resolution to 127.0.0.1
            updated_config['azure_relay']['send_timeout'] = 5
            updated_config['azure_relay']['message_retry_delay'] = 30
            updated_config['azure_relay']['message_retry'] = 3
            test_name = f"3/{azure_cred['type']}"
            server = AzureSmtpRelay(azure_auth=cred, name=test_name, port=config['test_port_range'] + test_num, **updated_config['azure_relay'])
            self.assertTrue(server.smtp_ok)

            # send the test messages
            # NOTE: This will only confirm that Azure accepted the message for the recipient, you will need to verify that you received!
            client = SMTP(host="127.0.0.1", port=config['test_port_range'] + test_num)
            for message in config['test_emails']:
                client.sendmail(from_addr=message['from'],
                                to_addrs=message['to'],
                                msg=TEST_MESSAGE.format(to=message['to'], msg_from=message['from'], cc=message['cc'], subject=message['subject'], body=message['body'], test=test_name))
                # NOTE: sendmail will raise an error if the message is not accepted
            client.close()

            # wait to ensure all messages have timed out and been requeued
            all_message_timeout = len(config['test_emails']) * updated_config['azure_relay']['send_timeout'] + 1
            sleep(all_message_timeout)
            self.assertTrue(len([x for x in server.log if x['status'] == 'REQUEUE']) == len(config['test_emails']))

            for x in range(1, updated_config['azure_relay']['message_retry']):
                # wait for all messages to have been attempted a second time
                sleep(updated_config['azure_relay']['message_retry_delay'] + 1 + all_message_timeout)
                self.assertTrue(len([x for x in server.log if x['status'] == 'REQUEUE']) == (x+1) * len(config['test_emails']))

            # wait one last round or the last retrans and verify that we are now failed
            sleep(updated_config['azure_relay']['message_retry_delay'] + 1 + all_message_timeout)
            self.assertTrue(len([x for x in server.log if x['status'] == 'FAILED']) == len(config['test_emails']))

            server.close()

    def test_4_test_azure_bad_email(self):
        ''' Startup a relay server and test an error response from the Azure service (by providing a bad source email address) '''
        # test timeout to a resolved address
        test_num = 4
        for azure_cred in config['azure_test_creds']:
            if azure_cred['type'] == 'key':
                cred = AzureKeyCredential(**azure_cred['values'])
            elif azure_cred['type'] == 'service_principal_secret':
                cred = ClientSecretCredential(**azure_cred['values'])
            else:
                raise ValueError(f"Unknown credential type: {azure_cred['type']}")
            updated_config = config.copy()
            updated_config['azure_relay']['from_address'] = 'bad@bad.com' # Not an accepted email address, will produce an error from Azure
            updated_config['azure_relay']['send_timeout'] = 2
            updated_config['azure_relay']['message_retry_delay'] = 15
            updated_config['azure_relay']['message_retry'] = 3
            test_name = f"4/{azure_cred['type']}"
            server = AzureSmtpRelay(azure_auth=cred, name=test_name, port=config['test_port_range'] + test_num, **updated_config['azure_relay'])
            self.assertTrue(server.smtp_ok)

            # send the test messages
            # NOTE: This will only confirm that Azure accepted the message for the recipient, you will need to verify that you received!
            client = SMTP(host="127.0.0.1", port=config['test_port_range'] + test_num)
            for message in config['test_emails']:
                client.sendmail(from_addr=message['from'],
                                to_addrs=message['to'],
                                msg=TEST_MESSAGE.format(to=message['to'], msg_from=message['from'], cc=message['cc'], subject=message['subject'], body=message['body'], test=test_name))
                # NOTE: sendmail will raise an error if the message is not accepted
            client.close()

            # wait to ensure all messages have timed out and been requeued
            all_message_timeout = len(config['test_emails']) * updated_config['azure_relay']['send_timeout'] + 1
            sleep(all_message_timeout)
            self.assertTrue(len([x for x in server.log if x['status'] == 'REQUEUE']) == len(config['test_emails']))

            for x in range(1, updated_config['azure_relay']['message_retry']):
                # wait for all messages to have been attempted a second time
                sleep(updated_config['azure_relay']['message_retry_delay'] + 5 + all_message_timeout)
                self.assertTrue(len([x for x in server.log if x['status'] == 'REQUEUE']) == (x+1) * len(config['test_emails']))

            # wait one last round or the last retrans and verify that we are now failed
            sleep(updated_config['azure_relay']['message_retry_delay'] + 1 + all_message_timeout)
            self.assertTrue(len([x for x in server.log if x['status'] == 'FAILED']) == len(config['test_emails']))

            server.close()

    def test_5_domain_restrictions(self):
        ''' Startup a relay server and test sending to a non-authorized domain '''
        test_num = 5
        for azure_cred in config['azure_test_creds']:
            if azure_cred['type'] == 'key':
                cred = AzureKeyCredential(**azure_cred['values'])
            elif azure_cred['type'] == 'service_principal_secret':
                cred = ClientSecretCredential(**azure_cred['values'])
            else:
                raise ValueError(f"Unknown credential type: {azure_cred['type']}")
            test_name = f"5/{azure_cred['type']}"
            server = AzureSmtpRelay(azure_auth=cred, name=test_name, port=config['test_port_range'] + test_num, **config['azure_relay'])
            self.assertTrue(server.smtp_ok)

            # send the test messages
            # NOTE: This will only confirm that Azure accepted the message for the recipient, you will need to verify that you received!
            client = SMTP(host="127.0.0.1", port=config['test_port_range'] + test_num)
            fail_messages = [
                {
                    "from": "bad@bad.com",
                    "to": "none@none.com",
                    "cc": "",
                    "subject": "test message #1",
                    "body": "This is test message #1"
                },
                {
                    "from": "bad2@bad.com",
                    "to": "none2@none.com",
                    "cc": "",
                    "subject": "test message #2",
                    "body": "This is test message #2"
                }
            ]
            for message in fail_messages:
                self.assertRaises(SMTPRecipientsRefused, client.sendmail, **dict(from_addr=message['from'],
                                to_addrs=message['to'],
                                msg=TEST_MESSAGE.format(to=message['to'], msg_from=message['from'], cc=message['cc'], subject=message['subject'], body=message['body'], test=test_name)))
                # NOTE: sendmail will raise an error if the message is not accepted
            client.close()
            server.close()

    def test_6_ip_restrictions(self):
        ''' Startup a relay server and test sending to a non-authorized relay ip '''
        test_num = 6
        for azure_cred in config['azure_test_creds']:
            if azure_cred['type'] == 'key':
                cred = AzureKeyCredential(**azure_cred['values'])
            elif azure_cred['type'] == 'service_principal_secret':
                cred = ClientSecretCredential(**azure_cred['values'])
            else:
                raise ValueError(f"Unknown credential type: {azure_cred['type']}")
            updated_config = dict(config)
            updated_config['azure_relay']['allowed_subnets'] = '169.254.254.254/32' # override the allowed subnet to a link local address
            test_name = f"6/{azure_cred['type']}"
            server = AzureSmtpRelay(azure_auth=cred, name=test_name, port=config['test_port_range'] + test_num, **updated_config['azure_relay'])
            self.assertTrue(server.smtp_ok)

            # send the test messages
            # NOTE: This will only confirm that Azure accepted the message for the recipient, you will need to verify that you received!
            client = SMTP(host="127.0.0.1", port=config['test_port_range'] + test_num)
            for message in config['test_emails']:
                self.assertRaises(SMTPRecipientsRefused, client.sendmail, **dict(from_addr=message['from'],
                                to_addrs=message['to'],
                                msg=TEST_MESSAGE.format(to=message['to'], msg_from=message['from'], cc=message['cc'], subject=message['subject'], body=message['body'], test=test_name)))
                # NOTE: sendmail will raise an error if the message is not accepted
            client.close()
            server.close()

if __name__ == '__main__':
    unittest.main()
