# Overnight refactoring – arbejdslog

**Repository:** `rabbyraptor/genvexconnect`  
**Arbejdsbranch:** `overnight-refactoring`  
**Udgangspunkt:** `e0f2f46214a0561515f7bb4fda5841e481b3abbe` (DEV9.1, 2026-11-23)  
**Mål:** Strukturforbedringer uden funktionelle regressioner eller ændringer på kørende HAOS.

## Baseline – gældende funktionalitet
- Genvex Remote HAOS-app 0.1.0-dev9 og Home Assistant-integration 0.3.0.
- Vedvarende Nabto Micro SDK-session; RPC45-målinger og råregistre; RPC42 valgt ventilationstrin (0–4).
- 24 tilgængelige sensorer efter v4-aktivering, inklusive sensor for ventilationstrin.
- Officielt verificeret displaymatch for RPC45 18/19 (styringsprocenter), men ingen antagelse om fysisk luftflow/RPM; øvrige usikre fortolkninger skal fortsat markeres som usikre.
- Automatisk parring og snapshot-versioner bevares.
- DEV9 er autoritativ baseline. Ældre DEV-grene og dokumenter er alene historiske.

## Arbejdsregler
1. Før **hver** opgave: læs **hele denne log**, kontrollér branchens aktuelle HEAD og relevante ændringer siden forrige opgave.
2. Kun `overnight-refactoring` ændres. Ingen HAOS-deploy eller live hardware-tests.
3. Ved uafsluttet eller konfliktende tidligere opgave: afslut/afklar denne før næste. Aldrig ignorér et kendt brud.
4. Registrér fund, konkrete filændringer, commits, automatiske/isolered tests, konfliktbeslutninger og restpunkter efter **hver afsluttet opgave**.
5. Slutrapport: opsummering af syv opgaver, praktisk betydning, DEV9-vs-slutbranch diffstat (filer/tilføjede/fjernede linjer/netto), antal commits og testresultater. Opret slutrapport i repo og meddel den til brugeren.
6. Bevar autoritative definitionskilder og undgå dobbelte deklarationer, cirkulære imports og ukontrollerede formatbrud.

## Opgaver
| Nr. | Opgave | Status |
|---|---|---|
| 1 | Arkitekturrevision og Single Source of Truth | **Afsluttet** |
| 2 | Gennemgribende refaktorering | **Afsluttet** |
| 3 | Fælles registerkatalog og datamodel | **Afsluttet** |
| 4 | Konfiguration og versionsstyring | **Afsluttet** |
| 5 | Dokumentation og oprydning | Afventer |
| 6 | Robusthed og fejlhåndtering | Afventer |
| 7 | Release- og installationssystem | Afventer |

## Logposter

### 2026-11-23 – Initialisering
- Oprettet branch direkte fra verificeret DEV9-commit `e0f2f46214a0561515f7bb4fda5841e481b3abbe`, fordi den gamle `remote-nabto-connection`-branch stadig indeholder DEV6 og ikke må være refaktoreringens baseline.
- Logstruktur og afhængighedsregler etableret.
- Ingen ændringer af runtime eller HAOS foretaget.

