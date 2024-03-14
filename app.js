const express = require("express");
const multer = require("multer");
const crypto = require("crypto");
const {
  SQSClient,
  SendMessageCommand,
  ReceiveMessageCommand,
  DeleteMessageCommand,
} = require("@aws-sdk/client-sqs");
const { S3Client, PutObjectCommand } = require("@aws-sdk/client-s3");

const app = express();
const upload = multer();

const sqsClient = new SQSClient({ region: "us-east-1" });
const s3Client = new S3Client({ region: "us-east-1" });

const requestQueueURL =
  "https://sqs.us-east-1.amazonaws.com/905418127621/1229935683-req-queue";
const responseQueueURL =
  "https://sqs.us-east-1.amazonaws.com/905418127621/1229935683-res-queue";
const inBucketName = "1229935683-in-bucket";

const object = {};

const waitForSQSResponseQueue = async (correlationId) => {
 
};

app.post("/", upload.single("inputFile"), async (req, res) => {
  try {
    // console.log("Original Request", req);
    // console.log("Request", req.file);

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
        VisibilityTimeout: 40
      };
      const { Messages } = await sqsClient.send(
        new ReceiveMessageCommand(sqsParams)
      );
  
      if (Messages && Messages.length > 0) {
        console.log(Messages)
        console.log("vanshaj",Messages[0].MessageAttributes.CorrelationId.StringValue)
        object[`${Messages[0].MessageAttributes.CorrelationId.StringValue}`] =
          Messages[0];
          console.log("Shrey", correlationId in object)
      }
      if (correlationId in object) {
        const message = object[correlationId];
        const body = message.Body
        console.log("Body", body)
        console.log("Received message from response queue:", body);
        // Process the message as needed
        const deleteParams = {
          QueueUrl: responseQueueURL,
          ReceiptHandle: message.ReceiptHandle,
        };
        await sqsClient.send(new DeleteMessageCommand(deleteParams));
        console.log(object, "Object");
        res.status(200).send(body) 
        break;// Returning the response message body
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
