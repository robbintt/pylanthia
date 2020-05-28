#!/bin/bash

# specify a lower security level in modern ubuntu for old DH key
# no idea why this isn't working in the dockerfile...
ln -sf /app/deploy/openssl.cnf /etc/ssl/openssl.cnf

# this manages the case in which lich is installed as .rb but not updated (to .rbw)
LICH_PATH=$([[ -f "/lich/lich.rbw" ]] && echo "/lich/lich.rbw" || echo "/lich/lich.rb")
echo "Using lich path: $LICH_PATH"

LICH_PORT=${LICH_PORT:-4901}
# these need to come from config
ruby $LICH_PATH -s --game=DR -g dr.simutronics.net:$LICH_PORT &

# is this even being caused by lich not booting up or is it a different network miss of some sort
sleep 1 # 2 was too low, 3 is too low as well, 4 is too low... maybe i should wait for some input

#cd /pylanthia && pipenv sync && pipenv run python3 pylanthia.py
cd /app && pyenv exec pipenv run python3 pylanthia.py
