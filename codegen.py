import sys
import os
from llvmlite import ir

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ast_nodes import (
    ProgramNode, FuncDefNode, ParamNode, VarDeclNode, AssignmentNode,
    IfStmtNode, WhileStmtNode, ReturnStmtNode, BinOpNode, UnOpNode,
    LiteralNode, VarRefNode, FunCallNode
)


class LLVMCodeGenVisitor:
    """
    Visitatore AST per la Generazione di Codice Intermedio LLVM IR.
    Include la gestione nativa delle funzioni di I/O mediante le funzioni C printf e scanf,
    scoping lessicale a stack e prevenzione di dead-code dopo istruzioni terminali.
    """
    def __init__(self):
        self.module = ir.Module(name="triac_module")
        self.module.triple = ir.GDT_DEFAULT_TRIPLE if hasattr(ir, 'GDT_DEFAULT_TRIPLE') else ""
        
        self.builder = None
        self.current_func = None
        # Pila di scope per supportare lo shadowing lessicale nel Back-End
        self.symbol_table_stack = [{}]
        self.functions = {}     # Mappa: nome_funzione -> ir.Function
        self.global_strings = {}

        # Mappatura dei tipi di TriaC verso i tipi LLVM IR fisici
        self.type_map = {
            "int": ir.IntType(32),
            "double": ir.DoubleType(),
            "boolean": ir.IntType(1),
            "string": ir.PointerType(ir.IntType(8))
        }

        # Dichiarazione esterna delle funzioni C di runtime (printf / scanf)
        self._declare_c_runtime()

    def _declare_c_runtime(self):
        """Dichiara le funzioni C esterne printf e scanf nel modulo LLVM."""
        printf_type = ir.FunctionType(ir.IntType(32), [ir.PointerType(ir.IntType(8))], var_arg=True)
        self.printf = ir.Function(self.module, printf_type, name="printf")

        scanf_type = ir.FunctionType(ir.IntType(32), [ir.PointerType(ir.IntType(8))], var_arg=True)
        self.scanf = ir.Function(self.module, scanf_type, name="scanf")

    def _get_or_create_global_string(self, text, name_prefix="str"):
        """Crea o riutilizza una costante di stringa globale terminata da null in LLVM."""
        if text in self.global_strings:
            global_var = self.global_strings[text]
        else:
            fmt_bytes = bytearray((text + "\0").encode("utf-8"))
            c_str = ir.Constant(ir.ArrayType(ir.IntType(8), len(fmt_bytes)), fmt_bytes)
            str_id = abs(hash(text)) & 0xffffff
            global_var = ir.GlobalVariable(self.module, c_str.type, name=f".{name_prefix}_{str_id}")
            global_var.linkage = 'internal'
            global_var.global_constant = True
            global_var.initializer = c_str
            self.global_strings[text] = global_var

        zero = ir.Constant(ir.IntType(32), 0)
        return self.builder.gep(global_var, [zero, zero], inbounds=True)

    # ==========================================================================
    # GESTIONE SCOPE LESSICALE E ALLOCAZIONI ENTRY BLOCK
    # ==========================================================================

    def push_scope(self):
        """Apre un nuovo scope annidato nello stack."""
        self.symbol_table_stack.append({})

    def pop_scope(self):
        """Chiude lo scope corrente ripristinando il livello precedente."""
        self.symbol_table_stack.pop()

    def define_var(self, name, ptr):
        """Associa un puntatore a una variabile nello scope corrente."""
        self.symbol_table_stack[-1][name] = ptr

    def lookup_var(self, name):
        """Risolve la variabile risalendo lo stack degli scope dall'interno all'esterno."""
        for scope in reversed(self.symbol_table_stack):
            if name in scope:
                return scope[name]
        raise KeyError(f"Variabile '{name}' non trovata nella symbol table del CodeGen.")

    def create_entry_block_alloca(self, var_type, name=""):
        """
        Alloca la memoria per una variabile esclusivamente nell'entry block della funzione,
        posizionandosi prima di qualsiasi istruzione non-alloca.
        Previene perdite di stack frame all'interno dei cicli e abilita l'ottimizzazione mem2reg.
        """
        entry_bb = self.current_func.entry_basic_block
        current_bb = self.builder.block if self.builder else None

        # Crea un builder dedicato ancorato all'inizio dell'entry block
        alloc_builder = ir.IRBuilder(entry_bb)
        alloc_builder.position_at_start(entry_bb)
        ptr = alloc_builder.alloca(var_type, name=name)

        # Ripristina il builder principale sul blocco corrente
        if current_bb is not None:
            self.builder.position_at_end(current_bb)

        return ptr

    def generate(self, ast_root: ProgramNode) -> str:
        """Punto di ingresso per la generazione del codice LLVM IR."""
        self.visit(ast_root)
        return str(self.module)

    def visit(self, node):
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        raise NotImplementedError(f"Nessun metodo 'visit_{type(node).__name__}' implementato nel CodeGen.")

    # ==========================================================================
    # STRUTTURA DEL PROGRAMMA E FUNZIONI
    # ==========================================================================

    def visit_ProgramNode(self, node: ProgramNode):
        for func in node.functions:
            param_types = [self.type_map[p.param_type] for p in func.params]
            ret_type = self.type_map[func.return_type]
            func_type = ir.FunctionType(ret_type, param_types)
            llvm_func = ir.Function(self.module, func_type, name=func.name)
            self.functions[func.name] = llvm_func

        for func in node.functions:
            self.visit(func)

    def visit_FuncDefNode(self, node: FuncDefNode):
        llvm_func = self.functions[node.name]
        self.current_func = llvm_func
        self.symbol_table_stack = [{}]

        entry_bb = llvm_func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(entry_bb)

        for i, param in enumerate(node.params):
            llvm_param = llvm_func.args[i]
            llvm_param.name = param.name
            
            param_type = self.type_map[param.param_type]
            ptr = self.create_entry_block_alloca(param_type, name=param.name)
            self.builder.store(llvm_param, ptr)
            self.define_var(param.name, ptr)

        for stmt in node.body:
            if self.builder.block.is_terminated:
                break
            self.visit(stmt)

        if not self.builder.block.is_terminated:
            if node.return_type == "int":
                self.builder.ret(ir.Constant(ir.IntType(32), 0))
            elif node.return_type == "double":
                self.builder.ret(ir.Constant(ir.DoubleType(), 0.0))
            elif node.return_type == "boolean":
                self.builder.ret(ir.Constant(ir.IntType(1), 0))

    # ==========================================================================
    # ISTRUZIONI (STATEMENTS)
    # ==========================================================================

    def visit_VarDeclNode(self, node: VarDeclNode):
        var_type = self.type_map[node.var_type]
        ptr = self.create_entry_block_alloca(var_type, name=node.name)
        self.define_var(node.name, ptr)

        if node.value is not None:
            val = self.visit(node.value)
            val = self.cast_if_needed(val, var_type)
            self.builder.store(val, ptr)
        else:
            default_val = ir.Constant(var_type, 0)
            self.builder.store(default_val, ptr)

    def visit_AssignmentNode(self, node: AssignmentNode):
        ptr = self.lookup_var(node.name)
        val = self.visit(node.expr)
        val = self.cast_if_needed(val, ptr.type.pointee)
        self.builder.store(val, ptr)

    def visit_IfStmtNode(self, node: IfStmtNode):
        cond_val = self.visit(node.condition)

        then_bb = self.current_func.append_basic_block(name="if.then")
        else_bb = self.current_func.append_basic_block(name="if.else") if node.else_block else None

        merge_bb = None
        if not else_bb:
            merge_bb = self.current_func.append_basic_block(name="if.end")
            target_else = merge_bb
        else:
            target_else = else_bb

        self.builder.cbranch(cond_val, then_bb, target_else)

        # Ramo Then
        self.builder.position_at_end(then_bb)
        self.push_scope()
        for stmt in node.then_block:
            if self.builder.block.is_terminated:
                break
            self.visit(stmt)
        self.pop_scope()
        then_terminated = self.builder.block.is_terminated
        then_end_bb = self.builder.block  # Cattura il blocco finale effettivo del then

        # Ramo Else
        else_terminated = False
        else_end_bb = None
        if else_bb:
            self.builder.position_at_end(else_bb)
            self.push_scope()
            for stmt in node.else_block:
                if self.builder.block.is_terminated:
                    break
                self.visit(stmt)
            self.pop_scope()
            else_terminated = self.builder.block.is_terminated
            else_end_bb = self.builder.block  # Cattura il blocco finale effettivo dell'else

        # Gestione confluenza Basic Block (Merge)
        if else_bb:
            if not then_terminated or not else_terminated:
                merge_bb = self.current_func.append_basic_block(name="if.end")
                if not then_terminated:
                    self.builder.position_at_end(then_end_bb)
                    self.builder.branch(merge_bb)
                if not else_terminated:
                    self.builder.position_at_end(else_end_bb)
                    self.builder.branch(merge_bb)
                self.builder.position_at_end(merge_bb)
        else:
            if not then_terminated:
                self.builder.position_at_end(then_end_bb)
                self.builder.branch(merge_bb)
            self.builder.position_at_end(merge_bb)
            
    def visit_WhileStmtNode(self, node: WhileStmtNode):
        cond_bb = self.current_func.append_basic_block(name="while.cond")
        body_bb = self.current_func.append_basic_block(name="while.body")
        end_bb = self.current_func.append_basic_block(name="while.end")

        self.builder.branch(cond_bb)

        self.builder.position_at_end(cond_bb)
        cond_val = self.visit(node.condition)
        self.builder.cbranch(cond_val, body_bb, end_bb)

        self.builder.position_at_end(body_bb)
        self.push_scope()
        for stmt in node.body:
            if self.builder.block.is_terminated:
                break
            self.visit(stmt)
        self.pop_scope()
        
        if not self.builder.block.is_terminated:
            self.builder.branch(cond_bb)

        self.builder.position_at_end(end_bb)

    def visit_ReturnStmtNode(self, node: ReturnStmtNode):
        val = self.visit(node.expr)
        ret_type = self.current_func.return_value.type
        val = self.cast_if_needed(val, ret_type)
        self.builder.ret(val)

    # ==========================================================================
    # ESPRESSIONI (EXPRESSIONS & BUILT-IN I/O)
    # ==========================================================================

    def visit_LiteralNode(self, node: LiteralNode):
        if node.literal_type == "int":
            return ir.Constant(ir.IntType(32), int(node.value))
        elif node.literal_type == "double":
            return ir.Constant(ir.DoubleType(), float(node.value))
        elif node.literal_type == "boolean":
            return ir.Constant(ir.IntType(1), 1 if node.value else 0)
        elif node.literal_type == "string":
            return self._get_or_create_global_string(str(node.value), "str_lit")
        raise ValueError(f"Tipo letterale non supportato: {node.literal_type}")

    def visit_VarRefNode(self, node: VarRefNode):
        ptr = self.lookup_var(node.name)
        return self.builder.load(ptr, name=node.name)

    def visit_BinOpNode(self, node: BinOpNode):
        left = self.visit(node.left)
        right = self.visit(node.right)

        if left.type == ir.DoubleType() or right.type == ir.DoubleType():
            left = self.cast_if_needed(left, ir.DoubleType())
            right = self.cast_if_needed(right, ir.DoubleType())
            is_double = True
        else:
            is_double = False

        op = node.op

        if op == "+":
            return self.builder.fadd(left, right, name="addtmp") if is_double else self.builder.add(left, right, name="addtmp")
        if op == "-":
            return self.builder.fsub(left, right, name="subtmp") if is_double else self.builder.sub(left, right, name="subtmp")
        if op == "*":
            return self.builder.fmul(left, right, name="multmp") if is_double else self.builder.mul(left, right, name="multmp")
        if op == "/":
            return self.builder.fdiv(left, right, name="divtmp") if is_double else self.builder.sdiv(left, right, name="divtmp")

        if op == "and":
            return self.builder.and_(left, right, name="andtmp")
        if op == "or":
            return self.builder.or_(left, right, name="ortmp")

        if is_double:
            cmp_map = {"==": "==", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">="}
            return self.builder.fcmp_ordered(cmp_map[op], left, right, name="cmptmp")
        else:
            return self.builder.icmp_signed(op, left, right, name="cmptmp")

    def visit_UnOpNode(self, node: UnOpNode):
        val = self.visit(node.expr)
        if node.op == "-":
            if val.type == ir.DoubleType():
                return self.builder.fsub(ir.Constant(ir.DoubleType(), 0.0), val, name="negtmp")
            return self.builder.sub(ir.Constant(ir.IntType(32), 0), val, name="negtmp")
        if node.op == "not":
            return self.builder.not_(val, name="nottmp")

    def visit_FunCallNode(self, node: FunCallNode):
        if node.name == "print_int":
            fmt_ptr = self._get_or_create_global_string("%d\n", "fmt_pi")
            arg_val = self.visit(node.args[0])
            return self.builder.call(self.printf, [fmt_ptr, arg_val], name="print_int_res")

        if node.name == "print_double":
            fmt_ptr = self._get_or_create_global_string("%.2f\n", "fmt_pd")
            arg_val = self.visit(node.args[0])
            arg_val = self.cast_if_needed(arg_val, ir.DoubleType())
            return self.builder.call(self.printf, [fmt_ptr, arg_val], name="print_dbl_res")

        if node.name == "print_string":
            fmt_ptr = self._get_or_create_global_string("%s\n", "fmt_ps")
            arg_val = self.visit(node.args[0])
            return self.builder.call(self.printf, [fmt_ptr, arg_val], name="print_str_res")

        if node.name == "read_int":
            fmt_ptr = self._get_or_create_global_string("%d", "fmt_ri")
            ptr = self.create_entry_block_alloca(ir.IntType(32), name="read_int_ptr")
            self.builder.call(self.scanf, [fmt_ptr, ptr])
            return self.builder.load(ptr, name="int_input")

        if node.name == "read_double":
            fmt_ptr = self._get_or_create_global_string("%lf", "fmt_rd")
            ptr = self.create_entry_block_alloca(ir.DoubleType(), name="read_dbl_ptr")
            self.builder.call(self.scanf, [fmt_ptr, ptr])
            return self.builder.load(ptr, name="dbl_input")

        func = self.functions[node.name]
        args = []
        for i, arg_node in enumerate(node.args):
            arg_val = self.visit(arg_node)
            param_type = func.args[i].type
            arg_val = self.cast_if_needed(arg_val, param_type)
            args.append(arg_val)
        return self.builder.call(func, args, name=f"{node.name}_call")

    def cast_if_needed(self, val, target_type):
        if val.type == ir.IntType(32) and target_type == ir.DoubleType():
            return self.builder.sitofp(val, ir.DoubleType(), name="cast_double")
        return val