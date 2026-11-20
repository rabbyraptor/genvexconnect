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


## Forberedt, men endnu ikke kørt: engangstest af én ekstra sensor

Det isolerede [`scripts/probe_optima270_single_source_candidate.py`](../scripts/probe_optima270_single_source_candidate.py) kan **offline** vise adressen og skalaen for præcis én af de 12 kildebaserede kandidater. Det kan **ikke** læse en vilkårlig brugerindtastet adresse, scanne en adresseblok eller sende skrivende RPC-kommandoer. Skriptet forventer den eksisterende autoriserede Steam Deck-testprofil ved en eventuel særskilt godkendt live-test; det har **ikke** adgang til installerede HAOS Apps.

**Sikker offline-preview på et checkout af branch `remote-nabto-connection`:**

```sh
python3 scripts/probe_optima270_single_source_candidate.py --key frost_protection_temp
```

Dette gør **intet på netværket**, importerer ikke Nabto SDK og læser ikke credentials. `--key` skal matche én af de 12 præcist navngivne kildebaserede kandidater. En live-test kræver **to ekstra eksplicitte CLI-flag og en særskilt operatørgodkendelse**; et live-kald sendes ikke automatisk.

Ved godkendt live-test: Højst **én** `nabtoRpcInvoke` for den valgte adresse via **RPC45**. Scriptet anvender den hidtil fungerende `candidate_read_datapoints.json`-XML med **én adresse**, sætter midlertidige testkopier af eksisterende certifikat/nøgle under privat tmp, frigiver SDK-svar og udskriver kun en begrænset status, eventuelle numeriske fejl-/eventkoder samt én rå og én kilde-skaleret måling. Kildeskaleret værdi betyder **ikke** automatisk, at korrekt fysisk enhed/tilgængelig hardware er verificeret.

**Driftsbegrænsning:** Den proprietære SDK's kald er ikke nødvendigvis afbrydelige fra Python. En senere operatørgodkendt kørsel skal derfor have en ekstern, hård tidsgrænse og efterkontrol af testprofil-oprydning. Tvangsafbrydelse eller SDK-nedbrud kan efterlade en midlertidig credential-kopi, som kræver kontrolleret oprydning. Denne risiko er en yderligere grund til ikke at aktivere live-kørslen før separat aftale.

[Offline CLI-/response-regressionstests](../experimental/genvex_remote/test_single_candidate_cli.py) kontrollerer standard-preview, særskilt autorisation, ét kendt objekt, fravær af skrive-RPC og fail-closed JSON-afkodning. Ingen af disse tests opretter en Nabto-session.


### Seneste offline-accept (`5a41bb1`)

