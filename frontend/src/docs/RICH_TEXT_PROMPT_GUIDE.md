# Guia de Rich Text para prompts (EventCut)

Esta guia describe que formato acepta el sistema de texto enriquecido en EventCut y como escribir prompts para obtener resultados que se rendericen bien en frontend.

Basado en:
- `src/components/util/RichTextEditor.vue`
- `src/components/util/RichTextRenderer.vue`
- `src/utils/richTextEmbeds.js`

---

## 1) Formato de entrada real

- El editor trabaja y emite **HTML enriquecido**.
- El renderer recibe `content` (string) y:
  - Si detecta texto plano, lo convierte a `<p>...</p>` por linea.
  - Si detecta HTML, lo sanitiza y renderiza.
- **Markdown no se parsea automaticamente**. Si pides markdown en prompts, conviertelo a HTML antes de renderizar.

---

## 2) Elementos y estilos soportados

### Texto y estructura
- Parrafos: `<p>`
- Titulos: `<h1>`, `<h2>`, `<h3>`
- Listas:
  - Vinetas: `<ul><li>`
  - Numeradas: `<ol><li>`
- Citas: `<blockquote>`
- Imagenes: `<img src="...">`
- Enlaces: `<a href="...">`
- Tambien existen estilos para: `<strong>`, `<em>`, `<u>`, `<s>`, `<code>`, `<pre>`, `<hr>`

### Alineacion
- Izquierda / centro / derecha (aplica sobre `heading` y `paragraph`)

---

## 3) Colores permitidos (Color Pair Mark)

Se aplican como marca `span` con `data-color-pair` y clase CSS:

- Rosa: `rt-color-pair-rose`
- Azul: `rt-color-pair-blue`
- Esmeralda: `rt-color-pair-emerald`
- Ambar: `rt-color-pair-amber`
- Violeta: `rt-color-pair-violet`
- Slate: `rt-color-pair-slate`

### Referencia visual (light/dark)
- rose: `#e11d48` / `#fda4af`
- blue: `#2563eb` / `#93c5fd`
- emerald: `#059669` / `#6ee7b7`
- amber: `#d97706` / `#fcd34d`
- violet: `#7c3aed` / `#c4b5fd`
- slate: `#334155` / `#cbd5e1`

Ejemplo:
```html
<p><span data-color-pair="emerald" class="rt-color-pair-emerald">Cupo limitado</span></p>
```

---

## 4) Emojis disponibles en toolbar

Lista cerrada actual:
`😀 🔥 🚀 🎉 ✅ ⚡ 💡 📌 📣 🎯 🧠 🌟 💬 📷 📅 🎵`

---

## 5) Reglas de enlaces, imagenes y embeds

### Enlaces
- Se normalizan con `https://` si no traen protocolo.
- `target="_blank"` y `rel="noopener noreferrer"` al renderizar.
- Se autolinkean URLs en texto plano.

### Imagenes embebibles por URL directa
Solo si terminan en extensiones:
- `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.avif`, `.svg`
- Acepta querystring (ej: `.png?size=1200`)

### YouTube soportado
- `https://youtu.be/{id}`
- `https://youtube.com/watch?v={id}`
- `https://youtube.com/embed/{id}`
- `https://youtube.com/shorts/{id}`
- tambien `m.youtube.com`

### Cuando se convierte un link a embed visual
El renderer reemplaza `<a>` por embed solo si:
1. URL corresponde a imagen o YouTube, y
2. El texto del link esta vacio o es exactamente la URL.

Si el link tiene texto personalizado (ej: `Ver trailer`), no lo reemplaza por embed.

---

## 6) Reglas de seguridad/sanitizacion

Se eliminan por seguridad:
- Tags: `script`, `iframe`, `object`, `embed`, `form`, `input`, `button`
- Atributos de evento: cualquiera que empiece con `on` (`onclick`, etc.)

Nota:
- Aunque `iframe` se elimina al sanitizar HTML de entrada, los embeds de YouTube se insertan luego por logica interna segura (`youtube-nocookie`).

---

## 7) Modo ocultar URLs y media (`hideUrlsAndMedia`)

Cuando esta activo:
- Elimina `img`, `video`, `audio`, `source`, `picture`, `iframe`
- Quita enlaces sin texto util
- Reemplaza enlaces con texto por su etiqueta limpia (sin URL)
- Elimina URLs en nodos de texto

---

## 8) Recomendaciones para prompts (para aprovechar el sistema)

Pide al modelo que devuelva HTML limpio y semantico:
- Usa `<h2>` y `<h3>` para secciones (evita saltar directamente a `<h1>` si no corresponde)
- Maximo 1-2 niveles de lista por claridad
- Inserta URLs completas (`https://...`) para enlaces y media
- Para forzar embed, deja la URL sola dentro del `<a>`
- Usa solo los 6 color-pair permitidos
- Emojis solo de la lista soportada para consistencia visual

---

## 9) Plantilla de prompt recomendada

