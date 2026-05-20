from src._core.application.dtos.base_response import PaginationInfo


def make_pagination(total_items: int, page: int, page_size: int) -> PaginationInfo:
    total_pages = (total_items + page_size - 1) // page_size
    return PaginationInfo(
        current_page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_previous=page > 1,
        has_next=page < total_pages,
        next_page=page + 1 if page < total_pages else None,
        previous_page=page - 1 if page > 1 else None,
    )
