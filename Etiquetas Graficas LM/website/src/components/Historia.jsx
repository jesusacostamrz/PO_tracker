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

export default function Historia() {
  return (
    <section className="relative bg-deep text-white py-20 overflow-hidden">
      <div className="absolute -top-24 -right-24 h-80 w-80 rounded-full bg-primary/25 blur-3xl" />
      <div className="absolute -bottom-24 -left-24 h-80 w-80 rounded-full bg-accent/15 blur-3xl" />
      <div className="relative max-w-7xl mx-auto px-6 sm:px-10 lg:px-16 grid lg:grid-cols-3 gap-10 items-center">
        <div className="lg:col-span-2">
          <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-primary-light mb-4">
            Nuestra historia
          </p>
          <h2 className="font-display text-2xl sm:text-4xl font-extrabold tracking-tight text-balance">
            Veinte años imprimiendo la confianza de Los Mochis
          </h2>
          <p className="text-white/65 mt-4 max-w-xl leading-relaxed">
            Somos una imprenta flexográfica local. Dos décadas acompañando a emprendedores y
            productores del noroeste, con trato cercano y color que se mantiene fiel en cada tiraje.
          </p>
        </div>
        <div className="flex gap-10">
          <div>
            <div className="font-display text-6xl font-extrabold tracking-tighter">
              <CountUp end={25} suffix="" />
            </div>
            <p className="font-mono text-[11px] uppercase tracking-widest text-white/50 mt-2">
              años de oficio
            </p>
          </div>
          <div>
            <div className="font-display text-6xl font-extrabold tracking-tighter">
              <CountUp end={100} suffix="%" />
            </div>
            <p className="font-mono text-[11px] uppercase tracking-widest text-white/50 mt-2">
              color fiel
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
