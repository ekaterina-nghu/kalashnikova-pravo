"""Build static service pages: python3 tools/render_services.py."""
from html import escape
import json
from pathlib import Path
from string import Template
from xml.etree import ElementTree

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
BASE = 'https://kalashnikova-pravo.ru'
CHANNELS = {
    'MAX': 'https://max.ru/u/f9LHodD0cOKdU3GIbdlTxom1ASJUoEKOcbNrV-EH7odaSLbE08D0mmyXYG8',
    'Telegram': 'https://t.me/kalashnikova_pravo',
}


def buttons(short=False):
    links = []
    for name, url in CHANNELS.items():
        style = 'button primary' if name == 'MAX' else 'button'
        label = name if short else f'Написать в {name}'
        links.append(f'<a class="{style}" href="{url}" data-channel="{name.lower()}" '
                     f'target="_blank" rel="noopener noreferrer">{label} <span aria-hidden="true">↗</span></a>')
    return '<div class="actions">' + '\n'.join(links) + '</div>'


def items(values):
    return '\n'.join(f'<li>{escape(value)}</li>' for value in values)


def price(amount):
    return 'от ' + f'{amount:,}'.replace(',', '\u00a0') + '\u00a0₽'


def structured_data(page, url):
    label = page['label']
    person = BASE + '/#ekaterina'
    name, minimum, _ = page['rates'][0]
    graph = [
        {'@type': 'Person', '@id': person, 'name': 'Калашникова Екатерина Павловна', 'telephone': '+79837202800', 'jobTitle': 'Юрист', 'url': BASE + '/'},
        {'@type': 'WebPage', '@id': url + '#page', 'url': url, 'name': page['title'],
         'description': page['description'], 'inLanguage': 'ru', 'mainEntity': {'@id': url + '#service'},
         'breadcrumb': {'@id': url + '#breadcrumbs'}},
        {'@type': 'BreadcrumbList', '@id': url + '#breadcrumbs', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Главная', 'item': BASE + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Услуги', 'item': BASE + '/uslugi/'},
            {'@type': 'ListItem', 'position': 3, 'name': label, 'item': url}]},
        {'@type': 'Service', '@id': url + '#service', 'name': ''.join(page['h1']), 'url': url,
         'description': ' '.join(page['outputs']), 'provider': {'@id': person},
         'areaServed': {'@type': 'Country', 'name': 'Россия'},
         'offers': {'@type': 'Offer', 'name': name, 'url': url + '#pricing',
                    'priceSpecification': {'@type': 'PriceSpecification', 'minPrice': minimum, 'priceCurrency': 'RUB'}}},
    ]
    return json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False, indent=2).replace('<', r'\u003c')


def render(page, pages, template, header, articles):
    url = f"{BASE}/uslugi/{page['slug']}/"
    parts = {key: escape(page[key]) for key in ('label', 'title', 'description', 'intro', 'contact')}
    parts.update({key: items(page[key]) for key in ('outputs', 'situations', 'docs', 'steps')})
    parts['rates'] = '\n'.join(f'<div><dt>{escape(name)}</dt><dd><strong>{price(amount)}</strong>'
                              f'<p>{escape(note)}</p></dd></div>' for name, amount, note in page['rates'])
    parts['faq'] = '\n'.join(f'<details><summary>{escape(q)}</summary><p>{escape(a)}</p></details>'
                            for q, a in page['faq'])
    sources = ' · '.join(f'<a href="{escape(link)}">{escape(label)}</a>' for label, link in page['sources'])
    parts['sources'] = f'<p class="note">Проверено 27 ноября 2026 года. {sources}.</p>' if sources else ''
    parts['related'] = '\n'.join(f'<a href="/uslugi/{slug}/">{escape(pages[slug]["label"])} '
                                 '<span aria-hidden="true">→</span></a>' for slug in page['related'])
    reading = [entry for entry in articles if page['slug'] in entry['services']]
    parts['reading'] = ''
    if reading:
        links = ''.join(f'<a href="/stati/{a["slug"]}/">{escape(a["title"])}</a>' for a in reading)
        parts['reading'] = f'<section class="wrap related reading"><h2>Полезные статьи</h2><nav aria-label="Статьи по теме">{links}</nav></section>'
    lead, emphasis = page['h1']
    return template.substitute(parts, header=header, buttons=buttons(), short_buttons=buttons(True),
                               schema=structured_data(page, url), url=url, starting=price(page['rates'][0][1]),
                               h1=escape(lead) + '<em>' + escape(emphasis) + '</em>')


