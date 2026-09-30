# Specifiche Tecniche e Relazione Architetturale: Compilatore TriaC

## 1. Introduzione e Specifiche del Linguaggio TriaC

TriaC è un linguaggio imperativo, tipizzato staticamente e orientato al silicio, ideato per eliminare il debito tecnico dei linguaggi didattici procedurali convenzionali.

### 1.1. Proprietà Cardine del Linguaggio
* **Struttura del Programma:** Un file sorgente TriaC è composto esclusivamente da una sequenza ordinata di funzioni (`func`). Non sono previste variabili globali mutevoli né procedure disgiunte.
* **Entry Point Obbligatorio:** Ogni programma TriaC valido deve contenere la definizione della funzione principale avente firma deterministica `func main() -> int:`.
* **Layout-Sensitivity:** La delimitazione dei blocchi di codice non ricorre a parentesi graffe né a parole chiave terminali (`endfunc`, `endif`), ma si basa rigorosamente sul livello di rientro (indentazione).
* **Semplificazione Procedurale:** Tutte le routine restituiscono un valore esplicito. I passaggi di parametro avvengono esclusivamente per valore, prevenendo effetti collaterali non tracciati.
* **Type System Formale:** Tipizzazione statica ed esplicita alla dichiarazione. I tipi primitivi sono:
  * `int`: Intero con segno rappresentato a 32 bit nel runtime.
  * `double`: Virgola mobile a 64 bit a precisione doppia IEEE 754.
  * `boolean`: Tipo logico a 1 bit con letterali `true` e `false`.
  * `string`: Supportato per costanti letterali e I/O tramite puntatori nativi (`i8*`).

### 1.2. Primitive di Input/Output (Built-in)
L'I/O in TriaC evita caratteri grafici complessi o string interpolation, demandando le operazioni a funzioni predefinite collegate alla libreria C standard (`libc`):
* `print_string(val: string) -> int`: Emette una stringa su standard output con terminatore di riga.
* `print_int(val: int) -> int`: Emette un intero formattato su standard output.
* `print_double(val: double) -> int`: Emette un floating-point su standard output con due cifre decimali.
* `read_int() -> int`: Acquisisce un intero da standard input.
* `read_double() -> double`: Acquisisce un decimale a precisione doppia da standard input.

---

## 2. Architettura della Pipeline del Compilatore

Il compilatore implementa una pipeline modulare a 5 stadi sequenziali coordinati dal driver `main.py`:

```text
Codice Sorgente (.tc)
│
▼
[1. Lexer + Indenter]  ──► indenter.py: Generazione token fisici e virtuali (_INDENT/_DEDENT)
│
▼
[2. Parser LALR(1)]    ──► grammar.lark + parser_wrapper.py: Validazione CST deterministica
│
▼
[3. AST Transformer]   ──► ast_nodes.py + ast_transformer.py: Costruzione AST canonico ad oggetti
│
▼
[4. Semantic Checker]  ──► semantic.py: Type checking, albero degli scope, return garantito
│
▼
[5. LLVM IR Codegen]   ──► codegen.py: Alloca-hoisting, scope stack e CFG via llvmlite (.ll)
│
▼
[Clang Linker]         ──► Generazione eseguibile binario nativo collegato a libc
```

---

## 3. Front-End: Analisi Lessicale, Sintattica e AST

### 3.1. Gestione dell'Indentazione (`indenter.py`)
I parser generati da automi a stati finiti deterministici operano su grammatiche libere da contesto (*Context-Free*) insensibili al layout. Per integrare la sintassi *off-side rule*, il compilatore interpone un **Post-Lexer** (`TriaCIndenter` esteso da `lark.indenter.Indenter`) tra la fase di scansione dei caratteri e la tabella di parsing:
* Mantiene uno stack di interi che traccia le colonne di indentazione correnti.
* All'incontro di un token `_NEWLINE`, confronta il numero di spazi iniziali della riga successiva con il top dello stack:
  * Incremento $\rightarrow$ emissione del token virtuale `_INDENT` e push del nuovo livello sullo stack.
  * Decremento $\rightarrow$ pop dei livelli dallo stack ed emissione di uno o più token virtuali `_DEDENT` fino a ristabilire la corrispondenza.
