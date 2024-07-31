const aws = require('aws-sdk');
const { nanoid } = require('nanoid');

const ses = new aws.SES({ region: 'ca-central-1' });
const documentClient = new aws.DynamoDB.DocumentClient({ region: 'ca-central-1' });
const sqs = new aws.SQS({ region: 'ca-central-1' });

const ADMIN_EMAIL = process.env.ADMIN_EMAIL;

exports.createContact = async (event) => {
    // obtain env variables

    const CONTACT_TABLE_NAME = process.env.CONTACT_TABLE_NAME;
    const CONTACT_PROCESSING_QUEUE_URL = process.env.CONTACT_PROCESSING_QUEUE_URL;
    const { body } = event;
    const { contactName, contactEmail, contactInstitution, contactSubject, contactMessage } = JSON.parse(body);
    const contactId = nanoid();

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
    // persist contact in dynamoDb

    await documentClient.put(putParams).promise();

    console.log(`Contact ${contactId} created`);

    // add the persisted contact in the queue which will notify the administrator

    const { MessageId } = await sqs.sendMessage({
        QueueUrl: CONTACT_PROCESSING_QUEUE_URL,
        MessageBody: JSON.stringify({ contact, admin: ADMIN_EMAIL })
    }).promise()

    console.log(`Message ${MessageId} sent to queue`);

    return {
        statusCode: 200,
        body: JSON.stringify({
            contact,
            messageId: MessageId,
        })
    }
};

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
        await ses.sendEmail(sesParams).promise();

        const confirmationMessage = `
Dear ${Name},

Thank you for reaching out to us. We have received your contact form and will get back to you shortly.

Best regards,
Martini Developers Team
        `;
        const confirmationParams = {
            Message: {
                Body: {
                    Text: {
                        Data: confirmationMessage,
                        Charset: 'UTF-8'
                    }
                },
                Subject: {
                    Data: "Confirmation of Your Contact Form Submission.",
                    Charset: 'UTF-8'
                }
            },
            Source: SOURCE_EMAIL,
            Destination: {
                ToAddresses: [Email]
            }
        };
        await ses.sendEmail(confirmationParams).promise();
    });
    await Promise.all(recordPromises);
}