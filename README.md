# ascii-earth

> THAT'S NO EARTH! — IT'S A SPACE STATION.

Рисует Землю ASCII-постером прямо в терминале. Реальная текстура NASA Blue
Marble back-проецируется на сферу (ортографическая проекция), сэмплируется по
каждой ячейке терминала, маппится в density-ramp и перекрашивается в
сине-белую палитру: синий океан, светлая суша, звёзды на фоне, тонкая
обводка-окружность и подписи сверху/снизу.

## Запуск

```sh
make install      # venv + pillow/numpy
make run          # напечатать постер один раз
make spin         # вращающийся глобус (Ctrl-C — стоп)
```

Текстура (~240 КБ, public domain) скачивается один раз в
`~/.cache/ascii-earth/` при первом запуске. Прекэш без рендера — `make assets`.

## Опции

```sh
python3.12 globe.py [опции]
```

| Опция | По умолчанию | Что делает |
|---|---|---|
| `--size N` | `72` | диаметр диска в столбцах |
| `--lon DEG` | `-30` | центральная долгота — поворачивает глобус |
| `--lat DEG` | `18` | наклон оси / широта обзора |
| `--color {256,truecolor,none}` | `256` | цветовой режим (`256` безопасен под tmux/mosh) |
| `--ramp STR` | density-ramp | символы тёмное→светлое |
| `--stars F` | `0.03` | плотность звёзд `0..1` |
| `--no-stars` / `--no-ring` / `--no-labels` | — | убрать элементы |
| `--top STR` / `--bottom STR` | пасхалка | свои подписи |
| `--spin` | — | анимация вращения |
| `--fps F` / `--step DEG` | `12` / `4` | скорость и шаг вращения |

Примеры:

```sh
python3.12 globe.py --lon 100 --lat 0           # вид на Азию, без наклона
python3.12 globe.py --color truecolor --size 90 # крупнее и truecolor
python3.12 globe.py --top "" --bottom "" --no-ring
python3.12 globe.py --spin --step 6 --fps 15
```

## Требования

`python3.12`, `pillow`, `numpy`. Терминал с поддержкой 256 цветов (или
truecolor). Под `screen`/`tmux`/`mosh` оставляй `--color 256`.