* Traccia il bilanciamento delle parentesi tonde (`OPEN_PAREN_types = ['LPAR']`, `CLOSE_PAREN_types = ['RPAR']`), sospendendo temporaneamente l'emissione dei token di indentazione per abilitare espressioni multi-riga sicure.

### 3.2. Grammatica Formale e Parsing LALR(1) (`grammar.lark`, `parser_wrapper.py`)
La grammatica formale è priva di conflitti *Shift/Reduce* e *Reduce/Reduce*, garantendo tempo di derivazione lineare O(n):
* **Cascata delle Precedenze:** L'ordine degli operatori è rigidamente gerarchico:
  $$\text{expr} \rightarrow \text{logical\_or} \rightarrow \text{logical\_and} \rightarrow \text{comparison} \rightarrow \text{arith\_expr} \rightarrow \text{term} \rightarrow \text{factor}$$
* **Associatività a Sinistra:** Implementata mediante la produzione iterativa `term (ADD_OP term)*`.
* **Tree Inlining (`?`):** Le regole unarie di transizione collassano automaticamente i nodi intermedi con un solo figlio, riducendo l'impronta di memoria del Parse Tree.
* **Regola `block`:** La sequenza `block: statement+` raggruppa le istruzioni del corpo di funzioni, cicli e diramazioni evitando l'appiattimento (*flattening*) della lista dei figli.
* **Tracciamento Posizionale:** L'attivazione di `propagate_positions=True` in `Lark.open` garantisce che le coordinate di riga e colonna vengano calcolate ed estese all'intero albero sintattico per la diagnostica d'errore.

### 3.3. Modello dell'AST e Trasformazione Bottom-Up (`ast_nodes.py`, `ast_transformer.py`)
* **Gerarchia delle Classi:** L'albero distingue formalmente tra `StmtNode` (istruzioni senza tipo, orientate agli effetti di stato) ed `ExprNode` (espressioni provviste dell'attributo `type`).
* **Catamorfismo Bottom-Up:** `TriaCASTTransformer` estende `lark.Transformer`, elaborando i nodi foglia e risalendo verso la radice `ProgramNode`.
* **Left-Associative Folding:** Per espressioni aritmetiche e relazionali, un ciclo `while` a passo 2 trasforma le sequenze piatte `[val1, op, val2, ...]` in alberi binari annidati `BinOpNode(op, left, right)`.
* **Gestione dei Terminali Maiuscoli:** La mappatura tiene conto della preservazione in Lark dei token in lettere maiuscole (`NAME`, `LPAR`, `RPAR`), recuperando con precisione parametri e blocchi di istruzioni.

---

## 4. Middle-End: Analisi Semantica e Type System (`semantic.py`)

L'analizzatore semantico agisce sull'AST tramite il Visitor Pattern, validando i vincoli context-sensitive non catturabili dalla grammatica formale.

### 4.1. Symbol Table con Scoping Lessicale ad Albero
La gestione degli identificatori adotta una struttura gerarchica ad albero orientata ai padri:

- Ogni funzione e blocco condizionale/iterativo istanzia un proprio ambiente SymbolTable(parent=...).
- Risoluzione (lookup_var): Ricerca localmente e risale ricorsivamente la catena dei padri, supportando lo shadowing lecito in blocchi interni e impedendo l'accesso a variabili fuori scope.
- Definizione (define_var): Rileva e blocca duplicazioni di variabili all'interno del medesimo blocco.

### 4.2. Analisi a Due Passate

