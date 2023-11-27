#!/bin/bash
# If a config file named "config.toml" exists in /app, start using the config file
# If no config file, pass command line parameters or use defaults

if test -f /app/config.toml; then
    python3 -m azure_smtp_relay --config /app/config.toml "$@"
else
    python3 -m azure_smtp_relay "$@"
fi
