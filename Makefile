SERIALIZATION_PKG ?= marshmallow
TRAVIS_PULL_REQUEST ?= nope

all: install test docs

test:
	SERIALIZATION_PKG=$(SERIALIZATION_PKG) coverage run --source=dynamorm setup.py test
	if [ "$(TRAVIS_PULL_REQUEST)" != "false" ]; then \
		git diff origin/master setup.py | grep "\+.*version=" || ( \
			printf "\n\n\n\nBump version in setup.py!\n\n\n\n" \
			exit 1 \
		) \
	fi

docs:
	if [ "$(TRAVIS_PULL_REQUEST)" = "false" ] && [ ! -z "$(GH_TOKEN)"]; then \
		pip install travis-sphinx \
		travis-sphinx --source=docs build \
		travis-sphinx deploy \
	fi

install:
	pip install -e .
	pip install codecov pytest
	pip install $(SERIALIZATION_PKG)
