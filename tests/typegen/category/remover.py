import libcst as cst


class ParameterHintRemover(cst.CSTTransformer):
    def leave_Param(self, _: cst.Param, updated_node: cst.Param) -> cst.Param:
        return updated_node.with_changes(annotation=None)


class ReturnHintRemover(cst.CSTTransformer):
    def leave_FunctionDef(
        self, _: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        return updated_node.with_changes(returns=None)


class AssignHintRemover(cst.CSTTransformer):
    def leave_AnnAssign(
        self, _: cst.AnnAssign, updated_node: cst.AnnAssign
    ) -> cst.BaseSmallStatement | cst.RemovalSentinel:
        if updated_node.value is None:
            return cst.RemoveFromParent()

        return cst.Assign(
            targets=[cst.AssignTarget(updated_node.target)], value=updated_node.value
        )
