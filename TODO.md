# KolmoX — lavori aperti

Ultimo aggiornamento: 2026-09-03.

## Engine orfani da collegare

Componenti che **esistono nel codice e hanno test che passano**, ma che
`DomainRouter` non raggiunge mai. Sono stati scoperti uno alla volta; questa
lista serve a non riscoprirli da capo.

### `FitsEngine` — `src/kolmox/engines/extended_domains.py:235`
Implementa uno schema a due stadi più ricco di quello attivo: delta modulare
orizzontale per HDU seguito da byte-plane slicing dei residui, con parsing
`astropy` e formato di serializzazione proprio. Coperto da
`tests/test_fits_scientific.py`.

**Perché è orfano:** un `.fits` viene classificato come `FLOAT32` generico e
gestito da `ScientificFloatEngine.transform_f32_byte_plane()`, che fa solo la
trasposizione a 4 piani — nessun delta, nessuna gestione dell'endianness,
nessuna consapevolezza della struttura FITS. Misura reale su JWST 117 MB:
**+16.31%** (1.47x → 1.76x).

**Da fare:** collegarlo al router e misurare se lo stadio di delta batte
davvero la trasposizione generica su dati astronomici. Non è scontato: va
verificato, non assunto. Nota che non emette un container KMX2, quindi va
adattato all'interfaccia `precondition()`/`postcondition()`.

### `MeshCADEngine` — `src/kolmox/core/mesh_cad.py`
Supporta OBJ (`transpose_mesh`), **STL binario** (`transpose_stl_binary`) e
**STEP / ISO 10303-21** (`transpose_step`). Coperto da `tests/test_mesh_cad.py`
e `tests/test_cad_extended.py`.

**Stato OBJ:** misurato sul toro parametrico — bit-exact, **+45.20%**. Il
`ColumnarTextEngine` collegato oggi fa **+63.14%** sullo stesso input, quindi
per l'OBJ il routing attuale è già migliore e non va cambiato.

**Il vero buco sono STL e STEP:** il router non li riconosce affatto.
`detect_domain()` manda `.stl` su `CAD_MESH_OBJ`, che oggi applica il demux
colonnare testuale — inutile su STL binario. STEP non è nemmeno rilevato.
`MeshCADEngine` ha già i detector (`is_stl`, `is_step`) pronti da collegare.

### `TextColumnarEngine` — `src/kolmox/core/text_columnar.py`
⚠️ **Non è bit-exact** (fallisce 4 casi limite su 6: senza newline finale,
righe vuote, righe irregolari, byte non-UTF8; la causa è `errors="replace"`
in decodifica, che distrugge i byte non-UTF8 in modo irreversibile).

**Indagine chiusa il 2026-09-04: nessun rischio per gli utenti.** Il difetto
non era raggiungibile, verificato con test e non per lettura:

1. `chunker.py`, unico consumatore, verificava già il roundtrip prima di
   accettare il percorso colonnare (`if rebuilt == block_data`).
2. `chunker.py` non era nemmeno importabile (dipendeva da `sandbox/runner.py`,
   sintatticamente rotto) e nessun modulo lo importava.
3. Il percorso chunked reale della CLI è `core/chunked.py`, che usa
   `KolmoXPipeline` con verifica CRC32 e non tocca `TextColumnarEngine`.
   Testato bit-exact su 7 casi limite, incluso binario puro.

`chunker.py` e `sandbox/runner.py` sono stati ritirati il 2026-09-04.

**Resta da fare:** ritirare anche `text_columnar.py`. È bloccato da
`benchmarks/real_world_bench.py`, che è l'unico riferimento rimasto.

### `RasterEngine` — `src/kolmox/engines/raster_engine.py`
Collegato al router il 2026-09-03, funzionante e bit-exact. L'encoding è stato
vettorizzato in NumPy (da ~2.6 MB/s a ~95 MB/s).

**Resta lento in decodifica: ~2.4 MB/s.** `unfilter_2d_plane` ha una dipendenza
sequenziale intrinseca — ogni pixel dipende dal vicino già ricostruito — quindi
non è vettorizzabile in NumPy. Serve un'estensione C sullo stesso modello di
`src/kolmox/core/fast_transforms.c`, che è già compilato e collegato.

**Nota:** in questa sessione non c'era un compilatore C disponibile, quindi il
lavoro non è stato nemmeno tentato per non produrre codice non verificabile.

---

## ~~VideoEngine: sostituire l'XOR con un delta aritmetico~~ — FATTO il 2026-09-04

