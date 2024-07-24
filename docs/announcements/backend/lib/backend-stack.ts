import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ses from 'aws-cdk-lib/aws-ses';

export class AnnouncementsStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create a DynamoDB table to store the subscribers
    const table = new dynamodb.Table(this, 'Subscribers', {
      partitionKey: { name: 'email', type: dynamodb.AttributeType.STRING },
      tableName: 'Subscribers',
    });
    
    // Create a DynamoDB table to store the verification tokens
    const verificationTable = new dynamodb.Table(this, 'VerificationTable', {
      partitionKey: { name: 'email', type: dynamodb.AttributeType.STRING },
      tableName: 'VerificationTable',
    });

    // Create an S3 bucket for announcements
    const bucket = new s3.Bucket(this, 'AnnouncementBucket', {
      bucketName: 'martini-announcements',
      versioned: true,
    });

    // Create Lambda functions
    const subscribeFunction = new lambda.Function(this, 'SubscribeFunction', {
      runtime: lambda.Runtime.NODEJS_16_X,
      code: lambda.Code.fromAsset('lambda'),
      handler: 'subscribe.handler',
      environment: {
        TABLE_NAME: table.tableName,
        VERIFICATION_TABLE_NAME: verificationTable.tableName,
        BASE_URL: 'https://your-website.com', // Replace with your actual base URL
        SOURCE_EMAIL: 'daniel.ramirezecheme@ucalgary.ca', // Replace with your actual source email
      },
    });

    // Create a Lambda function for verifying email addresses
    const verifyEmailFunction = new lambda.Function(this, 'VerifyEmailFunction', {
      runtime: lambda.Runtime.NODEJS_16_X,
      code: lambda.Code.fromAsset('lambda'),
      handler: 'verifyEmail.handler',
      environment: {
        VERIFICATION_TABLE_NAME: verificationTable.tableName,
      },
    });

    // Create a Lambda function for unsubscribing
    const unsubscribeFunction = new lambda.Function(this, 'UnsubscribeFunction', {
      runtime: lambda.Runtime.NODEJS_16_X,
      code: lambda.Code.fromAsset('lambda'),
      handler: 'unsubscribe.handler',
      environment: {
        TABLE_NAME: table.tableName,
      },
    });

    // Create a Lambda function for sending announcement emails
    const sendAnnouncementFunction = new lambda.Function(this, 'SendAnnouncementFunction', {
      runtime: lambda.Runtime.NODEJS_16_X,
      code: lambda.Code.fromAsset('lambda'),
      handler: 'sendAnnouncement.handler',
      environment: {
        TABLE_NAME: table.tableName,
        BUCKET_NAME: bucket.bucketName,
      },
    });

    // Grant permissions
    table.grantReadWriteData(subscribeFunction);
    table.grantReadWriteData(unsubscribeFunction);
    table.grantReadWriteData(sendAnnouncementFunction);
    bucket.grantRead(sendAnnouncementFunction);
    verificationTable.grantReadWriteData(subscribeFunction);
    verificationTable.grantReadWriteData(verifyEmailFunction);

    subscribeFunction.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ses:SendEmail', 'ses:SendRawEmail'],
      resources: ['*'],
    }));
    verifyEmailFunction.addToRolePolicy(new iam.PolicyStatement({
      actions: ['dynamodb:PutItem', 'dynamodb:UpdateItem'],
      resources: [verificationTable.tableArn],
    }));
    sendAnnouncementFunction.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ses:SendEmail', 'ses:SendRawEmail'],
      resources: ['*'],
    }));

    // Create API Gateway REST API
    const api = new apigateway.RestApi(this, 'AnnouncementsApi', {
      restApiName: 'Announcements Service',
    });

    // Define the subscribe API endpoint and integrate it with the Lambda function
    const subscribe = api.root.addResource('subscribe');
    const subscribeIntegration = new apigateway.LambdaIntegration(subscribeFunction);
    subscribe.addMethod('POST', subscribeIntegration);

    // Define the unsubscribe API endpoint and integrate it with the Lambda function
    const unsubscribe = api.root.addResource('unsubscribe');
    const unsubscribeIntegration = new apigateway.LambdaIntegration(unsubscribeFunction);
    unsubscribe.addMethod('GET', unsubscribeIntegration);

    // Define the verify email API endpoint and integrate it with the Lambda function
    const verifyEmail = api.root.addResource('verifyEmail');
    const verifyEmailIntegration = new apigateway.LambdaIntegration(verifyEmailFunction);
    verifyEmail.addMethod('GET', verifyEmailIntegration);

    // Add S3 event notification to trigger the Lambda function on new announcements
    bucket.addEventNotification(s3.EventType.OBJECT_CREATED, new s3n.LambdaDestination(sendAnnouncementFunction));
  }
}