### 2026-11-23 – Opgave 1 afsluttet: arkitektur og Single Source of Truth
- **Revision:** Gennemgået DEV9 commit-baseret filinventar, App runtime og HA integrationsgrænser, sensor-/registerkonstanter, v4-kæden, release-manifest, eksisterende paritetsværktøj, CI og dokumentationsindgange.
- **Fakta:** 400 filer i baseline; 18/23 App-runtime-moduler er byte-identiske, styrede kopier af `experimental/genvex_remote/`. Ingen grund til blindt at eliminere disse produktionspakke-kopier.
- **Reelle dubletter:** Worker definerer fem RPC45-specifikationer separat fra `sensor_model.py`; HA `const.py`, `raw_interpretation.py` og DEV9-releasescript gentager registrenes adresser/metadata fra runtime-kataloget. HA-side wire validators er derimod bevidst adskilte fra App for at validere tillidsgrænsen.
- **Beslutning:** `docs/overnight-architecture-baseline.md` er autoritativt arkitektur-/ejerskabskort. `sensor_model.py` og `raw_registers_v3.py` forbliver nuværende runtime-authorities, indtil opgave 3 indfører katalog/projektioner; `scripts/check_remote_runtime_parity.py` er fortsat kopisynkroniseringens authority.
- **Kodefiler:** Ingen runtime-/HA-kode ændret i opgave 1. Dokumentationsfil oprettet: `docs/overnight-architecture-baseline.md`.
- **Commit:** `12d29a763c6da9d36f64ccc1ba32beed05a01eea` (arkitekturdokument).
- **Verifikation:** Git tree, blob-SHA-identitet og kildekode gennemgået; **ingen nye automatiserede tests kørt** (dokumentations-/beslutningsopgave).
- **Konsekvens:** Næste opgaver kan rydde op uden at sammenblande runtime-/HA-ansvar eller gentage gamle DEV2/DEV8-statuspåstande.
- **For opgave 2:** Læs dette logafsnit og arkitekturdokumentet; hold spejlede moduler i byte-paritet, og undgå ændringer af RPC42/45-wireformat, entity-ID'er og gældende DEV9 API. Opgave 3 ejer registerkataloget, opgave 4 flags/versioner og opgave 5 den generelle status-dokumentation.

### 2026-11-23 – Opgave 2 i gang: eksekveret strukturel refaktorering (første session)
- **Reelt implementeret (ikke blot planlagt):** v3 og v4 snapshot-cache bruger nu én intern `_build_v1_v3_snapshots`-funktion i `raw_snapshot_state_v3.py`. Begge schema-projektioner er whitelisted, kopierede og stadig selvstændigt valideret; v4-sensorens fan_level-felt, read-only flow og RPC42/RPC45-opkald er uændrede.
- **Kodeændringer:** `experimental/genvex_remote/raw_snapshot_state_v3.py` og `raw_snapshot_state_v4.py`, byte-identiske App-kopier under `genvex-nabto-remote/runtime/`; `experimental/home_assistant/custom_components/genvex_remote/sensor.py` bygger nu identisk DeviceInfo fra én funktion i stedet for fire kopier.
- **Ny offline regressionsdækning:** `genvex-nabto-remote/tests/test_overnight_snapshot_projection.py` verificerer v1/v3/v4 projektionens lighed, 0 ekstra SDK-læsninger, manglende frivillige råværdier, null fan step og at kopier ikke deler mutable tilstand.
- **Commits – refaktorering:** `42de9f418bc856ea9ef2b62c227674333612bab3`, `a8f7f58273136b36ef59082eeed92a9dfc7d5845`, `28ae7784a8cb286ffa69e11f15cc18bf5eba03c3`, `59b9d91b864bd9f9d0d502a5cf6e78f9770b2303`, `e6b614038ac087cd99c400a61c37932c67e0ef9a`, `25ca35748340cd1ca61add6b39a03f7eccbb1026`.
- **CI aktiveret på arbejdsbranch:** eksisterende to offline-workflows inkluderer nu `overnight-refactoring`. Commits `58586fa7e3cf468ad36a185dea06124c0f4ec927`, `ba41d8c1a94fcd0b71b2f5fccd838f3e32ae1034`. Denne målrettede CI-aktivering kommer før den generelle konsolidering i opgave 7.
- **Faktisk testresultat:** Remote HAOS App candidate offline checks **SUCCESS** (Actions run `45092913548`); Remote Nabto offline-only tests, begge dependency-varianter, **SUCCESS** (run `45092916870`). Kilde/App-mirror er desuden verificeret med identiske Git blob-SHA'er for begge ændrede moduler. Formatter og hassfest-checks på refaktoreringens commits er bestået.
- **Separat kendt CI-fejl:** HACS validation fejler på repository-topics og deaktiverede issues (begge repository-metadata uden for denne branch); dette forekom allerede ved opgave 1, og er ikke en kode-/testregression.
- **Status:** Opgave 2 er **ikke** færdig efter første session. Fortsæt næste kørsel med at prioritere yderligere meningsfuld strukturel oprydning, uden at overtage opgave 3's registerkatalog eller opgave 4's options/versioner. Læs hele denne log igen og kontrollér CI-head før næste ændring. Eventuelle nye CI-fejl skal analyseres, før opgaven afsluttes.
- **Konsekvens:** Mindre dubleret konstruktion af v1/v3-wireformat og HA-enhedsmetadata, mens den verificerede DEV9-adfærd og App/source-paritet bevares.

