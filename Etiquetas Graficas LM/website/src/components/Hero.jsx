import { useEffect, useRef, useState } from 'react'
import { gsap } from 'gsap'
import { MessageCircle, Phone, Check } from 'lucide-react'
import { WA_DEFAULT, PHONE_DISPLAY, PHONE_TEL, prefersReducedMotion } from '../data/site.js'

const CLAIMS = ['Color fiel', 'Etiquetas en rollo', 'Listas rápido']

export default function Hero() {
  const ref = useRef(null)
  const [videoFailed, setVideoFailed] = useState(false)

  useEffect(() => {
    if (prefersReducedMotion) return
    const ctx = gsap.context(() => {
      gsap.from('.hero-line-1', { y: 40, opacity: 0, duration: 1, delay: 0.3, ease: 'power3.out' })
      gsap.from('.hero-line-2', { y: 60, opacity: 0, duration: 1.2, delay: 0.5, ease: 'power3.out' })
      gsap.from('.hero-rolls', { x: 70, opacity: 0, duration: 1.2, delay: 0.7, ease: 'power3.out' })
      gsap.from('.hero-meta, .hero-cta', {
        y: 24,
        opacity: 0,
        duration: 0.8,
        delay: 0.85,
        stagger: 0.12,
        ease: 'power3.out',
      })
    }, ref)
    return () => ctx.revert()
  }, [])

  return (
    <section id="inicio" ref={ref} className="relative min-h-[100dvh] overflow-hidden bg-deep">
      {/* Fondo: video con fallback a poster/imagen */}
      {videoFailed ? (
        <img
          src="/img/hero-poster.jpg"
          alt="Prensa flexográfica imprimiendo etiquetas"
          className="absolute inset-0 h-full w-full object-cover brightness-[0.4]"
          onError={(e) => {
            e.currentTarget.style.display = 'none'
          }}
        />
      ) : (
        <video
          className="absolute inset-0 h-full w-full object-cover brightness-[0.4]"
          poster="/img/hero-poster.jpg"
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          onError={() => setVideoFailed(true)}
        >
          <source src="/video/hero.mp4" type="video/mp4" />
        </video>
      )}
      <div className="absolute inset-0 bg-gradient-to-br from-deep/90 via-deep/55 to-primary/60" />
      <div className="absolute inset-x-0 bottom-0 h-72 bg-gradient-to-t from-deep to-transparent" />
      <div className="absolute top-0 inset-x-0 h-1 cmyk-strip opacity-90" />

      {/* Rollos de etiquetas — recorte flotante en primer plano (solo desktop) */}
      <div className="hero-rolls hidden lg:block absolute right-14 xl:right-24 bottom-28 z-10 w-[290px] xl:w-[330px] rotate-2 animate-float">
        <div className="relative rounded-3xl overflow-hidden border border-white/25 shadow-2xl shadow-deep/60 bg-deep/40 backdrop-blur-sm">
          <img
            src="/img/hero-rolls.jpg"
            alt="Rollos de etiquetas a color apilados"
            className="w-full aspect-[3/4] object-cover"
            onError={(e) => {
              e.currentTarget.closest('.hero-rolls').style.display = 'none'
            }}
          />
          <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-deep/80 to-transparent" />
          <p className="absolute bottom-3 left-4 right-4 font-mono text-[10px] uppercase tracking-[0.2em] text-white/80">
            Recién salidas de prensa
          </p>
          <div className="absolute top-0 inset-x-0 h-1 cmyk-strip" />
        </div>
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6 sm:px-10 lg:px-16 pt-32 pb-24 min-h-[100dvh] flex flex-col justify-end">
        <p className="hero-meta font-mono text-[11px] sm:text-xs uppercase tracking-[0.25em] text-white/70 mb-6">
          Veinte años · Imprenta flexográfica · Los Mochis
        </p>
        <h1 className="font-display text-5xl sm:text-7xl lg:text-[7.5rem] font-extrabold text-white tracking-tighter leading-[0.92] max-w-5xl">
          <span className="hero-line-1 block">Tu marca,</span>
          <span className="hero-line-2 block font-serif italic font-medium text-primary-light">
            en cada etiqueta.
          </span>
        </h1>
        <p className="hero-meta mt-8 max-w-xl text-white/75 text-base sm:text-lg leading-relaxed">
          Mándanos tu diseño y nosotros nos encargamos del resto.
        </p>
        <div className="hero-cta mt-9 flex flex-wrap gap-3">
          <a
            href={WA_DEFAULT}
            target="_blank"
            rel="noopener noreferrer"
            className="magnetic-btn inline-flex items-center gap-2 bg-accent text-white px-6 py-3.5 rounded-full font-semibold shadow-xl shadow-accent/30"
          >
            <MessageCircle className="h-5 w-5" /> Cotizar por WhatsApp
          </a>
          <a
            href={`tel:${PHONE_TEL}`}
            className="magnetic-btn inline-flex items-center gap-2 glass-dark text-white px-6 py-3.5 rounded-full font-semibold border border-white/15"
          >
            <Phone className="h-4 w-4" /> {PHONE_DISPLAY}
          </a>
        </div>

        <div className="hero-meta mt-8 flex flex-wrap gap-x-6 gap-y-2">
          {CLAIMS.map((c) => (
            <span key={c} className="inline-flex items-center gap-2 text-sm text-white/80">
              <Check className="h-4 w-4 text-primary-light shrink-0" /> {c}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
