"""Funciones puras para extraer datos de páginas de Doctoralia Chile.

Doctoralia (Docplanner) cambia su HTML con frecuencia, así que cada campo se
intenta obtener con varias estrategias en orden: configuración JS de la página
(ZLApp / dataLayer), microdatos schema.org, JSON-LD y, por último, el texto
visible. Si ninguna funciona el campo queda vacío en vez de romper el crawl.
"""
import json
import re
from datetime import datetime
from statistics import StatisticsError, mode

# Previsiones de salud chilenas que se buscan en el perfil.
PREVISIONES = [
    'Fonasa',
    'Banmédica',
    'Colmena',
    'Consalud',
    'Cruz Blanca',
    'Esencial',
    'Nueva Masvida',
    'Vida Tres',
    'Isalud',
    'Fundación',
    'Capredena',
    'Dipreca',
    'Particular',
]

_PRICE_RE = re.compile(r'\$\s*([\d.]+)')
_REGISTRO_RE = re.compile(
    r'(?:N[º°o]\.?\s*(?:de\s*)?registro|Registro\s+(?:Superintendencia|SIS|RNPI)[^:\d]{0,40})'
    r'\s*:?\s*(\d{3,})',
    re.IGNORECASE,
)
_TITULO_RE = re.compile(r'^(Dra?\.|Ps\.|Klgo\.|Klga\.|Nut\.|Mat\.|Prof\.|TO\.|Flgo\.|Flga\.)\s*', re.IGNORECASE)


def _clean(text):
    return re.sub(r'\s+', ' ', text or '').strip()


def _first(*values):
    for v in values:
        if v is not None and _clean(str(v)):
            return _clean(str(v))
    return ''


def _scripts_text(sel):
    return '\n'.join(sel.xpath('//script/text()').getall())


def _visible_text(sel):
    parts = sel.xpath('//body//text()[not(ancestor::script) and not(ancestor::style)]').getall()
    return _clean(' '.join(parts))


def _json_ld(sel):
    """Devuelve los objetos JSON-LD de la página, aplanando listas y @graph."""
    objs = []
    for raw in sel.xpath('//script[@type="application/ld+json"]/text()').getall():
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        for obj in stack:
            if isinstance(obj, dict):
                objs.append(obj)
                objs.extend(o for o in obj.get('@graph', []) if isinstance(o, dict))
    return objs


def _ld_physician(sel):
    for obj in _json_ld(sel):
        types = obj.get('@type', [])
        types = types if isinstance(types, list) else [types]
        if any(t in ('Physician', 'Person', 'MedicalBusiness', 'Dentist') for t in types):
            return obj
    return {}


def _js_value(scripts, key):
    """Lee `KEY: 'valor'` (ZLApp) o `['key'] = 'valor'` (dataLayer)."""
    m = re.search(rf"{key}\s*:\s*'?(.*?)'?\s*[,}}\n]", scripts)
    if m:
        return m.group(1)
    m = re.search(rf"\['{key}'\]\s*=\s*'(.*?)'", scripts)
    return m.group(1) if m else None


def parse_price(text):
    """'$35.000' -> 35000. Devuelve None si el texto no tiene monto."""
    m = _PRICE_RE.search(text or '')
    if not m:
        return None
    digits = m.group(1).replace('.', '')
    return int(digits) if digits.isdigit() else None


def split_titulo(nombre):
    """'Dra. Lina Navarro' -> ('Dra.', 'Lina Navarro')."""
    nombre = _clean(nombre)
    m = _TITULO_RE.match(nombre)
    if m:
        return m.group(1), nombre[m.end():]
    return '', nombre


def parse_servicios(sel):
    """Lista de {'servicio', 'precio', 'precio_texto'} a partir de los precios publicados."""
    servicios = []
    seen = set()
    for node in sel.xpath('//*[@data-id="service-price" or @itemprop="price" or contains(@class, "service-price")]'):
        precio_texto = _clean(' '.join(node.xpath('.//text()').getall())) or node.attrib.get('content', '')
        item = node.xpath(
            'ancestor::*[self::li or @data-id="service-item" or @data-test-id="address-service-item"'
            ' or contains(@class, "media")][1]'
        )
        nombre = ''
        if item:
            nombre = _clean(' '.join(
                t for t in item[0].xpath('.//text()[not(ancestor::script)]').getall()
            ).replace(precio_texto, ''))
        key = (nombre, precio_texto)
        if key in seen:
            continue
        seen.add(key)
        servicios.append({
            'servicio': nombre,
            'precio': parse_price(precio_texto),
            'precio_texto': precio_texto,
        })
    return servicios


def precio_mas_comun(servicios):
    """Precio numérico más común; si no hay, el texto más común (p. ej. 'Precio variable')."""
    numericos = [s['precio'] for s in servicios if s['precio'] is not None]
    textos = [s['precio_texto'] for s in servicios if s['precio_texto']]
    for values in (numericos, textos):
        try:
            return mode(values)
        except StatisticsError:
            continue
    return ''


