import { useMemo, useState } from 'react'
import { MessageCircle } from 'lucide-react'
import { SUAJES, SUAJE_GRUPOS } from '../data/suajes.js'
import { MATERIALES } from '../data/materiales.js'
import { wa } from '../data/site.js'
import { useReveal } from './shared.jsx'

const FORMAS = [
  { value: 'rect', label: 'Rectangular' },
  { value: 'square', label: 'Cuadrada' },
  { value: 'circle', label: 'Circular' },
  { value: 'oval', label: 'Ovalada' },
  { value: 'special', label: 'Especial' },
]

const CANTIDADES = ['1000', '2500', '5000', '10000', 'custom']

/* Dibuja el suaje a escala con cotas (mm + cm), estilo plantilla impresa. */
function SuajePreview({ shape, w_mm, h_mm }) {
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

  const shapeEl = (() => {
    if (shape === 'circle') return <circle cx={cx} cy={cy} r={Math.min(sw, sh) / 2} />
    if (shape === 'oval') return <ellipse cx={cx} cy={cy} rx={sw / 2} ry={sh / 2} />
    if (shape === 'special')
      return (
        <path
          d={`M${x0 + sw * 0.12},${y0} H${x0 + sw * 0.88} L${x0 + sw},${y0 + sh * 0.35}
              V${y0 + sh * 0.7} L${x0 + sw * 0.82},${y0 + sh} H${x0 + sw * 0.18}
              L${x0},${y0 + sh * 0.6} V${y0 + sh * 0.3} Z`}
        />
      )
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

  const suaje = useMemo(() => SUAJES.find((s) => s.code === suajeCode), [suajeCode])

  const preview =
    mode === 'catalogo'
      ? { shape: suaje?.shape || 'rect', w_mm: suaje?.w_mm, h_mm: suaje?.h_mm }
      : { shape: forma, w_mm: ancho, h_mm: alto }

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

  const waHref = wa(
    [
      '¡Hola Etiquetas Gráficas! Quiero cotizar etiquetas con esta especificación:',
      `• ${resumen.medida}`,
      `• Material: ${material}`,
      `• Cantidad: ${cantidadFinal}`,
      '¿Me pueden ayudar?',
    ].join('\n')
  )

  const grupos = SUAJE_GRUPOS.map((g) => ({
    label: g.label,
    items: SUAJES.filter((s) => g.families.includes(s.family)),
  })).filter((g) => g.items.length)

  return (
    <section id="cotizador" ref={ref} className="bg-background py-24 sm:py-32">
      <div className="max-w-7xl mx-auto px-6 sm:px-10 lg:px-16">
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
                          {s.code} — {s.label} ({s.w_mm}×{s.h_mm} mm)
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
              Vista a escala
            </p>
            <div className="flex-1 min-h-[240px] rounded-2xl bg-background border border-divider p-4">
              <SuajePreview shape={preview.shape} w_mm={preview.w_mm} h_mm={preview.h_mm} />
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
