from pathlib import Path

from scrapy.http import HtmlResponse

from doctoralia_cl.parsing import parse_doctor, parse_price, split_titulo
from doctoralia_cl.spiders.doctoralia_cl import DoctoraliaCL

FIXTURE = Path(__file__).parent / 'fixtures' / 'perfil_sintetico.html'


def _response(body, url='https://www.doctoralia.cl/ana-ejemplo-prueba/psicologo/santiago'):
    return HtmlResponse(url=url, body=body, encoding='utf-8')


def test_parse_price_clp():
    assert parse_price('$35.000') == 35000
    assert parse_price('desde $ 1.200.000') == 1200000
    assert parse_price('Precio variable') is None


def test_split_titulo():
    assert split_titulo('Dra. Lina Pérez') == ('Dra.', 'Lina Pérez')
    assert split_titulo('Ps.  Ana Ejemplo') == ('Ps.', 'Ana Ejemplo')
    assert split_titulo('Ana Ejemplo') == ('', 'Ana Ejemplo')


def test_parse_perfil_sintetico():
    item = parse_doctor(_response(FIXTURE.read_bytes()))
    assert item['doctor_id'] == '123456'
    assert item['titulo'] == 'Ps.'
    assert item['nombre'] == 'Ana Ejemplo Prueba'
    assert item['especialidades'] == ['Psicólogo', 'Psicólogo infantil']
    assert item['registro_sis'] == '654321'
    assert item['ciudad'] == 'santiago'
    assert item['region'] == 'region-metropolitana'
    assert item['direcciones'] == [{
        'calle': 'Av. Providencia 1234, of. 501',
        'comuna': 'Providencia',
        'region': 'Región Metropolitana',
    }]
    assert item['previsiones'] == ['Fonasa', 'Banmédica', 'Colmena']
    assert item['telemedicina'] == 1
    assert item['opiniones'] == '42'
    assert item['calificacion'] == '4.9'
    assert item['opinion_mas_reciente'] == '2026-09-15T18:30:00-03:00'
    assert item['precio'] == 30000
    assert {s['servicio'] for s in item['servicios']} == {
        'Primera consulta psicología', 'Psicoterapia individual',
        'Terapia de pareja', 'Informe psicológico',
    }
    assert item['url'] == 'https://www.doctoralia.cl/ana-ejemplo-prueba/psicologo/santiago'


def test_pagina_no_perfil_devuelve_none():
    assert parse_doctor(_response(b'<html><body><h1>Buscar</h1></body></html>')) is None


def test_argumentos_spider():
    s = DoctoraliaCL(urls='lina-navarro-serna, https://www.doctoralia.cl/x/y/z')
    assert s.perfiles == [
        'https://www.doctoralia.cl/perfil/lina-navarro-serna',
        'https://www.doctoralia.cl/x/y/z',
    ]
    assert DoctoraliaCL(especialidad='psicologo', ciudad='santiago').start_urls == [
        'https://www.doctoralia.cl/psicologo/santiago'
    ]
    assert DoctoraliaCL().start_urls == ['https://www.doctoralia.cl/especialidades-medicas']


def test_listado_sigue_perfiles_y_paginacion():
    html = b'''<html><body>
      <div data-id="result-item"><a data-id="doctor-name" href="/ana-ejemplo/psicologo/santiago">Ana</a></div>
      <a href="/clinicas/clinica-x">Clinica</a>
      <a aria-label="next" href="/psicologo/santiago/2">Siguiente</a>
    </body></html>'''
    reqs = list(DoctoraliaCL(especialidad='psicologo').parse(
        _response(html, url='https://www.doctoralia.cl/psicologo/santiago')))
    urls = {r.url: r.callback.__name__ for r in reqs}
    assert urls == {
        'https://www.doctoralia.cl/psicologo/santiago/2': 'parse',
        'https://www.doctoralia.cl/ana-ejemplo/psicologo/santiago': 'parse_doctor',
    }
