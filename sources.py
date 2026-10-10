"""Сборщики заказов с Kwork, FL.ru и freelance.ru.

Каждая функция fetch_* возвращает список Order для одной страницы категории.
Читаем только публичные страницы, без авторизации.
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

import config


@dataclass
class Order:
    site: str            # kwork | fl | freelanceru
    ext_id: str          # id заказа на площадке
    url: str
    title: str
    description: str = ""
    budget_text: str = ""
    budget: int | None = None
    category: str = ""
    category_skill: str | None = None
    tags: list[str] = field(default_factory=list)
    published_at: str | None = None   # ISO, если площадка отдаёт точное время
    published_text: str = ""          # «20 минут назад» и т.п.
    responses: int | None = None
    views: int | None = None


session = requests.Session()
session.headers.update({
    "User-Agent": config.USER_AGENT,
    "Accept-Language": "ru-RU,ru;q=0.9",
})


def _get(url: str, params=None) -> str:
    r = session.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.text


def _to_int(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", str(text).split(".")[0])
    return int(digits) if digits else None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# Все площадки показывают время по Москве. В базе храним UTC без tzinfo.
MSK = timezone(timedelta(hours=3))


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _msk_to_utc_iso(dt: datetime) -> str:
    return dt.replace(tzinfo=MSK).astimezone(timezone.utc).replace(tzinfo=None).isoformat()


# ---------------------------------------------------------------- Kwork

def fetch_kwork(cat_id: int, cat_name: str, skill: str | None, page: int = 1) -> list[Order]:
    html = _get("https://kwork.ru/projects", params={"c": cat_id, "page": page})
    key = '"wants":'
    i = html.find(key)
    if i < 0:
        raise ValueError("Kwork: не найден блок wants (изменилась вёрстка?)")
    wants, _ = json.JSONDecoder().raw_decode(html[i + len(key):])
    orders = []
    for w in wants:
        price = w.get("priceLimit")
        possible = w.get("possiblePriceLimit")
        budget = _to_int(price)
        budget_text = f"до {budget:,} ₽".replace(",", " ") if budget else ""
        if possible and _to_int(possible) and _to_int(possible) != budget:
            budget_text += f" (допустимо до {_to_int(possible):,} ₽)".replace(",", " ")
        orders.append(Order(
            site="kwork",
            ext_id=str(w["id"]),
            url=f"https://kwork.ru/projects/{w['id']}",
            title=_clean(w.get("name", "")),
            description=(w.get("description") or "").strip(),
            budget_text=budget_text,
            budget=budget,
            category=cat_name,
            category_skill=skill,
            published_at=_kwork_date(w.get("date_create")),
            published_text=(w.get("wantDates") or {}).get("dateCreate", ""),
            responses=_to_int(w.get("kwork_count")),
            views=_to_int(w.get("views_dirty")),
        ))
    return orders


def _kwork_date(s: str | None) -> str | None:
    try:
        return _msk_to_utc_iso(datetime.strptime(s, "%Y-%m-%d %H:%M:%S"))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- FL.ru

def fetch_fl(slug: str, cat_name: str, skill: str | None, page: int = 1) -> list[Order]:
    url = f"https://www.fl.ru/projects/category/{slug}/"
    if page > 1:
        url += f"page-{page}/"
    soup = BeautifulSoup(_get(url), "lxml")
    orders = []
    for card in soup.select('div[id^="project-item"]'):
        ext_id = card["id"].removeprefix("project-item")
        link = card.select_one("h2 a[href]")
        if not ext_id.isdigit() or not link:
            continue
        # У закрытого заказа здесь «Исполнитель определён» или «Победитель определён»
        status = card.select_one('[data-id="qa-order-status"]')
        if status and _clean(status.get_text()):
            continue
        price = card.select_one(".b-post__price")
        desc = card.select_one(".b-post__txt.text-5") or card.select_one(".b-post__body")
        foot = card.select_one(".b-post__foot .b-post__txt")
        kind, when = "", ""
        if foot:
            spans = foot.find_all("span", recursive=False)
            if spans:
                kind = _clean(spans[0].get_text())
            if len(spans) > 1:
                when = _clean(spans[1].get_text())
        responses = None
        foot_text = _clean(card.select_one(".b-post__foot").get_text(" ")) if card.select_one(".b-post__foot") else ""
        m = re.search(r"(\d+)\s+ответ", foot_text)
        if m:
            responses = int(m.group(1))
        elif "нет ответов" in foot_text.lower():
            responses = 0
        views_el = card.select_one('[title="Количество просмотров"]')
        budget_text = _clean(price.get_text()) if price else ""
        orders.append(Order(
            site="fl",
            ext_id=ext_id,
            url="https://www.fl.ru" + link["href"],
            title=_clean(link.get_text()),
            description=desc.get_text("\n", strip=True) if desc else "",
            budget_text=budget_text,
            budget=_to_int(budget_text) if "₽" in budget_text else None,
            category=cat_name,
            category_skill=skill,
            tags=[kind] if kind else [],
            published_at=_fl_date(when),
            published_text=when,
            responses=responses,
            views=_to_int(views_el.get_text()) if views_el else None,
        ))
    return orders


_MONTHS = {m: i for i, m in enumerate(
    ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
     "августа", "сентября", "октября", "ноября", "декабря"], 1)}


def _fl_date(text: str) -> str | None:
    """«4 октября, 10:45» или «20 часов 24 минуты назад» -> ISO."""
    now = datetime.now(MSK).replace(tzinfo=None)
    m = re.match(r"(\d{1,2})\s+([а-я]+)(?:\s+(\d{4}))?,\s*(\d{1,2}):(\d{2})", text)
    if m and m.group(2) in _MONTHS:
        year = int(m.group(3)) if m.group(3) else now.year
        dt = datetime(year, _MONTHS[m.group(2)], int(m.group(1)), int(m.group(4)), int(m.group(5)))
        if dt > now + timedelta(days=1):  # «декабря» в январе — прошлый год
            dt = dt.replace(year=year - 1)
        return _msk_to_utc_iso(dt)
    if "назад" in text:
        delta = timedelta()
        for num, unit in re.findall(r"(\d+)\s+(дн|день|час|минут|секунд)", text):
            n = int(num)
            delta += {"дн": timedelta(days=n), "день": timedelta(days=n),
                      "час": timedelta(hours=n), "минут": timedelta(minutes=n),
                      "секунд": timedelta(seconds=n)}[unit]
        return (utcnow() - delta).replace(second=0).isoformat()
    return None


# ---------------------------------------------------------------- freelance.ru

def fetch_freelanceru(cat_id: int, cat_name: str, skill: str | None, page: int = 1) -> list[Order]:
    soup = BeautifulSoup(
        _get("https://freelance.ru/task", params={"c[]": cat_id, "page": page}), "lxml")
    orders = []
    for card in soup.select("article.task-card"):
        link = card.select_one("a.task-card__title-link[href]")
        if not link:
            continue
        m = re.search(r"/task/view/(\d+)", link["href"])
        if not m:
            continue
        chips = [_clean(c.get_text()) for c in card.select(".task-chip")]
        cat_chip = card.select_one(".task-chip--cat")
        foot = card.select(".task-card__foot-item")
        published_at, published_text = None, ""
        if foot:
            published_text = _clean(foot[0].get_text())
            try:
                published_at = _msk_to_utc_iso(
                    datetime.strptime(foot[0].get("title", ""), "%d.%m.%Y %H:%M"))
            except ValueError:
                pass
        budget_el = card.select_one(".task-card__budget")
        budget_text = _clean(budget_el.get_text(" ")) if budget_el else ""
        desc = card.select_one(".task-card__desc")
        orders.append(Order(
            site="freelanceru",
            ext_id=m.group(1),
            url="https://freelance.ru" + link["href"],
            title=_clean(link.get("title") or link.get_text()),
            description=desc.get_text("\n", strip=True) if desc else "",
            budget_text=budget_text,
            budget=_to_int(budget_text) if "₽" in budget_text else None,
            category=_clean(cat_chip.get_text()) if cat_chip else cat_name,
            category_skill=skill,
            tags=[c for c in chips if not cat_chip or c != _clean(cat_chip.get_text())],
            published_at=published_at,
            published_text=published_text,
            responses=_to_int(foot[2].get_text()) if len(foot) > 2 else None,
            views=_to_int(foot[3].get_text()) if len(foot) > 3 else None,
        ))
    return orders


def all_jobs():
    """Список (метка, функция, аргументы) по всем категориям из config."""
    jobs = []
    for cid, name, skill in config.KWORK_CATEGORIES:
        jobs.append((f"kwork:{name}", fetch_kwork, (cid, name, skill)))
    for slug, name, skill in config.FL_CATEGORIES:
        jobs.append((f"fl:{name}", fetch_fl, (slug, name, skill)))
    for cid, name, skill in config.FREELANCERU_CATEGORIES:
        jobs.append((f"freelanceru:{name}", fetch_freelanceru, (cid, name, skill)))
    return jobs
