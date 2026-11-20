# Optima 270 – oversigt over kendte Nabto-læsekommandoer og værdier

**Status:** Kildebaseret teknisk opslagsværk · **Dato:** 20. november 2026 · **Område:** Genvex Connect / Optima 270, legacy Nabto 4/Micro.

> **Vigtigt:** Dokumentet er en komplet oversigt over de **aktive læsedefinitioner i den offentlige Optima 270-model**, ikke et bevis for, at alle disse læsninger virker via **Remote Nabto** eller findes på alle hardware-/firmwarevarianter. Fem datapunkter og RPC17-ping er verificeret via Remote. De øvrige adresser og RPC42 skal valideres, inden de bruges. Ingen kommandoer er kørt for at udarbejde dette dokument.

## Kort overblik

| Type | Antal | Remote-status |
| --- | ---: | --- |
| Gateway-/modelinformation via **RPC17** (`ping.json`) | 1 RPC | **Verificeret remote**; metadatafelter er kildebeskrevet |
| Løbende måleværdier via **RPC45** (datapoint read-list) | **17** aktive modeladresser | **5 verificeret remote**, **12 kun kildebaserede kandidater** |
| Styrings-/indstillingsværdier via **RPC42** (setpoint read-list) | **12** aktive modeldefinitioner, heraf **11** i standardlisten | **Ikke verificeret remote** |
| Fravalgte/udkommenterede setpoint-definitioner | **9** | **Ikke aktive** i modelkoden; ikke talt med i 12 |
| RPC43 (setpoint write-list) | Skrivekommando | **Ikke en læsekommando; ikke en del af vores Remote-undersøgelse** |

**Kommando-ID er ikke det samme som adresse:** Eksempelvis betyder **RPC45, adresse 42** eftervarmens PWM-værdi, mens **RPC42** betyder læsning af en *anden gruppe* – setpunkter. De må ikke forveksles.

**Statusforklaring:** **✅ Remote-verificeret** = faktisk læst fra den autoriserede enhed over Nabto 4/Micro med dokumenteret vellykket respons. **◻ Kildebaseret** = adressen findes i offentlig Optima 270-model, men en separat fjernlæsning er endnu ikke påvist. **⚠ Ikke aktiv** = udkommenteret eller fravalgt i standardforespørgslen.

## 1. Nabto-kommandoerne (RPC-niveau)

| RPC-ID | Navn i klient/protokol | Dansk betydning | Hvad returnerer det? | Dokumenteret status |
| ---: | --- | --- | --- | --- |
| **17** | `ping.json` / `PING` | Spørg gatewayen, hvem den er | Svar-/modeldata og firmwareversion (se nedenfor) | **✅ Remote-verificeret** |
| **45** | `DATAPOINT_READLIST` | Læs en liste af valgte aktuelle målinger | Liste af rå 16-bit sensorværdier, som afkodes via modelens adresser/skala | **✅ Remote-verificeret**, men kun for de fem kendte adresser |
| **42** | `SETPOINT_READLIST` | Læs en liste af aktuelle indstillinger/setpunkter | Rå indstillingsværdier efter modellens read-adresser og skalering | **◻ Kildebaseret**: lokal protokolkode; **ikke prøvet via Remote** |
| **2** | `KEEP_ALIVE` | Hold forbindelsen ved lige | Ikke et katalog over sensorværdier | Kendes i lokal protokolkode; ikke en sensor-læsekommando |

**Udeladt:** Kommando **43** (`SETPOINT_WRITELIST`) kan *ændre* indstillinger. Den er **ikke** en læsekommando og er ikke verificeret eller godkendt til Remote-test.

### 1.1 Identifikation med RPC17

LS Controls officielle Nabto XML-interface for `ping.json` angiver blandt andet disse returfelter:

| Feltnavn | Dansk forklaring | Bemærkning |
| --- | --- | --- |
| `Pong` | Bekræftelse på ping | Protokolværdi |
| `Devicenumber` | Enheds-/controller-nummer | Bruges sammen med `Model` til modelvalg |
| `Model` | Modelkode | Eksempel fra offentlig modelvælger: `2010` for Optima 270 **kombineret med** `Devicenumber=79265` |
| `Version` | Controllerens oplyste version | Skal fortolkes ift. firmware efter særskilt validering |
| `SlaveDevicenumber` | Undercontrollerens nummer | Vigtigt for andre controllerfamilier |
| `SlaveModel` | Undercontrollerens modelkode | Vigtigt for andre controllerfamilier |
| `UserNames:` | Kontorelaterede brugeroplysninger | **Følsomt; må ikke logges eller gemmes i modelkataloget** |