1. Passata 1 (Signature Harvesting): Registra nella tabella globale le firme (FunctionSymbol) di tutte le funzioni dell'utente e ne controlla l'univocità rispetto alle built-in predefinite. Verifica inoltre la presenza della funzione main().
2. Passata 2 (Body Validation): Esegue la discesa nei corpi delle funzioni validando istruzioni, compatibilità di assegnazione e corrispondenza parametri/argomenti nelle chiamate.

### 4.3. Type Checking e Regole di Coercizione
Il compilatore applica controlli di tipo rigorosi su 5 contesti specifici:

1. Dichiarazione: Compatibilità tra tipo dichiarato ed espressione di inizializzazione.
2. Assegnamento: Compatibilità del tipo della variabile a sinistra rispetto al valore a destra.
3. Argomento di funzione: Corrispondenza di arità e tipi tra parametri formali e attuali.
4. Istruzione di Return: Corrispondenza del tipo restituito con la firma della funzione.
5. Operatori di Confronto: Entrambi gli operandi devono appartenere allo stesso dominio numerico o logico.

- Promozione Implicita (Widening): In tutti i contesti sopra indicati, è consentita la promozione automatica da int a double. Il cast inverso (narrowing) da double a int è categoricamente vietato.
- Operazioni Booleane: and, or, not e le condizioni di guardia di if e while esigono rigorosamente il tipo boolean.

### 4.4. Control Flow Analysis: Verifica del Return Garantito
L'algoritmo check_all_paths_return ispeziona la struttura di controllo del corpo di ogni funzione per assicurare che non esistano cammini privi di terminatore:

- Un blocco sequenziale è chiuso se contiene un ReturnStmtNode.
- Un nodo IfStmtNode garantisce il ritorno se e solo se possiede la clausola else ed entrambi i sotto-blocchi (then_block e else_block) garantiscono il ritorno.
- I cicli WhileStmtNode non garantiscono il ritorno a causa della possibile non-esecuzione del corpo a runtime (0 iterazioni).

---

## 5. Back-End: Generazione Codice LLVM IR (`codegen.py`)

La traduzione verso LLVM IR è realizzata con llvmlite adottando il modello di compilazione memory-based e rispettando i vincoli di forma canonica del Control Flow Graph (CFG).

### 5.1. Entry-Block Alloca Hoisting
Per generare codice compatibile con il passo di ottimizzazione mem2reg di LLVM ed evitare l'esaurimento dello stack runtime:

- Tutte le istruzioni alloca (variabili locali, parametri formali e buffer temporanei utilizzati da read_int e read_double) vengono emesse esclusivamente nel blocco entry della funzione all'avvio del codice, sfruttando un builder dedicato (entry_builder).
- Nessuna alloca viene emessa all'interno di blocchi ciclici (while.body) o diramazioni condizionali. In questo modo lo stack frame della funzione rimane costante e di dimensione prefissata durante l'esecuzione del programma.

### 5.2. Scope Stack nel Back-End per lo Shadowing
Per allinearsi alla semantica dello scope ad albero del front-end, codegen.py gestisce uno stack LIFO di tabelle di allocazione (self.scopes):

- A ogni ingresso in un blocco indentato (visit_FuncDefNode, visit_IfStmtNode, visit_WhileStmtNode), viene eseguito push_scope(); al termine del blocco viene invocato pop_scope().
- La ricerca dei puntatori allocati risale lo stack dal livello più interno a quello esterno: le variabili locali dichiarate all'interno di blocchi annidati oscurano le variabili omonime dei blocchi genitore senza sovrascriverne la locazione di memoria.

### 5.3. Eliminazione del Codice Morto e Gestione dei Basic Block
Per garantire che l'IR prodotto sia formalmente valido e accettato dal validatore LLVM (clang -c):

