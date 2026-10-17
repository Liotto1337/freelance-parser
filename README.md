# Парсер заказов: Kwork, FL.ru, freelance.ru

Собирает новые заказы из выбранных категорий трёх бирж и показывает их в веб-дашборде.
В дашборде можно фильтровать заказы по навыкам, бюджету и дате, скрывать заказы, где покупатель уже выбрал исполнителя,
сортировать по дате, числу откликов и бюджету, отмечать статус и копировать отклик, собранный под конкретный заказ.

Парсер читает только публичные страницы бирж. Входить в аккаунт ему не нужно, и откликов он не отправляет.

## Состав

| Файл | Что делает |
|---|---|
| `config.py` | Категории бирж, навыки и ключевые слова, интервалы, шаблоны откликов |
| `sources.py` | Разбор страниц Kwork, FL.ru, freelance.ru |
| `db.py` | База SQLite (`orders.db`) и определение навыков по тексту заказа |
| `collector.py` | Сборщик: обходит все категории, раз в 10 минут с `--loop` |
| `app.py`, `templates/` | Дашборд |
| `deploy/` | systemd-сервисы для сервера |

## Запуск локально

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python collector.py --pages 3   # первый сбор, по 3 страницы на категорию
.venv/bin/python app.py                   # http://127.0.0.1:8080
```

## Запуск на сервере (Ubuntu/Debian)

```bash
sudo useradd -r -s /usr/sbin/nologin freelance
sudo cp -r freelance-parser /opt/freelance-parser
cd /opt/freelance-parser
sudo python3 -m venv .venv && sudo .venv/bin/pip install -r requirements.txt
sudo cp .env.example .env && sudo nano .env      # обязательно задайте DASHBOARD_PASSWORD
sudo chown -R freelance: /opt/freelance-parser
sudo cp deploy/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now freelance-collector freelance-dashboard
```

Дашборд откроется на `http://<ip-сервера>:8080` с логином и паролем из `.env`.
Без пароля дашборд не запустится на внешнем адресе.
Пароль по HTTP передаётся открытым текстом, поэтому для постоянной работы лучше поставить перед дашбордом nginx или Caddy с HTTPS.

Логи сборщика: `journalctl -u freelance-collector -f`.

## Настройка

- **Категории.** Списки `KWORK_CATEGORIES`, `FL_CATEGORIES`, `FREELANCERU_CATEGORIES` в `config.py`.
  Узкая категория (например, FL.ru «Python») сразу даёт заказу навык.
  У широкой (`None`) навыки определяются только по ключевым словам.
- **Ключевые слова.** Словарь `SKILLS` в `config.py`, регулярные выражения без учёта регистра.
- **Частота.** Переменные окружения `POLL_INTERVAL_SEC` (по умолчанию 600) и `REQUEST_DELAY_SEC` (3 с между запросами).
- **Отклик.** Кнопка «Скопировать отклик» собирает текст по `REPLY_TEMPLATE` из `config.py`.
  В шаблон подставляются `{title}` (название заказа), `{budget}`, `{site}` и `{experience}`.
  `{experience}` — абзац про опыт из `REPLY_EXPERIENCE` по навыку заказа: сначала навык узкой категории,
  иначе первый найденный по ключевым словам. Если навыка нет, берётся `REPLY_EXPERIENCE_DEFAULT`.
  Шаблон можно переопределить переменной `REPLY_TEMPLATE` в `.env`, переносы строк там пишутся как `\n`.

## Если что-то сломалось

Биржи иногда меняют вёрстку. Тогда в дашборде под «Обновлено…» появится «Ошибок при сборе: N».
Текст ошибок виден при наведении и в `journalctl`. Чинить нужно соответствующую функцию `fetch_*` в `sources.py`.
