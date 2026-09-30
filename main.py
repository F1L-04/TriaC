import os
import sys
import subprocess

sys.path.append(os.path.abspath(__file__))

from parser_wrapper import TriaCParser
from ast_transformer import TriaCASTTransformer
from semantic import SemanticVisitor, SemanticError
from codegen import LLVMCodeGenVisitor


def compila_triac(file_sorgente):
    """
    Driver principale da riga di comando per il compilatore TriaC.
    Esegue in sequenza la pipeline: Parsing -> AST -> Analisi Semantica -> LLVM IR -> Clang.
    """
    print(f"=== Compilatore TriaC: Avvio compilazione di '{file_sorgente}' ===")

    if not os.path.exists(file_sorgente):
        print(f"[ERRORE]: Impossibile trovare il file sorgente '{file_sorgente}'.")
        sys.exit(1)

    with open(file_sorgente, "r", encoding="utf-8") as f:
        codice_sorgente = f.read()

    # Fase 1: Parsing Sintattico (CST)
    try:
        print("[1/5] Esecuzione Analisi Sintattica (LALR + Post-Lexer Indenter)...")
        parser = TriaCParser()
        cst = parser.parse(codice_sorgente)
    except Exception as e:
        print(f"[ERRORE SINTATTICO]: {e}")
        sys.exit(1)

    # Fase 2: Trasformazione CST -> AST
    try:
        print("[2/5] Costruzione dell'Abstract Syntax Tree (AST)...")
        transformer = TriaCASTTransformer()
        ast = transformer.transform(cst)
    except Exception as e:
        print(f"[ERRORE AST]: {e}")
        sys.exit(1)

    # Fase 3: Analisi Semantica & Type Checking
    try:
        print("[3/5] Esecuzione Analisi Semantica e Type Checking...")
        semantic_analyzer = SemanticVisitor()
        semantic_analyzer.analyze(ast)
    except SemanticError as se:
        print(f"{se}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERRORE SEMANTICO INATTESO]: {e}")
        sys.exit(1)

    # Fase 4: Generazione Codice LLVM IR (.ll)
    try:
        print("[4/5] Generazione Codice LLVM IR...")
        codegen = LLVMCodeGenVisitor()
        llvm_ir = codegen.generate(ast)
        
        base_name = os.path.splitext(file_sorgente)[0]
        ll_file = f"{base_name}.ll"
        with open(ll_file, "w", encoding="utf-8") as out:
            out.write(llvm_ir)
        print(f"      -> File LLVM IR generato: '{ll_file}'")
    except Exception as e:
        print(f"[ERRORE CODEGEN]: {e}")
        sys.exit(1)

    # Fase 5: Compilazione Nativa tramite Clang
    try:
        exe_file = f"./{base_name}"
        print(f"[5/5] Invocazione di clang per la generazione dell'eseguibile nativo '{exe_file}'...")
        subprocess.run(["clang", ll_file, "-o", exe_file], check=True)
        print(f"\n[SUCCESSO]: Compilazione completata con successo!")
        print(f"Per eseguire il programma, digita da terminale: {exe_file}")
    except subprocess.CalledProcessError as cpe:
        print(f"[ERRORE COMPILAZIONE CLANG]: Clang ha restituito un codice di errore {cpe.returncode}")
        sys.exit(1)
    except FileNotFoundError:
        print("[AVVISO]: Clang non trovato nel PATH di sistema. Il file '.ll' è pronto ma richiede clang per generare il binario.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 main.py <file_sorgente.tc>")
        sys.exit(1)

    compila_triac(sys.argv[1])