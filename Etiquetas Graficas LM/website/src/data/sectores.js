/* Sectores en orden de prioridad del cliente. Imágenes generadas aparte
   en /img/sectores/*.jpg (con fallback a gradiente si faltan). */
export const SECTORES = [
  {
    slug: 'alimentos',
    name: 'Alimentos y bebidas',
    image: '/img/sectores/alimentos.jpg',
    line: 'Etiquetas que se ven de marca grande en el estante.',
    aplicaciones: [
      'Salsas y conservas artesanales',
      'Botellas y bebidas embotelladas',
      'Snacks, dulces y panadería',
      'Miel, mermeladas y aderezos',
    ],
  },
  {
    slug: 'agricola',
    name: 'Agrícola',
    image: '/img/sectores/agricola.jpg',
    line: 'Resistentes al campo, la humedad y el manejo rudo.',
    aplicaciones: [
      'Cajas y empaques de exportación',
      'Semillas y agroquímicos',
      'Trazabilidad y códigos de lote',
      'Etiquetas para producto fresco',
    ],
  },
  {
    slug: 'retail',
    name: 'Retail y comercio',
    image: '/img/sectores/retail.jpg',
    line: 'Marca, precio y código listos para el punto de venta.',
    aplicaciones: [
      'Etiquetas de producto y marca propia',
      'Precio y código de barras',
      'Promociones y ediciones especiales',
      'Sellos de garantía',
    ],
  },
  {
    slug: 'congelados',
    name: 'Congelados y enlatados',
    image: '/img/sectores/congelados.jpg',
    line: 'Adhesivo y color que aguantan el frío y la refrigeración.',
    aplicaciones: [
      'Mariscos y cárnicos congelados',
      'Enlatados y conservas',
      'Comida preparada refrigerada',
      'Etiquetas para congelador',
    ],
  },
  {
    slug: 'industrial',
    name: 'Industrial',
    image: '/img/sectores/industrial.jpg',
    line: 'Identificación durable para producto y proceso.',
    aplicaciones: [
      'Etiquetas de seguridad y advertencia',
      'Identificación de partes e inventario',
      'Lubricantes, químicos y solventes',
      'Marcado resistente a solventes',
    ],
  },
  {
    slug: 'farmaceutica',
    name: 'Farmacéutica',
    image: '/img/sectores/farmaceutica.jpg',
    line: 'Precisión, legibilidad y cumplimiento en cada pieza.',
    aplicaciones: [
      'Frascos, blísters y viales',
      'Lote, caducidad y variables',
      'Suplementos y productos naturistas',
      'Sellos de inviolabilidad',
    ],
  },
  {
    slug: 'cosmetica',
    name: 'Cosmética',
    image: '/img/sectores/cosmetica.jpg',
    line: 'Acabados finos que se sienten premium al tacto.',
    aplicaciones: [
      'Cremas, sueros y perfumería',
      'Transparentes y metalizados',
      'Cuidado personal y para el cabello',
      'Ediciones de temporada',
    ],
  },
]
