#!/bin/bash

set +ex

# why not subrepos again? i love subrepos...

git clone https://github.com/matt-lowe/Lich.git lich

git clone https://github.com/robbintt/dr-scripts
cd dr-scripts && git checkout robbintt/main && ./docker_create_symlinks.sh ../lich/scripts
