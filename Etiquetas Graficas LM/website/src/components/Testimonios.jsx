import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Star } from 'lucide-react'
import { TESTIMONIOS } from '../data/testimonios.js'
import { prefersReducedMotion } from '../data/site.js'
import { GlowLayer } from './shared.jsx'

/* Slide deck: una cita grande centrada a la vez, avance automático,
   flechas, swipe y paginación por puntos. */
export default function Testimonios() {
  const [idx, setIdx] = useState(0)
  const [paused, setPaused] = useState(false)
  const touchX = useRef(null)
  const n = TESTIMONIOS.length

  const go = (d) => setIdx((i) => (i + d + n) % n)

  useEffect(() => {
    if (prefersReducedMotion || paused) return
    const id = setInterval(() => setIdx((i) => (i + 1) % n), 6000)
    return () => clearInterval(id)
  }, [paused, n])

  const t = TESTIMONIOS[idx]

  return (
    <section
      className="relative bg-background py-24 sm:py-32 overflow-hidden diecut-pattern"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <GlowLayer />
      <div className="relative max-w-4xl mx-auto px-6 sm:px-10 text-center">
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-accent mb-10">
          Testimonios
        </p>

        <div
          className="select-none"
          onTouchStart={(e) => {
            touchX.current = e.touches[0].clientX
          }}
          onTouchEnd={(e) => {
            if (touchX.current == null) return
            const dx = e.changedTouches[0].clientX - touchX.current
            if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1)
            touchX.current = null
          }}
        >
          <div className="flex items-center justify-center gap-1.5 mb-8" aria-hidden="true">
            {Array.from({ length: 5 }).map((_, i) => (
              <Star key={i} className="h-5 w-5 text-accent" fill="currentColor" />
            ))}
          </div>

          <blockquote
            key={idx}
            className="font-display text-2xl sm:text-4xl font-bold text-ink tracking-tight leading-snug text-balance min-h-[9rem] sm:min-h-[11rem] flex items-center justify-center"
            style={{ animation: prefersReducedMotion ? 'none' : 'testi-fadein 0.5s ease-out' }}
          >
            “{t.quote}”
          </blockquote>

          <div className="mt-8">
            <p className="font-display font-bold text-ink text-lg">{t.name}</p>
            <p className="text-sm text-muted mt-1">
              {t.business} · {t.sector}
            </p>
          </div>
        </div>

        <div className="mt-10 flex items-center justify-center gap-6">
          <button
            onClick={() => go(-1)}
            aria-label="Testimonio anterior"
            className="h-10 w-10 rounded-full border border-divider bg-surface flex items-center justify-center text-ink hover:border-primary/50 hover:text-primary transition-colors"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-2.5">
            {TESTIMONIOS.map((_, i) => (
              <button
                key={i}
                onClick={() => setIdx(i)}
                aria-label={`Ir al testimonio ${i + 1}`}
                className={`rounded-full transition-all duration-300 ${
                  i === idx ? 'h-2.5 w-7 bg-accent' : 'h-2.5 w-2.5 bg-divider hover:bg-muted/50'
                }`}
              />
            ))}
          </div>
          <button
            onClick={() => go(1)}
            aria-label="Testimonio siguiente"
            className="h-10 w-10 rounded-full border border-divider bg-surface flex items-center justify-center text-ink hover:border-primary/50 hover:text-primary transition-colors"
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        </div>
      </div>
      <style>{`
        @keyframes testi-fadein {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </section>
  )
}