**RPC17 er ikke en sensorliste.** Den kan hjælpe os med at vælge den rette forhåndsdefinerede modelprofil.

## 2. Alle 17 aktive datapunkter – RPC45

Alle disse poster har **`obj=0`** i Optima 270-modellen (den generelle models standardobjekt). Skalaen er fra offentlig kode og angiver beregningen **fra rå værdi til vist værdi**.

| Adresse | Intern nøgle | Dansk navn | Hvad fortæller værdien? | Rå → vist værdi | Remote |
| ---: | --- | --- | --- | --- | --- |
| **20** | `TEMP_SUPPLY` | **Tillufttemperatur** | Temperaturen på luften, der blæses ind i boligen | `(rå - 300) / 10` °C | ✅ |
| **21** | `TEMP_OUTSIDE` | **Udelufttemperatur** | Temperaturen på luften, der suges ind udefra | `(rå - 300) / 10` °C | ✅ |
| **22** | `TEMP_EXHAUST` | **Afkastlufttemperatur** | Temperaturen på luften, der ledes ud af huset | `(rå - 300) / 10` °C | ✅ |
| **23** | `TEMP_EXTRACT` | **Fralufttemperatur** | Temperaturen på luften, der suges ud af rummene | `(rå - 300) / 10` °C | ✅ |
| **24** | `TEMP_FROSTPROTECTION` | Frostbeskyttelsestemperatur | Temperaturføler relateret til anlæggets frostsikring | `(rå - 300) / 10` °C | ◻ |
| **26** | `HUMIDITY` | **Luftfugtighed** | Målt relativ luftfugtighed | `rå` % | ✅ |
| **18** | `DUTYCYCLE_SUPPLY` | Tilluftventilator – styregrad | Ventilatorens styresignal/belastning, **ikke** omdrejningstal | `rå / 100` (LAN-visning: %) | ◻ |
| **19** | `DUTYCYCLE_EXTRACT` | Fraluftventilator – styregrad | Styregrad for ventilatoren, som suger luft ud af rummene | `rå / 100` (LAN-visning: %) | ◻ |
| **35** | `RPM_SUPPLY` | Tilluftventilator – RPM | Faktiske omdrejninger pr. minut | `rå` rpm | ◻ |
| **36** | `RPM_EXTRACT` | Fraluftventilator – RPM | Faktiske omdrejninger pr. minut | `rå` rpm | ◻ |
| **50** | `ROTOR_SPEED` | Rotorens omdrejninger | Hastighed for eventuel varmegenvindingsrotor | `rå` rpm | ◻ |
| **41** | `PREHEAT_PWM` | Forvarme – PWM | Reguleringssignal for forvarmeelement | `rå / 100` (LAN-visning: %) | ◻ |
| **42** | `REHEAT_PWM` | Eftervarme – PWM | Reguleringssignal for eftervarmeelement | `rå / 100` (LAN-visning: %) | ◻ |
| **53** | `BYPASS_ACTIVE` | Bypass aktiv | Status for bypassspjældet | `rå`; boolsk betydning skal verificeres | ◻ |
| **40** | `BYPASS_ANALOG` | Bypass – analog værdi | Rå positions-/reguleringsværdi for bypass | `rå`; præcis skala/enhed ukendt | ◻ |
| **114** | `ALARM_OPTIMA270_1` | Alarmregister 1 | Første del af controllerens alarmstatus | Rå 16-bit alarmfelt; kræver bitafkodning | ◻ |
| **115** | `ALARM_OPTIMA270_2` | Alarmregister 2 | Anden del af controllerens alarmstatus | Rå 16-bit alarmfelt; kræver bitafkodning | ◻ |

**Bekræftede fem:** RPC45 er udført med `obj=0` og adresserne **20, 21, 22, 23, 26** både enkeltvis og samlet. Et vellykket fem-elements batch beviser **ikke**, at alle 17 adresser kan læses i et enkelt Remote-batch.

**Detalje om procentværdier:** Den offentlige LAN-model dividerer ventilator-styregrad/PWM med 100 og HA-integrationens labels bruger `%`. Før vi udvider Remote, skal faktisk værdiområde og korrekt visningsskala kontrolleres mod anlægget; vi må ikke automatisk gange med 100 eller gætte om værdien er en brøk eller procenttal.

### 2.1 Alarmer – hvad ligger i de to registre?

