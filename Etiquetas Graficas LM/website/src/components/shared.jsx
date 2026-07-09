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

/* Capa de fondo interactiva: brillo radial que sigue al cursor dentro de la
   sección padre. Solo transform/vars CSS — sin layout thrash. */
export function GlowLayer({ color = '33,120,196', opacity = 0.09 }) {
  const ref = useRef(null)
  useEffect(() => {
    if (prefersReducedMotion) return
    const el = ref.current
    const parent = el?.parentElement
    if (!parent) return
    const onMove = (e) => {
      const r = parent.getBoundingClientRect()
      el.style.setProperty('--mx', `${e.clientX - r.left}px`)
      el.style.setProperty('--my', `${e.clientY - r.top}px`)
      el.style.opacity = '1'
    }
    const onLeave = () => {
      el.style.opacity = '0'
    }
    parent.addEventListener('mousemove', onMove)
    parent.addEventListener('mouseleave', onLeave)
    return () => {
      parent.removeEventListener('mousemove', onMove)
      parent.removeEventListener('mouseleave', onLeave)
    }
  }, [])
  return (
    <div
      ref={ref}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 transition-opacity duration-500 opacity-0"
      style={{
        background: `radial-gradient(560px circle at var(--mx, 50%) var(--my, 50%), rgba(${color},${opacity}), transparent 65%)`,
      }}
    />
  )
}

/* Tarjeta con tilt 3D que sigue al mouse + barrido de brillo (sheen).
   Solo transform/opacity. Respeta prefers-reduced-motion. */
export function TiltCard({ children, className = '', max = 7, as: Tag = 'div', ...rest }) {
  const ref = useRef(null)
  const onMove = (e) => {
    if (prefersReducedMotion) return
    const el = ref.current
    const r = el.getBoundingClientRect()
    const px = (e.clientX - r.left) / r.width
    const py = (e.clientY - r.top) / r.height
    el.style.transform = `perspective(900px) rotateX(${(0.5 - py) * max}deg) rotateY(${(px - 0.5) * max}deg) translateY(-2px)`
    el.style.setProperty('--shx', `${px * 100}%`)
    el.style.setProperty('--shy', `${py * 100}%`)
  }
  const onLeave = () => {
    if (ref.current) ref.current.style.transform = ''
  }
  return (
    <Tag
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      className={`eg-tilt group ${className}`}
      {...rest}
    >
      {children}
      <span aria-hidden="true" className="eg-sheen" />
    </Tag>
  )
}
