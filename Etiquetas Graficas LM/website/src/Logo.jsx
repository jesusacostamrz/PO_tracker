/* ----------------------------------------------------------------
   Logo — Escudo Etiquetas Gráficas (globo + monograma EG + anillo)
   Recreación vectorial fiel al manual de marca, escalable y nítida.
---------------------------------------------------------------- */

// Solo el escudo (globo + EG + anillo con texto)
export function LogoMark({ size = 44, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 200 200"
      className={className}
      role="img"
      aria-label="Etiquetas Gráficas"
    >
      <defs>
        <path id="eg-arc-top" d="M 30 100 A 70 70 0 0 1 170 100" fill="none" />
        <path id="eg-arc-bot" d="M 34 100 A 66 66 0 0 0 166 100" fill="none" />
      </defs>

      {/* Disco base */}
      <circle cx="100" cy="100" r="96" fill="#FFFFFF" />
      {/* Anillo exterior */}
      <circle cx="100" cy="100" r="92" fill="none" stroke="#16216B" strokeWidth="4" />
      <circle cx="100" cy="100" r="84" fill="none" stroke="#16216B" strokeWidth="1.5" opacity="0.5" />

      {/* Texto del anillo */}
      <text
        fontFamily="Archivo, Arial, sans-serif"
        fontWeight="700"
        fontSize="20"
        letterSpacing="3"
        fill="#16216B"
      >
        <textPath href="#eg-arc-top" startOffset="50%" textAnchor="middle">
          ETIQUETAS
        </textPath>
      </text>
      <text
        fontFamily="Archivo, Arial, sans-serif"
        fontWeight="700"
        fontSize="20"
        letterSpacing="3"
        fill="#16216B"
      >
        <textPath href="#eg-arc-bot" startOffset="50%" textAnchor="middle">
          GRAFICAS
        </textPath>
      </text>

      {/* Globo */}
      <circle cx="100" cy="100" r="56" fill="#2178C4" />
      <g stroke="#FFFFFF" strokeWidth="1.6" fill="none" opacity="0.9">
        <ellipse cx="100" cy="100" rx="18" ry="56" />
        <ellipse cx="100" cy="100" rx="38" ry="56" />
        <line x1="44" y1="100" x2="156" y2="100" />
        <path d="M52 74 H148 M52 126 H148" />
      </g>

      {/* Monograma EG */}
      <text
        x="100"
        y="104"
        textAnchor="middle"
        dominantBaseline="central"
        fontFamily="Archivo, Arial Black, sans-serif"
        fontWeight="900"
        fontSize="62"
        fill="#E0382B"
        stroke="#FFFFFF"
        strokeWidth="1.5"
        paintOrder="stroke"
      >
        EG
      </text>
    </svg>
  )
}

// Lockup horizontal: escudo + nombre
export function LogoLockup({ size = 40, dark = false, className = '' }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <LogoMark size={size} />
      <div className="leading-none">
        <div
          className={`font-display font-extrabold tracking-tight ${
            dark ? 'text-white' : 'text-primary'
          }`}
          style={{ fontSize: size * 0.4 }}
        >
          ETIQUETAS GRÁFICAS
        </div>
        <div
          className={`font-mono uppercase tracking-[0.3em] ${
            dark ? 'text-white/60' : 'text-muted'
          }`}
          style={{ fontSize: size * 0.2, marginTop: 2 }}
        >
          de Los Mochis
        </div>
      </div>
    </div>
  )
}

export default LogoMark
