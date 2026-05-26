# QCompFeed — Bollettino Compliance Cyber & Privacy

**Edizione:** 2026-04-27 · **Frequenza:** quindicinale · **Maintainer:** Referente CSIRT
**Destinatari:** CEO/Board · Manager · Operatori IT/Security · Fornitori esterni · DPO · Personale sanitario
**Sorgente master:** `legalsource.md` · **Feed strutturato:** `qcompfeed.source.yaml`

> Bollettino divulgativo: blending **legal + tech**, taglio operativo, focus **sanità/healthcare**.
> Niente fuffa: cosa cambia, chi è impattato, cosa fare, entro quando, a quale rischio sanzionatorio.

---

## 1. COSA SAPERE IN UN MINUTO

| Macro-tema | Stato 2026-04 | Cosa serve fare |
|------------|---------------|------------------|
| **NIS2 (D.Lgs. 138/2024)** | In attuazione: misure base ACN det. 164179/2025 + tassonomia incidenti feb-2026 | Iscrizione portale ACN, misure base, notifiche 24h/72h |
| **L. 90/2024** | Vigente | Designazione *referente cybersicurezza*, notifica CSIRT su PA + critici |
| **DORA (Reg. UE 2022/2554)** | Applicato dal 17-gen-2025 | ICT Risk Management, registro contratti TPP, test resilienza |
| **AI Act** | Vigente; obblighi alto-rischio fasati 2026-2027 | Inventario sistemi AI, classificazione rischio |
| **EHDS** | Applicato dal 26-mar-2026 | Adeguamenti FSE, interoperabilità, basi giuridiche per dati sanitari |
| **UNI/PdR 174:2025** | Disponibile (download UNI) | Adottare come base ISMS armonizzata ISO 27001 + NIST CSF 2.0 |
| **CRA (Reg. UE 2024/2847)** | Effettivo 11-dic-2027 | Cyber-by-design su prodotti software/hardware con elementi digitali |

---

## 2. PER RUOLO — COSA TI RIGUARDA

### 2.1 CEO / Board / Organo di Gestione

| Obbligo | Fonte | Sanzione max |
|---------|-------|--------------|
| Approvazione misure di gestione del rischio | Art. 23 D.Lgs. 138/2024 | sospensione funzioni dirigenziali (art. 38 c.9-10) |
| Formazione cyber per organi di gestione | Art. 23 c.2 D.Lgs. 138/2024 | concorre alle sanzioni governance |
| Designazione referente cybersicurezza (PA / soggetti L.90) | Art. 8 L. 90/2024 + Linee guida ACN 2025 | interdizione contratti PA |
| Adempimenti DORA (CdA approva strategia ICT-risk) | Art. 5 DORA | fino a €1M/giorno |
| Comunicazione data breach | Art. 33-34 GDPR | fino a €20M / 4% fatturato |
| Adempimenti AI Act (per sistemi alto-rischio) | Art. 26 AI Act | fino a €15M / 3% fatturato |

**Azioni 90 giorni:** approva carta cyber + delibera designazione referente + verifica copertura assicurativa.

### 2.2 Manager / Funzioni di linea

- Validare il Risk Treatment Plan e i relativi KPI.
- Garantire formazione e awareness annuali (cfr. UNI 11941:2024 sui profili).
- Gestire fornitori secondo Circ. ACN 348639/2025 (diversificazione + clausole contrattuali).
- Mantenere il Registro dei trattamenti (template GPDP) e il Registro incidenti.

### 2.3 Operatori IT / Security / SOC / CSIRT interno

- Misure base ACN (det. 164179/2025): hardening, MFA, log retention min. 6 mesi, backup offline.
- Notifica incidenti: **24h pre-notifica → 72h notifica completa → 1 mese report finale**.
- Tassonomia incidenti L.90/2024 (det. ACN feb-2026) per classificazione.
- Hardening: AGID 2020-05-07; TLS: CERT-AGID 2020-11-03; SDLC: AGID 2017-11-21.

### 2.4 Fornitori esterni / Terze parti

- Clausole NIS2/DORA in contratto: SLA, audit right, notifica incidente verso il committente.
- Compliance UNI/PdR 174:2025 o equivalente (ISO 27001 + CSF 2.0) come standard di mercato.
- Per supply chain critica: vedi Linee guida ACN procurement + Circ. 348639/2025.
- Per dispositivi medici / e-health: MDR/IVDR + ISO 81001-5-1 + MDCG 2019-16.

