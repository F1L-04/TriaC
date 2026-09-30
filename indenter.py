from lark.indenter import Indenter

class TriaCIndenter(Indenter):
    @property
    def NL_type(self) -> str:
        return "_NEWLINE"

    @property
    def INDENT_type(self) -> str:
        return "_INDENT"

    @property
    def DEDENT_type(self) -> str:
        return "_DEDENT"

    @property
    def OPEN_PAREN_types(self) -> list[str]:
        return ['LPAR']

    @property
    def CLOSE_PAREN_types(self) -> list[str]:
        return ['RPAR']

    @property
    def tab_len(self) -> int:
        return 4
