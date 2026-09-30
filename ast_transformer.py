from lark import Transformer
from ast_nodes import (
    ProgramNode, FuncDefNode, ParamNode, VarDeclNode, AssignmentNode,
    IfStmtNode, WhileStmtNode, ReturnStmtNode, BinOpNode, UnOpNode,
    LiteralNode, VarRefNode, FunCallNode, ExprNode
)

class TriaCASTTransformer(Transformer):
    def start(self, children):
        funcs = [c for c in children if isinstance(c, FuncDefNode)]
        return ProgramNode(funcs)

    def func_def(self, children):
        name_token = children[0]
        params = children[2] if children[2] is not None else []
        ret_type = children[4]
        body = children[5]
        return FuncDefNode(
            name=str(name_token),
            params=params,
            return_type=ret_type,
            body=body,
            line=name_token.line,
            column=name_token.column
        )

    def parameters(self, children):
        return children

    def param(self, children):
        name_token, param_type = children
        return ParamNode(
            name=str(name_token),
            param_type=param_type,
            line=name_token.line,
            column=name_token.column
        )
    
    def arguments(self, children):
        return children

    def type_int(self, _):
        return "int"

    def type_double(self, _):
        return "double"

    def type_bool(self, _):
        return "boolean"

    def block(self, children):
        return children

    def var_decl(self, children):
        name_token = children[0]
        var_type = children[1]
        value = children[2] if len(children) > 2 and children[2] is not None else None
        return VarDeclNode(
            name=str(name_token),
            var_type=var_type,
            value=value,
            line=name_token.line,
            column=name_token.column
        )

    def assignment(self, children):
        name_token, expr = children
        return AssignmentNode(
            name=str(name_token),
            expr=expr,
            line=name_token.line,
            column=name_token.column
        )

    def return_stmt(self, children):
        expr = children[0]
        line = expr.line if isinstance(expr, ExprNode) else None
        column = expr.column if isinstance(expr, ExprNode) else None
        return ReturnStmtNode(expr, line=line, column=column)

    def expr_stmt(self, children):
        return children[0]

    def while_stmt(self, children):
        cond = children[1]
        body = children[3]
        return WhileStmtNode(
            condition=cond,
            body=body,
            line=cond.line,
            column=cond.column
        )

    def if_stmt(self, children):
        cond = children[1]
        then_block = children[3]
        else_block = children[4] if len(children) > 4 else None
        return IfStmtNode(
            condition=cond,
            then_block=then_block,
            else_block=else_block,
            line=cond.line,
            column=cond.column
        )

    def or_op(self, children):
        if len(children) == 1:
            return children[0]
        node = children[0]
        for child in children[1:]:
            node = BinOpNode("or", node, child, line=node.line, column=node.column)
        return node

    def and_op(self, children):
        if len(children) == 1:
            return children[0]
        node = children[0]
        for child in children[1:]:
            node = BinOpNode("and", node, child, line=node.line, column=node.column)
        return node

    def comp_op(self, children):
        node = children[0]
        i = 1
        while i < len(children):
            op = str(children[i])
            right = children[i+1]
            node = BinOpNode(op, node, right, line=node.line, column=node.column)
            i += 2
        return node

    def add_op(self, children):
        node = children[0]
        i = 1
        while i < len(children):
            op = str(children[i])
            right = children[i+1]
            node = BinOpNode(op, node, right, line=node.line, column=node.column)
            i += 2
        return node

    def mul_op(self, children):
        node = children[0]
        i = 1
        while i < len(children):
            op = str(children[i])
            right = children[i+1]
            node = BinOpNode(op, node, right, line=node.line, column=node.column)
            i += 2
        return node

    def not_op(self, children):
        factor = children[0]
        return UnOpNode("not", factor, line=factor.line, column=factor.column)

    def neg_op(self, children):
        factor = children[0]
        return UnOpNode("-", factor, line=factor.line, column=factor.column)

    def fun_call(self, children):
        name_token = children[0]
        args = children[2] if children[2] is not None else []
        return FunCallNode(
            name=str(name_token),
            args=args,
            line=name_token.line,
            column=name_token.column
        )

    def var_ref(self, children):
        name_token = children[0]
        return VarRefNode(
            name=str(name_token),
            line=name_token.line,
            column=name_token.column
        )

    def paren_expr(self, children):
        return children[1]

    def int_lit(self, children):
        token = children[0]
        return LiteralNode(int(token), "int", line=token.line, column=token.column)

    def double_lit(self, children):
        token = children[0]
        return LiteralNode(float(token), "double", line=token.line, column=token.column)

    def true_lit(self, children):
        line = children[0].line if children else None
        column = children[0].column if children else None
        return LiteralNode(True, "boolean", line=line, column=column)

    def false_lit(self, children):
        line = children[0].line if children else None
        column = children[0].column if children else None
        return LiteralNode(False, "boolean", line=line, column=column)

    def string_lit(self, children):
        token = children[0]
        val = str(token)[1:-1]  
        return LiteralNode(val, "string", line=token.line, column=token.column)