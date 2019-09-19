#!/bin/bash


# may need the .rb before upgrading
# must manually specify the rbw after upgrading
#ruby /lich/lich.rb -s --game=DR -g dr.simutronics.net:4901 &
ruby /lich/lich.rbw -s --game=DR -g dr.simutronics.net:4901 &

sleep 3

cd /pylanthia && pipenv sync && pipenv run python3 pylanthia.py
