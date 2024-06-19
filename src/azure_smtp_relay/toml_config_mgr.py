# pylint: disable=consider-using-enumerate,consider-using-dict-items
'''
The toml_config_manager.py file contains a collection of classes and functions designed for 
handling configuration management, specifically for configurations stored in TOML (Tom's 
Obvious Minimal Language) format. 

The intent is to provide a simple class that can be used to load or store configuration
in the TOML format.  The class acts in conjuntion with argparser to allow for CLI input or
config file input with consistent naming, types and ranges.

TomlConfigMgr Class:
Serves as a configuration manager for handling TOML configuration files.
Manages configurations divided into sections with keys and associated settings.
Provides methods for loading configurations from TOML files, updating configurations, retrieving values, and handling required parameters.
Supports updating or creating an argparse.ArgumentParser with configuration parameters.

ip Class:
Represents an IP address.
Utilizes the ipcalc module for IP address handling.
Provides a string representation of the IP object.

network Class:
Represents an IP network.
Utilizes the ipcalc module for network handling.
Provides a string representation of the Network object.

email Class:
Represents an email address.
Validates the provided email address using the validators module.
Provides a string representation of the Email object.

domain Class:
Represents a domain.
Validates the provided domain name using the validators module.
Provides a string representation of the Domain object.

url Class:
Represents a URL.
Validates the provided URL using the validators module.
Provides a string representation of the URL object.


'''
import configparser
import argparse
import ipcalc
import validators
import os

class ip:
    """
    Represents an IP address.

    Attributes:
        ip (ipcalc.IP): IP object.

    Methods:
        __init__(self, address: str): Constructor to initialize the ip object.
        __str__(self): String representation of the IP object.
    """
    def __init__(self, address:str):
        """
        Constructor to initialize the ip object.

        Args:
            address (str): The IP address.

        Returns:
            None
        """
        self.ip = ipcalc.IP(address)

    def __str__(self):
        """
        String representation of the IP object.

        Returns:
            str: String representation of the IP object.
        """
        return str(self.ip)

class network:
    """
    Represents an IP network.

    Attributes:
        network (ipcalc.Network): Network object.

    Methods:
        __init__(self, network_cidr: str): Constructor to initialize the network object.
        __str__(self): String representation of the Network object.
    """
    def __init__(self, network_cidr:str):
        """
        Constructor to initialize the network object.

        Args:
            network_cidr (str): The network CIDR.

        Returns:
            None
        """
        self.network = ipcalc.Network(network_cidr)

    def __str__(self):
        """
        String representation of the Network object.

        Returns:
            str: String representation of the Network object.
        """
        return str(self.network)

class email:
    """
    Represents an email address.

    Attributes:
        email (str): Email address.

    Methods:
        __init__(self, email_addr: str): Constructor to initialize the email object.
        __str__(self): String representation of the Email object.
    """
    def __init__(self, email_addr:str):
        """
        Constructor to initialize the email object.

        Args:
            email_addr (str): The email address.

        Raises:
            ValueError: If the provided email address is not valid.

        Returns:
            None
        """
        if not validators.email(email_addr):
            raise ValueError(f"Email '{email_addr}' is not valid.")
        self.email = email_addr

    def __str__(self):
        """
        String representation of the Email object.

        Returns:
            str: String representation of the Email object.
        """
        return self.email

class domain:
    """
    Represents a domain.

    Attributes:
        domain (str): Domain name.

    Methods:
        __init__(self, domain_name: str): Constructor to initialize the domain object.
        __str__(self): String representation of the Domain object.
    """
    def __init__(self, domain_name:str):
        """
        Constructor to initialize the domain object.

        Args:
            domain_name (str): The domain name.

        Raises:
            ValueError: If the provided domain name is not valid.

        Returns:
            None
        """
        if not validators.domain(domain_name):
            raise ValueError(f"Domain '{domain_name}' is not valid.")
        self.domain = domain_name

    def __str__(self):
        """
        String representation of the Domain object.

        Returns:
            str: String representation of the Domain object.
        """
        return self.domain

