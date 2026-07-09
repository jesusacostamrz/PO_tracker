import { CLIENTES } from '../data/clientes.js'

/* Marquee CSS-only e infinito. Duplicamos la lista para el loop sin corte. */
export default function Clientes() {
  const row = [...CLIENTES, ...CLIENTES]
  return (
    <section className="bg-deep text-white py-14 overflow-hidden border-y border-white/10">
      <p className="text-center font-mono text-[11px] uppercase tracking-[0.25em] text-white/50 mb-8">
        Marcas que confían en nosotros
      </p>
      <div className="relative">
        <div className="flex gap-4 w-max eg-marquee">
          {row.map((c, i) => (
            <span
              key={i}
              className="shrink-0 rounded-2xl border border-white/10 bg-white/5 px-6 py-3 font-display font-bold text-white/70 whitespace-nowrap"
            >
              {c.name}
            </span>
          ))}
        </div>
        <div className="pointer-events-none absolute inset-y-0 left-0 w-24 bg-gradient-to-r from-deep to-transparent" />
        <div className="pointer-events-none absolute inset-y-0 right-0 w-24 bg-gradient-to-l from-deep to-transparent" />
      </div>
      <style>{`
        .eg-marquee { animation: eg-marquee 34s linear infinite; }
        @keyframes eg-marquee { from { transform: translateX(0); } to { transform: translateX(-50%); } }
        @media (prefers-reduced-motion: reduce) { .eg-marquee { animation: none; } }
      `}</style>
    </section>
  )
}