Adresse **114** og **115** er *ikke* to enkeltalarmer, men rå felter, som den eksisterende LAN-integration forsøger at omsætte til en samlet alarmliste. Den har danske oversættelser for blandt andet:

- Filterskift, ekstern stoptilstand og følerfejl på T1–T9.
- Fejl på fugtføler, brandtest/brandfejl, tilluft- og fraluftventilator.
- Frostfejl, fejl ved brandspjæld 1–4, brandbokse samt rotorfejl.

**Bemærk:** Den eksisterende kode indeholder forskellige bit-/tilstandstabeller og en særlig alarmdekoder. Bitværdierne og sammensætningen af registrene skal gennemgås og verificeres særskilt, før vi laver alarmentiteter i Remote. Det ovenstående er en beskrivelse af *mulige alarmtekster i koden*, ikke en valideret alarmmaskeliste.

## 3. Alle 12 aktive setpunktdefinitioner – RPC42 (kun kildebaserede)

Et setpunkt er en **indstilling**, som anlægget bruger i sin regulering, til forskel fra en direkte målt sensorværdi. Tabellen viser kun **læseadresserne**, aldrig skriveadresser. `read_obj=0` gælder alle nedenstående. Offentlig modelkode indeholder 12 definitioner, men kun de første 11 findes i dens standardlæseliste.

| Læseadresse | Intern nøgle | Dansk betegnelse | Hvad betyder den? | Rå → vist værdi | Standardlæst? |
| ---: | --- | --- | --- | --- | --- |
| **7** | `FAN_SPEED` | Valgt ventilatortrin | Det valgte driftstrin, i modellens område 0–4 | `rå` (trin) | Ja |
| **1** | `TEMP_SETPOINT` | Ønsket temperatur | Anlæggets temperatursetpunkt | `(rå + 100)/10` °C | Ja |
| **21** | `BYPASS_OPENOFFSET` | Bypass – åbningstillæg | Temperaturforskel/tillæg brugt i bypass-åbningslogikken | `rå/10` (°C-forskel) | Ja |
| **29** | `BYPASS_TURNOFF` | Bypass – stopbetingelse | Parameter som indgår i grænsen for, hvornår bypass ikke længere anvendes | `rå` (model-/HA-logik tolker som temperaturforskel) | Ja |
| **57** | `BYPASS_FORCE_SPEED` | Bypass – tvungen hastighed | Parameter for tvungen bypass-/ventilatorregulering; præcis mekanik bør verificeres | `rå` (kildeinterval 0–100) | Ja |
| **58** | `BYPASS_FORCE_TEMP` | Bypass – tvungen temperatur | Temperaturparameter til tvungen bypassfunktion | `rå/10` (°C) | Ja |
| **3** | `REHEATING` | Eftervarme aktiveret | Om eftervarmestyring er slået til | `rå` (0/1 i kildemodel) | Ja |
| **6** | `HUMIDITY_CONTROL` | Fugtstyring aktiveret | Om fugtbaseret regulering er aktiv | `rå` (0/1 i kildemodel) | Ja |
| **30** | `BOOST_ENABLE` | Boost/forcering | Om anlæggets boostfunktion er aktiveret | `rå` (0/1 i kildemodel) | Ja |
| **70** | `BOOST_TIME` | Varighed af boost | Tidsparameter for boost-funktion | `rå` (kildeinterval 1–120; enhed skal verificeres) | Ja |
| **100** | `FILTER_DAYS` | Dage siden filterskift | Filtertimerens antal dage i den eksisterende HA-visning | `rå` dage | Ja |
| **50** | `FILTER_RESET` | Nulstilling af filtertimer | Styringsparameter til filterreset; ikke normal løbende måling | `rå` (0–2 i kildemodel) | **Nej** |

**⚠ Ingen af disse RPC42-læsninger er endnu verificeret via Remote Nabto.** At indstillinger findes i lokal modelkode, betyder ikke, at det er muligt eller sikkert at læse dem via den fjerne gateway uden særskilt test. Vi sender **ingen skrivekommandoer**.

**Vigtig adresseadskillelse:** Setpunkt-adresse **21** (bypass-tillæg) er ikke samme måling som datapunkt-adresse **21** (udelufttemperatur), fordi de aflæses med forskellige RPC-kommandoer. Tilsvarende er setpunkt-adresse **50** (filterreset) ikke datapunkt-adresse **50** (rotorhastighed).

## 4. Definitioner, som *ikke* er aktive i den offentlige model

Disse er udkommenteret i kildefilen og skal **ikke** betragtes som tilgængelige Remote-sensorer eller aktiv setpunktunderstøttelse:

