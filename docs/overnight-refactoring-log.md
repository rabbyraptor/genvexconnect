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
| 1 | Arkitekturrevision og Single Source of Truth | Afventer opstart |
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
