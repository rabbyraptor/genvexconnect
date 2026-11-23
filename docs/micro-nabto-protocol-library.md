# Micro Nabto – modeludvideligt protokol- og registerbibliotek

**Status:** Kildebaseret opslag + verificerede DEV9-læsninger. **Ikke** en fuldstændig specifikation af den proprietære protokol.  
**Autoritativ kode:** `experimental/genvex_remote/register_catalog.py`  
**Shipping-kopier:** `genvex-nabto-remote/runtime/register_catalog.py` og `experimental/home_assistant/custom_components/genvex_remote/register_catalog.py` (byte-identiske, kontrolleres af parity-gate).  
**Historisk kildebevis:** `docs/references/optima270_micro_nabto_setpoint_catalog.json`; test sammenholder dette med den eksekverbare model.

## Hvad biblioteket indeholder

| Scope | Registrering | Status |
| --- | --- | --- |
| Fælles Micro Nabto-kommandoer | RPC **2** KEEP_ALIVE, **17** PING, **42** SETPOINT_READLIST, **43** SETPOINT_WRITELIST, **45** DATAPOINT_READLIST | Alle aktuelt identificerede opcode-definitioner i projektets kildebevis, **ikke** påstand om alle proprietære RPC-opkoder |
| Optima 270 datapunkter | **17** adresser under RPC45 (5 skalerede + 12 rå diagnostiske) | Læsbarhed af råværdier verificeret; fysisk hardwarefortolkning er kun verificeret for de fem basismålinger |
| Optima 270 aktive setpunkter | **12** par af **RPC42-læseadresse** og **RPC43-skriveadresse**, objekt, interval, skalering, default-read, evidens | Kun RPC42 valgt ventilationstrin (read obj=0/address=7) er fjernverificeret; **ingen RPC43-skrivning er verificeret** |
| Optima 270 inaktive setpunkter | **9** historisk udkommenterede par af adresser med årsag | Ikke aktive; vises kun ved eksplicit opslag |
| Modelvalg | `ModelProfile` med nøgle, kilde, datapunkter, setpunkter og inaktive definitioner | `optima270` registreret; hint for controller-id/modelkode er kun kildeoplysning, ikke automatisk hardwaredetektion |

**Særlig forskel:** RPC42 **læser** setpunktadresse 7 for ventilatortrin, mens en kildebaseret RPC43-**skriveadresse** er 24. Adressen 24 i RPC45 betyder derimod *frostbeskyttelses-råværdi*. Opslag skal derfor altid bruge **model + RPC-opkode + adresse + objekt**.

## Opslag fra terminal (offline)

```bash
python scripts/lookup_micro_nabto.py --commands
python scripts/lookup_micro_nabto.py --models
python scripts/lookup_micro_nabto.py --model optima270 --datapoints
python scripts/lookup_micro_nabto.py --model optima270 --setpoints
python scripts/lookup_micro_nabto.py --model optima270 --inactive

# Læsning af ventilatortrin: RPC42, adresse 7
python scripts/lookup_micro_nabto.py --model optima270 --rpc 42 --address 7

# Kildebaseret skriveadresse til samme indstilling: RPC43, adresse 24.
# Dette viser KUN metadata; ingen skrivekommando sendes.
python scripts/lookup_micro_nabto.py --model optima270 --rpc 43 --address 24

# Rå sensor i sin egen RPC45-adressetabel:
python scripts/lookup_micro_nabto.py --model optima270 --rpc 45 --address 24

# Historisk deaktiveret ventilatorprofil, kun efter eksplicit valg:
python scripts/lookup_micro_nabto.py --model optima270 --rpc 43 --address 30 --include-inactive
```

Alle opslag returnerer JSON. Ingen Nabto SDK, legitimationsoplysninger eller forbindelse til gatewayen er nødvendig.

## Direkte Python API

```python
from register_catalog import (
    get_micro_command, get_model, get_model_register, get_model_setpoint,
)

commands = get_micro_command(42)          # read opcode
model = get_model("optima270")           # typed model profile
fan = get_model_setpoint("optima270", "fan_speed")
read = get_model_register("optima270", 42, 7)
write_metadata = get_model_register("optima270", 43, 24)
sensor = get_model_register("optima270", 45, 20)

assert fan.read_address == 7
assert fan.write_address == 24
assert not write_metadata.write_enabled
assert sensor.key == "supply_air"
```

`SetpointDefinition.display_value(raw)` implementerer kun kildeformlen `(raw + offset) / divisor` og validerer de kildeangivne råværdigrænser. Den udløser ingen netværksaktivitet. Beskrivelsen af RPC43's LAN-pakkeformat er **ikke** det samme som et verificeret SDK XML-interface for fjernskrivning.

## Evidens og sikring mod falske konklusioner

- `remote_verified` gælder **RPC-typen** og dens begrænsede verificerede brug – **ikke** automatisk alle adresser i en kommando.
- Kun `fan_speed` har `remote_read_verified=True` blandt de 12 setpunkter. Alle 12 har `remote_write_verified=False` og `write_enabled=False`.
- RPC45's 18/19 indeholder et UI-sammenholdt styresignal (`raw / 100`), **ikke** målt luftflow eller RPM. Øvrige kandidatbetydninger er kildebaserede.
- RPC17's svar kan indeholde person-/kontorelaterede felter; biblioteket beskriver kun ikke-følsomme svarfelter.
- RPC43 og øvrige kildebaserede opkoder har opslag **uden** transmit-/write-implementering. Kun separat evidens og eksplicit godkendt skrivearkitektur kan ændre dette.

## Sådan tilføjes en ny model

1. Opret en særskilt evidensfil under `docs/references/` med kilde, datatyper, read/write-adresser, objekter, skalering, grænser og verificeringsstatus. Udelad adgangsoplysninger.
2. Tilføj modellens `RPC45Register`-, `SetpointDefinition`- og `InactiveSetpoint`-poster i **den kanoniske** `register_catalog.py`. Registrér dem i `MODEL_PROFILES` under et entydigt model-key. Brug ikke automatisk modelvalg fra et ubekræftet ping-hint.
3. Hvis den nye model bruger nye RPC-opkoder, registrér kildefund i `MICRO_COMMANDS` med tydelig operation/evidens/transportstatus. Skeln altid mellem read/write-adresse og SDK-/LAN-wire-format.
4. Synkronisér shipping-kopier med `python scripts/check_remote_runtime_parity.py --sync`; kontrollér med `--check`.
5. Udvid krydstjek og kør `python -m unittest discover -s experimental/genvex_remote -p 'test_overnight_micro_protocol_catalog.py' -v` samt projektets App/HA-offline gates. Nye modeller får ikke automatisk sensorregistrering eller skrivekapabilitet i HA.

**Aktuel afgrænsning:** Biblioteket er beregnet til katalogopslag og fremtidig modeludvikling. Det eksisterende DEV9 read-only transportlag og installerede 24 sensorer ændres ikke.
