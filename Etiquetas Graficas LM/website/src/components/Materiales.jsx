import { useState } from 'react'
import { X, Droplets, Sparkles, ShieldCheck, ChevronRight } from 'lucide-react'
import { MATERIALES } from '../data/materiales.js'
import { ImageFallback, useReveal, GlowLayer, TiltCard, WaveDivider } from './shared.jsx'

const TRAIT_ICONS = [Droplets, Sparkles, ShieldCheck]

function MaterialModal({ material, onClose }) {
  const [fichaOpen, setFichaOpen] = useState(false)
  if (!material) return null
  return (
    <div
      className="fixed inset-0 z-[70] flex items-end sm:items-center justify-center p-0 sm:p-6"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-deep/70 backdrop-blur-sm" />
      <div
        className="relative w-full sm:max-w-lg max-h-[92dvh] overflow-y-auto bg-surface rounded-t-3xl sm:rounded-3xl border border-divider shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          aria-label="Cerrar"
          className="absolute top-4 right-4 z-10 h-9 w-9 rounded-full bg-deep/40 text-white flex items-center justify-center hover:bg-deep/60"
        >
          <X className="h-5 w-5" />
        </button>
        <ImageFallback
          src={material.image}
          alt={material.name}
          className="h-52 w-full object-cover"
        />
        <div className="p-6 sm:p-8">
          <h3 className="font-display text-2xl font-bold text-ink">{material.name}</h3>
          <p className="text-muted mt-1">{material.tagline}</p>

          <div className="mt-6 grid grid-cols-3 gap-3">
            {material.traits.map((t, i) => {
              const Icon = TRAIT_ICONS[i % TRAIT_ICONS.length]
              return (
                <div
                  key={t}
                  className="rounded-2xl bg-background border border-divider p-3 text-center"
                >
                  <Icon className="h-5 w-5 text-primary mx-auto mb-2" />
                  <span className="text-xs font-medium text-ink leading-tight block">{t}</span>
                </div>
              )
            })}
          </div>

          <div className="mt-6">
            <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted mb-2">
              Ideal para
            </p>
            <div className="flex flex-wrap gap-2">
              {material.idealPara.map((chip) => (
                <span
                  key={chip}
                  className="text-xs font-medium text-primary bg-primary/10 px-3 py-1.5 rounded-full"
                >
                  {chip}
                </span>
              ))}
            </div>
          </div>

          {!fichaOpen ? (
            <button
              onClick={() => setFichaOpen(true)}
              className="magnetic-btn mt-7 w-full inline-flex items-center justify-center gap-2 bg-primary text-white px-6 py-3 rounded-full font-semibold"
            >
              Ver ficha técnica completa <ChevronRight className="h-4 w-4" />
            </button>
          ) : (
            <div className="mt-7 rounded-2xl border border-divider overflow-hidden">
              <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary bg-primary/5 px-4 py-3">
                Ficha técnica
              </p>
              <dl className="divide-y divide-divider">
                {Object.entries(material.ficha).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-4 px-4 py-3 text-sm">
                    <dt className="text-muted">{k}</dt>
                    <dd className="text-ink font-medium text-right">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Materiales() {
  const [active, setActive] = useState(null)
  const ref = useReveal('.mat-card')

  return (
    <section
      id="materiales"
      ref={ref}
      className="relative bg-background soft-tints pt-32 pb-24 sm:pb-32 overflow-hidden"
    >
      <WaveDivider fill="#0A1038" />
      <GlowLayer />
      <div className="relative max-w-7xl mx-auto px-6 sm:px-10 lg:px-16">
        <div className="max-w-2xl mb-14">
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-accent mb-4">
            Materiales
          </p>
          <h2 className="font-display text-3xl sm:text-5xl font-extrabold tracking-tight text-ink text-balance">
            ¿En qué material imprimimos tus etiquetas?
          </h2>
          <p className="text-muted mt-4 text-lg">Cada producto pide su material.</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {MATERIALES.map((m) => (
            <TiltCard
              key={m.slug}
              as="button"
              onClick={() => setActive(m)}
              revealClass="mat-card"
              className="rounded-3xl overflow-hidden bg-surface border border-divider shadow-sm"
            >
              <ImageFallback src={m.image} alt={m.name} className="h-44 w-full object-cover" />
              <div className="p-6">
                <h3 className="font-display text-xl font-bold text-ink">{m.name}</h3>
                <p className="text-muted text-sm mt-1">{m.tagline}</p>
                <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-primary transition-transform duration-300 group-hover:translate-x-1">
                  Ver material <ChevronRight className="h-4 w-4" />
                </span>
              </div>
            </TiltCard>
          ))}
        </div>
      </div>

      <MaterialModal material={active} onClose={() => setActive(null)} />
    </section>
  )
}