### 2026-11-23 – Opgave 2 afsluttet: aktiv fjernkode refaktoreret
- **Omfang:** DEV9's aktive remote runtime- og HA-kæde, ikke den uafhængige LAN-integration eller historiske draft-filer. Den forrige sessions v1/v3/v4 snapshot-cache-fællesfunktion og HA DeviceInfo-forenkling er bevaret.
- **Yderligere implementering:** Én `_rpc45_url`-funktion bygger nu både baseline- og optional-request i `genvex-nabto-remote/runtime/persistent_rpc45_worker.py`; fælles wire-envelope, samme adresseorden. `coordinator.py` bruger nu `_decode_payload` til v1/v3/v4-projektion med identisk raw-feltnavne og null-stage-håndtering.
- **Nye commits:** `90937d3c52d0392e6418809ebdbf65e24964e2c2` (worker), `028b2ba8aed616ce450e3817255f31e02970cbad` (HA coordinator), `821fe95096740c4a8c60b2578d0f22b3cdec21e6` (wire/scaling regression). Se tidligere session ovenfor for de allerede committede snapshot-/DeviceInfo-filer.
- **Offline test:** RPC45 5+12 request-address-order, JSON request-shape og fem skalerede værdier låst i `genvex-nabto-remote/tests/test_overnight_rpc45_encoding.py`. Allerede eksisterende v1/v3/v4/offline paritetstests bestået på final integreret kode i GitHub Actions App `45094049586` og Remote `45094049587`.
- **Konsekvens:** Fjernet gentaget request-/snapshot-/devicekonstruktion, reduceret risiko for forskellige kodestier ved senere DEV-udvidelser, uden ændring af registrenes faktiske værdier, entity-ID'er eller persistent SDK-session.
- **Afgrænsning:** Ingen bred sletning af historiske DEV-moduler; dette er ansvarligt begrænset til produktionsformet DEV9-kode. Historisk oprydning hører til opgave 5/7.

### 2026-11-23 – Opgave 3 afsluttet: kanonisk registerkatalog
- **One Source of Truth:** `experimental/genvex_remote/register_catalog.py` ejer nu de fem baseline- og 12 optional RPC45-definitioner (navn, adresse, orden, rå/skalering, labels, evidens/noter) og RPC42 read-only stage object=0/address=7/range=0–4. To byte-identiske shipping-kopier ligger i App runtime og HA-integrationen.
- **Konkrete konsumenter:** `sensor_model.py` projicerer fem skalerede specs, `raw_registers_v3.py` projicerer optional nøgle/adresse-orden, worker projicerer sin eksisterende tuple-/queryform, HA `const.py` projicerer entity-definitioner, `raw_interpretation.py` projicerer evidensnoter, og HA `sensor.py` udstiller fan-stage fra kataloget. Ingen af disse kan fremover ændre registrenes adresser uafhængigt af authority.
- **Drift-kontrol:** `scripts/check_remote_runtime_parity.py` check/sync omfatter nu også HA-katalogkopien. `test_overnight_register_catalog.py` fastholder 17 registeradresser, order, evidens og alle 3 kopiers byte-identitet.
- **Væsentlige commits:** `53559b80adf7be9072237e250ef686705db309e3` (canonical), `6660e1c8548820292d815b68b14c861e560afeab` (HA projection), `c97bdfa44294a3319df487d03c9b0417350c3674` (sensor projection), `cde98013cde381dcd136748bc6f3f11741983c74` (optional projection), `f860ce7738ea457f1c68b906f4ffbea0f5e6bdf6` (HA entities), `60e537c0558eb28e6493a70b0098e002536926f4` (evidence), `d5c6aaabb05e0dbf1aa3d797c78163623cd9bf69` (parity), `e7af100b611e4928cb9df2c7f221578034862878` (tests). Øvrige App-mirrors og fan worker/sensor fremgår af git-historikken.
- **Test:** App offline `45094049586` **SUCCESS**, Remote offline med begge cryptography-varianter `45094049587` **SUCCESS** (inklusive katalog- og paritetstests).
- **Konsekvens:** Centraliserede wire-/sensorfakta uden at importere across HA/App HTTP boundary. Usikre fysiske fortolkninger forbliver `source_model_only`; 18/19 UI-match er stadig kun styresignalprocenter, ikke målt airflow/RPM.

