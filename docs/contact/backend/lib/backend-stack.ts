import { Duration, Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambdaEventSource from 'aws-cdk-lib/aws-lambda-event-sources'; 

export class ContactsStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // create an SQS queue for processing contacts
    const contactQueue = new sqs.Queue(this, 'ContactProcessingQueue', {
      visibilityTimeout: Duration.seconds(45),
      queueName: 'contact-processing-queue',
    });

    // create an sqs event source
    const lambdaSqsEventSource = new lambdaEventSource.SqsEventSource(contactQueue, {
      batchSize: 10,
      enabled: true,
    });

    // create the lambda responsible for processing contacts
    const processContactFunction = new lambda.Function(this, 'ProcessContactLambda', {
          code: lambda.Code.fromAsset('lambda'),
          handler: 'lambda.processContact',
          runtime: lambda.Runtime.NODEJS_16_X,
        });

        // attach the event source to the ContactProcessing lambda, so that Lambda can poll the queue and invoke the ContactProcessing Lambda
        processContactFunction.addEventSource(lambdaSqsEventSource);
        // grant the contact process lambda permission to invoke SES
        processContactFunction.addToRolePolicy(new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ['ses:SendRawEmail', 'ses:SendTemplatedEmail', 'ses:SendEmail'],
          resources: ['*'],
          sid: 'SendEmailPolicySid',
        }));

    // provision the DynamoDB contact table
    const contactTable = new dynamodb.Table(this, 'ContactTable', {
          tableName: 'Contacts',
          partitionKey: { name: 'contactId', type: dynamodb.AttributeType.STRING },
          billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
          encryption: dynamodb.TableEncryption.DEFAULT,
          pointInTimeRecovery: false,
        });

    // creates the Lambda function to create the contact.
    const createContactFunction = new lambda.Function(this, 'CreateContactLambda', {
          code: lambda.Code.fromAsset('lambda'),
          handler: 'lambda.createContact',
          runtime: lambda.Runtime.NODEJS_16_X,
          memorySize: 256,
          timeout: Duration.seconds(10),
          environment: {
            CONTACT_TABLE_NAME: contactTable.tableName,
            CONTACT_PROCESSING_QUEUE_URL: contactQueue.queueUrl,
            ADMIN_EMAIL: 'daniel.ramirezecheme@ucalgary.ca',
          }
        });
        contactTable.grantWriteData(createContactFunction); // allow the createContact lambda function to write to the contact table
        contactQueue.grantSendMessages(createContactFunction); // allow the createContact lambda function to send messages to the contact processing queue

    // creates an API Gateway REST API
    const restApi = new apigateway.RestApi(this, 'ContactsServiceApi', {
          restApiName: 'Contacts Service',
        });

    // create an api gateway resource '/contacts/new'
    const newContacts = restApi.root.addResource('contacts').addResource('new');
        // creating a POST method for the new contact resource that integrates with the createContact Lambda function
        newContacts.addMethod('POST', new apigateway.LambdaIntegration(createContactFunction), {
          authorizationType: apigateway.AuthorizationType.NONE,
        });
  }
}
