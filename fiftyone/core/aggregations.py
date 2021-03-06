"""
Aggregations.

| Copyright 2017-2021, Voxel51, Inc.
| `voxel51.com <https://voxel51.com/>`_
|
"""
import numpy as np

import eta.core.utils as etau

import fiftyone.core.expressions as foe
import fiftyone.core.media as fom


class Aggregation(object):
    """Abstract base class for all aggregations.

    :class:`Aggregation` instances represent an aggregation or reduction
    of a :class:`fiftyone.core.collections.SampleCollection` instance.

    Args:
        field_name: the name of the field to operate on
        expr (None): an optional
            :class:`fiftyone.core.expressions.ViewExpression` or
            `MongoDB expression <https://docs.mongodb.com/manual/meta/aggregation-quick-reference/#aggregation-expressions>`_
            to apply to the field before aggregating
    """

    def __init__(self, field_name, expr=None):
        self._field_name = field_name
        self._expr = expr

    @property
    def field_name(self):
        """The field name being computed on."""
        return self._field_name

    @property
    def expr(self):
        """The :class:`fiftyone.core.expressions.ViewExpression` or MongoDB
        expression that will be applied to the field before aggregating, if any.
        """
        return self._expr

    def to_mongo(self, sample_collection):
        """Returns the MongoDB aggregation pipeline for this aggregation.

        Args:
            sample_collection: the
                :class:`fiftyone.core.collections.SampleCollection` to which
                the aggregation is being applied

        Returns:
            a MongoDB aggregation pipeline (list of dicts)
        """
        raise NotImplementedError("subclasses must implement to_mongo()")

    def parse_result(self, d):
        """Parses the output of :meth:`to_mongo`.

        Args:
            d: the result dict

        Returns:
            the aggregation result
        """
        raise NotImplementedError("subclasses must implement parse_result()")

    def default_result(self):
        """Returns the default result for this aggregation.

        Returns:
            the aggregation result
        """
        raise NotImplementedError("subclasses must implement default_result()")

    def _parse_field_name(self, sample_collection):
        return _parse_field_name(
            sample_collection, self._field_name, expr=self._expr
        )


class AggregationError(Exception):
    """An error raised during the execution of an :class:`Aggregation`."""

    pass


class Bounds(Aggregation):
    """Computes the bounds of a numeric field of a collection.

    ``None``-valued fields are ignored.

    This aggregation is typically applied to *numeric* field types (or lists of
    such types):

    -   :class:`fiftyone.core.fields.IntField`
    -   :class:`fiftyone.core.fields.FloatField`

    Examples::

        import fiftyone as fo
        from fiftyone import ViewField as F

        dataset = fo.Dataset()
        dataset.add_samples(
            [
                fo.Sample(
                    filepath="/path/to/image1.png",
                    numeric_field=1.0,
                    numeric_list_field=[1, 2, 3],
                ),
                fo.Sample(
                    filepath="/path/to/image2.png",
                    numeric_field=4.0,
                    numeric_list_field=[1, 2],
                ),
                fo.Sample(
                    filepath="/path/to/image3.png",
                    numeric_field=None,
                    numeric_list_field=None,
                ),
            ]
        )

        #
        # Compute the bounds of a numeric field
        #

        aggregation = fo.Bounds("numeric_field")
        bounds = dataset.aggregate(aggregation)
        print(bounds)  # (min, max)

        #
        # Compute the a bounds of a numeric list field
        #

        aggregation = fo.Bounds("numeric_list_field")
        bounds = dataset.aggregate(aggregation)
        print(bounds)  # (min, max)

        #
        # Compute the bounds of a transformation of a numeric field
        #

        aggregation = fo.Bounds("numeric_field", expr=2 * (F() + 1))
        bounds = dataset.aggregate(aggregation)
        print(bounds)  # (min, max)

    Args:
        field_name: the name of the field to operate on
        expr (None): an optional
            :class:`fiftyone.core.expressions.ViewExpression` or
            `MongoDB expression <https://docs.mongodb.com/manual/meta/aggregation-quick-reference/#aggregation-expressions>`_
            to apply to the field before aggregating
    """

    def default_result(self):
        """Returns the default result for this aggregation.

        Returns:
            ``(None, None)``
        """
        return None, None

    def parse_result(self, d):
        """Parses the output of :meth:`to_mongo`.

        Args:
            d: the result dict

        Returns:
            the ``(min, max)`` bounds
        """
        return d["min"], d["max"]

    def to_mongo(self, sample_collection):
        path, pipeline = self._parse_field_name(sample_collection)

        pipeline.append(
            {
                "$group": {
                    "_id": None,
                    "min": {"$min": "$" + path},
                    "max": {"$max": "$" + path},
                }
            }
        )

        return pipeline


