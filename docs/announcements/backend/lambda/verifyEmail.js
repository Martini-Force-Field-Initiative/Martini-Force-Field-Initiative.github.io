const AWS = require('aws-sdk');
const dynamoDb = new AWS.DynamoDB.DocumentClient();

const verificationTable = process.env.VERIFICATION_TABLE_NAME;
const subscribeTable = process.env.TABLE_NAME;

exports.handler = async (event) => {
    console.log("Event:", JSON.stringify(event));
    
    // Parse the query parameters
    const queryParams = event.queryStringParameters;
    const token = queryParams ? queryParams.token : null;
    const email = queryParams ? queryParams.email : null;

    if (!token || !email) {
        return {
            statusCode: 400,
            body: JSON.stringify({ message: token }),
        };
    }

    try {
        // Check the verification token
        const params = {
            TableName: verificationTable,
            Key: { email },
        };
        const result = await dynamoDb.get(params).promise();

        if (!result.Item || result.Item.token !== token) {
            return {
                statusCode: 400,
                body: JSON.stringify({ message: 'Invalid token' }),
            };
        }

        // Update the verification status
        const updateParams = {
            TableName: verificationTable,
            Key: { email },
            UpdateExpression: 'set verified = :verified',
            ExpressionAttributeValues: {
                ':verified': true,
            },
        };
        await dynamoDb.update(updateParams).promise();

        // Move the email to the subscribed table
        const subscribeParams = {
            TableName: subscribeTable,
            Item: { 
                email: email,
                token: token, 
            },
        };
        await dynamoDb.put(subscribeParams).promise();

        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'text/html',
            },
            body: `
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Email Verification</title>
                </head>
                <body>
                    <h1>Email verified successfully</h1>
                </body>
                </html>
            `,
        };
    } catch (error) {
        console.error("Error:", error);
        return {
            statusCode: 500,
            body: JSON.stringify({ message: 'An error occurred', error }),
        };
    }
};
