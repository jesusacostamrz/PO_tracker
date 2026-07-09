import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { SECTORES } from '../data/sectores.js'
import { ImageFallback, useReveal, GlowLayer, TiltCard } from './shared.jsx'

export default function SectoresSection() {
  const ref = useReveal('.sec-card')

  return (
    <section
      id="sectores"
      ref={ref}
      className="relative bg-gradient-to-b from-background via-surface to-surface py-24 sm:py-32 overflow-hidden"
    >
      <div className="absolute inset-0 diecut-pattern" aria-hidden="true" />
      <GlowLayer />
      <div className="relative max-w-7xl mx-auto px-6 sm:px-10 lg:px-16">
        <div className="flex flex-wrap items-end justify-between gap-6 mb-14">
          <div className="max-w-2xl">
            <p className="font-mono text-xs uppercase tracking-[0.25em] text-accent mb-4">
              Sectores
            </p>
            <h2 className="font-display text-3xl sm:text-5xl font-extrabold tracking-tight text-ink text-balance">
              Soluciones para cada sector
            </h2>
          </div>
          <Link
            to="/sectores"
            className="magnetic-btn inline-flex items-center gap-2 bg-primary text-white px-5 py-3 rounded-full text-sm font-semibold"
          >
            Ver todos los sectores <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        {/* 8 sectores → filas completas de 2 / 4 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {SECTORES.map((s) => (
            <TiltCard
              key={s.slug}
              as={Link}
              to="/sectores"
              revealClass="sec-card h-full"
              className="relative rounded-3xl overflow-hidden min-h-[250px] flex items-end border border-divider"
            >
              <ImageFallback
                src={s.image}
                alt={s.name}
                className="absolute inset-0 h-full w-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-deep via-deep/35 to-transparent transition-opacity duration-500 group-hover:opacity-90" />
              <div className="relative p-5 text-white w-full">
                <h3 className="font-display text-lg font-bold leading-tight">{s.name}</h3>
                {/* La línea se revela deslizándose al hacer hover */}
                <p className="text-white/80 text-sm mt-1 leading-snug lg:max-h-0 lg:opacity-0 lg:translate-y-2 overflow-hidden transition-all duration-500 group-hover:max-h-16 group-hover:opacity-100 group-hover:translate-y-0">
                  {s.line}
                </p>
              </div>
            </TiltCard>
          ))}
        </div>
      </div>
    </section>
  )
}
