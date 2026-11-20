# 2B – Optima 270: plan for sikre RPC45-udvidelser

**Dato:** 20. november 2026  
**Status:** Kilde- og offline-testfase. Ingen nye live Nabto-kald eller HA-entities udført.

## Formål

Vores mål er **modelidentifikation → katalogopslag → læs alle *verificeret understøttede* datapunkter**. Vi behøver ikke vente på en ukendt universel `get_all_sensors`-RPC: den offentlige Optima 270-model indeholder allerede **17 konkrete datapunkter**, og den rekonstruerede **read-only RPC45** har læst fem af dem fra anlægget.

Det er dog afgørende ikke at forveksle *kildebaseret adresse* med *remote-verificeret funktionalitet*. Først efter en vellykket, godkendt realtest flyttes den enkelte adresse til det aktive Remote-katalog.

## Aktuel sikker baseline

| Kilde | Resultat |
| --- | --- |
| Verificeret RPC45-batch (i denne rækkefølge) | `(0,20), (0,21), (0,22), (0,23), (0,26)` |
| Verificerede sensorer | Tilluft, udeluft, afkastluft, fraluft, luftfugtighed |
| Katalog, der må indgå i read-only forespørgsler | Kun fem `remote_rpc45_verified`-poster i [`capability_catalog.py`](../experimental/genvex_remote/capability_catalog.py) |
| Kildebaseret kandidatpulje | 12 poster i [`optima270_source_only.py`](../experimental/genvex_remote/optima270_source_only.py), **aldrig** i den normale batch |
| Pure-Python planlægningskode | [`verified_read_plan.py`](../experimental/genvex_remote/verified_read_plan.py) – genererer kun inert **fem-elements** RPC45-requeststruktur fra verificerede, filtrerede ping-metadata |
| Regressionstests | [`test_verified_read_plan.py`](../experimental/genvex_remote/test_verified_read_plan.py) – beskytter mod ukendte, ombyttede og kildebaserede adresser |

Alt dette er udviklingskode uden Nabto SDK, netværk, adgang til credentials eller HA Core. Den eksisterende LAN-integration, installerede Remote App, test-App og de fem fungerende læsninger er ikke ændret.

## Konkret testmatrix for de 12 resterende læsninger

Følgende er **nøjagtige adresser fra** [superrob/genvexnabto – Optima 270](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/models/optima270.py), ikke en numerisk scanning. `obj=0`, `RPC=45`. Kildeskalering er medtaget, men fysisk tolkning og Remote-support er endnu ikke verificeret.

| Prioritet | Adresse | Kildebetegnelse | Danske værdier | Skala i kildekoden | Hvad skal valideres? | Status |
| --- | ---: | --- | --- | --- | --- | --- |
| 1 | 24 | `TEMP_FROSTPROTECTION` | Frostbeskyttelsestemperatur | `(rå-300)/10` °C | Plausibilitet, følerens faktiske placering, sammenligning med kendt visning | Kildebaseret |
| 1 | 35 | `RPM_SUPPLY` | Tilluftventilatorens omdrejninger | `rå` rpm | Mulighed for 0 ved stilstand, plausible omdrejninger | Kildebaseret |
| 1 | 36 | `RPM_EXTRACT` | Fraluftventilatorens omdrejninger | `rå` rpm | Om værdien følger driftstilstand | Kildebaseret |
| 1 | 18 | `DUTYCYCLE_SUPPLY` | Tilluftventilatorens styregrad | `rå/100` | Afklar om korrekt vist værdi er %, forholdstal eller anden skala | Kildebaseret |
| 1 | 19 | `DUTYCYCLE_EXTRACT` | Fraluftventilatorens styregrad | `rå/100` | Samme skala-/enhedstjek | Kildebaseret |
| 2 | 53 | `BYPASS_ACTIVE` | Bypass-status | `rå` | Verificér boolske tilstande og faktisk spjældstatus; må ikke antages ud fra 0/1 alene | Kildebaseret |
| 2 | 40 | `BYPASS_ANALOG` | Bypass analog værdi | `rå` | Hvad er fysisk enhed, position og interval? | Kildebaseret |
| 2 | 41 | `PREHEAT_PWM` | Forvarme-styring | `rå/100` | Fortolkning, interval og eventuel manglende varmehardware | Kildebaseret |
| 2 | 42 | `REHEAT_PWM` | Eftervarme-styring | `rå/100` | Fortolkning, interval og hardwaretilstedeværelse; **ikke RPC ID42** | Kildebaseret |
| 2 | 50 | `ROTOR_SPEED` | Rotorens omdrejninger | `rå` rpm | Sondr mellem manglende rotor og målt 0 rpm | Kildebaseret |
| 3 | 114 | `ALARM_OPTIMA270_1` | Alarmregister 1 | Rå bitfelt | 16-bit fortolkning, bitrækkefølge og bevidst ingen alarmaktivering | Kildebaseret |
| 3 | 115 | `ALARM_OPTIMA270_2` | Alarmregister 2 | Rå bitfelt | Fortolkning som par med 114; ingen ukritisk alarmdekodning | Kildebaseret |