```text
Genera contenido en HTML (NO markdown), compatible con EventCut.
Reglas:
- Usa solo: p, h2, h3, ul, ol, li, blockquote, strong, em, u, s, a, img, code, pre, hr, span[data-color-pair]
- Enlaces siempre https://
- Si agregas YouTube o imagen para embed automatico, coloca el <a> con texto exactamente igual a la URL
- Colores permitidos: rose, blue, emerald, amber, violet, slate (data-color-pair y clase rt-color-pair-*)
- Emojis permitidos: 😀 🔥 🚀 🎉 ✅ ⚡ 💡 📌 📣 🎯 🧠 🌟 💬 📷 📅 🎵
- No incluyas scripts, iframes externos, ni atributos on*
Contexto de negocio: [describe evento/comunidad]
Objetivo del copy: [conversion/registro/asistencia]
Tono: [cercano/profesional]
```

---

## 10) Ejemplo de salida ideal (negocio EventCut)

```html
<h2>🎉 Meetup de Creadores en Comunidad Centro</h2>
<p>Unete a una jornada practica para compartir ideas, networking y casos reales.</p>

<p>
  <span data-color-pair="emerald" class="rt-color-pair-emerald">✅ Cupos confirmados:</span>
  120 asistentes
</p>

<ul>
  <li>📅 Sabado 24 de abril, 18:00</li>
  <li>📍 Auditorio Comunidad Centro</li>
  <li>🎵 Cierre con showcase local</li>
</ul>

<blockquote>"Trae una idea y sal con colaboradores."</blockquote>

<p>Trailer del evento:</p>
<p><a href="https://youtu.be/dQw4w9WgXcQ">https://youtu.be/dQw4w9WgXcQ</a></p>
```

---

## 11) Prompts listos por escenario

### A) Prompt para descripcion de eventos

Usa esta plantilla cuando quieras generar la descripcion de un evento en EventCut:

```text
Genera una descripcion de evento en HTML (NO markdown), compatible con EventCut.

Objetivo:
- Convertir visitas en registros al evento.

Contexto del evento:
- Nombre: [nombre del evento]
- Categoria: [tecnologia/musica/deportes/emprendimiento/etc]
- Fecha y hora: [fecha]
- Lugar: [lugar]
- Comunidad organizadora: [nombre]
- Perfil del publico: [principiantes/intermedios/profesionales]

Reglas de formato (obligatorias):
- Usa solo: p, h2, h3, ul, ol, li, blockquote, strong, em, u, s, a, img, code, pre, hr, span[data-color-pair]
- Usa h2 para titulo principal y h3 para subtitulos
- Enlaces siempre https://
- Si agregas YouTube o imagen para embed usa solo la URL
- Colores permitidos: rose, blue, emerald, amber, violet, slate (data-color-pair + clase rt-color-pair-*)
- Emojis permitidos: 😀 🔥 🚀 🎉 ✅ ⚡ 💡 📌 📣 🎯 🧠 🌟 💬 📷 📅 🎵
- No incluyas scripts, iframes externos, ni atributos on*

Estructura esperada:
1) Titulo atractivo con beneficio claro
2) Parrafo breve de propuesta de valor
3) Lista con agenda o puntos clave
4) Bloque de datos logisticos (fecha, lugar, modalidad)
5) Llamado a la accion para registrarse

Tono:
- Claro, cercano y orientado a accion.

Devuelve solo HTML valido.
```

### B) Prompt para post de comunidades

Usa esta plantilla cuando quieras generar publicaciones para feed o muro de comunidad:

```text
Genera un post de comunidad en HTML (NO markdown), compatible con EventCut.

Objetivo:
- Incentivar interaccion (comentarios, reacciones, participacion).

Contexto de la comunidad:
- Nombre: [nombre comunidad]
- Tema central: [tema]
- Tipo de publicacion: [anuncio/debate/resumen/invitacion]
- Audiencia: [nuevos miembros/miembros activos/todos]

Reglas de formato (obligatorias):
- Usa solo: p, h2, h3, ul, ol, li, blockquote, strong, em, u, s, a, img, code, pre, hr, span[data-color-pair]
- Enlaces siempre https://
- Si agregas YouTube o imagen para embed automatico, usa <a> con texto exactamente igual a la URL
- Colores permitidos: rose, blue, emerald, amber, violet, slate (data-color-pair + clase rt-color-pair-*)
- Emojis permitidos: 😀 🔥 🚀 🎉 ✅ ⚡ 💡 📌 📣 🎯 🧠 🌟 💬 📷 📅 🎵
- No incluyas scripts, iframes externos, ni atributos on*

Estructura esperada:
1) Hook inicial de 1-2 lineas
2) Cuerpo principal en parrafos cortos
3) Lista breve de puntos accionables (si aplica)
4) Pregunta final para abrir conversacion

Tono:
- Cercano, dinamico y comunitario.

Devuelve solo HTML valido.
```

### C) Atajo rapido para elegir plantilla

- Usa la plantilla de **eventos** cuando el KPI sea: registros, asistencia, conversion.
- Usa la plantilla de **comunidades** cuando el KPI sea: engagement, comentarios, actividad.