class Count(Aggregation):
    """Counts the number of field values in a collection.

    ``None``-valued fields are ignored.

    If no field is provided, the samples themselves are counted.

    Examples::

        import fiftyone as fo

        dataset = fo.Dataset()
        dataset.add_samples(
            [
                fo.Sample(
                    filepath="/path/to/image1.png",
                    predictions=fo.Detections(
                        detections=[
                            fo.Detection(label="cat"),
                            fo.Detection(label="dog"),
                        ]
                    ),
                ),
                fo.Sample(
                    filepath="/path/to/image2.png",
                    predictions=fo.Detections(
                        detections=[
                            fo.Detection(label="cat"),
                            fo.Detection(label="rabbit"),
                            fo.Detection(label="squirrel"),
                        ]
                    ),
                ),
                fo.Sample(
                    filepath="/path/to/image3.png",
                    predictions=None,
                ),
            ]
        )

        #
        # Count the number of samples in the dataset
        #

        aggregation = fo.Count()
        count = dataset.aggregate(aggregation)
        print(count)  # the count

        #
        # Count the number of samples with `predictions`
        #

        aggregation = fo.Count("predictions")
        count = dataset.aggregate(aggregation)
        print(count)  # the count

        #
        # Count the number of objects in the `predictions` field
        #

        aggregation = fo.Count("predictions.detections")
        count = dataset.aggregate(aggregation)
        print(count)  # the count

        #
        # Count the number of samples with more than 2 predictions
        #

        expr = (F("detections").length() > 2).if_else(F("detections"), None)
        aggregation = fo.Count("predictions", expr=expr)
        count = dataset.aggregate(aggregation)
        print(count)  # the count

    Args:
        field_name (None): the name of the field to operate on. If none is
            provided, the samples themselves are counted
        expr (None): an optional
            :class:`fiftyone.core.expressions.ViewExpression` or
            `MongoDB expression <https://docs.mongodb.com/manual/meta/aggregation-quick-reference/#aggregation-expressions>`_
            to apply to the field before aggregating
    """

    def __init__(self, field_name=None, expr=None):
        super().__init__(field_name, expr=expr)

    def default_result(self):
        """Returns the default result for this aggregation.

        Returns:
            ``0``
        """
        return 0

    def parse_result(self, d):
        """Parses the output of :meth:`to_mongo`.

        Args:
            d: the result dict

        Returns:
            the count
        """
        return d["count"]

    def to_mongo(self, sample_collection):
        if self._field_name is None:
            return [{"$count": "count"}]

        path, pipeline = self._parse_field_name(sample_collection)

        if sample_collection.media_type != fom.VIDEO or path != "frames":
            pipeline.append({"$match": {"$expr": {"$gt": ["$" + path, None]}}})

        pipeline.append({"$count": "count"})

        return pipeline


