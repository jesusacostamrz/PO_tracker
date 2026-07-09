/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Azul Tinta — ancla la marca, transmite confianza
        primary: '#16216B',
        'primary-dark': '#0E1650',
        'primary-light': '#2178C4', // Azul Globo
        // Rojo Etiqueta — energía y calidez
        accent: '#E0382B',
        'accent-dark': '#B82A20',
        // Acentos CMYK — herencia de imprenta
        cyan: '#00AEEF',
        magenta: '#EC008C',
        yellow: '#FFC400',
        // Neutros
        background: '#F7F7F4', // Hueso
        surface: '#FFFFFF',
        ink: '#1A1C24', // Carbón
        muted: '#5A5D67', // Gris
        divider: '#E0E0DA', // Niebla
        deep: '#0A1038', // Azul tinta profundo para secciones oscuras
      },
      fontFamily: {
        display: ['"Archivo"', 'system-ui', 'sans-serif'],
        serif: ['"IBM Plex Serif"', 'Georgia', 'serif'],
        body: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      borderRadius: {
        '2.5xl': '1.25rem',
        '4xl': '2rem',
        '5xl': '2.5rem',
        '6xl': '3rem',
        '7xl': '4rem',
      },
      animation: {
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        blink: 'blink 1s step-end infinite',
        float: 'float 6s ease-in-out infinite',
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
      },
    },
  },
  plugins: [],
}
