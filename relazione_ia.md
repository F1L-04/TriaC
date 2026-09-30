# Relazione sull'Utilizzo dell'Intelligenza Artificiale Generativa

**Progetto:** Compilatore TriaC  
**Corso:** Ingegneria dei Linguaggi di Programmazione (A.A. 2025/26)  
**Studente:** Andrea Filipuzzi

---

## 1. Introduzione e Ruolo dell'IA nel Progetto

Nello sviluppo del compilatore TriaC, gli strumenti di Intelligenza Artificiale basati su Large Language Model (LLM) sono stati impiegati come **supporto metodologico, esploratore di documentazione e assistente alla stesura del codice** (*pair programmer*), con gli obiettivi di:
* Accelerare la stesura del codice strutturale e boilerplate (nodi dell'AST, enumerazioni di tipo e visitatori base).
* Esplorare rapidamente le API specializzate delle librerie `lark` (motore LALR e modulo `indenter`) e `llvmlite` (generazione di LLVM IR).
* Supportare la stesura di casi di test per la validazione sintattica, semantica e di runtime.
* Condurre sessioni di revisione critica del codice (*code review*) e simulazioni di domande per l'esame orale.

L'interazione è stata guidata dal principio del **"Human-in-the-Loop"**: l'IA non è mai stata utilizzata per delegare passivamente le decisioni di progetto, ma come un moltiplicatore di produttività continuamente supervisionato e verificato mediante validazione empirica su compiler driver (`clang`) ed esecuzione nativa.

---

## 2. Metodologia di Interazione e Prompting

La collaborazione con l'IA è stata organizzata secondo un approccio modulare e iterativo allineato alle cinque fasi della pipeline:

1. **Prompting Modulare e Contestualizzato:** Anziché richiedere la generazione dell'intero compilatore in un'unica soluzione (approccio che conduce regolarmente ad allucinazioni architetturali e codice incompatibile), sono stati forniti al modello estratti mirati delle specifiche formali (regole EBNF, regole di tipo o AST), limitando la richiesta a un singolo modulo alla volta.
2. **Chain-of-Thought per la Risoluzione dei Conflitti:** Nella definizione della grammatica `grammar.lark`, il modello è stato stimolato a esplicitare i passaggi di derivazione per eliminare ambiguità, prevenire conflitti *Shift/Reduce* e implementare la corretta associatività a sinistra per gli operatori aritmetici.
3. **Validazione Binarizzata e Indipendente:** Nessuna porzione di codice generato è stata considerata valida prima di aver superato la suite automatica di test, che verifica sia la compilazione pulita con `clang -c` sia l'uguaglianza byte-a-byte dell'output a runtime.

---

## 3. Ambiti di Applicazione nel Progetto

### 3.1. Front-End (Lexer, Parser e AST)
* **Gestione della Layout-Sensitivity:** Supporto nella comprensione dell'interfaccia `lark.indenter.Indenter` per configurare l'iniezione automatica dei token virtuali `_INDENT` e `_DEDENT` e il tracciamento del bilanciamento delle parentesi tonde.
* **Grammatica e Precedenze:** Disambiguazione della cascata gerarchica degli operatori logici, relazionali e aritmetici in formalismo LALR(1).
* **AST Transformer:** Definizione dell'algoritmo di ripiegamento a sinistra (*left-associative folding*) per convertire le liste piatte di token in alberi binari annidati (`BinOpNode`).

### 3.2. Middle-End e Analisi Semantica
* **Scoping Lessicale ad Albero:** Riconoscimento dei limiti di una Symbol Table globale a singolo livello e passaggio a una struttura ad albero con puntatori al genitore (`parent`), fondamentale per supportare lo *shadowing* lecito nei blocchi `if` e `while`.
* **Analisi a Due Passate:** Separazione della raccolta delle firme delle funzioni (`Signature Harvesting`) dalla validazione dei corpi (`Body Validation`), consentendo forward references e ricorsione.
* **Control Flow Analysis:** Progettazione dell'algoritmo ricorsivo `check_all_paths_return` per validare staticamente che ogni percorso di esecuzione termini con un'istruzione `return`.

### 3.3. Back-End e Generazione LLVM IR
* **Modello Memory-Based:** Identificazione del pattern standard basato su allocazione di locazioni di stack (`alloca`), scrittura (`store`) e lettura (`load`), sfruttando il successivo passo `mem2reg` di LLVM per la conversione automatica in registri SSA.
* **Control Flow Graph (CFG):** Costruzione dei Basic Block per diramazioni e cicli (`then`, `else`, `merge`, `while.cond`, `while.body`, `while.end`).
* **Interfacciamento C Runtime:** Configurazione delle dichiarazioni esterne per `printf` e `scanf` e calcolo degli indirizzi delle stringhe di formato mediante l'istruzione `getelementptr`.

---

## 4. Analisi Critica: Limiti dell'IA e Interventi di Debugging Manuale

Durante lo sviluppo sono emerse diverse criticità in cui il codice proposto dall'IA si è rivelato lacunoso, non conforme ai vincoli del compilatore o formalmente errato. Tali situazioni hanno richiesto analisi analitica e riprogettazione manuale:

### Caso 1: Posizionamento delle Allocazioni (`alloca`) nei Cicli
* **Problema generato dall'IA:** Il generatore di codice proposto inizialmente emetteva le istruzioni `alloca` (incluse quelle per i buffer temporanei di `read_int` e `read_double`) nel punto esatto di utilizzo, ossia all'interno del Basic Block corrente (`while.body`).
* **Conseguenza:** All'interno di un ciclo iterativo, l'emissione ripetuta di `alloca` generava una crescita continua dello stack frame e impediva al passo `mem2reg` di LLVM di ottimizzare le variabili in registri SSA.
* **Soluzione Manuale:** Ristrutturazione di `codegen.py` introducendo un builder dedicato posizionato permanentemente all'inizio della funzione (`entry_builder`), forzando l'allocazione (*alloca hoisting*) di tutte le variabili locali e temporanee esclusivamente nell'entry block.

### Caso 2: Risoluzione dello Shadowing nel Back-End
* **Problema generato dall'IA:** Mentre nel front-end semantico l'IA aveva implementato l'albero degli scope, nel back-end di `codegen.py` manteneva un dizionario piatto di allocazioni.
* **Conseguenza:** La dichiarazione di una variabile locale con lo stesso nome di una variabile del blocco esterno sovrascriveva il puntatore LLVM, corrompendo la memoria al ritorno nello scope genitore.
* **Soluzione Manuale:** Implementazione di uno stack LIFO di dizionari di allocazione (`self.scopes`) in `codegen.py`, sincronizzato tramite `push_scope()` e `pop_scope()` alle entrate e uscite di ogni blocco indentato.

### Caso 3: Codice Morto e Conflitto di Terminatori nei Basic Block
* **Problema generato dall'IA:** L'IA generava istruzioni anche dopo un'istruzione `return` e, negli `if-else` annidati, posizionava il builder sul blocco iniziale anziché sull'ultimo Basic Block effettivo del ramo, emettendo rami di convergenza (`branch`) verso blocchi già terminati.
* **Conseguenza:** LLVM/Clang rifiutava l'IR emesso con errore *"expected instruction opcode"* o sollevava eccezioni interne di `llvmlite` (*"basic block already has terminator"*).
* **Soluzione Manuale:** Introduzione della verifica preliminare `self.builder.block.is_terminated` prima di elaborare ogni statement per arrestare l'emissione, e tracciamento rigoroso del Basic Block finale effettivo (`then_end_bb`, `else_end_bb`) con soppressione del blocco di convergenza (`if.end`) nel caso in cui entrambi i rami terminassero con un `return`.

### Caso 4: Preservazione dei Terminali Maiuscoli in Lark
* **Problema generato dall'IA:** Nel mappare i figli dell'AST in `ast_transformer.py`, l'IA assumeva che i token anonimi e le parentesi venissero scartati automaticamente.
* **Conseguenza:** Poiché i token denominati in maiuscolo (`LPAR`, `RPAR`) vengono mantenuti da Lark nell'albero CST, gli indici dei figli risultavano sfasati, causando errori di tipo `IndexError` a runtime.
* **Soluzione Manuale:** Ispezione analitica dell'albero CST e riallineamento manuale degli indici di scompattamento per funzioni, parametri ed espressioni.

---

## 5. Valutazione d'Impatto e Conclusioni

| Aspetto Operativo | Senza Strumenti IA | Con Approccio IA Integrato |
| :--- | :--- | :--- |
| **Prototipazione Front-End** | Studio e memorizzazione manuale della sintassi Lark (~20 ore) | Esplorazione guidata e scheletro rapido della grammatica (~6 ore) |
| **Apprendimento API `llvmlite`** | Consultazione della documentazione ufficiale a basso livello | Individuazione immediata dei pattern corretti per tipi e istruzioni |
| **Risoluzione Bug di Back-End** | Diagnosi basata su dump dell'IR e documentazione LLVM | Analisi e correzione manuale indispensabile (l'IA produceva codice invalido) |

### Riflessioni Conclusive

L'adozione dell'IA generativa si è confermata un acceleratore per la stesura del codice ripetitivo e per la documentazione tecnica. Tuttavia, l'esperienza ha evidenziato con chiarezza che **la correttezza formale di un compilatore non può essere demandata a un modello generativo**[cite: 1, 2]:
* L'IA tende a produrre codice che "appare" corretto sintatticamente, ma viola regolarmente vincoli semantici di basso livello (struttura SSA, dominanza, terminatori di Basic Block, conformità di stack frame)[cite: 1, 2].
* Il controllo del progetto e il superamento dei test hanno richiesto una solida padronanza teorica dei principi di compilazione, dimostrando che l'IA è efficace esclusivamente se guidata e validata criticamente dall'ingegnere umano[cite: 1, 2].