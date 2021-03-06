from typing import List, Optional, Union

from airflow.models import BaseOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.amazon.aws.utils.redshift import build_credentials_block
from airflow.providers.postgres.hooks.postgres import PostgresHook


class S3ToRedshiftOperator(BaseOperator):
    """
    Executes an COPY command to load files from s3 to Redshift
    .. seealso::
        For more information on how to use this operator, take a look at the guide:
        :ref:`howto/operator:S3ToRedshiftOperator`
    :param schema: reference to a specific schema in redshift database
    :type schema: str
    :param table: reference to a specific table in redshift database
    :type table: str
    :param s3_bucket: reference to a specific S3 bucket
    :type s3_bucket: str
    :param s3_key: reference to a specific S3 key
    :type s3_key: str
    :param redshift_conn_id: reference to a specific redshift database
    :type redshift_conn_id: str
    :param aws_conn_id: reference to a specific S3 connection
        If the AWS connection contains 'aws_iam_role' in ``extras``
        the operator will use AWS STS credentials with a token
        https://docs.aws.amazon.com/redshift/latest/dg/copy-parameters-authorization.html#copy-credentials
    :type aws_conn_id: str
    :param verify: Whether or not to verify SSL certificates for S3 connection.
        By default SSL certificates are verified.
        You can provide the following values:
        - ``False``: do not validate SSL certificates. SSL will still be used
                 (unless use_ssl is False), but SSL certificates will not be
                 verified.
        - ``path/to/cert/bundle.pem``: A filename of the CA cert bundle to uses.
                 You can specify this argument if you want to use a different
                 CA cert bundle than the one used by botocore.
    :type verify: bool or str
    :param column_list: list of column names to load
    :type column_list: List[str]
    :param copy_options: reference to a list of COPY options
    :type copy_options: list
    :param truncate_table: whether or not to truncate the destination table before the copy
    :type truncate_table: bool
    """

    template_fields = ('s3_bucket', 's3_key', 'schema', 'table', 'column_list', 'copy_options')
    template_ext = ()
    ui_color = '#99e699'

    def __init__(
        self,
        *,
        schema: str,
        table: str,
        s3_bucket: str,
        s3_key: str,
        redshift_conn_id: str = 'redshift_default',
        aws_conn_id: str = 'aws_default',
        verify: Optional[Union[bool, str]] = None,
        column_list: Optional[List[str]] = None,
        copy_options: Optional[List] = None,
        autocommit: bool = False,
        truncate_table: bool = False,
        primary_key: str = '',
        order_key: str = '',
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.schema = schema
        self.table = table
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        self.redshift_conn_id = redshift_conn_id
        self.aws_conn_id = aws_conn_id
        self.verify = verify
        self.column_list = column_list
        self.copy_options = copy_options or []
        self.autocommit = autocommit
        self.truncate_table = truncate_table
        self.primary_key = primary_key
        self.order_key = order_key

    def _build_copy_query(self, credentials_block: str, copy_options: str) -> str:
        column_names = "(" + ", ".join(self.column_list) + ")" if self.column_list else ''
        return f"""
                    COPY {self.schema}.{self.table} {column_names}
                    FROM 's3://{self.s3_bucket}/{self.s3_key}'
                    with credentials
                    '{credentials_block}'
                    {copy_options};
        """

    def get_columns_from_table(self, hook):
        sql = f"""SELECT column_name
        FROM information_schema.columns
        WHERE table_name = '{self.table}' and table_schema = '{self.schema}'
        ORDER BY ordinal_position"""
        results = hook.get_records(sql)
        cols = []
        for r in results:
            cols.append(r[0])
        return ",".join(cols)


    def generate_after_query(self, postgres_hook):
        if self.primary_key is not None and self.order_key is not None:
            columns = self.get_columns_from_table(postgres_hook)
            return f"""
                CREATE TEMPORARY TABLE T AS SELECT {columns}
                FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY {self.primary_key} ORDER BY {self.order_key} DESC) n
                    FROM {self.schema}.{self.table}
                )
                WHERE n = 1;
                DELETE FROM {self.schema}.{self.table};
                INSERT INTO {self.schema}.{self.table} SELECT * FROM T;
            """
        else:
            return ''


    def execute(self, context) -> None:
        postgres_hook = PostgresHook(postgres_conn_id=self.redshift_conn_id)
        s3_hook = S3Hook(aws_conn_id=self.aws_conn_id, verify=self.verify)
        credentials = s3_hook.get_credentials()
        credentials_block = build_credentials_block(credentials)
        copy_options = '\n\t\t\t'.join(self.copy_options)

        copy_statement = self._build_copy_query(credentials_block, copy_options)
        after_statement = self.generate_after_query(postgres_hook)

        if self.truncate_table:
            delete_statement = f'DELETE FROM {self.schema}.{self.table};'
            sql = f"""
            BEGIN;
            {delete_statement}
            {copy_statement}
            COMMIT
            """
        elif after_statement != '':
            sql = f"""
            BEGIN;
            {copy_statement}
            {after_statement}
            COMMIT
            """
        else:
            sql = copy_statement

        self.log.info('Executing COPY command...')
        postgres_hook.run(sql, self.autocommit)
        self.log.info("COPY command complete...")r