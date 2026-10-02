# WeatherLink Gateway

Oprogramowanie gatewaya WeatherLink dla Raspberry Pi. Odbiera pakiety pogodowe
z wielu nadajników przez nRF24L01+, rozdziela pomiary według Node ID i udostępnia
je w panelu WWW, MQTT oraz na wyświetlaczu OLED.

## Możliwości

- odbiór 32-bajtowych pakietów WeatherLink przez nRF24L01+
- obsługa wielu nadajników z osobnymi danymi, sekwencją i licznikami pakietów
- panel WWW z pomiarami pogody, INA3221, baterią i diagnostyką dla każdego noda
- szacowany poziom baterii Li-ion/LiPo 1S na podstawie INA CH1
- OLED SSD1306 128×64: dwa ekrany każdego noda oraz ekran systemowy gatewaya
- ekran systemowy OLED pokazuje Node ID, uptime, użycie CPU i RAM
- publikowanie danych w MQTT z topicami rozdzielonymi według Node ID
- konfiguracja gatewaya w `settings.json`

## Node ID i format pakietu

Gateway odczytuje Node ID z pola `reserved`, czyli przedostatniego bajtu
pakietu WeatherPacket. Nadajnik powinien wpisać tam swój unikalny numer od 0 do
255, a następnie obliczyć CRC z uwzględnieniem tego pola. Nadajniki z takim samym
ID będą widoczne jako jeden węzeł.

Sekwencje i liczniki odebranych oraz utraconych pakietów są prowadzone osobno
dla każdego Node ID. Błędy CRC i błędy formatu są liczone globalnie, bo
uszkodzonego pakietu nie można wiarygodnie przypisać do nadajnika.

## Wymagania

- Raspberry Pi z Raspberry Pi OS (Python 3.9 lub nowszy)
- nRF24L01+ podłączony do Raspberry Pi
- opcjonalnie SSD1306 OLED 128×64
- opcjonalnie broker MQTT
- dostęp do urządzeń SPI (`/dev/spidev*`); OLED wymaga I²C (`/dev/i2c-1`)

## Instalacja i uruchomienie

Najpierw włącz SPI, a jeśli używasz OLED, także I²C. Możesz to zrobić przez
`sudo raspi-config` → **Interface Options** → **SPI/I2C**. Następnie uruchom Pi
ponownie. Użytkownik uruchamiający gateway powinien należeć do grup `gpio`,
`spi` i `i2c`:

```bash
sudo usermod -aG gpio,spi,i2c "$USER"
```

Zainstaluj pakiety systemowe. Biblioteki `libopenjp2-7` i `liblcms2-2` są
potrzebne Pillow na Raspberry Pi OS; pakiety `-dev`, kompilator i CMake
zapewniają kompilację na Pi Zero W, gdy pip nie ma gotowego koła:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-dev \
  build-essential cmake libjpeg62-turbo libopenjp2-7 liblcms2-2 \
  libjpeg-dev zlib1g-dev libopenjp2-7-dev liblcms2-dev libfreetype6-dev
```

Po restarcie i skopiowaniu projektu przejdź do jego katalogu. Zależności
instaluj w wirtualnym środowisku, bez `--break-system-packages`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python3 app.py
```

Panel jest dostępny pod adresem `http://ADRES_RASPBERRY_PI:8080`.
Port można zmienić w sekcji `web.port` pliku `settings.json`.

## Emulator OLED w Windows

