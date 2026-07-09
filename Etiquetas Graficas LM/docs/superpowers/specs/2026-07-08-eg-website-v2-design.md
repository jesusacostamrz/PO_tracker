# EG Website v2 — Feedback-Corrected Redesign

**Date:** 2026-07-08
**Project:** `Etiquetas Graficas LM/website` (React 19 + Vite + Tailwind 3 + GSAP + react-router 6 — all already installed; no new dependencies)
**Goal:** Rebuild the reviewed prototype's sections into this codebase, corrected per the customer's feedback (`feedback/feedback de prototipo.pdf`), matching or beating their Lovable sample. Customer liked: "se siente como una app, fluida y no anticuada" — preserve that feel.

**Context note:** the committed `src/App.jsx` is an OLDER design than the prototype the customer reviewed. The reviewed blocks (Historia, Materiales, Cotizador, Envío) must be (re)built here, with the feedback applied from the start.

## Pages & routing

| Route | Content |
|---|---|
| `/` | Main single-page flow (sections below) |
| `/sectores` | Full sectors catalog page (feedback: "botón que nos vincule a otra página con todos los sectores") |
| `/privacidad`, `/terminos` | Keep existing |

Material ficha técnica opens as a modal over `/`, with an expanded detail view inside the modal (no separate route needed).

## Section order on `/`

### 1. Hero
- Minimal copy: `Tu marca,` (sans, bold) + `en cada etiqueta.` (serif italic — customer explicitly asked to keep this typography mix), ONE short supporting line, WhatsApp CTA + phone button, 3 checkmark micro-claims max.
- **No logo card** (logo already in navbar). Replaced by a Higgsfield-generated **cinematic motion loop** (flexo press printing branded EG labels / labeled products) as the hero visual — the wow element.
- Keep app-like fluidity: GSAP entrance, smooth scroll.

### 2. Materiales — "¿En qué material imprimimos tus etiquetas?"
- Promoted to block 2 (replaces Historia's position — feedback: "ir directamente a lo que vendemos").
- Sub-copy reduced to: "Cada producto pide su material."
- Material selector list (BOPP Blanco, BOPP Transparente, BOPP Metalizado, Papel Couché, Papel Kraft, Térmicas). Selecting one opens a **summary popup**: material photo, 3 plain-language traits (e.g. Impermeable / Gran claridad / Acabado brillante), **"Ideal para: …" chips**, and a button to the full **ficha técnica** (the detailed data — adhesivo, temperatura, acabado — lives there, not on the main page).

### 3. Sectores — "Soluciones para cada sector"
- Title per feedback. Carousel/cards of sectors in customer's priority order:
  1. Alimentos y bebidas, 2. Agrícola, 3. Retail y comercio, 4. Congelados y enlatados, 5. Industrial, 6. Farmacéutica, 7. Cosmética.
- Each card: photoreal Higgsfield image of products wearing "etiquetas gráficas de Los Mochis" labels (like the feedback examples), sector name, one line. Minimal text.
- "Ver todos los sectores" → `/sectores` (each sector expanded with image + typical applications).

### 4. Cotizador — "Arma tu cotización"
- Existing flow (forma, medidas, material, cantidad → resumen → **Enviar por WhatsApp**) plus feedback upgrades:
  - **Catálogo de suajes as dropdown**: all codes from MUESTRARIO EG 2025 grouped by family — RA/RB/RC (rectangulares), OA/OB (ovaladas), CA/CB/CC (circulares), EA/EB/EC (especiales). RB38 marked "solo térmico" if present in catalog.
  - **Live plantilla preview**: selecting a suaje draws its shape to scale (SVG) with dimension arrows (in + cm), like the printed muestrario.
  - "Medida personalizada" option remains (free width/height inputs).
- Data source: `src/data/suajes.js`, extracted from all 30 pages of the PDF (code, shape, W×H in mm, notes).
- No pricing engine — output remains a prefilled WhatsApp message with the spec summary.

### 5. Clientes — logo banner
- Horizontal auto-scrolling marquee of customer/brand logos ("marcas que confían en nosotros") — parity with the Lovable sample. Ships with tasteful text-based placeholder logos until the customer provides real ones (swappable files in `public/img/clientes/`).

### 6. Testimonios
- 3–4 testimonial cards (name, business, quote, sector) — parity with the Lovable sample. Placeholder-but-plausible local content clearly marked in code for the customer to replace. App-like carousel on mobile.

### 7. Diseño + Envío (merged — feedback: "bloques 5 y 7 unirlos")
- One section: "¿No tienes diseñador? No te preocupes" + "¿Cómo enviar tus archivos?".
- Left: the 4 prep details (Zona de sangrado 2mm, Trazo de suaje vectorial, CMYK, Fuentes a curvas) with the interactive preview.
- Right/below: 3-step send flow (Confirma la especificación → Prepara tus vectores → Envía tus archivos) + **Atención Directa** card (tel 668 817 2435, atencion@etiquetasgraficas.com, V. Carranza 460 Ote, Los Mochis + Google Maps link, WhatsApp CTA).

### 8. Historia (demoted)
- Compact band near the footer: "Veinte años imprimiendo la confianza de Los Mochis" + 2-3 lines + the 25-años stat. No full misión/visión/pilares grid on `/`.

### Footer, Navbar, WhatsApp float
- Keep existing (contacts already correct: WA 526682285554, tel 668 817 2435).
- Navbar links updated to new section order.

## Imagery & motion (Higgsfield MCP)

| Asset | Type | Notes |
|---|---|---|
| Hero motion loop | video (short loop, muted, autoplay) | Cinematic flexo press / branded labels — the centerpiece |
| Hero poster still | image | Fallback/poster for the video |
| 7 sector shots | photoreal images | Products with "etiquetas gráficas de Los Mochis" labels, per feedback examples |
| 5–6 material shots | photoreal images | BOPP blanco/transparente/metalizado, couché, kraft, térmicas |
| Feature motion | 1–2 short loops or GSAP reveals | Subtle motion on feature/material cards |

All assets downloaded to `website/public/img/` (and `/video/`); site never hot-links Higgsfield URLs. Video: mp4, compressed, `preload="metadata"`, poster image, graceful fallback to still on mobile/slow connections.

## Data modules

- `src/data/suajes.js` — full catalog (code, family, shape, w_mm, h_mm, label).
- `src/data/sectores.js` — 7 sectors (name, image, line, applications).
- `src/data/materiales.js` — 6 materials (name, tagline, traits[3], idealPara[], ficha{...}, image).
- `src/data/testimonios.js`, `src/data/clientes.js` — placeholder content, clearly commented for replacement.

## Out of scope (YAGNI)

- No CMS/backend, no real pricing engine, no auth, no analytics changes.
- No i18n (Spanish only).
- Real client logos/testimonials content — placeholders shipped, customer swaps.

## Success criteria

- Every feedback bullet from the PDF is addressed (hero text ↓, typography kept, logo card gone, materiales as block 2 with popup, sectores retitled/reordered with realistic images + full page, suaje catalog in cotizador with plantilla preview, bloques 5+7 merged, historia demoted).
- Has everything the Lovable sample has (testimonials, client banner) plus the cotizador/suaje preview it lacks.
- Feels app-like: fluid GSAP transitions, fast load (compressed assets), mobile-first responsive.
- `npm run build` passes; site verified in browser at all breakpoints.
