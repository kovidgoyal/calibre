from html import escape

from calibre.library.comments import sanitize_comments_html
from calibre.utils.date import dt_as_local, is_date_undefined, strftime


def safe_date(dt, fmt='%d %b %Y'):
    if not dt or is_date_undefined(dt):
        return ''
    return strftime(fmt, t=dt_as_local(dt).timetuple())


def render_legacy_book_details(ctx, mi, library_id):
    book_id = mi.id

    title = escape(mi.title or 'Unknown')

    series = ''
    if mi.series:
        series = f'{escape(mi.series)}' + (f' [{mi.series_index}]' if mi.series_index is not None else '')

    tags = mi.tags or []
    tags_html = ', '.join(f'<a href="/mobile?library_id={library_id}&search=tags:%22%3D{escape(tag)}%22">{escape(tag)}</a>' for tag in tags)

    comments = mi.comments or ''

    # Formats
    formats_html = ''
    if mi.formats:
        links = []
        for fmt in mi.formats:
            if not fmt or fmt.lower().startswith('original_'):
                continue

            url = ctx.url_for(
                '/legacy/get',
                what=fmt,
                book_id=book_id,
                library_id=library_id
            )
            fmt = escape(fmt)
            links.append(f'<a href="{url}" class="download-button" download="{title}.{fmt.lower()}">Download {fmt}</a>')

        formats_html = ' '.join(links)

    cover_url = ctx.url_for(
        '/get',
        what='cover',
        book_id=book_id,
        library_id=library_id
    )

    # Build metadata table
    metadata_rows = []

    # Authors
    if mi.authors:
        author_links = []
        for author in mi.authors:
            search_url = f'/mobile?library_id={library_id}&search=authors:%22%3D{escape(author)}%22'
            author_links.append(f'<a href="{search_url}">{escape(author)}</a>')
        metadata_rows.append(f'<tr><td>Authors</td><td>{" ".join(author_links)}</td></tr>')

    # Series
    if series:
        series_name = escape(mi.series)
        search_url = f'/mobile?library_id={library_id}&search=series:%22%3D{series_name}%22'
        metadata_rows.append(f'<tr><td>Series</td><td><a href="{search_url}">{series}</a></td></tr>')

    # Tags
    if tags:
        metadata_rows.append(f'<tr><td>Tags</td><td>{tags_html}</td></tr>')

    if mi.publisher:
        metadata_rows.append(f'<tr><td>Publisher</td><td>{escape(mi.publisher)}</td></tr>')

    if mi.pubdate:
        date_str = safe_date(mi.pubdate)
        search_url = f'/mobile?library_id={library_id}&search=pubdate:%22%3D{mi.pubdate.isoformat()}%22'
        metadata_rows.append(f'<tr><td>Published</td><td><a href="{search_url}">{date_str}</a></td></tr>')

    if mi.timestamp:
        date_str = safe_date(mi.timestamp)
        search_url = f'/mobile?library_id={library_id}&search=timestamp:%22%3D{mi.timestamp.isoformat()}%22'
        metadata_rows.append(f'<tr><td>Date</td><td><a href="{search_url}">{date_str}</a></td></tr>')

    if mi.rating and mi.rating > 0:
        stars = '★' * round(mi.rating)
        search_url = f'/mobile?library_id={library_id}&search=rating:%22%3D{int(mi.rating)}%22'
        metadata_rows.append(f'<tr><td>Rating</td><td><a href="{search_url}">{stars}</a></td></tr>')

    if mi.languages:
        lang_links = []
        for lang in mi.languages:
            search_url = f'/mobile?library_id={library_id}&search=languages:%22%3D{lang}%22'
            lang_links.append(f'<a href="{search_url}">{lang}</a>')
        metadata_rows.append(f'<tr><td>Languages</td><td>{", ".join(lang_links)}</td></tr>')

    # Identifiers
    if mi.identifiers:
        id_links = []
        for key, value in mi.identifiers.items():
            if key.lower() in ('amazon', 'mobi-asin'):
                url = f'https://www.amazon.com/dp/{value}'
                display = 'Amazon.com'
            elif key.lower() == 'goodreads':
                url = f'https://www.goodreads.com/book/show/{value}'
                display = 'Goodreads'
            else:
                url = f'#{key}:{value}'  # fallback
                display = f'{key}: {value}'
            id_links.append(f'<a href="{url}" target="_blank">{display}</a>')
        metadata_rows.append(f'<tr><td>Identifiers</td><td>{", ".join(id_links)}</td></tr>')

    if mi.formats:
        fmt_links = []
        for fmt in mi.formats:
            if not fmt or fmt.lower().startswith('original_'):
                continue
            fmt_links.append(f'<a href="javascript:void(0)" data-format="{fmt}" data-book-id="{book_id}">{fmt}</a>')
        metadata_rows.append(f'<tr><td>Formats</td><td>{", ".join(fmt_links)}</td></tr>')

    metadata_table = '<table class="metadata">' + ''.join(metadata_rows) + '</table>' if metadata_rows else ''

    return f'''
    <html>
    <head>
        <title>{title}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: sans-serif; margin: 0; padding: 0; background-color: #f6f3e9; color: var(--calibre-color-window-foreground); }}
            .top-bar {{
                    position: fixed; top: 0; left: 0; width: 100%; background: #39322b;
                    color: #f6f3e9; padding: 0.5em; display: flex; justify-content: space-between;
                    align-items: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); z-index: 1; }}
            .top-bar a {{ text-decoration: none; color: #f6f3e9; }}
            .top-bar .title {{ font-weight: bold; flex-grow: 1; margin-left: 0.5em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
            .content {{ margin-top: 4em; padding: 1em; }}
            .book-details {{ display: flex; flex-wrap: wrap; align-items: flex-start; }}
            .cover {{ margin-right: 1em; margin-bottom: 1em; max-width: 200px; flex-shrink: 0; }}
            .cover img {{ max-width: 100%; height: auto; border-radius: 10px; }}
            .info {{ flex-grow: 1; min-width: 200px; }}
            .metadata {{ width: 100%; border-collapse: collapse; margin-top: 1em; }}
            .metadata td {{ padding: 0.5em; border-bottom: 1px solid #ddd; vertical-align: top; }}
            .metadata td:first-child {{ font-weight: bold; width: 30%; }}
            .metadata a {{ color: var(--calibre-color-link); text-decoration: none; }}
            .metadata a:hover {{ text-decoration: underline; }}
            .formats {{ margin-top: 1em; }}
            .download-button {{
                display: inline-block; padding: 0.5em 1em; background: #39322b;
                color: #f6f3e9; text-decoration: none; border-radius: 4px; margin-right: 0.5em;
            }}
            .download-button:hover {{ background: #2a2520; }}
            .description {{ margin-top: 2em; word-wrap: break-word; }}
            @media (max-width: 600px) {{
                .top-bar {{ font-size: 0.9em; padding: 0.4em; }}
                .content {{ margin-top: 3.5em; padding: 0.5em; }}
                .cover {{ max-width: 120px; margin-right: 0.5em; }}
                .info {{ min-width: 150px; }}
                .metadata td {{ padding: 0.3em; font-size: 0.9em; }}
                .metadata td:first-child {{ width: 35%; }}
                .download-button {{ padding: 0.4em 0.8em; font-size: 0.9em; }}
            }}
        </style>
    </head>
    <body>
        <div class="top-bar">
            <a href="javascript:history.back()" title="Back">&larr; Back</a>
            <span class="title">{title}</span>
        </div>
        <div class="content">
            <div class="book-details">
                <div class="cover">
                    <img src="{cover_url}" alt="{title}" />
                </div>
                <div class="info">
                    <h1>{title}</h1>
                    <div class="formats">{formats_html}</div>
                    {metadata_table}
                </div>
            </div>
            {f'<div class="description"><h2>Description</h2>{sanitize_comments_html(comments)}</div>' if comments else ''}
        </div>
    </body>
    </html>
    '''
