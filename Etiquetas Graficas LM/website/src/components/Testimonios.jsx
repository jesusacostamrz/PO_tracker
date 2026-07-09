import { Quote } from 'lucide-react'
import { TESTIMONIOS } from '../data/testimonios.js'
import { useReveal } from './shared.jsx'

export default function Testimonios() {
  const ref = useReveal('.testi-card')
  return (
    <section className="bg-background py-24 sm:py-32" ref={ref}>
      <div className="max-w-7xl mx-auto px-6 sm:px-10 lg:px-16">
        <div className="max-w-2xl mb-14">
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-accent mb-4">
            Testimonios
          </p>
          <h2 className="font-display text-3xl sm:text-5xl font-extrabold tracking-tight text-ink text-balance">
            Lo que dicen nuestros clientes
          </h2>
        </div>

        {/* Carrusel con scroll-snap en móvil, grid en desktop */}
        <div className="flex lg:grid lg:grid-cols-3 gap-5 overflow-x-auto snap-x snap-mandatory scrollbar-hide -mx-6 px-6 lg:mx-0 lg:px-0 lg:overflow-visible">
          {TESTIMONIOS.map((t) => (
            <figure
              key={t.name}
              className="testi-card snap-center shrink-0 w-[85%] sm:w-[70%] lg:w-auto rounded-3xl bg-surface border border-divider p-7 shadow-sm flex flex-col"
            >
              <Quote className="h-8 w-8 text-primary/25 mb-4" />
              <blockquote className="text-ink leading-relaxed flex-1">“{t.quote}”</blockquote>
              <figcaption className="mt-6 pt-5 border-t border-divider">
                <p className="font-display font-bold text-ink">{t.name}</p>
                <p className="text-sm text-muted">
                  {t.business} · {t.sector}
                </p>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  )
}
