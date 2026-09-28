"""reader.repo â€“ feature-domain repository sub-package.

Re-exports every public function so existing callers continue to work unchanged.
"""

from .folders import (
    get_top_folders,
    add_folder_item_counts,
    get_folder,
    get_subfolders_with_item_count,
    get_breadcrumbs_for_folder,
    get_folder_preview_thumbnails,
    folder_is_leaf,
)
from .comics import (
    get_comics_in_folder,
    get_last_added_comics,
    get_continue_reading_comics,
    get_series_comics,
    get_series_comics_for_comic,
    search_comics,
    search_comics_grouped,
)
from .metadata import (
    get_comic_id_by_uuid,
    get_folder_id_for_comic,
    get_initial_page,
    get_metadata,
    ensure_metadata_row,
    update_metadata,
)
from .progress import (
    get_progress,
    update_progress,
    clear_progress,
    mark_all_comics_in_folder_completed,
    toggle_comic_completed,
)
from .tags import (
    get_tags_for_comic,
    get_all_tags_with_counts,
    get_comics_for_tag,
)

from .series import (
    get_all_series_with_counts,
    get_comics_for_metadata_series,
)

__all__ = [
    "get_top_folders", "add_folder_item_counts", "get_folder",
    "get_subfolders_with_item_count", "get_breadcrumbs_for_folder",
    "get_folder_preview_thumbnails", "folder_is_leaf",
    "get_comics_in_folder", "get_last_added_comics", "get_continue_reading_comics",
    "get_series_comics", "get_series_comics_for_comic",
    "search_comics", "search_comics_grouped",
    "get_comic_id_by_uuid", "get_folder_id_for_comic", "get_initial_page",
    "get_metadata", "ensure_metadata_row", "update_metadata",
    "get_progress", "update_progress", "clear_progress",
    "mark_all_comics_in_folder_completed", "toggle_comic_completed",
    "get_tags_for_comic", "get_all_tags_with_counts",
    "get_comics_for_tag",
    "get_all_series_with_counts", "get_comics_for_metadata_series",
]
