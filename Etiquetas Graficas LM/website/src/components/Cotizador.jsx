import { useMemo, useRef, useState } from 'react'
import { MessageCircle } from 'lucide-react'
import { SUAJES, SUAJE_GRUPOS } from '../data/suajes.js'
import { MATERIALES } from '../data/materiales.js'
import { wa } from '../data/site.js'
import { useReveal, GlowLayer } from './shared.jsx'

const FORMAS = [
  { value: 'rect', label: 'Rectangular' },
  { value: 'square', label: 'Cuadrada' },
  { value: 'circle', label: 'Circular' },
  { value: 'oval', label: 'Ovalada' },
  { value: 'special', label: 'Especial' },
]

const CANTIDADES = ['1000', '2500', '5000', '10000', 'custom']

/* ----------------------------------------------------------------
   Plantillas para suajes especiales, elegidas por palabras clave de
   la descripción del muestrario. Devuelve un path SVG honesto dentro
   de la caja (x0,y0,sw,sh) o null si no hay plantilla que aplique
   (en ese caso se muestra la caja envolvente punteada).
---------------------------------------------------------------- */
function specialPath(text, x0, y0, sw, sh) {
  const t = (text || '').toLowerCase()
  const cx = x0 + sw / 2
  const has = (...words) => words.some((w) => t.includes(w))

  // tira/banner curvo: banda de grosor constante con tapas rectas
  if (has('tira curva', 'banner curvo')) {
    const horizontal = sw >= sh
    if (horizontal) {
      const th = sh * 0.55
      return `M${x0},${y0 + th} Q${cx},${y0 - th * 0.8} ${x0 + sw},${y0 + th}
              L${x0 + sw},${y0 + sh} Q${cx},${y0 + sh - th * 1.6} ${x0},${y0 + sh} Z`
    }
    const th = sw * 0.55
    const cy = y0 + sh / 2
    return `M${x0 + th},${y0} Q${x0 - th * 0.8},${cy} ${x0 + th},${y0 + sh}
            L${x0 + sw},${y0 + sh} Q${x0 + sw - th * 1.6},${cy} ${x0 + sw},${y0} Z`
  }
  // media luna / riñón
  if (has('media luna', 'rinon', 'riñon', 'kidney')) {
    const cy = y0 + sh / 2
    return `M${x0 + sw * 0.35},${y0} Q${x0 + sw},${y0} ${x0 + sw},${cy}
            Q${x0 + sw},${y0 + sh} ${x0 + sw * 0.35},${y0 + sh}
            Q${x0 + sw * 0.75},${cy} ${x0 + sw * 0.35},${y0} Z`
  }
  // abanico / cuarto de círculo
  if (has('abanico', 'cuarto de circulo')) {
    return `M${x0},${y0 + sh} L${x0},${y0} A${sw},${sh} 0 0 1 ${x0 + sw},${y0 + sh} Z`
  }
  // triángulo redondeado
  if (has('triangulo')) {
    const r = Math.min(sw, sh) * 0.12
    return `M${cx - r},${y0 + r * 0.4} Q${cx},${y0} ${cx + r},${y0 + r * 0.4}
            L${x0 + sw - r * 0.4},${y0 + sh - r} Q${x0 + sw},${y0 + sh} ${x0 + sw - r},${y0 + sh}
            L${x0 + r},${y0 + sh} Q${x0},${y0 + sh} ${x0 + r * 0.4},${y0 + sh - r} Z`
  }
  // tag / etiqueta con arco superior (domo + base recta)
  if (has('tag', 'arco superior')) {
    return `M${x0},${y0 + sh} L${x0},${y0 + sh * 0.32} Q${x0},${y0} ${cx},${y0}
            Q${x0 + sw},${y0} ${x0 + sw},${y0 + sh * 0.32} L${x0 + sw},${y0 + sh} Z`
  }
  // arco / domo / lado o tope redondeado
  if (has('arco/domo', 'domo', 'tope redondeado', 'lado redondeado')) {
    return `M${x0},${y0 + sh} L${x0},${y0 + sh * 0.4} Q${x0},${y0} ${cx},${y0}
            Q${x0 + sw},${y0} ${x0 + sw},${y0 + sh * 0.4} L${x0 + sw},${y0 + sh} Z`
  }
  // barril / tonel (lados abombados)
  if (has('barril', 'tonel')) {
    const b = Math.min(sw, sh) * 0.22
    return `M${x0 + b},${y0} L${x0 + sw - b},${y0} Q${x0 + sw},${y0 + sh / 2} ${x0 + sw - b},${y0 + sh}
            L${x0 + b},${y0 + sh} Q${x0},${y0 + sh / 2} ${x0 + b},${y0} Z`
  }
  // gota / blob / limón
  if (has('gota', 'blob', 'limon')) {
    return `M${cx},${y0} Q${x0 + sw},${y0 + sh * 0.45} ${x0 + sw * 0.85},${y0 + sh * 0.8}
            Q${cx},${y0 + sh * 1.05} ${x0 + sw * 0.15},${y0 + sh * 0.8}
            Q${x0},${y0 + sh * 0.45} ${cx},${y0} Z`
  }
  // cápsula / óvalo redondeado
  if (has('capsula')) {
    const r = Math.min(sw, sh) / 2
    return `M${x0 + r},${y0} L${x0 + sw - r},${y0} A${r},${r} 0 0 1 ${x0 + sw - r},${y0 + sh}
            L${x0 + r},${y0 + sh} A${r},${r} 0 0 1 ${x0 + r},${y0} Z`
  }
  // casa / pentágono con techo
  if (has('casa', 'pentagono')) {
    return `M${x0},${y0 + sh * 0.35} L${cx},${y0} L${x0 + sw},${y0 + sh * 0.35}
            L${x0 + sw},${y0 + sh} L${x0},${y0 + sh} Z`
  }
  // trapecio / rectángulo inclinado
  if (has('trapecio', 'inclinado')) {
    return `M${x0},${y0 + sh * 0.18} L${x0 + sw},${y0} L${x0 + sw},${y0 + sh}
            L${x0},${y0 + sh} Z`
  }
  // romboide / cuadrilátero irregular
  if (has('romboide', 'cuadrilatero')) {
    return `M${x0 + sw * 0.12},${y0} L${x0 + sw},${y0 + sh * 0.08} L${x0 + sw * 0.9},${y0 + sh}
            L${x0},${y0 + sh * 0.88} Z`
  }
  // carpeta / folder con pestaña
  if (has('carpeta', 'folder', 'pestana', 'pestaña')) {
    return `M${x0},${y0 + sh * 0.22} L${x0},${y0} L${x0 + sw * 0.42},${y0}
            L${x0 + sw * 0.52},${y0 + sh * 0.22} L${x0 + sw},${y0 + sh * 0.22}
            L${x0 + sw},${y0 + sh} L${x0},${y0 + sh} Z`
  }
  // llave / paleta (círculo con lengüeta)
  if (has('llave', 'paleta', 'lengueta', 'lengüeta')) {
    const r = sh / 2
    const cy = y0 + sh / 2
    return `M${x0 + r * 1.7},${cy - sh * 0.22} L${x0 + sw},${cy - sh * 0.22}
            L${x0 + sw},${cy + sh * 0.22} L${x0 + r * 1.7},${cy + sh * 0.22}
            A${r},${r} 0 1 1 ${x0 + r * 1.7},${cy - sh * 0.22} Z`
  }
  return null // sin plantilla honesta → caja punteada
}

