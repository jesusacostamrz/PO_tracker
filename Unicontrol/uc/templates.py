"""PMI/PMP baseline WBS for machining + system-integration projects.

See docs/schedule-templates.md for the rationale. Each item is:
    (wbs, name, etapa, duration_days, [predecessor wbs ids], is_milestone)
Consumed by scripts/load_templates.py (creates Odoo projects) and the Gantt artifact.
"""
from __future__ import annotations

# (wbs, name, etapa, dur, preds, milestone)
MACHINING = [
    ("1.1", "Kickoff y revisión de OC/alcance", "Diseño", 1, [], False),
    ("1.2", "Confirmar planos, tolerancias y criterios de aceptación", "Diseño", 1, ["1.1"], False),
    ("M1", "Kickoff completo", "—", 0, ["1.2"], True),
    ("2.1", "Modelar/adaptar piezas en Fusion", "Diseño", 5, ["1.2"], False),
    ("2.2", "Estrategia de maquinado y viabilidad CAM", "Diseño", 2, ["2.1"], False),
    ("2.3", "BOM: material, herramienta y consumibles", "Diseño", 2, ["2.1"], False),
    ("2.4", "Identificar material de largo plazo y pedir tiempos de proveedor", "Diseño", 1, ["2.3"], False),
    ("3.1", "Revisión de diseño interna (manufacturabilidad, tolerancias, setups)", "Revisión de Diseño", 1, ["2.2", "2.3"], False),
    ("3.2", "Incorporar cambios de la revisión", "Revisión de Diseño", 1, ["3.1"], False),
    ("M2", "Diseño aprobado / liberado a producción", "—", 0, ["3.2"], True),
    ("4.1", "Emitir OC — materia prima", "Compras", 1, ["M2"], False),
    ("4.2", "Tiempo de entrega de material (proveedor) *", "Compras", 10, ["4.1"], False),
    ("4.3", "Compra de herramienta / insertos *", "Compras", 5, ["M2"], False),
    ("M3", "Material y herramienta recibidos", "—", 0, ["4.2", "4.3"], True),
    ("5.1", "Programación CAM y post", "Maquinado", 3, ["M2"], False),
    ("5.2", "Preparación de fixtures / sujeción", "Maquinado", 2, ["5.1"], False),
    ("5.3", "Setup de máquina y primera pieza", "Maquinado", 2, ["5.2", "M3"], False),
    ("5.4", "Inspección de primera pieza (FAI)", "Maquinado", 1, ["5.3"], False),
    ("M4", "Primera pieza aprobada", "—", 0, ["5.4"], True),
    ("5.5", "Corrida de producción / maquinado del lote", "Maquinado", 6, ["M4"], False),
    ("5.6", "Rebabeo / acabado", "Maquinado", 2, ["5.5"], False),
    ("6.1", "Inspección dimensional final / QC", "Ensamble", 2, ["5.6"], False),
    ("6.2", "Tratamiento superficial / recubrimiento (externo, si aplica) *", "Compras", 5, ["6.1"], False),
    ("6.3", "Inspección de recepción de piezas tratadas", "Ensamble", 1, ["6.2"], False),
    ("7.1", "Empaque y documentación", "Entrega", 1, ["6.3"], False),
    ("7.2", "Entrega al cliente", "Entrega", 1, ["7.1"], False),
    ("M5", "Piezas entregadas", "—", 0, ["7.2"], True),
    ("7.3", "Lecciones aprendidas / capturar duraciones reales", "Entrega", 1, ["7.2"], False),
    ("M6", "Proyecto cerrado", "—", 0, ["7.3"], True),
]

