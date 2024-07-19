const AWS = require('aws-sdk');
const dynamoDb = new AWS.DynamoDB.DocumentClient();
const ses = new AWS.SES();

exports.handler = async (event) => {
  const requestBody = JSON.parse(event.body);
  const emailSubject = requestBody.subject;
  const emailBody = requestBody.body;

  const params = {
    TableName: process.env.TABLE_NAME,
  };

  try {
    const data = await dynamoDb.scan(params).promise();
    const emails = data.Items;

    const sendEmailPromises = emails.map(item => {
      const unsubscribeLink = `https://se8uiyvcg0.execute-api.ca-central-1.amazonaws.com/prod/unsubscribe?email=${encodeURIComponent(item.email)}&token=${item.token}`;
      const emailParams = {
        Source: 'daniel.ramirezecheme@ucalgary.ca',
        Destination: {
          ToAddresses: [item.email],
        },
        Message: {
          Subject: { Data: emailSubject },
          Body: { Html: { Data: `${emailBody}<br><br><a href="${unsubscribeLink}">Unsubscribe</a>` } },
        },
      };
      return ses.sendEmail(emailParams).promise();
    });

    await Promise.all(sendEmailPromises);

    return {
      statusCode: 200,
      body: JSON.stringify({ message: 'Emails sent successfully' }),
    };
  } catch (error) {
    return {
      statusCode: 500,
      body: JSON.stringify({ message: 'An error occurred', error }),
    };
  }
};