def parse_direcciones(sel):
    direcciones = []
    for addr in sel.xpath('//*[@itemprop="address"]'):
        d = {
            'calle': _first(*addr.xpath('.//*[@itemprop="streetAddress"]//text() | .//*[@itemprop="streetAddress"]/@content').getall()),
            'comuna': _first(*addr.xpath('.//*[@itemprop="addressLocality"]//text() | .//*[@itemprop="addressLocality"]/@content').getall()),
            'region': _first(*addr.xpath('.//*[@itemprop="addressRegion"]//text() | .//*[@itemprop="addressRegion"]/@content').getall()),
        }
        if any(d.values()) and d not in direcciones:
            direcciones.append(d)
    if not direcciones:
        addr = _ld_physician(sel).get('address')
        for a in (addr if isinstance(addr, list) else [addr] if addr else []):
            if isinstance(a, dict):
                direcciones.append({
                    'calle': _clean(a.get('streetAddress')),
                    'comuna': _clean(a.get('addressLocality')),
                    'region': _clean(a.get('addressRegion')),
                })
    return direcciones


def parse_previsiones(text):
    encontradas = []
    lower = text.lower()
    for p in PREVISIONES:
        if re.search(rf'\b{re.escape(p.lower())}\b', lower):
            encontradas.append(p)
    return encontradas


def parse_doctor(sel, url=''):
    """Extrae un dict con los datos del profesional desde un Selector/Response de perfil.

    Devuelve None si la página no parece un perfil de profesional.
    """
    scripts = _scripts_text(sel)
    texto = _visible_text(sel)
    ld = _ld_physician(sel)

    doctor_id = _first(
        _js_value(scripts, 'DOCTOR_ID'),
        sel.xpath('//@data-doctor-id').get(),
    )
    nombre_raw = _first(
        sel.xpath('//h1//text()').get() and _clean(' '.join(sel.xpath('//h1//text()').getall())),
        _js_value(scripts, 'FULLNAME'),
        _js_value(scripts, 'doctor-name'),
        ld.get('name'),
        sel.xpath('//meta[@property="og:title"]/@content').get(),
    )
    if not doctor_id and not ld and not sel.xpath('//*[@itemprop="reviewCount"]'):
        return None

    titulo, nombre = split_titulo(nombre_raw)

    especialidades = [
        _clean(t) for t in sel.xpath(
            '//*[@itemprop="medicalSpecialty"]//text() | //*[@data-test-id="doctor-specializations"]//a//text()'
        ).getall() if _clean(t)
    ]
    ld_spec = ld.get('medicalSpecialty')
    if not especialidades and ld_spec:
        especialidades = [_clean(s) for s in (ld_spec if isinstance(ld_spec, list) else [ld_spec])]
    if not especialidades and _js_value(scripts, 'specialization'):
        especialidades = [_js_value(scripts, 'specialization')]
    especialidades = list(dict.fromkeys(especialidades))

    rating = ld.get('aggregateRating') or {}
    servicios = parse_servicios(sel)
    fechas = sel.xpath('//time/@datetime').getall()
    registro = _REGISTRO_RE.search(texto)

    tele_js = _js_value(scripts, 'virtual-consultation-profile')
    telemedicina = (
        int(tele_js in ('1', 'true', 'True')) if tele_js is not None
        else int(bool(re.search(r'consulta (en línea|online|virtual)|telemedicina', texto, re.I)))
    )

    return {
        'doctor_id': doctor_id,
        'titulo': titulo,
        'nombre': nombre,
        'especialidades': especialidades,
        'registro_sis': registro.group(1) if registro else '',
        'ciudad': _first(_js_value(scripts, 'city'), _js_value(scripts, 'NAME')),
        'region': _first(_js_value(scripts, 'region')),
        'direcciones': parse_direcciones(sel),
        'previsiones': parse_previsiones(texto),
        'telemedicina': telemedicina,
        'opiniones': _first(
            sel.xpath('//*[@itemprop="reviewCount"]/@content').get(),
            rating.get('reviewCount'),
        ),
        'calificacion': _first(
            sel.xpath('//*[@itemprop="ratingValue"]/@content').get(),
            rating.get('ratingValue'),
        ),
        'opinion_mas_reciente': max(fechas, default=''),
        'precio': precio_mas_comun(servicios),
        'servicios': servicios,
        'descripcion': _first(
            ld.get('description'),
            sel.xpath('//meta[@name="description"]/@content').get(),
        ),
        'url': _first(sel.xpath('//link[@rel="canonical"]/@href').get(), url),
        'fetch_time': f'{datetime.now():%Y-%m-%dT%H:%M:%S}',
    }
