import duckdb


def connect() -> duckdb.DuckDBPyConnection:
    """DuckDB connection with the progress bar off (it garbles log output when piped)."""
    con = duckdb.connect()
    con.execute("SET enable_progress_bar = false")
    return con
