# Doctoralia Chile Scraper

Scraper de [doctoralia.cl](https://www.doctoralia.cl) basado en
[corralm/doctoralia-scraper](https://github.com/corralm/doctoralia-scraper) (Brasil),
adaptado al contexto chileno: precios en CLP, previsiones (Fonasa / Isapres),
número de registro en la Superintendencia de Salud, comunas y regiones.

## Instalación

```bash
cd doctoralia-cl
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Uso

Todos los comandos se ejecutan dentro de `doctoralia-cl/`. `-O` sobrescribe el
archivo de salida (`.json`, `.jl`, `.csv`).

```bash
# Uno o varios perfiles puntuales (slug o URL completa, separados por coma)
scrapy crawl doctoralia_cl -a urls=lina-navarro-serna -O perfil.json

# Una especialidad, opcionalmente en una ciudad
scrapy crawl doctoralia_cl -a especialidad=psicologo -a ciudad=santiago -O psicologos.jl

# Todo el sitio (lento: respeta robots.txt y usa autothrottle)
scrapy crawl doctoralia_cl -O doctoralia_cl.jl

# Limitar la cantidad de perfiles para probar
scrapy crawl doctoralia_cl -a especialidad=pediatra -s CLOSESPIDER_ITEMCOUNT=20 -O muestra.jl
```

Leer los resultados con pandas:

```python
import pandas as pd
df = pd.read_json('psicologos.jl', lines=True)
```

## Atributos

| Atributo | Descripción |
|---|---|
| `doctor_id` | ID interno de Doctoralia |
| `titulo` | Dr., Dra., Ps., Klgo., etc. |
| `nombre` | Nombre completo |
| `especialidades` | Lista de especialidades |
| `registro_sis` | Nº de registro en la Superintendencia de Salud, si aparece en el perfil |
| `ciudad`, `region` | Ciudad y región principal (slugs de Doctoralia) |
| `direcciones` | Lista de `{calle, comuna, region}` de cada consulta |
| `previsiones` | Fonasa / Isapres mencionadas en el perfil |
| `telemedicina` | 1 si ofrece consulta en línea, 0 si no |
| `opiniones`, `calificacion` | Número de opiniones y nota promedio |
| `opinion_mas_reciente` | Fecha de la opinión más reciente |
| `precio` | Precio más común en CLP (o texto como "Precio variable") |
| `servicios` | Lista de `{servicio, precio, precio_texto}` |
| `descripcion` | Descripción / meta description del perfil |
| `url`, `fetch_time` | URL canónica y fecha de extracción |

## Diferencias con el scraper de Brasil

- Dominio `doctoralia.cl`, índice en `/especialidades-medicas`.
- Redirecciones habilitadas: `/perfil/<slug>` redirige a la URL canónica.
- Modo de perfiles puntuales (`-a urls=`) y filtros por especialidad/ciudad.
- Cada campo se extrae con varias estrategias (config JS, microdatos, JSON-LD,
  texto visible) en vez de depender de la posición de un `<script>`, que se
  rompe cuando el sitio cambia.
- Campos nuevos: `registro_sis`, `direcciones`, `previsiones`, `calificacion`, `servicios`.

## Pruebas

```bash
pytest
```

`tests/fixtures/perfil_sintetico.html` es un perfil **ficticio** que imita la
estructura habitual de Doctoralia. Los selectores no han sido validados contra
el HTML real de doctoralia.cl; si algún campo sale vacío, guarda una página
real (`scrapy fetch --nolog <url> > pagina.html`) y ajusta `doctoralia_cl/parsing.py`.

## Uso responsable

Revisa los términos de uso de Doctoralia antes de recolectar datos a escala,
mantén el ritmo bajo (configurado por defecto) y trata la información personal
conforme a la Ley 19.628 sobre protección de la vida privada.