| Udkommenteret nøgle | Angivet læseadresse | Kommentar |
| --- | ---: | --- |
| `BYPASS_MIN_ON` | 59 | Udkommenteret med bemærkning om mulig låsning |
| `SUPPLY_AIR_LEVEL1` | 10 | Tilluft, niveau 1 – ikke aktiv |
| `SUPPLY_AIR_LEVEL2` | 11 | Tilluft, niveau 2 – ikke aktiv |
| `SUPPLY_AIR_LEVEL3` | 12 | Tilluft, niveau 3 – ikke aktiv |
| `SUPPLY_AIR_LEVEL4` | 8 | Tilluft, niveau 4 – ikke aktiv |
| `EXTRACT_AIR_LEVEL1` | 13 | Fraluft, niveau 1 – ikke aktiv |
| `EXTRACT_AIR_LEVEL2` | 14 | Fraluft, niveau 2 – ikke aktiv |
| `EXTRACT_AIR_LEVEL3` | 15 | Fraluft, niveau 3 – ikke aktiv |
| `EXTRACT_AIR_LEVEL4` | 9 | Fraluft, niveau 4 – ikke aktiv |

## 5. Beregnede Home Assistant-værdier – ikke selvstændige Nabto-kommandoer

Følgende kan principielt udledes, når de nødvendige inddata er indlæst og godkendt:

| Beregnet visning | Grundlag | Vigtigt |
| --- | --- | --- |
| Varmegenvindingseffektivitet | Tilluft (20), udeluft (21) og fraluft (23) | Eksisterende LAN-formel: `(tilluft – udeluft)/(fraluft – udeluft) × 100`; håndtér division med nul og ugyldige målinger |
| Samlet alarmliste og antal alarmer | Alarmfelter 114 og 115 | Kræver korrekt, testet fortolkning af bitmasker før Remote |
| Bypass-relaterede grænsetemperaturer | Temperatursetpunkt og visse bypass-setpunkter | Kræver læsbare RPC42-værdier, som **ikke** er remote-verificeret |

De beregnede entiteter medfører ikke nødvendigvis ekstra RPC-kald; de må **ikke** få selvstændige registeradresser.

## 6. Hvad kan vi trygt arbejde videre med?

1. **Nu:** Brug de fem verificerede datapunkter som stabilt Remote-grundlag; behold eksisterende snapshot v1 og installerede løsninger urørt.
2. **Næste dokumenterede skridt:** Lav en kildebaseret testmatrix for de **12** yderligere RPC45-adresser, deres datatyper, numeriske intervaller og korrekte enheder. En eventuel live-test kræver særskilt godkendelse; ingen automatisk scanning.
3. **Dernæst:** Undersøg read-only RPC42 separat for **11 standardsetpunkter** og evt. filterreset-feltet; verificér at koden kun læser, ikke ændrer.
4. **Fremtidig HA-arkitektur:** Vælg model via whitelisted `ping.json`-metadata, opret kun verificeret understøttede entiteter, og lad avancerede diagnostiske entiteter være deaktiveret som standard. Ukendte sensorer skal ikke oprettes som falske entiteter.

## Kilder (gennemgået 20. november 2026)

- [Optima 270-modellens præcise datapunkter, setpunkter og standardlister](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/models/optima270.py)
- [Basisdefinitioner, standardobjekt, offset/division](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/models/basemodel.py)
- [Protokolkommandoer og RPC-opkoder](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/protocol/payload.py) · [datapunkt-læseliste](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/protocol/cmd_datapoint_readlist.py) · [setpunkt-læseliste](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/protocol/cmd_setpoint_readlist.py)
- [Nabto/LS Controls officielle ping-RPC-interface](https://github.com/nabto/cordova-lsc-test/blob/main/www/js/index.js)
- [GenvexNabto modeladapter og afkodningslogik](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/genvexnabto_modeladapter.py)
- [Eksisterende danske Home Assistant-oversættelser](../custom_components/genvex_connect/translations/da.json) og [alarmliste-implementering](../custom_components/genvex_connect/sensor.py) (læst som reference; **ikke ændret**)
- [Projektets fjernverificerede sensoraflæsninger](remote-phase1-sensor-validation-2026-11-19.md) · [2B-undersøgelse](remote-device-discovery-2b.md) · [2A-katalog](remote-sensor-catalog-2a.md)

**Intet i dette opslagsværk er en tilladelse til at teste uspecificerede RPC-id'er, skrive til anlægget, ændre LAN-integrationen eller ændre de installerede Apps.**