Implementato con versionamento del magic: si scrive `KMXV2` (delta aritmetico),
si legge sia `KMXV2` sia `KMXV1` (XOR legacy). Retrocompatibilità coperta da
`tests/test_video_format_versions.py`, che verifica esplicitamente che un
container KMXV1 resti decomprimibile bit-exact attraverso la pipeline pubblica.

Risultato misurato sullo stesso campione, confronto alla pari:

| | ratio | vs Zstd |
|---|---:|---:|
| KMXV1 XOR (prima) | 2.28x | +25.14% |
| **KMXV2 delta (ora)** | **2.79x** | **+38.87%** |

Miglioramento di 13.73 punti, output 18.34% più piccolo. La riga sintetica è
passata da +43.45% a +56.74%.

**Nota sulla versione:** questo è un cambio di formato del payload. I container
scritti d'ora in poi non sono leggibili da kolmox ≤ 1.2.1. Al prossimo rilascio
serve un bump minore (1.3.0) e una voce nel CHANGELOG.

<details>
<summary>Analisi originale (2026-09-03)</summary>

Misurato su 60 frame reali di gameplay 5120x1440 (2026-09-03), non ipotizzato.

`VideoEngine.compress_sequence` calcola `frame[i] XOR frame[i-1]`. Su dati
continui come il video l'XOR è penalizzante: due valori adiacenti a cavallo di
un bit alto danno un residuo enorme (`127 ^ 128 = 255`) dove la sottrazione
darebbe `1`. Sugli stessi 20 frame:

| Trasformazione | Dimensione | vs Zstd puro |
|---|---:|---:|
| Zstd puro sul raw | 255,469,299 | — |
| XOR temporale (attuale) | 192,039,869 | +24.83% |
| **Delta aritmetico mod 256** | **158,488,817** | **+37.96%** |

Il delta aritmetico è **17.47% più piccolo** dell'XOR, ed è reversibile:
verificato che `np.cumsum(delta, axis=0) % 256` ricostruisce i frame bit-exact.

**Perché non era stato fatto subito:** cambia il formato del payload prodotto
da `VideoEngine`, quindi i container esistenti con `domain_id=9` non sarebbero
più leggibili. Risolto usando il magic stesso come campo versione.

</details>

---

## ~~Benchmark: assorbire il confronto con baseline più forti~~ — FATTO il 2026-09-04

Implementato come flag `--strong-baselines` in `benchmarks/benchmark_extended.py`.
Senza il flag il comportamento è identico a prima, quindi i numeri pubblicati
non cambiano. Con il flag: seconda passata a Zstd livello 19 applicato a
**entrambi i lati** (baseline e compressore interno della pipeline), più Gzip-9
come riferimento. Costo: ~80 secondi contro ~15.

**Esito: il vantaggio strutturale regge ovunque, nessun guadagno si azzera o va
in negativo.** Tre domini migliorano a livello 19 (CAD Mesh +5.09, FITS +4.32,
Video +3.48), otto si riducono. Il caso peggiore è il LiDAR, da +58.79% a
+23.37%: coerente col fatto che quel dataset è una rampa deterministica, che a
livello 19 zstd trova da solo — è una conferma indipendente della cautela già
scritta nella nota ¹ del README.

**Limite metodologico dichiarato:** il confronto con Gzip-9 non isola il valore
del preconditioning, perché la pipeline usa zstd internamente e non è
configurabile su un altro backend. Quella colonna mescola due effetti. La
colonna a livello 19 invece è equa.

**Osservazione sul costo, da valutare:** `KolmoX@19` è sistematicamente più
lento di `Zstd-19` (es. G-Code 1.4 contro 3 MB/s) perché il fallback adattivo
comprime due volte, baseline e candidato. A livello 3 è trascurabile, a
livello 19 raddoppia il lavoro più costoso della pipeline. Vale la pena
valutare se il baseline di confronto possa essere calcolato a un livello più
economico — ma attenzione: cambierebbe la garanzia "mai peggio di Zstd allo
stesso livello" in qualcosa di più debole, quindi non è una modifica gratuita.

<details>
<summary>Analisi originale</summary>

## Benchmark: assorbire il confronto con baseline più forti

`benchmarks/real_world_bench.py` è stato ritirato il 2026-09-04 perché
applicava le trasformazioni a mano fuori dalla pipeline — il pattern che la
nota metodologica del README dichiara non riportabile — e copriva gli stessi
tre domini che `benchmark_extended.py` già misura correttamente.

**Una cosa però la faceva e l'altro no: confrontava contro Gzip livello 9 e
Zstandard livello 19**, non solo Zstd livello 3. È un'informazione che vale la
pena recuperare: sapere se il vantaggio strutturale regge contro un entropy
coder molto più aggressivo è più interessante che batterlo al livello 3.