class url:
    """
    Represents a URL.

    Attributes:
        url (str): URL string.

    Methods:
        __init__(self, url_string: str): Constructor to initialize the URL object.
        __str__(self): String representation of the URL object.
    """
    def __init__(self, url_string:str):
        """
        Constructor to initialize the URL object.

        Args:
            url_string (str): The URL string.

        Raises:
            ValueError: If the provided URL is not valid.

        Returns:
            None
        """
        if not validators.url(url_string):
            raise ValueError(f"URL '{url_string}' is not valid.")
        self.url = url_string

    def __str__(self):
        """
        String representation of the URL object.

        Returns:
            str: String representation of the URL object.
        """
        return self.url


# Designate classes that should be cast to a string when returning
CAST_TO_STR = (ip, network, email, domain, url)


class TomlConfigMgr:
    """
    Configuration manager for handling TOML configuration files.

    Attributes:
        _config (dict): Dictionary containing configuration specifications.
        _toml_config (configparser.ConfigParser): TOML configuration parser.

    Methods:
        __init__(self, **kwargs): Constructor to initialize the TomlConfigMgr object.
        load_toml(self, filename: str): Load the configuration from a TOML config file.
        update(self, section: str, key: str, value): Update the config for a specific entry after verifying against the configured requirements.
        get(self, section: str, key: str): Return the value for a specific key.
        required_ok(self) -> bool: Return True if all required values are set.
        required_parameters_missing(self) -> dict: Return a dictionary of required parameters that are not yet set.
        sections(self) -> list: Return a list of the config sections.
        section_keys(self, section: str) -> list: Return a list of keys in a specific section.
        config(self, section=None) -> dict: Return the config from a specified section, if no section is given then all config is returned.
        update_argparser(self, parser=None) -> argparse.ArgumentParser: Update or create an ArgumentParser with configuration parameters.
    """
    def __init__(self, **kwargs):
        ''' Take a keyword args as section names. Section should be a dict of values. Each value should be a dict with the
            following values:
                type: (required) value type or list of types, support any builtin Python type plus 'ip', 'network', 'email', 'url', 'domain'
                list_type: (optional) if type is a list, what types are supported (can be a single type or list of types)
                default: (optional) Default value if none has been provided
                separators: (optional) Separators to use if a list.  Default is "," and "\n"
                required: (optional) Designate that a value is required to be provided (not necessary if a default is provided)
                valid_values: (optional) List of valid values that can be accepted. If type is a list, checks each item in the list.
                help: (optional) Printable info for output
                '''
        self._config = {}
        self._toml_config = None
        for key, item in kwargs.items():
            self._config[key] = item

    def load_toml(self, filename:str):
        """
        Load the configuration from a TOML config file.

        Args:
            filename (str): The path to the TOML config file.

        Returns:
            None

        Raises:
            FileNotFoundError - If passed file not present
        """
        if not os.path.isfile(filename):
            raise FileNotFoundError(f"File '{filename}' not found!")
        self._toml_config = configparser.ConfigParser()
        self._toml_config.read(filename)
        for section in self._toml_config.sections():
            for key in self._toml_config[section]:
                self.update(section, key, self._toml_config[section][key])

    def update(self, section:str, key:str, value):
        """
        Update the config for a specific entry after verifying against the configured requirements.

        Args:
            section (str): The section name.
            key (str): The key within the section.
            value: The value to set.

        Returns:
            None
        """
        # remove '[section]-' from key (account for 'prepend_section' option when creating argparser)
        key = key.replace(section + '-', '')
        if section not in self._config:
            raise KeyError(f"Section '{section}' not present in config!")
        if key not in self._config[section]:
            raise KeyError(f"Section '{section}' does not contain a key '{key}'!")
        if value is None:
            return
        # remove extra quotes from value if present (artifact of how TOML configparse library works)
        value = str(value).strip('"').strip("'").strip()

        # Verify value type matches
        if self._config[section][key]['type'] == list:
            # if a list, need to split it and check list types if provided
            split_value = [value.replace('[', '').replace(']', '')]
            x_pos = 0
            for separator in self._config[section][key].get('separators', [',', '\n']):
                while x_pos < len(split_value):
                    if separator in split_value[x_pos]:
                        # split the value in place
                        split_value = (split_value[0:x_pos-1] if x_pos > 0 else []) + split_value[x_pos].split(separator) + (split_value[x_pos+1:] if x_pos < len(split_value) else [])
                    else:
                        x_pos += 1
            # attempt to recast each value
            for x in range(len(split_value)):
                split_value[x] = cast_type(self._config[section][key].get('list_type', str), split_value[x])
            self._config[section][key]['value'] = split_value
        else:
            self._config[section][key]['value'] = cast_type(self._config[section][key]['type'], value)

    def get(self, section:str, key:str):
        """
        Return the value for a specific key.

        Args:
            section (str): The section name.
            key (str): The key within the section.

        Returns:
            The value associated with the key.
        """
        value = self._config[section][key].get('value', self._config[section][key].get('default', None))
        # Need to recast to a string if one of the special classes
        if isinstance(value, CAST_TO_STR):
            return str(value)
        return value

    @property
    def required_ok(self):
        """
        Return True if all required values are set.

        Returns:
            bool: True if all required values are set, False otherwise.
        """
        for section in self._config:
            for settings in self._config[section].values():
                if settings.get('required', False) and (settings.get('value', None) is None and settings.get('default') is None):
                    return False
        return True

    @property
    def required_parameters_missing(self):
        """
        Return a dictionary of required parameters that are not yet set.

        Returns:
            dict: Dictionary containing missing required parameters.
        """
        missing_params = {}
        for section in self._config:
            for key, settings in self._config[section].items():
                if settings.get('required', False) and (settings.get('value', None) is None and settings.get('default') is None):
                    if section not in missing_params:
                        missing_params[section] = {}
                    missing_params[section] = self._config[section][key]
        return missing_params

    def sections(self) -> list:
        """
        Return a list of the config sections.

        Returns:
            list: List of section names.
        """
        return list(self._config.keys())

    def section_keys(self, section:str) -> list:
        """
        Return a list of keys in a specific section.

        Args:
            section (str): The section name.

        Returns:
            list: List of key names within the specified section.
        """
        return list(self._config[section].keys())

    def config(self, section=None) -> dict:
        """
        Return the config from a specified section, if no section is given then all config is returned.

        Args:
            section (str, optional): The section name. Defaults to None.

        Returns:
            dict: Dictionary containing configuration values.
        """
        if self.required_ok:
            config = {
                section:{
                    key:self.get(section, key) for key in self._config[section].keys()
                } for section in self._config.keys()
            }
            if section is None:
                return config
            else:
                return config[section]
        raise ValueError(f"Required configuration has not been provided. Missing values: {self.required_parameters_missing}")

    def update_argparser(self, parser=None, prepend_sections=False) -> argparse.ArgumentParser:
        """
        Update or create an ArgumentParser with configuration parameters.

        Args:
            parser (argparse.ArgumentParser, optional): The ArgumentParser object to update. Defaults to None.
            prepend_sections (Bool, optional): If True, section names are prepended to variable names

        Returns:
            argparse.ArgumentParser: Updated or newly created ArgumentParser object.
        """
        if parser is None:
            parser = argparse.ArgumentParser()
        for section in self._config.keys():
            for key, settings in self._config[section].items():
                parser.add_argument(f"--{section.replace('_', '-') + '-' if prepend_sections else ''}{key.replace('_','-')}",
                                    default=settings.get('default', None),
                                    help=f"[{section}] " + (f"(DEFAULT: {settings.get('default', None)}) " if settings.get('default', None) is not None else '') + str(settings.get('help', '')))
        return parser


def cast_type(types, value):
    """
    Check a value against a single or list of types.

    Args:
        types: The type or list of types to check against.
        value: The value to check.

    Returns:
        The casted value if successful.

    Raises:
        ValueError: If the value cannot be cast to the specified type(s).
    """
    if not isinstance(types, list):
        types = [types]
    for x in types:
        try:
            return x(value)
        except ValueError:
            pass
    raise ValueError(f"Value '{value}' cannot be cast to type(s): {types}")
