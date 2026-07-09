import { useEffect, useRef, useState } from 'react'
import { useReveal, WaveDivider } from './shared.jsx'

function CountUp({ end, suffix = '', duration = 1800 }) {
  const [value, setValue] = useState(0)
  const ref = useRef(null)
  const started = useRef(false)
  useEffect(() => {
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true
          const startTs = performance.now()
          const tick = (now) => {
            const t = Math.min(1, (now - startTs) / duration)
            setValue(Math.round(end * (1 - Math.pow(1 - t, 3))))
            if (t < 1) requestAnimationFrame(tick)
          }
          requestAnimationFrame(tick)
        }
      },
      { threshold: 0.2 }
    )
    if (ref.current) obs.observe(ref.current)
    return () => obs.disconnect()
  }, [end, duration])
  return (
    <span ref={ref} className="tabular-nums">
      {value}
      {suffix}
    </span>
  )
}

const STATS = [
  { end: 20, suffix: '+', label: 'Años de experiencia' },
  { end: 500, suffix: '+', label: 'Clientes activos' },
  { end: 10, suffix: 'M+', label: 'Etiquetas impresas' },
  { end: 98, suffix: '%', label: 'Satisfacción' },
]

/* Banda azul sólida de ancho completo con 4 estadísticas gigantes. */
export default function Historia() {
  const ref = useReveal('.hist-reveal', { y: 30, stagger: 0.1 })
  return (
    <section
      ref={ref}
      className="relative bg-gradient-to-br from-primary via-primary to-primary-dark text-white overflow-hidden"
    >
      <WaveDivider fill="#FFFFFF" />
      {/* Motivo: globo EG delineado con deriva sutil al hacer scroll */}
      <svg
        aria-hidden="true"
        viewBox="0 0 200 200"
        className="parallax-drift absolute -left-32 -top-24 h-[420px] w-[420px] opacity-[0.06]"
      >
        <g stroke="#FFFFFF" strokeWidth="1.2" fill="none">
          <circle cx="100" cy="100" r="92" />
          <circle cx="100" cy="100" r="56" />
          <ellipse cx="100" cy="100" rx="18" ry="56" />
          <ellipse cx="100" cy="100" rx="38" ry="56" />
          <line x1="44" y1="100" x2="156" y2="100" />
        </g>
      </svg>
      <div className="relative max-w-7xl mx-auto px-6 sm:px-10 lg:px-16 pt-24 pb-16 sm:pb-20">
        <div className="hist-reveal max-w-3xl mb-12">
          <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-white/60 mb-4">
            Nuestra historia
          </p>
          <h2 className="font-display text-2xl sm:text-4xl font-extrabold tracking-tight text-balance">
            Veinte años imprimiendo la confianza de Los Mochis
          </h2>
          <p className="text-white/70 mt-3 max-w-xl leading-relaxed">
            Dos décadas acompañando a emprendedores y productores del noroeste, con trato cercano y
            color que se mantiene fiel en cada tiraje.
          </p>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-x-8 gap-y-10">
          {STATS.map((s) => (
            <div key={s.label} className="hist-reveal">
              <div className="font-display text-5xl sm:text-7xl font-extrabold tracking-tighter">
                <CountUp end={s.end} suffix={s.suffix} />
              </div>
              <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/60 mt-3">
                {s.label}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
