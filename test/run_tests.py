import os
import sys
import subprocess
from pathlib import Path

# Configurazione percorsi assoluti
TEST_DIR = Path(__file__).resolve().parent
ROOT_DIR = TEST_DIR.parent
SRC_DIR = ROOT_DIR / "src"

sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(SRC_DIR))

from parser_wrapper import TriaCParser
from ast_transformer import TriaCASTTransformer
from semantic import SemanticVisitor, SemanticError
from codegen import LLVMCodeGenVisitor


def compile_pipeline(source_code):
    """Esegue le prime 4 fasi della pipeline restituendo l'LLVM IR generato."""
    parser = TriaCParser()
    cst = parser.parse(source_code)
    transformer = TriaCASTTransformer()
    ast = transformer.transform(cst)
    semantic_analyzer = SemanticVisitor()
    semantic_analyzer.analyze(ast)
    codegen = LLVMCodeGenVisitor()
    return codegen.generate(ast)


def run_valid_tests(casi_validi_dir):
    print("\n--- ESECUZIONE CASI VALIDI ---")
    tc_files = sorted(casi_validi_dir.glob("*.tc"))
    if not tc_files:
        print("[ERRORE]: Nessun file .tc trovato in casi_validi/")
        return False

    for tc_path in tc_files:
        base_name = tc_path.stem
        expected_path = casi_validi_dir / f"{base_name}.expected"
        stdin_path = casi_validi_dir / f"{base_name}.stdin"
        ll_path = casi_validi_dir / f"{base_name}.ll"
        obj_path = casi_validi_dir / f"{base_name}.o"
        exe_path = casi_validi_dir / f"{base_name}.bin"

        if not expected_path.exists():
            print(f"[FAIL] {base_name}: Manca il file {base_name}.expected")
            return False

        with open(tc_path, "r", encoding="utf-8") as f:
            code = f.read()
        with open(expected_path, "r", encoding="utf-8") as f:
            expected_output = f.read().strip()

        # (a) Compilazione fino a LLVM IR
        try:
            llvm_ir = compile_pipeline(code)
            with open(ll_path, "w", encoding="utf-8") as f:
                f.write(llvm_ir)
        except Exception as e:
            print(f"[FAIL] {base_name}: Fallimento pipeline: {e}")
            return False

        # (b) Validazione dell'IR con clang -c
        try:
            subprocess.run(["clang", "-c", str(ll_path), "-o", str(obj_path)], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"[FAIL] {base_name}: IR LLVM NON VALIDO per clang -c:")
            print(e.stderr.decode("utf-8"))
            return False

        # (c) Linking ed esecuzione binaria con confronto stdout
        try:
            subprocess.run(["clang", str(ll_path), "-o", str(exe_path)], check=True, capture_output=True)
            stdin_data = None
            if stdin_path.exists():
                with open(stdin_path, "r", encoding="utf-8") as f:
                    stdin_data = f.read()

            res = subprocess.run([str(exe_path)], input=stdin_data, text=True, capture_output=True, check=True)
            actual_output = res.stdout.strip()

            if actual_output != expected_output:
                print(f"[FAIL] {base_name}: Output non corrispondente.")
                print(f"       Atteso:\n{expected_output}")
                print(f"       Ottenuto:\n{actual_output}")
                return False
        except subprocess.CalledProcessError as e:
            print(f"[FAIL] {base_name}: Errore a runtime nell'eseguibile: {e}")
            return False
        finally:
            for p in [ll_path, obj_path, exe_path]:
                if p.exists():
                    p.unlink()

        print(f"[PASS] {base_name}")
    return True


def run_error_tests(casi_errore_dir, auto_fix=False):
    print("\n--- ESECUZIONE CASI ERRORE ---")
    tc_files = sorted(casi_errore_dir.glob("*.tc"))
    if not tc_files:
        print("[ERRORE]: Nessun file .tc trovato in casi_errore/")
        return False

    all_passed = True
    for tc_path in tc_files:
        base_name = tc_path.stem
        expected_path = casi_errore_dir / f"{base_name}.expected"

        with open(tc_path, "r", encoding="utf-8") as f:
            code = f.read()

        expected_fragment = ""
        if expected_path.exists():
            with open(expected_path, "r", encoding="utf-8") as f:
                expected_fragment = f.read().strip()

        try:
            compile_pipeline(code)
            print(f"[FAIL] {base_name}: La compilazione ha avuto successo ma era atteso un errore.")
            if not auto_fix:
                return False
            all_passed = False
        except Exception as e:
            err_msg = str(e)

            # Estrae la parte descrittiva dell'errore togliendo il prefisso "(Riga X, Colonna Y):"
            clean_msg = err_msg
            if "): " in err_msg:
                clean_msg = err_msg.split("): ", 1)[1].strip()
            elif "]: " in err_msg:
                clean_msg = err_msg.split("]: ", 1)[1].strip()
            else:
                # Per errori sintattici multilinea (Lark), prende solo la prima riga
                clean_msg = clean_msg.splitlines()[0].strip()
                
            if auto_fix:
                if not expected_path.exists() or expected_fragment not in err_msg:
                    with open(expected_path, "w", encoding="utf-8") as f:
                        f.write(clean_msg)
                    print(f"[FIX]  {base_name}: Aggiornato frammento atteso -> '{clean_msg}'")
                else:
                    print(f"[PASS] {base_name}")
            else:
                if not expected_path.exists() or expected_fragment not in err_msg:
                    print(f"[FAIL] {base_name}: Messaggio d'errore non corrispondente.")
                    print(f"       Frammento atteso: '{expected_fragment}'")
                    print(f"       Errore ottenuto:  '{err_msg}'")
                    return False
                print(f"[PASS] {base_name}")

    return all_passed


if __name__ == "__main__":
    auto_fix = "--fix" in sys.argv

    casi_validi_dir = TEST_DIR / "casi_validi"
    casi_errore_dir = TEST_DIR / "casi_errore"

    if not casi_validi_dir.exists() or not casi_errore_dir.exists():
        print("[ERRORE]: Le cartelle 'casi_validi/' e 'casi_errore/' devono esistere all'interno di 'test/'.")
        sys.exit(1)

    if auto_fix:
        print("=== MODALITÀ AUTO-FIX: ALLINEAMENTO AUTOMATICO DEI FILE .EXPECTED ===")
        run_error_tests(casi_errore_dir, auto_fix=True)
        print("\nAllineamento completato! Riesegui ora: python3 test/run_test.py")
        sys.exit(0)

    success_val = run_valid_tests(casi_validi_dir)
    if not success_val:
        print("\n=== SUITE FALLITA NEI CASI VALIDI ===")
        sys.exit(1)

    success_err = run_error_tests(casi_errore_dir, auto_fix=False)
    if not success_err:
        print("\n=== SUITE FALLITA NEI CASI ERRORE ===")
        sys.exit(1)

    print("\n=== TUTTI I TEST DELLA SUITE SONO STATI SUPERATI CON SUCCESSO (0 ERRORI) ===")
    sys.exit(0)