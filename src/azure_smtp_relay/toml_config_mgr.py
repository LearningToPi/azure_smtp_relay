# pylint: disable=consider-using-enumerate,consider-using-dict-items
import configparser
import argparse
import ipcalc
import validators


class ip:
    def __init__(self, address:str):
        self.ip = ipcalc.IP(address)

    def __str__(self):
        return str(self.ip)
    
class network:
    def __init__(self, network_cidr:str):
        self.network = ipcalc.Network(network_cidr)

    def __str__(self):
        return str(self.network)
    
class email:
    def __init__(self, email_addr:str):
        if not validators.email(email_addr):
            raise ValueError(f"Email '{email_addr}' is not valid.")
        self.email = email_addr

    def __str__(self):
        return self.email
    
class domain:
    def __init__(self, domain_name:str):
        if not validators.domain(domain_name):
            raise ValueError(f"Domain '{domain_name}' is not valid.")
        self.domain = domain_name

    def __str__(self):
        return self.domain

class url:
    def __init__(self, url_string:str):
        if not validators.url(url_string):
            raise ValueError(f"URL '{url_string}' is not valid.")
        self.url = url_string
        
    def __str__(self):
        return self.url


class TomlConfigMgr:
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
        ''' Load the configuration from a TOML config file '''
        self._toml_config = configparser.ConfigParser()
        self._toml_config.read(filename)
        for section in self._toml_config.sections():
            for key in self._toml_config[section]:
                self.update(section, key, self._toml_config[section][key])

    def update(self, section:str, key:str, value):
        ''' Update the config for a specific entry after verifying against the configured requirements '''
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
        ''' Return the value for a specific key '''
        return self._config[section][key].get('value', self._config[section][key].get('default', None))

    @property
    def required_ok(self):
        ''' Return True if all required values are set '''
        for section in self._config:
            for settings in self._config[section].values():
                if settings.get('required', False) and (settings.get('value', None) is None and settings.get('default') is None):
                    return False
        return True

    @property
    def required_parameters_missing(self):
        ''' Return a list of required parameters that are not yet set:
            [
                {'section': ...,
                 '[key]': {}}
            ] '''
        missing_params = {}
        for section in self._config:
            for key, settings in self._config[section].items():
                if settings.get('required', False) and (settings.get('value', None) is None and settings.get('default') is None):
                    if section not in missing_params:
                        missing_params[section] = {}
                    missing_params[section] = self._config[section][key]
        return missing_params
    
    def sections(self) -> list:
        ''' Return a list of the config sections '''
        return list(self._config.keys())
    
    def section_keys(self, section:str) -> list:
        ''' return a list of keys in a specific section '''
        return list(self._config[section].keys())

    def config(self, section=None) -> dict:
        ''' Return the config from a specified section, if no section is given then all config is returned '''
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
    
    def update_argparser(self, parser=None) -> argparse.ArgumentParser:
        ''' If no ArgumentParser is passed, create one and return it after populating, otherwise update the provided parser '''
        if parser is None:
            parser = argparse.ArgumentParser()
        for section in self._config.keys():
            for key, settings in self._config[section].items():
                parser.add_argument(f"--{key.replace('_','-')}",
                                    default=settings.get('default', None),
                                    help=f"[{section}] " + (f"(DEFAULT: {settings.get('default', None)}) " if settings.get('default', None) is not None else '') + str(settings.get('help', '')))
        return parser


def cast_type(types, value):
    ''' Cehck a value against a single or list of types '''
    if not isinstance(types, list):
        types = [types]
    for x in types:
        try:
            return x(value)
        except ValueError:
            pass
    raise ValueError(f"Value '{value}' cannot be cast to type(s): {types}")
