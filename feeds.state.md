# CTI Feeds — Stato lavoro & registro fonti

**Data:** 2026-05-10
**Output:** `feeds.yaml` (12 feed configurati, 3 commentati per espansione futura)
**Scope:** organizzazioni/autorità/eventi cybersecurity Italia + UE per il backend FastAPI CTI.

---

## 1. Stato di avanzamento

| Step | Stato | Note |
|------|-------|------|
| Ricerca fonti per ciascuna voce richiesta | ✅ done | 4 query web parallele × 2 batch |
| Verifica feed RSS ufficiali | ✅ done | ACN, ENISA confermati direttamente |
| Identificazione fallback per RSS dismessi | ✅ done | ENISA → sitemap diff |
| Generazione `feeds.yaml` | ✅ done | 12 feed attivi, raggruppati per tier |
| Definizione strategia ETag / Last-Modified | ✅ done | Conditional GET + state per-feed |
| Validazione endpoint WordPress (`/feed/`) | ⚠️ pending | Probe HEAD al primo poll del worker |
| Implementazione worker poller in `main.py` | ⏭ next | Skeleton sotto in §5 |
| Integrazione cache.py per state per-feed | ⏭ next | Estendere TTLCache con persistenza JSON |

---

## 2. Mappa feed → tier → endpoint

