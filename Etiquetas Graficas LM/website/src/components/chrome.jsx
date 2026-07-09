import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Menu, X, ArrowUpRight, MessageCircle, Phone, Mail, MapPin } from 'lucide-react'
import { LogoMark, LogoLockup } from '../Logo.jsx'
import {
  NAV_LINKS,
  WA_DEFAULT,
  PHONE_DISPLAY,
  PHONE_TEL,
  EMAIL,
  ADDRESS,
} from '../data/site.js'

/* Los anchors se prefijan con "/" para que funcionen tanto en la home
   como desde /sectores (navega a la home y hace scroll a la sección). */
export function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 80)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <>
      <header className="fixed top-4 left-1/2 -translate-x-1/2 z-50 w-[calc(100%-1.5rem)] max-w-5xl">
        <nav
          className={`flex items-center justify-between rounded-full px-4 sm:px-6 py-2.5 transition-all duration-500 ${
            scrolled ? 'glass shadow-lg shadow-primary/10' : 'bg-transparent'
          }`}
        >
          <Link to="/" className="flex items-center gap-2.5" aria-label="Etiquetas Gráficas">
            <LogoMark size={38} />
            <span
              className={`font-display font-extrabold tracking-tight text-sm leading-none transition-colors ${
                scrolled ? 'text-primary' : 'text-white'
              }`}
            >
              ETIQUETAS
              <br />
              GRÁFICAS
            </span>
          </Link>

          <div className="hidden lg:flex items-center gap-1">
            {NAV_LINKS.map((l) => (
              <a
                key={l.href}
                href={`/${l.href}`}
                className={`px-3 py-2 rounded-full text-sm font-medium transition-colors ${
                  scrolled
                    ? 'text-ink/70 hover:text-primary hover:bg-primary/5'
                    : 'text-white/80 hover:text-white hover:bg-white/10'
                }`}
              >
                {l.label}
              </a>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <a
              href={WA_DEFAULT}
              target="_blank"
              rel="noopener noreferrer"
              className="magnetic-btn hidden sm:inline-flex items-center gap-2 bg-accent text-white px-4 py-2 rounded-full text-sm font-semibold shadow-lg shadow-accent/30"
            >
              Cotizar <ArrowUpRight className="h-4 w-4" />
            </a>
            <button
              onClick={() => setOpen(true)}
              aria-label="Abrir menú"
              className={`lg:hidden p-2 rounded-full transition-colors ${
                scrolled ? 'text-primary hover:bg-primary/10' : 'text-white hover:bg-white/10'
              }`}
            >
              <Menu className="h-6 w-6" />
            </button>
          </div>
        </nav>
      </header>

      <div
        className={`fixed inset-0 z-[60] bg-deep/95 backdrop-blur-2xl transition-all duration-500 lg:hidden ${
          open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
      >
        <div className="flex items-center justify-between px-6 py-6">
          <LogoLockup size={34} dark />
          <button
            onClick={() => setOpen(false)}
            aria-label="Cerrar menú"
            className="p-2 rounded-full text-white hover:bg-white/10"
          >
            <X className="h-7 w-7" />
          </button>
        </div>
        <div className="flex flex-col px-6 pt-8 gap-2">
          {NAV_LINKS.map((l, i) => (
            <a
              key={l.href}
              href={`/${l.href}`}
              onClick={() => setOpen(false)}
              className="font-display text-3xl font-bold text-white/90 hover:text-accent transition-colors py-3 border-b border-white/10"
              style={{ animation: open ? `rain-fadein 0.4s ease-out ${i * 0.06}s both` : 'none' }}
            >
              {l.label}
            </a>
          ))}
          <a
            href={WA_DEFAULT}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setOpen(false)}
            className="mt-6 inline-flex items-center justify-center gap-2 bg-accent text-white px-6 py-4 rounded-full font-semibold text-lg"
          >
            <MessageCircle className="h-5 w-5" /> Cotizar por WhatsApp
          </a>
        </div>
      </div>
    </>
  )
}

export function Footer() {
  const links = [
    { label: 'Materiales', href: '/#materiales' },
    { label: 'Sectores', href: '/sectores' },
    { label: 'Cotizador', href: '/#cotizador' },
    { label: 'Envío de archivos', href: '/#envio' },
    { label: 'Contacto', href: '/#contacto' },
  ]
  return (
    <footer className="bg-deep text-white">
      <div className="max-w-7xl mx-auto px-6 sm:px-10 lg:px-16 py-16">
        <div className="grid lg:grid-cols-4 gap-10">
          <div className="lg:col-span-2">
            <LogoLockup size={42} dark />
            <p className="font-serif italic text-xl text-primary-light mt-5 mb-4">
              Tu marca, en cada etiqueta.
            </p>
            <p className="text-white/60 text-sm max-w-xs leading-relaxed mb-5">
              Imprenta flexográfica de etiquetas en rollo en Los Mochis. Veinte años imprimiendo la
              confianza del noroeste de México.
            </p>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/5 px-3 py-1.5">
              <span className="relative h-2 w-2 rounded-full bg-emerald-500">
                <span className="absolute inset-0 rounded-full bg-emerald-500 animate-ping" />
              </span>
              <span className="font-mono text-[10px] uppercase tracking-widest text-white/70">
                Taller operando
              </span>
            </div>
          </div>

          <div>
            <h4 className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary-light mb-4">
              Explora
            </h4>
            <ul className="space-y-2.5 text-sm text-white/70">
              {links.map((l) => (
                <li key={l.href}>
                  <a href={l.href} className="hover:text-white transition-colors">
                    {l.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary-light mb-4">
              Contacto
            </h4>
            <ul className="space-y-3 text-sm text-white/70">
              <li className="flex items-start gap-2.5">
                <Phone className="h-4 w-4 mt-0.5 shrink-0 text-primary-light" />
                <a href={`tel:${PHONE_TEL}`} className="hover:text-white transition-colors">
                  {PHONE_DISPLAY}
                </a>
              </li>
              <li className="flex items-start gap-2.5">
                <Mail className="h-4 w-4 mt-0.5 shrink-0 text-primary-light" />
                <a href={`mailto:${EMAIL}`} className="hover:text-white transition-colors break-all">
                  {EMAIL}
                </a>
              </li>
              <li className="flex items-start gap-2.5">
                <MapPin className="h-4 w-4 mt-0.5 shrink-0 text-primary-light" />
                <span>{ADDRESS}</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-14 pt-6 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="font-mono text-[11px] text-white/40">
            © {new Date().getFullYear()} Etiquetas Gráficas de Los Mochis. Todos los derechos
            reservados.
          </p>
          <div className="flex items-center gap-5 text-[11px] font-mono text-white/40">
            <Link to="/privacidad" className="hover:text-white transition-colors">
              Aviso de privacidad
            </Link>
            <Link to="/terminos" className="hover:text-white transition-colors">
              Términos
            </Link>
          </div>
        </div>
      </div>
      <div className="h-1.5 cmyk-strip" />
    </footer>
  )
}

export function WhatsAppFloat() {
  return (
    <a
      href={WA_DEFAULT}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Cotizar por WhatsApp"
      className="fixed bottom-5 right-5 z-[55] group"
    >
      <span className="relative flex items-center">
        <span className="hidden sm:block absolute right-16 whitespace-nowrap bg-deep text-white text-sm font-medium px-4 py-2 rounded-full shadow-lg opacity-0 translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all">
          Cotiza por WhatsApp
        </span>
        <span className="h-14 w-14 rounded-full bg-[#25D366] flex items-center justify-center shadow-xl shadow-[#25D366]/40 ring-pulse">
          <MessageCircle className="h-7 w-7 text-white" fill="white" />
        </span>
      </span>
    </a>
  )
}
