const AWS = require('aws-sdk');
const dynamoDb = new AWS.DynamoDB.DocumentClient();
const queryString = require('querystring');

const verificationTable = process.env.VERIFICATION_TABLE_NAME;

exports.handler = async (event) => {
    console.log("Event:", JSON.stringify(event));
    const queryParams = queryString.parse(event.queryStringParameters);
    const { token, email } = queryParams;

    if (!token || !email) {
        return {
            statusCode: 400,
            body: JSON.stringify({ message: 'Invalid request' }),
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
            TableName: process.env.TABLE_NAME,
            Item: { 
                email: email,
                token: token, 
            },
        };
        await dynamoDb.put(subscribeParams).promise();

        return {
            statusCode: 200,
            body: JSON.stringify({ message: 'Email verified successfully' }),
        };
    } catch (error) {
        console.error("Error:", error);
        return {
            statusCode: 500,
            body: JSON.stringify({ message: 'An error occurred', error }),
        };
    }
};
