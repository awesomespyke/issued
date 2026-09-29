"""Series discovery queries for the web reader."""

from __future__ import annotations


_COMICS_WITH_META = """
    SELECT
        c.id,
        c.uuid,
        c.filename,
        c.folder_id,
        c.page_count,
        c.thumbnail_generated,
        m.title,
        m.series,
        m.issue_number,
        m.publisher,
        m.year,
        m.writer,
        m.artist
    FROM comics c
    INNER JOIN metadata m ON m.comic_id = c.id
"""


def get_all_series_with_counts(conn) -> list[dict]:
    """All embedded metadata series with comic counts."""
    cur = conn.execute(
        """
        SELECT m.series AS name, COUNT(c.id) AS comic_count
        FROM metadata m
        INNER JOIN comics c ON c.id = m.comic_id
        WHERE m.series IS NOT NULL
          AND TRIM(m.series) != ''
        GROUP BY m.series COLLATE NOCASE
        ORDER BY m.series COLLATE NOCASE
        """
    )
    return [dict(row) for row in cur.fetchall()]


def get_comics_for_metadata_series(conn, series_name: str) -> list[dict]:
    """All comics belonging to an embedded metadata series, in issue order."""
    cur = conn.execute(
        _COMICS_WITH_META
        + """
        WHERE m.series = ? COLLATE NOCASE
        ORDER BY
            CASE WHEN m.issue_number IS NULL THEN 1 ELSE 0 END,
            m.issue_number,
            c.filename COLLATE NOCASE
        """,
        (series_name,),
    )
    return [dict(row) for row in cur.fetchall()]

def get_metadata_series_for_comic(conn, comic_uuid: str) -> tuple[str, list[dict]] | None:
    """Return a comic's metadata series and all comics in that series."""
    cur = conn.execute(
        """
        SELECT m.series
        FROM comics c
        INNER JOIN metadata m ON m.comic_id = c.id
        WHERE c.uuid = ?
          AND m.series IS NOT NULL
          AND TRIM(m.series) != ''
        """,
        (comic_uuid,),
    )
    row = cur.fetchone()
    if not row:
        return None

    series_name = row["series"]

    cur = conn.execute(
        """
        SELECT
            c.uuid,
            c.filename,
            c.page_count,
            c.folder_id,
            m.title,
            m.series,
            m.issue_number,
            m.current_page,
            m.last_read_at,
            COALESCE(m.is_completed, 0) AS is_completed
        FROM comics c
        INNER JOIN metadata m ON m.comic_id = c.id
        WHERE m.series = ? COLLATE NOCASE
        ORDER BY
            CASE WHEN m.issue_number IS NULL THEN 1 ELSE 0 END,
            m.issue_number,
            c.filename COLLATE NOCASE
        """,
        (series_name,),
    )

    return series_name, [dict(row) for row in cur.fetchall()]