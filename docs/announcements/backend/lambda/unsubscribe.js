// AWS SDK v3 specific requires
const { DynamoDBClient } = require("@aws-sdk/client-dynamodb");
const { GetCommand, DeleteCommand } = require("@aws-sdk/lib-dynamodb");

// Initialize AWS SDK v3 client
const dynamoDb = new DynamoDBClient({});

exports.handler = async (event) => {
  const email = event.queryStringParameters.email;
  const token = event.queryStringParameters.token;

  const params = {
    TableName: process.env.TABLE_NAME,
    Key: { email },
  };

  const params_verify = {
    TableName: process.env.VERIFICATION_TABLE_NAME,
    Key: { email },
  };

  try {
    // Check the email token
    const data = await dynamoDb.send(new GetCommand(params));

    if (data.Item && data.Item.token === token) {
      // Delete from both tables
      await dynamoDb.send(new DeleteCommand(params));
      await dynamoDb.send(new DeleteCommand(params_verify));

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
                <h1>Sorry to see you go ;(</h1>
                <p>You have successfully unsubscribed to receive announcements from the Martini Force Field Initiative.<br>
                You are welcome to subscribe again at any time.</p>
            </div>
        </body>
        </html>
        `,
      };
    } else {
      return {
        statusCode: 400,
        body: JSON.stringify({ message: 'Invalid token' }),
      };
    }
  } catch (error) {
    console.error("Error:", error);
    return {
      statusCode: 500,
      body: JSON.stringify({ message: 'An error occurred', error: error.message }),
    };
  }
};
