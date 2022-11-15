import logging
import libcst as cst
import libcst.codemod as codemod

import pandas as pd


class AnnotationProvider(codemod.ContextAwareTransformer):
    def __init__(self, context: codemod.CodemodContext, traced: pd.DataFrame) -> None:
        super().__init__(context=context)
        self.traced = traced

        self.logger = logging.getLogger(self.__class__.__qualname__)

    def _create_annotation(self, vartype: str) -> cst.Annotation:
        return cst.Annotation(annotation=cst.parse_expression(vartype))
