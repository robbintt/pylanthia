#!/bin/bash

# specify a lower security level in modern ubuntu for old DH key
# no idea why this isn't working in the dockerfile...
ln -sf /app/deploy/openssl.cnf /etc/ssl/openssl.cnf

echo "Config file used: ${PYLANTHIA_CONFIG}"

#cd /pylanthia && pipenv sync && pipenv run python3 pylanthia.py
cd /app && pyenv exec pipenv run python3 pylanthia.py
