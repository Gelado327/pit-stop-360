#!/usr/bin/env python3
"""Atualiza noticias.json com manchetes encontradas nas páginas oficiais de F1 e F2."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "noticias.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PitStop360NewsBot/1.0)"}
TIMEOUT = 25


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def get_soup(url):
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def f1_items():
    # Feed oficial da Formula1.com.
    url = "https://www.formula1.com/en/latest/all.xml"
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "xml")
    items = []
    for item in soup.find_all("item"):
        title = clean(item.find("title").get_text(" ", strip=True) if item.find("title") else "")
        link = clean(item.find("link").get_text(" ", strip=True) if item.find("link") else "")
        desc_tag = item.find("description")
        desc = clean(BeautifulSoup(desc_tag.get_text(" ", strip=True), "html.parser").get_text(" ", strip=True)) if desc_tag else ""
        date_tag = item.find("pubDate")
        date = clean(date_tag.get_text(" ", strip=True) if date_tag else "")
        if title and link.startswith("http"):
            items.append({"categoria": "F1", "fonte": "Formula1.com", "titulo": title,
                          "resumo": desc[:350], "data": date, "link": link})
        if len(items) >= 12:
            break
    if not items:
        raise RuntimeError("O feed oficial da F1 não retornou manchetes reconhecíveis.")
    return items


def f2_items():
    # Página oficial de notícias da FIA Formula 2. Seletores podem mudar com o site.
    base = "https://www.fiaformula2.com/"
    url = urljoin(base, "en/latest")
    soup = get_soup(url)
    items = []
    seen = set()
    for a in soup.select('a[href*="/en/latest/article/"]'):
        title = clean(a.get_text(" ", strip=True))
        href = a.get("href", "")
        if len(title) < 12 or not href:
            continue
        link = urljoin(base, href)
        if link in seen:
            continue
        seen.add(link)
        card = a
        for _ in range(3):
            if card.parent:
                card = card.parent
        desc = clean(card.get_text(" ", strip=True))
        if desc.startswith(title):
            desc = desc[len(title):].strip()
        desc = desc[:350]
        items.append({"categoria": "F2", "fonte": "FIA Formula 2", "titulo": title,
                      "resumo": desc, "data": "", "link": link})
        if len(items) >= 12:
            break
    if not items:
        raise RuntimeError("A página oficial da F2 não retornou manchetes reconhecíveis; o site pode ter mudado.")
    return items


def load_existing():
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return data.get("noticias", [])
    except (OSError, json.JSONDecodeError):
        return []


def main():
    previous = load_existing()
    fresh = []
    errors = []
    for label, func in (("F1", f1_items), ("F2", f2_items)):
        try:
            fresh.extend(func())
        except Exception as exc:
            errors.append(f"{label}: {exc}")
            # Preserve previous items for a category if its source temporarily fails.
            fresh.extend(item for item in previous if item.get("categoria") == label)
    if not fresh:
        raise RuntimeError("Nenhuma notícia disponível; arquivo anterior preservado.")

    unique = []
    seen = set()
    for item in fresh:
        link = item.get("link", "")
        if link and link not in seen:
            seen.add(link)
            unique.append(item)
    payload = {"atualizadoEm": datetime.now(timezone.utc).isoformat(timespec="seconds"), "noticias": unique}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Salvas {len(unique)} notícias em {OUT.name}.")
    if errors:
        print("Avisos: " + " | ".join(errors))


if __name__ == "__main__":
    main()