INTEGRATION = [
    ("1.1", "Kickoff y revisión de contrato/OC", "Diseño", 1, [], False),
    ("1.2", "Captura de requerimientos (URS)", "Diseño", 3, ["1.1"], False),
    ("1.3", "Confirmar alcance, interfaces y criterios FAT/SAT", "Diseño", 2, ["1.2"], False),
    ("M1", "Requerimientos congelados", "—", 0, ["1.3"], True),
    ("2.1", "Layout conceptual y secuencia de operación", "Diseño", 4, ["M1"], False),
    ("2.2", "Concepto mecánico preliminar", "Diseño", 3, ["2.1"], False),
    ("2.3", "Arquitectura eléctrica/control preliminar", "Diseño", 3, ["2.1"], False),
    ("2.4", "Revisión de diseño preliminar con cliente", "Revisión de Diseño", 1, ["2.2", "2.3"], False),
    ("M2", "Concepto aprobado", "—", 0, ["2.4"], True),
    ("3.1", "Diseño mecánico detallado (marcos, transportadores, guardas)", "Diseño", 10, ["M2"], False),
    ("3.2", "Diseño eléctrico detallado (tablero, I/O, cableado)", "Diseño", 8, ["M2"], False),
    ("3.3", "Diseño de control (especificación PLC/HMI/robot)", "Diseño", 6, ["M2"], False),
    ("3.4", "BOM completo (mec + eléctrico + neumático + componentes)", "Diseño", 3, ["3.1", "3.2"], False),
    ("3.5", "Identificar componentes de largo plazo y tiempos de proveedor", "Diseño", 2, ["3.4"], False),
    ("4.1", "Revisión de diseño interdisciplinaria interna", "Revisión de Diseño", 2, ["3.1", "3.2", "3.3", "3.4"], False),
    ("4.2", "Incorporar cambios / liberar para fabricación", "Revisión de Diseño", 2, ["4.1"], False),
    ("M3", "Diseño aprobado / liberado", "—", 0, ["4.2"], True),
    ("5.1", "Emitir OC — largo plazo (robot, PLC, drives, servos)", "Compras", 2, ["3.5"], False),
    ("5.2", "Tiempo de entrega de componentes de largo plazo *", "Compras", 25, ["5.1"], False),
    ("5.3", "Emitir OC — componentes estándar y materia prima", "Compras", 2, ["M3"], False),
    ("5.4", "Tiempo de entrega de componentes estándar *", "Compras", 10, ["5.3"], False),
    ("M4", "Todos los componentes recibidos", "—", 0, ["5.2", "5.4"], True),
    ("6.1", "Maquinar piezas a medida (ver plantilla de maquinado)", "Maquinado", 10, ["M3"], False),
    ("6.2", "Fabricar marcos / estructuras", "Maquinado", 8, ["M3"], False),
    ("6.3", "Tratamiento superficial / pintura *", "Compras", 5, ["6.1", "6.2"], False),
    ("7.1", "Ensamble mecánico de la celda / transportadores", "Ensamble", 8, ["6.3", "M4"], False),
    ("7.2", "Instalación de neumática y sensores", "Ensamble", 4, ["7.1"], False),
    ("M5", "Ensamble mecánico completo", "—", 0, ["7.2"], True),
    ("8.1", "Armado de tablero y cableado", "Ensamble", 6, ["5.4"], False),
    ("8.2", "Cableado de campo y terminación de I/O", "Ensamble", 5, ["7.2", "8.1"], False),
    ("8.3", "Programación PLC / HMI", "Ensamble", 10, ["8.1"], False),
    ("8.4", "Programación de robot / integración", "Ensamble", 8, ["7.1", "8.3"], False),
    ("M6", "Energización / verificación de I/O completa", "—", 0, ["8.2"], True),
    ("9.1", "Marcha en vacío / depuración de secuencia", "Ensamble", 5, ["8.2", "8.3", "8.4"], False),
    ("9.2", "Prueba de integración interna", "Ensamble", 3, ["9.1"], False),
    ("9.3", "FAT (prueba de aceptación en fábrica) con cliente", "Revisión de Diseño", 2, ["9.2"], False),
    ("M7", "FAT aprobada", "—", 0, ["9.3"], True),
    ("10.1", "Desensamble y empaque", "Entrega", 2, ["M7"], False),
    ("10.2", "Envío a sitio *", "Entrega", 2, ["10.1"], False),
    ("10.3", "Instalación y reensamble en sitio", "Entrega", 4, ["10.2"], False),
    ("10.4", "Puesta en marcha y SAT", "Entrega", 3, ["10.3"], False),
    ("M8", "SAT aprobada / aceptada", "—", 0, ["10.4"], True),
    ("11.1", "Documentación as-built, manuales, capacitación", "Entrega", 3, ["M8"], False),
    ("11.2", "Entrega formal e inicio de garantía", "Entrega", 1, ["11.1"], False),
    ("11.3", "Lecciones aprendidas / capturar reales", "Entrega", 1, ["11.2"], False),
    ("M9", "Proyecto cerrado", "—", 0, ["11.3"], True),
]

TEMPLATES = {
    "[PLANTILLA] Proyecto de Maquinado": MACHINING,
    "[PLANTILLA] Integración de Sistemas": INTEGRATION,
}

from collections import Counter

PHASE_NAMES = {
    "[PLANTILLA] Proyecto de Maquinado": {
        "1": "1. Inicio y alcance",
        "2": "2. Diseño",
        "3": "3. Revisión de diseño",
        "4": "4. Compras y materiales",
        "5": "5. Maquinado",
        "6": "6. Inspección y acabado",
        "7": "7. Entrega y cierre",
    },
    "[PLANTILLA] Integración de Sistemas": {
        "1": "1. Requerimientos",
        "2": "2. Diseño conceptual",
        "3": "3. Diseño detallado",
        "4": "4. Revisión de diseño",
        "5": "5. Compras",
        "6": "6. Fabricación",
        "7": "7. Ensamble mecánico",
        "8": "8. Ensamble eléctrico y control",
        "9": "9. Pruebas y FAT",
        "10": "10. Entrega y SAT",
        "11": "11. Cierre",
    },
}


def phase_groups(items, phase_names) -> list[dict]:
    """Group non-milestone template rows by WBS-major into ordered phases."""
    order: list[str] = []
    groups: dict[str, dict] = {}
    etapas: dict[str, list[str]] = {}
    for (w, _name, etapa, _dur, _preds, mile) in items:
        if mile:
            continue
        major = w.split(".")[0]
        if major not in groups:
            groups[major] = {"major": major, "name": phase_names.get(major, f"Fase {major}"),
                             "etapa": "", "leaves": []}
            etapas[major] = []
            order.append(major)
        groups[major]["leaves"].append(w)
        etapas[major].append(etapa)
    for major in order:
        groups[major]["etapa"] = Counter(etapas[major]).most_common(1)[0][0]
    return [groups[m] for m in order]
