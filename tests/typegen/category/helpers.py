import libcst as cst


class ParameterHintRemover(cst.CSTTransformer):
    def leave_Param(self, _: cst.Param, updated_node: cst.Param) -> cst.Param:
        return updated_node.with_changes(annotation=None)
