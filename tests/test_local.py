import os
import socket
import time

from dynamorm.local import DynamoLocal

DYNAMO_CONN_RETRIES = 10
DYNAMO_CONN_SLEEP = 1


def test_shutdown_local_dynamo():
    dynamo_local_dir = os.environ.get('DYNAMO_LOCAL', 'build/dynamo-local')
    dynamo_local = DynamoLocal(dynamo_local_dir)
    connected = -1
    for _ in range(DYNAMO_CONN_RETRIES):
        connected = _connect_to_port(dynamo_local.port)
        if connected == 0:
            break
        time.sleep(DYNAMO_CONN_SLEEP)
    assert connected == 0
    dynamo_local.shutdown()
    assert dynamo_local.dynamo_proc is None
    assert _connect_to_port(dynamo_local.port) != 0


def _connect_to_port(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = sock.connect_ex(('127.0.0.1', port))
    finally:
        sock.close()
    return result
