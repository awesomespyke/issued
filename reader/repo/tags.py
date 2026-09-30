"""Tag queries for the web reader."""

from __future__ import annotations

from .comics import _COMICS_WITH_META, explicit_filter
from .metadata import get_comic_id_by_uuid


def get_tags_for_comic(conn, comic_uuid: str) -> list[str]:
    """Sorted list of tag names for a comic."""
    comic_id = get_comic_id_by_uuid(conn, comic_uuid)
    if not comic_id:
        return []
    cur = conn.execute(
        """
        SELECT t.name FROM tags t
        INNER JOIN comic_tags ct ON ct.tag_id = t.id
        WHERE ct.comic_id = ?
        ORDER BY t.name COLLATE NOCASE
        """,
        (comic_id,),
    )
    return [row["name"] for row in cur.fetchall()]


def get_all_tags_with_counts(conn, show_explicit: bool = True) -> list[dict]:
    """All visible tags with their comic counts, sorted by name."""
    sql = """
        SELECT t.name, COUNT(ct.comic_id) AS comic_count
        FROM tags t
        INNER JOIN comic_tags ct ON ct.tag_id = t.id
        INNER JOIN metadata m ON m.comic_id = ct.comic_id
        WHERE
    """
    sql += explicit_filter(show_explicit)
    sql += """
        GROUP BY t.id
        HAVING COUNT(ct.comic_id) > 0
        ORDER BY t.name COLLATE NOCASE
    """
    cur = conn.execute(sql)
    return [dict(row) for row in cur.fetchall()]


def get_popular_tags(
    conn,
    limit: int = 12,
    show_explicit: bool = True,
) -> list[dict]:
    """Most-used visible tags for discovery on the Comics homepage."""
    sql = """
        SELECT t.name, COUNT(ct.comic_id) AS comic_count
        FROM tags t
        INNER JOIN comic_tags ct ON ct.tag_id = t.id
        INNER JOIN metadata m ON m.comic_id = ct.comic_id
        WHERE
    """
    sql += explicit_filter(show_explicit)
    sql += """
        GROUP BY t.id
        HAVING COUNT(ct.comic_id) > 0
        ORDER BY comic_count DESC, t.name COLLATE NOCASE
        LIMIT ?
    """
    cur = conn.execute(sql, (limit,))
    return [dict(row) for row in cur.fetchall()]

def get_comics_for_tag(
    conn,
    tag_name: str,
    show_explicit: bool = True,
) -> list[dict]:
    """All visible comics with the given tag, grouped by folder."""
    sql = (
        _COMICS_WITH_META
        + """
         INNER JOIN comic_tags ct ON ct.comic_id = c.id
         INNER JOIN tags t ON t.id = ct.tag_id
         WHERE t.name = ?
        """
    )
    sql += f" AND {explicit_filter(show_explicit)}"
    sql += " ORDER BY f.name, c.filename"

    cur = conn.execute(sql, (tag_name,))
    rows = [dict(row) for row in cur.fetchall()]

    groups: dict[str, list] = {}
    for row in rows:
        key = row["folder_name"] or ""
        groups.setdefault(key, [])
        groups[key].append(row)

    return [{"series": name, "comics": comics} for name, comics in groups.items()]
