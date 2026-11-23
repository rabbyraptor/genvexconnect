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
| 2 | Gennemgribende refaktorering | **I gang** |
| 3 | Fælles registerkatalog og datamodel | Afventer |
| 4 | Konfiguration og versionsstyring | Afventer |
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