Katalog/kandidater, verified-only-requestplanen og engangstestværktøjets CLI-sikkerhedstests blev kørt i [Remote Nabto offline CI](https://github.com/rabbyraptor/genvexconnect/actions/runs/44801745246) og [Remote App offline CI](https://github.com/rabbyraptor/genvexconnect/actions/runs/44801744289), begge **PASS**. Også [formattering](https://github.com/rabbyraptor/genvexconnect/actions/runs/44801744047) og [Hassfest](https://github.com/rabbyraptor/genvexconnect/actions/runs/44801744124) bestod. Ingen live Nabto-test blev kørt.

[HACS-validatering](https://github.com/rabbyraptor/genvexconnect/actions/runs/44801744154) fejler stadig alene på repositorymetadata: **Issues slået fra** og **manglende gyldige topics**. Denne uafhængige releaseopgave findes allerede i vedligeholdelsesplanen; projektets konfiguration ændres ikke her.


## 2B Steam Deck live-run timeout, korrekt nøgleprompt (2026-11-20)

Ved den første *forsøgte* live-kørsel indtastede operatøren den skjulte e-mail-identitet og det 12-cifrede device-ID, hvorefter `timeout` returnerede **exit 124** uden `===== ONE SOURCE-DEFINED RPC45 READ ONLY =====` eller andre SDK-statuslinjer. Det tidligere Python-script bad om nøgleadgangskoden med `getpass.getpass()` **før** den første statuslinje; en blokering dér er mest sandsynlig, men den præcise årsag er ikke bevist. **Der er ingen dokumentation for, at et RPC-kald blev sendt**, og sensoren **24** forbliver `source_only_unverified`.

For at undgå blind timeout i en skjult nøgleprompt er der nu tilføjet en **Steam Deck-runner**: [`scripts/run_optima270_one_read_from_deck.sh`](../scripts/run_optima270_one_read_from_deck.sh).

- **Standard `--preflight`** udfører udelukkende syntakskontrol og offline-katalog-preview, uden Nabto-session eller legitimationsoplysninger.
- **`--execute-live`** kontrollerer tilstedeværelse af eksisterende testprofil og SDK, spørger **synligt** efter de tre *skjulte* input (e-mail, device-ID og eksisterende nøgleadgangskode), og sender kun adgangskoden gennem en lukket stdin-pipe. Ingen nøgleadgangskode placeres i miljøvariabler eller argumenter.
- Python accepterer nu kun `--passphrase-stdin` ved live-tilstand; direkte live-kørsel med gammel `getpass.getpass`-adfærd er afvist for at undgå en ny skjult 90-sekunders timeout.
- Wrapperens parentproces ejer et privat `TMPDIR` og forsøger oprydning også ved timeout; bruger `timeout -k 5s 90s`, udfører højst **én** read-only `RPC45` for **adresse 24**, og gentager aldrig automatisk.
- Python udskriver et ikke-følsomt pre-SDK-stage-mærke efter eksisterende profiltjek og efter modtagelse af pipe-input; dermed kan en fremtidig fejl lokaliseres uden at udskrive person-/account-data.
- Live-kørsel kræver fortsat særskilt operatørbeslutning; de eksisterende installerede HAOS Apps og LAN-integrationen er urørte.

**Offline først:**

```sh
bash scripts/run_optima270_one_read_from_deck.sh --preflight
```

**Kun ved særskilt godkendt én-sensor-test:**

```sh
bash scripts/run_optima270_one_read_from_deck.sh --execute-live
```

Behold kun redigeret terminaloutput uden e-mail, device-ID eller nøgleadgangskode i eventuelle supporttråde. De nye [Python CLI-sikkerhedstests](../experimental/genvex_remote/test_single_candidate_cli.py) og [Bash-wrapper-tests](../experimental/genvex_remote/test_deck_runner_preflight.py) udføres offline i projektets eksisterende GitHub-testworkflow.


## Første live-forsøg: Nabto gateway-opslag fejlede (2026-11-20)

Brugerens Steam Deck-output fra den særskilt godkendte **ene read-only RPC45-forespørgsel** viser:

```text
PASS: existing test profile and SDK files are present
PASS: encrypted-key input received; preparing SDK
===== ONE SOURCE-DEFINED RPC45 READ ONLY =====
Candidate key: frost_protection_temp address: 24
RPC status: 26 events: (1000015,)
Session close status: 0
SDK shutdown status: 0
FAIL: single-candidate probe returned status 1; no automatic retry.
```

**Kildedokumenteret fejltolkning:**
- `26` betyder `NABTO_FAILED_WITH_JSON_MESSAGE`, altså et SDK-statusresultat med detaljer i JSON. [Officielt C API header](https://github.com/nabto/nabto4-python-wrapper/blob/master/extension/linux64/include/nabto_client_api.h).
- `1000015` betyder `MICROSERVER_NOT_KNOWN`. [Officielle Nabto Micro eventkonstanter](https://github.com/nabto/cordova-plugin-nabto/blob/master/www/nabto-constants.js), [Nabto legacy klientmanual TEN025, appendix 7](https://downloads.nabto.com/assets/docs/TEN025%20Writing%20a%20Nabto%20API%20client%20application.pdf). Det er en **gateway-opslags-/tilgængelighedsfejl**, ikke en verificeret afvisning af **adresse 24**.
- `nabtoOpenSession` lykkedes implicit (ellers havde scriptet afsluttet med `SDK authenticated session failed`), men beviser ikke, at den eksterne gateway var fundet/online. `nabtoRpcInvoke` returnerede fejl, uden brugbar rå sensorværdi; det vides **ikke**, om RPC45 nåede controlleren.
- Nabto-session og SDK lukkede begge med status `0`. Ingen indstillinger blev ændret. Ingen automatisk gentagelse blev sendt.
- **Adresse 24 forbliver `source_only_unverified`.** De fem tidligere verificerede sensorværdier forbliver verificerede fra tidligere særskilte vellykkede runs. Dette er ikke en generel tilbagekaldelse af RPC45's virkemåde.

**Næste sikre diagnose (ingen nye RPC'er):** Operatøren bør lokalt kontrollere, at de indtastede 12 cifre svarer til det **tidligere fungerende remote Nabto-hostnavn/device-id** fra de vellykkede Steam Deck/HAOS-tests, og om Genvex Connect-appen kan nå gatewayen via en **ekstern forbindelse**. Indtastede ID'er, konto/e-mail, fuld fejl-JSON og nøgleadgangskoder må ikke kopieres til GitHub/logs/chat.

Hvis gatewayen fortsat ikke findes, stop uden flere adresseforsøg og undersøg autoriseret enhedsidentitet, online-status, remote-registrering og netværk. En **eventuel** ny enkeltstående RPC17/45-kontrol mod det korrekte kendte hostnavn skal være særskilt valgt/godkendt; ingen automatisk retry, registerscan eller batch på 17 adresser.

**Efterfølgende kodeforbedring:** [Testscriptet](../scripts/probe_optima270_single_source_candidate.py) klassificerer nu `(status=26,event=1000015)` som `GATEWAY_NOT_KNOWN_OR_UNAVAILABLE` uden at udskrive rå JSON. [Regressionstests](../experimental/genvex_remote/test_single_candidate_cli.py) dækker forskellen på gatewayfejl og manglende klient-XML-query. Kodeændringen foretager ingen netværkskald.


## 2B hostnavnssammenligning – offline kodeaudit (2026-11-20)

Efter brugerens bekræftelse på, at Genvex Connect-appen viser aktuelle målinger, blev de tidligere succesfulde scripts sammenholdt med den nye enkelt-sensor-test:

| Kode | Hvordan vælges gateway? | Faktisk format |
| --- | --- | --- |
| [`probe_remote_sensors_phase1.py`](../scripts/probe_remote_sensors_phase1.py) og [`probe_remote_sensors_batch_phase1b.py`](../scripts/probe_remote_sensors_batch_phase1b.py) | Operatøren indtaster fuldt `GENVEX_NABTO_HOST` fra den allerede kendte gateway | Videresendes uændret til `nabto://...` |
| [`sensor_model.remote_hostname()`](../experimental/genvex_remote/sensor_model.py) og [`sdk_snapshot_adapter.py`](../experimental/genvex_remote/sdk_snapshot_adapter.py) | Konstrueres fra et valideret 12-cifret device-ID | `<12-digit-ID>.remote.lscontrol.dk` |
| Første version af [`run_optima270_one_read_from_deck.sh`](../scripts/run_optima270_one_read_from_deck.sh) | Operatøren indtaster kun 12-cifret device-ID; runneren konstruerer hostnavn | Samme suffix som den tidligere verificerede adapter |

**Konklusion:** Hostnavnsformatet er **ikke forskelligt**. Der er ikke fundet nogen dokumenteret kodefejl i suffixet. Det er dog muligt, at det ID, som blev indtastet under det fejlede live-forsøg, ikke var det samme som i den tidligere vellykkede test; dette er **ikke bekræftet**. En fungerende iPhone-app viser, at appens adgangsvej virker, men garanterer ikke, at den særskilte SDK-profil, gatewayidentitet eller remote session virker samtidig.

**Sikker rettelse:** Steam Deck-runneren kræver nu, at operatøren indtaster både device-ID og det **tidligere fungerende fulde Nabto-hostnavn** via skjulte prompts. Den kontrollerer format og præcis overensstemmelse **lokalt før** nøgleadgangskode, Nabto SDK eller RPC. Hvis de ikke matcher, stopper den uden netværk og uden at udskrive nogen af værdierne. Ingen automatisk gentagelse, ingen ny sensor og ingen HAOS-ændring.

**Vigtig begrænsning:** Det er en menneskelig, uafhængig sammenligning med det *tidligere dokumenteret fungerende* hostnavn – ikke en verifikation mod serveren. Operatøren må ikke bare konstruere det samme hostnavn på ny ud fra det samme ubekræftede ID; så mister kontrollen sin værdi. Hvis det tidligere hostnavn ikke kan findes lokalt, skal testen stoppes og den oprindelige succesfulde testkonfiguration gennemgås uden at eksponere device-ID eller credentials.

## Andet live-forsøg – første succesfulde RPC45-læsning af adresse 24 (2026-11-20)

**VERIFICERET ud fra operatørens Steam Deck-output:** Efter opdatering til `fc093a7`, hvor den indtastede 12-cifrede ID blev sammenholdt lokalt med det uafhængigt indtastede, tidligere fungerende Nabto-hostnavn, gav samme isolerede read-only test:

```text
PASS: device ID matches independently entered known working hostname
===== ONE SOURCE-DEFINED RPC45 READ ONLY =====
Candidate key: frost_protection_temp address: 24
RPC status: 0
Raw int16: 0 elapsed_ms: 312
Source-scaled (NOT yet physically verified): -30.0
Result: ONE_CANDIDATE_DECODED
Session close status: 0
SDK shutdown status: 0
PASS: exactly one read-only candidate RPC45 probe completed
```

### Bevisniveau og konsekvens

- **Remote-RPC-læsbarhed: VERIFIED** for `RPC45`, `obj=0`, `address=24`, med præcis én `int16`-værdi, `raw=0`, successtatus 0, observeret RPC-varighed **312 ms**. SDK-session og SDK-shutdown returnerede 0. Dette er et enkelt succesfuldt realforsøg.
- **Skalering: SOURCE**: `(raw - 300)/10` giver matematisk **−30,0 °C**. Det er **ikke** dokumenteret, at dette er en faktisk frostbeskyttelsestemperatur. `raw=0` kan være en ubenyttet/manglende følers standardværdi, en gyldig ekstrem værdi, en variantafhængig registerbetydning eller noget andet; disse muligheder er **hypoteser**, ikke fakta.
- **Home Assistant-entity: IKKE GODKENDT.** Behold adresse 24 uden for det aktive fem-sensor-katalog, `verified_read_plan` og HA-entities, indtil betydning og faktisk hardware/føler er afklaret ved uafhængig autoriseret visning eller dokumentation. Den eksisterende fem-målingers baseline ændres ikke.
- **Tidligere `1000015`:** Efter brugerens uafhængige hostnavnskontrol forsvandt gatewayopslagsfejlen ved den efterfølgende kørsel. En forkert tidligere indtastet identitet er en plausibel forklaring, **ikke bevist**, da gatewayens tilgængelighed også kan have ændret sig mellem forsøgene. Vi må ikke omskrive den tidligere fejl til en bekræftet sensorafvisning.
- **Privatliv:** Intet faktisk device-ID, hostnavn, e-mail, certifikat, privat nøgle, adgangskode eller rå SDK-JSON gemmes her.

**Næste offline skridt:** Undersøg den mulige funktion og rå-nulværdi i den offentlige Optima270-model samt eventuelt producentmateriale. En alternativ live-sensoradresse kræver en ny separat operatørbeslutning; der sendes **ingen automatisk scanning**. Ingen installerede HAOS Apps, fungerende LAN-integration eller legitimationsoplysninger blev ændret.

## App-krydstjek for RPC45 adresse 24 – T8 og T9 (2026-11-20)

**Brugerobserveret:** Den officielle Genvex Connect-app viser **−30,00 °C** for **både T8 og T9**. Vores særskilt godkendte remote RPC45-læsning af `(obj=0,address=24)` gav `raw int16=0`, og den offentlige Optima270-kildeskalering `(raw-300)/10` gav **−30,0 °C**.

**Hvad sammenligningen støtter:** Værdien og den valgte kildeskalering er numerisk **konsistent** med appens viste temperaturer ved denne observation. Der er stadig ikke en verificeret mapping fra **adresse 24 til T8 eller T9**, da **begge** viste samme værdi; det er heller ikke dokumenteret, at målingen er en reel fysisk temperatur frem for en fraværende/ikke aktiv sensor eller en standardværdi.

**Evidensstatus:** `RPC45 address24 read=VERIFIED`; `app numerical agreement=USER_OBSERVED`; `address24 equals T8/T9=OPEN`; `sensor physical validity=OPEN`. Behold adressen uden for det aktive fem-sensor-katalog, standard-read-plan og Home Assistant-entities. Ingen yderligere live-RPC eller sensor-scanning udført.

## Officiel Genvex Connect-app: brugerens skærmbillede (2026-11-20)

**Brugerens dokumentation:** Et iPhone-skærmbillede af Genvex Connect-appens informationsvisning viser følgende værdier og labels. Appen viser **kun T8 og T9 med T-numre**; de øvrige fire temperaturer vises under deres funktionsnavne, så der er **ingen evidens** for en mapping til T1–T7 i denne visning.

| App-label | Observeret værdi | Remote RPC45 / status |
| --- | ---: | --- |
| Supply air | 6.70 °C | Adresse 20, tidligere remote-verificeret; ikke en samtidighedstest |
| Outdoor air | 0.40 °C | Adresse 21, tidligere remote-verificeret |
| Exhaust air | 1.80 °C | Adresse 22, tidligere remote-verificeret |
| Extract air | 7.80 °C | Adresse 23, tidligere remote-verificeret |
| Humidity sensor | 67 % | Adresse 26, tidligere remote-verificeret |
| Bypass | Off | Ikke selvstændigt remote-verificeret som boolsk status |
| Reheat | Off | Ikke selvstændigt remote-verificeret som boolsk status |
| Preheat | Off | Ikke selvstændigt remote-verificeret som boolsk status |
| Supply fan | 60.00 % | Adresse 18 er kun en kildebaseret kandidat |
| Extract fan | 58.00 % | Adresse 19 er kun en kildebaseret kandidat |
| T8 sensor | −30.00 °C | Eksakt adresse ukendt |
| T9 sensor | −30.00 °C | Eksakt adresse ukendt |
| Controller version | 11 | App-observeret; ingen separat remote registermapping verificeret |

**Sammenligning med live-RPC:** Den særskilt verificerede RPC45-adresse 24 gav `raw=0`, kildeskaleret til `−30.0 °C`, som numerisk matcher **begge** T8/T9-appværdier. Der er ingen basis for at identificere adressen entydigt som den ene føler. `−30.0 °C` kan være en sentinel/ikke-tilsluttet føler, men det er **ikke bevist**. Målinger fra tidligere fem-adresse RPC45-tests og dette appskærmbillede er ikke dokumenteret som samtidige, så de er kun semantiske/omtrentlige referencepunkter, ikke præcise punkt-for-punkt-krydstjek.

**Plan:** Behold fem aktive verificerede datapunkter. Adresse 24 er remote-læsbar, men semantisk uafklaret. Kandidaterne 18/19 og øvrige status-/temperaturadresser er fortsat source-only, indtil særskilt godkendte live-aflæsninger og uafhængig sammenligning foreligger. Ingen installerede HAOS Apps eller LAN-integrationen ændres.

## Forberedt: samlet RPC45-batch af alle 12 kildebaserede kandidater (2026-11-20)

Brugeren har udtrykkeligt bedt om at spare tid ved at læse alle resterende kandidatadresser **i ét kald**. Derfor er der lavet et nyt, isoleret værktøj, uden ændringer af installerede HAOS Apps eller eksisterende LAN-integration:

- [`probe_optima270_all_source_candidates_batch.py`](../scripts/probe_optima270_all_source_candidates_batch.py): Default **offline**, fast liste af præcis 12 adresser fra `optima270_source_only.py`, `obj=0`, `trailer=1`, **én** `nabtoRpcInvoke` af read-only `RPC45`. Ingen vilkårlige adresser, scanning, write RPC, retries eller parallelle forespørgsler.
- [`run_optima270_all_candidates_batch_from_deck.sh`](../scripts/run_optima270_all_candidates_batch_from_deck.sh): Steam Deck-launcher med offline preflight, skjult indtastning af e-mail, device-ID, det **tidligere fungerende** fulde Nabto-hostnavn og krypteret nøgles passphrase. Lokalt ID/host-match før SDK/netværk. Hard timeout 90 sekunder; privat midlertidig profil og best-effort oprydning.
- [`test_twelve_candidate_batch.py`](../experimental/genvex_remote/test_twelve_candidate_batch.py): offline-regressioner for præcis 12 elementer, ingen vilkårlig adresse, godkendelseskrav, fail-closed svarvalidering, read-only XML og Bash preflight.

**Fastsat rækkefølge:** `24,18,19,35,36,41,42,53,40,114,115,50` (rækkefølgen i kildekataloget). Der kræves præcis **12** `int16`-svar, alle type-/intervalvaliderede, før nogen værdi udskrives. Svarene knyttes kun til adresser efter position, da responsformatet ikke medsender adresser. Hvis gatewayen afviser en kandidat eller hele batchen, stopper testen uden at udpege en bestemt adresse eller forsøge fallback. Svarværdier er kun **source-scaled**, ikke fysisk validerede.

**Kørsel (først offline):**

```sh
bash scripts/run_optima270_all_candidates_batch_from_deck.sh --preflight
```

**Kun efter operatørens særskilte accept af præcis ét live read-only 12-item batchkald:**

```sh
bash scripts/run_optima270_all_candidates_batch_from_deck.sh --execute-live
```

**Status:** Koden er forberedt og tests er offline-only. **Ingen 12-adresse live-batch er kørt eller remote-verificeret.** De 12 kandidater er ikke tilføjet til det aktive HA-katalog. App-reference: Supply fan **60 %**, Extract fan **58 %**, bypass/reheat/preheat **Off**, T8/T9 **−30 °C** (brugerens screenshot). Appværdier og en senere batch skal vurderes med hensyn til tidsforskydning og mulige sensor-sentinels.

## Steam Deck: enklere prompts og seneste batchfejl (2026-11-20)

**Operatørens seneste live-forsøg:** En samlet, særskilt godkendt 12-adresse RPC45-batch (`24,18,19,35,36,41,42,53,40,114,115,50`) returnerede `RPC status=26`, `event=1000015`, klassificeret som `GATEWAY_NOT_KNOWN_OR_UNAVAILABLE`. Session close og SDK shutdown var begge 0. **Ingen af de 12 målinger blev afkodet i dette forsøg**; den tidligere vellykkede enkeltlæsning af adresse 24 står fortsat ved magt. Fejlen viser ikke, at 12-element-batchen er afvist på grund af batchstørrelse eller en bestemt adresse.

**Efter brugerens ønske** er både [12-kandidat-launcheren](../scripts/run_optima270_all_candidates_batch_from_deck.sh) og [én-kandidat-launcheren](../scripts/run_optima270_one_read_from_deck.sh) ændret således:

- E-mail-identitet og 12-cifret device-ID indtastes **synligt** via Bash `read -r -p`; tidligere fuldt remote-hostnavn bliver **ikke længere spurgt om**.
- `GENVEX_NABTO_HOST` dannes fra det indtastede validerede device-ID som `<12 digits>.remote.lscontrol.dk`. Den tidligere ekstra uafhængige hostkontrol er fjernet efter udtrykkeligt brugerønske; et forkert indtastet device-ID kan derfor igen give Nabto-event 1000015. Device-ID valideres fortsat mod præcis 12 ASCII-cifre inden SDK-kald.
- **Kun den krypterede nøgles passphrase** indtastes skjult (`read -r -s -p`) og sendes via stdin, ikke via argv eller miljøvariabel. Programmets egne statuslinjer logger fortsat hverken identitet, device-ID, hostnavn eller nøgle.
- Default `--preflight` er fortsat offline. Live-tilstand har fortsat højst ét read-only RPC45-kald, 90 sekunders timeout, private midlertidige profiler og ingen automatisk gentagelse.

**Privatliv:** Fordi e-mail og device-ID nu er synlige, kan de fremgå af terminaloptagelser/skærmbilleder. Fjern disse oplysninger inden deling af logs. Ingen installerede HAOS Apps eller LAN-integration er ændret.


## Live-verifikation: alle 12 kildebaserede kandidater i én batch (2026-11-20)

**VERIFICERET i brugerens Steam Deck-terminaloutput** efter checkout af `52f6b9a`: Præcis én autentificeret, read-only `RPC45`-forespørgsel med tolv datapunkter i kildens faste rækkefølge `24,18,19,35,36,41,42,53,40,114,115,50` gav `RPC status=0` på **358 ms**, præcis **12 signede int16-værdier**, `Result: TWELVE_CANDIDATES_DECODED_SOURCE_ONLY`, og `Session close status=0` / `SDK shutdown status=0`. Testen var én session og én forespørgsel; ingen skrive-RPC, registerscanning eller automatisk retry.

| Adresse | Kildebetegnelse | Rå int16 | Kildeskaleret / tentativ tolkning | Krydstjek og begrænsning |
| ---: | --- | ---: | --- | --- |
| 24 | `frost_protection_temp` | 0 | −30,0 °C | Matcher numerisk appens både T8 og T9, men eksakt føleridentitet og faktisk tilslutning ukendt |
| 18 | `fan_duty_supply` | 6000 | 60,0 % | **Konsistent** med Genvex Connect's tidligere viste Supply fan 60,00 % |
| 19 | `fan_duty_extract` | 5800 | 58,0 % | **Konsistent** med appens tidligere Extract fan 58,00 % |
| 35 | `fan_rpm_supply` | 2432 | 2432 rpm (kildeenhed) | Ikke uafhængigt målt/verificeret, plausibelt |
| 36 | `fan_rpm_extract` | 2268 | 2268 rpm (kildeenhed) | Ikke uafhængigt målt/verificeret, plausibelt |
| 41 | `preheat_pwm` | 0 | 0,0 (rå/100) | Konsistent med Preheat Off, men fysisk hardware/fortolkning uafklaret |
| 42 | `reheat_pwm` | 0 | 0,0 (rå/100) | Konsistent med Reheat Off, men fysisk hardware/fortolkning uafklaret. Registeradresse 42 er ikke RPC42 |
| 53 | `bypass_active_raw` | 0 | 0 | Konsistent med Bypass Off, men boolsk status/aktiveringslogik ikke dynamisk verificeret |
| 40 | `bypass_analog_raw` | 0 | 0 | Analog position/skala ukendt |
| 114 | `alarm_word_1_raw` | 0 | 0 | Rå bitfelt; ingen alarmstatus/bevis for alarmløs tilstand udledt |
| 115 | `alarm_word_2_raw` | 0 | 0 | Rå bitfelt; ingen alarmstatus/bevis for alarmløs tilstand udledt |
| 50 | `rotor_rpm` | 10 | 10 (kildens rpm-enhed) | Rotorhardware/semantik ukendt; må ikke antages at være fysisk 10 rpm |

**Vigtig sondring:** `12/12 RPC-læsbarhed` og `batch-format verificeret` betyder **ikke**, at alle 12 målinger nu har verificeret fysiske enheder, følerspecifik T8/T9-mapping eller er klar som Home Assistant-entities. Især for `raw=0` kan en inaktiv/ikke-tilsluttet funktion ikke skelnes fra en gyldig nulmåling. `fan_duty_supply/extract` er de tydeligste nye HA-kandidater, fordi skala og etiketter matcher officielle appobservationer; appskærmbilledet var **ikke samtidigt** med batchen. RPM, analog bypass, PWM, alarmbitfelter og rotormåling kræver mere afklaring.

**Status efter forsøget:** 5 tidligere aktive, dokumenterede remote RPC45-målinger + 12 nye **remote-læsbare** kildeposter, i alt **17 kildebaserede adresser med påvist fjernlæsbarhed**. `capability_catalog.py`, `verified_read_plan.py`, sensor-snapshot v1 og HA-entities forbliver **uændrede** (fortsat præcis 5). Der er ikke udført installering, polling eller ændring af HAOS Apps eller LAN-integration.

**Privatliv:** Brugerens originale terminaludskrift indeholdt synligt indtastede identitets- og gatewayoplysninger. Dette dokument og eventuelle kodetestdata kopierer **ingen** af disse værdier. Nøglen/passphrase var skjult. Anbefal kun fremtidige anonymiserede terminaludskrifter.


## Næste udviklingstrin: isoleret snapshot v2-udkast (2026-11-20)

På baggrund af den succesfulde 12/12-batch er der oprettet en **offline-only** skitse til et fremtidigt versioneret snapshotformat: [`snapshot_v2_draft.py`](../experimental/genvex_remote/snapshot_v2_draft.py) og [offline-tests](../experimental/genvex_remote/test_snapshot_v2_draft.py).

- **Eksisterende v1 uændret:** Alle fem hidtidige temperatur-/fugtighedsværdier kræves fortsat samlet, friske og fra korrekt enhed. `snapshot_contract.py`, runtime-API, installerede HAOS Apps og LAN-integration ændres ikke.
- **Fremtidigt v2-envelope:** `schema_version=2` med de fem v1-værdier i `values` og et særskilt `optional.fan_duty`-objekt, der enten er tomt (ikke tilgængeligt) eller indeholder **begge** `fan_duty_supply` og `fan_duty_extract`. Ingen opdigtede 0-værdier ved fejlet valgfri aflæsning.
- **Kilde- og appunderstøttet skalering:** Rå `6000/5800` til `60.0/58.0 %`; kun præcis to gyldige heltal fra 0 til 10000 accepteres i den valgfrie dekoder. Dette er et designudkast, **ikke** tilladelse til nye live-kald.
- **Fejlisolering:** Ugyldige valgfrie ventilatorværdier resulterer i tom `fan_duty`-sektion; ugyldig/stale v1-baseline afvises stadig helt. V2 er **ikke** bagudkompatibelt ved at sende v2 direkte til en v1-klient: separat endpoint/versionforhandling kræves før deployment.
- **Afventer:** Separat autoriseret runtime-plan, HA entity-design, tilgængelighedspolitik og vurdering af de øvrige 10 nye læsbare adresser. Ingen ekstra adresse eller live-aflæsning aktiveret.

Dette er kun kode- og kontraktforberedelse, ingen ændring af brugerens eksisterende Home Assistant.


## Offline HA-visning af snapshot v2 (2026-11-20)

Efter den verificerede batchtest og det isolerede v2-kontraktudkast er der tilføjet en **ren Python-projektion** af kommende sensor-entities: [`ha_v2_projection.py`](../experimental/genvex_remote/ha_v2_projection.py) med [`test_ha_v2_projection.py`](../experimental/genvex_remote/test_ha_v2_projection.py).

- Projektionen modtager kun en allerede valideret v2-snapshot (ingen Nabto SDK, HTTP, HA Core eller device-kontrol). `parse_v2` kræver friskhed, korrekt device-ID, fuldt v1-sæt og validerer den valgfrie fan-parring.
- Returnerer stabil rækkefølge på **7 sensorkandidater**: de fem allerede eksisterende med **samme semantiske keys og unique-ID mønster** (`<device_id>_<key>`) plus `fan_duty_supply` og `fan_duty_extract`. Sidstnævnte har `%` som enhed og `measurement` som state class; ingen antagelse om særlig Home Assistant device class.
- Hvis begge ventilatoraflæsninger er gyldige, vises numerisk procent (inklusive **gyldig 0 %**). Hvis de valgfrie data mangler eller afvises, er begge **unavailable med `value=None`**, mens de fem basale sensorer er tilgængelige. Der skabes aldrig falske 0 %-målinger ved fejl.
- Der produceres **ingen** RPM-, rotor-, bypass-, PWM-, temperaturføler-T8/T9- eller alarm-entities fra endnu uafklarede kandidatmålinger.
- **Ikke installerbart:** Den faktiske `experimental/home_assistant/custom_components/genvex_remote`-integration og dens v1-snapshot-parser, den eksisterende runtime `/v1/snapshot` og installerede HAOS Apps er uændrede. Den nye projektion er et kontraktbevis, ikke live-dataindsamling eller deployment.

**Afventer før brug i HA:** Afklaring af hvordan runtime læser og tidsstempler både de fem basismålinger og de to valgfrie ventilatorer, versioneret separat v2-API, autentificeret IPC-transport, entity-tilgængelighed og test i isoleret HAOS-miljø. Ingen nye live-kald blev udført i dette udviklingstrin.


## Opt-in isoleret v2 HTTP-endpoint: offline prototype (2026-11-20)

For at afprøve versionering uden at ændre nogen installeret eller bundlet HAOS-runtime er der oprettet [`snapshot_api_v2.py`](../experimental/genvex_remote/snapshot_api_v2.py), en **separat loopback-only** [`polling_http_server_v2_draft.py`](../experimental/genvex_remote/polling_http_server_v2_draft.py) og [`test_snapshot_v2_http.py`](../experimental/genvex_remote/test_snapshot_v2_http.py).

- **Eksisterende v1 uændret:** `experimental/genvex_remote/polling_http_server.py` er bevidst genskabt nøjagtigt fra `genvex-nabto-remote/runtime/polling_http_server.py`. HAOS App-packagings integritetstest kræver byte-for-byte paritet. Derfor er v2 **IKKE** en valgfri parameter i den eksisterende server og er ikke tilgængelig i den installerede eller pakkede HAOS-runtime. `GET /v1/snapshot` forbliver uændret.
- **Kun separat offline-server:** `ExperimentalV2HTTPServer` oprettes kun eksplicit i tests, kan **kun** bindes til `127.0.0.1`, og tilbyder `GET /v1/snapshot` og `GET /v2/snapshot` på samme lokale testport fra injicerede, syntetiske providers. Den opstarter intet ved import og kræver ingen SDK, secrets eller HA Core.
- **Sikkerhed:** Bearer-token og rute valideres før providers kaldes. Ingen andre HTTP-metoder eller request body tillades. Forkert/stale baseline, wrong-device og ødelagt v2 returnerer en redigeret 503-fejl uden rå data. V2-genopbygning indeholder kun de allowlistede, validerede felter.
- **Syntetiske tests:** De to servere kan sammenlignes på localhost: v1-produktionstypen eksponerer ikke v2 (404), mens den særskilte v2-testserver kan levere begge formater. Testdækning omfatter token, fejlede valgfrie ventilatorer (unavailable i stedet for opfundet 0 %), ægte 0 %, ugyldig device-ID og forældet snapshot.
- **Begrænsning:** Live SDK-adapteren udsender fortsat kun **fem v1-værdier**. Den injicerede v2-provider er en mock. Der er endnu ingen live syv-sensor polling, ingen tidsmæssig kobling mellem fan/baseline, ingen v2-integration i HA Core og ingen installation. Fremtidig integration må sikre at en valgt fanværdi ikke genbruges fra en tidligere poll under nyt tidsstempel.

**CI-fund under udvikling:** Første implementeringsforsøg ændrede `experimental/genvex_remote/polling_http_server.py` uden at ændre den bundlet appkopi; den etablerede `remote-app-offline`-kontrol afviste korrekt forskellen. Den eksisterende v1-server blev derfor **gendannet identisk**, og v2-testserveren blev flyttet til separat prototype. Dette var en offline CI-fejl, ikke en Nabto-, enheds- eller HAOS-installationsfejl.


## Offline RPC45-plan med syv adresser og ét måletidspunkt (2026-11-20)

Der er nu en separat, **inert** [`seven_read_plan_v2_draft.py`](../experimental/genvex_remote/seven_read_plan_v2_draft.py) med [`test_seven_read_plan_v2_draft.py`](../experimental/genvex_remote/test_seven_read_plan_v2_draft.py). Det er en forberedelse til fremtidig **enkeltkalds-/enkeltmåletidspunkt-strategi**, ikke en live SDK-adapter.

- Den præcise, faste read-only RPC45-liste er `[(0,20),(0,21),(0,22),(0,23),(0,26),(0,18),(0,19)]`, i den rækkefølge. Ingen scanning, write RPC, oprettet Nabto-session eller nye credentials.
- Det syntetiske **komplette syv-elementers** svar dekodes til et v2-envelope med ét `timestamp_utc`, fem obligatoriske basalværdier og to valgfri fanprocenter, og valideres af den eksisterende v2-kontrakt. Ugyldig baseline, ufuldstændigt batch eller ugyldige int16-typer giver fejl for hele snapshot. Fysisk usandsynlige, men korrekt kodede ventilatorråværdier resulterer i et tomt `optional.fan_duty`-par uden falske 0 %.
- Ved et fremtidigt **enkelt read-only RPC45-kald med alle syv adresser** vil råværdierne være fra én forespørgsel, hvilket er mere sammenhængende end to adskilte polling-kald. Det samlede syv-adresse batch er dog **endnu ikke live-testet**: tidligere 5-adresse og 12-adresse batch er selvstændigt verificeret. Én samlet RPC-fejl vil gøre alle syv utilgængelige; den valgfrie felt-degradering kan kun bruges, når hele svaret er vellykket og komplet.
- Den rigtige `SDKSnapshotAdapter`, `SnapshotState`, `PollingService`, `polling_runtime.py` og HA-klient er fortsat v1-only. Den nye plan bruges hverken i den pakkede HAOS App, i en installeret integration eller i tests med rigtig gateway.

**Næste nødvendige milepæl** er en isoleret, udtrykkeligt godkendt read-only live-test af præcis syv-adresse-batchen, efterfulgt af udvikling af en separat v2-producer, som faktisk kan danne en frisk, atomisk snapshot fra en valideret SDK-respons. Der er ikke foretaget live-kald i denne kodeændring.
