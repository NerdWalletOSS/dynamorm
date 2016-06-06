import random
import socket

import pytest

from dynamallow import MarshModel

from marshmallow import fields


@pytest.fixture(scope='session')
def TestModel():
    """Provides a test model"""

    class TestModel(MarshModel):
        class Table:
            name = 'peanut-butter'
            hash_key = 'foo'
            range_key = 'bar'
            read = 1
            write = 1

        class Schema:
            foo = fields.String(required=True)
            bar = fields.String(required=True)
            baz = fields.String()
            count = fields.Integer()

        def business_logic(self):
            return 'http://art.lawver.net/funny/internet.jpg?foo={}&bar={}'.format(
                self.foo,
                self.bar
            )

    return TestModel

@pytest.fixture(scope='function')
def TestModel_table(request, TestModel):
    """Used with TestModel, creates and deletes the table around the test"""
    TestModel.create_table()
    request.addfinalizer(TestModel.delete_table)


@pytest.fixture(scope='session')
def dynamo_local(request, TestModel):
    """Connect to a local dynamo instance"""
    # XXX TODO: check for DYNAMO_LOCAL in os.environ, if it doesn't exist then download the latest copy of dynamo and
    # run it out of our build/ dir

    def get_random_port():
        """Find a random port that appears to be available"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        random_port = random.randint(35000, 45000)
        result = sock.connect_ex(('127.0.0.1', random_port))
        sock.close()
        if result == 0:
            return get_random_port()
        return random_port

    random_port = get_random_port()

    # XXX TODO: start dynamo on a random port with inMemory in a new subprocess

    def shutdown_dynamo():
        # XXX TODO: shutdown dynamo here
        pass

    request.addfinalizer(shutdown_dynamo)

    TestModel.get_resource(
        aws_access_key_id="anything",
        aws_secret_access_key="anything",
        region_name="us-west-2",
        endpoint_url='http://localhost:8000'
    )

    return random_port
