
(model-overview)=
# Model Overview
Currently, H2I recognizes five types of models:

```{eval-rst}

.. grid:: 1 1 2 3
    :gutter: 2 3 4 4

    .. grid-item-card::

        Technology Models
        ^^^

        Listing and in-depth descriptions of each of technologies for energy generation
        or conversion.

        +++

        .. button-ref:: ../technology_models/index
            :expand:
            :color: secondary
            :click-parent:

            To the technology reference.

    .. grid-item-card::

        Storage Models
        ^^^

        Guide to energy storage models.

        +++

        .. button-ref:: ../storage/storage_models_index
            :expand:
            :color: secondary
            :click-parent:

            To the storage reference

    .. grid-item-card::

        Resource Models
        ^^^

        Explanations, background, configuration, and usage of the resource (tides, solar, wind, etc.).

        +++

        .. button-ref:: ../resource/index
            :expand:
            :color: secondary
            :click-parent:

            To the resource reference

    .. grid-item-card::

        Control Models
        ^^^

        Guide to controlled energy dispatching and optimization.

        +++

        .. button-ref:: ../control/index
            :expand:
            :color: secondary
            :click-parent:

            To the controller reference

    .. grid-item-card::

        Demand Models
        ^^^

        Learn more about commodity demand profiling.

        +++

        .. button-ref:: ../demand/index
            :expand:
            :color: secondary
            :click-parent:

            To the demand reference

    .. grid-item-card::

        Finance Models
        ^^^

        Learn more about financial modeling.

        +++

        .. button-ref:: ../finance_models/finance_index
            :expand:
            :color: secondary
            :click-parent:

            To the finance reference

    .. grid-item-card::

        Reliability Modeling
        ^^^

        Learn more about modeling system and component availability.

        +++

        .. button-ref:: ../reliability/reliability_guide
            :expand:
            :color: secondary
            :click-parent:

            To the reliability reference
```

(resource)=
## Resource
`Resource` models process resource data that is usually passed to a technology model. See {ref}`Resource models <resource-models>` for available models.


(converters)=
## Converters
`Converter` models are technologies that:
- converts energy available in the 'Primary Input' to another form of energy ('Primary Commodity') OR
- consumes the 'Primary Input' (and perhaps secondary inputs or feedstocks), which is converted to the 'Primary Commodity' through some process

```{note}
When the Primary Commodity is electricity, those converters are considered electricity producing technologies and their electricity production is summed for financial calculations.
```

See {ref}`Converter models <converter-models>` for the full list of available converter technologies.

(transport)=
## Transport
`Transport` models are used to either:
- connect the 'Transport Commodity' from a technology that produces the 'Transport Commodity' to a technology that consumes or stores the 'Transport Commodity' OR
- combine multiple input streams of the 'Transport Commodity' into a single stream
- split a single input stream of the 'Transport Commodity' into multiple output streams

Connection: `[source_tech, dest_tech, transport_commodity, transport_technology]`

See {ref}`Transport models <transport-models>` for available models.

(storage)=
## Storage
`Storage` technologies input and output the 'Storage Commodity' at different times. These technologies can be filled or charged, then unfilled or discharged at some later time. These models are usually constrained by two key model parameters: storage capacity and charge/discharge rate.

See {ref}`Storage models <storage-models>` for available models.

(control)=
(controller)=
## Control
`Control` models are used to control the `Storage` models and resource flows.

See {ref}`Control models <control-models>` for available models.

(reliability)=
## Reliability
`PerformanceReliability` acts as a WOMBAT-lite means of modeling failure and maintenance events with
optionally varying downtime durations that can be integrated into performance models as desired.
As such, they make no use of the OpenMDAO infrastructure and sit outside of the `supported_models`
framework. Please see [reliability user guide](#reliability-guide) for available models and
more details.

See the [registered model catalog](model_registry.md) for all available models.
