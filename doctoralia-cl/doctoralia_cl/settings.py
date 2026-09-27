BOT_NAME = 'doctoralia_cl'

SPIDER_MODULES = ['doctoralia_cl.spiders']
NEWSPIDER_MODULE = 'doctoralia_cl.spiders'

LOG_LEVEL = 'INFO'

# /perfil/<slug> redirige a la URL canónica del profesional, así que las
# redirecciones deben estar habilitadas (el scraper de Brasil las desactivaba).
REDIRECT_ENABLED = True

# Recorrido en anchura para no quedarse atrapado en una sola especialidad.
DEPTH_PRIORITY = 1
SCHEDULER_DISK_QUEUE = 'scrapy.squeues.PickleFifoDiskQueue'
SCHEDULER_MEMORY_QUEUE = 'scrapy.squeues.FifoMemoryQueue'

# Ser respetuoso con el sitio.
ROBOTSTXT_OBEY = True
COOKIES_ENABLED = False
CONCURRENT_REQUESTS_PER_DOMAIN = 2
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 5
AUTOTHROTTLE_MAX_DELAY = 60
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-CL,es;q=0.9',
}

TWISTED_REACTOR = 'twisted.internet.asyncioreactor.AsyncioSelectorReactor'
FEED_EXPORT_ENCODING = 'utf-8'
