import atexit
import logging
import os
import random
import socket
import subprocess
import tarfile
import tempfile

try:
    from urllib import urlretrieve
except ImportError:
    from urllib.request import urlretrieve

log = logging.getLogger(__name__)


class DynamoLocal(object):
    """
    Spins up a local dynamo instance. This should ONLY be used for testing!! This instance
    will register the cleanup method ``shutdown`` with the ``atexit`` module.
    """
    def __init__(self, dynamo_dir, port=None):
        self.port = port or get_random_port()
        if not os.path.isdir(dynamo_dir):
            log.info("Creating dynamo_local_dir: {0}".format(dynamo_dir))
            assert not os.path.exists(dynamo_dir)
            os.makedirs(dynamo_dir, 0o755)

        if not os.path.exists(os.path.join(dynamo_dir, 'DynamoDBLocal.jar')):
            temp_fd, temp_file = tempfile.mkstemp()
            os.close(temp_fd)
            log.info("Downloading dynamo local to: {0}".format(temp_file))
            urlretrieve(
                'http://dynamodb-local.s3-website-us-west-2.amazonaws.com/dynamodb_local_latest.tar.gz',
                temp_file
            )

            log.info("Extracting dynamo local...")
            archive = tarfile.open(temp_file, 'r:gz')
            archive.extractall(dynamo_dir)
            archive.close()

            os.unlink(temp_file)

        log.info("Running dynamo from {dir} on port {port}".format(
            dir=dynamo_dir,
            port=self.port
        ))
        self.dynamo_proc = subprocess.Popen(
            (
                'java',
                '-Djava.library.path=./DynamoDBLocal_lib',
                '-jar', 'DynamoDBLocal.jar',
                '-sharedDb',
                '-inMemory',
                '-port', str(self.port)
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=dynamo_dir
        )
        atexit.register(self.shutdown)

    def shutdown(self):
        if self.dynamo_proc:
            self.dynamo_proc.terminate()
            self.dynamo_proc.wait()
        self.dynamo_proc = None


def get_random_port():
    """Find a random port that appears to be available"""
    random_port = random.randint(25000, 55000)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = sock.connect_ex(('127.0.0.1', random_port))
    finally:
        sock.close()
    if result == 0:
        return get_random_port()
    return random_port
