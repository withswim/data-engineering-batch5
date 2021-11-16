{
          'table': 'user_session_summary',
          'schema': 'withswim',
          'main_sql': """
SELECT usc.*, t.ts
FROM raw_data.user_session_channel usc
LEFT JOIN raw_data.session_timestamp t ON t.sessionid = usc.sessionid
""",
          'input_check':
          [
            {
              'sql': 'SELECT COUNT(1) FROM raw_data.user_session_channel',
              'count': 100000
            },
          ],
          'output_check':
          [
            {
              'sql': 'SELECT COUNT(1) FROM {schema}.temp_{table}',
              'count': 101000
            }
          ],
}