# brightness-scheduler

Automatická úprava jasu dvou externích monitorů podle polohy Slunce v Praze —
ne podle pevných hodin, ale podle skutečného sunrise/noon/sunset, které se
každý den přepočítají knihovnou [`astral`](https://astral.readthedocs.io/).

Skládá se ze tří částí: periodického systemd timeru, CLI nástroje a
Plasma widgetu se slidery pro ruční doladění.

## Jak funguje interpolace jasu

Nejde o "aktivní kotvu pro danou chvíli" — jas se vždy **lineárně
interpoluje mezi dvěma sousedními časovými body**. Žádná kotva neplatí sama
o sobě, je to jen bod na časové ose.

Pro každý monitor existují 4 kotvy (hodnota jasu v %):

| Kotva     | Čas                                             |
|-----------|--------------------------------------------------|
| `night`   | půlnoc (00:00)                                    |
| `sunrise` | reálný východ slunce v Praze (mění se den ode dne) |
| `noon`    | reálné sluneční poledne                           |
| `sunset`  | reálný západ slunce                               |

Aby "teď" vždy spadalo mezi dva body i těsně po/před půlnocí, se body
generují pro včerejšek, dnešek a zítřek zároveň — vznikne řetězec
`noc → východ → poledne → západ → noc(dalšího dne) → …` táhnoucí se přes tři
dny. Aktuální jas se pak spočítá takto:

```
najdi dva sousední body (t0, v0) a (t1, v1), mezi které teď spadá
frac = (teď − t0) / (t1 − t0)
jas  = v0 + (v1 − v0) × frac
```

Příklad: dnes východ slunce v 4:50 (kotva `sunrise` = 55 %), poledne ve
12:02 (kotva `noon` = 100 %). V 8:26 (přesně v polovině intervalu) by jas
byl `55 + (100 − 55) × 0.5 = 77,5 %`.

Žádné skoky, žádný úsek dne "nepatří" jedné kotvě celý — jas se mezi kotvami
plynule mění.

## Architektura

Tři komponenty sdílející `~/.config/brightness-scheduler/config.json`
(mimo git — obsahuje jen osobní vyladěné hodnoty; šablona je v
[`config/config.json`](config/config.json)):

- [`scheduler/schedcore.py`](scheduler/schedcore.py) — sdílené jádro:
  config I/O, výpočet sunrise/noon/sunset, lineární interpolace mezi
  kotvami, volání D-Bus `SetBrightness`.
- [`scheduler/brightness-scheduler.py`](scheduler/brightness-scheduler.py) —
  periodický apply, spouští ho systemd timer. Cachuje poslední nastavenou
  hodnotu a nezapisuje, pokud je rozdíl < 1 % (šetří zbytečné DDC volání).
- [`scheduler/schedctl.py`](scheduler/schedctl.py) — CLI pro widget:
  `get-status` / `set-anchor` / `set-enabled` / `preview`. Volané z QML
  přes shell, protože čisté QML nemá file I/O ani D-Bus bindings.
- [`plasmoid/org.vencator.brightnessscheduler/`](plasmoid/org.vencator.brightnessscheduler/) —
  Plasma widget se slidery (night/sunrise/noon/sunset) pro oba monitory
  zvlášť + master on/off switch.

### Živý náhled při tažení slideru

Tažením slideru ve widgetu se přes `schedctl preview` okamžitě nastaví
reálný jas monitoru — je to jen dočasný náhled, nic se nezapisuje. Teprve
puštěním slideru se přes `schedctl set-anchor` nová hodnota kotvy trvale
uloží do configu. Hned poté se reálný jas monitoru "srovná" zpátky na
hodnotu, kterou by měl mít právě teď podle (aktualizovaného) rozvrhu —
takže náhled nezůstane viset, dokud nedoběhne příští tick systemd timeru.

## Hardware

- **LG 34GL750** — `DP-1`, DDC bus `/dev/i2c-0`, D-Bus `display0`. DDC/CI
  spolehlivé.
- **Acer V243W** (2008) — `DP-2`, DDC bus `/dev/i2c-1`, D-Bus `display1`.
  Připojený přes DP→DVI redukci, syrové `ddcutil` volání EIO chybují, ale
  funguje to přes `powerdevil` (má vlastní retry s backoffem). Proto celý
  projekt jde přes Plasma D-Bus rozhraní, ne přímo přes `ddcutil` CLI.

## D-Bus rozhraní (Plasma 6, stejné jako systémový slider jasu)

```
service:   org.kde.org_kde_powerdevil
paths:     /org/kde/ScreenBrightness/display0  (LG)
           /org/kde/ScreenBrightness/display1  (Acer)
interface: org.kde.ScreenBrightness.Display
method:    SetBrightness(int32 value, uint32 flags)   # value 0–10000 = 0–100 %
```

## Nasazení

Symlinky, ne kopie — úpravy v repu se projeví okamžitě:

```bash
~/.config/systemd/user/brightness-scheduler.{service,timer}
    -> scheduler/../systemd/brightness-scheduler.{service,timer}
~/.local/share/plasma/plasmoids/org.vencator.brightnessscheduler
    -> plasmoid/org.vencator.brightnessscheduler
```

Po úpravě QML: `kbuildsycoca6` (přebuild cache) + restart plasmoidu/plasmashellu.

## Verifikace / testovací příkazy

```bash
# ruční běh (dry-run i naostro)
python3 scheduler/brightness-scheduler.py --dry-run --verbose
python3 scheduler/brightness-scheduler.py --verbose

# stav configu + dnešní sunrise/noon/sunset
python3 scheduler/schedctl.py get-status

# aktuální hodnota jasu přes D-Bus
busctl --user get-property org.kde.org_kde_powerdevil \
  /org/kde/ScreenBrightness/display0 org.kde.ScreenBrightness.Display Brightness

# stav timeru
systemctl --user status brightness-scheduler.timer
journalctl --user -u brightness-scheduler.service --no-pager
```
