#!/bin/bash

set -eux

SERIALIZATION_PKG=${SERIALIZATION_PKG:-marshmallow}
TRAVIS_PULL_REQUEST=${TRAVIS_PULL_REQUEST:-false}

pip install -e .
pip install codecov pytest pytest-mock
pip install ${SERIALIZATION_PKG}

SERIALIZATION_PKG=${SERIALIZATION_PKG} coverage run --source=dynamorm $(which py.test) -v tests/

if [ "${TRAVIS_PULL_REQUEST}" != "false" ]; then
    if [ -z "`git diff origin/master setup.py | grep '\+.*version='`" ]; then
        printf "\n\n\n\nBump version in setup.py!\n\n\n\n"
        exit 1
    fi
fi

# only build docs on py2.7, non-pr builds
if [ "${TRAVIS_PULL_REQUEST}" = "false" ] && \
   [ "${TRAVIS_PYTHON_VERSION}" = "2.7" ] && \
   [ ! -z "${GH_TOKEN}" ]; then
    pip install travis-sphinx
    travis-sphinx --source=docs build
    travis-sphinx deploy
fi
