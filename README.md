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

- Raspberry Pi z systemem Linux
- Python 3
- nRF24L01+ podłączony do Raspberry Pi
- opcjonalnie SSD1306 OLED 128×64
- opcjonalnie broker MQTT

## Instalacja i uruchomienie

W katalogu projektu:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Panel jest dostępny pod adresem `http://ADRES_RASPBERRY_PI:8080`.
Port można zmienić w sekcji `web.port` pliku `settings.json`.

## Panel WWW

Panel tworzy osobny blok dla każdego wykrytego nadajnika. Pokazuje ostatnie
odczyty czujników, sekwencję, dane kanałów INA3221 i diagnostykę pakietów.
Bateria jest mierzona na INA CH1. Procent jest orientacyjnym przeliczeniem
napięcia dla Li-ion/LiPo 1S, przy zakresie około 3,0–4,2 V; zależy od stanu
obciążenia i charakterystyki konkretnego ogniwa.

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
Wygaszacz OLED jest dostępny w konfiguracji i działa cyklicznie, niezależnie od
tego, czy nadajniki wysyłają dane. Domyślnie ekran świeci przez 300 sekund,
pozostaje wygaszony przez 60 sekund i następnie pokazuje aktualne dane. Można
wyłączyć wygaszacz przełącznikiem albo zmienić oba czasy w ustawieniach OLED.

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

Plik `weatherlink-gateway.service` zawiera przykładową usługę. Przed
instalacją dostosuj w nim użytkownika i ścieżkę do katalogu projektu, a potem:

```bash
sudo cp weatherlink-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now weatherlink-gateway
sudo systemctl status weatherlink-gateway
```
