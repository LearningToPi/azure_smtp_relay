#!/bin/bash
# If a config file named "config.toml" exists in /app, start using the config file
# If no config file, pass command line parameters or use defaults

exec() {
    "$@" &
    pid="$!"
    trap 'kill `pidof python3`' SIGTERM
    wait
}

if test -f /config.toml; then
    exec python3 -m azure_smtp_relay --config /config.toml "$@"
elif test -f /app/config.toml; then
    exec python3 -m azure_smtp_relay --config /app/config.toml "$@"
else
    exec python3 -m azure_smtp_relay "$@"
fi
