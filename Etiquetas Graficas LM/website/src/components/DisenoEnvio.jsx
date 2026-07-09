import { useState } from 'react'
import { Phone, Mail, MapPin, MessageCircle, FileCheck, PenTool, Send, ChevronRight } from 'lucide-react'
import {
  WA_DEFAULT,
  PHONE_DISPLAY,
  PHONE_TEL,
  EMAIL,
  ADDRESS,
  MAPS_URL,
} from '../data/site.js'
import { useReveal } from './shared.jsx'

const PREPS = [
  {
    key: 'sangrado',
    title: 'Zona de sangrado 2 mm',
    tag: 'Obligatorio para flexo',
    text: 'Extiende el fondo 2 mm más allá del corte para que no aparezcan filos blancos al suajar.',
    preview: (
      <svg viewBox="0 0 200 140" className="w-full h-full">
        <rect x="20" y="20" width="160" height="100" fill="#EC008C" fillOpacity="0.12" stroke="#EC008C" strokeDasharray="4 3" />
        <rect x="30" y="30" width="140" height="80" fill="#2178C4" fillOpacity="0.15" stroke="#16216B" />
        <text x="100" y="132" textAnchor="middle" fontSize="9" fontFamily="monospace" fill="#EC008C">
          sangrado 2 mm
        </text>
      </svg>
    ),
  },
  {
    key: 'suaje',
    title: 'Trazo de suaje vectorial',
    tag: 'Línea de corte',
    text: 'Marca el contorno de corte como trazo vectorial en una capa aparte, sin relleno.',
    preview: (
      <svg viewBox="0 0 200 140" className="w-full h-full">
        <rect x="30" y="30" width="140" height="80" rx="12" fill="none" stroke="#16216B" strokeDasharray="6 4" strokeWidth="1.5" />
        <text x="100" y="132" textAnchor="middle" fontSize="9" fontFamily="monospace" fill="#16216B">
          contorno de suaje
        </text>
      </svg>
    ),
  },
  {
    key: 'cmyk',
    title: 'Modo de color CMYK',
    tag: 'Color de imprenta',
    text: 'Trabaja en CMYK (no RGB) para que el color impreso salga fiel a lo que ves.',
    preview: (
      <svg viewBox="0 0 200 140" className="w-full h-full">
        {['#00AEEF', '#EC008C', '#FFC400', '#1A1A1A'].map((c, i) => (
          <rect key={c} x={28 + i * 38} y="35" width="30" height="70" rx="4" fill={c} />
        ))}
        <text x="100" y="128" textAnchor="middle" fontSize="9" fontFamily="monospace" fill="#16216B">
          C · M · Y · K
        </text>
      </svg>
    ),
  },
  {
    key: 'fuentes',
    title: 'Fuentes convertidas a curvas',
    tag: 'Sin sorpresas',
    text: 'Convierte los textos a curvas/trazos para que la tipografía no cambie al abrir el archivo.',
    preview: (
      <svg viewBox="0 0 200 140" className="w-full h-full">
        <text x="100" y="90" textAnchor="middle" fontSize="64" fontFamily="Archivo, sans-serif" fontWeight="900" fill="none" stroke="#16216B" strokeWidth="1.5">
          Ag
        </text>
        {[[64, 88], [136, 88], [100, 44], [100, 108]].map(([x, y]) => (
          <rect key={`${x}-${y}`} x={x - 3} y={y - 3} width="6" height="6" fill="#E0382B" />
        ))}
        <text x="100" y="130" textAnchor="middle" fontSize="9" fontFamily="monospace" fill="#16216B">
          texto a curvas
        </text>
      </svg>
    ),
  },
]

const PASOS = [
  { icon: FileCheck, title: 'Confirma la especificación', text: 'Medida, material y cantidad (usa el cotizador de arriba).' },
  { icon: PenTool, title: 'Prepara tus vectores', text: 'Aplica sangrado, suaje, CMYK y fuentes a curvas.' },
  { icon: Send, title: 'Envía tus archivos', text: 'Mándalos por WhatsApp o correo y nosotros seguimos.' },
]

