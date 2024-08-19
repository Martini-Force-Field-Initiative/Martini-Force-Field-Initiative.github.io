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

      // Extract the title and content without front matter from the markdown file
      const { title, description } = extractTitleAndContent(announcementContent);

      const subscribers = await dynamoDb.scan({ TableName: tableName }).promise();
      const emailPromises = subscribers.Items.map(item => {
        const emailParams = {
          Source: 'noreply@cgmartini.nl',
          Destination: { ToAddresses: [item.email] },
          Message: {
            Subject: { Data: `New Announcement from the Martini Force Field Initiative.` },
            Body: { Html: { Data: 
              `
              <h3>Title<hr></h3>
              ${title}
              
              <h3>Short description<hr></h3>
              ${description}

              <h3>Details<hr></h3>
              For more details please visit our <a href="https://cgmartini.nl/docs/announcements/">Announcement Board</a>.
                            
              <br><br>

              <hr style="border: 0.5px solid #000;">
              <em>If you no longer wish to receive emails from us, you can <a href="https://q8hgi2weih.execute-api.ca-central-1.amazonaws.com/prod/unsubscribe?email=${encodeURIComponent(item.email)}&token=${item.token}">unsubscribe from our mailing list</a>.</em>
              
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

function extractTitleAndContent(markdownContent) {
  const frontMatterMatch = markdownContent.match(/---([\s\S]*?)---/);
  if (!frontMatterMatch) {
    throw new Error('Invalid markdown format: Missing front matter');
  }
  const frontMatter = frontMatterMatch[1];
  const titleMatch = frontMatter.match(/title: ["']?([\s\S]*?)["']?(?=\n\S|$)/);
  if (!titleMatch) {
    throw new Error('Invalid markdown format: Missing title');
  }
  const title = titleMatch[1].trim();
  const descriptionMatch = frontMatter.match(/description:\s*(\|)?\s*([\s\S]*?)(?=\n\S|$)/);
  if (!descriptionMatch) {
    throw new Error('Invalid markdown format: Missing description');
  }
  const description = descriptionMatch[2].trim();

  return { title, description };
}
