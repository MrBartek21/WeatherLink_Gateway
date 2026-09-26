# WeatherLink Gateway

Gateway dla stacji WeatherLink na Raspberry Pi.

## Funkcje

- odbiór `WeatherPacket` 32 B przez nRF24L01+
- wiele nadajników rozróżnianych przez `Node ID` (pole `reserved` w pakiecie; 0–255)
- osobne dane, sekwencje i liczniki odebranych/utraconych pakietów dla każdego węzła
- adres `WTHLS`
- kanał 50
- 250 KBPS
- HIGH
- Auto ACK
- CRC8
- kontrola sequence i utraconych pakietów
- OLED SSD1306 128x64
- MQTT
- WebUI
- konfiguracja zapisywana w `settings.json`

## Uruchomienie

```bash
cd /home/d02/app/weatherlink-gateway
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Panel:
`http://IP_RPI:8080`

## OLED

Domyślnie:

- I2C bus 1
- adres 0x3C
- SSD1306 128x64

## MQTT

Dane każdego nadajnika są publikowane pod topicami zaczynającymi się od
`WeatherLink/node/<Node ID>/`, np. `WeatherLink/node/2/data` oraz
`WeatherLink/node/2/ina3221/ch1/voltage`. Topic `WeatherLink/data` nadal
zawiera ostatni pakiet dowolnego węzła dla zgodności ze starszymi klientami.

## Node ID nadajnika

Gateway odczytuje `Node ID` z bajtu `reserved` (przedostatni bajt 32-bajtowego
pakietu). Oprogramowanie każdego nadajnika musi wpisać tam swój unikalny numer
0–255 i uwzględnić ten bajt przy obliczaniu CRC. Sekwencja pakietów może być
niezależna na każdym nadajniku. Nadajnik, który nadal wysyła `reserved = 0`,
będzie widoczny jako `Node ID 0`.

Uszkodzonych pakietów nie da się wiarygodnie przypisać do węzła, dlatego błędy
CRC i formatu w diagnostyce są licznikami całego odbiornika. Pakiety odebrane i
utracone są liczone osobno dla każdego Node ID.

Pozostałe odczyty z identyfikatorem węzła są dostępne pod analogicznymi
topicami, np. `WeatherLink/node/2/aht20/temperature`.

Poprzednie topiki czujników bez `node/<id>` nie są już publikowane, ponieważ
przy wielu nadajnikach nadpisywałyby się nawzajem.

```text
WeatherLink/data
WeatherLink/status
WeatherLink/aht20/temperature
WeatherLink/aht20/humidity
WeatherLink/bmp280/temperature
WeatherLink/bmp280/pressure
WeatherLink/ds18b20/temperature
WeatherLink/temt6000/adc
WeatherLink/ina3221/ch1/voltage
WeatherLink/ina3221/ch1/current
WeatherLink/ina3221/ch2/voltage
WeatherLink/ina3221/ch2/current
WeatherLink/ina3221/ch3/voltage
WeatherLink/ina3221/ch3/current
WeatherLink/test
```

## Usługa systemd

Po instalacji dostosuj `User` i ścieżkę w:

```text
weatherlink-gateway.service
```

Następnie:

```bash
sudo cp weatherlink-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now weatherlink-gateway
sudo systemctl status weatherlink-gateway
```
