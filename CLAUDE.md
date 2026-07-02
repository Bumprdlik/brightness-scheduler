# brightness-scheduler

Automatická úprava jasu dvou externích monitorů podle polohy Slunce v Praze
(ne podle pevných hodin — sunrise/noon/sunset se počítají denně z `astral`).

## Hardware

- **LG 34GL750** — `DP-1`, DDC bus `/dev/i2c-0`, D-Bus `display0`. DDC/CI spolehlivé.
- **Acer V243W** (2008) — `DP-2`, DDC bus `/dev/i2c-1`, D-Bus `display1`. Připojený
  přes DP→DVI redukci (aktivní converter chip), DDC/CI je nespolehlivé na úrovni
  syrového `ddcutil` (EIO chyby), ale **funguje** přes `powerdevil`, protože ten má
  vlastní retry s backoffem (1s, 2s...) a na pár pokusů se spojí. Proto celý projekt
  jde přes Plasma D-Bus rozhraní, ne přímo přes `ddcutil` CLI.
- Grafika (RTX 4060) nemá žádný DVI výstup (jen 3× DP + 1× HDMI), takže adaptér
  na Aceru je nutný. Uvažovali jsme přepojení na HDMI→DVI (pasivnější, možná
  stabilnější DDC) — zatím neuděláno, uživatel to případně vyřeší fyzicky sám.

## Architektura

Tři komponenty sdílející `~/.config/brightness-scheduler/config.json`
(mimo git — obsahuje jen osobní vyladěné hodnoty; šablona je v `config/config.json`):

- `scheduler/schedcore.py` — sdílené jádro: config I/O, výpočet sunrise/noon/sunset
  (`astral`), lineární interpolace mezi kotvami (`night/sunrise/noon/sunset`),
  volání D-Bus `SetBrightness`.
- `scheduler/brightness-scheduler.py` — periodický apply, spouští ho systemd timer.
  Cachuje poslední nastavenou hodnotu v `~/.cache/brightness-scheduler/last.json`
  a nezapisuje, pokud je rozdíl < 1 % (šetří zbytečné DDC volání na Acer).
- `scheduler/schedctl.py` — CLI pro widget: `get-status` / `set-anchor` /
  `set-enabled` / `preview` (live náhled bez persistence). Volané z QML přes
  shell (`Plasma5Support.DataSource`, engine `"executable"`), protože čisté QML
  nemá file I/O ani D-Bus bindings.
- `plasmoid/org.vencator.brightnessscheduler/` — Plasma widget se slidery
  (night/sunrise/noon/sunset) pro oba monitory zvlášť + master on/off switch.

## D-Bus rozhraní (Plasma 6, stejné jako systémový slider jasu)

```
service:   org.kde.org_kde_powerdevil
paths:     /org/kde/ScreenBrightness/display0  (LG)
           /org/kde/ScreenBrightness/display1  (Acer)
interface: org.kde.ScreenBrightness.Display
method:    SetBrightness(int32 value, uint32 flags)   # value 0–10000 = 0–100 %
property:  Brightness, MaxBrightness, Label
```

## Nasazení: symlinky, ne kopie

Zdrojáky žijí jen tady v `~/Projects/Personal/brightness-scheduler/`; do
systémových míst vedou symlinky, takže úpravy tady se projeví okamžitě:

```
~/.config/systemd/user/brightness-scheduler.{service,timer}
    -> ~/Projects/Personal/brightness-scheduler/systemd/brightness-scheduler.{service,timer}
~/.local/share/plasma/plasmoids/org.vencator.brightnessscheduler
    -> ~/Projects/Personal/brightness-scheduler/plasmoid/org.vencator.brightnessscheduler
```

Po úpravě QML: `kbuildsycoca6` (přebuild cache) + restart plasmoidu/plasmashellu,
aby se změna projevila.

## Plasma 6 QML gotchas (narazili jsme na tyhle, ověřeno na Plasma 6.7.2)

- `metadata.json` **nesmí** mít `"X-Plasma-API": "declarativeappletscript"` —
  to je legacy Plasma 4/5 marker a způsobí hlášku "not compatible with Plasma 6".
  Správně: `"KPackageStructure": "Plasma/Applet"` a `"X-Plasma-API-Minimum-Version": "6.0"`,
  žádný `X-Plasma-MainScript` (KPackage si `contents/ui/main.qml` najde sám).
- Import je `org.kde.plasma.plasma5support`, ne `org.kde.plasma5support`
  (balíček `plasma5support` obsahuje `DataSource` s `engine: "executable"` pro
  spouštění shellových příkazů z QML).
- `org.kde.plasma.core` v této verzi neexportuje `IconItem` — použij
  `Kirigami.Icon` (`import org.kde.kirigami as Kirigami`) místo `PlasmaCore.IconItem`.
- Testování bez nutnosti přidávat widget na panel: `plasmoidviewer -a <plugin-id>
  -f application -s 500x600` rovnou zobrazí `fullRepresentation`, ne jen
  `compactRepresentation` v malém desktop containeru.

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
