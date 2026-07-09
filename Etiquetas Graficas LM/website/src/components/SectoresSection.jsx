import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { SECTORES } from '../data/sectores.js'
import { ImageFallback, useReveal } from './shared.jsx'

export default function SectoresSection() {
  const ref = useReveal('.sec-card')

  return (
    <section id="sectores" ref={ref} className="bg-surface py-24 sm:py-32 border-t border-divider">
      <div className="max-w-7xl mx-auto px-6 sm:px-10 lg:px-16">
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

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {SECTORES.map((s) => (
            <Link
              to="/sectores"
              key={s.slug}
              className="sec-card group relative rounded-3xl overflow-hidden min-h-[240px] flex items-end border border-divider"
            >
              <ImageFallback
                src={s.image}
                alt={s.name}
                className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-deep via-deep/40 to-transparent" />
              <div className="relative p-6 text-white">
                <h3 className="font-display text-xl font-bold">{s.name}</h3>
                <p className="text-white/80 text-sm mt-1 leading-snug">{s.line}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  )
}
