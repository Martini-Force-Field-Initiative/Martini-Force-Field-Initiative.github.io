const AWS = require('aws-sdk');
const dynamoDb = new AWS.DynamoDB.DocumentClient();

exports.handler = async (event) => {
  const email = event.queryStringParameters.email;

  const params = {
    TableName: process.env.TABLE_NAME,
    Key: { email },
  };

  try {
    await dynamoDb.delete(params).promise();
    return {
      statusCode: 200,
      body: JSON.stringify({ message: 'Unsubscription successful' }),
    };
  } catch (error) {
    return {
      statusCode: 500,
      body: JSON.stringify({ message: 'An error occurred' }),
    };
  }
};
