"""Brand colour mapping shared by every dashboard renderer.

One source of truth so the static HTML, the Streamlit app, and the PNG export
all colour each competitor consistently. Colours are brand-associated but also
chosen to stay visually distinct on a chart. Unknown competitors fall back to a
deterministic palette so the same name always gets the same colour.
"""
from __future__ import annotations

# Competitor name -> hex colour. Keys match the `name` used in config.yaml.
BRAND_COLORS: dict[str, str] = {
    "New Balance Kids": "#CF0A2C",  # NB red
    "Fila Kids": "#002A6D",         # Fila navy
    "Adidas Kids": "#1D1D1B",       # near-black
    "Nike Kids": "#FF6A00",         # orange accent
    "Play Kids": "#00A86B",         # green
}

# Deterministic fallback palette for any competitor/keyword not in BRAND_COLORS.
_FALLBACK = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]


def color_for(name: str) -> str:
    """Return a stable hex colour for a competitor (or keyword/group) name."""
    if name in BRAND_COLORS:
        return BRAND_COLORS[name]
    # Stable hash -> palette index so the same name is always the same colour.
    idx = sum(ord(ch) for ch in name) % len(_FALLBACK)
    return _FALLBACK[idx]


def color_map(names: list[str]) -> dict[str, str]:
    """Convenience: build a {name: colour} map for a list of names."""
    return {n: color_for(n) for n in names}
