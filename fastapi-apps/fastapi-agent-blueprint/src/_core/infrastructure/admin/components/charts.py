"""ECharts builders for the admin design system.

The first chart surface in the repo (admin dashboard). Centralizes the chart
option shape, the theme-agnostic axis/grid colors, and the height token so
pages stay declarative and any future chart shares one styling source.

Charts render onto their own canvas, *outside* the ``--admin-*`` CSS variable
cascade, so dark-mode-flipping vars do not reach them. The neutral mid-tone
axis/grid colors (``AdminColors.CHART_*``) are chosen to read on both the light
and dark content surfaces without client-side dark-mode detection.
"""

from __future__ import annotations

from collections.abc import Sequence

from nicegui import ui

from src._core.config import settings
from src._core.infrastructure.admin.theme import (
    AdminClasses,
    AdminColors,
    palette_primary,
)


def bar_chart(categories: Sequence[str], values: Sequence[float]) -> ui.echart:
    """Vertical bar chart sized to the ``--admin-chart-height`` token.

    The container height comes from :data:`AdminClasses.CHART` (theme CSS), not
    an inline style, so it stays in the design-system token surface. The bar
    fill tracks the active ``ADMIN_THEME_PALETTE`` primary color so the chart
    matches the rest of the shell under any preset.
    """
    bar_color = palette_primary(settings.admin_theme_palette)
    return ui.echart(
        {
            "textStyle": {"color": AdminColors.CHART_AXIS},
            "tooltip": {"trigger": "axis"},
            "grid": {"left": 44, "right": 16, "top": 16, "bottom": 64},
            "xAxis": {
                "type": "category",
                "data": list(categories),
                "axisLabel": {"color": AdminColors.CHART_AXIS, "rotate": 30},
                "axisLine": {"lineStyle": {"color": AdminColors.CHART_AXIS}},
            },
            "yAxis": {
                "type": "value",
                "minInterval": 1,
                "axisLabel": {"color": AdminColors.CHART_AXIS},
                "splitLine": {"lineStyle": {"color": AdminColors.CHART_GRID}},
            },
            "series": [
                {
                    "type": "bar",
                    "data": list(values),
                    # Cap the width so a single / few categories render as tidy
                    "barMaxWidth": 56,
                    "itemStyle": {
                        "color": bar_color,
                        "borderRadius": [4, 4, 0, 0],
                    },
                }
            ],
        }
    ).classes(AdminClasses.CHART)
