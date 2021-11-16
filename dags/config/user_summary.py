{
          'table': 'user_summary',
          'schema': 'withswim',
          'main_sql': """SELECT usc.channel, usc.sessionid, usc.userid, sts.ts, st.refunded, st.amount
          FROM raw_data.user_session_channel AS usc
LEFT JOIN raw_data.session_timestamp AS sts ON usc.sessionid = sts.sessionid
LEFT JOIN raw_data.session_transaction AS st ON usc.sessionid = st.sessionid""",
          'input_check':
          [
            {
              'sql': 'SELECT COUNT(1) FROM raw_data.user_session_channel',
              'count': 101000
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