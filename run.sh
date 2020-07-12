#!/bin/bash

PYLANTHIA_CONFIG="config.json"

docker-compose run -e PYLANTHIA_CONFIG=${PYLANTHIA_CONFIG} pylanthia
