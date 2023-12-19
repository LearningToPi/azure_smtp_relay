# Azure SMTP Relay

Source: <https://github.com/LearningToPi/azure_smtp_relay>
PyPi: <https://pypi.org/project/azure-smtp-relay/>
Homepage: <https://www.learningtopi.com/python-modules-applications/azure_smtp_relay/>

## Overview

This Dockerfile is based on the azure_smtp_relay Python3 package available on PyPi or GitHub.

The azure_smtp_relay was born out of the change in Azure that blocks outbound SMTP unless you have an Enterprise agreement with Azure to specifically allow outbound SMTP.  (See Microsoft's documentation for more information: <https://learn.microsoft.com/en-us/azure/virtual-network/troubleshoot-outbound-smtp-connectivity>)

Previously I had used a VM running in Azure to relay SMTP messages from systems in my home lab (which also couldn't send direct due to ISP restrictions on outbound SMTP).  Now that Microsoft ALSO blocks SMTP an alternative was needed.

azure_smtp_relay uses the Azure Communication Service (<https://azure.microsoft.com/en-us/products/communication-services>) to foward email from internal systems.  This service acts as an SMTP server to receive inbound email, then forwards the message through the Azure Communication Service which forwards to the appropriate mail server.

## Azure Communication Service

** Please see the Azure_Setup.md () doc for detailed setup of Azure.

The Azure Communication Service accepts email only from domains that have been verified.  You MUST have access to update DNS records of the domain to configure.  You will need to create a TXT record for Azure to verify the domain.  Ideally you will also need to create SPF and DKIM records to minimize the chance of your messages being marked as spam.

** Azure will handle DKIM certificates, you only need to configure DNS records which will be provided for you.

Azure will only allow emails that are FROM  specific addresses.  An email address of 'DoNotReply@...com' will be created in the service automatically.  Additional addresses can be added.  Multiple domains can also be registered with the communication service, however the azure_smtp_relay app will only use one.

## Azure Authentication

Azure supports multiple methods of authentication for the Azure Communication service.  For simplicity, we support two methods with the azure_smtp_relay application:

1. Key based authentication
2. Service Principal Authentication

### Key Based Authentication

Azure auto generates two keys that can be used to authenticate to the endpoint.  Only two keys are supported for the service.  The intent is to allow rotation of 1 key while the other is in operation.  Key based authentication is useful in limited use situations.  Service Principals are recommended as more than one account can be created to allow access to the Azure Communication Service.

## Service Principal

A service principal is more complicated to configure, but allows multiple accounts to be used with the service simultaneously.  A service principal is essentially a service account with a generated password.

Please see the Azure_Setup.md () for detailed setup instructions.

After the service account is created in Microsoft Entra ID (formerly Azure AD) the service account needs to be granted access to use the Azure Commnication service.

## How it works

1. On startup, config is read from a config.toml file, or from command-line parameters (command line parameters will override settings in the config file)
2. Python3 aiosmtpd is used to listen for inbound SMTP
3. A custom handler performs some verification when the SMTP RCTP command is sent (messages that fail the verification are dropped at this point)
   1. Is the message destined to an email address in an authorized domain?
   2. Is the sender from an approved subnet?
4. A custom handler takes the SMTP DATA (MiME content is supported) and places it in a queue and returns OK to the sending device.  The FROM address is moved to the "reply-to" field, and the FROM address is replaced with the email address in the config.  This MUST match one of the email addresses the communication service is configure for (i.e. DoNotReply@...com).
5. Queued messages are sent to the Azure Communication via TLS to the endpoint with the authentication specified in the configuration.  If a message fails to send (TCP timeout, DNS lookup error, etc), the message will be requeued and tried again later.

## Important Notes

- THIS IS NOT INTENDED TO BE AN OPEN RELAY!  You MUST provide both a list of email domains SMTP clients are allowed to send to as well as a list of subnets that you will allow relay from.  This is intended for internal networks that need to send email notifications!
- The docker container will listen on port 10025 by default.  Use the docker "-p 25:10025" option to forward port 25 on your system to the container's port 10025
- By default the azure_smtp_relay package will listen on all available IP's (0.0.0.0). In a docker container this is the containers assigned address and the loopback address.
- A "from_address" is REQUIRED.  This MUST match one of the email addresses configured in the Azure Communication service.  If this does not match Azure will reject the message (i.e. DoNotReply@...com)
- You MUST provide a list of domains the azure_smtp_relay service is allowed to send TO.  This is intended to relay email from internal systems to your own email domain.
- You MUST provide a list of IP networks to azure_smtp_relay that you want to allow SMTP traffic from.  This is not intended to be an open relay.

## TOML Configuration File

THe configuration file used is a ".toml" file.  If you are unfamiliar, this is a similar format to a Windows .INI file.

The "config.toml" file consists of 3 sections:

1. [azure]
2. [relay]
3. [server]

### [azure] Section

The [azure] section is REQUIRED and MUST contain either a key (if using Key based authentication) --OR-- a tenant_id, client_id and client_secret (if using a service principal).  The URL for the Azure Communication service is also required.

    [azure]
    endpoint = "https://.....unitedstates.communication.azure.com"
    tenant_id = '........-....-....-....-............'
    client_id = '........-....-....-....-............'
    client_secret = "........"

### [relay] Section

The [relay] section at minimum must contain the from address, domain list, and list of subnets to allow relay from and from_address are required.  The remaining are additional options that can be provided.

    [relay]
    address = 0.0.0.0
    port = 10025
    from_address = DoNotReply@yourdomain.com
    domains = yourdomain.com,yourdomain2.com
    subnets = 10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
    log_level = INFO
    max_queue_length = 100
    enable_send_log = True
    retain_log_days = 3
    send_queue_max_age = 43200
    send_timeout = 30
    message_retry = 3
    message_retry_delay = 3600

- address - Generally use 0.0.0.0 to listen on all interfaces, ideal if running in Docker
- port - Default is 10025, unless running as root using 25 will be prohibited by the OS. If running in Docker, forward port 25 from the host to port 10025 in the container.
- from_address - This MUST be an address that is permitted to send for the domain in the Azure Communication Service.  See Azure documentation for details.
- domains - comma separated list of domains to allow sending to. This is intended for forwarding to your owm domains, not as an open relay.
- subnets - comma separated list of subnets using CIDR notation.  RFC1918 used above for example.
- log_level - INFO / DEBUG
- max_queue_length - Maximum number of messages to hold in the queue. Once the max is reached new messages will be denied. The idea is to allow caching of messages if Azure is unreachable.
- enable_send_log - Enable logging the relayed messages. Tracks from, to and subject only. Future state may allow for API access to this log, or writing to a file.
- retain_log_days = number of days to store the send log for (retained in RAM currently)
- send_queue_max_age - Max time a message will remain in the queue before it is discareded
- send_timeout - Timeout for sending a message to Azure
- message_retry - Maximum number of times a message can be retried before it is discarded.
- message_retry_delay - Amount of time the message is held for after a failure to send before it is retried.

### [server] section

The [server] section includes options to manage the service itself. Presently only two options are available:

    [server]
    server_restart_per_hour = 5
    server_restart_email = admin@yourdomain.com

- server_restart_per_hour - specifies a number of times the service will resetart after a critical failure before ending.  Default is 5 within an hour.
- server_restart_email - Email address to send a notification to after a restart occurs with details of the failure.

## Running from the CLI

The azure_smtp_relay module is also designed to use command line parameters either in addition or in place of the TOML file. Azure credentials may be passed via command line parameter, however it is recommended to use the TOML file for security reasons.  The following is an example of running from the CLI:

NOTE: Make sure to create a venv and install the require packages from the requirements.txt file.

    (venv) $ python3 -m azure_smtp_relay --help
    usage: python3 -m azure_smtp_relay [-h] [--address ADDRESS] [--port PORT] [--from-address FROM_ADDRESS] [--domains DOMAINS] [--subnets SUBNETS] [--log-level LOG_LEVEL] [--max-queue-length MAX_QUEUE_LENGTH]
                                   [--enable-send-log ENABLE_SEND_LOG] [--retain-log-days RETAIN_LOG_DAYS] [--send-queue-max-age SEND_QUEUE_MAX_AGE] [--send-timeout SEND_TIMEOUT] [--message-retry MESSAGE_RETRY]
                                   [--message-retry-delay MESSAGE_RETRY_DELAY] [--server-restart-per-hour SERVER_RESTART_PER_HOUR] [--server-restart-email SERVER_RESTART_EMAIL] [--endpoint ENDPOINT] [--key KEY]
                                   [--tenant-id TENANT_ID] [--client-id CLIENT_ID] [--client-secret CLIENT_SECRET] [--config CONFIG] [--print-version]

    Python SMTP service using aiosmtpd that relay's through Azure Email Communication Service

    options:
      -h, --help            show this help message and exit
      --address ADDRESS     [relay] (DEFAULT: 0.0.0.0) IP address to listen on. By default uses 0.0.0.0 (all addresses)
      --port PORT           [relay] (DEFAULT: 10025) TCP port number to listen on for incoming SMTP traffic. By default uses port 25.
      --from-address FROM_ADDRESS
                            [relay] Email address to use as From address. Must be authorized in Azure communication service.
      --domains DOMAINS     [relay] Domains to accept email for. Domains should be a comma separated list. i.e. none.com,onmicrosoft.com
      --subnets SUBNETS     [relay] Subnets that should be allowed to relay email. Subnets should be a comma separated list. i.e. 192.168.0.0/16,10.0.0.0/8
      --log-level LOG_LEVEL
                            [relay] Logging level for the service. Defaults to INFO.
      --max-queue-length MAX_QUEUE_LENGTH
                            [relay] (DEFAULT: 100) Maximum number of messages to retain in the queue before discarding.
      --enable-send-log ENABLE_SEND_LOG
                            [relay] (DEFAULT: True) Enable the send log.
      --retain-log-days RETAIN_LOG_DAYS
                            [relay] (DEFAULT: 72) Number of days to retain log data
      --send-queue-max-age SEND_QUEUE_MAX_AGE
                            [relay] (DEFAULT: 43200) 'Maximum number of seconds to hold a message in the queue.
      --send-timeout SEND_TIMEOUT
                            [relay] (DEFAULT: 30) Timeout for sending to the Azure communication service.
      --message-retry MESSAGE_RETRY
                            [relay] (DEFAULT: 3) Number of times to retry a message before discarding.
      --message-retry-delay MESSAGE_RETRY_DELAY
                            [relay] (DEFAULT: 3600) Number of seconds before retrying a message.
      --server-restart-per-hour SERVER_RESTART_PER_HOUR
                            [server] (DEFAULT: 5) Maximum number of times to attempt restarting the server if a failure occurs.
      --server-restart-email SERVER_RESTART_EMAIL
                            [server] Email address to send a report to after a server restarts after a failure.
      --endpoint ENDPOINT   [azure] Azure Communication Endpoint URL. See README.md for help finding.
      --key KEY             [azure] Azure Key to use for authentication. Not required if using service principal. See README.md for help finding.
      --tenant-id TENANT_ID
                            [azure] Azure Tenant ID. Only required when using a service principal. See README.md for help finding.
      --client-id CLIENT_ID
                            [azure] Azure client ID (unique ID of service principal). See README.md for help finding.
      --client-secret CLIENT_SECRET
                            [azure] Azure client secret generated for the service principal. See README.md for help generating.
      --config CONFIG, -c CONFIG
                            JSON config file to load. See README.md file for contents.
      --print-version, -vv  Print the current version and quit.
    (venv) $ 