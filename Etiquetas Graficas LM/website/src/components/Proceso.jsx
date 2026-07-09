import { PenTool, Layers, FileCheck, Printer, SearchCheck, Truck } from 'lucide-react'
import { useReveal, GlowLayer } from './shared.jsx'

const PASOS = [
  { n: '01', icon: PenTool, title: 'Diseño', text: 'Preprensa y prueba de color.' },
  { n: '02', icon: Layers, title: 'Desarrollo', text: 'Selección de sustratos, adhesivo y acabados.' },
  { n: '03', icon: FileCheck, title: 'Prueba', text: 'Muestra física para aprobación.' },
  { n: '04', icon: Printer, title: 'Producción', text: 'Flexo o digital según volumen.' },
  { n: '05', icon: SearchCheck, title: 'Control de Calidad', text: 'Inspección pieza por pieza.' },
  { n: '06', icon: Truck, title: 'Entrega', text: 'Rollos empacados y despachados a tiempo.' },
]

/* Línea de tiempo horizontal en banda azul marino oscura. */
export default function Proceso() {
  const ref = useReveal('.paso-item', { y: 30, stagger: 0.1 })

  return (
    <section ref={ref} className="relative bg-deep text-white py-24 sm:py-32 overflow-hidden">
      <GlowLayer color="33,120,196" opacity={0.14} />
      <div className="absolute -top-24 -left-24 h-80 w-80 rounded-full bg-primary/25 blur-3xl" />
      <div className="relative max-w-7xl mx-auto px-6 sm:px-10 lg:px-16">
        <div className="max-w-2xl mb-16">
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-primary-light mb-4">
            Nuestro proceso
          </p>
          <h2 className="font-display text-3xl sm:text-5xl font-extrabold tracking-tight text-balance">
            Del brief a tu bodega, <span className="font-serif italic font-medium text-primary-light">en 6 pasos.</span>
          </h2>
        </div>

        <ol className="relative grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-x-6 gap-y-12">
          {/* Línea conectora (desktop) */}
          <div className="hidden lg:block absolute top-6 left-[8.33%] right-[8.33%] h-px bg-gradient-to-r from-primary-light/60 via-white/25 to-primary-light/60" aria-hidden="true" />
          {PASOS.map((p) => {
            const Icon = p.icon
            return (
              <li key={p.n} className="paso-item relative">
                <div className="relative z-10 h-12 w-12 rounded-2xl bg-primary/30 border border-primary-light/40 flex items-center justify-center mb-5 backdrop-blur-sm">
                  <Icon className="h-5 w-5 text-primary-light" />
                </div>
                <span className="font-display text-4xl font-extrabold text-white/10 absolute top-0 right-0" aria-hidden="true">
                  {p.n}
                </span>
                <h3 className="font-display font-bold text-lg leading-tight">
                  <span className="text-primary-light font-mono text-xs mr-1.5 align-middle">{p.n}</span>
                  {p.title}
                </h3>
                <p className="text-white/60 text-sm mt-2 leading-relaxed">{p.text}</p>
              </li>
            )
          })}
        </ol>
      </div>
    </section>
  )
}
