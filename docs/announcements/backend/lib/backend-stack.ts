import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ses from 'aws-cdk-lib/aws-ses';

export class AnnouncementsStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create a DynamoDB table
    const table = new dynamodb.Table(this, 'Subscribers', {
      partitionKey: { name: 'email', type: dynamodb.AttributeType.STRING },
      tableName: 'Subscribers',
      removalPolicy: cdk.RemovalPolicy.DESTROY, // Not recommended for production code
    });

    // Create a Lambda function for subscribing
    const subscribeFunction = new lambda.Function(this, 'SubscribeFunction', {
      runtime: lambda.Runtime.NODEJS_14_X,
      code: lambda.Code.fromAsset('lambda'),
      handler: 'subscribe.handler',
      environment: {
        TABLE_NAME: table.tableName,
      },
    });

    // Create a Lambda function for unsubscribing
    const unsubscribeFunction = new lambda.Function(this, 'UnsubscribeFunction', {
      runtime: lambda.Runtime.NODEJS_14_X,
      code: lambda.Code.fromAsset('lambda'),
      handler: 'unsubscribe.handler',
      environment: {
        TABLE_NAME: table.tableName,
      },
    });

    // Create a Lambda function for sending emails
    const sendEmailFunction = new lambda.Function(this, 'SendEmailFunction', {
      runtime: lambda.Runtime.NODEJS_14_X,
      code: lambda.Code.fromAsset('lambda'),
      handler: 'sendEmail.handler',
      environment: {
        TABLE_NAME: table.tableName,
      },
    });

    // Grant the Lambda functions permissions to access the DynamoDB table
    table.grantReadWriteData(subscribeFunction);
    table.grantReadWriteData(unsubscribeFunction);
    table.grantReadWriteData(sendEmailFunction);

    // Grant the Lambda function permissions to send emails using SES
    sendEmailFunction.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ses:SendEmail', 'ses:SendRawEmail'],
      resources: ['*'],
    }));

    // Create an API Gateway REST API
    const api = new apigateway.RestApi(this, 'NewsletterApi', {
      restApiName: 'Newsletter Service',
    });

    // Define the subscribe API endpoint and integrate it with the Lambda function
    const subscribe = api.root.addResource('subscribe');
    const subscribeIntegration = new apigateway.LambdaIntegration(subscribeFunction);
    subscribe.addMethod('POST', subscribeIntegration);

    // Define the unsubscribe API endpoint and integrate it with the Lambda function
    const unsubscribe = api.root.addResource('unsubscribe');
    const unsubscribeIntegration = new apigateway.LambdaIntegration(unsubscribeFunction);
    unsubscribe.addMethod('POST', unsubscribeIntegration);
    unsubscribe.addMethod('GET', unsubscribeIntegration);

    // Define the send email API endpoint and integrate it with the Lambda function
    const sendEmail = api.root.addResource('sendEmail');
    const sendEmailIntegration = new apigateway.LambdaIntegration(sendEmailFunction);
    sendEmail.addMethod('POST', sendEmailIntegration);
  }
}
