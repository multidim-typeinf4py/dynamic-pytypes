from __future__ import annotations

from dataclasses import dataclass, field
import pathlib
import operator

from common import TraceDataCategory

import pandas as pd

from constants import Column, Schema


@dataclass
class TraceUpdateOverride:
    # The file name in which the variables are declared
    file_name: pathlib.Path | None = None

    # Module of the class the variable is in
    class_module: str | None = None

    # Name of the class the variable is in
    class_name: str | None = None

    # The function which declares the variable
    function_name: str | None = None

    # The line number
    line_number: int | None = None


@dataclass(frozen=True)
class TraceUpdate:
    """
    A simple dataclass holding the contents of a singular update

    :params file_name: The file name in which the variables are declared
    :params class_module: Module of the class the variable is in
    :params class_name: Name of the class the variable is in
    :params function_name: The function which declares the variable
    :params line_number: The line number
    :params category: The data category of the row
    :params names2types: A dictionary containing the variable name, the type's module and the type's name

    """

    # The file name in which the variables are declared
    file_name: pathlib.Path

    # Module of the class the variable is in
    class_module: str | None

    # Name of the class the variable is in
    class_name: str | None

    # The function which declares the variable
    function_name: str | None

    # The line number
    line_number: int

    # The data category of the row
    category: TraceDataCategory

    # A dictionary containing the variable name, the type's module and the type's name
    names2types: dict[str, tuple[str | None, str]]


