const AWS = require('aws-sdk');
const dynamoDb = new AWS.DynamoDB.DocumentClient();

exports.handler = async (event) => {
  const email = event.queryStringParameters.email;
  const token = event.queryStringParameters.token;

  const params = {
    TableName: process.env.TABLE_NAME,
    Key: { email },
  };

  try {
    const data = await dynamoDb.get(params).promise();

    if (data.Item && data.Item.token === token) {
      await dynamoDb.delete(params).promise();
      return {
        statusCode: 200,
        body: JSON.stringify({ message: 'Unsubscription successful' }),
      };
    } else {
      return {
        statusCode: 400,
        body: JSON.stringify({ message: 'Invalid token' }),
      };
    }
  } catch (error) {
    return {
      statusCode: 500,
      body: JSON.stringify({ message: 'An error occurred' }),
    };
  }
};
