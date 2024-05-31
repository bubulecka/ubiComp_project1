# Simple MQTT-based endpoint metadata management client for the Kaa IoT platform.
import itertools
import json
import queue
import random
import signal
import string
import sys
import time

import paho.mqtt.client as mqtt
import serial

KPC_HOST = "mqtt.cloud.kaaiot.com"  # Kaa Cloud plain MQTT host
KPC_PORT = 1883                     # Kaa Cloud plain MQTT port

APPLICATION_VERSION = "cpd0dbic8hds7384b2n0-v1"
ENDPOINT_TOKEN = "token1"

LOCAL_SERIAL_PORT = "COM7"
LOCAL_BAUD = 9600

class MetadataClient:

    def __init__(self, client):
        self.client = client
        self.metadata_by_request_id = {}
        self.global_request_id = itertools.count()
        get_metadata_subscribe_topic = f'kp1/{APPLICATION_VERSION}/epmx/{ENDPOINT_TOKEN}/get/#'
        self.client.message_callback_add(get_metadata_subscribe_topic, self.handle_metadata)

    def handle_metadata(self, client, userdata, message):
        request_id = int(message.topic.split('/')[-2])
        if message.topic.split('/')[-1] == 'status' and request_id in self.metadata_by_request_id:
            print(f'<--- Received metadata response on topic {message.topic}')
            metadata_queue = self.metadata_by_request_id[request_id]
            metadata_queue.put_nowait(message.payload)
        else:
            print(f'<--- Received bad metadata response on topic {message.topic}:\n{str(message.payload.decode("utf-8"))}')

    def get_metadata(self):
        request_id = next(self.global_request_id)
        get_metadata_publish_topic = f'kp1/{APPLICATION_VERSION}/epmx/{ENDPOINT_TOKEN}/get/{request_id}'

        metadata_queue = queue.Queue()
        self.metadata_by_request_id[request_id] = metadata_queue

        print(f'---> Requesting metadata by topic {get_metadata_publish_topic}')
        self.client.publish(topic=get_metadata_publish_topic, payload=json.dumps({}))
        try:
            metadata = metadata_queue.get(True, 5)
            del self.metadata_by_request_id[request_id]
            return str(metadata.decode("utf-8"))
        except queue.Empty:
            print('Timed out waiting for metadata response from server')
            sys.exit()

    def patch_metadata_unconfirmed(self, metadata):
        partial_metadata_udpate_publish_topic = f'kp1/{APPLICATION_VERSION}/epmx/{ENDPOINT_TOKEN}/update/keys'

        print(f'---> Reporting metadata on topic {partial_metadata_udpate_publish_topic}\nwith payload {metadata}')
        self.client.publish(topic=partial_metadata_udpate_publish_topic, payload=metadata)

