import json
import uuid
import time
import boto3
import botocore
import threading

from flask import Flask, request


app = Flask(__name__)

sqs_client = boto3.client(
    'sqs',
    region_name='us-east-1'
)
s3_client = boto3.client('s3')


def send_message(queue_url, message_body):
    try:
        response = sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body)
        )

    except Exception as e:
        print(e)

    return response

message_dict = {}

def receive_messages():
    """
    Receive messages in a single request from an SQS queue.

    :param queue_url: The queue from which to receive messages.
    :return: The ReceiptHandle of Message objects received, response body
    """
    try:
        resp_queue_url = "https://sqs.us-east-1.amazonaws.com/767397819602/1229059834-resp-queue"
        while True:
            messages = sqs_client.receive_message(
                QueueUrl = resp_queue_url,
                MaxNumberOfMessages=1,
                VisibilityTimeout=20,
            )
        
            for msg in messages.get("Messages", []):
                received_dict = json.loads(msg["Body"])
                print("*"*10, received_dict)
                message_dict[received_dict["id"]] = received_dict
                sqs_client.delete_message(
                    QueueUrl=resp_queue_url,
                    ReceiptHandle=msg["ReceiptHandle"]
                )
            time.sleep(10)
    
    except botocore.exceptions.ClientError as error:
        print("Couldn't receive messages from queue")
        raise error


@app.route('/', methods=['POST'])
def capture_payload():
    req_queue_url = "https://sqs.us-east-1.amazonaws.com/767397819602/1229059834-req-queue"        
    resp_queue_url = "https://sqs.us-east-1.amazonaws.com/767397819602/1229059834-resp-queue"

    try:
        # image_encoded = base64.b64encode(request.files["inputFile"].read()).decode('utf-8')
        
        # storing file in S3 so that APP tier can retrieve it
        request_file = request.files["inputFile"]
        s3_client.put_object(Body=request_file, Bucket="1229059834-in-bucket", Key=request_file.filename)

        unique_id = uuid.uuid4().hex
        message_body = {
            "fileName": request_file.filename,
            "id": unique_id
            # "fileContent": image_encoded
        }

        response = send_message(req_queue_url, message_body)
        while True:
            if unique_id in message_dict:
                # delete the msg from queue
                response_json = message_dict[unique_id]
                return response_json["response"], 200
            time.sleep(5)
                # return msg["ReceiptHandle"], received_dict
            # if receipt_handle:
            #     if resp_message["id"] == unique_id:
            #         # delete the msg from queue
            #         sqs_client.delete_message(
            #             QueueUrl=resp_queue_url,
            #             ReceiptHandle=receipt_handle
            #         )
            #         return resp_message["response"], 200

    except Exception as e:
        print(e)

    return "", 200


if __name__ == '_main_':
    # print(lookup_map)
    polling_thread = threading.Thread(target=receive_messages)
    polling_thread.daemon = True
    polling_thread.start()
    app.run(host='0.0.0.0', port=8000, threaded=True)