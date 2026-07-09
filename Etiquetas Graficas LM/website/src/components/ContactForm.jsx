import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  MessageCircle,
  Phone,
  Mail,
  MapPin,
  Clock,
  CheckCircle2,
  Upload,
  Send,
  X,
} from 'lucide-react'
import { wa, WA_DEFAULT, PHONE_DISPLAY, PHONE_TEL, EMAIL, ADDRESS } from '../data/site.js'

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted mb-1.5 block">
        {label}
      </span>
      {children}
    </label>
  )
}

const inputCls =
  'w-full rounded-2xl border border-divider bg-background px-4 py-3 text-sm text-ink placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition'

export default function ContactForm() {
  const [status, setStatus] = useState('idle')
  const [files, setFiles] = useState([])
  const [form, setForm] = useState({ name: '', email: '', phone: '', product: '', message: '' })

  const onChange = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const onDrop = (e) => {
    e.preventDefault()
    const list = [...e.dataTransfer.files]
      .filter((f) => f.type.startsWith('image/') || f.type === 'application/pdf')
      .slice(0, 5 - files.length)
    setFiles((prev) => [...prev, ...list])
  }
  const onPick = (e) => {
    const list = [...e.target.files].slice(0, 5 - files.length)
    setFiles((prev) => [...prev, ...list])
  }
  const removeFile = (i) => setFiles((prev) => prev.filter((_, idx) => idx !== i))

  const onSubmit = (e) => {
    e.preventDefault()
    setStatus('sending')
    setTimeout(() => setStatus('sent'), 1200)
  }

  const waFromForm = wa(
    `¡Hola Etiquetas Gráficas! Soy ${form.name || '(nombre)'}. ` +
      `Quiero cotizar etiquetas${form.product ? ` para ${form.product}` : ''}. ` +
      `${form.message || ''}`.trim()
  )

  return (
    <section id="contacto" className="bg-surface py-24 sm:py-32 border-t border-divider">
      <div className="max-w-7xl mx-auto px-6 sm:px-10 lg:px-16">
        <div className="grid lg:grid-cols-12 gap-12">
          <div className="lg:col-span-5">
            <p className="font-mono text-xs uppercase tracking-[0.25em] text-accent mb-4">
              Contacto
            </p>
            <h2 className="font-display text-3xl sm:text-5xl font-extrabold tracking-tight text-ink text-balance mb-6">
              Cotiza tus etiquetas hoy
            </h2>
            <p className="text-muted leading-relaxed mb-8 max-w-md">
              Mándanos tu diseño o cuéntanos tu idea. Te respondemos rápido y con gusto, como
              vecinos.
            </p>

            <div className="space-y-3">
              <a
                href={WA_DEFAULT}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-4 p-4 rounded-2xl bg-background border border-divider lift-on-hover"
              >
                <span className="h-11 w-11 rounded-xl bg-[#25D366]/15 flex items-center justify-center shrink-0">
                  <MessageCircle className="h-5 w-5 text-[#1da851]" />
                </span>
                <span>
                  <span className="block font-mono text-[10px] uppercase tracking-widest text-muted">
                    WhatsApp
                  </span>
                  <span className="font-semibold text-ink">668 228 5554</span>
                </span>
              </a>
              <a
                href={`tel:${PHONE_TEL}`}
                className="flex items-center gap-4 p-4 rounded-2xl bg-background border border-divider lift-on-hover"
              >
                <span className="h-11 w-11 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                  <Phone className="h-5 w-5 text-primary" />
                </span>
                <span>
                  <span className="block font-mono text-[10px] uppercase tracking-widest text-muted">
                    Teléfono
                  </span>
                  <span className="font-semibold text-ink">{PHONE_DISPLAY}</span>
                </span>
              </a>
              <a
                href={`mailto:${EMAIL}`}
                className="flex items-center gap-4 p-4 rounded-2xl bg-background border border-divider lift-on-hover"
              >
                <span className="h-11 w-11 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                  <Mail className="h-5 w-5 text-primary" />
                </span>
                <span>
                  <span className="block font-mono text-[10px] uppercase tracking-widest text-muted">
                    Correo
                  </span>
                  <span className="font-semibold text-ink break-all">{EMAIL}</span>
                </span>
              </a>
              <div className="flex items-center gap-4 p-4 rounded-2xl bg-background border border-divider">
                <span className="h-11 w-11 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                  <MapPin className="h-5 w-5 text-primary" />
                </span>
                <span>
                  <span className="block font-mono text-[10px] uppercase tracking-widest text-muted">
                    Taller
                  </span>
                  <span className="font-semibold text-ink">{ADDRESS}</span>
                </span>
              </div>
              <div className="flex items-center gap-4 p-4 rounded-2xl bg-background border border-divider">
                <span className="h-11 w-11 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                  <Clock className="h-5 w-5 text-primary" />
                </span>
                <span>
                  <span className="block font-mono text-[10px] uppercase tracking-widest text-muted">
                    Horario
                  </span>
                  <span className="font-semibold text-ink">
                    Lun–Vie 9:00–18:00 · Sáb 9:00–14:00
                  </span>
                </span>
              </div>
            </div>
          </div>

          <div className="lg:col-span-7">
            {status === 'sent' ? (
              <div className="h-full min-h-[420px] flex flex-col items-center justify-center text-center rounded-3xl border border-divider bg-background p-12">
                <div className="h-16 w-16 rounded-full bg-emerald-500/15 flex items-center justify-center mb-6">
                  <CheckCircle2 className="h-8 w-8 text-emerald-600" />
                </div>
                <h3 className="font-display text-2xl font-bold text-ink mb-2">
                  ¡Gracias! Te contactamos pronto.
                </h3>
                <p className="text-muted max-w-sm mb-6">
                  Recibimos tu solicitud. Si quieres, mándanos tu diseño directo por WhatsApp para ir
                  más rápido.
                </p>
                <a
                  href={waFromForm}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="magnetic-btn inline-flex items-center gap-2 bg-accent text-white px-6 py-3 rounded-full font-semibold"
                >
                  <MessageCircle className="h-5 w-5" /> Continuar en WhatsApp
                </a>
              </div>
            ) : (
              <form onSubmit={onSubmit} className="rounded-3xl border border-divider bg-background p-6 sm:p-8">
                <div className="grid sm:grid-cols-2 gap-4">
                  <Field label="Nombre">
                    <input required value={form.name} onChange={onChange('name')} placeholder="Tu nombre" className={inputCls} />
                  </Field>
                  <Field label="Correo">
                    <input type="email" value={form.email} onChange={onChange('email')} placeholder="tucorreo@ejemplo.com" className={inputCls} />
                  </Field>
                </div>
                <div className="grid sm:grid-cols-2 gap-4 mt-4">
                  <Field label="Teléfono / WhatsApp">
                    <input value={form.phone} onChange={onChange('phone')} placeholder="668 000 0000" className={inputCls} />
                  </Field>
                  <Field label="Tipo de producto">
                    <input value={form.product} onChange={onChange('product')} placeholder="Alimento, bebida, cosmética…" className={inputCls} />
                  </Field>
                </div>
                <div className="mt-4">
                  <Field label="Cuéntanos de tu tiraje">
                    <textarea rows={5} value={form.message} onChange={onChange('message')} placeholder="Medida, cantidad, material o cualquier duda…" className={inputCls + ' resize-none'} />
                  </Field>
                </div>

                <div
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={onDrop}
                  className="mt-4 rounded-2xl border-2 border-dashed border-divider hover:border-primary/40 transition-colors p-6 text-center"
                >
                  <input id="file-up" type="file" multiple accept="image/*,application/pdf" onChange={onPick} className="hidden" />
                  <label htmlFor="file-up" className="cursor-pointer flex flex-col items-center gap-2">
                    <span className="h-11 w-11 rounded-xl bg-primary/10 flex items-center justify-center">
                      <Upload className="h-5 w-5 text-primary" />
                    </span>
                    <span className="text-sm font-medium text-ink">Arrastra tu diseño o haz clic para subir</span>
                    <span className="font-mono text-[10px] uppercase tracking-widest text-muted">PDF o imágenes · máx. 5 archivos</span>
                  </label>
                  {files.length > 0 && (
                    <ul className="mt-4 space-y-2 text-left">
                      {files.map((f, i) => (
                        <li key={i} className="flex items-center justify-between gap-2 bg-surface border border-divider rounded-xl px-3 py-2">
                          <span className="text-xs text-ink truncate">{f.name}</span>
                          <button type="button" onClick={() => removeFile(i)} className="text-muted hover:text-accent" aria-label="Quitar archivo">
                            <X className="h-4 w-4" />
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="mt-6 flex flex-col sm:flex-row gap-3">
                  <button
                    type="submit"
                    disabled={status === 'sending'}
                    className="magnetic-btn flex-1 inline-flex items-center justify-center gap-2 bg-primary text-white px-6 py-3.5 rounded-full font-semibold shadow-lg shadow-primary/25 disabled:opacity-70"
                  >
                    {status === 'sending' ? 'Enviando…' : (<>Enviar solicitud <Send className="h-4 w-4" /></>)}
                  </button>
                  <a
                    href={waFromForm}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="magnetic-btn inline-flex items-center justify-center gap-2 bg-accent text-white px-6 py-3.5 rounded-full font-semibold"
                  >
                    <MessageCircle className="h-5 w-5" /> WhatsApp
                  </a>
                </div>
                <p className="mt-4 font-mono text-[10px] text-muted text-center">
                  Tus datos se usan solo para atender tu solicitud. Lee nuestro{' '}
                  <Link to="/privacidad" className="underline hover:text-primary">aviso de privacidad</Link>.
                </p>
              </form>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
