import re
from urllib.parse import urlparse

from scrapy import Request
from scrapy.spiders import Spider

from doctoralia_cl.parsing import parse_doctor

BASE = 'https://www.doctoralia.cl'

# Rutas de un solo segmento que no son especialidades ni perfiles.
_NO_ESPECIALIDAD = {
    'especialidades-medicas', 'preguntas-medicas', 'enfermedades', 'tratamientos',
    'clinicas', 'centros-medicos', 'login', 'registro', 'terminos', 'privacidad',
    'ayuda', 'blog', 'pro', 'consulta-online',
}


class DoctoraliaCL(Spider):
    """Recorre doctoralia.cl y extrae datos de profesionales de la salud.

    Argumentos (-a):
      urls         Perfiles puntuales, separados por coma (URL completa o slug).
      especialidad Slug de especialidad, p. ej. psicologo, pediatra.
      ciudad       Slug de ciudad, p. ej. santiago, valparaiso (requiere especialidad).
    Sin argumentos recorre todas las especialidades.
    """
    name = 'doctoralia_cl'
    allowed_domains = ['doctoralia.cl']

    def __init__(self, urls=None, especialidad=None, ciudad=None, **kwargs):
        super().__init__(**kwargs)
        self.perfiles = [self._perfil_url(u) for u in (urls or '').split(',') if u.strip()]
        if especialidad:
            path = f'/{especialidad.strip("/")}' + (f'/{ciudad.strip("/")}' if ciudad else '')
            self.start_urls = [BASE + path]
        else:
            self.start_urls = [f'{BASE}/especialidades-medicas']

    @staticmethod
    def _perfil_url(u):
        u = u.strip()
        if u.startswith('http'):
            return u
        return f'{BASE}/perfil/{u.strip("/")}'

    async def start(self):
        if self.perfiles:
            for url in self.perfiles:
                yield Request(url, callback=self.parse_doctor)
            return
        for url in self.start_urls:
            yield Request(url, callback=self.parse)

    def parse(self, response):
        """Página índice de especialidades o listado de resultados."""
        rx, rc = response.xpath, response.css

        # Índice de especialidades -> listados.
        if urlparse(response.url).path.rstrip('/') == '/especialidades-medicas':
            links = rc('.align-items-center .text-muted::attr(href)').getall()
            if not links:
                links = [
                    h for h in rx('//main//a/@href | //body//ul//a/@href').getall()
                    if self._es_especialidad(response.urljoin(h))
                ]
            yield from response.follow_all(set(links), self.parse)
            return

        # Paginación.
        siguiente = rx('//a[@aria-label="next"]/@href | //link[@rel="next"]/@href | '
                       '//li[contains(@class,"next")]/a/@href').getall()
        yield from response.follow_all(set(siguiente), self.parse)

        # Perfiles del listado.
        links = rx('//div[@class="media"]/div[@class="pr-1"]//@href').getall()
        links += rx('//*[@data-id="result-item"]//a[@data-id="doctor-name" or @itemprop="url"]/@href').getall()
        links += rx('//*[contains(@itemtype, "Physician")]//a[@itemprop="url"]/@href').getall()
        links += [h for h in rx('//a/@href').getall() if '/perfil/' in h]
        links = {l for l in links if '/clinicas/' not in l and '/centros-medicos/' not in l}
        yield from response.follow_all(links, self.parse_doctor)

    @staticmethod
    def _es_especialidad(url):
        p = urlparse(url)
        partes = [s for s in p.path.split('/') if s]
        return (
            p.netloc.endswith('doctoralia.cl') and len(partes) == 1
            and partes[0] not in _NO_ESPECIALIDAD and re.fullmatch(r'[a-z-]+', partes[0])
        )

    def parse_doctor(self, response):
        item = parse_doctor(response, url=response.url)
        if item:
            yield item
        else:
            self.logger.warning('No parece un perfil de profesional: %s', response.url)