**Da fare:** aggiungere a `benchmark_extended.py` due colonne baseline
opzionali (Gzip-9, Zstd-19) dietro un flag `--strong-baselines`, per non
rallentare l'esecuzione di default — Zstd-19 su 117 MB di FITS non è gratis.
Ci si aspetta che diversi guadagni si riducano: è esattamente il numero onesto
che serve conoscere.

</details>

---

## Benchmark su dati reali: piano per `benchmark_real.py`

Obiettivo: rendere l'**Evidence Tier 2** del README riproducibile da terzi come
già lo è il Tier 1. Oggi il Tier 2 dichiara dataset di produzione ma nessuno
può rieseguirli.

### Vincoli concordati
- **Tetto di 500 MB complessivi** per tutti i dataset scaricati.
- **Fonti archivistiche con DOI** dove possibile, non link diretti: gli URL
  grezzi marciscono, ed è il punto debole di ogni suite di questo tipo.

### `download_datasets.py`
Scarica in `benchmarks/datasets/` (già in `.gitignore`), con:
- manifest dichiarativo per dataset: URL/DOI, **checksum SHA-256**, licenza,
  dimensione attesa, dominio KolmoX di destinazione
- verifica del checksum dopo il download, ripresa se interrotto, salto di ciò
  che è già presente e valido
- rifiuto di procedere se il totale supererebbe il tetto

### Candidati per dominio

| Dominio | Fonte | Licenza |
|---|---|---|
| FITS | MAST/STScI, osservazioni JWST pubbliche | pubblico dominio |
| LiDAR | USGS 3DEP, oppure AHN3 (NL), `.laz` → `.xyz` | pubblico / CC0 |
| Audio WAV | OpenSLR, oppure Freesound CC0 | CC0 |
| Mesh OBJ/STL | Stanford 3D Scanning Repository; NASA 3D Resources | ricerca / pubblico |
| G-code | repository di stampa 3D con licenza CC | CC |
| Telemetria CSV | UCI ML Repository (sensori industriali) | CC BY |

### `benchmark_real.py`
Stessa struttura di `benchmark_extended.py`, che è il modello da seguire:
misura attraverso `KolmoXPipeline.compress_bytes()`/`decompress_bytes()`,
assert bit-exact su ogni dominio, exit non-zero al primo fallimento, righe
markdown pronte per il README. Salta con un avviso i dataset non scaricati,
così gira anche parzialmente e non obbliga a scaricare tutto.

---

## Altri difetti noti

- **`VideoEngine.decompress_sequence` ignora il parametro `channels`** e assume
  sempre 3. Con RGBA (channels=4) userebbe la dimensione frame sbagliata.
  Aggirato in `domain_router.py` rifiutando `channels != 3`, non risolto.
- **`src/kolmox/c_ext/fast_ops.c`** è codice morto con 4 errori che ne
  impedirebbero la compilazione (`PyBytes_ASCHAR`, `PyBytes_FromAndSize`,
  `bqf1.buf`, `0z`). Non è in `setup.py`, quindi non rompe l'installazione.
- **`BaseDomainEngine`** è un ABC i cui metodi astratti non sono implementati da
  nessuna delle classi che lo ereditano (funziona solo perché non vengono mai
  istanziate). Ereditarietà di facciata.

### Risolti il 2026-09-04
- ~~`getattr(self, 'allow_code_execution', True)` fail-open~~ → ora `False`
  (fail-closed), fissato da `test_script_execution_is_refused_by_default`, che
  verifica anche il caso in cui l'attributo manchi del tutto. Era regredito
  tre volte.
- ~~2 test falliscono~~ → aggiornati con l'opt-in esplicito. **Suite ora 56/56.**

---

## Metodo

Vale per chiunque riprenda questo lavoro, ed è il motivo per cui la maggior
parte delle voci qui sopra esiste:

1. **Non fidarsi di un fix "a leggere il codice"** — scrivere sempre un test che
   lo verifichi (roundtrip bit-exact + confronto dimensione con Zstd puro).
2. **Non scrivere mai numeri di benchmark a mano.** Ricalcolarli eseguendo il
   codice reale, attraverso `KolmoXPipeline.compress_bytes()` /
   `decompress_bytes()` — non chiamando gli engine direttamente, che scavalca
   l'header KMX2 e il fallback competitivo.
3. **Distinguere sempre** ciò che è stato verificato con un test da ciò che è
   solo un'ipotesi di lettura.
4. Gli script del batch 02/09 in `_quarantine_02_09_batch/` **non vanno
   eseguiti**: scrivevano numeri inventati in README e whitepaper. Vedi
   `_quarantine_02_09_batch/AUDIT.md`.
