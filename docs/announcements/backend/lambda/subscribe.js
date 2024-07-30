const AWS = require('aws-sdk');
const dynamoDb = new AWS.DynamoDB.DocumentClient();
const ses = new AWS.SES();
const crypto = require('crypto');

const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const verificationTable = process.env.VERIFICATION_TABLE_NAME;
const baseUrl = process.env.BASE_URL;

exports.handler = async (event) => {
    console.log("Event:", JSON.stringify(event));
    const requestBody = JSON.parse(event.body);
    const email = requestBody.email;

    if (!emailRegex.test(email)) {
        console.log("Invalid email address:", email);
        return {
            statusCode: 400,
            body: JSON.stringify({ message: 'Invalid email address' }),
        };
    }

    try {
        // Check if the email is already subscribed
        const params = {
            TableName: process.env.TABLE_NAME,
            Key: { email },
        };
        const result = await dynamoDb.get(params).promise();

        if (result.Item) {
            return {
                statusCode: 200,
                body: JSON.stringify({ message: 'Email already subscribed' }),
            };
        }

        // Generate a verification token
        const token = crypto.randomBytes(20).toString('hex');

        // Save the email and token to the verification table
        const verificationParams = {
            TableName: verificationTable,
            Item: { email, token, verified: false },
        };
        await dynamoDb.put(verificationParams).promise();

        // Send a verification email
        const verificationUrl = `${baseUrl}/verifyEmail?token=${token}&email=${encodeURIComponent(email)}`;
        const emailParams = {
            Destination: {
                ToAddresses: [email],
            },
            Message: {
                Body: {
                    Text: {
                        Data: `Please verify your email by clicking the following link: ${verificationUrl}`,
                    },
                },
                Subject: {
                    Data: 'Email Verification',
                },
            },
            Source: process.env.SOURCE_EMAIL,
        };
        await ses.sendEmail(emailParams).promise();

        return {
            statusCode: 200,
            body: JSON.stringify({ message: 'Verification email sent. Please check your inbox.' }),
        };
    } catch (error) {
        console.error("Error:", error);
        return {
            statusCode: 500,
            body: JSON.stringify({ message: 'An error occurred', error }),
        };
    }
};
