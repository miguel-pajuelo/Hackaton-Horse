# Referencia de estilo: «atlas» (hueapp.io/showcase/atlas/landing-page), versión light

Medido con estilos computados en el navegador (14/11/2026).

## Paleta

| Rol | Hex | RGB | Uso observado |
|---|---|---|---|
| Fondo papel | `#F5F1E8` | 245,241,232 | Fondo de body y secciones; texto sobre botones primarios |
| Superficie alterna | `#EBE5D3` | 235,229,211 | Tarjetas, bandas de sección, paneles |
| Tinte de acento | `#E8CFC0` | 232,207,192 | Fondos destacados suaves (badges, resaltados) |
| Borde / regla | `#C9BFA3` | 201,191,163 | Líneas de 1px (el borde más usado, ~25 elementos) |
| Tinta principal | `#0A2540` | 10,37,64 | Titulares, texto fuerte, botón de tema |
| Texto secundario | `#3C5878` | 60,88,120 | Párrafos, navegación, metadatos (el color de texto más usado) |
| Acento (óxido) | `#B8441F` | 184,68,31 | CTA principal, bordes de acento, etiquetas puntuales |

Proporción aproximada: ~85 % crema/papel, ~12 % azul tinta (texto), ~3 % óxido. El acento se reserva para la acción principal y pocos detalles.

```css
:root {
  --paper: #F5F1E8;
  --surface: #EBE5D3;
  --accent-tint: #E8CFC0;
  --rule: #C9BFA3;
  --ink: #0A2540;
  --ink-soft: #3C5878;
  --accent: #B8441F;
}
```

## Tipografía (tres familias con roles fijos)

- **IBM Plex Serif 500** – titulares. H1 44px / lh 1.02 / tracking −0.88px (−0.02em). H2 34–36px / lh 1.05–1.1 / tracking −0.015em a −0.02em. Logotipo «atlas» en minúscula, 22px.
- **Inter** – cuerpo e interfaz. 16px/400 para párrafos, 13–14px/500 para botones y enlaces (tracking +0.01em).
- **IBM Plex Mono** – capa «técnica»: navegación (12px, minúsculas, +0.04em), eyebrows y etiquetas (10–11px, MAYÚSCULAS, +0.08em), metadatos y coordenadas.
- Iconos: Phosphor (trazo fino), 14px.

## Forma y componentes

- **Radio 2px** en todo: casi rectangular, aspecto de documento impreso / carta náutica.
- **Sin sombras**: la jerarquía sale de bordes de 1px `#C9BFA3` y del cambio de superficie (`#F5F1E8` → `#EBE5D3`).
- **Botón primario**: fondo `#B8441F`, texto `#F5F1E8`, Inter 500 14px, padding horizontal 24px, radio 2px.
- **Botón secundario**: transparente, texto `#0A2540`, borde de 1px.
- **Enlace de texto**: Inter 500 14px tinta, con flecha «→» y subrayado o borde inferior (padding-bottom 2px).
- **Conmutador de tema**: Mono 11px en mayúsculas sobre fondo tinta.
- Contenedor máx. **1200px**; columnas de texto ~640px; la cuadrícula se marca con reglas finas.

## Tono y concepto

- Metáfora sostenida de **cartografía / navegación** («Chart the systems», «coordinate», «waypoint», «ship's log», «Two berths», «Take the helm»). Todo el texto y las secciones refuerzan el tema.
- Titulares cortos y declarativos, terminados en punto.
- Estética editorial y analógica: papel cálido, tinta azul marino, acento de óxido (como lacre o tinta roja de un mapa), etiquetas mono como anotaciones de un plano.
- Mucho espacio en blanco, pocos elementos por sección: titular serif + párrafo + un CTA.

## Cómo aplicarlo a nuestra app

1. Sustituir fondos blancos por `--paper` y tarjetas por `--surface` con borde de 1px `--rule`; quitar sombras.
2. Titulares en serif (IBM Plex Serif, gratis en Google Fonts), UI en Inter, y datos, cifras, KPIs y etiquetas en Plex Mono.
3. Un único color de acento (`--accent`) para el CTA principal y estados críticos; el resto en tinta y tinta suave.
4. Radio de 2px y rejilla con reglas finas para dar un aspecto de «informe técnico».
5. Buscar una metáfora propia del dominio y aplicarla de forma coherente en los textos.

Nota: en Streamlit se puede aplicar con `.streamlit/config.toml` (`backgroundColor`, `secondaryBackgroundColor`, `textColor`, `primaryColor`) más CSS inyectado para tipografías, bordes y radios.
