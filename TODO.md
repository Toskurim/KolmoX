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
⚠️ **Non è bit-exact.** Testato sugli stessi casi limite di
`ColumnarTextEngine`, fallisce 4 casi su 6:

| Caso | Esito |
|---|---|
| CSV normale | OK |
| CRLF | OK |
| senza newline finale | **FALLITO** |
| righe vuote in mezzo | **FALLITO** |
| righe irregolari (ragged) | **FALLITO** |
| byte non-UTF8 | **FALLITO** |

La causa è `errors="replace"` in decodifica, che distrugge i byte non-UTF8 in
modo irreversibile, più la ricostruzione dei newline "a indovinare".

**Non è orfano — è peggio: `src/kolmox/core/chunker.py` lo usa** (righe 29-34,
84). Va quindi verificato se il percorso chunked può corrompere dati su input
non-UTF8 o con righe irregolari. **Questa è la voce a priorità più alta della
lista**, perché è l'unica che può produrre output sbagliato invece che
semplicemente mancare un'ottimizzazione.

**Da fare:** riprodurre il problema attraverso `chunker.py`, poi migrare a
`ColumnarTextEngine` (che è bit-exact per costruzione) oppure ritirarlo.
I due nomi quasi identici sono di per sé una trappola: vanno unificati.

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

## VideoEngine: sostituire l'XOR con un delta aritmetico

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

**Perché non è già stato fatto:** cambia il formato del payload prodotto da
`VideoEngine`, quindi i container esistenti con `domain_id=9` non sarebbero
più leggibili. Va gestito come cambio di formato — o con un flag di versione
nell'header `KMXV1`, che ha già un campo versione inutilizzato nel container
esterno KMX2.

**Guadagno atteso:** la riga video su gameplay reale passerebbe da +25.14% a
circa +38%.

## Altri difetti noti

- **`getattr(self, 'allow_code_execution', True)`** in `pipeline.py:75` e `:125`
  è **fail-open**: se l'attributo manca, `exec()` viene permesso. Oggi è
  innocuo perché `__init__` lo imposta sempre, ma il default sicuro è `False`.
- **`VideoEngine.decompress_sequence` ignora il parametro `channels`** e assume
  sempre 3. Con RGBA (channels=4) userebbe la dimensione frame sbagliata.
  Aggirato in `domain_router.py` rifiutando `channels != 3`, non risolto.
- **`src/kolmox/c_ext/fast_ops.c`** è codice morto con 4 errori che ne
  impedirebbero la compilazione (`PyBytes_ASCHAR`, `PyBytes_FromAndSize`,
  `bqf1.buf`, `0z`). Non è in `setup.py`, quindi non rompe l'installazione.
- **2 test falliscono** (`test_end_to_end.py`, `test_synthesizer.py`): usano
  `compress_with_script` senza `allow_code_execution=True`. Vanno aggiornati al
  nuovo default sicuro.
- **`BaseDomainEngine`** è un ABC i cui metodi astratti non sono implementati da
  nessuna delle classi che lo ereditano (funziona solo perché non vengono mai
  istanziate). Ereditarietà di facciata.

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
