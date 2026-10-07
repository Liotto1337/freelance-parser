"""Сборщик: обходит категории всех площадок и сохраняет заказы в базу.

    python collector.py            # один проход
    python collector.py --loop     # бесконечно, раз в POLL_INTERVAL_SEC
    python collector.py --pages 3  # глубже по страницам (для первого запуска)
"""
import argparse
import json
import logging
import random
import time

import config
import db
import sources
from sources import utcnow

log = logging.getLogger("collector")


def run_once(pages: int) -> int:
    started = utcnow().isoformat()
    new_total, errors = 0, []
    for label, fn, args in sources.all_jobs():
        for page in range(1, pages + 1):
            try:
                orders = fn(*args, page=page)
            except Exception as e:  # сеть, вёрстка, блокировка: пишем и идём дальше
                log.warning("%s p%d: %s", label, page, e)
                errors.append(f"{label} p{page}: {e}")
                break
            finally:
                time.sleep(config.REQUEST_DELAY_SEC + random.uniform(0, 1.5))
            with db.connect() as conn:
                new = sum(db.upsert(conn, o) for o in orders)
            new_total += new
            log.info("%s p%d: %d заказов, новых %d", label, page, len(orders), new)
            if not orders:
                break
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO runs (started_at, finished_at, new_orders, errors) VALUES (?,?,?,?)",
            (started, utcnow().isoformat(), new_total,
             json.dumps(errors, ensure_ascii=False)))
    log.info("Проход завершён: новых заказов %d, ошибок %d", new_total, len(errors))
    return new_total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true", help="собирать бесконечно")
    ap.add_argument("--pages", type=int, default=config.PAGES_PER_CATEGORY)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    db.init()
    while True:
        run_once(args.pages)
        if not args.loop:
            break
        time.sleep(config.POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
