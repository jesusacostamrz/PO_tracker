"""Phase (etapa) colors shared by the template artifact and the customer Gantt."""
from __future__ import annotations

ACCENT = "#d97b12"

ETAPA_COLOR = {
    "Diseño": "#3f7cac",
    "Revisión de Diseño": "#6c8f3f",
    "Compras": "#c07a1e",
    "Maquinado": "#7a6cae",
    "Ensamble": "#2f938a",
    "Entrega": "#b5495b",
    "—": "#8a99a8",
}

# Distinct, cycling colors for customer phase bars (assigned in timeline order).
PHASE_PALETTE = [
    "#3f7cac", "#6c8f3f", "#c07a1e", "#7a6cae", "#2f938a", "#b5495b",
    "#4a6d8c", "#8a6d3b", "#5b7f9c", "#9c5b7f", "#3b8a6d",
]

# etapa → Odoo project.tags color index (0–11) for a legible kanban.
ETAPA_TAG_COLOR = {
    "Diseño": 4,
    "Revisión de Diseño": 10,
    "Compras": 2,
    "Maquinado": 5,
    "Ensamble": 7,
    "Entrega": 9,
    "—": 8,
}
