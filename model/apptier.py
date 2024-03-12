import boto3
from flask import Flask, request
import torch
from PIL import Image
from facenet_pytorch import MTCNN, InceptionResnetV1
from torchvision import datasets
from torch.utils.data import DataLoader

import json



mtcnn = MTCNN(image_size=240, margin=0, min_face_size=20) # initializing mtcnn for face detection
resnet = InceptionResnetV1(pretrained='vggface2').eval() # initializing resnet for face img to embeding conversion

def face_match(img_path, data_path): # img_path= location of photo, data_path= location of data.pt
    # getting embedding matrix of the given img
    print(img_path)
    img = Image.open(img_path)
    face, prob = mtcnn(img, return_prob=True) # returns cropped face and probability
    emb = resnet(face.unsqueeze(0)).detach() # detech is to make required gradient false

    saved_data = torch.load('data.pt') # loading data.pt file
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

s3_client = boto3.client('s3')
in_bucket_name = '1229935683-in-bucket'
out_bucket_name = '1229935683-out-bucket'


static_path = "../dataset/face_images_1000/"
while True:
    response = sqs_client.receive_message(
    QueueUrl = req_queue_url,
    MaxNumberOfMessages = 10,
    WaitTimeSeconds = 20
)

    if 'Messages' in response:
        for message in response['Messages']:
            msg_body = message['Body']
            imgae_name = msg_body.split(":")[1][2:-2].strip()
            print("Image_Name", imgae_name)
            image_full_path = static_path +  imgae_name
            response = s3_client.get_object(
                Bucket=in_bucket_name,
                Key=imgae_name
            )
            result = face_match(response['Body'], 'data.pt')
            print(result[0], "result..........................")
            
            out_img_name = imgae_name.split('.')[0]
            out_data = result[0]
            json_data = json.dumps(out_data)
            s3_client.put_object(
                Bucket=out_bucket_name,
                Key=out_img_name,
                Body=json_data
            )
            sqs_client.send_message(
                QueueUrl = res_queue_url,
                MessageBody = f"{out_img_name}:{result[0]}"
            )
            sqs_client.delete_message(QueueUrl = req_queue_url, ReceiptHandle=message['ReceiptHandle'])

    else:
        print("no msg received....")