def editorial_pages(pages, articles, header):
    template = Template((TOOLS / 'editorial-page.html').read_text())
    routes = []
    label = 'Правовой кабинет Екатерины Калашниковой'
    org = {'@type': 'Organization', 'name': label, 'url': BASE + '/'}

    def save(route, title, description, heading, category, content, entries, parent=None, article=None):
        url = BASE + route
        crumbs = [('Главная', '/')]
        if parent:
            crumbs.append(parent)
        crumbs.append((heading, route))
        crumb_html = ' / '.join(f'<a href="{path}">{escape(name)}</a>' for name, path in crumbs[:-1])
        crumb_html += f' / <span aria-current="page">{escape(heading)}</span>'
        breadcrumb = {'@type': 'BreadcrumbList', '@id': url + '#breadcrumbs',
                      'itemListElement': [{'@type': 'ListItem', 'position': i, 'name': name, 'item': BASE + path}
                                          for i, (name, path) in enumerate(crumbs, 1)]}
        page = {'@type': 'WebPage' if article else 'CollectionPage', '@id': url + '#page', 'url': url,
                'name': title, 'description': description, 'inLanguage': 'ru', 'breadcrumb': {'@id': breadcrumb['@id']}}
        if article:
            entity = {'@type': 'Article', '@id': url + '#article', 'headline': heading, 'description': description,
                      'dateModified': article['reviewed'], 'author': org, 'publisher': org, 'inLanguage': 'ru',
                      'mainEntityOfPage': {'@id': page['@id']}, 'articleSection': category,
                      'citation': [source for _, source in article['sources']]}
        else:
            entity = {'@type': 'ItemList', '@id': url + '#list', 'numberOfItems': len(entries),
                      'itemListElement': [{'@type': 'ListItem', 'position': i, 'name': name, 'url': BASE + path}
                                          for i, (name, path) in enumerate(entries, 1)]}
        page['mainEntity'] = {'@id': entity['@id']}
        schema = json.dumps({'@context': 'https://schema.org', '@graph': [page, breadcrumb, entity]}, ensure_ascii=False, indent=2)
        result = template.substitute(title=escape(title), description=escape(description), heading=escape(heading),
                                     category=escape(category), url=url, header=header, crumbs=crumb_html,
                                     content=content, schema=schema, kind='article' if article else 'website')
        folder = ROOT / route.strip('/')
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'index.html').write_text(result)
        routes.append(route)

    def card(name, route, description, detail):
        return (f'<li><a class="directory-card" href="{route}"><h3>{escape(name)}</h3>'
                f'<p>{escape(description)}</p><span>{escape(detail)} <b aria-hidden="true">→</b></span></a></li>')

    def service_card(slug):
        p = pages[slug]
        return card(p['label'], f'/uslugi/{slug}/', p['rates'][0][2], price(p['rates'][0][1]))

    groups = [
        ('Консультация и документы', ['konsultaciya', 'dosudebnaya-pretenziya', 'iskovoe-zayavlenie', 'dogovory']),
        ('Деньги и покупки', ['vzyskanie-dolga', 'otmena-sudebnogo-prikaza', 'zashchita-prav-potrebiteley']),
        ('Семья и работа', ['vzyskanie-alimentov', 'semeynye-spory', 'trudovye-spory'])]
    entries, sections = [], []
    for name, slugs in groups:
        entries.extend((pages[s]['label'], f'/uslugi/{s}/') for s in slugs)
        cards = ''.join(service_card(slug) for slug in slugs)
        sections.append(f'<section class="directory-group"><h2>{name}</h2><ul class="directory">{cards}</ul></section>')
    if len(entries) != len(pages) or len(set(entries)) != len(entries):
        raise ValueError('Каждая услуга должна входить в одну группу каталога')
    save('/uslugi/', 'Юридические услуги и начальные цены | Екатерина Калашникова',
         'Выберите, с чем нужна помощь. В каждой карточке указаны начальная стоимость, состав работы и документы для первого обращения.',
         'Каталог юридических услуг', 'Новосибирск · Онлайн по России', ''.join(sections), entries)

    article_links = [(a['title'], f'/stati/{a["slug"]}/') for a in articles]
    cards = ''.join(card(name, link, a['description'], a['topic']) for (name, link), a in zip(article_links, articles))
    save('/stati/', 'Полезные статьи по гражданскому праву | Правовой кабинет',
         'Пошаговые материалы о судебном приказе, возврате займа и претензиях. В каждом разборе есть перечень документов и ссылки на нормы закона.',
         'Полезные статьи', 'Практика и документы', f'<ul class="directory">{cards}</ul>', article_links)

    for article, (heading, route) in zip(articles, article_links):
        links = ''.join(f'<li><a href="#step-{i}">{escape(name)}</a></li>' for i, (name, _) in enumerate(article['sections'], 1))
        sections = [f'<div class="article-layout"><aside><nav aria-label="Содержание статьи"><h2>В этой статье</h2><ol>{links}</ol></nav></aside><article>']
        for i, (name, paragraph) in enumerate(article['sections'], 1):
            sections.append(f'<section id="step-{i}"><h2>{escape(name)}</h2><p>{escape(paragraph)}</p></section>')
        sections.append('<section class="check"><h2>Что проверить</h2><ul>' + items(article['check']) + '</ul></section>')
        sources = ''.join(f'<li><a href="{escape(link)}">{escape(name)}</a></li>' for name, link in article['sources'])
        sections.append(f'<section><h2>Правовые источники</h2><p>Проверено <time datetime="{article["reviewed"]}">27 ноября 2026 года</time>.</p><ul>{sources}</ul></section>')
        cards = ''.join(service_card(slug) for slug in article['services'])
        sections.append(f'<section><h2>Помощь по этой теме</h2><ul class="directory in-article">{cards}</ul></section></article></div>')
        save(route, heading + ' | Правовой кабинет', article['description'], heading, article['topic'],
             ''.join(sections), [], ('Полезные статьи', '/stati/'), article)
    return routes


