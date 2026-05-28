# IaaS Italia — Datacenter e Status Feed

Censimento dei principali datacenter italiani e provider IaaS con endpoint di monitoring.
Fonte primaria machine-readable: `iaas-source.md` → elaborata da `iaas_gen.py`.

---

## Provider per Regione

| Provider | Sede / DC | Tier | Tipo | Status feed |
|---|---|---|---|---|
| **Aruba Cloud** | Arezzo (IT-AR), Ponte San Pietro BG (IT-BG) | III+ | statuspage | `https://status.cloud.aruba.it/api/v2/summary.json` |
| **Seeweb** | Milano (Caldera Park), Roma | III | statuspage | `https://status.seeweb.it/api/v2/summary.json` |
| **Irideos** | Milano, Roma, Bologna | III+ | html | `https://www.irideos.it/stato-servizi/` |
| **Noovle (TIM)** | Roma, Milano, Napoli | III | html | `https://noovle.com/it/supporto/stato-servizi/` |
| **Fastweb** | Milano (Caldera Park), Roma | III | html | `https://supporto.fastweb.it/en/uptime` |
| **CDLAN** | Milano (Avalon DC) | III | html | `https://cdlan.it/noc/` |
| **Equinix ML** | Milano (ML1/ML2/ML3) | IV | statuspage | `https://www.equinixstatus.com/api/v2/summary.json` |
| **Digital Realty MIL** | Milano | III+ | statuspage | `https://digitalrealtycloud.statuspage.io/api/v2/summary.json` |
| **Data4 Milano** | Cornaredo (MI) | III+ | statuspage | `https://status.data4group.com/api/v2/summary.json` |
| **Supernap Italia** | Siziano (PV) | IV | html | `https://supernap.it/it/operations/` |
| **BT Italia / Colt** | Milano, Roma | III | html | `https://www.colt.net/network-status/` |
| **OVHcloud (EU)** | Gravelines/Roubaix | III | statuspage | `https://status.ovhcloud.com/api/v2/summary.json` |

---

## Internet Exchange Points (IXP)

| IXP | Città | ASN | Looking Glass |
|---|---|---|---|
| MIX | Milano | AS61968 | `https://www.mix-it.net/looking-glass/` |
| NAMEX | Roma | AS137705 | `https://www.namex.it/looking-glass/` |
| TOP-IX | Torino | AS3302 | `https://www.top-ix.org/it/looking-glass/` |
| VSIX | Vicenza | AS49367 | `https://vsix.eu/` |

---

## Certificazioni Comuni

- **Tier III / III+**: ridondanza N+1, uptime target 99.982%
- **Tier IV**: fault-tolerant, uptime target 99.995%
- **ISO 27001**: gestione sicurezza informazioni
- **ISO 22301**: business continuity
- **SOC 2 Type II**: audit sicurezza indipendente

---

## Note Tecniche

- Provider `statuspage`: espongono `/api/v2/summary.json` (Atlassian Statuspage) — leggibili da `cloud_status.py`
- Provider `html`: nessun endpoint machine-readable; monitoraggio possibile solo via HTTP HEAD + regex
- Provider `rss`: alcune NOC pubblicano feed RSS per incident/maintenance
- Aggiornare `iaas-source.md` e rigenerare con `python iaas_gen.py` per propagare modifiche a `config.yaml`
