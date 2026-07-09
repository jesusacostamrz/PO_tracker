import { useEffect, useRef, useState } from 'react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { prefersReducedMotion } from '../data/site.js'

gsap.registerPlugin(ScrollTrigger)

/* Imagen con fallback a un div degradado si el archivo no existe todavía.
   Los assets de /img/* se generan aparte; esto evita imágenes rotas. */
export function ImageFallback({ src, alt, className = '', gradient = 'from-primary/30 to-deep' }) {
  const [failed, setFailed] = useState(false)
  if (failed || !src) {
    return (
      <div
        className={`bg-gradient-to-br ${gradient} flex items-center justify-center ${className}`}
        aria-label={alt}
        role="img"
      >
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/60 px-4 text-center">
          {alt}
        </span>
      </div>
    )
  }
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      className={className}
      onError={() => setFailed(true)}
    />
  )
}

/* Reveal por scroll reutilizable (patrón de GSAP del App original). */
export function useReveal(selector = '.reveal', opts = {}) {
  const ref = useRef(null)
  useEffect(() => {
    if (prefersReducedMotion) return
    const ctx = gsap.context(() => {
      gsap.from(selector, {
        scrollTrigger: { trigger: ref.current, start: 'top 82%', once: true },
        y: 40,
        opacity: 0,
        duration: 0.8,
        stagger: 0.12,
        ease: 'power3.out',
        ...opts,
      })
    }, ref)
    return () => ctx.revert()
  }, [selector])
  return ref
}
