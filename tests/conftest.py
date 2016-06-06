import logging
import os
import random
import socket
import subprocess
import tarfile
import tempfile
import urllib

import pytest

from dynamallow import MarshModel

from marshmallow import fields

log = logging.getLogger(__name__)


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
    dynamo_local_dir = os.environ.get('DYNAMO_LOCAL', 'build/dynamo-local')

    if not os.path.isdir(dynamo_local_dir):
        log.info("Creating dynamo_local_dir: {}".format(dynamo_local_dir))
        assert not os.path.exists(dynamo_local_dir)
        os.makedirs(dynamo_local_dir, 0755)

    if not os.path.exists(os.path.join(dynamo_local_dir, 'DynamoDBLocal.jar')):
        temp_fd, temp_file = tempfile.mkstemp()
        os.close(temp_fd)
        log.info("Downloading dynamo local to: {}".format(temp_file))
        urllib.urlretrieve(
            'http://dynamodb-local.s3-website-us-west-2.amazonaws.com/dynamodb_local_latest.tar.gz',
            temp_file
        )

        log.info("Extracting dynamo local...")
        archive = tarfile.open(temp_file, 'r:gz')
        archive.extractall(dynamo_local_dir)
        archive.close()

        os.unlink(temp_file)

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

    log.info("Running dynamo from {} on port {}".format(dynamo_local_dir, random_port))

    dynamo_proc = subprocess.Popen(
        (
            'java',
            '-Djava.library.path=./DynamoDBLocal_lib',
            '-jar', 'DynamoDBLocal.jar',
            '-sharedDb',
            '-inMemory',
            '-port', str(random_port)
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=dynamo_local_dir
    )

    def shutdown_dynamo():
        dynamo_proc.terminate()
        dynamo_proc.wait()
    request.addfinalizer(shutdown_dynamo)

    TestModel.get_resource(
        aws_access_key_id="anything",
        aws_secret_access_key="anything",
        region_name="us-west-2",
        endpoint_url='http://localhost:{}'.format(random_port)
    )

    return random_port