export default function DisenoEnvio() {
  const ref = useReveal('.de-reveal')
  const [active, setActive] = useState(0)

  return (
    <section
      id="envio"
      ref={ref}
      className="relative bg-gradient-to-b from-background via-surface to-surface py-24 sm:py-32 overflow-hidden"
    >
      <div className="max-w-7xl mx-auto px-6 sm:px-10 lg:px-16">
        <div className="max-w-2xl mb-14 de-reveal">
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-accent mb-4">
            Diseño y envío
          </p>
          <h2 className="font-display text-3xl sm:text-5xl font-extrabold tracking-tight text-ink text-balance">
            ¿No tienes diseñador? No te preocupes
          </h2>
          <p className="text-muted mt-4 text-lg">
            Te dejamos el arte listo para imprimir. Y si ya tienes tus archivos, así se preparan.
          </p>
        </div>

        {/* Detalles de preparación + preview */}
        <div className="grid lg:grid-cols-2 gap-6 de-reveal">
          <div className="space-y-3">
            {PREPS.map((p, i) => (
              <button
                key={p.key}
                onClick={() => setActive(i)}
                className={`w-full text-left rounded-2xl border p-5 transition-colors ${
                  active === i
                    ? 'border-primary bg-primary/5'
                    : 'border-divider bg-background hover:border-primary/40'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-display font-bold text-ink">{p.title}</h3>
                  <span className="font-mono text-[10px] uppercase tracking-widest text-accent whitespace-nowrap">
                    {p.tag}
                  </span>
                </div>
                {active === i && <p className="text-muted text-sm mt-2 leading-relaxed">{p.text}</p>}
              </button>
            ))}
          </div>
          <div className="rounded-3xl bg-background border border-divider p-6 flex items-center justify-center min-h-[280px] lg:sticky lg:top-24 self-start">
            <div className="w-full max-w-sm">{PREPS[active].preview}</div>
          </div>
        </div>

        {/* Flujo de envío + Atención directa */}
        <div className="grid lg:grid-cols-2 gap-6 mt-8 de-reveal">
          <div className="rounded-3xl bg-deep text-white p-8">
            <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary-light mb-6">
              ¿Cómo enviar tus archivos?
            </p>
            <ol className="space-y-5">
              {PASOS.map((s, i) => {
                const Icon = s.icon
                return (
                  <li key={s.title} className="flex gap-4">
                    <span className="h-10 w-10 shrink-0 rounded-xl bg-white/10 flex items-center justify-center">
                      <Icon className="h-5 w-5 text-primary-light" />
                    </span>
                    <div>
                      <h4 className="font-display font-bold">
                        {i + 1}. {s.title}
                      </h4>
                      <p className="text-white/60 text-sm mt-0.5">{s.text}</p>
                    </div>
                  </li>
                )
              })}
            </ol>
          </div>

          <div className="rounded-3xl bg-background border border-divider p-8">
            <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary mb-6">
              Atención directa
            </p>
            <ul className="space-y-4 text-sm">
              <li className="flex items-center gap-3">
                <Phone className="h-5 w-5 text-primary shrink-0" />
                <a href={`tel:${PHONE_TEL}`} className="text-ink font-medium hover:text-primary">
                  {PHONE_DISPLAY}
                </a>
              </li>
              <li className="flex items-center gap-3">
                <Mail className="h-5 w-5 text-primary shrink-0" />
                <a href={`mailto:${EMAIL}`} className="text-ink font-medium hover:text-primary break-all">
                  {EMAIL}
                </a>
              </li>
              <li className="flex items-start gap-3">
                <MapPin className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                <a href={MAPS_URL} target="_blank" rel="noopener noreferrer" className="text-ink font-medium hover:text-primary">
                  {ADDRESS}
                  <span className="inline-flex items-center text-primary ml-1">
                    · Ver mapa <ChevronRight className="h-3.5 w-3.5" />
                  </span>
                </a>
              </li>
            </ul>
            <a
              href={WA_DEFAULT}
              target="_blank"
              rel="noopener noreferrer"
              className="magnetic-btn mt-7 w-full inline-flex items-center justify-center gap-2 bg-accent text-white px-6 py-3.5 rounded-full font-semibold shadow-lg shadow-accent/30"
            >
              <MessageCircle className="h-5 w-5" /> Enviar por WhatsApp
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}
