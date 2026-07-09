import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, MessageCircle, CheckCircle2 } from 'lucide-react'
import { SECTORES } from '../data/sectores.js'
import { WA_DEFAULT } from '../data/site.js'
import { Navbar, Footer, WhatsAppFloat } from '../components/chrome.jsx'
import { ImageFallback } from '../components/shared.jsx'

export default function SectoresPage() {
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [])

  return (
    <div className="relative">
      <div className="noise-overlay" />
      <Navbar />
      <main>
        <header className="relative bg-deep text-white pt-36 pb-20 overflow-hidden">
          <div className="absolute top-0 inset-x-0 h-1 cmyk-strip opacity-90" />
          <div className="absolute -top-24 -left-24 h-96 w-96 rounded-full bg-primary/30 blur-3xl" />
          <div className="relative max-w-7xl mx-auto px-6 sm:px-10 lg:px-16">
            <Link
              to="/"
              className="inline-flex items-center gap-2 text-sm text-white/70 hover:text-white mb-8"
            >
              <ArrowLeft className="h-4 w-4" /> Volver al inicio
            </Link>
            <p className="font-mono text-xs uppercase tracking-[0.25em] text-primary-light mb-4">
              Sectores
            </p>
            <h1 className="font-display text-4xl sm:text-6xl font-extrabold tracking-tight max-w-3xl">
              Soluciones para cada sector
            </h1>
            <p className="mt-5 text-white/70 max-w-xl text-lg">
              Adaptamos material, medida y acabado a lo que tu producto necesita. Explora las
              aplicaciones típicas de cada sector.
            </p>
          </div>
        </header>

        <div className="bg-background py-20 sm:py-28">
          <div className="max-w-7xl mx-auto px-6 sm:px-10 lg:px-16 space-y-8">
            {SECTORES.map((s, i) => (
              <div
                key={s.slug}
                className={`grid lg:grid-cols-2 gap-0 rounded-4xl overflow-hidden border border-divider bg-surface shadow-sm ${
                  i % 2 === 1 ? 'lg:[&>*:first-child]:order-2' : ''
                }`}
              >
                <ImageFallback
                  src={s.image}
                  alt={s.name}
                  className="h-64 lg:h-full w-full object-cover min-h-[240px]"
                />
                <div className="p-8 sm:p-12">
                  <h2 className="font-display text-2xl sm:text-3xl font-bold text-ink">{s.name}</h2>
                  <p className="text-muted mt-2 text-lg">{s.line}</p>
                  <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary mt-7 mb-3">
                    Aplicaciones típicas
                  </p>
                  <ul className="space-y-2.5">
                    {s.aplicaciones.map((a) => (
                      <li key={a} className="flex items-center gap-2.5 text-sm text-ink/80">
                        <CheckCircle2 className="h-5 w-5 text-primary-light shrink-0" /> {a}
                      </li>
                    ))}
                  </ul>
                  <a
                    href={WA_DEFAULT}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="magnetic-btn mt-8 inline-flex items-center gap-2 bg-accent text-white px-5 py-3 rounded-full text-sm font-semibold"
                  >
                    <MessageCircle className="h-4 w-4" /> Cotizar para {s.name.toLowerCase()}
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
      <Footer />
      <WhatsAppFloat />
    </div>
  )
}