class DataCollectionClient:

    def __init__(self, client):
        self.client = client
        self.data_collection_topic = f'kp1/{APPLICATION_VERSION}/dcx/{ENDPOINT_TOKEN}/json/15'
        self.lighton = False
        self.switch = False
        self.color = 'r'

        command_turnon_topic = f'kp1/{APPLICATION_VERSION}/cex/{ENDPOINT_TOKEN}/command/turnon/status'
        self.client.message_callback_add(command_turnon_topic, self.handle_turnon_command)
        self.command_turnon_result_topic = f'kp1/{APPLICATION_VERSION}/cex/{ENDPOINT_TOKEN}/result/turnon'

        command_turnoff_topic = f'kp1/{APPLICATION_VERSION}/cex/{ENDPOINT_TOKEN}/command/turnoff/status'
        self.client.message_callback_add(command_turnoff_topic, self.handle_turnoff_command)
        self.command_turnoff_result_topic = f'kp1/{APPLICATION_VERSION}/cex/{ENDPOINT_TOKEN}/result/turnoff'

    def connect_to_server(self):
        print(f'Connecting to Kaa server at {KPC_HOST}:{KPC_PORT} using application version {APPLICATION_VERSION} and endpoint token {ENDPOINT_TOKEN}')
        self.client.connect(KPC_HOST, KPC_PORT, 60)
        print('Successfully connected')

    def disconnect_from_server(self):
        print(f'Disconnecting from Kaa server at {KPC_HOST}:{KPC_PORT}...')
        self.client.loop_stop()
        self.client.disconnect()
        print('Successfully disconnected')
    
    def handle_turnoff_command(self, client, userdata, message):
        print(f'<--- Received "turnoff" command on topic {message.topic}')
        command_result = self.compose_command_result_payload(message)
        print(f'command result {command_result}')
        client.publish(topic=self.command_turnoff_result_topic, payload=command_result)
        self.switch = True
        self.lighton = False

    def handle_turnon_command(self, client, userdata, message):
        print(f'<--- Received "turnon" command on topic {message.topic}')
        command_payload = json.loads(str(message.payload.decode("utf-8")))
        payload_value = command_payload[0]['payload']['color']
        if payload_value in ['r', 'g', 'b']:
            self.color = payload_value
        command_result = self.compose_command_result_payload(message)
        print(f'command result {command_result}')
        client.publish(topic=self.command_turnon_result_topic, payload=command_result)
        self.switch = True
        self.lighton = True

    def compose_command_result_payload(self, message):
        command_payload = json.loads(str(message.payload.decode("utf-8")))
        print(f'command payload: {command_payload}')
        command_result_list = []
        for command in command_payload:
            commandResult = {"id": command['id'], "statusCode": 200, "reasonPhrase": "OK", "payload": "Success"}
            command_result_list.append(commandResult)
        return json.dumps(
            command_result_list
        )
    
    def adjustLight(self, ser):
        if self.switch == True:
            self.switch = False
            if self.lighton:
                ser.write(self.color.encode())
            else:
                ser.write('f'.encode())

# When used with MQTT optionally specify the "Request ID" to subscribe on /status or /error topic to get the operation status. 
#Alternatively subscribe to "kp1/<appversion_name>/dcx/<token>/json/#" to receieve both status and error responses.
def on_message(client, userdata, message):
    print(f'<-- Message received: topic "{message.topic}":\n{str(message.payload.decode("utf-8"))}')

def main():
    # Open serial port
    ser = serial.Serial(LOCAL_SERIAL_PORT, LOCAL_BAUD)

    # Initiate server connection
    client = mqtt.Client(client_id=''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6)))
    data_collection_client = DataCollectionClient(client)
    data_collection_client.connect_to_server()
    client.on_message = on_message
    client.loop_start()

    # Fetch current endpoint metadata attributes
    metadata_client = MetadataClient(client)
    retrieved_metadata = metadata_client.get_metadata()
    print(f'Retrieved metadata from server: {retrieved_metadata}')

    # Send data samples in loop
    package = {}
    listener = SignalListener()
    while listener.keepRunning:

        # check if we need to adjust light
        data_collection_client.adjustLight(ser)

        data = ser.readline().decode().strip()
        if data:
            if ':' in data:
                key, value = data.split(":")
                package[key] = float(value)
        else:
            package['timestamp'] = int(round(time.time() * 1000))
            payload = json.dumps(package)

            result = data_collection_client.client.publish(topic=data_collection_client.data_collection_topic, payload=payload)
            if result.rc != 0:
                print('Server connection lost, attempting to reconnect')
                data_collection_client.connect_to_server()
            else:
                print(f'--> Sent message on topic "{data_collection_client.data_collection_topic}":\n{payload}')
            
            package = {}

    data_collection_client.disconnect_from_server()



class SignalListener:
    keepRunning = True

    def __init__(self):
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

    def stop(self, signum, frame):
        print('Shutting down...')
        self.keepRunning = False


if __name__ == '__main__':
    main()