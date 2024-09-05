// AWS SDK v3 imports
const { S3Client, GetObjectCommand } = require("@aws-sdk/client-s3");
const { DynamoDBClient, ScanCommand } = require("@aws-sdk/client-dynamodb");
const { SESClient, SendEmailCommand } = require("@aws-sdk/client-ses");
const { stringify } = require("querystring");

// Initialize AWS SDK v3 clients
const s3 = new S3Client({});
const dynamoDb = new DynamoDBClient({});
const ses = new SESClient({});

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
      const data = await s3.send(new GetObjectCommand(params));
      const announcementContent = (await streamToString(data.Body)).toString('utf-8');

      // Extract the title and content without front matter from the markdown file
      const { title, description } = extractTitleAndContent(announcementContent);

      const subscribers = await dynamoDb.send(new ScanCommand({ TableName: tableName }));
      const emailPromises = subscribers.Items.map(item => {
        const emailParams = {
          Source: 'noreply@cgmartini.nl',
          Destination: { ToAddresses: [`${item.email.S}`] },
          Message: {
            Subject: { Data: `New Announcement from the Martini Force Field Initiative.` },
            Body: { Html: { Data: 
              `
              <h3>Title<hr></h3>
              ${title}
              
              <h3>Short description<hr></h3>
              ${description}

              <h3>Details<hr></h3>
              For more details please visit our <a href="https://martini-force-field-initiative.github.io/docs/announcements/">Announcement Board</a>.
                            
              <br><br>

              <hr style="border: 0.5px solid #000;">
              <em>If you no longer wish to receive emails from us, you can <a href="https://q8hgi2weih.execute-api.ca-central-1.amazonaws.com/prod/unsubscribe?email=${encodeURIComponent(item.email.S)}&token=${item.token.S}">unsubscribe from our mailing list</a>.</em>
              
              <hr style="border: 0.5px solid #000;">

              <i>Maintained by the Martini Developers Team.</i>
              `
            } },
          },
        };
        return ses.send(new SendEmailCommand(emailParams));
      });

      await Promise.all(emailPromises);
      console.log(`Announcement emails sent for ${key}`);
    } catch (error) {
      console.error(`Error processing announcement ${key}:`, error);
    }
  }
};

// Utility function to convert stream to string
const streamToString = async (stream) => {
  const chunks = [];
  for await (const chunk of stream) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
};

// function to extract title and content from markdown content
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
