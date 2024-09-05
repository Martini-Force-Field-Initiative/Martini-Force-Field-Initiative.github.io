// AWS SDK v3 specific requires
const { DynamoDBClient } = require("@aws-sdk/client-dynamodb");
const { GetCommand, PutCommand } = require("@aws-sdk/lib-dynamodb");
const { SESClient, SendEmailCommand } = require("@aws-sdk/client-ses");
const crypto = require("crypto");

// Initialize AWS SDK v3 clients
const dynamoDb = new DynamoDBClient({});
const ses = new SESClient({});

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
        const getParams = {
            TableName: process.env.TABLE_NAME,
            Key: { email },
        };
        const getResult = await dynamoDb.send(new GetCommand(getParams));

        if (getResult.Item) {
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
        await dynamoDb.send(new PutCommand(verificationParams));

        // Send a verification email
        const verificationUrl = `${baseUrl}/verifyEmail?token=${token}&email=${encodeURIComponent(email)}`;
        const emailParams = {
            Destination: {
                ToAddresses: [email],
            },
            Message: {
                Body: {
                    Html: {
                        Data: `
                        Please verify your email by clicking the following link: <a href="${verificationUrl}">${verificationUrl}</a>. <br><br>

                        <em>Note: If you did not submit a subscription request to the Martini Force Field Initiative, please ignore this email.</em>
                        `,
                    },
                },
                Subject: {
                    Data: 'Email Verification for Martini Announcements.',
                },
            },
            Source: process.env.SOURCE_EMAIL,
        };
        await ses.send(new SendEmailCommand(emailParams));

        return {
            statusCode: 200,
            body: JSON.stringify({ message: 'Verification email sent. Please check your inbox.' }),
        };
    } catch (error) {
        console.error("Error:", error);
        return {
            statusCode: 500,
            body: JSON.stringify({ message: 'An error occurred', error: error.message }),
        };
    }
};
