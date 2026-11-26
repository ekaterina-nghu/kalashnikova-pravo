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
        {'@type': 'Person', '@id': person, 'name': 'Екатерина Калашникова', 'jobTitle': 'Юрист', 'url': BASE + '/'},
        {'@type': 'WebPage', '@id': url + '#page', 'url': url, 'name': page['title'],
         'description': page['description'], 'inLanguage': 'ru', 'mainEntity': {'@id': url + '#service'},
         'breadcrumb': {'@id': url + '#breadcrumbs'}},
        {'@type': 'BreadcrumbList', '@id': url + '#breadcrumbs', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Главная', 'item': BASE + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': label, 'item': url}]},
        {'@type': 'Service', '@id': url + '#service', 'name': ''.join(page['h1']), 'url': url,
         'description': ' '.join(page['outputs']), 'provider': {'@id': person},
         'areaServed': {'@type': 'Country', 'name': 'Россия'},
         'offers': {'@type': 'Offer', 'name': name, 'url': url + '#pricing',
                    'priceSpecification': {'@type': 'PriceSpecification', 'minPrice': minimum, 'priceCurrency': 'RUB'}}},
    ]
    return json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False, indent=2).replace('<', r'\u003c')


def render(page, pages, template, header):
    url = f"{BASE}/uslugi/{page['slug']}/"
    parts = {key: escape(page[key]) for key in ('label', 'title', 'description', 'intro', 'contact')}
    parts.update({key: items(page[key]) for key in ('outputs', 'situations', 'docs', 'steps')})
    parts['rates'] = '\n'.join(f'<div><dt>{escape(name)}</dt><dd><strong>{price(amount)}</strong>'
                              f'<p>{escape(note)}</p></dd></div>' for name, amount, note in page['rates'])
    parts['faq'] = '\n'.join(f'<details><summary>{escape(q)}</summary><p>{escape(a)}</p></details>'
                            for q, a in page['faq'])
    sources = ' · '.join(f'<a href="{escape(link)}">{escape(label)}</a>' for label, link in page['sources'])
    parts['sources'] = f'<p class="note">Правовая основа для гражданского процесса. {sources}.</p>' if sources else ''
    parts['related'] = '\n'.join(f'<a href="/uslugi/{slug}/">{escape(pages[slug]["label"])} '
                                 '<span aria-hidden="true">→</span></a>' for slug in page['related'])
    lead, emphasis = page['h1']
    return template.substitute(parts, header=header, buttons=buttons(), short_buttons=buttons(True),
                               schema=structured_data(page, url), url=url, starting=price(page['rates'][0][1]),
                               h1=escape(lead) + '<em>' + escape(emphasis) + '</em>')


def main():
    data = json.loads((TOOLS / 'services.json').read_text())
    pages = {p['slug']: p for p in data}
    template = Template((TOOLS / 'service-page.html').read_text())
    home = (ROOT / 'index.html').read_text()
    start = home.index('<header class="site-header">')
    header = home[start:home.index('</header>', start) + len('</header>')]
    header = header.replace('href="#top"', 'href="/"').replace('href="#services"', 'href="/#services"')
    header = header.replace('src="monogram.webp"', 'src="/monogram.webp"')
    for slug, page in pages.items():
        folder = ROOT / 'uslugi' / slug
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'index.html').write_text(render(page, pages, template, header))
    # Preserve sitemap entries for pages outside the service catalogue.
    sitemap = ROOT / 'sitemap.xml'
    ns = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    ElementTree.register_namespace('', ns)
    tree = ElementTree.parse(sitemap)
    existing = {node.text for node in tree.iter(f'{{{ns}}}loc')}
    for slug in pages:
        url = f'{BASE}/uslugi/{slug}/'
        if url not in existing:
            entry = ElementTree.SubElement(tree.getroot(), f'{{{ns}}}url')
            ElementTree.SubElement(entry, f'{{{ns}}}loc').text = url
    if len(existing) != len(list(tree.iter(f'{{{ns}}}loc'))):
        ElementTree.indent(tree)
        tree.write(sitemap, encoding='utf-8', xml_declaration=True)


if __name__ == '__main__':
    main()
