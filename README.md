# TriaC Compiler

Compilatore *end-to-end* per il linguaggio di programmazione imperativo **TriaC**, con emissione di codice intermedio **LLVM IR** e generazione di codice nativo tramite **Clang**.

---

## 1. Descrizione del Progetto

TriaC è un linguaggio di programmazione fortemente tipizzato e *layout-sensitive* (strutturato a rientri/indentazione senza parentesi graffe). Il compilatore implementa una pipeline a 5 stadi:
1. **Analisi Lessicale & Post-Lexing Indenter:** Riconoscimento dei token e iniezione virtuale dei delimitatori di blocco `_INDENT` e `_DEDENT` tramite gestione a stack.
2. **Parsing Sintattico deterministico LALR(1):** Validazione formale della grammatica ed emissione del Concrete Syntax Tree (CST).
3. **AST Transformation (Bottom-Up):** Eliminazione del rumore sintattico e costruzione dell'Abstract Syntax Tree a oggetti.
4. **Analisi Semantica & Type Checking:** Risoluzione degli identificatori su Symbol Table ad albero con scope lessicale, validazione dei tipi e analisi del flusso di controllo (*guaranteed return*).
5. **Generazione Codice LLVM IR & Compilazione Nativa:** Traduzione dell'AST in rappresentazione intermedia LLVM (`.ll`) via `llvmlite` e linking nativo con la libc standard tramite `clang`.

---

## 2. Requisiti di Sistema

* **Sistema Operativo:** macOS, Linux o Windows (WSL raccomandato)
* **Python:** versione 3.10 o superiore
* **Compilatore C/LLVM:** `clang` installato e accessibile nel `PATH` di sistema
  * *macOS:* Fornito da Xcode Command Line Tools (`xcode-select --install`)
  * *Ubuntu/Debian:* `sudo apt-get install clang`
* **Librerie Python:**
  * `lark` (parser generator e motore LALR)
  * `llvmlite` (binding per LLVM IR)

---

## 3. Installazione e Configurazione

1. Clonare il repository o estrarre la cartella di progetto:
  ```bash
   git clone <url-repository>
   cd compiler
   ```

2. Creare un ambiente virtuale isolato (venv):
  ```bash
    python3 -m venv venv
  ```

3. Attivare l'ambiente virtuale:
  ```bash 
    -macOS / Linux:
      source venv/bin/activate
    
    -Windows (PowerShell):
      .\venv\Scripts\Activate.ps1
  ```

4. Installare le dipendenze richieste:
  ```bash
    pip install --upgrade pip
    pip install lark llvmlite
  ```

---

## 4. Struttura del Repository
```text
compiler/
├── grammar.lark                 # Grammatica formale LALR(1) del linguaggio TriaC
├── indenter.py                  # Post-Lexer per la gestione dell'indentazione significativa
├── parser_wrapper.py            # Modulo di interfacciamento con il parser Lark
├── ast_nodes.py                 # Definizione delle classi dei nodi dell'AST
├── ast_transformer.py           # Trasformatore dal CST all'AST ad oggetti
├── semantic.py                  # Symbol Table, Type Checker e Control Flow Analysis
├── codegen.py                   # Generatore di codice LLVM IR (con alloca hoisting e dead-code check)
├── main.py                      # Compiler Driver da riga di comando
├── README.md                    # Specifiche operative di installazione ed esecuzione
├── documentazione_tecnica.md    # Relazione tecnica di architettura e design del compilatore
├── relazione_ia.md              # Report sull'utilizzo degli strumenti di intelligenza artificiale
└── test/
    ├── run_tests.py             # Test Runner automatizzato end-to-end
    ├── casi_validi/             # Suite casi validi (*.tc, *.expected, *.stdin)
    └── casi_errore/             # Suite casi errore (*.tc, *.expected con frammenti)
```
---

## 5. Suite di Test Automatizzata
La suite di test verifica l'intero compilatore in modo deterministico attraverso un unico comando:
  ```bash
  python3 test/run_tests.py
  ```

Meccanismo di Validazione:

- Casi Validi (test/casi_validi/): Per ciascun programma, il runner esegue un controllo a tre livelli:
  - Completamento della pipeline (Parsing -> AST -> Semantica -> LLVM IR);
  - Validazione formale dell'IR: esecuzione di clang -c <file>.ll -o <file>.o verificando che il compilatore LLVM esca con codice 0;
  - Esecuzione binaria: esecuzione dell'eseguibile compilato (con eventuale iniezione dei dati da .stdin) e confronto byte-a-byte con l'output atteso in .expected.

- Casi di Errore (test/casi_errore/): Verifica che programmi non validi vengano respinti tempestivamente sollevando l'eccezione prevista (SemanticError o errore sintattico) e controllando la presenza del messaggio d'errore atteso corredato da riga e colonna.

Il runner si arresta con codice di uscita 1 al primo errore riscontrato e restituisce codice 0 esclusivamente al completamento con successo di tutti i test della suite.

---

## 6. Compilazione ed Esecuzione di Programmi TriaC
Compilazione di un file sorgente

Per compilare un file sorgente .tc in codice nativo tramite il compiler driver main.py:
  ```bash
  python3 main.py percorso/del/file.tc
  ```

La pipeline esegue le 5 fasi, genera il codice intermedio LLVM IR temporaneo, invoca clang per la generazione del binario ed emette l'eseguibile finale nella medesima directory.

Esecuzione del Benchmark Calcolatrice Interattiva (Linee Guida Sez. 4)
In conformità alla Sezione 4 delle Linee Guida, il progetto include un programma completo che implementa un menu interattivo, gestione I/O sia su interi che su double, costrutto ciclico iterativo e scomposizione su funzioni multiple:

```bash
  # Compilazione del benchmark
  python3 main.py test/casi_validi/test_calcolatrice.tc

  # Esecuzione interattiva da console
  ./test/casi_validi/test_calcolatrice
```