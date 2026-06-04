#!/bin/bash
CURR_DIR="$PWD"

for service in api react rq-dashboard watcher
do
    sudo ln -s "$CURR_DIR/services/$service.service" /etc/systemd/system/demetra-$service.service
    sudo systemctl enable demetra-$service.service
    sudo systemctl start demetra-$service.service
done

sudo ln -s "$CURR_DIR/services/worker.service" /etc/systemd/system/demetra-worker@.service
sudo systemctl enable demetra-worker.service
sudo systemctl start demetra-worker@{1..4}.service

sudo ln -s "$CURR_DIR/nginx.conf" /etc/nginx/sites-enabled/demetra.manti.by
sudo systemctl restart nginx
