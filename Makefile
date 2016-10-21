SERIALIZATION_PKG ?= marshmallow

all: install test docs

test:
	SERIALIZATION_PKG=$(SERIALIZATION_PKG) coverage run --source=dynamorm setup.py test

	ifneq ("$(TRAVIS_PULL_REQUEST)", "false")
		git diff origin/master setup.py | grep "\+.*version=" || (echo "Bump version in setup.py!"; exit 1)
	endif

docs:
	ifeq ("$(TRAVIS_PULL_REQUEST)", "false")
		ifdef GH_TOKEN
			pip install travis-sphinx
			travis-sphinx --source=docs build
			travis-sphinx deploy
		endif
	endif

install:
	pip install -e .
	pip install codecov pytest
	pip install $(SERIALIZATION_PKG)
