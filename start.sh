#!/bin/bash

# no idea why this isn't working in the dockerfile...
ln -sf /pylanthia/deploy/openssl.cnf /etc/ssl/openssl.cnf

LICH_PATH=$([[ -f "/lich/lich.rbw" ]] && echo "/lich/lich.rbw" || echo "/lich/lich.rb")
echo "Using lich path: $LICH_PATH"

# may need the .rb before upgrading
# must manually specify the rbw after upgrading
ruby $LICH_PATH -s --game=DR -g dr.simutronics.net:4901 &

sleep 2

cd /pylanthia && pipenv sync && pipenv run python3 pylanthia.py
