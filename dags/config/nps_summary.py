{
          'table': 'nps_summary',
          'schema': 'withswim',
          'main_sql': """SELECT LEFT(created_at, 7) AS month,
  ROUND(SUM(CASE
    WHEN score >= 9 THEN 1 
    WHEN score <= 6 THEN -1 END)::float*100/COUNT(1), 2)
FROM withswim.nps
GROUP BY 1
ORDER BY 1;""",
          'input_check':
          [
            {
              'sql': 'SELECT COUNT(1) FROM withswim.nps',
              'count': 150000
            },
          ],
          'output_check':
          [
            {
              'sql': 'SELECT COUNT(1) FROM {schema}.temp_{table}',
              'count': 12
            }
          ],
}