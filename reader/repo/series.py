"""Series discovery queries for the web reader."""

from __future__ import annotations

from .comics import explicit_filter


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


def get_all_series_with_counts(conn, show_explicit: bool = True) -> list[dict]:
    """All embedded metadata series with comic counts."""
    sql = """
        SELECT m.series AS name, COUNT(c.id) AS comic_count
        FROM metadata m
        INNER JOIN comics c ON c.id = m.comic_id
        WHERE m.series IS NOT NULL
          AND TRIM(m.series) != ''
    """
    sql += f" AND {explicit_filter(show_explicit)}"
    sql += """
        GROUP BY m.series COLLATE NOCASE
        ORDER BY m.series COLLATE NOCASE
    """
    cur = conn.execute(sql)
    return [dict(row) for row in cur.fetchall()]


def get_comics_for_metadata_series(
    conn,
    series_name: str,
    show_explicit: bool = True,
) -> list[dict]:
    """All comics belonging to an embedded metadata series, in issue order."""
    sql = _COMICS_WITH_META + """
        WHERE m.series = ? COLLATE NOCASE
    """
    sql += f" AND {explicit_filter(show_explicit)}"
    sql += """
        ORDER BY
            CASE WHEN m.issue_number IS NULL THEN 1 ELSE 0 END,
            m.issue_number,
            c.filename COLLATE NOCASE
    """
    cur = conn.execute(sql, (series_name,))
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

def get_library_entries(conn, show_explicit: bool = True) -> list[dict]:
    """Return the library as reading choices: multi-comic series plus individual comics."""
    visibility = explicit_filter(show_explicit)

    cur = conn.execute(
        f"""
        WITH visible_comics AS (
            SELECT
                c.id,
                c.uuid,
                c.filename,
                c.page_count,
                c.thumbnail_generated,
                (m.is_completed = 1) AS is_completed,
                m.title,
                NULLIF(TRIM(m.series), '') AS series,
                m.issue_number,
                m.publisher,
                m.year,
                m.artist,
                m.writer,
                m.penciller,
                m.score,
                m.last_read_at,
                m.age_rating
            FROM comics c
            LEFT JOIN metadata m ON m.comic_id = c.id
            WHERE {visibility}
        ),
        series_counts AS (
            SELECT series, COUNT(*) AS comic_count
            FROM visible_comics
            WHERE series IS NOT NULL
            GROUP BY series COLLATE NOCASE
        )
        SELECT
            'series' AS entry_type,
            MIN(v.uuid) AS uuid,
            NULL AS filename,
            NULL AS page_count,
            NULL AS is_completed,
            s.series AS title,
            s.series AS series,
            NULL AS issue_number,
            NULL AS publisher,
            NULL AS year,
            NULL AS artist,
            NULL AS writer,
            NULL AS penciller,
            NULL AS score,
            NULL AS last_read_at,
            NULL AS age_rating,
            s.comic_count AS comic_count
        FROM series_counts s
        JOIN visible_comics v ON v.series = s.series COLLATE NOCASE
        WHERE s.comic_count >= 2
        GROUP BY s.series COLLATE NOCASE

        UNION ALL

        SELECT
            'comic' AS entry_type,
            v.uuid,
            v.filename,
            v.page_count,
            v.is_completed,
            v.title,
            v.series,
            v.issue_number,
            v.publisher,
            v.year,
            v.artist,
            v.writer,
            v.penciller,
            v.score,
            v.last_read_at,
            v.age_rating,
            1 AS comic_count
        FROM visible_comics v
        LEFT JOIN series_counts s
            ON v.series = s.series COLLATE NOCASE
        WHERE v.series IS NULL
           OR COALESCE(s.comic_count, 0) < 2

        ORDER BY title COLLATE NOCASE
        """
    )

    return [dict(row) for row in cur.fetchall()]

def get_library_entries_for_creator(
    conn,
    creator_name: str,
    show_explicit: bool = True,
) -> list[dict]:
    """Reading choices containing an exact writer, penciller, or artist credit."""
    creator_key = creator_name.strip().casefold()

    def credited(value: str | None) -> bool:
        if not value:
            return False
        return any(
            name.strip().casefold() == creator_key
            for name in value.split(",")
        )

    entries = get_library_entries(conn, show_explicit=show_explicit)
    matched = []

    for entry in entries:
        if entry["entry_type"] == "comic":
            if any(credited(entry.get(field)) for field in ("writer", "penciller", "artist")):
                matched.append(entry)
            continue

        comics = get_comics_for_metadata_series(
            conn,
            entry["series"],
            show_explicit=show_explicit,
        )
        if any(
            credited(comic.get(field))
            for comic in comics
            for field in ("writer", "penciller", "artist")
        ):
            matched.append(entry)

    return matched
