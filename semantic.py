import sys
import os

# Consente l'importazione sia se eseguito dalla radice sia dalla cartella src/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ast_nodes import (
    ProgramNode, FuncDefNode, ParamNode, VarDeclNode, AssignmentNode,
    IfStmtNode, WhileStmtNode, ReturnStmtNode, BinOpNode, UnOpNode,
    LiteralNode, VarRefNode, FunCallNode, ExprNode, StmtNode
)


class SemanticError(Exception):
    """
    Eccezione personalizzata per gli errori semantici del linguaggio TriaC.
    Mantiene la posizione (riga e colonna) per segnalare l'errore in modo preciso.
    """
    def __init__(self, message, line=None, column=None):
        pos_info = f" (Riga {line}, Colonna {column})" if line is not None else ""
        super().__init__(f"[ERRORE SEMANTICO]{pos_info}: {message}")
        self.line = line
        self.column = column


class SymbolTable:
    """
    Tabella dei Simboli con supporto agli scope annidati.
    Traccia le variabili locali e i relativi tipi per ciascun blocco d'esecuzione.
    """
    def __init__(self, parent=None):
        self.symbols = {}  # Mappa: nome_variabile -> tipo ('int', 'double', 'boolean', 'string')
        self.parent = parent

    def define_var(self, name, var_type, line=None, column=None):
        """Registra una nuova variabile nello scope corrente."""
        if name in self.symbols:
            raise SemanticError(f"Ridefinizione della variabile '{name}' nello stesso scope.", line, column)
        self.symbols[name] = var_type

    def lookup_var(self, name):
        """Cerca una variabile nello scope corrente o risale negli scope genitori."""
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup_var(name)
        return None


class FunctionSymbol:
    """Rappresenta la firma formale di una funzione nella Symbol Table globale."""
    def __init__(self, name, return_type, param_types):
        self.name = name
        self.return_type = return_type
        self.param_types = param_types  # Lista di tuple: [(nome_param, tipo_param), ...]


