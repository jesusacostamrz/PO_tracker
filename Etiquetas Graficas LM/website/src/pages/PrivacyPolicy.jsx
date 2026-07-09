import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { LogoLockup } from '../Logo.jsx'

export default function PrivacyPolicy() {
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
          Aviso de Privacidad
        </h1>
        <p className="font-mono text-xs text-muted mb-10">
          Última actualización · 2026 · Los Mochis, Sinaloa
        </p>

        <div className="space-y-8 font-body text-[15px] leading-relaxed text-ink/85">
          <section>
            <h2 className="font-display text-xl font-bold text-primary mb-2">Responsable</h2>
            <p>
              Etiquetas Gráficas de Los Mochis, con domicilio en V. Carranza 460 Ote, C.P. 81200,
              Los Mochis, Sinaloa, es responsable del uso y protección de tus datos personales,
              conforme a la Ley Federal de Protección de Datos Personales en Posesión de los
              Particulares.
            </p>
          </section>
          <section>
            <h2 className="font-display text-xl font-bold text-primary mb-2">Datos que recabamos</h2>
            <p>
              Nombre, correo electrónico, teléfono y los archivos de diseño que nos compartes para
              cotizar e imprimir tus etiquetas. Los usamos únicamente para atender tu solicitud,
              elaborar tu cotización y darte seguimiento.
            </p>
          </section>
          <section>
            <h2 className="font-display text-xl font-bold text-primary mb-2">Finalidad</h2>
            <p>
              Tus datos se utilizan para contactarte, preparar presupuestos, producir tus pedidos y
              brindarte servicio. No vendemos ni compartimos tu información con terceros con fines
              comerciales.
            </p>
          </section>
          <section>
            <h2 className="font-display text-xl font-bold text-primary mb-2">Tus derechos (ARCO)</h2>
            <p>
              Puedes acceder, rectificar, cancelar u oponerte al tratamiento de tus datos
              escribiéndonos a{' '}
              <a className="text-accent font-medium" href="mailto:atencion@etiquetasgraficas.com">
                atencion@etiquetasgraficas.com
              </a>
              .
            </p>
          </section>
          <section>
            <h2 className="font-display text-xl font-bold text-primary mb-2">Contacto</h2>
            <p>
              ¿Dudas sobre este aviso? Llámanos al 668 817 2435 o escríbenos por WhatsApp. Estamos
              para ayudarte como vecinos, no como proveedores anónimos.
            </p>
          </section>
        </div>
      </main>
    </div>
  )
}