Emulator i jego zależności znajdują się w osobnym katalogu `test`. Do testowania
wyglądu bez Raspberry Pi w Windows wystarczy dwukrotnie kliknąć
`test\start_oled_emulator.bat`. Przy pierwszym uruchomieniu skrypt przygotuje
środowisko tylko w tym katalogu i doinstaluje Pillow. Jeśli Python nie jest
zainstalowany, launcher zapyta o instalację Python 3.13 przez Windows Package
Manager (`winget`); jeśli `winget` nie jest dostępny, zainstaluj Python z
[oficjalnej strony Pythona](https://www.python.org/downloads/windows/) i uruchom
launcher ponownie. Można też uruchomić ręcznie w PowerShell, jeśli polecenie
`python` jest dostępne:

```powershell
cd test
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-emulator.txt
.venv\Scripts\python.exe oled_emulator.py
```

Otworzy się okno z ekranem OLED powiększonym pięciokrotnie. Wybierz widok
pogody, zasilania, systemu albo ekran startowy; suwaki od razu aktualizują
przykładowe pomiary. Emulator korzysta z tych samych metod rysowania co gateway.
Nie wymaga SPI, I²C, radia nRF24 ani uruchamiania `app.py`.

## Panel WWW

Panel tworzy osobny blok dla każdego wykrytego nadajnika. Pokazuje ostatnie
odczyty czujników, sekwencję, dane kanałów INA3221 i diagnostykę pakietów.
Bateria jest mierzona na INA CH1. Procent jest orientacyjnym przeliczeniem
napięcia dla Li-ion/LiPo 1S, przy zakresie około 3,0–4,2 V; zależy od stanu
obciążenia i charakterystyki konkretnego ogniwa. Odczyt 0,6 V lub niższy
pokazuje 0%.

Konfiguracja NRF24, MQTT i OLED pozostaje dostępna w prawym panelu. Zmiana
ustawień NRF24 wymaga ponownego uruchomienia gatewaya.

## OLED

Każdy nadajnik ma dwa cyklicznie wyświetlane ekrany:

1. Pogoda: AHT20, BMP280, DS18B20 i odczyt światła.
2. Zasilanie: poziom baterii i napięcie INA CH1, prądy/napięcia INA oraz
   numer sekwencji.

Po ekranach nadajników wyświetlany jest jeden ekran systemowy gatewaya z listą
Node ID, uptime oraz użyciem CPU i RAM. Domyślna konfiguracja OLED to I2C bus 1,
adres `0x3C` i rozdzielczość 128×64. Czas wyświetlania strony ustawia
`oled.page_seconds`. Podczas uruchamiania OLED pokazuje ekran powitalny z logo
WeatherLink Gateway; po odebraniu danych przechodzi do ekranów pomiarowych.
Konfigurowalny, cykliczny wygaszacz działa również podczas normalnego odbioru
pakietów. Domyślnie ekran jest włączony przez 300 sekund, wygaszony przez 60
sekund, a potem automatycznie wraca do aktualnych danych. Można go wyłączyć
przełącznikiem w konfiguracji OLED lub zmienić oba czasy.
OLED używa lokalnego, proporcjonalnego fontu `assets/RobotoCondensed.ttf`,
dołączonego do projektu. Minimalny rozmiar znaków jest dobrany pod czytelność
na monochromatycznym ekranie OLED. Informacja licencyjna znajduje się w
`assets/ROBOTO-CONDENSED-OFL.txt`.

## MQTT

Dane nadajnika o Node ID `2` trafiają pod bazowy topic z prefiksem
`node/2/`, na przykład:

```text
WeatherLink/node/2/data
WeatherLink/node/2/status
WeatherLink/node/2/aht20/temperature
WeatherLink/node/2/aht20/humidity
WeatherLink/node/2/bmp280/temperature
WeatherLink/node/2/bmp280/pressure
WeatherLink/node/2/ds18b20/temperature
WeatherLink/node/2/temt6000/adc
WeatherLink/node/2/ina3221/ch1/voltage
WeatherLink/node/2/ina3221/ch1/current
WeatherLink/node/2/ina3221/ch2/voltage
WeatherLink/node/2/ina3221/ch2/current
WeatherLink/node/2/ina3221/ch3/voltage
WeatherLink/node/2/ina3221/ch3/current
```

Zastąp `WeatherLink` wartością `mqtt.base_topic`, a `2` Node ID nadajnika.
Topic `<bazowy>/data` nadal publikuje ostatni pakiet dowolnego noda dla
zgodności ze starszymi klientami. Pozostałe odczyty są rozdzielone według Node ID.

## Usługa systemd

Plik `weatherlink-gateway.service` uruchamia aplikację interpreterem z `.venv`.
Jeśli używasz innego konta lub katalogu niż `/home/ndn01/Gateway`, popraw w
nim `User`, `WorkingDirectory` i `ExecStart`, a potem:

```bash
sudo cp weatherlink-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now weatherlink-gateway
sudo systemctl status weatherlink-gateway
```
