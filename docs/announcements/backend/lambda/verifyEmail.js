// AWS SDK v3 specific requires
const { DynamoDBClient } = require("@aws-sdk/client-dynamodb");
const { GetCommand, UpdateCommand, PutCommand } = require("@aws-sdk/lib-dynamodb");

// Initialize AWS SDK v3 client
const dynamoDb = new DynamoDBClient({});

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
            body: JSON.stringify({ message: 'Missing token or email' }),
        };
    }

    try {
        // Check the verification token
        const getParams = {
            TableName: verificationTable,
            Key: { email },
        };
        const getResult = await dynamoDb.send(new GetCommand(getParams));

        if (!getResult.Item || getResult.Item.token !== token) {
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
        await dynamoDb.send(new UpdateCommand(updateParams));

        // Move the email to the subscribed table
        const subscribeParams = {
            TableName: subscribeTable,
            Item: { 
                email: email,
                token: token, 
            },
        };
        await dynamoDb.send(new PutCommand(subscribeParams));

        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'text/html',
            },
            body: `
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Email Verification</title>
                <script>
                    function closeCurrentTab() {
                        window.open('', '_self').close();
                    }
                </script>
                <style>
                    body {
                        font-family: 'Arial', sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #72edf2, #5151e5);
                        color: #fff;
                    }
                    .container {
                        text-align: center;
                        background: rgba(0, 0, 0, 0.5);
                        padding: 40px;
                        border-radius: 10px;
                        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
                    }
                    h1 {
                        margin: 0 0 20px;
                        font-size: 2.5em;
                    }
                    p {
                        font-size: 1.2em;
                    }
                    .button {
                        display: inline-block;
                        padding: 10px 20px;
                        margin-top: 20px;
                        font-size: 1em;
                        color: #5151e5;
                        background-color: #fff;
                        border: none;
                        border-radius: 5px;
                        text-decoration: none;
                        transition: background-color 0.3s ease;
                    }
                    .button:hover {
                        background-color: #72edf2;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Email Verified!</h1>
                    <p>You have successfully subscribed to receive announcements from the Martini Force Field Initiative.</p>
                </div>
            </body>
            </html>
        `,
        };
    } catch (error) {
        console.error("Error:", error);
        return {
            statusCode: 500,
            body: JSON.stringify({ message: 'An error occurred', error: error.message }),
        };
    }
};