### 2026-11-23 – Opgave 4 afsluttet: option-, versions- og releasekontrakter
- **Manifest-ejerskab:** App-version `0.1.0-dev9` læses fra `genvex-nabto-remote/config.yaml` og HA-version `0.3.0` fra HA `manifest.json` af `scripts/package_dev9_combined.py`; RPC45-liste og RPC42 stage i release-manifest genereres fra det kanoniske katalog i stedet for hardcodede 17 adresser.
- **Konfiguration:** `app_bootstrap.APP_DEFAULTS` og `VALID_OPTION_KEYS` samler de eksisterende optional-defaults/keys. `scripts/check_remote_contracts.py` afviser uoverensstemmelser mellem App config.yaml, bootstraps tilladte option-keys/defaults, HA's v3/v4 optionnavne og release-metadata. Begge offline-workflows kører denne gate.
- **Reel fejlrettelse:** `pairing_options.py` gemmer nu `fan_level_v4: true` også ved manuel IPC-token-parring, samtidig med at `raw_registers_v3` implicit aktiveres; automatisk pairing bevarer den hidtidige adfærd. Nye tests dækker begge flows.
- **Commits:** `85f50084879ed43d67fe57dae97a863d026add80` (bootstrap defaults), `3c7da6ff394bfedeb5ab070223c743bbf0def918` (manual v4 fix), `5cd46706c0050b710461e6581aadecf319313318` (flow tests), `033787a9c359dd2b60145fc82244af8f1fbcd109` (contract gate), `db65e12181c90b67abc296bce53526c13ba03ed0` (release syntax correction), `5faf07ad751396b267e9d60f6a1c81b25037c600` (CI path filters), `89e354bfbd01a7bf2d72d29b2eeb5b1b206ec3b8` (architecture update). Se mellemcommits for oprindelig release-refaktor og dens efterfølgende CI-drevne rettelser.
- **CI på `db65e121` efter fejlrettelser:** Remote HAOS App candidate offline checks **SUCCESS** (<https://github.com/rabbyraptor/genvexconnect/actions/runs/45094049586>), Remote Nabto offline-only begge matrix-ben **SUCCESS** (<https://github.com/rabbyraptor/genvexconnect/actions/runs/45094049587>), Formatting **SUCCESS** (`45094049651`), hassfest **SUCCESS** (`45094049592`). Begge workflows inkluderer contract gate og deterministisk DEV9 source/package check.
- **Tidligere røde commits:** Nye release-gates afdækkede en ufuldstændig streng og efterfølgende duplikeret trailing source i pakker-scriptet; begge blev rettet og genkontrolleret med grønne offline-workflows på `db65e121`. Midlertidige røde historiske CI-runs skal ikke forveksles med final CI-state.
- **Kendt uafhængig fejl:** HACS Validate-workflowet fejler på repository-topics og deaktiverede issues; ikke på Python-koden. Dette ligger uden for refaktoreringens branch-skift.
- **Konsekvens:** Fremtidige versions-/registerændringer kan ikke uforvarende give andre packaged metadata, default-flags eller v4-parring, uden at parity/kontraktgates fejler. Ingen HAOS-installation eller live SDK-tests udført.

### Overdragelse til opgave 5
- Læs hele denne log og `docs/overnight-architecture-baseline.md` før ændringer. Opgave 2–4 er afsluttet; **næste uafsluttede opgave er 5 (dokumentationsrevision)**.
- Brug `register_catalog.py` som eneste forfatterskilde til RPC45/RPC42 fakta. Begge deploymentkopier er kontrollerede mirrors. Brug App config.yaml og HA manifest.json som versionskilder. Lad ikke gammel DEV2/DEV8 status i `docs/README.md` eller `docs/STATUS.md` overskrive DEV9 fakta.
- Bevar tidligere status for 24 sensors, automatisk parring og manual-token-valg samt read-only RPC42/RPC45. Hold App/HA schema-validatorer adskilt.
- Opgave 7 må eventuelt konsolidere CI, men må ikke fjerne de nye parity/contract-gates eller ændre manifest-ejede versioner.

### 2026-11-23 – Opgave 3 tillæg: komplet *kendt* Micro Nabto kommando-/modelopslag
- **Brugerkrav:** Kataloget skal dække protokolkommandoer, både læsning af datapunkter og read/write-adressepar for indstillinger, samt være udvideligt til flere controller-modeller. Dette er ikke en genåbning af øvrige afsluttede opgaver.
- **Implementeret:** Den kanoniske `experimental/genvex_remote/register_catalog.py` har nu `MicroCommand` med alle fem *aktuelt kildeidentificerede* RPC-opkoder: 2, 17, 42, 43, 45; `ModelProfile`, `SetpointDefinition` og `InactiveSetpoint`. Optima 270-profilen dækker alle 17 RPC45-adresser, alle 12 aktive RPC42-read/RPC43-write-par, ni udkommenterede setpunktpar og kildebaseret modelidentitetshint. Fremtidige modeller tilføjes under særskilt key i `MODEL_PROFILES`; fysisk understøttelse antages aldrig fra profilen alene.
- **Lookup API:** `get_micro_command`, `get_model`, `get_model_register`, `get_model_setpoint` skelner model, RPC-opkode, objekt, read/write-adresse, datatyper, skalering og evidens. `scripts/lookup_micro_nabto.py` giver offline JSON-opslag via CLI (ingen SDK/netværkskald). Brug `docs/micro-nabto-protocol-library.md` som udvikler-/brugerreference.
- **Evidensgrænse:** RPC42 er kun remote-verificeret ved fan_speed læseadresse 7; andre setpunkter er source-only. RPC43 write-adresser/kilde-Wireformat er dokumentation, ikke remote-verificerede SDK-write-pakker; `write_enabled=False` og `remote_write_verified=False` for alle aktive setpunkter. De 9 udkommenterede adresser kræver eksplicit `include_inactive` ved lookup. Protokollisten er `alle kendte i denne kildebase`, ikke en påstand om vendor-komplet protokol.
- **Authoritative definition / mirrors:** Samme Python-katalog er skrevet identisk i source, App-runtime og HA, med eksisterende parity check for drift. `docs/references/optima270_micro_nabto_setpoint_catalog.json` er kildebevis/krydstjek, ikke en ny uafhængig operativ definition.
- **Commits:** `d40d961a50e8c73597ae41dc16aa09d49c75489f` canonical, `7cad9ef9015f1964c5bb30442f52bbb32ecb9bf4` App mirror, `f2bf8897bf5e4dd777b34714fa4105fc492ea3ae` HA mirror, `8c21dfd03576be56e972c9a825f6ce4b338846e0` source crosscheck tests, `f0137d9837bc5657b83b3908515c5dfc2b1e3fa3` CLI, `1a6b396b4336fa1652f8fee53208cce85db88a00` CLI regression tests, `702ab7665364255840e96ac6d9acd91dbca19d8e` library guide, `89eebeee3fb27dc83c9b82083e13a042cb6d732e` architecture link.
- **Testresultater:** App offline **SUCCESS** run `45095300079`, Remote Nabto offline **SUCCESS** run `45095299962` (363 tests + 143 HA-tests pr. cryptography-matrixben), Formatting **SUCCESS** run `45095300036`, hassfest **SUCCESS** run `45095299971`, alt på kodecommit `1a6b396b`. De nye tests sammenholder alle 12 + 9 setpunkter og fem kommandoer mod kildebevis og kontrollerer read/write-adresseseparation og CLI-opslag. HACS-metadatafejlen er uændret.
- **Praktisk betydning:** Kommandoer kan nu findes uden at lede i historiske dokumenter; fremtidige modelprofiler kan beskrives uden at ændre DEV9's aktive sensortransport. Ingen HAOS-deploy, live-SDK-tests, RPC43-pakker eller hardware-skrivekommandoer udført.
- **Til næste automatiske opgave 5:** Læs denne post og brug `docs/micro-nabto-protocol-library.md` som autoritativ oversigt; adskil fortsat kildebaserede/udkommenterede registre fra fjernverificerede operationer. Fortsæt dokumentationsopgaven, som stadig er første uafsluttede opgave.
