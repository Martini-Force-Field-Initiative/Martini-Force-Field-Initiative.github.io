// Import specific clients and commands from AWS SDK v3
const { SESClient, SendEmailCommand } = require('@aws-sdk/client-ses');
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, PutCommand } = require('@aws-sdk/lib-dynamodb');
const { SQSClient, SendMessageCommand } = require('@aws-sdk/client-sqs');
const crypto = require("crypto");

// Initialize clients
const sesClient = new SESClient({ region: 'ca-central-1' });

const dynamoDbClient = new DynamoDBClient({ region: 'ca-central-1' });
// Wrap the DynamoDB client in the DynamoDBDocumentClient
const documentClient = DynamoDBDocumentClient.from(dynamoDbClient);

const sqsClient = new SQSClient({ region: 'ca-central-1' });

const ADMIN_EMAIL = process.env.ADMIN_EMAIL;

// Lambda function to create contact
exports.createContact = async (event) => {
    const CONTACT_TABLE_NAME = process.env.CONTACT_TABLE_NAME;
    const CONTACT_PROCESSING_QUEUE_URL = process.env.CONTACT_PROCESSING_QUEUE_URL;
    const { body } = event;
    const { contactName, contactEmail, contactInstitution, contactSubject, contactMessage } = JSON.parse(body);
    const contactId = crypto.randomBytes(16).toString('hex');

    const contact = {
        contactId,
        Name: contactName,
        Email: contactEmail,
        Institution: contactInstitution,
        Subject: contactSubject,
        Message: contactMessage
    };

    const putParams = {
        TableName: CONTACT_TABLE_NAME,
        Item: contact
    };

    // Persist contact in DynamoDB
    await documentClient.send(new PutCommand(putParams));

    console.log(`Contact ${contactId} created`);

    // Add the persisted contact to the SQS queue
    const sendMessageParams = {
        QueueUrl: CONTACT_PROCESSING_QUEUE_URL,
        MessageBody: JSON.stringify({ contact, admin: ADMIN_EMAIL })
    };

    const { MessageId } = await sqsClient.send(new SendMessageCommand(sendMessageParams));

    console.log(`Message ${MessageId} sent to queue`);

    return {
        statusCode: 200,
        body: JSON.stringify({
            contact,
            messageId: MessageId,
        })
    };
};

// Lambda function to process contact
exports.processContact = async (event) => {
    const SOURCE_EMAIL = 'noreply@cgmartini.nl';
    const recordPromises = event.Records.map(async (record) => {
        const { body } = record;
        const { contact, admin } = JSON.parse(body);
        const { Name, Email, Institution, Subject, Message } = contact;

        const contactMessage = `
Name: ${Name} 

Email: ${Email}

Institution: ${Institution}

Subject: ${Subject}

Message: ${Message}
        `;
        const sesParams = {
            Message: {
                Body: {
                    Text: {
                        Data: contactMessage,
                        Charset: 'UTF-8'
                    }
                },
                Subject: {
                    Data: "New Contact Form submitted through the Martini web portal.",
                    Charset: 'UTF-8'
                }
            },
            Source: SOURCE_EMAIL,
            Destination: {
                ToAddresses: [admin]
            }
        };
 
        // Send email using SES
        await sesClient.send(new SendEmailCommand(sesParams));
    });
 
    await Promise.all(recordPromises);
 
}