@dataclass
class TraceBatch:
    """
    A builder-pattern style interface for each relevant category, allowing updates to be chained as each event requires.
    After all updates have been handled, a DataFrame can be produced that is to added to the otherwise accumulated trace data.

    The constructor accepts values that are used by default to create instances of `TraceUpdate`,
    unless overwritten by an argument in one of the builder methods.

    `dict[str, tuple[str | None, str]]` is a map of identifiers to (module name, type name).
    The module_name is None if the type is builtin, such as int, str, float etc.

    :params file_name: The file name in which the variables are declared
    :params class_module: Module of the class the variable is in
    :params class_name: Name of the class the variable is in
    :params function_name: The function which declares the variable
    :params line_number: The line number
    """

    file_name: pathlib.Path
    class_module: str | None
    class_name: str | None
    function_name: str
    line_number: int

    _updates: list[TraceUpdate] = field(default_factory=list)

    def local_variables(
        self,
        line_number: int,
        names2types: dict[str, tuple[str | None, str]],
        override: TraceUpdateOverride | None = None,
    ) -> TraceBatch:
        """
        Create an update consisting of local variables

        :params line_number: Because the line number that a variable is written on is not the same
            as the one it is put on the stack, this must be manually specified
        :params names2types: Names of local variables mapped to the module and type names of their types
        :params override: Replace default values specified in constructor hereby
        :returns: A reference to newly updated batch
        """
        if override is not None:
            assert (
                override.line_number is None
            ), f"Cannot specify `line_number` twice in {self.local_variables.__name__}; Found {line_number=} as an argument, and {override.line_number=} as an override"

        override = override or TraceUpdateOverride()
        override.line_number = override.line_number or line_number

        update = self._build_update(
            names2types, category=TraceDataCategory.LOCAL_VARIABLE, override=override
        )
        if update:
            self._updates.append(update)

        return self

    def global_variables(
        self,
        names2types: dict[str, tuple[str | None, str]],
        override: TraceUpdateOverride | None = None,
    ) -> TraceBatch:
        """
        Create an update consisting of global variables.
        Because they are stateful, their line number is always 0, and can only be
        differentiated by their name and the file they occur in

        :params names2types: Names of global variables mapped to the module and type names of their types
        :params override: Replace default values specified in constructor hereby
        :returns: A reference to newly updated batch
        """
        override = override or TraceUpdateOverride()
        override.line_number = override.line_number or 0

        update = self._build_update(
            names2types,
            category=TraceDataCategory.GLOBAL_VARIABLE,
            override=override,
        )
        if update:
            self._updates.append(update)

        return self

    def returns(
        self,
        names2types: dict[str, tuple[str | None, str]],
        override: TraceUpdateOverride | None = None,
    ) -> TraceBatch:
        """
        Create an update consisting of return types from functions.
        Their line number is always 0, so that unifiers can group them together appropriately later.

        :params names2types: Names of functions mapped to the module and type name of their return types
        :params override: Replace default values specified in constructor hereby
        :returns: A reference to newly updated batch
        """
        override = override or TraceUpdateOverride()
        override.line_number = override.line_number or 0
        update = self._build_update(
            names2types,
            category=TraceDataCategory.CALLABLE_RETURN,
            override=override,
        )
        if update:
            self._updates.append(update)

        return self

    def parameters(
        self,
        names2types: dict[str, tuple[str | None, str]],
        override: TraceUpdateOverride | None = None,
    ) -> TraceBatch:
        """
        Create an update consisting of parameters for a callable.

        :params names2types: Names of the parameters to a callable mapped to the module and type names of their types
        :params override: Replace default values specified in constructor hereby
        :returns: A reference to newly updated batch
        """
        override = override or TraceUpdateOverride()
        override.line_number = override.line_number or self.line_number
        update = self._build_update(
            names2types,
            category=TraceDataCategory.CALLABLE_PARAMETER,
            override=override,
        )
        if update:
            self._updates.append(update)

        return self

    def members(
        self,
        names2types: dict[str, tuple[str | None, str]],
        override: TraceUpdateOverride | None = None,
    ) -> TraceBatch:
        """
        Create an update consisting of attributes of a class.
        Because they are stateful, their line number is always 0, and can only be
        differentiated by the file they occur in, their identifier and the class they occur in

        :params names2types: Names of the members of a class mapped to the module and type names of their types
        :params override: Replace default values specified in constructor hereby
        :returns: A reference to newly updated batch
        """
        override = override or TraceUpdateOverride()

        override.line_number = override.line_number or 0

        update = self._build_update(
            names2types, category=TraceDataCategory.CLASS_MEMBER, override=override
        )
        if update:
            self._updates.append(update)

        return self

    def to_frame(self) -> pd.DataFrame:
        """
        Consume this batch of updates in order to produce a DataFrame.

        :params self: Nothing else :)
        :returns: A DataFrame encompassing the entire batch
        """
        updates = list()
        for update in self._updates:
            names2types = update.names2types
            varnames = list(names2types.keys())
            vartype_modules = list(map(operator.itemgetter(0), names2types.values()))
            vartypes = list(map(operator.itemgetter(1), names2types.values()))

            update_dict = {
                Column.FILENAME: [str(update.file_name)] * len(varnames),
                Column.CLASS_MODULE: [update.class_module] * len(varnames),
                Column.CLASS: [update.class_name] * len(varnames),
                Column.FUNCNAME: [update.function_name] * len(varnames),
                Column.LINENO: [update.line_number] * len(varnames),
                Column.CATEGORY: [update.category] * len(varnames),
                Column.VARNAME: varnames,
                Column.VARTYPE_MODULE: vartype_modules,
                Column.VARTYPE: vartypes,
            }
            update_df = pd.DataFrame(
                update_dict, columns=Schema.TraceData.keys()
            ).astype(Schema.TraceData)
            updates.append(update_df)

        if not updates:
            return pd.DataFrame(columns=Schema.TraceData.keys()).astype(
                Schema.TraceData
            )

        return pd.concat(updates, ignore_index=True).astype(Schema.TraceData)

    def _build_update(
        self,
        names2types: dict[str, tuple[str | None, str]],
        category: TraceDataCategory,
        override: TraceUpdateOverride,
    ) -> TraceUpdate | None:
        if not names2types:
            return None

        return TraceUpdate(
            file_name=override.file_name or self.file_name,
            class_module=override.class_module or self.class_module,
            class_name=override.class_name or self.class_name,
            function_name=override.function_name or self.function_name,
            line_number=override.line_number
            if override.line_number is not None
            else self.line_number,
            category=category,
            names2types=names2types,
        )