def legal_page(header):
    route = '/pravovaya-informaciya/'
    url = BASE + route
    title = 'Исполнитель и политика обработки персональных данных | Правовой кабинет'
    heading = 'Исполнитель и персональные данные'
    description = 'Сведения об исполнителе юридических услуг, порядок обработки данных и рабочий контакт для обращений.'
    crumbs = '<a href="/">Главная</a> / <span aria-current="page">Правовая информация</span>'
    schema = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'WebPage', '@id': url, 'url': url, 'name': title, 'description': description,
         'inLanguage': 'ru', 'about': {'@id': BASE + '/#ekaterina'}, 'breadcrumb': {'@id': url + '#breadcrumbs'}},
        {'@type': 'BreadcrumbList', '@id': url + '#breadcrumbs', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Главная', 'item': BASE + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Правовая информация', 'item': url}]}]}
    template = Template((TOOLS / 'editorial-page.html').read_text())
    page = template.substitute(header=header, title=title, url=url, category='Правовой кабинет',
                               kind='website', heading=heading, description=description, crumbs=crumbs,
                               content=(TOOLS / 'privacy-content.html').read_text(),
                               schema=json.dumps(schema, ensure_ascii=False, indent=2))
    folder = ROOT / route.strip('/')
    folder.mkdir(exist_ok=True)
    (folder / 'index.html').write_text(page)


def main():
    data = json.loads((TOOLS / 'services.json').read_text())
    pages = {p['slug']: p for p in data}
    template = Template((TOOLS / 'service-page.html').read_text())
    home = (ROOT / 'index.html').read_text()
    start = home.index('<header class="site-header">')
    header = home[start:home.index('</header>', start) + len('</header>')]
    header = header.replace('href="#top"', 'href="/"').replace('href="#services"', 'href="/#services"')
    header = header.replace('src="monogram.webp"', 'src="/monogram.webp"')
    articles = json.loads((TOOLS / 'articles.json').read_text())
    for slug, page in pages.items():
        folder = ROOT / 'uslugi' / slug
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'index.html').write_text(render(page, pages, template, header, articles))
    editorial_header = header.replace('href="#', 'href="/#')
    extra = editorial_pages(pages, articles, editorial_header)
    legal_page(editorial_header)
    # Preserve sitemap entries for pages outside the catalogue.
    sitemap = ROOT / 'sitemap.xml'
    ns = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    ElementTree.register_namespace('', ns)
    tree = ElementTree.parse(sitemap)
    existing = {node.text for node in tree.iter(f'{{{ns}}}loc')}
    for route in [*(f'/uslugi/{slug}/' for slug in pages), *extra]:
        url = BASE + route
        if url not in existing:
            entry = ElementTree.SubElement(tree.getroot(), f'{{{ns}}}url')
            ElementTree.SubElement(entry, f'{{{ns}}}loc').text = url
    if len(existing) != len(list(tree.iter(f'{{{ns}}}loc'))):
        ElementTree.indent(tree)
        tree.write(sitemap, encoding='utf-8', xml_declaration=True)


if __name__ == '__main__':
    main()
