/* Constantes de contacto/marca compartidas por toda la app. */
export const WA_NUMBER = '526682285554'
export const wa = (msg) => `https://wa.me/${WA_NUMBER}?text=${encodeURIComponent(msg)}`
export const WA_DEFAULT = wa('¡Hola! Me gustaría cotizar mis etiquetas. ¿Me pueden ayudar?')
export const PHONE_DISPLAY = '668 817 2435'
export const PHONE_TEL = '+526688172435'
export const EMAIL = 'atencion@etiquetasgraficas.com'
export const ADDRESS = 'V. Carranza 460 Ote · 81200 · Los Mochis'
export const MAPS_URL =
  'https://www.google.com/maps/search/?api=1&query=V.+Carranza+460+Ote+Los+Mochis+Sinaloa'

export const NAV_LINKS = [
  { label: 'Inicio', href: '#inicio' },
  { label: 'Materiales', href: '#materiales' },
  { label: 'Sectores', href: '#sectores' },
  { label: 'Cotizador', href: '#cotizador' },
  { label: 'Envío', href: '#envio' },
  { label: 'Contacto', href: '#contacto' },
]

export const prefersReducedMotion =
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches
