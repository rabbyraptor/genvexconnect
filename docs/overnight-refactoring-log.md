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
| 2 | Gennemgribende refaktorering | Afventer |
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