- Controllo Preventivo Terminatori: Prima di generare l'IR per qualunque statement, il visitor verifica la proprietà self.builder.block.is_terminated. Se il blocco corrente possiede già un terminatore (ret o br), il ciclo di emissione viene interrotto immediatamente (break), inibendo l'inserimento di codice non raggiungibile post-return.
- Costrutti If-Else Annidati: Il generatore traccia il blocco finale effettivo di ciascun ramo (then_end_bb ed else_end_bb). Il Basic Block di confluenza (if.end) viene creato e collegato solo se almeno uno dei due rami non è terminato. Se entrambi i rami contengono un'istruzione di return, l'emissione del blocco merge viene soppressa per non generare Basic Block orfani privi di predecessori.
- Cicli While: Strutturati nei tre blocchi while.cond, while.body e while.end. Il salto incondizionato retroattivo verso while.cond viene emesso solo se il corpo del ciclo non è stato terminato da un return interno.

### 5.4. Mappatura Tipi Fisici e Chiamate Esterne
- int $\to$ i32, double $\to$ double, boolean $\to$ i1, string $\to$ i8*.
- Le conversioni numeriche emettono l'istruzione nativa sitofp (Signed Integer to Floating Point).
- L'interfacciamento con printf e scanf avviene mediante dichiarazione di costanti globali indicizzate (es. "%d\n", "%lf") accedute tramite gep (getelementptr).

---

## 6. Testing, Benchmark e Validazione

La convalida del compilatore è affidata a una suite di test completa e deterministica gestita dal runner unico test/run_tests.py.

### 6.1. Architettura del Test Runner (run_tests.py)
Il runner esegue tutti i test senza intervento manuale e si arresta con codice di uscita 1 al primo fallimento (risposta binaria 0/1):
- Casi Validi (test/casi_validi/ - 18 test):
  Per ciascun sorgente .tc, il runner esegue una validazione a tre livelli:
    1. Completamento della pipeline senza eccezioni Python.
    2. Validazione formale dell'IR: esecuzione di clang -c <file>.ll -o <file>.o con verifica dell'exit code 0 (garantisce l'assenza di violazioni SSA, Basic Block malformati o istruzioni dopo terminatori).
    3. Esecuzione binaria: esecuzione dell'eseguibile (alimentato con l'eventuale .stdin) e confronto byte-a-byte con .expected.Casi coperti: ricorsione, precedenze e associatività, promozione int $\to$ double, dead-code nei 3 scenari, cicli annidati, allocazioni alloca nei loop, variabili non inizializzate, costrutti booleani e shadowing a più livelli.

- Casi di Errore (test/casi_errore/ - 16 test):
  Verifica che programmi formalmente errati vengano respinti sollevando l'eccezione prevista (SemanticError o errore sintattico) e che il messaggio contenga il frammento atteso con riga e colonna corrette.
  Casi coperti: variabile non dichiarata, uso fuori scope, ridichiarazione nello stesso blocco, tipi incompatibili nelle 5 posizioni (dichiarazione, assegnamento, argomento, return, confronto), condizione non booleana, main mancante, funzione duplicata, arità errata, chiamata esplicita a main, return non garantito e indentazione incoerente.
  
### 6.2. Benchmark Calcolatrice Interattiva (test_calcolatrice.tc)
In conformità alla Sezione 4 delle Linee Guida d'esame, il progetto integra un benchmark interattivo completo:
- Mostra a video un menu testuale di selezione per le 4 operazioni aritmetiche fondamentali.
- Acquisisce valori numerici da console sia interi (scelta menu) sia floating-point a precisione doppia (operandi).
- Gestisce un ciclo iterativo while di continuazione fino all'inserimento del comando di uscita (0).
- Scompone il flusso logico su più funzioni distinte (stampa_menu, esegui_calcolo e main), proteggendo l'esecuzione da divisioni per zero.
- Il benchmark viene convalidato sia in modalità automatica non presidiata (iniettando lo standard input tramite .stdin ed .expected) sia in modalità interattiva da console.