class CountValues(Aggregation):
    """Counts the occurrences of field values in a collection.

    This aggregation is typically applied to *countable* field types (or lists
    of such types):

    -   :class:`fiftyone.core.fields.BooleanField`
    -   :class:`fiftyone.core.fields.IntField`
    -   :class:`fiftyone.core.fields.StringField`

    Examples::

        import fiftyone as fo

        dataset = fo.Dataset()
        dataset.add_samples(
            [
                fo.Sample(
                    filepath="/path/to/image1.png",
                    tags=["sunny"],
                    predictions=fo.Detections(
                        detections=[
                            fo.Detection(label="cat"),
                            fo.Detection(label="dog"),
                        ]
                    ),
                ),
                fo.Sample(
                    filepath="/path/to/image2.png",
                    tags=["cloudy"],
                    predictions=fo.Detections(
                        detections=[
                            fo.Detection(label="cat"),
                            fo.Detection(label="rabbit"),
                        ]
                    ),
                ),
                fo.Sample(
                    filepath="/path/to/image3.png",
                    predictions=None,
                ),
            ]
        )

        #
        # Compute the tag counts in the dataset
        #

        aggregation = fo.CountValues("tags")
        counts = dataset.aggregate(aggregation)
        print(counts)  # dict mapping values to counts

        #
        # Compute the predicted label counts in the dataset
        #

        aggregation = fo.CountValues("predictions.detections.label")
        counts = dataset.aggregate(aggregation)
        print(counts)  # dict mapping values to counts

        #
        # Compute the predicted label counts after some normalization
        #

        expr = F().map_values({"cat": "pet", "dog": "pet"}).upper()
        aggregation = fo.CountValues("predictions.detections.label", expr=expr)
        counts = dataset.aggregate(aggregation)
        print(counts)  # dict mapping values to counts

    Args:
        field_name: the name of the field to operate on
        expr (None): an optional
            :class:`fiftyone.core.expressions.ViewExpression` or
            `MongoDB expression <https://docs.mongodb.com/manual/meta/aggregation-quick-reference/#aggregation-expressions>`_
            to apply to the field before aggregating
    """

    def default_result(self):
        """Returns the default result for this aggregation.

        Returns:
            ``{}``
        """
        return {}

    def parse_result(self, d):
        """Parses the output of :meth:`to_mongo`.

        Args:
            d: the result dict

        Returns:
            a dict mapping values to counts
        """
        return {i["k"]: i["count"] for i in d["result"]}

    def to_mongo(self, sample_collection):
        path, pipeline = self._parse_field_name(sample_collection)

        pipeline += [
            {"$group": {"_id": "$" + path, "count": {"$sum": 1}}},
            {
                "$group": {
                    "_id": None,
                    "result": {"$push": {"k": "$_id", "count": "$count"}},
                }
            },
        ]

        return pipeline


