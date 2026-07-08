# Unicontrol — Project Schedule Templates (PMI/PMP-aligned)

Two reusable baseline schedules to derive each job's internal plan from — the thing the
review meeting said is missing ("ningún proyecto ha tenido un plan interno"). One for
**machining** projects, one for **system-integration** projects.

They follow PMI/PMBOK practice: a deliverable-oriented **WBS**, **milestones**, explicit
**Finish-to-Start dependencies** so a **critical path** can be computed, a mandatory
**design-review gate** before fabrication, and **procurement lead-time** modeled as real
schedule activities (Unicontrol's #1 bottleneck) instead of being discovered late.

## How to read these
- **Dur** = working days, a *mid-size* baseline. Tune per job; capture actuals to improve estimates.
- **Pred** = predecessor WBS IDs (Finish-to-Start unless noted). Parallel tasks share a predecessor.
- **★** = milestone (zero duration, a checkpoint / gate).
- **`*`** = a **supplier/subcontractor lead time** — the value MUST come from a real quote at
  sell/quote time, not guessed. These usually sit on the critical path.
- **Etapa** maps to the 6 Odoo stages (Diseño → Revisión de Diseño → Compras → Maquinado →
  Ensamble → Entrega); Delay Watch then monitors the plan and flags slips.
- **Role**: Coordinación (PM), Diseño, Compras, Maquinado, Ensamble, Controles, Calidad, Ventas.

---

## Template A — Machining project (~6-week baseline)
Custom machined parts / fixtures / tooling batch.

| WBS | Task / Deliverable | Etapa | Dur | Pred | Role |
|----|----|----|----|----|----|
| 1 | **Initiation** | — | | | |
| 1.1 | Kickoff & PO/scope review | Diseño | 1 | — | Coordinación |
| 1.2 | Confirm drawings, tolerances, acceptance criteria | Diseño | 1 | 1.1 | Coordinación/Diseño |
| ★M1 | **Kickoff complete** | — | 0 | 1.2 | |
| 2 | **Engineering / Design** | | | | |
| 2.1 | Model / adapt parts in Fusion | Diseño | 5 | 1.2 | Diseño |
| 2.2 | Machining strategy & CAM feasibility | Diseño | 2 | 2.1 | Maquinado/Diseño |
| 2.3 | BOM: raw material + tooling + consumables | Diseño | 2 | 2.1 | Diseño/Compras |
| 2.4 | Identify long-lead material & request supplier lead times | Diseño | 1 | 2.3 | Compras |
| 3 | **Design Review (GATE)** | | | | |
| 3.1 | Internal design review (manufacturability, tolerances, setups) | Revisión de Diseño | 1 | 2.2, 2.3 | Diseño+Maquinado |
| 3.2 | Incorporate review changes | Revisión de Diseño | 1 | 3.1 | Diseño |
| ★M2 | **Design approved / released to production** | — | 0 | 3.2 | |
| 4 | **Procurement** | | | | |
| 4.1 | Issue POs — raw material | Compras | 1 | M2 | Compras |
| 4.2 | Raw material lead time `*` | Compras | 10`*` | 4.1 | Compras |
| 4.3 | Tooling / inserts procurement `*` | Compras | 5`*` | M2 | Compras |
| ★M3 | **Material & tooling received** | — | 0 | 4.2, 4.3 | |
| 5 | **Machining / Production** | | | | |
| 5.1 | CAM programming & post (overlaps procurement) | Maquinado | 3 | M2 | Maquinado |
| 5.2 | Fixturing / workholding prep | Maquinado | 2 | 5.1 | Maquinado |
| 5.3 | Machine setup & first article | Maquinado | 2 | 5.2, M3 | Maquinado |
| 5.4 | First-Article Inspection (FAI) | Maquinado | 1 | 5.3 | Calidad |
| ★M4 | **First article approved** | — | 0 | 5.4 | |
| 5.5 | Production run / batch machining | Maquinado | 6 | M4 | Maquinado |
| 5.6 | Deburr / finishing | Maquinado | 2 | 5.5 | Maquinado |
| 6 | **Quality** | | | | |
| 6.1 | Final dimensional inspection / QC | Ensamble | 2 | 5.6 | Calidad |
| 6.2 | Surface treatment / coating (outsourced, if req.) `*` | Compras | 5`*` | 6.1 | Compras |
| 6.3 | Incoming inspection of treated parts | Ensamble | 1 | 6.2 | Calidad |
| 7 | **Delivery & Closeout** | | | | |
| 7.1 | Packaging & documentation | Entrega | 1 | 6.3 | Ensamble |
| 7.2 | Delivery to customer | Entrega | 1 | 7.1 | Ventas |
| ★M5 | **Parts delivered** | — | 0 | 7.2 | |
| 7.3 | Lessons learned / capture actual durations | Entrega | 1 | 7.2 | Coordinación |
| ★M6 | **Project closed** | — | 0 | 7.3 | |

**Typical critical path:** 1.1→1.2→2.1→2.3→3.1→3.2→4.1→**4.2 (material lead)**→M3→5.3→5.4→5.5→5.6→6.1→(6.2)→7.1→7.2.
Material lead time (4.2) is the usual swing item — confirm it at quote time.

---

## Template B — System-integration project (~16-week baseline)
Custom automation cell (e.g., conveyor + robot + controls panel).

| WBS | Task / Deliverable | Etapa | Dur | Pred | Role |
|----|----|----|----|----|----|
| 1 | **Initiation & Requirements** | | | | |
| 1.1 | Kickoff & contract/PO review | Diseño | 1 | — | Coordinación |
| 1.2 | Requirements capture (URS) | Diseño | 3 | 1.1 | Coordinación/Diseño |
| 1.3 | Confirm scope, interfaces, FAT/SAT acceptance criteria | Diseño | 2 | 1.2 | Coordinación |
| ★M1 | **Requirements frozen** | — | 0 | 1.3 | |
| 2 | **Concept / Preliminary Design** | | | | |
| 2.1 | Concept layout & sequence of operations | Diseño | 4 | M1 | Diseño |
| 2.2 | Preliminary mechanical concept | Diseño | 3 | 2.1 | Diseño |
| 2.3 | Preliminary electrical/controls architecture | Diseño | 3 | 2.1 | Controles |
| 2.4 | Preliminary design review w/ customer | Revisión de Diseño | 1 | 2.2, 2.3 | Coordinación |
| ★M2 | **Concept approved** | — | 0 | 2.4 | |
| 3 | **Detailed Design (parallel disciplines)** | | | | |
| 3.1 | Detailed mechanical design (frames, conveyors, guarding) | Diseño | 10 | M2 | Diseño |
| 3.2 | Detailed electrical design (panel, I/O, wiring) | Diseño | 8 | M2 | Controles |
| 3.3 | Controls design (PLC/HMI/robot program spec) | Diseño | 6 | M2 | Controles |
| 3.4 | Full BOM (mech + electrical + pneumatic + components) | Diseño | 3 | 3.1, 3.2 | Diseño/Compras |
| 3.5 | Identify long-lead components & get supplier lead times | Diseño | 2 | 3.4 | Compras |
| 4 | **Design Review (GATE)** | | | | |
| 4.1 | Internal cross-discipline design review | Revisión de Diseño | 2 | 3.1, 3.2, 3.3, 3.4 | All leads |
| 4.2 | Incorporate changes / release for build | Revisión de Diseño | 2 | 4.1 | Diseño/Controles |
| ★M3 | **Design approved / released** | — | 0 | 4.2 | |
| 5 | **Procurement** | | | | |
| 5.1 | Issue POs — long-lead (robot, PLC, drives, servos) | Compras | 2 | 3.5 | Compras |
| 5.2 | Long-lead component lead time `*` | Compras | 25`*` | 5.1 | Compras |
| 5.3 | Issue POs — standard components & raw material | Compras | 2 | M3 | Compras |
| 5.4 | Standard components lead time `*` | Compras | 10`*` | 5.3 | Compras |
| ★M4 | **All components received** | — | 0 | 5.2, 5.4 | |
| 6 | **Fabrication & Machining** | | | | |
| 6.1 | Machine custom parts (see Template A) | Maquinado | 10 | M3 | Maquinado |
| 6.2 | Fabricate frames / structures | Maquinado | 8 | M3 | Maquinado |
| 6.3 | Surface treatment / paint `*` | Compras | 5`*` | 6.1, 6.2 | Compras |
| 7 | **Mechanical Assembly** | | | | |
| 7.1 | Mechanical assembly of cell / conveyors | Ensamble | 8 | 6.3, M4 | Ensamble |
| 7.2 | Pneumatics & sensors install | Ensamble | 4 | 7.1 | Ensamble |
| ★M5 | **Mechanical assembly complete** | — | 0 | 7.2 | |
| 8 | **Electrical & Controls** | | | | |
| 8.1 | Panel build & wiring | Ensamble | 6 | 5.4 | Controles |
| 8.2 | Field wiring & I/O termination | Ensamble | 5 | 7.2, 8.1 | Controles |
| 8.3 | PLC / HMI programming (parallel w/ assembly) | Ensamble | 10 | 8.1 | Controles |
| 8.4 | Robot programming / integration | Ensamble | 8 | 7.1, 8.3 | Controles |
| ★M6 | **Power-on / I/O check complete** | — | 0 | 8.2 | |
| 9 | **Integration & Test** | | | | |
| 9.1 | Dry run / sequence debug | Ensamble | 5 | 8.2, 8.3, 8.4 | Controles/Ensamble |
| 9.2 | Internal integration test | Ensamble | 3 | 9.1 | All leads |
| 9.3 | FAT (Factory Acceptance Test) w/ customer | Revisión de Diseño | 2 | 9.2 | Coordinación |
| ★M7 | **FAT passed** | — | 0 | 9.3 | |
| 10 | **Delivery, Install & Commissioning** | | | | |
| 10.1 | Disassembly & packaging | Entrega | 2 | M7 | Ensamble |
| 10.2 | Shipping to site `*` | Entrega | 2`*` | 10.1 | Compras/Logística |
| 10.3 | Installation & reassembly at site | Entrega | 4 | 10.2 | Ensamble |
| 10.4 | Commissioning & SAT (Site Acceptance Test) | Entrega | 3 | 10.3 | Controles/Coordinación |
| ★M8 | **SAT passed / accepted** | — | 0 | 10.4 | |
| 11 | **Closeout** | | | | |
| 11.1 | As-built docs, manuals, training | Entrega | 3 | M8 | Diseño/Coordinación |
| 11.2 | Handover & warranty start | Entrega | 1 | 11.1 | Ventas |
| 11.3 | Lessons learned / capture actuals | Entrega | 1 | 11.2 | Coordinación |
| ★M9 | **Project closed** | — | 0 | 11.3 | |

**Typical critical path:** requirements → concept → detailed design → M3 → **5.1→5.2 (long-lead
components)** → M4 → mechanical assembly → controls integration (8.3/8.4) → 9.1→9.2→9.3 → install →
SAT. Long-lead procurement (5.2) and controls integration usually govern the delivery date —
which is exactly why 3.5/5.1/5.2 exist as first-class tasks defined at quote time.

---

## Using these in Odoo + Delay Watch
1. Create one Odoo **Project template** per type with these tasks, set each task's **planned
   dates** (from Dur + Pred, back-scheduled from the delivery date) and **"Blocked by"** links.
2. Fill every `*` lead time from a **real supplier quote** before the plan is baselined.
3. Instantiate the template per job; assign a task **Assignee** and a project **Manager** so
   Delay Watch can route alerts.
4. `delay_watch.py` then computes the critical path and raises internal alerts when a task slips —
   especially the lead-time and integration tasks that drive the delivery date.
