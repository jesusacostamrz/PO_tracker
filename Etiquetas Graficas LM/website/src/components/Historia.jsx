import { useEffect, useRef, useState } from 'react'

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
      { threshold: 0.4 }
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
  return (
    <section className="relative bg-primary text-white overflow-hidden">
      <div className="absolute top-0 inset-x-0 h-1 cmyk-strip opacity-80" />
      <div className="max-w-7xl mx-auto px-6 sm:px-10 lg:px-16 py-16 sm:py-20">
        <div className="max-w-3xl mb-12">
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
            <div key={s.label}>
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