class Distinct(Aggregation):
    """Computes the distinct values of a field in a collection.

    ``None``-valued fields are ignored.

    This aggregation is typically applied to *countable* field types (or lists
    of such types):

    -   :class:`fiftyone.core.fields.BooleanField`
    -   :class:`fiftyone.core.fields.IntField`
    -   :class:`fiftyone.core.fields.StringField`

    Examples::

        import fiftyone as fo

        dataset = fo.Dataset()
        dataset.add_samples(
            [
                fo.Sample(
                    filepath="/path/to/image1.png",
                    tags=["sunny"],
                    predictions=fo.Detections(
                        detections=[
                            fo.Detection(label="cat"),
                            fo.Detection(label="dog"),
                        ]
                    ),
                ),
                fo.Sample(
                    filepath="/path/to/image2.png",
                    tags=["sunny", "cloudy"],
                    predictions=fo.Detections(
                        detections=[
                            fo.Detection(label="cat"),
                            fo.Detection(label="rabbit"),
                        ]
                    ),
                ),
                fo.Sample(
                    filepath="/path/to/image3.png",
                    predictions=None,
                ),
            ]
        )

        #
        # Get the distinct tags in a dataset
        #

        aggregation = fo.Distinct("tags")
        values = dataset.aggregate(aggregation)
        print(values)  # list of distinct values

        #
        # Get the distinct predicted labels in a dataset
        #

        aggregation = fo.Distinct("predictions.detections.label")
        values = dataset.aggregate(aggregation)
        print(values)  # list of distinct values

        #
        # Get the distinct predicted labels after some normalization
        #

        expr = F().map_values({"cat": "pet", "dog": "pet"}).upper()
        aggregation = fo.Distinct("predictions.detections.label", expr=expr)
        values = dataset.aggregate(aggregation)
        print(values)  # list of distinct values

    Args:
        field_name: the name of the field to operate on
        expr (None): an optional
            :class:`fiftyone.core.expressions.ViewExpression` or
            `MongoDB expression <https://docs.mongodb.com/manual/meta/aggregation-quick-reference/#aggregation-expressions>`_
            to apply to the field before aggregating
    """

    def default_result(self):
        """Returns the default result for this aggregation.

        Returns:
            ``[]``
        """
        return []

    def parse_result(self, d):
        """Parses the output of :meth:`to_mongo`.

        Args:
            d: the result dict

        Returns:
            a sorted list of distinct values
        """
        return sorted(d["values"])

    def to_mongo(self, sample_collection):
        path, pipeline = self._parse_field_name(sample_collection)

        pipeline += [
            {"$match": {"$expr": {"$gt": ["$" + path, None]}}},
            {"$group": {"_id": None, "values": {"$addToSet": "$" + path}}},
        ]

        return pipeline


