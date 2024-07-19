const AWS = require('aws-sdk');
const s3 = new AWS.S3();
const dynamoDb = new AWS.DynamoDB.DocumentClient();
const ses = new AWS.SES();

exports.handler = async (event) => {
  const bucketName = process.env.BUCKET_NAME;
  const tableName = process.env.TABLE_NAME;

  for (const record of event.Records) {
    const key = record.s3.object.key;

    const params = {
      Bucket: bucketName,
      Key: key,
    };

    try {
      const data = await s3.getObject(params).promise();
      const announcementContent = data.Body.toString('utf-8');

      const subscribers = await dynamoDb.scan({ TableName: tableName }).promise();
      const emailPromises = subscribers.Items.map(item => {
        const emailParams = {
          Source: 'daniel.ramirezecheme@ucalgary.ca',
          Destination: { ToAddresses: [item.email] },
          Message: {
            Subject: { Data: `New Announcement: ${key}` },
            Body: { Html: { Data: 
              `
              ${announcementContent}
              
              <br><br>
              
              <hr style="border: 0.5px solid #000;">
              If you no longer wish to receive emails from us, you can <a href="https://ilidpuzbe9.execute-api.ca-central-1.amazonaws.com/prod/unsubscribe?email=${encodeURIComponent(item.email)}&token=${item.token}">unsubscribe from our mailing list</a>.
              
              <hr style="border: 0.5px solid #000;">

              <i>Maintained by the Martini Developers Team.</i>
              `
            } },
          },
        };
        return ses.sendEmail(emailParams).promise();
      });

      await Promise.all(emailPromises);
      console.log(`Announcement emails sent for ${key}`);
    } catch (error) {
      console.error(`Error processing announcement ${key}:`, error);
    }
  }
};
