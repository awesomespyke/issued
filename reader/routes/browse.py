"""Browse and reader page routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response

from server.database import db_connection
from .. import repo
from .. import services
from .. import series
from ._common import templates, _library_title, _reader_auth_enabled

router = APIRouter(tags=["reader"])


def _show_explicit(request: Request) -> bool:
    """Whether explicit titles should appear in browse/discovery views."""
    return request.cookies.get("issued-show-explicit", "true").lower() != "false"

@router.post("/api/preferences/show-explicit", include_in_schema=False)
def set_show_explicit(show: bool) -> Response:
    response = Response(status_code=204)
    response.set_cookie(
        key="issued-show-explicit",
        value="true" if show else "false",
        path="/",
        samesite="lax",
    )
    return response


def _comic_reader_path(
    request: Request,
    comic: dict,
    folder_id: int | None,
    *,
    start_from_beginning: bool = False,
) -> str:
    path = request.url_for("reader_view", comic_uuid=comic["uuid"]).path
    query = []

    if folder_id is not None:
        query.append(f"series={folder_id}")

    if start_from_beginning or comic.get("is_completed"):
        query.append("start=1")

    return f"{path}?{'&'.join(query)}" if query else path


def _series_continue_context(request: Request, conn, folder_id: int) -> dict:
    state = series.get_continue_series(conn, folder_id)
    target = state.get("target")
    if target:
        state["target_url"] = _comic_reader_path(
            request,
            target,
            folder_id,
            start_from_beginning=not state["resume"],
        )
    return state


def _series_navigation_context(request: Request, conn, comic_uuid: str) -> dict | None:
    navigation = series.get_series_navigation(conn, comic_uuid)
    if navigation is None:
        return None

    series_name = navigation["series_name"]
    navigation["return_url"] = request.url_for(
        "browse_metadata_series",
        series_name=series_name,
    ).path

    for direction in ("previous", "next"):
        comic = navigation[direction]
        if comic:
            comic["reader_url"] = _comic_reader_path(request, comic, None)
            comic["thumbnail_url"] = request.url_for(
                "get_thumbnail", comic_uuid=comic["uuid"]
            ).path

    return navigation


# --- Browse: root ---


@router.get("/")
def browse_root(request: Request):
    """Browse the library as reading choices: series plus individual comics."""
    show_explicit = _show_explicit(request)

    with db_connection() as conn:
        library_entries = repo.get_library_entries(
            conn,
            show_explicit=show_explicit,
        )
        popular_tags = repo.get_popular_tags(
            conn,
            12,
            show_explicit=show_explicit,
        )
        continue_reading = repo.get_continue_reading_comics(
            conn,
            12,
            show_explicit=show_explicit,
        )

    return templates.TemplateResponse(
        request,
        "browser.html",
        {
            "title": _library_title(),
            "breadcrumbs": [],
            "folders": [],
            "comics": [],
            "grouped_comics": [],
            "library_entries": library_entries,
            "is_search": False,
            "show_last_added": False,
            "last_added_comics": [],
            "continue_reading_comics": continue_reading,
            "homepage_tags": popular_tags,
            "reader_auth_enabled": _reader_auth_enabled(),
            "folder_id": None,
            "series_continue": None,
            "is_leaf": False,
        },
    )

# --- Browse: search ---


@router.get("/search")
def browse_search(request: Request, q: str = ""):
    """Search comics by filename or metadata."""
    with db_connection() as conn:
        grouped_comics = repo.search_comics_grouped(conn, q, show_explicit=_show_explicit(request))

    return templates.TemplateResponse(
        request,
        "browser.html",
        {
            "title": f"Search: {q} - {_library_title()}",
            "breadcrumbs": [],
            "folders": [],
            "comics": [],
            "grouped_comics": grouped_comics,
            "is_search": True,
            "show_last_added": False,
            "last_added_comics": [],
            "continue_reading_comics": [],
            "reader_auth_enabled": _reader_auth_enabled(),
            "folder_id": None,
            "is_leaf": False,
        },
    )


# --- Browse: last added ---


@router.get("/recent")
@router.get("/last-added")
def browse_last_added(request: Request, limit: int = 50):
    """Browse last added comics."""
    with db_connection() as conn:
        comics = repo.get_last_added_comics(conn, min(limit, 200), show_explicit=_show_explicit(request))

    return templates.TemplateResponse(
        request,
        "browser.html",
        {
            "title": "Newly Added",
            "breadcrumbs": [],
            "folders": [],
            "comics": comics,
            "grouped_comics": [],
            "is_search": False,
            "show_last_added": False,
            "last_added_comics": [],
            "continue_reading_comics": [],
            "reader_auth_enabled": _reader_auth_enabled(),
            "folder_id": None,
            "is_leaf": False,
        },
    )


# --- Browse: folder ---


@router.get("/folder/{folder_id:int}")
def browse_folder(request: Request, folder_id: int):
    """Browse a folder: subfolders and comics."""
    with db_connection() as conn:
        folder = repo.get_folder(conn, folder_id)
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

        subfolders = repo.get_subfolders_with_item_count(conn, folder_id, show_explicit=_show_explicit(request))
        comics = repo.get_comics_in_folder(conn, folder_id, show_explicit=_show_explicit(request))
        breadcrumbs = repo.get_breadcrumbs_for_folder(conn, folder_id)
        is_leaf = repo.folder_is_leaf(conn, folder_id)
        series_continue = (
            _series_continue_context(request, conn, folder_id)
            if is_leaf
            else None
        )

    return templates.TemplateResponse(
        request,
        "browser.html",
        {
            "title": f"{folder['name']} - {_library_title()}",
            "breadcrumbs": breadcrumbs,
            "folders": subfolders,
            "comics": comics,
            "grouped_comics": [],
            "is_search": False,
            "show_last_added": False,
            "last_added_comics": [],
            "continue_reading_comics": [],
            "reader_auth_enabled": _reader_auth_enabled(),
            "folder_id": folder_id,
            "series_continue": series_continue,
            "is_leaf": is_leaf,
        },
    )


# --- Reader: single comic view ---


@router.get("/comic/{comic_uuid}")
def reader_view(
    request: Request,
    comic_uuid: str,
    start: bool = False,
    series_id: int | None = Query(default=None, alias="series"),
):
    """Reader page: open a comic and flip through pages."""
    comic = services.get_comic_by_uuid(comic_uuid)
    if not comic:
        if series_id is not None:
            with db_connection() as conn:
                folder = repo.get_folder(conn, series_id)
            if folder:
                return templates.TemplateResponse(
                    request,
                    "reader-error.html",
                    {
                        "title": f"Comic unavailable - {_library_title()}",
                        "message": "This comic is no longer available in the library.",
                        "return_url": request.url_for(
                            "browse_folder", folder_id=series_id
                        ).path,
                        "return_label": f"Back to {folder['name']}",
                        "reader_auth_enabled": _reader_auth_enabled(),
                    },
                    status_code=404,
                )
        raise HTTPException(status_code=404, detail="Comic not found")

    page_count = comic["page_count"] or 1
    with db_connection() as conn:
        initial_page = 1 if start else repo.get_initial_page(conn, comic_uuid, page_count)
        folder_id = repo.get_folder_id_for_comic(conn, comic_uuid)
        breadcrumbs = repo.get_breadcrumbs_for_folder(conn, folder_id) if folder_id else []
        metadata = repo.get_metadata(conn, comic_uuid)
        issue_title = (metadata or {}).get("title")
        issue_number = (metadata or {}).get("issue_number")
        progress = repo.get_progress(conn, comic_uuid)
        series_navigation = _series_navigation_context(request, conn, comic_uuid)

    return templates.TemplateResponse(
        request,
        "reader.html",
        {
            "title": f"{comic['filename']} - {_library_title()}",
            "breadcrumbs": breadcrumbs,
            "comic_uuid": comic_uuid,
            "comic_filename": comic["filename"],
            "issue_title": issue_title,
            "issue_number": issue_number,
            "page_count": page_count,
            "initial_page": initial_page,
            "was_completed": bool((progress or {}).get("is_completed")),
            "series_navigation": series_navigation,
            "reader_auth_enabled": _reader_auth_enabled(),
        },
    )


# --- Browse: metadata series ---


@router.get("/series")
def browse_series(request: Request):
    """Series index derived from embedded ComicInfo metadata."""
    with db_connection() as conn:
        series_rows = repo.get_all_series_with_counts(conn, show_explicit=_show_explicit(request))
    return templates.TemplateResponse(
        request,
        "series.html",
        {
            "title": f"Series - {_library_title()}",
            "series_rows": series_rows,
            "reader_auth_enabled": _reader_auth_enabled(),
        },
    )


@router.get("/series/{series_name:path}")
def browse_metadata_series(request: Request, series_name: str):
    """Browse comics belonging to an embedded metadata series."""
    with db_connection() as conn:
        comics = repo.get_comics_for_metadata_series(conn, series_name, show_explicit=_show_explicit(request))

    if not comics:
        raise HTTPException(status_code=404, detail="Series not found")

    return templates.TemplateResponse(
        request,
        "browser.html",
        {
            "title": series_name,
            "breadcrumbs": [],
            "folders": [],
            "comics": comics,
            "grouped_comics": [],
            "is_search": False,
            "show_last_added": False,
            "last_added_comics": [],
            "continue_reading_comics": [],
            "reader_auth_enabled": _reader_auth_enabled(),
            "folder_id": None,
            "is_leaf": False,
        },
    )


# --- Browse: creator ---


@router.get("/creator/{creator_name:path}")
def browse_creator(request: Request, creator_name: str):
    """Browse reading choices credited to a creator."""
    with db_connection() as conn:
        library_entries = repo.get_library_entries_for_creator(
            conn,
            creator_name,
            show_explicit=_show_explicit(request),
        )

    if not library_entries:
        raise HTTPException(status_code=404, detail="Creator not found")

    return templates.TemplateResponse(
        request,
        "browser.html",
        {
            "title": creator_name,
            "breadcrumbs": [],
            "folders": [],
            "comics": [],
            "grouped_comics": [],
            "library_entries": library_entries,
            "is_search": False,
            "show_last_added": False,
            "last_added_comics": [],
            "continue_reading_comics": [],
            "homepage_tags": [],
            "reader_auth_enabled": _reader_auth_enabled(),
            "folder_id": None,
            "is_leaf": False,
        },
    )

# --- Browse: tags ---


@router.get("/tags")
def browse_tags(request: Request):
    """Tag index: all tags with comic counts."""
    with db_connection() as conn:
        tag_rows = repo.get_all_tags_with_counts(conn, show_explicit=_show_explicit(request))
    return templates.TemplateResponse(
        request,
        "tags.html",
        {
            "title": f"Tags - {_library_title()}",
            "tag_rows": tag_rows,
            "reader_auth_enabled": _reader_auth_enabled(),
        },
    )


@router.get("/tags/{tag_name}")
def browse_tag(request: Request, tag_name: str):
    """Browse all comics with a given tag."""
    with db_connection() as conn:
        grouped_comics = repo.get_comics_for_tag(conn, tag_name, show_explicit=_show_explicit(request))
    return templates.TemplateResponse(
        request,
        "browser.html",
        {
            "title": f"Tag: {tag_name} - {_library_title()}",
            "breadcrumbs": [],
            "folders": [],
            "comics": [],
            "grouped_comics": grouped_comics,
            "is_search": True,
            "show_last_added": False,
            "last_added_comics": [],
            "continue_reading_comics": [],
            "reader_auth_enabled": _reader_auth_enabled(),
            "folder_id": None,
            "is_leaf": False,
        },
    )
