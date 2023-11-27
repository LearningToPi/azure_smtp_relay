import argparse
import configparser
import inspect
from datetime import datetime
from time import time, sleep
from azure.identity import ClientSecretCredential
from azure.core.credentials import AzureKeyCredential
from smtplib import SMTP
from . import VERSION
from .relay import AzureSmtpRelay
from .toml_config_mgr import TomlConfigMgr
from logging_handler import create_logger, INFO, WARNING
from .config import KEEPALIVE_INTERVAL, AZURE_SEND_TIMEOUT, AZURE_SEND_QUEUE_MAX_AGE, AZURE_MESSAGE_RETRY, AZURE_MESSAGE_RETRY_DELAY, RETAIN_LOG_DAYS, RELAY_QUEUE_LIMIT

LOG_LEVEL = INFO
SMTP_DEFAULT_PORT = "25"
SMTP_DEFAULT_LISTEN = '0.0.0.0'
RESTART_PER_HOUR = '5'
RESTART_DELAY_SECONDS = '5'
CONFIGPARSE_LIST_PARAMS = ['domains', 'subnets']

TOML_CONFIG = {
    "relay": {
        "address": {
            "type": str, 
            "default": "0.0.0.0",
            "help": "IP address to listen on. By default uses 0.0.0.0 (all addresses)"},
        "port": {
            "type": int, 
            "default": 10025,
            "help": "TCP port number to listen on for incoming SMTP traffic. By default uses port 25."},
        "from_address": {
            "type": str, 
            "required": True,
            "help": "Email address to use as From address. Must be authorized in Azure communication service."},
        "domains": {
            "type": list, 
            "list_types": str, 
            "separators": [',', '\n'], 
            "required": True,
            "help": 'Domains to accept email for. Domains should be a comma separated list. i.e. none.com,onmicrosoft.com'},
        "subnets": {
            "type": list, 
            "list_types": [str], 
            "separators": [',', '\n'], 
            "required": True,
            "help": 'Subnets that should be allowed to relay email. Subnets should be a comma separated list. i.e. 192.168.0.0/16,10.0.0.0/8'},
        "log_level": {
            "type": str, 
            "valid_values": ["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL", "info", "debug", "warning", "error", "critical"],
            "help": 'Logging level for the service. Defaults to INFO.'},
        "max_queue_length": {"type": int,
            "default": RELAY_QUEUE_LIMIT,
            "help": "Maximum number of messages to retain in the queue before discarding."},
        "enable_send_log": {"type": bool,
            "default": True,
            "help": "Enable the send log."},
        "retain_log_days": {"type": int, 
            "default": RETAIN_LOG_DAYS,
            "help": "Number of days to retain log data"},
        "send_queue_max_age": {"type": int, 
            "default": AZURE_SEND_QUEUE_MAX_AGE,
            "help": "'Maximum number of seconds to hold a message in the queue."},
        "send_timeout": {"type": int, 
            "default": AZURE_SEND_TIMEOUT,
            "help": "Timeout for sending to the Azure communication service."},
        "message_retry": {"type": int,
            "default": AZURE_MESSAGE_RETRY,
            "help": "Number of times to retry a message before discarding."},
        "message_retry_delay": {"type": int,
            "default": AZURE_MESSAGE_RETRY_DELAY,
            "help": "Number of seconds before retrying a message."}
    },
    "server": {
        "server_restart_per_hour": {"type": int,
            "default": RESTART_PER_HOUR,
            "help": 'Maximum number of times to attempt restarting the server if a failure occurs.'},
        "server_restart_email": {"type": str,
            "help": "Email address to send a report to after a server restarts after a failure."}
    },
    "azure": {
        "endpoint": {"type": str,
                     "help": "Azure Communication Endpoint URL. See README.md for help finding."},
        "key": {"type": str,
                "help": "Azure Key to use for authentication. Not required if using service principal. See README.md for help finding."},
        "tenant_id": {"type": str,
                      "help": "Azure Tenant ID. Only required when using a service principal. See README.md for help finding."},
        "client_id": {"type": str,
                      "help": "Azure client ID (unique ID of service principal). See README.md for help finding."},
        "client_secret": {"type": str,
                          "help": "Azure client secret generated for the service principal. See README.md for help generating."}
    }
}