class HistogramValues(Aggregation):
    """Computes a histogram of the field values in a collection.

    This aggregation is typically applied to *numeric* field types (or
    lists of such types):

    -   :class:`fiftyone.core.fields.IntField`
    -   :class:`fiftyone.core.fields.FloatField`

    Examples::

        import numpy as np
        import matplotlib.pyplot as plt

        import fiftyone as fo

        samples = []
        for idx in range(100):
            samples.append(
                fo.Sample(
                    filepath="/path/to/image%d.png" % idx,
                    numeric_field=np.random.randn(),
                    numeric_list_field=list(np.random.randn(10)),
                )
            )

        dataset = fo.Dataset()
        dataset.add_samples(samples)

        def plot_hist(counts, edges):
            counts = np.asarray(counts)
            edges = np.asarray(edges)
            left_edges = edges[:-1]
            widths = edges[1:] - edges[:-1]
            plt.bar(left_edges, counts, width=widths, align="edge")

        #
        # Compute a histogram of a numeric field
        #

        aggregation = fo.HistogramValues("numeric_field", bins=50)
        counts, edges, other = dataset.aggregate(aggregation)

        plot_hist(counts, edges)
        plt.show(block=False)

        #
        # Compute the histogram of a numeric list field
        #

        aggregation = fo.HistogramValues("numeric_list_field", bins=50)
        counts, edges, other = dataset.aggregate(aggregation)

        plot_hist(counts, edges)
        plt.show(block=False)

        #
        # Compute the histogram of a transformation of a numeric field
        #

        aggregation = fo.HistogramValues(
            "numeric_field", expr=2 * (F() + 1), bins=50
        )
        counts, edges, other = dataset.aggregate(aggregation)

        plot_hist(counts, edges)
        plt.show(block=False)

    Args:
        field_name: the name of the field to operate on
        expr (None): an optional
            :class:`fiftyone.core.expressions.ViewExpression` or
            `MongoDB expression <https://docs.mongodb.com/manual/meta/aggregation-quick-reference/#aggregation-expressions>`_
            to apply to the field before aggregating
        bins (None): can be either an integer number of bins to generate or a
            monotonically increasing sequence specifying the bin edges to use.
            By default, 10 bins are created. If ``bins`` is an integer and no
            ``range`` is specified, bin edges are automatically computed from
            the bounds of the field
        range (None): a ``(lower, upper)`` tuple specifying a range in which to
            generate equal-width bins. Only applicable when ``bins`` is an
            integer or ``None``
        auto (False): whether to automatically choose bin edges in an attempt
            to evenly distribute the counts in each bin. If this option is
            chosen, ``bins`` will only be used if it is an integer, and the
            ``range`` parameter is ignored
    """

    def __init__(
        self, field_name, expr=None, bins=None, range=None, auto=False
    ):
        super().__init__(field_name, expr=expr)
        self._bins = bins
        self._range = range
        self._auto = auto

        self._num_bins = None
        self._edges = None
        self._edges_last_used = None
        self._parse_args()

    def default_result(self):
        """Returns the default result for this aggregation.

        Returns:
            a tuple of

            -   counts: ``[]``
            -   edges: ``[]``
            -   other: ``0``
        """
        return [], [], 0

    def parse_result(self, d):
        """Parses the output of :meth:`to_mongo`.

        Args:
            d: the result dict

        Returns:
            a tuple of

            -   counts: a list of counts in each bin
            -   edges: an increasing list of bin edges of length
                ``len(counts) + 1``. Note that each bin is treated as having an
                inclusive lower boundary and exclusive upper boundary,
                ``[lower, upper)``, including the rightmost bin
            -   other: the number of items outside the bins
        """
        if self._auto:
            return self._parse_result_auto(d)

        return self._parse_result_edges(d)

    def to_mongo(self, sample_collection):
        path, pipeline = self._parse_field_name(sample_collection)

        if self._auto:
            pipeline.append(
                {
                    "$bucketAuto": {
                        "groupBy": "$" + path,
                        "buckets": self._num_bins,
                        "output": {"count": {"$sum": 1}},
                    }
                }
            )
        else:
            if self._edges is not None:
                edges = self._edges
            else:
                edges = self._compute_bin_edges(sample_collection)

            self._edges_last_used = edges
            pipeline.append(
                {
                    "$bucket": {
                        "groupBy": "$" + path,
                        "boundaries": edges,
                        "default": "other",  # counts documents outside of bins
                        "output": {"count": {"$sum": 1}},
                    }
                }
            )

        pipeline.append({"$group": {"_id": None, "bins": {"$push": "$$ROOT"}}})

        return pipeline

    def _parse_args(self):
        if self._bins is None:
            bins = 10
        else:
            bins = self._bins

        if self._auto:
            if etau.is_numeric(bins):
                self._num_bins = bins
            else:
                self._num_bins = 10

            return

        if not etau.is_numeric(bins):
            # User-provided bin edges
            self._edges = list(bins)
            return

        if self._range is not None:
            # Linearly-spaced bins within `range`
            self._edges = list(
                np.linspace(self._range[0], self._range[1], bins + 1)
            )
        else:
            # Compute bin edges from bounds
            self._num_bins = bins

    def _compute_bin_edges(self, sample_collection):
        bounds = sample_collection.bounds(self._field_name, expr=self._expr)
        return list(
            np.linspace(bounds[0], bounds[1] + 1e-6, self._num_bins + 1)
        )

    def _parse_result_edges(self, d):
        _edges_array = np.array(self._edges_last_used)
        edges = list(_edges_array)
        counts = [0] * (len(edges) - 1)
        other = 0
        for di in d["bins"]:
            left = di["_id"]
            if left == "other":
                other = di["count"]
            else:
                idx = np.abs(_edges_array - left).argmin()
                counts[idx] = di["count"]

        return counts, edges, other

    def _parse_result_auto(self, d):
        counts = []
        edges = []
        for di in d["bins"]:
            counts.append(di["count"])
            edges.append(di["_id"]["min"])

        edges.append(di["_id"]["max"])

        return counts, edges, 0


