from __future__ import unicode_literals

import boto
import tempfile
from mock import patch, call, Mock
from nose.tools import eq_
from tests import TestCase

from catsnap import settings
from catsnap import Config, HASH_KEY

class TestConfig(TestCase):
    def test_it_is_a_singleton(self):
        config1 = Config()
        config2 = Config()
        assert config1 is config2

    @patch('catsnap.Config.ensure_config_files_exist')
    def test_initialization_runs_ensure_config(self, ensure_config):
        Config()
        ensure_config.assert_called_with()

    @patch('catsnap.sys')
    @patch('catsnap.Config.get_aws_credentials')
    @patch('catsnap.Config.get_catsnap_config')
    def test_ensure_config_files_exist__degenerate_case(self, setup_boto,
            setup_catsnap, sys):
        (_, creds) = tempfile.mkstemp()

        with patch('catsnap.os.path') as path:
            path.exists.return_value = True
            with patch('catsnap.Config.CREDENTIALS_FILE', creds) as _:
                Config().ensure_config_files_exist()
        eq_(setup_boto.call_count, 0, "get_aws_credentials shouldn't've "
                "been called")
        eq_(setup_catsnap.call_count, 0, "get_catsnap_config shouldn't've "
                "been called")
        eq_(sys.stdout.write.call_count, 0, "stdout.write shouldn't've "
                "been called")

    #using @patch(os.path) here will F up the mkstemp call :(
    @patch('catsnap.sys')
    @patch('catsnap.Config.get_catsnap_config')
    @patch('catsnap.Config.get_aws_credentials')
    def test_ensure_aws_config_exists(self, get_creds, get_config, sys):
        get_config.side_effect = AssertionError("shouldn't've been called")
        get_creds.return_value = 'the credentials'
        (_, creds) = tempfile.mkstemp()

        with patch('catsnap.os.path') as path:
            path.exists.side_effect = [ True, False, True, False ]
            with patch('catsnap.Config.CREDENTIALS_FILE', creds) as _:
                Config()
        with open(creds, 'r') as creds_file:
            eq_(creds_file.read(), 'the credentials')
        sys.stdout.write.assert_called_with(
                "Looks like this is your first run.\n")

    #using @patch(os.path) here will F up the mkstemp call :(
    @patch('catsnap.sys')
    @patch('catsnap.Config.get_aws_credentials')
    @patch('catsnap.Config.get_catsnap_config')
    def test_ensure_catsnap_config_exists(self, get_config, get_creds, sys):
        get_creds.side_effect = AssertionError("shouldn't've been called")
        get_config.return_value = 'the Config'
        (_, conf) = tempfile.mkstemp()

        with patch('catsnap.os.path') as path:
            path.exists.side_effect = [ False, True, False, True ]
            with patch('catsnap.Config.CONFIG_FILE', conf) as _:
                Config()
        with open(conf, 'r') as config_file:
            eq_(config_file.read(), 'the Config')
        sys.stdout.write.assert_called_with(
                "Looks like this is your first run.\n")

    @patch('catsnap.getpass')
    @patch('catsnap.sys')
    def test_get_credentials(self, sys, getpass):
        getpass.getpass.side_effect = ['access key id', 'secret access key']

        creds = Config().get_aws_credentials()
        sys.stdout.write.assert_called_with("Find your credentials at "
                "https://portal.aws.amazon.com/gp/aws/securityCredentials\n")
        eq_(creds, """[Credentials]
aws_access_key_id = access key id
aws_secret_access_key = secret access key""")

    @patch('catsnap.os')
    @patch('catsnap.Config._input')
    def test_get_catsnap_config(self, _input, os):
        os.environ.__getitem__.return_value = 'mcgee'
        _input.return_value = ''

        conf = Config().get_catsnap_config()
        _input.assert_has_calls([
            call("Please name your bucket (leave blank to use "
                "'catsnap-mcgee'): "),
            call("Please choose a table prefix (leave blank to use "
                "'catsnap-mcgee'): "),
        ])
        eq_(conf, """[catsnap]
bucket = catsnap-mcgee
table_prefix = catsnap-mcgee""")

    @patch('catsnap.os')
    @patch('catsnap.Config._input')
    def test_get_catsnap_config__custom_names(self, _input, os):
        os.environ.__getitem__.return_value = 'mcgee'
        _input.side_effect = ['booya', '']

        conf = Config().get_catsnap_config()
        eq_(conf, """[catsnap]
bucket = booya
table_prefix = booya""")

        _input.side_effect = ['rutabaga', 'wootabaga']
        conf = Config().get_catsnap_config()
        eq_(conf, """[catsnap]
bucket = rutabaga
table_prefix = wootabaga""")

