import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { LogoLockup } from '../Logo.jsx'

export default function Terms() {
  return (
    <div className="min-h-screen bg-background text-ink">
      <header className="border-b border-divider">
        <div className="max-w-3xl mx-auto px-6 py-5 flex items-center justify-between">
          <Link to="/" aria-label="Inicio">
            <LogoLockup size={34} />
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-muted hover:text-primary transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Volver
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-16">
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-accent mb-4">
          Documento legal
        </p>
        <h1 className="font-display text-4xl font-extrabold tracking-tight mb-2">
          Términos y Condiciones
        </h1>
        <p className="font-mono text-xs text-muted mb-10">
          Última actualización · 2026 · Los Mochis, Sinaloa
        </p>

        <div className="space-y-8 font-body text-[15px] leading-relaxed text-ink/85">
          <section>
            <h2 className="font-display text-xl font-bold text-primary mb-2">Cotizaciones</h2>
            <p>
              Las cotizaciones se elaboran con base en la información y los archivos que nos
              proporcionas (medidas, material, cantidad y acabado). El precio final puede variar si
              cambian las especificaciones del pedido.
            </p>
          </section>
          <section>
            <h2 className="font-display text-xl font-bold text-primary mb-2">Archivos y diseño</h2>
            <p>
              Tú eres responsable de contar con los derechos sobre los diseños, marcas e imágenes
              que nos envíes. Antes de imprimir te compartimos una prueba para tu aprobación; una vez
              aprobada, el tiraje se produce tal cual.
            </p>
          </section>
          <section>
            <h2 className="font-display text-xl font-bold text-primary mb-2">
              Tiempos de entrega
            </h2>
            <p>
              Los tiempos se confirman al aprobar tu pedido. Hacemos todo lo posible por cumplir lo
              prometido; cualquier ajuste se te comunica de inmediato.
            </p>
          </section>
          <section>
            <h2 className="font-display text-xl font-bold text-primary mb-2">Color e impresión</h2>
            <p>
              Trabajamos para mantener el color fiel en cada tiraje. Pueden existir variaciones
              menores propias del proceso flexográfico y del material elegido, dentro de tolerancias
              normales de la industria.
            </p>
          </section>
          <section>
            <h2 className="font-display text-xl font-bold text-primary mb-2">Pagos</h2>
            <p>
              Las condiciones de pago se acuerdan al confirmar el pedido. Para pedidos nuevos puede
              solicitarse un anticipo antes de iniciar la producción.
            </p>
          </section>
          <section>
            <h2 className="font-display text-xl font-bold text-primary mb-2">Contacto</h2>
            <p>
              ¿Dudas sobre estos términos? Escríbenos a{' '}
              <a className="text-accent font-medium" href="mailto:atencion@etiquetasgraficas.com">
                atencion@etiquetasgraficas.com
              </a>{' '}
              o llámanos al 668 817 2435.
            </p>
          </section>
        </div>
      </main>
    </div>
  )
}