class Mean(Aggregation):
    """Computes the arithmetic mean of the field values of a collection.

    ``None``-valued fields are ignored.

    This aggregation is typically applied to *numeric* field types (or lists of
    such types):

    -   :class:`fiftyone.core.fields.IntField`
    -   :class:`fiftyone.core.fields.FloatField`

    Examples::

        import fiftyone as fo

        dataset = fo.Dataset()
        dataset.add_samples(
            [
                fo.Sample(
                    filepath="/path/to/image1.png",
                    numeric_field=1.0,
                    numeric_list_field=[1, 2, 3],
                ),
                fo.Sample(
                    filepath="/path/to/image2.png",
                    numeric_field=4.0,
                    numeric_list_field=[1, 2],
                ),
                fo.Sample(
                    filepath="/path/to/image3.png",
                    numeric_field=None,
                    numeric_list_field=None,
                ),
            ]
        )

        #
        # Compute the mean of a numeric field
        #

        aggregation = fo.Mean("numeric_field")
        mean = dataset.aggregate(aggregation)
        print(mean)  # the mean

        #
        # Compute the mean of a numeric list field
        #

        aggregation = fo.Mean("numeric_list_field")
        mean = dataset.aggregate(aggregation)
        print(mean)  # the mean

        #
        # Compute the mean of a transformation of a numeric field
        #

        aggregation = fo.Mean("numeric_field", expr=2 * (F() + 1))
        mean = dataset.aggregate(aggregation)
        print(mean)  # the mean

    Args:
        field_name: the name of the field to operate on
        expr (None): an optional
            :class:`fiftyone.core.expressions.ViewExpression` or
            `MongoDB expression <https://docs.mongodb.com/manual/meta/aggregation-quick-reference/#aggregation-expressions>`_
            to apply to the field before aggregating
    """

    def default_result(self):
        """Returns the default result for this aggregation.

        Returns:
            ``0``
        """
        return 0

    def parse_result(self, d):
        """Parses the output of :meth:`to_mongo`.

        Args:
            d: the result dict

        Returns:
            the mean
        """
        return d["mean"]

    def to_mongo(self, sample_collection):
        path, pipeline = self._parse_field_name(sample_collection)

        pipeline.append(
            {"$group": {"_id": None, "mean": {"$avg": "$" + path}}}
        )

        return pipeline


class Std(Aggregation):
    """Computes the standard deviation of the field values of a collection.

    ``None``-valued fields are ignored.

    This aggregation is typically applied to *numeric* field types (or lists of
    such types):

    -   :class:`fiftyone.core.fields.IntField`
    -   :class:`fiftyone.core.fields.FloatField`

    Examples::

        import fiftyone as fo

        dataset = fo.Dataset()
        dataset.add_samples(
            [
                fo.Sample(
                    filepath="/path/to/image1.png",
                    numeric_field=1.0,
                    numeric_list_field=[1, 2, 3],
                ),
                fo.Sample(
                    filepath="/path/to/image2.png",
                    numeric_field=4.0,
                    numeric_list_field=[1, 2],
                ),
                fo.Sample(
                    filepath="/path/to/image3.png",
                    numeric_field=None,
                    numeric_list_field=None,
                ),
            ]
        )

        #
        # Compute the standard deviation of a numeric field
        #

        aggregation = fo.Std("numeric_field")
        std = dataset.aggregate(aggregation)
        print(std)  # the standard deviation

        #
        # Compute the standard deviation of a numeric list field
        #

        aggregation = fo.Std("numeric_list_field")
        std = dataset.aggregate(aggregation)
        print(std)  # the standard deviation

        #
        # Compute the standard deviation of a transformation of a numeric field
        #

        aggregation = fo.Std("numeric_field", expr=2 * (F() + 1))
        std = dataset.aggregate(aggregation)
        print(std)  # the standard deviation

    Args:
        field_name: the name of the field to operate on
        expr (None): an optional
            :class:`fiftyone.core.expressions.ViewExpression` or
            `MongoDB expression <https://docs.mongodb.com/manual/meta/aggregation-quick-reference/#aggregation-expressions>`_
            to apply to the field before aggregating
        sample (False): whether to compute the sample standard deviation rather
            than the population standard deviation
    """

    def __init__(self, field_name, expr=None, sample=False):
        super().__init__(field_name, expr=expr)
        self._sample = sample

    def default_result(self):
        """Returns the default result for this aggregation.

        Returns:
            ``0``
        """
        return 0

    def parse_result(self, d):
        """Parses the output of :meth:`to_mongo`.

        Args:
            d: the result dict

        Returns:
            the standard deviation
        """
        return d["std"]

    def to_mongo(self, sample_collection):
        path, pipeline = self._parse_field_name(sample_collection)

        op = "$stdDevSamp" if self._sample else "$stdDevPop"
        pipeline.append({"$group": {"_id": None, "std": {op: "$" + path}}})

        return pipeline


