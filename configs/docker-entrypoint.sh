#!/bin/sh
set -e

export HOME=/home/demetra

providers_config=/home/demetra/.config/opencode/providers.json
opencode_config=/home/demetra/.config/opencode/opencode.json
if [ -f "$providers_config" ]; then
    python /usr/local/bin/derive-opencode-config.py "$providers_config" "$opencode_config"
    if [ "$(id -u)" = "0" ]; then
        chown demetra:demetra "$opencode_config"
    fi
fi

if [ "$(id -u)" = "0" ]; then
    if [ ! -e /home/demetra/.home-ready ]; then
        chown demetra:demetra /home/demetra
        find /home/demetra -mindepth 1 \
            \( -path /home/demetra/.config/gh/hosts.yml \
               -o -path /home/demetra/.config/opencode/opencode.json \
               -o -path /home/demetra/.local/share/opencode/auth.json \
               -o -name .ssh -o -name .gnupg -o -name .gitconfig -o -name .git-credentials \) -prune \
            -o -exec chown -h demetra:demetra {} +
        touch /home/demetra/.home-ready
        chown demetra:demetra /home/demetra/.home-ready
    fi

    mkdir -p /home/demetra/.config/gh /home/demetra/.local/share/opencode
    chown demetra:demetra /home/demetra/.config/gh /home/demetra/.local/share/opencode

    exec setpriv --reuid=demetra --regid=demetra --init-groups "$@"
fi

exec "$@"
