from leadscraper.extract.htmlutil import decode_cloudflare_email, extract_lines, extract_links, extract_text

HTML = """<!doctype html><html><head><title>T</title><style>.x{}</style><script>var a=1;</script></head>
<body><nav><a href="/impressum">Impressum</a><a href="/team/">Unser <b>Team</b></a></nav>
<div class="card"><h3>Thomas Berger</h3><p>Geschäftsführer<br>Mobil: <b>0171 5550123</b></p>
<a href="tel:+491715550123">anrufen</a> <a href="mailto:t.berger@rheinblick-immobilien.de">Mail</a>
<a href="https://wa.me/491715550123?text=Hallo">WhatsApp</a>
<a href="/vcard/berger.vcf" download>vCard</a></div>
<table><tr><td>Tel.</td><td>0221 5550000</td></tr></table>
<footer>&copy; 2026 &amp; <a href="https://www.linkedin.com/company/rheinblick">LinkedIn</a>
<a href="https://immobilienscout24.de/x">Portal</a> <a href="#top">nach oben</a>
<a class="__cf_email__" href="/cdn-cgi/l/email-protection"
 data-cfemail="8fe6e1e9e0cffde7eae6e1ede3e6ece4a1ebea">[email&#160;protected]</a>
</footer></body></html>"""


def test_extract_text_block_newlines_and_inline_kept():
    text = extract_text(HTML)
    assert "Thomas Berger\nGeschäftsführer\nMobil: 0171 5550123" in text
    assert "var a=1" not in text and ".x{}" not in text
    assert "Unser Team" in text  # inline <b> bleibt in der Zeile
    assert "Tel. · 0221 5550000" in text  # Tabellenzellen getrennt
    assert "© 2026 &" in text


def test_extract_lines():
    lines = extract_lines(HTML)
    assert lines[0] == "Impressum Unser Team"  # Nav-Links auf einer Zeile
    assert "Mobil: 0171 5550123" in lines
    assert all(line.strip() for line in lines)


def test_extract_links_kinds_and_resolution():
    links = {
        (lk.kind, lk.href) for lk in extract_links(HTML, "https://www.rheinblick-immobilien.de/kontakt/")
    }
    assert ("internal", "https://www.rheinblick-immobilien.de/impressum") in links
    assert ("internal", "https://www.rheinblick-immobilien.de/team/") in links
    assert ("tel", "tel:+491715550123") in links
    assert ("mailto", "mailto:t.berger@rheinblick-immobilien.de") in links
    assert ("whatsapp", "https://wa.me/491715550123?text=Hallo") in links
    assert ("vcard", "https://www.rheinblick-immobilien.de/vcard/berger.vcf") in links
    assert ("social", "https://www.linkedin.com/company/rheinblick") in links
    assert ("external", "https://immobilienscout24.de/x") in links
    assert ("other", "#top") in links
    assert ("mailto", "mailto:info@rheinblick.de") in links  # Cloudflare dekodiert


def test_link_text_and_attrs():
    link = next(lk for lk in extract_links(HTML, "https://rheinblick-immobilien.de") if lk.kind == "vcard")
    assert link.text == "vCard"
    assert "download" in link.attrs
    team = next(
        lk for lk in extract_links(HTML, "https://rheinblick-immobilien.de") if lk.href.endswith("/team/")
    )
    assert team.text == "Unser Team"


def test_decode_cloudflare_email():
    assert decode_cloudflare_email("8fe6e1e9e0cffde7eae6e1ede3e6ece4a1ebea") == "info@rheinblick.de"
    assert decode_cloudflare_email("zz") is None
    assert decode_cloudflare_email("8f") is None


def test_empty_and_broken_html():
    assert extract_text("") == ""
    assert extract_lines("<div><p>a<p>b") == ["a", "b"]
    assert extract_links("<a>kein href</a>", "https://x.de") == []


def test_image_alt_texts():
    from leadscraper.extract.htmlutil import image_alt_texts

    html = """<html><body>
      <img src="a.jpg" alt="Anna Schmidt">
      <img src="b.jpg" alt="  Max   Weber, Immobilienkaufmann ">
      <img src="c.jpg" title="Tim Brandt">
      <img src="logo.svg" alt="">
      <div data-name="Lena Fischer"></div>
    </body></html>"""
    assert image_alt_texts(html) == [
        "Anna Schmidt",
        "Max Weber, Immobilienkaufmann",
        "Tim Brandt",
        "Lena Fischer",
    ]