| ID | Voce richiesta | Tier (TTL) | Tipo | URL |
|----|----------------|------------|------|-----|
| `acn_main` | ACN | high (15') | RSS | https://www.acn.gov.it/portale/it/feedrss |
| `csirt_alerts_scrape` | CSIRT Italia | high (15') | Scrape | https://www.acn.gov.it/portale/it/csirt-italia/alert-e-bollettini |
| `enisa_news_sitemap` | ENISA / ECSM | medium (60') | Sitemap | https://www.enisa.europa.eu/sitemap.xml |
| `ecsm_awareness` | ECSM kick-off | low (24h) | Scrape | https://cybersecuritymonth.eu/news |
| `cybersecitalia_news` | CyberSec Italia | medium (60') | RSS | https://www.cybersecitalia.it/feed/ |
| `federprivacy_news` | Privacy Day Italia | medium (60') | RSS | https://www.federprivacy.org/?format=feed&type=rss |
| `aisis_news` | AISIS / e-health Italia | medium (60') | RSS | https://www.aisis.it/feed/ |
| `forumpa_news` | Forum PA | medium (60') | RSS | https://www.forumpa.it/feed/ |
| `cybertech_europe` | Cybertech Europe Roma | low (24h) | Scrape | https://italy.cybertechconference.com/news |
| `itasec_conference` | ACN — Conferenza nazionale | low (24h) | Scrape | https://cybersecnatlab.it/category/itasec/ |
| `himss_europe` | HIMSS Europe / e-Health | low (24h) | RSS | https://www.himss.org/news-center/rss.xml |
| `soiel_security_events` | SmartSec / Net&System Security | low (24h) | Scrape | https://www.soiel.it/eventi/ |

---

## 3. Tutti i link raccolti durante la ricerca

### 3.1 ACN — Agenzia Cybersicurezza Nazionale
- Newsroom: https://www.acn.gov.it/portale/en/comunicazione
- Home (EN): https://www.acn.gov.it/portale/en/
- News & events: https://www.acn.gov.it/portale/en/ncc-italia/notizie-ed-eventi
- **FeedRss ufficiale:** https://www.acn.gov.it/portale/en/feedrss
- Wikipedia: https://en.wikipedia.org/wiki/Agenzia_per_la_Cybersicurezza_Nazionale

### 3.2 CSIRT Italia
- Hub CSIRT: https://www.acn.gov.it/portale/en/csirt-italia
- **Alert e Bollettini:** https://www.acn.gov.it/portale/en/csirt-italia/alert-e-bollettini
- Esempio alert (Cisco): https://www.acn.gov.it/portale/en/w/vulnerabilita-su-prodotti-cisco-al02/210204/csirt-ita-
- Esempio alert (Moodle): https://www.acn.gov.it/portale/en/w/vulnerabilita-in-moodle-al02/230620/csirt-ita-
- Articolo Agenda Digitale (referente CSIRT): https://www.agendadigitale.eu/sicurezza/referente-csirt-chi-e-e-cosa-fa-i-nuovi-obblighi-di-cybersecurity/

### 3.3 ENISA
- Publications: https://www.enisa.europa.eu/publications
- Press office: https://www.enisa.europa.eu/press-office
- News: https://www.enisa.europa.eu/news
- **RSS dismessi (avviso):** https://www.enisa.europa.eu/rss-feeds-discontinued-new-subscription-mechanism-coming-soon
- Pagina RSS legacy: https://www.enisa.europa.eu/rss-feeds
- OPML community feeds: https://github.com/cudeso/OPML-Security-Feeds/blob/master/feedly.opml
- ENISA-Do-It-Yourself toolbox: https://health-isac.org/peek-into-the-enisa-do-it-yourself-toolbox/
- Top 100 Cyber Security RSS: https://rss.feedspot.com/cyber_security_rss_feeds/

### 3.4 ECSM — European Cybersecurity Month
- ENISA topic page: https://www.enisa.europa.eu/topics/cyber-hygiene/european-cybersecurity-month
- Sito ufficiale ECSM: https://cybersecuritymonth.eu/about-ecsm
- Awards page: https://www.enisa.europa.eu/topics/cyber-hygiene/european-cybersecurity-month/european-cybersecurity-month-awards
- Kick-off event: https://www.enisa.europa.eu/events/european-cyber-security-month-ecsm-kick-off-event
- EU Digital Skills & Jobs: https://digital-skills-jobs.europa.eu/en/initiatives/european-initiatives/european-cyber-security-month-ecsm
- Cyberwatching: https://cyberwatching.eu/news-events/news/european-cyber-security-month

### 3.5 Cybertech Europe — Roma
- **Sito ufficiale:** https://italy.cybertechconference.com/it
- About: https://italy.cybertechconference.com/About
- Main themes: https://italy.cybertechconference.com/main_themes
- 10times listing: https://10times.com/cybertech-rome
- Showsbee: https://www.showsbee.com/fairs/Cybertech-Europe.html
- CyberSec360 coverage 2025: https://www.cybersecurity360.it/news/cybertech-europe-2025-a-roma-si-parla-di-ai-resilienza-e-difesa-europea/
- HackerJournal: https://hackerjournal.it/14567/si-terra-a-roma-il-cybertech-europe-2025

### 3.6 Forum PA
- **Sito ufficiale:** https://www.forumpa.it/
- Programma 2026: https://www.forumpa.it/riforma-pa/verso-forum-pa-2026-il-programma-per-una-pa-che-genera-futuro-scopri-gli-scenari-e-iscriviti/
- Incontri ed eventi: https://www.forumpa.it/incontri-ed-eventi/
- Roma Capitale: https://www.comune.roma.it/web/it/notizia/roma-gualtieri-forum-pa-2025.page
- Convenzione EFI: https://efi-italia.it/forumpa2026
- Regione ER sede Roma: https://www.regione.emilia-romagna.it/sederoma/appuntamenti/forum-pa-2026

### 3.7 ACN — Conferenza nazionale cybersicurezza (ITASEC)
- **CINI Cybersec Lab:** https://cybersecnatlab.it/itasec26-decima-edizione-della-conferenza-nazionale-sulla-cybersecurity/
- Pressenza: https://www.pressenza.com/it/2026/02/conferenza-nazionale-cybersicurezza/
- Cybertrends: https://www.cybertrends.it/itasec2026/
- ACN — II Conferenza Cyber Capacity Building: https://www.acn.gov.it/portale/en/w/ii-conferenza-nazionale-dell-ecosistema-italiano-di-cyber-capacity-building
- ACN — Agenda di Ricerca: https://www.acn.gov.it/portale/en/w/presentazione-dell-agenda-di-ricerca-e-innovazione-per-la-cybersicurezza
- ACN — IN CYBER Forum 2026: https://www.acn.gov.it/portale/en/w/in-cyber-forum-2026-porta-la-tua-innovazione-cyber-nel-cuore-dell-europa
- Take The Date: https://takethedate.it/tutti-gli-eventi/Eventi/50575-cybersec2026-la-cybersicurezza-e-sicurezza-nazionale.html
- Agenda Digitale: https://www.agendadigitale.eu/sicurezza/agenda-acn-2026-ricerca-talenti-e-innovazione-per-la-sicurezza-del-paese/

### 3.8 Privacy Day Forum (Federprivacy)
- **Sito ufficiale:** https://www.federprivacy.org/
- Privacy Day Forum 2026: https://www.federprivacy.org/informazione/primo-piano/privacy-day-forum-2026-professionisti-e-manager-d-impresa-chiamati-a-un-cambio-di-paradigma-tra-compliance-gdpr-e-rispetto-della-privacy
- Privacy Day Forum 2025 (recap): https://www.federprivacy.org/attivita/privacy-day-forum-2025-video-slides-e-numeri-dell-evento-annuale-di-federprivacy
- Agenda: https://www.federprivacy.org/agenda
- Tag privacy day: https://www.federprivacy.org/informazione/societa/tag/privacy%20day
- Federprivacy associativo: https://www.federprivacy.it/

### 3.9 HIMSS Europe / e-Health Summit
- **Sito evento:** https://www.himss.org/events-overview/european-health-conference-and-exhibition
- Programma HIMSS26: https://himss1.eventsair.com/himss26-europe/programme
- Press release Copenhagen 2026: https://www.himss.org/news-center/himss-european-health-conference-exhibition-heads-copenhagen-2026/
- World-class voices: https://www.himss.org/news-center/himss26-europe-welcomes-world-class-voices-at-the-forefront-of-healthcare-innovation-to-copenhagen/
- Programme themes: https://www.himss.org/news-center/nine-key-programme-themes-announced-for-the-2026-himss-european-conference-and-exhibition/
- Call for proposals: https://www.himss.org/news-center/call-for-proposals-opens-for-himss26-europe/
- Eventi globali HIMSS: https://www.himss.org/events-overview

### 3.10 AISIS — e-Health Italia
- **Sito ufficiale:** https://www.aisis.it/
- Exposanità: https://www.exposanita.it/portal/en/aisis-associazione-italiana-sistemi-informativi-in-sanita
- LinkedIn: https://it.linkedin.com/company/associazione-italiana-sistemi-informativi-in-sanit%C3%A0
- YouTube: https://www.youtube.com/@aisis5512
- Nuova leadership 2025 (iMille): https://www.imille.com/2025/10/15/nuova-leadership-in-aisis-marco-foracchia-presidente-tra-digitalizzazione-e-sanita/

### 3.11 SmartSec / Net&System Security (eventi tecnici SOC)
- **Soiel — Sicurezza ICT:** https://www.soiel.it/eventi/sicurezza-2023-milano/
- IT & Cybersec Meeting: https://itecybersec.it/
- Expo Security Pescara: https://www.exposecurity.it/
- ItaliaSec Milano 2026: https://italy.cyberseries.io/
- Innovation Cybersecurity Summit: https://www.cybersecitalysummit.it/

### 3.12 CyberSec Italia (testata + evento CyberSEC)
- **Quotidiano:** https://www.cybersecitalia.it/
- CyberSec Italia Events: https://www.cybersecitalia.events/en/home-en/
- CyberSEC2026: https://www.cybersecitalia.events/cybersec2026/en/home-english/
- ICT Security Magazine: https://www.ictsecuritymagazine.com/
- Cybersecurity 360: https://www.cybersecurity360.it/
- Rivista Cybersecurity Trends: https://www.cybertrends.it/
- ZeroUno cyber: https://www.zerounoweb.it/techtarget/searchsecurity/cybersecurity/

---

## 4. Decisioni di design (antirez-style)

1. **Nessun framework di feed-aggregation** (no Celery, no scheduler esterno). Worker = `asyncio.Task` lanciato all'avvio FastAPI tramite `lifespan`.
2. **HTTP conditional GET come primo strumento di throttling.** ETag + `If-None-Match` riducono banda/load del ~95% sui feed maturi.
3. **State per-feed in JSON atomico**, non DB. Un file `<feed_id>.json` in `.cache/feeds/`. Nessun lock: scrittura via `os.replace()`.
4. **Tier discreti (high/medium/low)** invece di TTL arbitrari per ogni feed: 3 valori bastano per coprire tutti i casi reali.
5. **`verified: false`** è un flag esplicito invece di silenziare i feed non probati: il worker fa HEAD al primo poll e flippa il flag.
6. **Negative cache** (`negative_ttl_min`): se un feed dà 5xx ripetuti, non lo si re-tenta per 30'. Evita amplification su outage upstream.
7. **Sitemap diff per ENISA**: pattern affidabile per siti che hanno ucciso gli RSS. `<lastmod>` è ufficiale e standardizzato.

---

## 5. Skeleton worker (riferimento per implementazione)

```python
# In main.py — aggiungere al lifespan
import yaml, asyncio, json, hashlib
from pathlib import Path
from datetime import datetime, timezone

CFG = yaml.safe_load(open("feeds.yaml"))
STATE_DIR = Path(CFG["defaults"]["cache"]["dir"]); STATE_DIR.mkdir(parents=True, exist_ok=True)

async def poll_feed(client, spec):
    sid = STATE_DIR / f"{spec['id']}.json"
    state = json.loads(sid.read_text()) if sid.exists() else {}
    headers = {"User-Agent": CFG["defaults"]["user_agent"]}
    if state.get("etag"):          headers["If-None-Match"] = state["etag"]
    if state.get("last_modified"): headers["If-Modified-Since"] = state["last_modified"]
    try:
        r = await client.get(spec["url"], headers=headers, timeout=CFG["defaults"]["timeout_sec"])
    except Exception as e:
        state["error_count"] = state.get("error_count", 0) + 1
        state["last_error"] = str(e)
    else:
        if r.status_code == 304:
            pass  # not modified
        elif r.status_code == 200:
            state["etag"] = r.headers.get("etag")
            state["last_modified"] = r.headers.get("last-modified")
            new_hash = hashlib.sha256(r.content).hexdigest()
            if new_hash != state.get("last_hash"):
                state["last_hash"] = new_hash
                # parse + dispatch new entries here (rss/sitemap/scrape)
            state["error_count"] = 0
        else:
            state["error_count"] = state.get("error_count", 0) + 1
    state["last_fetch"] = datetime.now(timezone.utc).isoformat()
    tmp = sid.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(sid)

async def feeds_worker(app):
    import httpx
    async with httpx.AsyncClient(follow_redirects=True) as client:
        while True:
            now = datetime.now(timezone.utc).timestamp()
            for spec in CFG["feeds"]:
                if not spec.get("enabled"): continue
                ttl = CFG["tiers"][spec["tier"]]["ttl_min"] * 60
                last = (STATE_DIR / f"{spec['id']}.json")
                if last.exists():
                    s = json.loads(last.read_text())
                    if s.get("last_fetch"):
                        elapsed = now - datetime.fromisoformat(s["last_fetch"]).timestamp()
                        if elapsed < ttl: continue
                await poll_feed(client, spec)
            await asyncio.sleep(60)
```

---

## 6. Prossimi step

1. Probe HEAD su tutti i feed `verified: false` → flippare nel YAML.
2. Aggiungere `/api/feeds` e `/api/feeds/{id}` per esporre stato al frontend.
3. Tab "Feeds" in `static/index.html` con 3 colonne (high/medium/low) + status pill.
4. Estendere `feeds.yaml` con i feed IoC commentati (URLhaus, CISA, OTX) quando si vuole alzare il livello CTI.
