#!/bin/bash

# this manages the case in which lich is installed as .rb but not updated (to .rbw)
LICH_PATH=$([[ -f "/lich/lich.rbw" ]] && echo "/lich/lich.rbw" || echo "/lich/lich.rb")
echo "Using lich path: $LICH_PATH"

LICH_PORT=${LICH_PORT:-4901}
# these need to come from config
ruby $LICH_PATH -s --game=DR -g dr.simutronics.net:$LICH_PORT &