/* Dibuja el suaje a escala con cotas (mm + cm), estilo plantilla impresa. */
function SuajePreview({ shape, w_mm, h_mm, desc }) {
  const w = Number(w_mm) || 0
  const h = Number(h_mm) || 0
  if (!w || !h) {
    return (
      <div className="h-full flex items-center justify-center text-muted text-sm">
        Elige o captura una medida
      </div>
    )
  }
  const maxDim = Math.max(w, h)
  const scale = 150 / maxDim // px por mm, ajustando el lado mayor a 150px
  const sw = w * scale
  const sh = h * scale
  const pad = 46
  const vbW = sw + pad * 2
  const vbH = sh + pad * 2
  const x0 = pad
  const y0 = pad
  const cx = x0 + sw / 2
  const cy = y0 + sh / 2
  const stroke = '#16216B'

  let unknownSpecial = false
  const shapeEl = (() => {
    if (shape === 'circle') return <circle cx={cx} cy={cy} r={Math.min(sw, sh) / 2} />
    if (shape === 'oval') return <ellipse cx={cx} cy={cy} rx={sw / 2} ry={sh / 2} />
    if (shape === 'special') {
      const d = specialPath(desc, x0, y0, sw, sh)
      if (d) return <path d={d} />
      // Sin plantilla: caja envolvente honesta, nunca un polígono engañoso
      unknownSpecial = true
      return <rect x={x0} y={y0} width={sw} height={sh} strokeDasharray="6 4" fill="none" />
    }
    // rect / square
    return <rect x={x0} y={y0} width={sw} height={sh} rx={shape === 'square' ? 4 : 6} />
  })()

  const mm = (n) => `${n} mm · ${(n / 10).toFixed(n % 10 === 0 ? 0 : 1)} cm`

  return (
    <svg viewBox={`0 0 ${vbW} ${vbH}`} className="w-full h-full" role="img" aria-label="Vista de la etiqueta a escala">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M1,1 L7,4 L1,7" fill="none" stroke={stroke} strokeWidth="1" />
        </marker>
      </defs>
      <g fill="#2178C4" fillOpacity="0.1" stroke={stroke} strokeWidth="1.5">
        {shapeEl}
      </g>
      {unknownSpecial && (
        <text x={cx} y={cy} textAnchor="middle" fontSize="9" fontFamily="monospace" fill={stroke}>
          <tspan x={cx} dy="-4">forma especial</tspan>
          <tspan x={cx} dy="12">ver muestrario físico</tspan>
        </text>
      )}

      {/* Cota horizontal (ancho) */}
      <g stroke={stroke} strokeWidth="1">
        <line x1={x0} y1={y0 + sh + 22} x2={x0 + sw} y2={y0 + sh + 22} markerStart="url(#arrow)" markerEnd="url(#arrow)" />
        <line x1={x0} y1={y0 + sh + 4} x2={x0} y2={y0 + sh + 28} />
        <line x1={x0 + sw} y1={y0 + sh + 4} x2={x0 + sw} y2={y0 + sh + 28} />
      </g>
      <text x={cx} y={y0 + sh + 40} textAnchor="middle" fontSize="11" fontFamily="monospace" fill={stroke}>
        {mm(w)}
      </text>

      {/* Cota vertical (alto) */}
      <g stroke={stroke} strokeWidth="1">
        <line x1={x0 - 22} y1={y0} x2={x0 - 22} y2={y0 + sh} markerStart="url(#arrow)" markerEnd="url(#arrow)" />
        <line x1={x0 - 28} y1={y0} x2={x0 - 4} y2={y0} />
        <line x1={x0 - 28} y1={y0 + sh} x2={x0 - 4} y2={y0 + sh} />
      </g>
      <text
        x={x0 - 30}
        y={cy}
        textAnchor="middle"
        fontSize="11"
        fontFamily="monospace"
        fill={stroke}
        transform={`rotate(-90 ${x0 - 30} ${cy})`}
      >
        {mm(h)}
      </text>
    </svg>
  )
}

