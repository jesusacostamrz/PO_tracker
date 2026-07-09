import { useEffect } from 'react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { Navbar, Footer, WhatsAppFloat } from './components/chrome.jsx'
import Hero from './components/Hero.jsx'
import Materiales from './components/Materiales.jsx'
import SectoresSection from './components/SectoresSection.jsx'
import Cotizador from './components/Cotizador.jsx'
import Proceso from './components/Proceso.jsx'
import Clientes from './components/Clientes.jsx'
import Testimonios from './components/Testimonios.jsx'
import DisenoEnvio from './components/DisenoEnvio.jsx'
import Historia from './components/Historia.jsx'
import ContactForm from './components/ContactForm.jsx'

gsap.registerPlugin(ScrollTrigger)

export default function App() {
  useEffect(() => {
    const id = setTimeout(() => ScrollTrigger.refresh(), 300)
    return () => clearTimeout(id)
  }, [])

  return (
    <div className="relative">
      <div className="noise-overlay" />
      <Navbar />
      <main>
        <Hero />
        <Materiales />
        <SectoresSection />
        <Cotizador />
        <Proceso />
        <Clientes />
        <Testimonios />
        <DisenoEnvio />
        <Historia />
        <ContactForm />
      </main>
      <Footer />
      <WhatsAppFloat />
    </div>
  )
}
