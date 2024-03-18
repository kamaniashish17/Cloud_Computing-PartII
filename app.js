const express = require("express");
const multer = require("multer");
const crypto = require("crypto");
const {
  SQSClient,
  SendMessageCommand,
  ReceiveMessageCommand,
  DeleteMessageCommand,
  GetQueueAttributesCommand,
} = require("@aws-sdk/client-sqs");
const { S3Client, PutObjectCommand } = require("@aws-sdk/client-s3");
const {
  EC2Client,
  TerminateInstancesCommand,
  RunInstancesCommand,
} = require("@aws-sdk/client-ec2");
let instanceArray = [];
const userData = `Content-Type: multipart/mixed; boundary="//"
MIME-Version: 1.0

--//
Content-Type: text/cloud-config; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: attachment; filename="cloud-config.txt"

#cloud-config
cloud_final_modules:
- [scripts-user, always]

--//
Content-Type: text/x-shellscript; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: attachment; filename="userdata.txt"

#!/bin/bash
source /home/ubuntu/env/bin/activate
python3 /home/ubuntu/apptier.py
--//--`;
const app = express();
const upload = multer();
let numOfRequestsHit = 0;

const sqsClient = new SQSClient({ region: "us-east-1" });
const s3Client = new S3Client({ region: "us-east-1" });
const ec2Client = new EC2Client({ region: "us-east-1" });


const requestQueueURL =
  "https://sqs.us-east-1.amazonaws.com/905418127621/1229935683-req-queue";
const responseQueueURL =
  "https://sqs.us-east-1.amazonaws.com/905418127621/1229935683-res-queue";
const inBucketName = "1229935683-in-bucket";

const object = {};

const startInstance = async (num) => {
  const instanceParams = {
    ImageId: "ami-003d3c000e3f7d02a",
    InstanceType: "t2.micro",
    KeyName: "my_key_pair",
    MinCount: 1,
    MaxCount: 1,
    UserData: Buffer.from(userData).toString("base64"),
    TagSpecifications: [
      {
        ResourceType: "instance",
        Tags: [{ Key: "Name", Value: `app-tier-instance-${num}` }],
      },
    ],
    IamInstanceProfile: {
      Name: "Full_Access_SQS_S3",
    },
  };

  const command = new RunInstancesCommand(instanceParams);
  const response = await ec2Client.send(command);
  instanceArray.push(response.Instances[0].InstanceId);
};

const stopInstances = async () => {
  console.log("Stopping Instances!!!!!!!!!!!!!!!")
  const params = {
    InstanceIds: instanceArray,
  };

  await ec2Client.send(new TerminateInstancesCommand(params));
};
app.post("/", upload.single("inputFile"), async (req, res) => {
  try {
    // console.log("Original Request", req);
    // console.log("Request", req.file);
    const num = numOfRequestsHit + 1;
    numOfRequestsHit += 1;
    const file = req.file;
    const imagePayload = file.originalname;
    // console.log("images ---- ", imagePayload);
    const correlationId = crypto.randomBytes(16).toString("hex");
    const msgBody = {
      file_name: imagePayload,
    };

    const sqsParams = {
      QueueUrl: requestQueueURL,
      MessageBody: imagePayload,
      MessageAttributes: {
        CorrelationId: {
          DataType: "String",
          StringValue: correlationId,
        },
      },
    };

    const sqsResponse = await sqsClient.send(new SendMessageCommand(sqsParams));

    if (num < 20) {
      await startInstance(num);
    }

    const s3Params = {
      Bucket: inBucketName,
      Key: imagePayload,
      Body: file.buffer,
    };

    await s3Client.send(new PutObjectCommand(s3Params));

    while (true) {
      const sqsParams = {
        QueueUrl: responseQueueURL,
        MaxNumberOfMessages: 1,
        WaitTimeSeconds: 20, // Adjust according to your requirements
        MessageAttributeNames: ["CorrelationId"],
        VisibilityTimeout: 40,
      };
      const { Messages } = await sqsClient.send(
        new ReceiveMessageCommand(sqsParams)
      );

      if (Messages && Messages.length > 0) {
        // console.log(Messages);
        // console.log(
        //   "vanshaj",
        //   Messages[0].MessageAttributes.CorrelationId.StringValue
        // );
        object[`${Messages[0].MessageAttributes.CorrelationId.StringValue}`] =
          Messages[0];
      }
      if (correlationId in object) {
        const message = object[correlationId];
        const body = message.Body;
        // Process the message as needed
        const deleteParams = {
          QueueUrl: responseQueueURL,
          ReceiptHandle: message.ReceiptHandle,
        };
        await sqsClient.send(new DeleteMessageCommand(deleteParams));
        res.status(200).send(body);
        numOfRequestsHit--;
        if (numOfRequestsHit === 0) {
          await stopInstances();
        }
        break; // Returning the response message body
      }
    }

    // console.log("Message sent to the SQS Req Queue", sqsResponse);

    // const response = await waitForSQSResponseQueue(correlationId);
    // if (response) {
    //   console.log("Response", response);
    //   res.status(200).send(response);
    // } else {
    //   res.status(404).send("No response received");
    // }
    // res.status(200).send(`${imagePayload}: ${imageClassificationLookup.loc[imagePayload]['Results']}`);
  } catch (error) {
    console.error("Error:", error);
    res.status(500).send("Internal Server Error");
  }
});

const port = 8000;
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});
