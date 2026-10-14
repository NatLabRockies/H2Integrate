
(model-overview)=
# Model Overview
Currently, H2I recognizes five types of models:

- [Resource](#resource)
- [Converter](#converters)
- [Transport](#transport)
- [Storage](#storage)
- [Controllers](#controller)
- [Reliability](#reliability)

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
