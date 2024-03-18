import boto3
import torch
from PIL import Image
from facenet_pytorch import MTCNN, InceptionResnetV1
from torchvision import datasets
from torch.utils.data import DataLoader

import time



mtcnn = MTCNN(image_size=240, margin=0, min_face_size=20) # initializing mtcnn for face detection
resnet = InceptionResnetV1(pretrained='vggface2').eval() # initializing resnet for face img to embeding conversion

def face_match(img_path, data_path): # img_path= location of photo, data_path= location of data.pt
    # getting embedding matrix of the given img
    # print(img_path)
    img = Image.open(img_path)
    face, prob = mtcnn(img, return_prob=True) # returns cropped face and probability
    emb = resnet(face.unsqueeze(0)).detach() # detech is to make required gradient false

    saved_data = torch.load('/home/ubuntu/data.pt') # loading data.pt file
    embedding_list = saved_data[0] # getting embedding data
    name_list = saved_data[1] # getting list of names
    dist_list = [] # list of matched distances, minimum distance is used to identify the person

    for idx, emb_db in enumerate(embedding_list):
        dist = torch.dist(emb, emb_db).item()
        dist_list.append(dist)

    idx_min = dist_list.index(min(dist_list))
    return (name_list[idx_min], min(dist_list))




sqs_client = boto3.client('sqs', region_name = 'us-east-1')

req_queue_url = "https://sqs.us-east-1.amazonaws.com/905418127621/1229935683-req-queue"
res_queue_url = "https://sqs.us-east-1.amazonaws.com/905418127621/1229935683-res-queue"

s3_client = boto3.client('s3', region_name = 'us-east-1')
in_bucket_name = '1229935683-in-bucket'
out_bucket_name = '1229935683-out-bucket'


static_path = "../dataset/face_images_1000/"
while True:
    response = sqs_client.receive_message(
    QueueUrl = req_queue_url,
    MaxNumberOfMessages = 1,
    WaitTimeSeconds = 20,
    MessageAttributeNames = ["All"],
    VisibilityTimeout=20
)

    if 'Messages' in response:
        message = response['Messages'][0]
        coorelation_Id= message["MessageAttributes"]["CorrelationId"]["StringValue"]
        # print(coorelation_Id)
        msg_body = message['Body']
        # print(msg_body)
        response = s3_client.get_object(
            Bucket=in_bucket_name,
            Key=msg_body
        )
        result = face_match(response['Body'], '/home/ubuntu/data.pt')
        # print(result[0], "result..........................")
        
        out_img_name = msg_body.split('.')[0]
        s3_client.put_object(
            Bucket=out_bucket_name,
            Key=out_img_name,
            Body=result[0]
        )
        sqs_client.send_message(
            QueueUrl = res_queue_url,
            MessageBody = f"{out_img_name}:{result[0]}",
            MessageAttributes = {
                "CorrelationId": {
                "DataType": 'String',
                "StringValue": coorelation_Id
                }
            }
        )
        sqs_client.delete_message(QueueUrl = req_queue_url, ReceiptHandle=message['ReceiptHandle'])
        time.sleep(10) 
    else:
        print("no msg received....")