**Prioritet er en undersøgelsesrækkefølge, ikke sikkerhedsgodkendelse**. Vi skal undgå at skabe automatiske HA-alarmhændelser på baggrund af uprøvede bitmasker. Det er også vigtigt at skelne mellem en **fysisk manglende funktion** (fx rotor) og en målt **nulværdi**.

## Forslag til kontrolleret realverifikation (kræver særskilt godkendelse)

1. Bekræft først, at **RPC17** fra den eksisterende autoriserede testprofil giver den forventede, *whitelistede* numeriske modelidentitet. Under ingen omstændigheder udskrives eller gemmes `UserNames:`, hele ping-JSON, credentials eller device-ID.
2. **Ét nyt kildebaseret datapunkt ad gangen** via **kun read-only RPC45**, med dokumenteret adresse, maksimum ét listeelement pr. kald, begrænset køretid og stop ved første RPC/afkodningsfejl. Ingen gættede adresser, RPC42 eller skrivekommando RPC43. Den eksisterende fem-element-batch ændres ikke.
3. Sammenhold måleværdien med controllerens kendte UI eller en anden autoriseret visning, hvor den findes. Et vellykket `RPC status=0` bekræfter ikke automatisk korrekt enhed, skalering eller sensorhardware.
4. Registrér pr. post: controller-/firmwareprofil i ikke-personhenførbar form, succes/fejl, responstælling, rå datatype, plausibilitet, eventuelt særlig hardware og om værdien bør være aktiveret eller **deaktiveret som standard** i HA.
5. Først efter positiv godkendt validering opdateres Remote-katalogets bevisstatus; efterfølgende afprøves selvstændige korte batchgrupper **med versionsopdelt snapshotformat** (3A), så fejl i en valgfri måling ikke gør de fem grundsensorer utilgængelige.

## Dynamiske entities efter Shelly-modellen

Det globale katalog er en **union** af alle kendte målinger på tværs af modeller, men en konkret installation får kun **de sensorer som dens verificerede model og hardware understøtter**.

| Betingelse | Beslutning i HA |
| --- | --- |
| Verificeret måling, almindelig brug | Opret – enabled |
| Verificeret måling, avanceret/diagnostisk | Opret – disabled by default; bruger kan aktivere |
| Ukendt, source-only eller fraværende hardware | Opret ikke |
| Verificeret måling, midlertidig kommunikationsfejl | Behold – unavailable, ikke disabled |

**Vigtigt:** Disabled by default i Home Assistant ændrer ikke nødvendigvis Nabto Appens polling. Om kun aktiverede sensorer skal læses, eller om små verificerede grupper kan batches fast, undersøges særskilt under **3A**.

## Milepæle

- [x] Identificeret de 17 Optima 270-datapunkter i offentlig kildekode.
- [x] 5 læsninger fjernverificeret via RPC45 og bevaret som stabil v1.
- [x] Identificeret de 12 ikke-verificerede adresser uden scanning.
- [x] Etableret isoleret kildebaseret kandidatpulje og sikker offline-planlægger.
- [ ] Live RPC17-identitet verificeret med whitelist og godkendelse.
- [ ] 12 enkeltvise live RPC45-aflæsninger vurderet og dokumenteret.
- [ ] Kun godkendte/validerede målinger optaget i egentligt Remote-katalog.
- [ ] HA Core-oprettelse, disabled defaults og versioneret multi-type snapshot testet.

## Referencer

[Dansk fuld oversigt](optima270-nabto-read-command-reference-da.md) · [2B research](remote-device-discovery-2b.md) · [2A katalog](remote-sensor-catalog-2a.md) · [Projektets verificerede facts](remote-nabto-verified-facts.md).

**Ingen live-kald, credentials, Apps eller LAN-konfigurationer er ændret som led i denne forberedelse.**