class Sum(Aggregation):
    """Computes the sum of the field values of a collection.

    ``None``-valued fields are ignored.

    This aggregation is typically applied to *numeric* field types (or lists of
    such types):

    -   :class:`fiftyone.core.fields.IntField`
    -   :class:`fiftyone.core.fields.FloatField`

    Examples::

        import fiftyone as fo

        dataset = fo.Dataset()
        dataset.add_samples(
            [
                fo.Sample(
                    filepath="/path/to/image1.png",
                    numeric_field=1.0,
                    numeric_list_field=[1, 2, 3],
                ),
                fo.Sample(
                    filepath="/path/to/image2.png",
                    numeric_field=4.0,
                    numeric_list_field=[1, 2],
                ),
                fo.Sample(
                    filepath="/path/to/image3.png",
                    numeric_field=None,
                    numeric_list_field=None,
                ),
            ]
        )

        #
        # Compute the sum of a numeric field
        #

        aggregation = fo.Sum("numeric_field")
        total = dataset.aggregate(aggregation)
        print(total)  # the sum

        #
        # Compute the sum of a numeric list field
        #

        aggregation = fo.Sum("numeric_list_field")
        total = dataset.aggregate(aggregation)
        print(total)  # the sum

        #
        # Compute the sum of a transformation of a numeric field
        #

        aggregation = fo.Sum("numeric_field", expr=2 * (F() + 1))
        total = dataset.aggregate(aggregation)
        print(total)  # the sum

    Args:
        field_name: the name of the field to operate on
        expr (None): an optional
            :class:`fiftyone.core.expressions.ViewExpression` or
            `MongoDB expression <https://docs.mongodb.com/manual/meta/aggregation-quick-reference/#aggregation-expressions>`_
            to apply to the field before aggregating
    """

    def default_result(self):
        """Returns the default result for this aggregation.

        Returns:
            ``0``
        """
        return 0

    def parse_result(self, d):
        """Parses the output of :meth:`to_mongo`.

        Args:
            d: the result dict

        Returns:
            the sum
        """
        return d["sum"]

    def to_mongo(self, sample_collection):
        path, pipeline = self._parse_field_name(sample_collection)

        pipeline.append({"$group": {"_id": None, "sum": {"$sum": "$" + path}}})

        return pipeline


def _parse_field_name(sample_collection, field_name, expr=None):
    path, is_frame_field, list_fields = sample_collection._parse_field_name(
        field_name
    )

    if is_frame_field:
        pipeline = [
            {"$unwind": "$frames"},
            {"$replaceRoot": {"newRoot": "$frames"}},
        ]
    else:
        pipeline = []

    if expr is not None:
        # Don't unroll terminal lists unless explicitly requested
        list_fields = [lf for lf in list_fields if lf != field_name]

    for list_field in list_fields:
        pipeline.append({"$unwind": "$" + list_field})

    if expr is not None:
        expr = _get_mongo_expr(expr, prefix="$" + path)
        pipeline.append({"$project": {path: expr}})
    else:
        pipeline.append({"$project": {path: True}})

    return path, pipeline


def _get_mongo_expr(expr, prefix=None):
    if isinstance(expr, foe.ViewExpression):
        return expr.to_mongo(prefix=prefix)

    return expr