class TestGetBucket(TestCase):
    @patch('catsnap.Config.bucket_name')
    @patch('catsnap.boto')
    def test_does_not_re_create_buckets(self, mock_boto, bucket_name):
        bucket_name.return_value = 'oodles'
        mock_bucket = Mock()
        mock_bucket.name = 'oodles'
        s3 = Mock()
        s3.get_all_buckets.return_value = [ mock_bucket ]
        s3.get_bucket.return_value = mock_bucket
        mock_boto.connect_s3.return_value = s3

        bucket = Config().bucket()
        eq_(s3.create_bucket.call_count, 0, "shouldn't've created a bucket")
        eq_(bucket, mock_bucket)

    @patch('catsnap.Config.bucket_name')
    @patch('catsnap.boto')
    def test_creates_bucket_if_necessary(self, mock_boto, bucket_name):
        bucket_name.return_value = 'galvanized'
        s3 = Mock()
        mock_bucket = Mock()
        s3.create_bucket.return_value = mock_bucket
        s3.get_all_buckets.return_value = []
        mock_boto.connect_s3.return_value = s3

        bucket = Config().bucket()
        s3.create_bucket.assert_called_with('galvanized')
        eq_(bucket, mock_bucket)

    @patch('catsnap.Config.bucket_name')
    @patch('catsnap.boto')
    def test_get_bucket_is_memoized(self, mock_boto, bucket_name):
        bucket_name.return_value = 'oodles'
        mock_bucket = Mock()
        mock_bucket.name = 'oodles'
        s3 = Mock()
        s3.get_all_buckets.return_value = [ mock_bucket ]
        s3.get_bucket.side_effect = [ 1, 2 ]
        mock_boto.connect_s3.return_value = s3

        bucket1 = Config().bucket()
        bucket2 = Config().bucket()
        assert bucket1 is bucket2, 'multiple s3 connections were established'
        eq_(s3.get_bucket.call_count, 1)

class TestGetTable(TestCase):
    @patch('catsnap.Config._table_prefix')
    @patch('catsnap.boto')
    def test_does_not_re_create_tables(self, mock_boto, _table_prefix):
        _table_prefix.return_value = 'rooibos'
        mock_table = Mock()
        mock_table.name = 'rooibos-things'
        dynamo = Mock()
        dynamo.list_tables.return_value = [ 'rooibos-things' ]
        dynamo.get_table.return_value = mock_table
        mock_boto.connect_dynamodb.return_value = dynamo

        table = Config().table('things')
        eq_(dynamo.create_table.call_count, 0, "shouldn't've created a table")
        eq_(table, mock_table)

    @patch('catsnap.Config._table_prefix')
    @patch('catsnap.boto')
    def test_memoization(self, boto, _table_prefix):
        _table_prefix.return_value = 'foo'
        config = Config()
        mock_table = Mock()
        config._tables = {'foo-tags': mock_table}

        table = config.table('tags')
        eq_(table, mock_table)
        eq_(boto.connect_dynamodb.call_count, 0)

class TestCreateTable(TestCase):
    @patch('catsnap.Config._table_prefix')
    @patch('catsnap.boto')
    def test_create_table(self, mock_boto, _table_prefix):
        _table_prefix.return_value = 'myemmatable'
        dynamo = Mock()
        mock_table = Mock()
        schema = Mock()
        dynamo.create_table.return_value = mock_table
        dynamo.create_schema.return_value = schema
        mock_boto.connect_dynamodb.return_value = dynamo

        table = Config().create_table('things')
        dynamo.create_schema.assert_called_with(
                hash_key_name='tag',
                hash_key_proto_value='S')
        dynamo.create_table.assert_called_with(name='myemmatable-things',
                schema=schema,
                read_units=3,
                write_units=5)
        eq_(table, mock_table)

    @patch('catsnap.Config._table_prefix')
    @patch('catsnap.Config.table')
    @patch('catsnap.boto')
    def test_no_error_if_table_exists(self, mock_boto, table, _table_prefix):
#        boto.exception.DynamoDBResponseError: DynamoDBResponseError: 400 Bad Request
#{u'message': u'Attempt to change a resource which is still in use: Duplicate table name: catsnap-andrewlorente-image', u'__type': u'com.amazonaws.dynamodb.v20111205#ResourceInUseException'}
        _table_prefix.return_value = 'foo'
        dynamo = Mock()
        error = boto.exception.DynamoDBResponseError(400, 'table exists')
        error.error_code = 'ResourceInUseException'
        dynamo.create_table.side_effect = error
        mock_boto.connect_dynamodb.return_value = dynamo
        table.return_value = 'this is the table'

        created_table = Config().create_table('things')
        eq_(created_table, 'this is the table')

class TestGetConnections(TestCase):
    @patch('catsnap.boto')
    def test_get_dynamodb(self, boto):
        Config().get_dynamodb()
        eq_(boto.connect_dynamodb.call_count, 1)

    @patch('catsnap.boto')
    def test_get_dynamodb__is_memoized(self, boto):
        boto.connect_dynamodb.side_effect = [1, 2]
        dynamo1 = Config().get_dynamodb()
        dynamo2 = Config().get_dynamodb()

        assert dynamo1 is dynamo2, 'different connections were established'
        eq_(boto.connect_dynamodb.call_count, 1)

    @patch('catsnap.boto')
    def test_get_s3(self, boto):
        Config().get_s3()
        eq_(boto.connect_s3.call_count, 1)

    @patch('catsnap.boto')
    def test_get_s3__is_memoized(self, boto):
        boto.connect_dynamodb.side_effect = [1, 2]
        sss1 = Config().get_s3()
        sss2 = Config().get_s3()

        assert sss1 is sss2, 'different connections were established'
        eq_(boto.connect_s3.call_count, 1)


class TestBuildParser(TestCase):
    def test_build_parser(self):
        (_, conf) = tempfile.mkstemp()
        with open(conf, 'w') as config_file:
            config_file.write("""[catsnap]
bucket = boogles
table_prefix = bugglez""")

        config = Config()
        with patch('catsnap.Config.CONFIG_FILE', conf) as _:
            parser = config._parser()
        eq_(parser.get('catsnap', 'bucket'), 'boogles')
        eq_(parser.get('catsnap', 'table_prefix'), 'bugglez')
        eq_(config.bucket_name(), 'boogles')
        eq_(config._table_prefix(), 'bugglez')