class SemanticVisitor:
    """
    Visitatore AST per l'Analisi Semantica e Type Checking di TriaC.
    Include la registrazione e validazione delle funzioni I/O predefinite (built-in).
    """
    def __init__(self):
        self.global_functions = {}  # Mappa: nome_funzione -> FunctionSymbol
        self.current_function = None
        self._register_builtins()

    def _register_builtins(self):
        """Registra le funzioni I/O predefinite (built-in) del runtime TriaC."""
        builtins = [
            FunctionSymbol("print_int", "int", [("val", "int")]),
            FunctionSymbol("print_double", "int", [("val", "double")]),
            FunctionSymbol("print_string", "int", [("s", "string")]),
            FunctionSymbol("read_int", "int", []),
            FunctionSymbol("read_double", "double", []),
        ]
        for b in builtins:
            self.global_functions[b.name] = b

    def analyze(self, ast_root):
        """Punto di ingresso dell'analisi semantica."""
        if isinstance(ast_root, FuncDefNode):
            ast_root = ProgramNode([ast_root])
        self.visit(ast_root, None)

    def visit(self, node, scope: SymbolTable):
        """Dispatcher dinamico basato sul nome della classe del nodo."""
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node, scope)

    def generic_visit(self, node, scope):
        raise NotImplementedError(f"Nessun metodo 'visit_{type(node).__name__}' implementato nel SemanticVisitor.")

    # ==========================================================================
    # STRUTTURA DEL PROGRAMMA E FUNZIONI
    # ==========================================================================

    def visit_ProgramNode(self, node: ProgramNode, scope: SymbolTable):
        builtin_names = ["print_int", "print_double", "print_string", "read_int", "read_double"]
        
        # 1. Registrazione globale delle firme delle funzioni definite dall'utente
        for func in node.functions:
            if func.name in self.global_functions and func.name not in builtin_names:
                raise SemanticError(f"Ridefinizione della funzione '{func.name}'.", func.line, func.column)
            
            param_types = [(p.name, p.param_type) for p in func.params]
            self.global_functions[func.name] = FunctionSymbol(func.name, func.return_type, param_types)

        # 2. Controllo della presenza obbligatoria della funzione main()
        if "main" not in self.global_functions:
            raise SemanticError("Funzione 'main()' non trovata nel programma.")

        # 3. Visita e validazione del corpo di ciascuna funzione
        for func in node.functions:
            self.visit(func, None)

    def visit_FuncDefNode(self, node: FuncDefNode, scope: SymbolTable):
        self.current_function = self.global_functions[node.name]
        func_scope = SymbolTable(parent=None)

        for param in node.params:
            func_scope.define_var(param.name, param.param_type, param.line, param.column)

        for stmt in node.body:
            self.visit(stmt, func_scope)

        # Control Flow Analysis: verifica che ogni percorso garantisca un return
        if not self.check_all_paths_return(node.body):
            raise SemanticError(
                f"La funzione '{node.name}' non garantisce un'istruzione 'return' su tutti i percorsi di esecuzione.",
                node.line, node.column
            )

        self.current_function = None

    def check_all_paths_return(self, statements: list) -> bool:
        """Verifica ricorsivamente se la sequenza di istruzioni garantisce un return."""
        for stmt in statements:
            if isinstance(stmt, ReturnStmtNode):
                return True
            if isinstance(stmt, IfStmtNode):
                if stmt.else_block is not None:
                    then_returns = self.check_all_paths_return(stmt.then_block)
                    else_returns = self.check_all_paths_return(stmt.else_block)
                    if then_returns and else_returns:
                        return True
        return False

    # ==========================================================================
    # ISTRUZIONI (STATEMENTS)
    # ==========================================================================

    def visit_VarDeclNode(self, node: VarDeclNode, scope: SymbolTable):
        scope.define_var(node.name, node.var_type, node.line, node.column)

        if node.value is not None:
            expr_type = self.visit(node.value, scope)
            if not self.is_type_compatible(node.var_type, expr_type):
                raise SemanticError(
                    f"Tipo non compatibile nell'inizializzazione di '{node.name}'. "
                    f"Dichiarato '{node.var_type}', ma ricevuta espressione di tipo '{expr_type}'.",
                    node.line, node.column
                )

    def visit_AssignmentNode(self, node: AssignmentNode, scope: SymbolTable):
        var_type = scope.lookup_var(node.name)
        if var_type is None:
            raise SemanticError(f"Uso di variabile non dichiarata '{node.name}'.", node.line, node.column)

        expr_type = self.visit(node.expr, scope)
        if not self.is_type_compatible(var_type, expr_type):
            raise SemanticError(
                f"Tipo non compatibile nell'assegnazione a '{node.name}'. "
                f"Atteso '{var_type}', ottenuto '{expr_type}'.",
                node.line, node.column
            )

    def visit_IfStmtNode(self, node: IfStmtNode, scope: SymbolTable):
        cond_type = self.visit(node.condition, scope)
        if cond_type != "boolean":
            raise SemanticError(
                f"La condizione del costrutto 'if' deve essere di tipo 'boolean', trovata invece di tipo '{cond_type}'.",
                node.line, node.column
            )

        then_scope = SymbolTable(parent=scope)
        for stmt in node.then_block:
            self.visit(stmt, then_scope)

        if node.else_block is not None:
            else_scope = SymbolTable(parent=scope)
            for stmt in node.else_block:
                self.visit(stmt, else_scope)

    def visit_WhileStmtNode(self, node: WhileStmtNode, scope: SymbolTable):
        cond_type = self.visit(node.condition, scope)
        if cond_type != "boolean":
            raise SemanticError(
                f"La condizione del ciclo 'while' deve essere di tipo 'boolean', trovata invece di tipo '{cond_type}'.",
                node.line, node.column
            )

        while_scope = SymbolTable(parent=scope)
        for stmt in node.body:
            self.visit(stmt, while_scope)

    def visit_ReturnStmtNode(self, node: ReturnStmtNode, scope: SymbolTable):
        ret_type = self.visit(node.expr, scope)
        expected_type = self.current_function.return_type

        if not self.is_type_compatible(expected_type, ret_type):
            raise SemanticError(
                f"Tipo di ritorno non coerente nella funzione '{self.current_function.name}'. "
                f"Dichiarato '{expected_type}', ma restituito '{ret_type}'.",
                node.line, node.column
            )

    # ==========================================================================
    # ESPRESSIONI (EXPRESSIONS & TYPE CHECKER)
    # ==========================================================================

    def visit_LiteralNode(self, node: LiteralNode, scope: SymbolTable):
        node.type = node.literal_type
        return node.type

    def visit_VarRefNode(self, node: VarRefNode, scope: SymbolTable):
        var_type = scope.lookup_var(node.name)
        if var_type is None:
            raise SemanticError(f"Variabile non dichiarata '{node.name}'.", node.line, node.column)
        node.type = var_type
        return node.type

    def visit_BinOpNode(self, node: BinOpNode, scope: SymbolTable):
        left_type = self.visit(node.left, scope)
        right_type = self.visit(node.right, scope)

        if node.op in ["and", "or"]:
            if left_type != "boolean" or right_type != "boolean":
                raise SemanticError(
                    f"L'operatore logico '{node.op}' richiede operandi 'boolean', trovati '{left_type}' e '{right_type}'.",
                    node.line, node.column
                )
            node.type = "boolean"
            return node.type

        if node.op in ["==", "!=", "<", ">", "<=", ">="]:
            if not self.are_arithmetic_compatible(left_type, right_type) and left_type != right_type:
                raise SemanticError(
                    f"Impossibile confrontare tipi non omogenei: '{left_type}' {node.op} '{right_type}'.",
                    node.line, node.column
                )
            node.type = "boolean"
            return node.type

        if node.op in ["+", "-", "*", "/"]:
            if not self.are_arithmetic_compatible(left_type, right_type):
                raise SemanticError(
                    f"Operatore aritmetico '{node.op}' non supportato per i tipi '{left_type}' e '{right_type}'.",
                    node.line, node.column
                )
            node.type = "double" if "double" in [left_type, right_type] else "int"
            return node.type

        raise SemanticError(f"Operatore binario sconosciuto '{node.op}'.", node.line, node.column)

    def visit_UnOpNode(self, node: UnOpNode, scope: SymbolTable):
        expr_type = self.visit(node.expr, scope)

        if node.op == "not":
            if expr_type != "boolean":
                raise SemanticError(
                    f"L'operatore 'not' richiede un'espressione 'boolean', trovata invece '{expr_type}'.",
                    node.line, node.column
                )
            node.type = "boolean"
            return node.type

        if node.op == "-":
            if expr_type not in ["int", "double"]:
                raise SemanticError(
                    f"L'operatore algebrico '-' richiede un valore numerico ('int' o 'double'), trovato '{expr_type}'.",
                    node.line, node.column
                )
            node.type = expr_type
            return node.type

        raise SemanticError(f"Operatore unario sconosciuto '{node.op}'.", node.line, node.column)

    def visit_FunCallNode(self, node: FunCallNode, scope: SymbolTable):
        if node.name == "main":
            raise SemanticError(
                "La chiamata esplicita alla funzione 'main()' è vietata dal runtime di TriaC.",
                node.line, node.column
            )

        if node.name not in self.global_functions:
            raise SemanticError(f"Chiamata a funzione non dichiarata '{node.name}()'.", node.line, node.column)

        func_sym = self.global_functions[node.name]

        if len(node.args) != len(func_sym.param_types):
            raise SemanticError(
                f"Numero errato di argomenti nella chiamata a '{node.name}()'. "
                f"Attesi {len(func_sym.param_types)}, forniti {len(node.args)}.",
                node.line, node.column
            )

        for i, arg in enumerate(node.args):
            arg_type = self.visit(arg, scope)
            param_name, param_type = func_sym.param_types[i]
            if not self.is_type_compatible(param_type, arg_type):
                raise SemanticError(
                    f"Tipo argomento errato nella chiamata a '{node.name}()' per il parametro '{param_name}'. "
                    f"Atteso '{param_type}', fornito '{arg_type}'.",
                    node.line, node.column
                )

        node.type = func_sym.return_type
        return node.type

    # ==========================================================================
    # METODI AUSILIARI DI COMPATIBILITÀ TIPI
    # ==========================================================================

    def is_type_compatible(self, target_type, source_type):
        if target_type == source_type:
            return True
        if target_type == "double" and source_type == "int":
            return True
        if target_type == "string" and source_type == "string":
            return True
        return False

    def are_arithmetic_compatible(self, t1, t2):
        valid_types = ["int", "double"]
        return t1 in valid_types and t2 in valid_types