### 2.5 DPO / Privacy

- DPIA su trattamenti ad alto rischio (template EDPB + tool Garante).
- Cooperazione con Referente CSIRT su data breach (single notification flow).
- Aggiornamento Registro trattamenti (modello Garante PMI).
- Specifico sanità: FSE 2.0 (DM 2023-09-07) + Provv. GPDP 55/2019 + EHDS dal 2026-03-26.

### 2.6 Dipendenti / Utenti finali

- Phishing/awareness obbligatori (almeno annuale).
- Procedura segnalazione incidenti: chi chiamare, in quanto tempo, quali canali.
- Uso accettabile asset, password, MFA, BYOD, smart-working.

---

## 3. SETTORE SANITÀ — FOCUS DEDICATO

### 3.1 Quadro normativo applicabile

- **NIS2** (D.Lgs. 138/2024 All. I): ospedali, laboratori, farmaceutici, dispositivi medici critici → **soggetti essenziali** (massimo edittale: max(€10M, 2% fatturato)).
- **GDPR + Codice Privacy** (D.Lgs. 196/2003): trattamento dati particolari art. 9.
- **FSE 2.0** (DM 7-set-2023) + **Provv. Garante 55/2019**.
- **MDR / IVDR** (Reg. UE 2017/745 + 2017/746) per dispositivi medici e diagnostici in vitro.
- **MDCG 2019-16** + **ISO 81001-5-1**: cybersecurity device-side.
- **EHDS** (Reg. UE 2025/327): applicabile **dal 26-marzo-2026**.
- **UNI/PdR 142:2023**: telemedicina (servizi e processi).
- **Det. ACN 164179/2025 — All. 4**: incidenti significativi soggetti essenziali (sanità).

### 3.2 Scadenze chiave 2026 — sanità

| Data | Evento | Riferimento |
|------|--------|-------------|
| **2026-03-26** | EHDS applicabile (interoperabilità FSE, basi giuridiche dati sanitari) | Reg. UE 2025/327 |
| **2026-Q2** | Prima rendicontazione misure base ACN per soggetti essenziali (sanità) | Det. 164179/2025 |
| **2026-Q3** | Cicli audit interno NIS2 (riesame direzione) | Art. 21 NIS2 |
| **2026-Q4** | Aggiornamento DPIA su sistemi FSE 2.0 / telemedicina | GPDP-DPIA |
| **2027-Q1** | Allineamento ISO 81001-5-1 su software medical device | MDR/IVDR |



---

## 4. SANZIONI IN PILLOLE

| Regime | Massimo edittale | Quando scatta |
|--------|------------------|---------------|
| NIS2 — soggetti essenziali | max(**€10M**, 2% fatturato) | misure inadeguate / mancata notifica significativa |
| NIS2 — soggetti importanti | max(**€7M**, 1,4% fatturato) | idem |
| NIS2 — mancata registrazione portale | da €30k a €1,5M | iscrizione tardiva/omessa |
| GDPR — violazioni gravi | max(**€20M**, 4% fatturato) | principi, basi, diritti, transfer extra-UE |
| DORA | fino a **€1M/giorno** | violazione perdurante ICT-risk |
| AI Act — pratiche vietate | max(**€35M**, 7% fatturato) | art. 5 AI Act |
| MDR/IVDR (Italia) | fino a **€150k** + ritiro CE | non conformità dispositivi medici |
| L. 90/2024 | aggravamento pene + interdizione PA | reati informatici / mancata notifica |

> **Pratica:** la sanzione amministrativa è il floor, non il soffitto: aggiungi danno reputazionale, civile (data subjects), e — per organi apicali — penale.

---

## 5. AGENDA — EVENTI E CICLI 2026

### 5.1 Cicli compliance interni (consigliati)

| Cadenza | Attività |
|---------|----------|
| Settimanale | Revisione bollettini CSIRT Italia + ACN news |
| Mensile | Audit interno controllo accessi + log review |
| Trimestrale | Riesame Risk Treatment Plan + KPI cyber |
| Semestrale | Tabletop incident response + DR test |
| Annuale | Riesame della direzione + audit ISMS + revisione DPIA + formazione |

### 5.2 Eventi istituzionali / di settore (preferiti)

| Quando | Evento | Per chi |


> Le date senza giorno sono indicative: vanno ri-confermate sui siti ufficiali. Lo script `update_sources.py` può prelevare/aggiornare automaticamente da feed eventi (`monitoring_feeds.events_*` — estendibile).