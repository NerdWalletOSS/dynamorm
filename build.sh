#!/bin/bash

set -eux

SERIALIZATION_PKG=${SERIALIZATION_PKG:-marshmallow}
TRAVIS_PULL_REQUEST=${TRAVIS_PULL_REQUEST:-nope}

pip install -e .
pip install codecov pytest
pip install ${SERIALIZATION_PKG}

SERIALIZATION_PKG=${SERIALIZATION_PKG} coverage run --source=dynamorm setup.py test

if [ "${TRAVIS_PULL_REQUEST}" != "false" ]; then
    if [ -z "`git diff origin/master setup.py | grep '\+.*version='`" ]; then
        printf "\n\n\n\nBump version in setup.py!\n\n\n\n"
        exit 1
    fi
fi

if [ "${TRAVIS_PULL_REQUEST}" = "false" ] && [ ! -z "${GH_TOKEN}" ]; then
    pip install travis-sphinx
    travis-sphinx --source=docs build
    travis-sphinx deploy
fi
