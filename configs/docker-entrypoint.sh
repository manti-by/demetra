#!/bin/sh
set -e

export HOME=/home/demetra

if [ ! -e /home/demetra/.home-ready ]; then
    chown demetra:demetra /home/demetra
    find /home/demetra -mindepth 1 \
        \( -name .ssh -o -name .gnupg -o -name .gitconfig -o -name .git-credentials \) -prune \
        -o -exec chown demetra:demetra {} +
    touch /home/demetra/.home-ready
    chown demetra:demetra /home/demetra/.home-ready
fi

exec setpriv --reuid=demetra --regid=demetra --init-groups "$@"
