import snowflake.connector

_conn = None


def get_connection():
    global _conn
    if _conn is None or _conn.is_closed():
        _conn = snowflake.connector.connect(
            connection_name="zendesk-global",
        )
    return _conn


def execute_query(sql):
    conn = get_connection()
    cur = conn.cursor(snowflake.connector.DictCursor)
    cur.execute(sql)
    return cur.fetchall()


def close():
    global _conn
    if _conn and not _conn.is_closed():
        _conn.close()
        _conn = None
