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

/* Reveal por scroll reutilizable (patrón de GSAP del App original).
   - clearProps al terminar: el elemento queda con transform limpio para no
     pelear con otros efectos (tilt) ni dejar offsets residuales.
   - Si hay elementos .parallax-drift dentro de la sección, se les aplica
     una deriva sutil ligada al scroll (solo transform). */
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
        clearProps: 'transform,opacity',
        ...opts,
      })
      const drift = ref.current?.querySelectorAll('.parallax-drift')
      if (drift?.length) {
        gsap.to(drift, {
          scrollTrigger: {
            trigger: ref.current,
            start: 'top bottom',
            end: 'bottom top',
            scrub: 1,
          },
          y: 70,
          ease: 'none',
        })
      }
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
   El tilt vive en el elemento INTERNO; el envoltorio externo (revealClass)
   es el objetivo del reveal de scroll — nunca comparten transform. */
export function TiltCard({
  children,
  className = '',
  revealClass = '',
  max = 7,
  as: Tag = 'div',
  ...rest
}) {
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
    <div className={revealClass}>
      <Tag
        ref={ref}
        onMouseMove={onMove}
        onMouseLeave={onLeave}
        className={`eg-tilt group block w-full h-full text-left ${className}`}
        {...rest}
      >
        {children}
        <span aria-hidden="true" className="eg-sheen" />
      </Tag>
    </div>
  )
}

/* Divisor de ola entre secciones: se coloca en el tope de la sección
   siguiente con el color de fondo de la sección anterior. */
export function WaveDivider({ fill = '#F7F7F4', flip = false }) {
  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute inset-x-0 leading-none ${
        flip ? 'bottom-0 rotate-180' : 'top-0'
      }`}
    >
      <svg viewBox="0 0 1440 72" preserveAspectRatio="none" className="block w-full h-10 sm:h-16">
        <path
          d="M0,0 H1440 V16 C1140,68 820,6 500,36 C310,54 150,46 0,18 Z"
          fill={fill}
        />
      </svg>
    </div>
  )
}