/* ----------------------------------------------------------------
   Lienzo de dibujo para suaje especial personalizado.
   Coordenadas en mm (viewBox = ancho×alto mm). Click agrega puntos;
   los segmentos pueden ser recta o curva (suavizado cuadrático).
---------------------------------------------------------------- */
function buildSketchPath(points, closed) {
  if (points.length < 2) return ''
  const r1 = (n) => Math.round(n * 10) / 10
  const pts = closed ? [...points, points[0]] : points
  let d = `M${r1(pts[0].x)},${r1(pts[0].y)}`
  for (let i = 1; i < pts.length; i++) {
    const p = pts[i]
    const prev = pts[i - 1]
    if (p.curve) {
      // suavizado cuadrático: control = punto anterior desplazado al medio
      const mx = (prev.x + p.x) / 2
      const my = (prev.y + p.y) / 2
      const cx = mx + (p.y - prev.y) * 0.25
      const cy = my - (p.x - prev.x) * 0.25
      d += ` Q${r1(cx)},${r1(cy)} ${r1(p.x)},${r1(p.y)}`
    } else {
      d += ` L${r1(p.x)},${r1(p.y)}`
    }
  }
  if (closed) d += ' Z'
  return d
}

function DibujoEspecial({ w, h, sketch, onChange }) {
  const svgRef = useRef(null)
  const { points, closed, segMode } = sketch

  const addPoint = (e) => {
    if (closed) return
    const r = svgRef.current.getBoundingClientRect()
    const x = ((e.clientX - r.left) / r.width) * w
    const y = ((e.clientY - r.top) / r.height) * h
    onChange({
      ...sketch,
      points: [...points, { x, y, curve: segMode === 'curve' && points.length > 0 }],
    })
  }

  const grid = []
  for (let gx = 10; gx < w; gx += 10) grid.push(<line key={`v${gx}`} x1={gx} y1={0} x2={gx} y2={h} />)
  for (let gy = 10; gy < h; gy += 10) grid.push(<line key={`h${gy}`} x1={0} y1={gy} x2={w} y2={gy} />)

  const path = buildSketchPath(points, closed)

  return (
    <div className="h-full flex flex-col">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <div className="inline-flex p-0.5 rounded-full bg-surface border border-divider">
          {[
            { v: 'line', l: 'Línea' },
            { v: 'curve', l: 'Curva' },
          ].map((t) => (
            <button
              key={t.v}
              type="button"
              onClick={() => onChange({ ...sketch, segMode: t.v })}
              className={`px-3 py-1 rounded-full text-xs font-semibold transition-colors ${
                segMode === t.v ? 'bg-primary text-white' : 'text-muted hover:text-ink'
              }`}
            >
              {t.l}
            </button>
          ))}
        </div>
        <button
          type="button"
          disabled={points.length < 3 || closed}
          onClick={() => onChange({ ...sketch, closed: true })}
          className="px-3 py-1 rounded-full text-xs font-semibold border border-divider bg-surface text-ink disabled:opacity-40 hover:border-primary/40"
        >
          Cerrar forma
        </button>
        <button
          type="button"
          disabled={!points.length}
          onClick={() =>
            onChange(
              closed
                ? { ...sketch, closed: false }
                : { ...sketch, points: points.slice(0, -1) }
            )
          }
          className="px-3 py-1 rounded-full text-xs font-semibold border border-divider bg-surface text-ink disabled:opacity-40 hover:border-primary/40"
        >
          Deshacer
        </button>
        <button
          type="button"
          disabled={!points.length}
          onClick={() => onChange({ ...sketch, points: [], closed: false })}
          className="px-3 py-1 rounded-full text-xs font-semibold border border-divider bg-surface text-accent disabled:opacity-40 hover:border-accent/40"
        >
          Borrar
        </button>
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${w} ${h}`}
        onClick={addPoint}
        className="flex-1 w-full bg-white rounded-xl border border-divider cursor-crosshair"
        style={{ maxHeight: 320 }}
        role="img"
        aria-label="Lienzo para dibujar tu suaje"
      >
        {/* Retícula de 10 mm */}
        <g stroke="#16216B" strokeOpacity="0.08" vectorEffect="non-scaling-stroke">
          {grid}
        </g>
        <rect x="0" y="0" width={w} height={h} fill="none" stroke="#16216B" strokeOpacity="0.3" strokeDasharray="4 3" vectorEffect="non-scaling-stroke" />
        {path && (
          <path
            d={path}
            fill={closed ? '#2178C4' : 'none'}
            fillOpacity="0.12"
            stroke="#E0382B"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
          />
        )}
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={Math.max(w, h) / 70} fill={i === 0 ? '#E0382B' : '#16216B'} />
        ))}
      </svg>
      <p className="mt-2 font-mono text-[10px] text-muted">
        Haz clic para agregar puntos sobre la retícula de {w}×{h} mm ·{' '}
        {closed ? 'forma cerrada' : `${points.length} punto${points.length === 1 ? '' : 's'}`}
      </p>
    </div>
  )
}

export default function Cotizador() {
  const ref = useReveal('.cot-reveal')
  const [mode, setMode] = useState('catalogo') // catalogo | personalizada
  const [suajeCode, setSuajeCode] = useState(SUAJES[0].code)
  const [forma, setForma] = useState('rect')
  const [ancho, setAncho] = useState('60')
  const [alto, setAlto] = useState('40')
  const [material, setMaterial] = useState(MATERIALES[0].name)
  const [cantidad, setCantidad] = useState('1000')
  const [cantidadCustom, setCantidadCustom] = useState('')
  const [sketch, setSketch] = useState({ points: [], closed: false, segMode: 'line' })

  const suaje = useMemo(() => SUAJES.find((s) => s.code === suajeCode), [suajeCode])

  const preview =
    mode === 'catalogo'
      ? {
          shape: suaje?.shape || 'rect',
          w_mm: suaje?.w_mm,
          h_mm: suaje?.h_mm,
          desc: `${suaje?.label || ''} ${suaje?.notes || ''}`,
        }
      : { shape: forma, w_mm: ancho, h_mm: alto }

  const drawMode = mode === 'personalizada' && forma === 'special'

  const cantidadFinal = cantidad === 'custom' ? cantidadCustom || '—' : cantidad

  const resumen = useMemo(() => {
    const medida =
      mode === 'catalogo'
        ? suaje
          ? `${suaje.code} · ${suaje.label} · ${suaje.w_mm}×${suaje.h_mm} mm`
          : ''
        : `Medida personalizada · ${forma} · ${ancho}×${alto} mm`
    return { medida }
  }, [mode, suaje, forma, ancho, alto])

  const waHref = useMemo(() => {
    const lines = [
      '¡Hola Etiquetas Gráficas! Quiero cotizar etiquetas con esta especificación:',
      `• ${resumen.medida}`,
      `• Material: ${material}`,
      `• Cantidad: ${cantidadFinal}`,
    ]
    if (drawMode && sketch.points.length >= 2) {
      const xs = sketch.points.map((p) => p.x)
      const ys = sketch.points.map((p) => p.y)
      const bw = Math.round(Math.max(...xs) - Math.min(...xs))
      const bh = Math.round(Math.max(...ys) - Math.min(...ys))
      lines.push(
        `• Forma dibujada por el cliente: ${sketch.points.length} puntos, aprox ${bw}×${bh} mm${
          sketch.closed ? ' (cerrada)' : ''
        }`
      )
      const path = buildSketchPath(sketch.points, sketch.closed)
      if (path.length <= 400) lines.push(`• Trazo SVG: ${path}`)
    }
    lines.push('¿Me pueden ayudar?')
    return wa(lines.join('\n'))
  }, [resumen.medida, material, cantidadFinal, drawMode, sketch])

  const grupos = SUAJE_GRUPOS.map((g) => ({
    label: g.label,
    items: SUAJES.filter((s) => g.families.includes(s.family)),
  })).filter((g) => g.items.length)

  return (
    <section id="cotizador" ref={ref} className="relative bg-background py-24 sm:py-32 overflow-hidden diecut-pattern">
      <GlowLayer />
      <div className="relative max-w-7xl mx-auto px-6 sm:px-10 lg:px-16">
        <div className="max-w-2xl mb-12 cot-reveal">
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-accent mb-4">Cotizador</p>
          <h2 className="font-display text-3xl sm:text-5xl font-extrabold tracking-tight text-ink text-balance">
            Arma tu cotización
          </h2>
          <p className="text-muted mt-4 text-lg">
            Elige tu suaje o captura tu medida, y te lo mandamos por WhatsApp listo para cotizar.
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-6 cot-reveal">
          {/* Controles */}
          <div className="rounded-3xl bg-surface border border-divider p-6 sm:p-8">
            {/* Toggle de modo */}
            <div className="inline-flex p-1 rounded-full bg-background border border-divider mb-6">
              {[
                { v: 'catalogo', l: 'Catálogo de suajes' },
                { v: 'personalizada', l: 'Medida personalizada' },
              ].map((t) => (
                <button
                  key={t.v}
                  onClick={() => setMode(t.v)}
                  className={`px-4 py-2 rounded-full text-sm font-semibold transition-colors ${
                    mode === t.v ? 'bg-primary text-white' : 'text-muted hover:text-ink'
                  }`}
                >
                  {t.l}
                </button>
              ))}
            </div>

            {mode === 'catalogo' ? (
              <label className="block mb-5">
                <span className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted mb-1.5 block">
                  Suaje del muestrario
                </span>
                <select
                  value={suajeCode}
                  onChange={(e) => setSuajeCode(e.target.value)}
                  className="w-full rounded-2xl border border-divider bg-background px-4 py-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary/40"
                >
                  {grupos.map((g) => (
                    <optgroup key={g.label} label={g.label}>
                      {g.items.map((s) => (
                        <option key={s.code} value={s.code}>
                          {s.label}
                          {s.notes ? ` · ${s.notes}` : ''}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </label>
            ) : (
              <div className="mb-5 space-y-4">
                <label className="block">
                  <span className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted mb-1.5 block">
                    Forma
                  </span>
                  <select
                    value={forma}
                    onChange={(e) => setForma(e.target.value)}
                    className="w-full rounded-2xl border border-divider bg-background px-4 py-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary/40"
                  >
                    {FORMAS.map((f) => (
                      <option key={f.value} value={f.value}>
                        {f.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="grid grid-cols-2 gap-4">
                  <label className="block">
                    <span className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted mb-1.5 block">
                      Ancho (mm)
                    </span>
                    <input
                      type="number"
                      min="1"
                      value={ancho}
                      onChange={(e) => setAncho(e.target.value)}
                      className="w-full rounded-2xl border border-divider bg-background px-4 py-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary/40"
                    />
                  </label>
                  <label className="block">
                    <span className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted mb-1.5 block">
                      Alto (mm)
                    </span>
                    <input
                      type="number"
                      min="1"
                      value={alto}
                      onChange={(e) => setAlto(e.target.value)}
                      className="w-full rounded-2xl border border-divider bg-background px-4 py-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary/40"
                    />
                  </label>
                </div>
              </div>
            )}

            <label className="block mb-5">
              <span className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted mb-1.5 block">
                Material
              </span>
              <select
                value={material}
                onChange={(e) => setMaterial(e.target.value)}
                className="w-full rounded-2xl border border-divider bg-background px-4 py-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary/40"
              >
                {MATERIALES.map((m) => (
                  <option key={m.slug} value={m.name}>
                    {m.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="mb-2">
              <span className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted mb-2 block">
                Cantidad
              </span>
              <div className="flex flex-wrap gap-2">
                {CANTIDADES.map((c) => (
                  <button
                    key={c}
                    onClick={() => setCantidad(c)}
                    className={`px-4 py-2 rounded-full text-sm font-semibold border transition-colors ${
                      cantidad === c
                        ? 'bg-primary text-white border-primary'
                        : 'bg-background text-ink border-divider hover:border-primary/40'
                    }`}
                  >
                    {c === 'custom' ? 'Otra' : Number(c).toLocaleString('es-MX')}
                  </button>
                ))}
              </div>
              {cantidad === 'custom' && (
                <input
                  type="number"
                  min="1"
                  value={cantidadCustom}
                  onChange={(e) => setCantidadCustom(e.target.value)}
                  placeholder="¿Cuántas etiquetas?"
                  className="mt-3 w-full rounded-2xl border border-divider bg-background px-4 py-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              )}
            </div>
          </div>

          {/* Vista + resumen */}
          <div className="rounded-3xl bg-surface border border-divider p-6 sm:p-8 flex flex-col">
            <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary mb-3">
              {drawMode ? 'Dibuja tu suaje' : 'Vista a escala'}
            </p>
            <div className="flex-1 min-h-[240px] rounded-2xl bg-background border border-divider p-4">
              {drawMode ? (
                <DibujoEspecial
                  w={Math.max(Number(ancho) || 0, 10)}
                  h={Math.max(Number(alto) || 0, 10)}
                  sketch={sketch}
                  onChange={setSketch}
                />
              ) : (
                <SuajePreview
                  shape={preview.shape}
                  w_mm={preview.w_mm}
                  h_mm={preview.h_mm}
                  desc={preview.desc}
                />
              )}
            </div>

            <div className="mt-6 rounded-2xl bg-background border border-divider p-5">
              <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted mb-3">
                Resumen
              </p>
              <dl className="space-y-1.5 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Medida</dt>
                  <dd className="text-ink font-medium text-right">{resumen.medida || '—'}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Material</dt>
                  <dd className="text-ink font-medium text-right">{material}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Cantidad</dt>
                  <dd className="text-ink font-medium text-right">
                    {cantidadFinal === '—' ? '—' : Number(cantidadFinal).toLocaleString('es-MX')}
                  </dd>
                </div>
              </dl>
            </div>

            <a
              href={waHref}
              target="_blank"
              rel="noopener noreferrer"
              className="magnetic-btn mt-5 w-full inline-flex items-center justify-center gap-2 bg-accent text-white px-6 py-3.5 rounded-full font-semibold shadow-lg shadow-accent/30"
            >
              <MessageCircle className="h-5 w-5" /> Enviar por WhatsApp
            </a>
            <p className="mt-3 font-mono text-[10px] text-muted text-center">
              Te enviamos la cotización según tu especificación. Sin compromiso.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
