import logging
import libcst as cst
import libcst.codemod as codemod

import pandas as pd

from constants import Column

def _create_annotation(vartype: str) -> cst.Annotation:
    return cst.Annotation(annotation=cst.parse_expression(vartype))

class AnnotationProvider(codemod.ContextAwareTransformer):
    def __init__(self, context: codemod.CodemodContext, traced: pd.DataFrame) -> None:
        super().__init__(context=context)
        if self.context.filename:
            self.traced = traced[traced[Column.FILENAME] == self.context.filename]
        else:
            self.traced = traced

        self.logger = logging.getLogger(self.__class__.__qualname__)