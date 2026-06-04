#!/bin/bash
CURR_DIR="$PWD"

for service in api react rq-dashboard watcher worker
do
    sudo ln -s "$CURR_DIR/services/$service.service" /etc/systemd/system/demetra-$service.service
    sudo systemctl enable demetra-$service.service
    sudo systemctl start demetra-$service.service
done

sudo ln -s "$CURR_DIR/nginx.conf" /etc/nginx/sites-enabled/demetra.manti.by
sudo systemctl restart nginx