def main():
    # setup the argument parser
    parser = argparse.ArgumentParser(prog="azure_smtp_relay.py", description="Manage the build, test and Git deployment of Python packages.")
    run_config = TomlConfigMgr(**TOML_CONFIG)
    run_config.update_argparser(parser)

    parser.add_argument('--config', '-c', required=False, type=str, default=None,
                        help="JSON config file to load. See README.md file for contents.")
    parser.add_argument('--print-version', '-vv', required=False, action='store_true', default=False,
                        help="Print the current version and quit.")

    args = vars(parser.parse_args())

    if args.get('print_version'):
        print("SMTP relay service forwarding through Azure Communication Service (azure_smtp_relay)")
        print(f"Version: {str(VERSION[0])}.{str(VERSION[1])}.{str(VERSION[2])}{'-' + str(VERSION[3]) if len(VERSION) >= 4 else ''}") # type: ignore
        print("Use command line parameter '-h' or see the README.md file in github for usage details: https://github.com/learningtopi/azure_smtp_relay/")
        quit(0)

    # if a config file was provided, load the config file
    if args.get('config') is not None:
        run_config.load_toml(str(args.get('config')))

    # load all passed parameters
    for section in run_config.sections():
        for key in run_config.section_keys(section):
            run_config.update(section, key, args.get(key))

    # start the relay server
    logger = create_logger(WARNING, name='RelayException')
    restart_from_exception = False
    restart_info = []
    while True:
        try:
            # create the azure login object
            azure_creds = None
            if run_config.get('azure', 'key') is not None:
                azure_creds = AzureKeyCredential(key=run_config.get('azure', 'key'))
            if run_config.get('azure', 'client_secret') is not None:
                if run_config.get('azure', 'tenant_id') is None or run_config.get('azure', 'client_id') is None:
                    print('If using an Azure service principal you MUST provide a tenant_id, client_id and client_secret.')
                    quit(1)
                azure_creds = ClientSecretCredential(tenant_id=run_config.get('azure', 'tenant_id'),
                                                     client_id=run_config.get('azure', 'client_id'),
                                                     client_secret=run_config.get('azure', 'client_secret'))
            if azure_creds is None:
                print('Azure credentials are required!')
                quit(1)


            relay_server = AzureSmtpRelay(azure_auth=azure_creds, endpoint=run_config.get('azure', 'endpoint'), **run_config.config('relay')) # type: ignore
            if restart_from_exception and run_config.get('server', 'server_restart_email') is not None:
                # we are restarting after a server failure, send an email with the failure info
                client = SMTP(host=run_config.get('relay', 'address') if run_config.get('relay', 'address') != '0.0.0.0' else '127.0.0.1',
                              port=int(run_config.get('relay', 'port')))
                try:
                    message = "To: {to}\r\n" \
                              "From: {msg_from}\r\n" \
                              "Subject: {subject}\r\n" \
                              "\r\n" \
                              "{body}\r\n"
                    client.sendmail(from_addr=run_config.get('relay', 'from_address'),
                                    to_addrs=run_config.get('relay', 'server_restart_email'),
                                    msg=message.format(to=run_config.get('server', 'server_restart_email'),
                                                       smg_from=run_config.get('relay', 'from_address'),
                                                       subject="AZURE SMTP RELAY SERVICE FAILURE",
                                                       body=f"Relay service failed at {datetime.fromtimestamp(restart_info[-1]['time'])}, error {restart_info[-1]['error']}"))
                except Exception as e:
                    logger.error(f"Error sending email regarding relay service failure: {e}. Original failure message: Relay service failed at {datetime.fromtimestamp(restart_info[-1]['time'])}, error {restart_info[-1]['error']}")

            # raise an exception if the relay server is down
            while True:
                try:
                    if not relay_server.smtp_ok:
                        raise ChildProcessError(f"Relay service not operational.  SMTP status: {relay_server.smtp_ok}, message queue length: {relay_server.message_queue_length}. Queued messages will be lost.")
                except KeyboardInterrupt:
                    logger.info("Interrupt received.  Stopping relay server...")
                    relay_server.close()
                    quit(0)

        except Exception as e:
            # the server crashed, log it and wait before restarting
            restart_from_exception = True
            restart_info.append(dict(time=time(), error=e))
            logger.critical(f"Azure relay service failed with error: {e}")
            if len([x for x in restart_info if x.get('time') > time() - 3600]) > int(RESTART_PER_HOUR):
                logger.critical(f"Restarted {RESTART_PER_HOUR} in the last hour. Terminating.")
                quit(2)
            else:
                logger.critical(f"Restarting the azure relay service in {RESTART_DELAY_SECONDS} seconds.  Restarted {len([x for x in restart_info if x.get('time') > time() - 3600])} times in past hour...")
            sleep(int(RESTART_DELAY_SECONDS))

if __name__ == "__main__":
    main()
