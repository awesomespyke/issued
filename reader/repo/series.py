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
