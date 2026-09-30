class ASTNode:
    def __init__(self, line=None, column=None):
        self.line = line      
        self.column = column  


class StmtNode(ASTNode):
    pass


class ExprNode(ASTNode):
    def __init__(self, line=None, column=None):
        super().__init__(line, column)
        self.type = None  


class ProgramNode(ASTNode):
    def __init__(self, functions, line=None, column=None):
        super().__init__(line, column)
        self.functions = functions  

    def __repr__(self):
        return f"ProgramNode(functions={self.functions})"


class FuncDefNode(ASTNode):
    def __init__(self, name, params, return_type, body, line=None, column=None):
        super().__init__(line, column)
        self.name = name                
        self.params = params            
        self.return_type = return_type  
        self.body = body                

    def __repr__(self):
        return f"FuncDefNode(name='{self.name}', params={self.params}, return_type='{self.return_type}', body={self.body})"


class ParamNode(ASTNode):
    def __init__(self, name, param_type, line=None, column=None):
        super().__init__(line, column)
        self.name = name            
        self.param_type = param_type  

    def __repr__(self):
        return f"ParamNode(name='{self.name}', type='{self.param_type}')"


class VarDeclNode(StmtNode):
    def __init__(self, name, var_type, value=None, line=None, column=None):
        super().__init__(line, column)
        self.name = name          
        self.var_type = var_type  
        self.value = value        
        
    def __repr__(self):
        return f"VarDeclNode(name='{self.name}', type='{self.var_type}', value={self.value})"


class AssignmentNode(StmtNode):
    def __init__(self, name, expr, line=None, column=None):
        super().__init__(line, column)
        self.name = name  
        self.expr = expr  

    def __repr__(self):
        return f"AssignmentNode(target='{self.name}', expr={self.expr})"


class IfStmtNode(StmtNode):
    def __init__(self, condition, then_block, else_block=None, line=None, column=None):
        super().__init__(line, column)
        self.condition = condition    
        self.then_block = then_block  
        self.else_block = else_block  

    def __repr__(self):
        return f"IfStmtNode(cond={self.condition}, then={self.then_block}, else={self.else_block})"


class WhileStmtNode(StmtNode):
    def __init__(self, condition, body, line=None, column=None):
        super().__init__(line, column)
        self.condition = condition  
        self.body = body            

    def __repr__(self):
        return f"WhileStmtNode(cond={self.condition}, body={self.body})"


class ReturnStmtNode(StmtNode):
    def __init__(self, expr, line=None, column=None):
        super().__init__(line, column)
        self.expr = expr  

    def __repr__(self):
        return f"ReturnStmtNode(expr={self.expr})"


class BinOpNode(ExprNode):
    def __init__(self, op, left, right, line=None, column=None):
        super().__init__(line, column)
        self.op = op        
        self.left = left    
        self.right = right  

    def __repr__(self):
        return f"BinOpNode(op='{self.op}', left={self.left}, right={self.right})"


class UnOpNode(ExprNode):
    def __init__(self, op, expr, line=None, column=None):
        super().__init__(line, column)
        self.op = op      
        self.expr = expr  
        
    def __repr__(self):
        return f"UnOpNode(op='{self.op}', expr={self.expr})"


class LiteralNode(ExprNode):
    def __init__(self, value, literal_type, line=None, column=None):
        super().__init__(line, column)
        self.value = value                
        self.literal_type = literal_type  

    def __repr__(self):
        return f"LiteralNode(value={self.value}, type='{self.literal_type}')"


class VarRefNode(ExprNode):
    def __init__(self, name, line=None, column=None):
        super().__init__(line, column)
        self.name = name  

    def __repr__(self):
        return f"VarRefNode(name='{self.name}')"


class FunCallNode(ExprNode):
    def __init__(self, name, args, line=None, column=None):
        super().__init__(line, column)
        self.name = name  
        self.args = args  

    def __repr__(self):
        return f"FunCallNode(name='{self.name}', args={self.args})"