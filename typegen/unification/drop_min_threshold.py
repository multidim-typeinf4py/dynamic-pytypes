import pandas as pd

from .filter_base import TraceDataFilter

from constants import Column, Schema


class MinThresholdFilter(TraceDataFilter):
    """Drops all rows whose types appear less often than the minimum threshold."""

    COUNT_COLUMN = "count"
    MAX_COUNT_COLUMN = "max_count"

    ident = "drop_min_threshold"

    min_threshold: float = 0.25

    def apply(self, trace_data: pd.DataFrame) -> pd.DataFrame:
        subset = list(Schema.TraceData.keys())
        grouped_trace_data = (
            trace_data.groupby(subset, dropna=False)[Column.VARTYPE]
            .count()
            .reset_index(name=MinThresholdFilter.COUNT_COLUMN)
        )
        joined_trace_data = pd.merge(
            trace_data, grouped_trace_data, on=subset, how="inner"
        )
        subset.remove(Column.VARTYPE_MODULE)
        subset.remove(Column.VARTYPE)

        grouped_trace_data = (
            joined_trace_data.groupby(subset, dropna=False)[
                MinThresholdFilter.COUNT_COLUMN
            ]
            .max()
            .reset_index(name=MinThresholdFilter.MAX_COUNT_COLUMN)
        )

        joined_trace_data = pd.merge(
            joined_trace_data, grouped_trace_data, on=subset, how="inner"
        )

        indices = (
            joined_trace_data[MinThresholdFilter.COUNT_COLUMN]
            / joined_trace_data[MinThresholdFilter.MAX_COUNT_COLUMN]
            > self.min_threshold
        )
        processed_data = joined_trace_data[indices]
        processed_data = processed_data.drop(
            [MinThresholdFilter.COUNT_COLUMN, MinThresholdFilter.MAX_COUNT_COLUMN],
            axis=1,
        )
        return processed_data.reset_index(drop=True).astype(Schema.TraceData)
