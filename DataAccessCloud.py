import boto3
from boto3.dynamodb.conditions import Key, Attr


class dataAccess(object):


    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb',
                          region_name='eu-west-2',
                          endpoint_url='http://dynamodb.eu-west-2.amazonaws.com')

    def getDynamoDBRef(self):
        return self.dynamodb
        
        
    def getDigest(self, table):
        # DynamoDB stuff here
        self.table = self.dynamodb.Table(table)
        DigestQuery = self.table.scan()  # will only ever have one row in it
        # add index error exception here for empty table
        Digest = DigestQuery["Items"][0]["Digest"]
        return Digest


    def replaceDigest(self, sig):
        scan = self.table.scan()
        with self.table.batch_writer() as batch:
            for each in scan['Items']:
                batch.delete_item(
                    Key={
                        'Digest': each['Digest']
                    }
                )

        # Insert new digest
        response = self.table.put_item(
            Item={
                'Digest': sig}
        )

    def logRun(self, table, date_string, output, sig):
        # hack here - need to update the table fields to match
        # with signature in the primary field it wasn't logging eac run only when it changed
        table = self.dynamodb.Table(table)
        response = table.put_item(
            Item={
                'LogTime': date_string,
                'Output': output,
                'Signature': sig

            }
        )
        return response