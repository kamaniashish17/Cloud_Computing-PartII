from flask import Flask, request
import boto3

app = Flask(__name__)

# image_classification_lookup = pd.read_csv('Classification Results on Face Dataset (1000 images).csv')
# image_classification_lookup.set_index(["Image"], inplace=True)
sqs_client = boto3.client('sqs', region_name='us-east-1')
s3_client = boto3.client('s3')


queue_url = "https://sqs.us-east-1.amazonaws.com/905418127621/1229935683-req-queue"
in_bucket_name = '1229935683-in-bucket'

@app.route("/", methods=["POST"])
def handle_request():
    print("Original Request", request)
    print("Request", request.files)
    file = request.files["inputFile"]
    image_payload = request.files["inputFile"].filename
    print("images ---- ", image_payload)


    msg_body = {
        "file_name" : image_payload
    }

    response= sqs_client.send_message(
        QueueUrl = queue_url,
        MessageBody = str(msg_body)
    )

    s3_client.put_object(
        Bucket=in_bucket_name,
        Key=image_payload,
        Body = file.read()
    )

    print("Message from SQS Req", response)

    return "test", 200
# image_payload + ":" + image_classification_lookup.loc[image_payload]['Results'], 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)