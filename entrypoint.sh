#!/bin/bash

# specify a lower security level in modern ubuntu for old DH key
# no idea why this isn't working in the dockerfile...
ln -sf /app/deploy/openssl.cnf /etc/ssl/openssl.cnf

echo "Character name: ${PYLANTHIA_CHARACTER:?You must specify a PYLANTHIA_CHARACTER: the character to play.}"

#cd /pylanthia && pipenv sync && pipenv run python3 pylanthia.py
cd /app && pyenv exec pipenv run python3 pylanthia.py -c ${PYLANTHIA_CHARACTER}
